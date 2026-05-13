"""Lower Gaia IR (LocalCanonicalGraph) to gaia.bp.FactorGraph.

Spec: docs/foundations/gaia-ir/07-lowering.md
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from gaia.ir.formalize import formalize_named_strategy
from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.knowledge import KnowledgeType, is_structural_expression_helper
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.review import ReviewManifest, ReviewStatus
from gaia.ir.strategy import (
    _FORMAL_STRATEGY_TYPES,
    CompositeStrategy,
    FormalStrategy,
    Strategy,
    StrategyType,
)

# Deduction is a hard predictive implication in Jaynes form:
#   P(C=true | premise=true, I) = 1 - ε
#   P(C=true | premise=false, I) = q
# where q defaults to 0.5 by MaxEnt unless an explicit base-rate model is added
# later. Accepted review gates whether the relation enters I; it never supplies
# a numerical prior for the deduction warrant.
_DEDUCTION_FALSE_PREMISE_BASE_RATE = 0.5

# Support remains the soft implication family. Its warrant prior is still folded
# into an effective P(C|premise) until support is redesigned as a separate
# likelihood-style operator.
_SOFT_IMPLICATION_TYPES = frozenset({StrategyType.SUPPORT})

# Operators whose conclusion is a "relation assertion" (the operator
# DECLARES that the relation holds) — their helper claim should be
# pinned to ``1 - CROMWELL_EPS`` (asserted true).  DISJUNCTION is
# compositional (``h = a OR b`` is a derived value), so its helper
# stays at the neutral 0.5 default and the factor potential drives
# the marginal.
_RELATION_OPS = frozenset(
    {
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
        OperatorType.IMPLICATION,
    }
)

_ASSOCIATE_TOLERANCE = 1e-6

_OPERATOR_MAP: dict[OperatorType, FactorType] = {
    OperatorType.IMPLICATION: FactorType.IMPLICATION,
    OperatorType.NEGATION: FactorType.NEGATION,
    OperatorType.CONJUNCTION: FactorType.CONJUNCTION,
    OperatorType.DISJUNCTION: FactorType.DISJUNCTION,
    OperatorType.EQUIVALENCE: FactorType.EQUIVALENCE,
    OperatorType.CONTRADICTION: FactorType.CONTRADICTION,
    OperatorType.COMPLEMENT: FactorType.COMPLEMENT,
}


_SYMMETRIC_OPS = frozenset(
    {
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
        OperatorType.DISJUNCTION,
        OperatorType.CONJUNCTION,
    }
)


def _canonical_op_key(op: Operator) -> tuple:
    """Structural canonical key for D2 duplicate detection.

    V9 (Jaynes D2): two operators sharing this key encode the same
    class-I information (up to the operator's known symmetry). L1
    structural enforcement only; deeper semantic equivalence belongs
    to Archon / SAT verifiers.
    """
    args = frozenset(op.variables) if op.operator in _SYMMETRIC_OPS else tuple(op.variables)
    return (op.operator, args)


def _dedup_operators(
    ops: Sequence[Operator],
    *,
    dedup_audit: list[dict],
    context: str,
) -> list[Operator]:
    """L1 D2 dedup: drop later operators matching an earlier canonical key.

    * Same key AND same conclusion -> silently drop, record in dedup_audit.
    * Same key but DIFFERENT conclusion -> raise ValueError (D1+D2 violation).
    """
    seen: dict[tuple, tuple[str, int]] = {}
    out: list[Operator] = []
    for op in ops:
        key = _canonical_op_key(op)
        if key in seen:
            prev_concl, _prev_idx = seen[key]
            if prev_concl == op.conclusion:
                dedup_audit.append(
                    {
                        "context": context,
                        "op": str(op.operator),
                        "args": sorted(op.variables)
                        if op.operator in _SYMMETRIC_OPS
                        else list(op.variables),
                        "conclusion": op.conclusion,
                        "dropped_index": len(out) + (len(seen) - 1),
                    }
                )
                continue
            raise ValueError(
                f"D2 violation [{context}]: operator {op.operator.value} over "
                f"args="
                f"{sorted(op.variables) if op.operator in _SYMMETRIC_OPS else list(op.variables)} "
                f"is declared with two different conclusions: "
                f"'{prev_concl}' (first) vs '{op.conclusion}' (duplicate). "
                f"The same logical relation cannot assert into two distinct helper claims."
            )
        seen[key] = (op.conclusion, len(out))
        out.append(op)
    return out


def _next_fid(prefix: str, i: list[int]) -> str:
    i[0] += 1
    return f"{prefix}_f{i[0]}"


def _review_target_allowed(
    target_id: str | None,
    metadata: dict[str, Any] | None,
    review_manifest: ReviewManifest | None,
) -> bool:
    if review_manifest is None:
        return True
    if not metadata or not metadata.get("action_label"):
        return True
    if not target_id:
        return False
    return review_manifest.latest_status(target_id) == ReviewStatus.ACCEPTED


def _operator_asserts_relation(op: Operator) -> bool:
    """Return True when a relation-operator conclusion is an asserted helper."""
    if op.operator not in _RELATION_OPS:
        return False
    # Formula connectives use the conclusion as the formula truth variable.
    # Its authored prior must remain live instead of being pinned as a hard
    # relation assertion.
    return (op.metadata or {}).get("formula_lowering") != "connective"


def _helper_prior_filter_ids(canonical: LocalCanonicalGraph) -> tuple[set[str], set[str]]:
    """Return helper IDs whose user/default priors should be ignored."""
    helper_ids = {
        k.id for k in canonical.knowledges if k.id and k.label and k.label.startswith("__")
    }
    expression_helper_ids = {
        k.id for k in canonical.knowledges if k.id and is_structural_expression_helper(k)
    }
    return helper_ids | expression_helper_ids, expression_helper_ids


def _metadata_priors(
    canonical: LocalCanonicalGraph,
    expression_helper_ids: set[str],
) -> dict[str, float]:
    """Collect metadata priors except for structural expression helpers."""
    return {
        k.id: float(k.metadata["prior"])
        for k in canonical.knowledges
        if k.id and k.metadata and "prior" in k.metadata and k.id not in expression_helper_ids
    }


def _review_allowed_operators(
    canonical: LocalCanonicalGraph,
    review_manifest: ReviewManifest | None,
) -> list[Operator]:
    """Return operators admitted by the optional review manifest."""
    return [
        op
        for op in canonical.operators
        if _review_target_allowed(op.operator_id, op.metadata, review_manifest)
    ]


def _relation_conclusion_ids(operators: list[Operator]) -> set[str]:
    """Return conclusions whose relation operators assert the helper true."""
    return {op.conclusion for op in operators if _operator_asserts_relation(op)}


def _add_claim_variables(
    fg: FactorGraph,
    canonical: LocalCanonicalGraph,
    *,
    priors: dict[str, float],
    expression_helper_ids: set[str],
    relation_concl_ids: set[str],
) -> set[str]:
    """Register claim variables with the documented prior precedence rules."""
    claim_ids = {k.id for k in canonical.knowledges if k.type == KnowledgeType.CLAIM and k.id}
    for knowledge in canonical.knowledges:
        if knowledge.type != KnowledgeType.CLAIM or not knowledge.id:
            continue
        meta = knowledge.metadata or {}
        metadata_prior = meta.get("prior")
        is_observed = metadata_prior is not None and meta.get("supported_by") is not None
        if knowledge.id in expression_helper_ids:
            fg.add_variable(knowledge.id)
        elif knowledge.id in relation_concl_ids:
            fg.add_variable(knowledge.id)
            fg.add_evidence(knowledge.id, 1)
        elif knowledge.id in priors:
            fg.add_variable(knowledge.id, priors[knowledge.id])
        elif is_observed:
            fg.add_variable(knowledge.id, float(metadata_prior))
        else:
            fg.add_variable(knowledge.id)
    return claim_ids


def _lower_operators(
    fg: FactorGraph,
    operators: list[Operator],
    *,
    priors: dict[str, float],
    claim_ids: set[str],
    expression_helper_ids: set[str],
    ctr: list[int],
) -> None:
    """Lower review-admitted operators to factor-graph factors."""
    for op in operators:
        fid = _next_fid("op", ctr)
        ft = _OPERATOR_MAP[op.operator]
        for vid in op.variables:
            _ensure_claim_var(fg, vid, priors, claim_ids)
        conclusion = op.conclusion
        if conclusion not in fg.variables:
            if conclusion in expression_helper_ids:
                fg.add_variable(conclusion)
            elif _operator_asserts_relation(op):
                fg.add_variable(conclusion)
                fg.add_evidence(conclusion, 1)
            else:
                fg.add_variable(conclusion, priors.get(conclusion))
        fg.add_factor(fid, ft, op.variables, conclusion)


def _lower_graph_strategies(
    fg: FactorGraph,
    canonical: LocalCanonicalGraph,
    *,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    metadata_priors: dict[str, float],
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    review_manifest: ReviewManifest | None,
) -> None:
    """Lower review-admitted strategies to factor-graph factors."""
    seen_strategies: set[str] = set()
    for strategy in canonical.strategies:
        if not _review_target_allowed(strategy.strategy_id, strategy.metadata, review_manifest):
            continue
        _lower_strategy(
            fg,
            strategy,
            strat_by_id,
            priors,
            strat_params,
            metadata_priors,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            canonical.namespace,
            canonical.package_name,
            seen_strategies=seen_strategies,
            review_manifest=review_manifest,
        )


def lower_local_graph(
    canonical: LocalCanonicalGraph,
    *,
    node_priors: dict[str, float] | None = None,
    strategy_conditional_params: dict[str, list[float]] | None = None,
    expand_formal: bool = True,
    infer_use_degraded_noisy_and: bool = False,
    review_manifest: ReviewManifest | None = None,
) -> FactorGraph:
    """Build a FactorGraph from a local canonical Gaia IR graph.

    Parameters
    ----------
    canonical:
        Local graph with knowledges, operators, strategies.
    node_priors:
        Optional prior P(claim=1) per Knowledge id (claim nodes only).
    strategy_conditional_params:
        Maps strategy_id -> conditional_probabilities list (infer: 2^k entries,
        noisy_and: 1 entry).
    expand_formal:
        If True, expand FormalStrategy to deterministic factors. If False,
        fold is required but only implemented when no internal variables exist.
    infer_use_degraded_noisy_and:
        If True, lower ``infer`` with CONJUNCTION+SOFT_ENTAILMENT using only
        all-true / all-false CPT entries (information loss for general CPT).
    review_manifest:
        Optional qualitative ReviewManifest. When present, v6 action-backed
        strategies/operators are lowered only after their latest review is
        accepted. Legacy IR targets without ``metadata.action_label`` are not
        gated.
    """
    priors = node_priors or {}
    no_user_prior_ids, expression_helper_ids = _helper_prior_filter_ids(canonical)
    if no_user_prior_ids:
        priors = {k: v for k, v in priors.items() if k not in no_user_prior_ids}
    metadata_priors = _metadata_priors(canonical, expression_helper_ids)
    strat_params = strategy_conditional_params or {}
    fg = FactorGraph()
    ctr = [0]

    lowerable_operators = _review_allowed_operators(canonical, review_manifest)
    lowerable_operators = _dedup_operators(
        lowerable_operators,
        dedup_audit=fg.dedup_audit,
        context="graph_operators",
    )
    claim_ids = _add_claim_variables(
        fg,
        canonical,
        priors=priors,
        expression_helper_ids=expression_helper_ids,
        relation_concl_ids=_relation_conclusion_ids(lowerable_operators),
    )

    strat_by_id = {s.strategy_id: s for s in canonical.strategies if s.strategy_id}

    _lower_operators(
        fg,
        lowerable_operators,
        priors=priors,
        claim_ids=claim_ids,
        expression_helper_ids=expression_helper_ids,
        ctr=ctr,
    )
    _lower_graph_strategies(
        fg,
        canonical,
        strat_by_id=strat_by_id,
        priors=priors,
        strat_params=strat_params,
        metadata_priors=metadata_priors,
        expand_formal=expand_formal,
        infer_degraded=infer_use_degraded_noisy_and,
        ctr=ctr,
        claim_ids=claim_ids,
        review_manifest=review_manifest,
    )

    return fg


def _ensure_claim_var(
    fg: FactorGraph, vid: str, priors: dict[str, float], claim_ids: set[str]
) -> None:
    del claim_ids
    if vid in fg.variables:
        return
    fg.add_variable(vid, priors.get(vid))


def _clamp_probability(value: float) -> float:
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, float(value)))


def _resolve_associate_marginal(
    *,
    variable_id: str,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    strategy_id: str | None,
) -> float | None:
    providers: list[tuple[str, float]] = []
    if variable_id in priors:
        providers.append(("node_priors", _clamp_probability(priors[variable_id])))
    if variable_id in metadata_priors:
        providers.append(("metadata.prior", _clamp_probability(metadata_priors[variable_id])))

    if not providers:
        return None

    first_source, first_value = providers[0]
    for source, value in providers[1:]:
        if abs(value - first_value) > _ASSOCIATE_TOLERANCE:
            raise ValueError(
                f"associate strategy {strategy_id}: conflicting marginal providers for "
                f"{variable_id!r}: {first_source}={first_value:g}, {source}={value:g}"
            )
    return first_value


def _associate_pairwise_weights(
    s: Strategy,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
) -> tuple[str, str, float, float, tuple[float, float, float, float]]:
    if len(s.premises) != 2:
        raise ValueError(f"associate strategy {s.strategy_id}: requires exactly 2 premises")
    if s.p_a_given_b is None or s.p_b_given_a is None:
        raise ValueError(
            f"associate strategy {s.strategy_id}: requires p_a_given_b and p_b_given_a"
        )

    a, b = s.premises
    p_a_given_b = _clamp_probability(s.p_a_given_b)
    p_b_given_a = _clamp_probability(s.p_b_given_a)
    pi_a = _resolve_associate_marginal(
        variable_id=a,
        priors=priors,
        metadata_priors=metadata_priors,
        strategy_id=s.strategy_id,
    )
    pi_b = _resolve_associate_marginal(
        variable_id=b,
        priors=priors,
        metadata_priors=metadata_priors,
        strategy_id=s.strategy_id,
    )

    if pi_a is None and pi_b is None:
        raise ValueError(
            f"associate strategy {s.strategy_id}: missing marginal prior for {a!r} or {b!r}"
        )
    if pi_a is None:
        pi_a = pi_b * p_a_given_b / p_b_given_a  # type: ignore[operator]
    if pi_b is None:
        pi_b = pi_a * p_b_given_a / p_a_given_b
    if not (0.0 < pi_a < 1.0 and 0.0 < pi_b < 1.0):
        raise ValueError(
            f"associate strategy {s.strategy_id}: derived marginals must be in (0,1), "
            f"got pi_a={pi_a:g}, pi_b={pi_b:g}"
        )

    p11_from_a = p_b_given_a * pi_a
    p11_from_b = p_a_given_b * pi_b
    if abs(p11_from_a - p11_from_b) > _ASSOCIATE_TOLERANCE:
        raise ValueError(
            f"associate strategy {s.strategy_id}: Bayes-inconsistent marginals "
            f"(p_b_given_a*pi_a={p11_from_a:g}, p_a_given_b*pi_b={p11_from_b:g})"
        )

    p11 = 0.5 * (p11_from_a + p11_from_b)
    p01 = pi_b - p11
    p10 = pi_a - p11
    p00 = 1.0 - pi_a - pi_b + p11
    cells = (p00, p10, p01, p11)
    if any(cell < -_ASSOCIATE_TOLERANCE for cell in cells):
        raise ValueError(
            f"associate strategy {s.strategy_id}: conditionals and marginals imply "
            f"negative joint cell(s): {cells!r}"
        )
    p00, p10, p01, p11 = (max(0.0, cell) for cell in cells)

    weights = (
        p00 / ((1.0 - pi_a) * (1.0 - pi_b)),
        p10 / (pi_a * (1.0 - pi_b)),
        p01 / ((1.0 - pi_a) * pi_b),
        p11 / (pi_a * pi_b),
    )
    return a, b, pi_a, pi_b, weights


def fold_composite_to_cpt(
    s: CompositeStrategy,
    strat_by_id: dict[str, Strategy],
    strat_params: dict[str, list[float]],
    expand_formal: bool = True,
) -> list[float]:
    """Compute the effective CPT of a CompositeStrategy via tensor contraction.

    Layer-by-layer variable elimination: each sub-strategy's CPT is computed
    recursively (cached by strategy_id), then child CPTs are contracted along
    shared bridge variables.  Exact, no BP iterations.

    Returns a list of 2^k floats (k = number of premises), indexed by the
    binary encoding of the premise assignment (bit 0 = first premise).
    """
    from gaia.bp.contraction import StrategyCptCacheValue, cpt_tensor_to_list, strategy_cpt

    if not expand_formal:
        raise NotImplementedError(
            "fold_composite_to_cpt with expand_formal=False is not supported "
            "by the tensor-contraction path. See "
            "docs/foundations/gaia-ir/07-lowering.md §9."
        )

    if s.conclusion is None:
        raise ValueError(f"CompositeStrategy {s.strategy_id} requires a conclusion for folding.")

    cache: dict[str, StrategyCptCacheValue] = {}
    cpt_tensor, axes = strategy_cpt(
        s,
        strat_by_id=strat_by_id,
        strat_params=strat_params,
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    return cpt_tensor_to_list(cpt_tensor, axes, list(s.premises), s.conclusion)


def _mark_strategy_seen(s: Strategy, seen_strategies: set[str] | None) -> bool:
    """Return True when strategy lowering should continue after deduping."""
    if seen_strategies is None or not s.strategy_id:
        return True
    if s.strategy_id in seen_strategies:
        return False
    seen_strategies.add(s.strategy_id)
    return True


def _lower_composite_strategy(
    fg: FactorGraph,
    s: CompositeStrategy,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    metadata_priors: dict[str, float],
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    namespace: str,
    package_name: str,
    *,
    seen_strategies: set[str] | None,
    review_manifest: ReviewManifest | None,
) -> None:
    """Lower sub-strategies referenced by a CompositeStrategy."""
    for sid in s.sub_strategies:
        sub = strat_by_id.get(sid)
        if sub is None:
            raise KeyError(f"CompositeStrategy references missing strategy_id {sid!r}")
        _lower_strategy(
            fg,
            sub,
            strat_by_id,
            priors,
            strat_params,
            metadata_priors,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            namespace,
            package_name,
            seen_strategies=seen_strategies,
            review_manifest=review_manifest,
        )


def _lower_deduction_implication(
    fg: FactorGraph,
    s: FormalStrategy,
    op: Operator,
    fid: str,
    priors: dict[str, float],
    claim_ids: set[str],
) -> None:
    """Lower a deduction implication as a conditional factor."""
    antecedent = op.variables[0]
    consequent = op.variables[1]
    _ensure_claim_var(fg, antecedent, priors, claim_ids)
    _ensure_claim_var(fg, consequent, priors, claim_ids)
    # V2 (Jaynes D3): false-premise branch inherits consequent leaf prior π_C.
    # When premise is false, the deduction warrant carries no information
    # about C, so the CPT must reproduce π_C and add nothing. Falls back to
    # 0.5 (MaxEnt) only when consequent has no leaf prior. metadata override
    # remains for authors who model a custom base rate.
    explicit_q = (s.metadata or {}).get("false_premise_base_rate")
    if explicit_q is not None:
        q = float(explicit_q)
    elif consequent in priors:
        q = float(priors[consequent])
    else:
        q = _DEDUCTION_FALSE_PREMISE_BASE_RATE
    fg.add_factor(
        fid,
        FactorType.CONDITIONAL,
        [antecedent],
        consequent,
        cpt=[q, 1.0 - CROMWELL_EPS],
    )
    fg.variables.pop(op.conclusion, None)
    fg.unary_factors.pop(op.conclusion, None)


def _lower_support_implication(
    fg: FactorGraph,
    op: Operator,
    fid: str,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    claim_ids: set[str],
) -> None:
    """Lower a support implication by marginalizing the helper prior."""
    helper_prior = priors.get(op.conclusion, metadata_priors.get(op.conclusion, 1.0 - CROMWELL_EPS))
    p1_eff = helper_prior * (1.0 - CROMWELL_EPS) + (1.0 - helper_prior) * 0.5
    antecedent = op.variables[0]
    consequent = op.variables[1]
    _ensure_claim_var(fg, antecedent, priors, claim_ids)
    _ensure_claim_var(fg, consequent, priors, claim_ids)
    fg.add_factor(
        fid,
        FactorType.SOFT_ENTAILMENT,
        [antecedent],
        consequent,
        p1=p1_eff,
        p2=0.5,
    )
    fg.variables.pop(op.conclusion, None)
    fg.unary_factors.pop(op.conclusion, None)


def _lower_formal_operator_default(
    fg: FactorGraph,
    op: Operator,
    fid: str,
    priors: dict[str, float],
    claim_ids: set[str],
) -> None:
    """Lower a formal operator with its direct factor mapping."""
    fg.add_factor(fid, _OPERATOR_MAP[op.operator], op.variables, op.conclusion)
    for vid in op.variables:
        _ensure_claim_var(fg, vid, priors, claim_ids)
    conclusion = op.conclusion
    if conclusion not in fg.variables:
        prior = 1.0 - CROMWELL_EPS if op.operator in _RELATION_OPS else priors.get(conclusion)
        fg.add_variable(conclusion, prior)
    elif op.operator in _RELATION_OPS:
        fg.add_variable(conclusion, 1.0 - CROMWELL_EPS)


def _lower_formal_strategy(
    fg: FactorGraph,
    s: FormalStrategy,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    expand_formal: bool,
    ctr: list[int],
    claim_ids: set[str],
) -> None:
    """Lower a FormalStrategy by expanding each formal operator."""
    if not expand_formal:
        raise NotImplementedError(
            "FormalStrategy fold (marginalize to CONDITIONAL) is not implemented yet. "
            "See docs/foundations/bp/inference.md and docs/foundations/gaia-ir/07-lowering.md §9."
        )
    fe_ops = _dedup_operators(
        s.formal_expr.operators,
        dedup_audit=fg.dedup_audit,
        context=f"formal_strategy:{s.strategy_id}",
    )
    for index, op in enumerate(fe_ops):
        fid = _next_fid(f"fs_{s.strategy_id}_{index}", ctr)
        if s.type == StrategyType.DEDUCTION and op.operator == OperatorType.IMPLICATION:
            _lower_deduction_implication(fg, s, op, fid, priors, claim_ids)
        elif s.type in _SOFT_IMPLICATION_TYPES and op.operator == OperatorType.IMPLICATION:
            _lower_support_implication(fg, op, fid, priors, metadata_priors, claim_ids)
        else:
            _lower_formal_operator_default(fg, op, fid, priors, claim_ids)


def _prepare_leaf_strategy_variables(
    fg: FactorGraph,
    s: Strategy,
    priors: dict[str, float],
    claim_ids: set[str],
) -> tuple[str, str]:
    """Validate and register leaf strategy variables."""
    if s.conclusion is None:
        raise ValueError(f"Leaf strategy {s.strategy_id} requires a conclusion for lowering.")
    if s.strategy_id is None:
        raise ValueError("Strategy requires a strategy_id for lowering.")
    _ensure_claim_var(fg, s.conclusion, priors, claim_ids)
    for premise_id in s.premises:
        _ensure_claim_var(fg, premise_id, priors, claim_ids)
    return s.conclusion, s.strategy_id


def _lower_infer_strategy(
    fg: FactorGraph,
    s: Strategy,
    conc: str,
    strategy_id: str,
    strat_params: dict[str, list[float]],
    infer_degraded: bool,
    ctr: list[int],
) -> None:
    """Lower an ``infer`` strategy to conditional or degraded soft-entailment factors."""
    cpt = (
        s.conditional_probabilities
        or strat_params.get(strategy_id)
        or [0.5] * (1 << len(s.premises))
    )
    if infer_degraded:
        _lower_degraded_infer(fg, s, conc, strategy_id, cpt, ctr)
    else:
        expected = 1 << len(s.premises)
        if len(cpt) != expected:
            raise ValueError(
                f"infer strategy {s.strategy_id}: expected {expected} CPT entries, got {len(cpt)}"
            )
        fg.add_factor(_next_fid("infer", ctr), FactorType.CONDITIONAL, s.premises, conc, cpt=cpt)


def _lower_degraded_infer(
    fg: FactorGraph,
    s: Strategy,
    conc: str,
    strategy_id: str,
    cpt: list[float],
    ctr: list[int],
) -> None:
    """Lower infer with the legacy degraded noisy-and-compatible path."""
    if len(s.premises) == 1:
        fg.add_factor(
            _next_fid("infer_deg", ctr),
            FactorType.SOFT_ENTAILMENT,
            [s.premises[0]],
            conc,
            p1=float(cpt[1]),
            p2=1.0 - float(cpt[0]),
        )
        return
    full = (1 << len(s.premises)) - 1
    m = f"_m_infer_{strategy_id}"
    fg.add_variable(m)
    fg.add_factor(_next_fid("infer_conj", ctr), FactorType.CONJUNCTION, s.premises, m)
    fg.add_factor(
        _next_fid("infer_se", ctr),
        FactorType.SOFT_ENTAILMENT,
        [m],
        conc,
        p1=float(cpt[full]),
        p2=1.0 - float(cpt[0]),
    )


def _lower_noisy_and_strategy(
    fg: FactorGraph,
    s: Strategy,
    conc: str,
    strategy_id: str,
    strat_params: dict[str, list[float]],
    ctr: list[int],
) -> None:
    """Lower a deprecated noisy-and strategy."""
    raw = s.conditional_probabilities or strat_params.get(strategy_id) or [0.5]
    p = float(raw[0])
    premises = list(s.premises)
    if len(premises) == 1:
        fg.add_factor(
            _next_fid("na", ctr),
            FactorType.SOFT_ENTAILMENT,
            premises,
            conc,
            p1=p,
            p2=1.0 - CROMWELL_EPS,
        )
        return
    m = f"_m_na_{strategy_id}"
    fg.add_variable(m)
    fg.add_factor(_next_fid("na_conj", ctr), FactorType.CONJUNCTION, premises, m)
    fg.add_factor(
        _next_fid("na_se", ctr),
        FactorType.SOFT_ENTAILMENT,
        [m],
        conc,
        p1=p,
        p2=1.0 - CROMWELL_EPS,
    )


def _lower_associate_strategy(
    fg: FactorGraph,
    s: Strategy,
    conc: str,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    ctr: list[int],
) -> None:
    """Lower an associate strategy as a pairwise potential."""
    a, b, pi_a, pi_b, weights = _associate_pairwise_weights(s, priors, metadata_priors)
    fg.variables.pop(conc, None)
    fg.unary_factors.pop(conc, None)
    fg.add_variable(a, pi_a)
    fg.add_variable(b, pi_b)
    fg.add_factor(_next_fid("assoc", ctr), FactorType.PAIRWISE_POTENTIAL, [a], b, cpt=weights)


def _lower_named_formal_leaf(
    fg: FactorGraph,
    s: Strategy,
    conc: str,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    metadata_priors: dict[str, float],
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    namespace: str,
    package_name: str,
    *,
    seen_strategies: set[str] | None,
    review_manifest: ReviewManifest | None,
) -> None:
    """Auto-formalize and lower a named formal leaf strategy."""
    ns = namespace if s.scope == "local" else None
    pkg = package_name if s.scope == "local" else None
    result = formalize_named_strategy(
        scope=s.scope,
        type_=s.type,
        premises=list(s.premises),
        conclusion=conc,
        namespace=ns,
        package_name=pkg,
        background=s.background,
        steps=s.steps,
        metadata=s.metadata,
    )
    for knowledge in result.knowledges:
        if knowledge.id and knowledge.metadata and "prior" in knowledge.metadata:
            priors[knowledge.id] = float(knowledge.metadata["prior"])
    for knowledge in result.knowledges:
        if knowledge.id:
            _ensure_claim_var(fg, knowledge.id, priors, claim_ids)
    _lower_strategy(
        fg,
        result.strategy,
        strat_by_id,
        priors,
        strat_params,
        metadata_priors,
        expand_formal,
        infer_degraded,
        ctr,
        claim_ids,
        namespace,
        package_name,
        seen_strategies=seen_strategies,
        review_manifest=review_manifest,
    )


def _lower_leaf_strategy(
    fg: FactorGraph,
    s: Strategy,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    metadata_priors: dict[str, float],
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    namespace: str,
    package_name: str,
    *,
    seen_strategies: set[str] | None,
    review_manifest: ReviewManifest | None,
) -> None:
    """Lower a non-composite, non-formal strategy."""
    conc, strategy_id = _prepare_leaf_strategy_variables(fg, s, priors, claim_ids)
    if s.type == StrategyType.INFER:
        _lower_infer_strategy(fg, s, conc, strategy_id, strat_params, infer_degraded, ctr)
        return
    if s.type == StrategyType.NOISY_AND:
        _lower_noisy_and_strategy(fg, s, conc, strategy_id, strat_params, ctr)
        return
    if s.type == StrategyType.ASSOCIATE:
        _lower_associate_strategy(fg, s, conc, priors, metadata_priors, ctr)
        return
    if s.type in _FORMAL_STRATEGY_TYPES:
        _lower_named_formal_leaf(
            fg,
            s,
            conc,
            strat_by_id,
            priors,
            strat_params,
            metadata_priors,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            namespace,
            package_name,
            seen_strategies=seen_strategies,
            review_manifest=review_manifest,
        )
        return
    raise NotImplementedError(
        f"Leaf strategy type {s.type!r} is deferred in Gaia IR core "
        "(docs/foundations/gaia-ir/02-gaia-ir.md §3.3). "
        "Supply a pre-formalized FormalStrategy, or use infer/noisy_and/associate."
    )


def _lower_strategy(
    fg: FactorGraph,
    s: Strategy,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    metadata_priors: dict[str, float] | None,
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    namespace: str,
    package_name: str,
    seen_strategies: set[str] | None = None,
    review_manifest: ReviewManifest | None = None,
) -> None:
    if not _review_target_allowed(s.strategy_id, s.metadata, review_manifest):
        return
    if not _mark_strategy_seen(s, seen_strategies):
        return
    metadata_priors = metadata_priors or {}

    if isinstance(s, CompositeStrategy):
        _lower_composite_strategy(
            fg,
            s,
            strat_by_id,
            priors,
            strat_params,
            metadata_priors,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            namespace,
            package_name,
            seen_strategies=seen_strategies,
            review_manifest=review_manifest,
        )
        return

    if isinstance(s, FormalStrategy):
        _lower_formal_strategy(fg, s, priors, metadata_priors, expand_formal, ctr, claim_ids)
        return

    _lower_leaf_strategy(
        fg,
        s,
        strat_by_id,
        priors,
        strat_params,
        metadata_priors,
        expand_formal,
        infer_degraded,
        ctr,
        claim_ids,
        namespace,
        package_name,
        seen_strategies=seen_strategies,
        review_manifest=review_manifest,
    )


def lower_operator(graph: FactorGraph, op: Operator, factor_id: str) -> None:
    """Lower a single IR Operator into one factor (public helper for tests)."""
    ft = _OPERATOR_MAP[op.operator]
    graph.add_factor(factor_id, ft, op.variables, op.conclusion)


def merge_factor_graphs(
    local_fg: FactorGraph,
    dep_graphs: list[tuple[str, FactorGraph, str]],
    *,
    local_prefix: str,
) -> FactorGraph:
    """Merge local and dependency factor graphs for joint inference.

    Parameters
    ----------
    local_fg:
        The local package's factor graph.
    dep_graphs:
        List of ``(dep_import_name, dep_factor_graph, dep_qid_prefix)``
        triples. ``dep_qid_prefix`` identifies variables owned by that
        dependency, e.g. ``"github:dep_pkg::"``.
    local_prefix:
        QID prefix for the local package, e.g. ``"github:my_pkg::"``.
        Variables starting with this prefix are owned by the local package.

    Returns:
        A merged :class:`FactorGraph` where shared QIDs map to a single
        variable (dep-owned prior takes precedence for dep nodes) and all
        factors coexist with prefixed IDs to avoid collision.
    """
    merged = FactorGraph()

    def _copy_variable(source: FactorGraph, var_id: str) -> None:
        if var_id in source.unary_factors:
            merged.add_variable(var_id, source.unary_factors[var_id])
        else:
            merged.variables[var_id] = source.variables.get(var_id, 0.5)
            merged.unary_factors.pop(var_id, None)

    # 1. Add dep variables first. A dep graph is authoritative only for
    # variables it owns; foreign references may carry neutral placeholder priors.
    for _dep_name, dep_fg, dep_prefix in dep_graphs:
        for var_id in dep_fg.variables:
            if var_id.startswith(dep_prefix) or var_id not in merged.variables:
                _copy_variable(dep_fg, var_id)

    # 2. Add local variables — overwrite only for locally-owned nodes
    for var_id in local_fg.variables:
        if var_id.startswith(local_prefix):
            # Local owns this node — always use local prior
            _copy_variable(local_fg, var_id)
        elif var_id not in merged.variables:
            # New variable only seen locally (e.g. intermediate _m_ vars)
            _copy_variable(local_fg, var_id)
        # else: dep owns it, dep prior already set — skip

    # 3. Copy dep factors with prefixed IDs
    for dep_name, dep_fg, _dep_prefix in dep_graphs:
        for factor in dep_fg.factors:
            prefixed = replace(factor, factor_id=f"dep_{dep_name}_{factor.factor_id}")
            merged.factors.append(prefixed)

    # 4. Copy local factors with prefix
    for factor in local_fg.factors:
        prefixed = replace(factor, factor_id=f"local_{factor.factor_id}")
        merged.factors.append(prefixed)

    return merged
