"""Lower Bayes runtime claims into existing Gaia IR strategies/operators."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.ir import Knowledge as IrKnowledge
from gaia.ir import Operator as IrOperator
from gaia.ir import Strategy as IrStrategy
from gaia.ir.knowledge import KnowledgeType, make_qid
from gaia.lang.bayes.distributions.base import _is_deferred_reference
from gaia.lang.bayes.runtime import ComparisonResult, PredictiveModel
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


def lower_bayes_claims(
    knowledge_nodes: list[Knowledge],
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    existing_operators: list[IrOperator] | None = None,
) -> BayesLoweringResult:
    knowledges: list[IrKnowledge] = []
    operators: list[IrOperator] = []
    strategies: list[IrStrategy] = []
    metadata_updates: dict[str, dict[str, Any]] = {}
    existing_relations = _existing_relations(existing_operators or [])

    for node in knowledge_nodes:
        if isinstance(node, PredictiveModel):
            metadata_updates[knowledge_map[id(node)]] = _prediction_metadata(node, knowledge_map)

    for node in knowledge_nodes:
        if not isinstance(node, ComparisonResult):
            continue
        lowered = _lower_comparison(
            node,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            existing_relations=existing_relations,
        )
        knowledges.extend(lowered.knowledges)
        operators.extend(lowered.operators)
        strategies.extend(lowered.strategies)
        metadata_updates.update(lowered.metadata_updates)
        existing_relations.update(_existing_relations(lowered.operators))

    return BayesLoweringResult(
        knowledges=knowledges,
        operators=operators,
        strategies=strategies,
        metadata_updates=metadata_updates,
    )


def _prediction_metadata(model: PredictiveModel, knowledge_map: dict[int, str]) -> dict[str, Any]:
    return {
        "bayes": {
            "role": "prediction",
            "distribution": model.distribution.model_dump(),
            "hypotheses": [knowledge_map[id(h)] for h in model.hypotheses],
            "observable": _variable_descriptor(model.observable),
        }
    }


def _lower_comparison(
    result: ComparisonResult,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    existing_relations: set[tuple[str, frozenset[str]]],
) -> BayesLoweringResult:
    cmp_id = knowledge_map[id(result)]
    model_id = knowledge_map[id(result.via)]
    data_ids = [knowledge_map[id(d)] for d in result.data]
    likelihoods = _comparison_likelihoods(result)
    if not any(math.isfinite(value) for value in likelihoods.values()):
        raise ValueError(
            f"BayesLikelihoodError: likelihood {result.label or result.content!r} has zero "
            "support under every hypothesis. Fix: check the observation value, the "
            "predictive distribution support, or use precomputed likelihoods."
        )

    metadata_updates = {
        cmp_id: {
            "bayes": {
                "role": "comparison",
                "exclusivity": result.exclusivity,
                "likelihoods": {knowledge_map[id(h)]: value for h, value in likelihoods.items()},
                "data": data_ids,
                "model": model_id,
            }
        }
    }

    log_l_max = max(likelihoods.values())
    strategies = []
    for hypothesis, log_likelihood in likelihoods.items():
        lr = math.exp(log_likelihood - log_l_max)
        p1 = _clamp((1.0 - CROMWELL_EPS) * lr)
        h_id = knowledge_map[id(hypothesis)]
        strategies.append(
            IrStrategy(
                scope="local",
                type="infer",
                premises=[h_id],
                conclusion=cmp_id,
                conditional_probabilities=[0.5, p1],
                metadata={
                    "bayes": {
                        "role": "likelihood_factor",
                        "comparison": cmp_id,
                        "hypothesis": h_id,
                        "log_likelihood": log_likelihood,
                    }
                },
            )
        )

    helper_knowledges, operators = _exclusivity_operators(
        list(likelihoods),
        result,
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
    )


def _comparison_likelihoods(result: ComparisonResult) -> dict[Claim, float]:
    if result.precomputed is not None:
        return {hypothesis: float(value) for hypothesis, value in result.precomputed.items()}

    likelihoods: dict[Claim, float] = {}
    for hypothesis in result.via.hypotheses:
        distribution = _bind_distribution(result.via.distribution, hypothesis)
        total = 0.0
        for data_claim in result.data:
            value = _observation_value(data_claim, result.via.observable)
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
        return distribution.logpmf(value)
    return distribution.logpdf(float(value))


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


def _exclusivity_operators(
    hypotheses: list[Claim],
    result: ComparisonResult,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    cmp_id: str,
    existing_relations: set[tuple[str, frozenset[str]]],
) -> tuple[list[IrKnowledge], list[IrOperator]]:
    if result.exclusivity == "none" or len(hypotheses) < 2:
        return [], []
    if result.exclusivity == "exhaustive_pairwise_complement" and len(hypotheses) == 2:
        relation_key = ("complement", frozenset(knowledge_map[id(h)] for h in hypotheses))
        if relation_key in existing_relations:
            return [], []
        return _pair_operator(
            "complement",
            hypotheses[0],
            hypotheses[1],
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            cmp_id=cmp_id,
        )

    knowledges: list[IrKnowledge] = []
    operators: list[IrOperator] = []
    for a, b in combinations(hypotheses, 2):
        a_id = knowledge_map[id(a)]
        b_id = knowledge_map[id(b)]
        if ("contradiction", frozenset([a_id, b_id])) in existing_relations:
            continue
        helper, op = _pair_operator(
            "contradiction",
            a,
            b,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            cmp_id=cmp_id,
        )
        knowledges.extend(helper)
        operators.extend(op)

    if result.exclusivity == "exhaustive_pairwise_complement":
        label = _helper_label("bayes_exhaustive", cmp_id)
        helper_id = make_qid(namespace, package_name, label)
        knowledges.append(
            IrKnowledge(
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
        )
        operators.append(
            IrOperator(
                operator_id=_operator_id(
                    "disjunction", [knowledge_map[id(h)] for h in hypotheses], helper_id
                ),
                scope="local",
                operator="disjunction",
                variables=[knowledge_map[id(h)] for h in hypotheses],
                conclusion=helper_id,
                metadata={"bayes": {"auto_generated_by": f"likelihood:{cmp_id}"}},
            )
        )
    return knowledges, operators


def _pair_operator(
    operator: str,
    a: Claim,
    b: Claim,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    cmp_id: str,
) -> tuple[list[IrKnowledge], list[IrOperator]]:
    a_id = knowledge_map[id(a)]
    b_id = knowledge_map[id(b)]
    label = _helper_label(f"bayes_{operator}", "|".join(sorted([cmp_id, a_id, b_id])))
    helper_id = make_qid(namespace, package_name, label)
    helper = IrKnowledge(
        id=helper_id,
        label=label,
        type=KnowledgeType.CLAIM,
        content=f"Bayes auto-generated {operator} constraint.",
        metadata={
            "generated": True,
            "review": False,
            "helper_kind": f"{operator}_result",
            "bayes": {"auto_generated_by": f"likelihood:{cmp_id}"},
        },
    )
    op = IrOperator(
        operator_id=_operator_id(operator, [a_id, b_id], helper_id),
        scope="local",
        operator=operator,
        variables=[a_id, b_id],
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
