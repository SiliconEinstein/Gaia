"""Bayes lowering — ``Prediction`` / ``ModelComparison`` → Gaia IR.

Dispatches on :class:`Prediction` and :class:`ModelComparison` (the
Actions produced by :func:`predict` and :func:`compare`), and reads the
unified ``metadata["observation"]`` / ``metadata["prediction"]`` schema.

What this module owns:

* Helper Claims compiled from ``Prediction`` actions get their
  ``metadata["prediction"]`` finalised with the IR-side reference shape
  (knowledge IDs in place of runtime object references).
* ``ModelComparison`` actions emit one ``infer`` strategy per hypothesis
  whose CPT is ``[0.5, clamp(LR_i)]`` with ``LR_i = exp(logL_i - logL_max)``.
* Exclusivity contracts ("pairwise_contradiction" /
  "exhaustive_pairwise_complement" / "none") emit Structural Actions and
  the clamped Disjunction helper operator for ≥3 hypotheses.

What this module does NOT own:

* Reading observation value or noise out of ``claim.formula`` — value and
  noise live exclusively in ``metadata["observation"]``.
* Any compatibility shim for an earlier in-flight Bayes surface. The
  legacy ``bayes.model`` / ``bayes.likelihood`` / ``bayes.data`` verbs
  and the typed-value ``bayes.Normal`` aliases were removed in the
  unified-design clean break.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from gaia.engine.bayes.distributions.base import _is_deferred_reference
from gaia.engine.bayes.runtime import ModelComparison, PrecomputedLikelihoods, Prediction
from gaia.engine.bp.factor_graph import CROMWELL_EPS
from gaia.engine.ir import Knowledge as IrKnowledge
from gaia.engine.ir import Operator as IrOperator
from gaia.engine.ir import Strategy as IrStrategy
from gaia.engine.ir.knowledge import KnowledgeType, make_qid
from gaia.engine.ir.operator import OperatorType
from gaia.engine.ir.strategy import StrategyType
from gaia.engine.lang.formula.connective import Land
from gaia.engine.lang.formula.predicate import Equals
from gaia.engine.lang.formula.term import Constant
from gaia.engine.lang.runtime import Claim, Distribution, Knowledge, Variable


@dataclass(frozen=True)
class BayesLoweringResult:
    """IR additions and metadata updates emitted by Bayes lowering."""

    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    action_label_map: dict[str, str] = field(default_factory=dict)
    target_action_labels_by_id: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------


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
    """Lower ``Prediction`` and ``ModelComparison`` actions to IR."""
    del knowledge_nodes
    knowledges: list[IrKnowledge] = []
    operators: list[IrOperator] = []
    strategies: list[IrStrategy] = []
    metadata_updates: dict[str, dict[str, Any]] = {}
    action_label_map: dict[str, str] = {}
    target_action_labels_by_id: dict[str, str] = {}
    existing_relations = _existing_relations(existing_operators or [])
    labels_by_object = action_labels_by_object or {}

    # Phase 1: settle prediction helper metadata with IR-side references.
    for action in actions:
        if not isinstance(action, Prediction):
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

    # Phase 2: lower model-comparison actions into infer strategies.
    for action in actions:
        if not isinstance(action, ModelComparison):
            continue
        action_label = labels_by_object.get(id(action))
        lowered = _lower_comparison(
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


# ---------------------------------------------------------------------------
# Prediction metadata
# ---------------------------------------------------------------------------


def _prediction_metadata(
    action: Prediction,
    knowledge_map: dict[int, str],
    *,
    action_label: str | None,
) -> dict[str, Any]:
    if action.hypothesis is None or action.target is None or action.distribution is None:
        raise ValueError("Bayes Prediction action requires hypothesis, target, distribution")
    payload = {
        "kind": "prediction",
        "distribution": action.distribution.model_dump(),
        "hypothesis": knowledge_map[id(action.hypothesis)],
        "hypotheses": [knowledge_map[id(action.hypothesis)]],
        "target": _target_descriptor(action.target),
    }
    metadata: dict[str, Any] = {"prediction": payload}
    if action_label:
        metadata["review_target"] = {"action_label": action_label, "pattern": "prediction"}
    return metadata


def _target_descriptor(target: Variable | Distribution) -> dict[str, Any]:
    if isinstance(target, Variable):
        domain = getattr(target.domain, "name", None) or getattr(target.domain, "label", None)
        return {"kind": "variable", "symbol": target.symbol, "domain": domain}
    return {
        "kind": "distribution",
        "label": target.label,
        "family": target.kind,
    }


# ---------------------------------------------------------------------------
# ModelComparison → IR strategies
# ---------------------------------------------------------------------------


def _prediction_action(helper: Claim) -> Prediction:
    for candidate in helper.from_actions:
        if isinstance(candidate, Prediction) and candidate.helper is helper:
            return candidate
    raise ValueError(f"{helper.label or helper.content!r} is not a predict() helper")


def _comparison_prediction_actions(action: ModelComparison) -> tuple[Prediction, ...]:
    if not action.models:
        raise ValueError("Bayes ModelComparison action requires models")
    return tuple(_prediction_action(helper) for helper in action.models)


def _comparison_hypotheses(action: ModelComparison) -> tuple[Claim, ...]:
    hypotheses = tuple(p.hypothesis for p in _comparison_prediction_actions(action))
    if any(h is None for h in hypotheses):
        raise ValueError("predict() action is missing its hypothesis")
    return tuple(h for h in hypotheses if h is not None)


def _lower_comparison(
    action: ModelComparison,
    *,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    action_label: str | None,
    existing_relations: set[tuple[str, frozenset[str]]],
) -> BayesLoweringResult:
    if action.helper is None:
        raise ValueError("Bayes ModelComparison action requires helper")
    cmp_id = knowledge_map[id(action.helper)]
    model_ids = [knowledge_map[id(m)] for m in action.models]
    data_ids = [knowledge_map[id(d)] for d in action.data]
    prediction_actions = _comparison_prediction_actions(action)
    hypotheses = _comparison_hypotheses(action)

    likelihoods = _likelihoods(action, prediction_actions)
    action.log_likelihoods = dict(likelihoods)
    if not any(math.isfinite(value) for value in likelihoods.values()):
        raise ValueError(
            f"BayesCompareError: comparison {action.label or action.helper.content!r} has zero "
            "support under every hypothesis. Fix: check the observation value, the "
            "predictive distribution support, or use precomputed likelihoods."
        )

    comparison_metadata = {
        "kind": "comparison",
        "exclusivity": action.exclusivity,
        "likelihoods": {knowledge_map[id(h)]: value for h, value in likelihoods.items()},
        "data": data_ids,
        "models": model_ids,
        "hypotheses": [knowledge_map[id(h)] for h in hypotheses],
    }
    if isinstance(action.precomputed, PrecomputedLikelihoods):
        comparison_metadata["precomputed_source"] = knowledge_map[id(action.precomputed)]

    metadata_updates = {
        cmp_id: {
            "comparison": comparison_metadata,
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
            "comparison_factor": {
                "kind": "comparison_factor",
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


# ---------------------------------------------------------------------------
# Likelihood evaluation
# ---------------------------------------------------------------------------


def _likelihoods(
    action: ModelComparison,
    prediction_actions: tuple[Prediction, ...],
) -> dict[Claim, float]:
    if action.precomputed is not None and action.log_likelihoods:
        # The DSL verb already validated and stored these; just hand them back
        # in the iteration order matching prediction_actions.
        out: dict[Claim, float] = {}
        for p_action in prediction_actions:
            if p_action.hypothesis is None:
                raise ValueError("Bayes Prediction action is missing its hypothesis")
            out[p_action.hypothesis] = float(action.log_likelihoods[p_action.hypothesis])
        return out

    likelihoods: dict[Claim, float] = {}
    for p_action in prediction_actions:
        if p_action.hypothesis is None or p_action.distribution is None or p_action.target is None:
            raise ValueError("Bayes Prediction action is incomplete")
        hypothesis = p_action.hypothesis
        distribution_impl = _bind_distribution_impl(p_action.distribution, hypothesis)
        total = 0.0
        for data_claim in action.data:
            value = _observation_value(data_claim, p_action.target)
            noise = _observation_noise(data_claim)
            total += _log_likelihood(distribution_impl, value, noise)
        likelihoods[hypothesis] = total
    return likelihoods


def _bind_distribution_impl(distribution: Distribution, hypothesis: Claim) -> Any:
    """Bind deferred Variable params on a Distribution Knowledge → concrete _impl.

    Returns the underlying pydantic ``_BaseDistribution`` with concrete
    params, ready for logpdf/logpmf.
    """
    impl = distribution.impl
    bindings = _claim_parameter_bindings(hypothesis)
    params: dict[str, Any] = {}
    for name, value in impl.params.items():
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
    return impl._replace_params(params)


@dataclass(frozen=True)
class _Bindings:
    by_object: dict[int, Any]
    by_symbol: dict[str, list[Any]]


def _claim_parameter_bindings(claim: Claim) -> _Bindings:
    """Walk a hypothesis claim's formula and harvest Variable→value bindings.

    Hypothesis formulas are expected to be ``Equals(variable, Constant)``
    or conjunctions thereof — exactly what :func:`parameter` produces.
    """
    by_object: dict[int, Any] = {}
    by_symbol: dict[str, list[Any]] = {}
    for variable, value in _equals_variable_constant_pairs(getattr(claim, "formula", None)):
        by_object[id(variable)] = value
        by_symbol.setdefault(variable.symbol, []).append(value)
    return _Bindings(by_object=by_object, by_symbol=by_symbol)


def _equals_variable_constant_pairs(formula: Any) -> list[tuple[Variable, Any]]:
    """Extract (Variable, value) bindings from Equals / Land(Equals, ...) formulas."""
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


def _observation_value(data_claim: Claim, target: Variable | Distribution) -> Any:
    """Read the observed value from the unified metadata['observation'] schema.

    The match between observation and prediction targets is by Python
    object identity (Variable / Distribution Knowledge); symbol-name
    fallback is permitted for Variables to support hand-built data
    Claims.
    """
    observation = (data_claim.metadata or {}).get("observation")
    if not isinstance(observation, dict):
        raise ValueError(
            f"compare() data {data_claim.label or data_claim.content!r} has no "
            "metadata['observation'] payload (use observe(target, value=...))"
        )
    observed_target = observation.get("target")
    if observed_target is not target:
        # Fall back to symbol match for Variables only. Distribution targets
        # are Knowledge objects and must match by identity so observations
        # for one measured quantity cannot silently feed another.
        if isinstance(target, Variable) and isinstance(observed_target, Variable):
            if observed_target.symbol != target.symbol:
                raise ValueError(
                    f"compare() data target {observed_target!r} does not match "
                    f"prediction target {target!r}"
                )
        else:
            raise ValueError(
                f"compare() data {data_claim.label or data_claim.content!r} target "
                f"{observed_target!r} does not match prediction target {target!r}"
            )
    if "value" not in observation:
        raise ValueError(
            f"compare() data {data_claim.label or data_claim.content!r} "
            "metadata['observation'] is missing 'value'"
        )
    return observation["value"]


def _observation_noise(data_claim: Claim) -> Distribution | None:
    """Read the noise Distribution from the unified observation schema (or None)."""
    observation = (data_claim.metadata or {}).get("observation")
    if not isinstance(observation, dict):
        return None
    noise = observation.get("noise")
    if noise is None:
        return None
    if not isinstance(noise, Distribution):
        raise TypeError(
            f"compare() data {data_claim.label or data_claim.content!r} noise must be a "
            f"Distribution Knowledge object or None; got {type(noise).__name__}"
        )
    return noise


def _log_likelihood(
    distribution_impl: Any,
    value: Any,
    noise: Distribution | None,
) -> float:
    """Evaluate log P(value | distribution_impl), folding in optional noise."""
    if noise is None:
        if distribution_impl.kind in {"betabinomial", "binomial", "poisson"}:
            return float(distribution_impl.logpmf(value))
        return float(distribution_impl.logpdf(float(value)))
    return _log_likelihood_with_noise(distribution_impl, value, noise)


def _log_likelihood_with_noise(
    distribution_impl: Any,
    value: Any,
    noise: Distribution,
) -> float:
    """Convolve predictive with Normal additive noise."""
    if noise.kind != "normal":
        raise NotImplementedError("Bayes compare currently supports only Normal additive noise")
    noise_impl = noise.impl
    sigma = float(noise_impl.params["sigma"])
    low, high = distribution_impl.support()
    if distribution_impl.kind in {"betabinomial", "binomial", "poisson"}:
        if not math.isfinite(high):
            high = max(int(value + 10 * sigma), int(value) + 50)
        terms = []
        for x in range(int(low), int(high) + 1):
            terms.append(distribution_impl.logpmf(x) + noise_impl.logpdf(float(value) - x))
        return _logsumexp(terms)

    from scipy.integrate import quad

    def integrand(x: float) -> float:
        return math.exp(distribution_impl.logpdf(x) + noise_impl.logpdf(float(value) - x))

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


# ---------------------------------------------------------------------------
# Exhaustive disjunction helper (≥3 hypotheses + exhaustive_pairwise_complement)
# ---------------------------------------------------------------------------


def _exhaustive_disjunction_operator(
    hypotheses: list[Claim],
    action: ModelComparison,
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

    label = _helper_label("compare_exhaustive", cmp_id)
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
            "comparison": {"auto_generated_by": f"compare:{cmp_id}"},
        },
    )
    op = IrOperator(
        operator_id=_operator_id("disjunction", variables, helper_id),
        scope="local",
        operator=OperatorType.DISJUNCTION,
        variables=variables,
        conclusion=helper_id,
        metadata={"comparison": {"auto_generated_by": f"compare:{cmp_id}"}},
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


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))
