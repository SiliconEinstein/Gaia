"""Lower Bayes runtime actions into existing Gaia IR strategies/operators."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.ir import Knowledge as IrKnowledge
from gaia.ir import Operator as IrOperator
from gaia.ir import Strategy as IrStrategy
from gaia.ir.knowledge import KnowledgeType, make_qid
from gaia.ir.operator import OperatorType
from gaia.ir.strategy import StrategyType
from gaia.lang.bayes.distributions.base import _is_deferred_reference
from gaia.lang.bayes.runtime import Likelihood, PredictiveModel
from gaia.lang.formula.connective import Land
from gaia.lang.formula.predicate import Equals
from gaia.lang.formula.term import Constant
from gaia.lang.runtime import Claim, Knowledge, Variable


@dataclass(frozen=True)
class BayesLoweringResult:
    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    action_label_map: dict[str, str] = field(default_factory=dict)
    target_action_labels_by_id: dict[str, str] = field(default_factory=dict)


def lower_bayes_claims(
    knowledge_nodes: list[Knowledge],
    *,
    actions: list[Any] | tuple[Any, ...] = (),
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    action_labels_by_object: dict[int, str] | None = None,
    existing_operators: list[IrOperator] | None = None,
) -> BayesLoweringResult:
    knowledges: list[IrKnowledge] = []
    operators: list[IrOperator] = []
    strategies: list[IrStrategy] = []
    metadata_updates: dict[str, dict[str, Any]] = {}
    action_label_map: dict[str, str] = {}
    target_action_labels_by_id: dict[str, str] = {}
    existing_relations = _existing_relations(existing_operators or [])
    labels_by_object = action_labels_by_object or {}

    for action in actions:
        if not isinstance(action, PredictiveModel):
            continue
        action_label = labels_by_object.get(id(action))
        helper_id = knowledge_map[id(action.helper)]
        metadata_updates[helper_id] = _prediction_metadata(
            action,
            knowledge_map,
            action_label=action_label,
        )
        if action_label:
            action_label_map[action_label] = helper_id
            target_action_labels_by_id[helper_id] = action_label

    for action in actions:
        if not isinstance(action, Likelihood):
            continue
        action_label = labels_by_object.get(id(action))
        lowered = _lower_likelihood(
            action,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            action_label=action_label,
            existing_relations=existing_relations,
        )
        knowledges.extend(lowered.knowledges)
        operators.extend(lowered.operators)
        strategies.extend(lowered.strategies)
        metadata_updates.update(lowered.metadata_updates)
        action_label_map.update(lowered.action_label_map)
        target_action_labels_by_id.update(lowered.target_action_labels_by_id)
        existing_relations.update(_existing_relations(lowered.operators))

    return BayesLoweringResult(
        knowledges=knowledges,
        operators=operators,
        strategies=strategies,
        metadata_updates=metadata_updates,
        action_label_map=action_label_map,
        target_action_labels_by_id=target_action_labels_by_id,
    )


def _prediction_metadata(
    action: PredictiveModel,
    knowledge_map: dict[int, str],
    *,
    action_label: str | None,
) -> dict[str, Any]:
    if action.hypothesis is None or action.observable is None or action.distribution is None:
        raise ValueError(
            "Bayes PredictiveModel action requires hypothesis, observable, distribution"
        )
    bayes = {
        "role": "prediction",
        "distribution": action.distribution.model_dump(),
        "hypothesis": knowledge_map[id(action.hypothesis)],
        "hypotheses": [knowledge_map[id(action.hypothesis)]],
        "observable": _variable_descriptor(action.observable),
    }
    payload: dict[str, Any] = {"bayes": bayes}
    if action_label:
        payload["review_target"] = {"action_label": action_label, "pattern": "prediction"}
    return payload


def _model_action(helper: Claim) -> PredictiveModel:
    for action in helper.supports:
        if isinstance(action, PredictiveModel) and action.helper is helper:
            return action
    raise ValueError(f"{helper.label or helper.content!r} is not a bayes.model() helper")


def _likelihood_model_actions(action: Likelihood) -> tuple[PredictiveModel, ...]:
    if action.model is None:
        raise ValueError("Bayes Likelihood action requires model")
    return (_model_action(action.model), *(_model_action(helper) for helper in action.against))


def _model_hypotheses(action: Likelihood) -> tuple[Claim, ...]:
    hypotheses = tuple(
        model_action.hypothesis for model_action in _likelihood_model_actions(action)
    )
    if any(hypothesis is None for hypothesis in hypotheses):
        raise ValueError("Bayes PredictiveModel action is missing a hypothesis")
    return tuple(hypothesis for hypothesis in hypotheses if hypothesis is not None)


def _lower_likelihood(
    action: Likelihood,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    action_label: str | None,
    existing_relations: set[tuple[str, frozenset[str]]],
) -> BayesLoweringResult:
    if action.helper is None or action.model is None:
        raise ValueError("Bayes Likelihood action requires helper and model")
    cmp_id = knowledge_map[id(action.helper)]
    model_id = knowledge_map[id(action.model)]
    against_ids = [knowledge_map[id(model)] for model in action.against]
    data_ids = [knowledge_map[id(d)] for d in action.data]
    model_actions = _likelihood_model_actions(action)
    hypotheses = _model_hypotheses(action)
    likelihoods = _likelihoods(action, model_actions)
    action.log_likelihoods = dict(likelihoods)
    if not any(math.isfinite(value) for value in likelihoods.values()):
        raise ValueError(
            f"BayesLikelihoodError: likelihood {action.label or action.helper.content!r} has zero "
            "support under every hypothesis. Fix: check the observation value, the "
            "predictive distribution support, or use precomputed likelihoods."
        )

    metadata_updates = {
        cmp_id: {
            "bayes": {
                "role": "comparison",
                "exclusivity": action.exclusivity,
                "likelihoods": {knowledge_map[id(h)]: value for h, value in likelihoods.items()},
                "data": data_ids,
                "model": model_id,
                "against": against_ids,
                "hypotheses": [knowledge_map[id(h)] for h in hypotheses],
            }
        }
    }

    log_l_max = max(likelihoods.values())
    strategies = []
    target_action_labels_by_id: dict[str, str] = {}
    for hypothesis, log_likelihood in likelihoods.items():
        lr = math.exp(log_likelihood - log_l_max)
        p1 = _clamp((1.0 - CROMWELL_EPS) * lr)
        h_id = knowledge_map[id(hypothesis)]
        metadata: dict[str, Any] = {
            "pattern": "inference",
            "bayes": {
                "role": "likelihood_factor",
                "comparison": cmp_id,
                "hypothesis": h_id,
                "log_likelihood": log_likelihood,
            },
        }
        if action_label:
            metadata["action_label"] = action_label
        strategy = IrStrategy(
            scope="local",
            type=StrategyType.INFER,
            premises=[h_id],
            conclusion=cmp_id,
            conditional_probabilities=[0.5, p1],
            metadata=metadata,
        )
        strategies.append(strategy)
        if action_label and strategy.strategy_id:
            target_action_labels_by_id[strategy.strategy_id] = action_label

    helper_knowledges, operators = _exhaustive_disjunction_operator(
        list(hypotheses),
        action,
        namespace=namespace,
        package_name=package_name,
        knowledge_map=knowledge_map,
        cmp_id=cmp_id,
        existing_relations=existing_relations,
    )
    return BayesLoweringResult(
        knowledges=helper_knowledges,
        operators=operators,
        strategies=strategies,
        metadata_updates=metadata_updates,
        action_label_map={action_label: cmp_id} if action_label else {},
        target_action_labels_by_id=target_action_labels_by_id,
    )


def _likelihoods(
    action: Likelihood,
    model_actions: tuple[PredictiveModel, ...],
) -> dict[Claim, float]:
    if action.precomputed is not None:
        hypotheses = {
            model_action.hypothesis
            for model_action in model_actions
            if model_action.hypothesis is not None
        }
        for key in action.precomputed:
            if not isinstance(key, Claim) or key not in hypotheses:
                raise ValueError("precomputed likelihood keys must be original hypothesis Claims")
        provided = set(action.precomputed)
        if provided != hypotheses:
            missing = sorted((claim.label or claim.content for claim in hypotheses - provided))
            details = []
            if missing:
                details.append(f"missing {missing}")
            suffix = f": {', '.join(details)}" if details else ""
            raise ValueError(
                "precomputed likelihoods must cover exactly the model hypotheses" + suffix
            )
        return {hypothesis: float(value) for hypothesis, value in action.precomputed.items()}
    likelihoods: dict[Claim, float] = {}
    for model_action in model_actions:
        if (
            model_action.hypothesis is None
            or model_action.distribution is None
            or model_action.observable is None
        ):
            raise ValueError("Bayes PredictiveModel action is incomplete")
        hypothesis = model_action.hypothesis
        distribution = _bind_distribution(model_action.distribution, hypothesis)
        total = 0.0
        for data_claim in action.data:
            value = _observation_value(data_claim, model_action.observable)
            total += _log_likelihood(distribution, value, data_claim)
        likelihoods[hypothesis] = total
    return likelihoods


def _bind_distribution(distribution: Any, hypothesis: Claim) -> Any:
    bindings = _claim_bindings(hypothesis)
    params: dict[str, Any] = {}
    for name, value in distribution.params.items():
        if _is_deferred_reference(value):
            bound = bindings.by_object.get(id(value))
            if bound is None:
                matches = bindings.by_symbol.get(value.symbol, [])
                if len(matches) == 1:
                    bound = matches[0]
            if bound is None:
                raise ValueError(
                    f"BindingError: Variable {value.symbol!r} is unbound under "
                    f"{hypothesis.label or hypothesis.content!r}. "
                    "Fix: add parameter(variable, value) for this hypothesis."
                )
            params[name] = bound
        else:
            params[name] = value
    return distribution._replace_params(params)


@dataclass(frozen=True)
class _Bindings:
    by_object: dict[int, Any]
    by_symbol: dict[str, list[Any]]


def _claim_bindings(claim: Claim) -> _Bindings:
    by_object: dict[int, Any] = {}
    by_symbol: dict[str, list[Any]] = {}
    for variable, value in _equals_variable_constant_pairs(getattr(claim, "formula", None)):
        by_object[id(variable)] = value
        by_symbol.setdefault(variable.symbol, []).append(value)
    return _Bindings(by_object=by_object, by_symbol=by_symbol)


def _observation_value(claim: Claim, observable: Variable) -> Any:
    values: list[Any] = []
    for variable, value in _equals_variable_constant_pairs(getattr(claim, "formula", None)):
        if variable is observable or variable.symbol == observable.symbol:
            values.append(value)
    if not values:
        raise ValueError(
            f"likelihood() data {claim.label or claim.content!r} has no observation "
            f"for variable {observable.symbol!r}"
        )
    if len(values) > 1:
        raise ValueError(
            f"likelihood() data {claim.label or claim.content!r} has multiple values "
            f"for variable {observable.symbol!r}"
        )
    return values[0]


def _equals_variable_constant_pairs(formula: Any) -> list[tuple[Variable, Any]]:
    if isinstance(formula, Equals):
        left, right = formula.left, formula.right
        if isinstance(left, Variable) and isinstance(right, Constant):
            return [(left, right.value)]
        if isinstance(right, Variable) and isinstance(left, Constant):
            return [(right, left.value)]
        return []
    if isinstance(formula, Land):
        pairs: list[tuple[Variable, Any]] = []
        for operand in formula.operands:
            pairs.extend(_equals_variable_constant_pairs(operand))
        return pairs
    return []


def _log_likelihood(distribution: Any, value: Any, data_claim: Claim) -> float:
    noise_payload = ((data_claim.metadata or {}).get("bayes") or {}).get("noise")
    if noise_payload:
        return _log_likelihood_with_noise(distribution, value, noise_payload)
    if distribution.kind in {"binomial", "poisson"}:
        return float(distribution.logpmf(value))
    return float(distribution.logpdf(float(value)))


def _log_likelihood_with_noise(
    distribution: Any, value: Any, noise_payload: dict[str, Any]
) -> float:
    if noise_payload.get("kind") != "normal":
        raise NotImplementedError("Bayes likelihood currently supports only Normal additive noise")
    from gaia.lang.bayes.distributions.continuous import Normal

    noise = Normal(**noise_payload.get("params", {}))
    low, high = distribution.support()
    if distribution.kind in {"binomial", "poisson"}:
        if not math.isfinite(high):
            high = max(int(value + 10 * noise.params["sigma"]), int(value) + 50)
        terms = []
        for x in range(int(low), int(high) + 1):
            terms.append(distribution.logpmf(x) + noise.logpdf(float(value) - x))
        return _logsumexp(terms)

    from scipy.integrate import quad

    def integrand(x: float) -> float:
        return math.exp(distribution.logpdf(x) + noise.logpdf(float(value) - x))

    integral, _ = quad(integrand, float(low), float(high), limit=100)
    if integral <= 0.0 or not math.isfinite(integral):
        return -math.inf
    return math.log(integral)


def _logsumexp(values: list[float]) -> float:
    finite = [v for v in values if math.isfinite(v)]
    if not finite:
        return -math.inf
    m = max(finite)
    return m + math.log(sum(math.exp(v - m) for v in finite))


def _exhaustive_disjunction_operator(
    hypotheses: list[Claim],
    action: Likelihood,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    cmp_id: str,
    existing_relations: set[tuple[str, frozenset[str]]],
) -> tuple[list[IrKnowledge], list[IrOperator]]:
    if action.exclusivity != "exhaustive_pairwise_complement" or len(hypotheses) < 3:
        return [], []
    variables = [knowledge_map[id(h)] for h in hypotheses]
    relation_key = ("disjunction", frozenset(variables))
    if relation_key in existing_relations:
        return [], []

    label = _helper_label("bayes_exhaustive", cmp_id)
    helper_id = make_qid(namespace, package_name, label)
    helper = IrKnowledge(
        id=helper_id,
        label=label,
        type=KnowledgeType.CLAIM,
        content="At least one Bayes hypothesis in the comparison is true.",
        metadata={
            "generated": True,
            "review": False,
            "helper_kind": "bayes_exhaustive_result",
            "prior": 1.0 - CROMWELL_EPS,
            "bayes": {"auto_generated_by": f"likelihood:{cmp_id}"},
        },
    )
    op = IrOperator(
        operator_id=_operator_id("disjunction", variables, helper_id),
        scope="local",
        operator=OperatorType.DISJUNCTION,
        variables=variables,
        conclusion=helper_id,
        metadata={"bayes": {"auto_generated_by": f"likelihood:{cmp_id}"}},
    )
    return [helper], [op]


def _helper_label(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode()).hexdigest()[:12]
    return f"__{prefix}_{digest}"


_SYMMETRIC_OPS = frozenset(
    {"equivalence", "contradiction", "complement", "disjunction", "conjunction"}
)


def _operator_id(operator: str, variables: list[str], conclusion: str) -> str:
    var_ids = sorted(variables) if operator in _SYMMETRIC_OPS else list(variables)
    raw = f"{operator}|{'|'.join(var_ids)}|{conclusion}"
    return f"lco_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _existing_relations(operators: list[IrOperator]) -> set[tuple[str, frozenset[str]]]:
    relations: set[tuple[str, frozenset[str]]] = set()
    for operator in operators:
        relations.add((str(operator.operator), frozenset(operator.variables)))
    return relations


def _variable_descriptor(variable: Variable) -> dict[str, Any]:
    domain = getattr(variable.domain, "name", None) or getattr(variable.domain, "label", None)
    return {"symbol": variable.symbol, "domain": domain}


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))
