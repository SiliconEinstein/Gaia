"""Lower Gaia IR (LocalCanonicalGraph) to gaia.bp.FactorGraph.

Spec: docs/foundations/gaia-ir/07-lowering.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from gaia.ir.formalize import formalize_named_strategy
from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.knowledge import KnowledgeType
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.strategy import (
    _FORMAL_STRATEGY_TYPES,
    CompositeStrategy,
    FormalStrategy,
    Strategy,
    StrategyType,
)

_RELATION_OPS = frozenset(
    {
        OperatorType.EQUIVALENCE,
        OperatorType.CONTRADICTION,
        OperatorType.COMPLEMENT,
        OperatorType.DISJUNCTION,
    }
)

if TYPE_CHECKING:
    pass

_OPERATOR_MAP: dict[OperatorType, FactorType] = {
    OperatorType.IMPLICATION: FactorType.IMPLICATION,
    OperatorType.CONJUNCTION: FactorType.CONJUNCTION,
    OperatorType.DISJUNCTION: FactorType.DISJUNCTION,
    OperatorType.EQUIVALENCE: FactorType.EQUIVALENCE,
    OperatorType.CONTRADICTION: FactorType.CONTRADICTION,
    OperatorType.COMPLEMENT: FactorType.COMPLEMENT,
}


def _next_fid(prefix: str, i: list[int]) -> str:
    i[0] += 1
    return f"{prefix}_f{i[0]}"


def lower_local_graph(
    canonical: LocalCanonicalGraph,
    *,
    node_priors: dict[str, float] | None = None,
    strategy_conditional_params: dict[str, list[float]] | None = None,
    expand_formal: bool = True,
    infer_use_degraded_noisy_and: bool = False,
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
    """
    priors = node_priors or {}
    strat_params = strategy_conditional_params or {}
    fg = FactorGraph()
    ctr = [0]

    relation_concl_ids: set[str] = set()
    for op in canonical.operators:
        if op.operator in _RELATION_OPS:
            relation_concl_ids.add(op.conclusion)

    claim_ids = {k.id for k in canonical.knowledges if k.type == KnowledgeType.CLAIM and k.id}
    for k in canonical.knowledges:
        if k.type != KnowledgeType.CLAIM or not k.id:
            continue
        if k.id in relation_concl_ids and k.id not in priors:
            fg.add_variable(k.id, 1.0 - CROMWELL_EPS)
        else:
            fg.add_variable(k.id, priors.get(k.id, 0.5))

    strat_by_id = {s.strategy_id: s for s in canonical.strategies if s.strategy_id}

    for op in canonical.operators:
        fid = _next_fid("op", ctr)
        ft = _OPERATOR_MAP[op.operator]
        for vid in op.variables:
            _ensure_claim_var(fg, vid, priors, claim_ids)
        concl = op.conclusion
        if concl not in fg.variables:
            default = 1.0 - CROMWELL_EPS if op.operator in _RELATION_OPS else 0.5
            fg.add_variable(concl, priors.get(concl, default))
        fg.add_factor(fid, ft, op.variables, concl)

    for s in canonical.strategies:
        _lower_strategy(
            fg,
            s,
            strat_by_id,
            priors,
            strat_params,
            expand_formal,
            infer_use_degraded_noisy_and,
            ctr,
            claim_ids,
            canonical.namespace,
            canonical.package_name,
        )

    return fg


def _ensure_claim_var(
    fg: FactorGraph, vid: str, priors: dict[str, float], claim_ids: set[str]
) -> None:
    if vid in fg.variables:
        return
    fg.add_variable(vid, priors.get(vid, 0.5))


def fold_composite_to_cpt(
    s: CompositeStrategy,
    strat_by_id: dict[str, Strategy],
    strat_params: dict[str, list[float]],
    expand_formal: bool = True,
) -> list[float]:
    """Compute the effective CPT of a CompositeStrategy by marginalization.

    Builds a temporary factor graph from the sub-strategies, then for each
    assignment of the composite's premises, clamps premise priors and runs BP
    to obtain P(conclusion=1 | assignment).

    Returns a list of 2^k floats (k = number of premises), indexed by the
    binary encoding of the premise assignment (bit 0 = first premise).
    """
    from gaia.bp.bp import BeliefPropagation

    k = len(s.premises)
    cpt: list[float] = []
    CLAMP_HI = 1.0 - 1e-6
    CLAMP_LO = 1e-6

    for assignment in range(1 << k):
        # Build a fresh mini factor graph for this assignment.
        mini = FactorGraph()
        ctr = [0]
        claim_ids: set[str] = set()

        # Clamp premise priors according to this assignment.
        clamped: dict[str, float] = {}
        for bit, pid in enumerate(s.premises):
            clamped[pid] = CLAMP_HI if (assignment >> bit) & 1 else CLAMP_LO

        # Lower each sub-strategy into the mini graph.
        for sid in s.sub_strategies:
            sub = strat_by_id.get(sid)
            if sub is None:
                raise KeyError(f"CompositeStrategy references missing strategy_id {sid!r}")
            _lower_strategy(
                mini,
                sub,
                strat_by_id,
                clamped,
                strat_params,
                expand_formal,
                infer_degraded=False,
                ctr=ctr,
                claim_ids=claim_ids,
                namespace="",
                package_name="",
            )

        # Run BP on the mini graph.
        result = BeliefPropagation(damping=0.5, max_iterations=200).run(mini)
        cpt.append(result.beliefs.get(s.conclusion, 0.5))

    return cpt


def _lower_strategy(
    fg: FactorGraph,
    s: Strategy,
    strat_by_id: dict[str, Strategy],
    priors: dict[str, float],
    strat_params: dict[str, list[float]],
    expand_formal: bool,
    infer_degraded: bool,
    ctr: list[int],
    claim_ids: set[str],
    namespace: str,
    package_name: str,
) -> None:
    if isinstance(s, CompositeStrategy):
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
                expand_formal,
                infer_degraded,
                ctr,
                claim_ids,
                namespace,
                package_name,
            )
        return

    if isinstance(s, FormalStrategy):
        if not expand_formal:
            raise NotImplementedError(
                "FormalStrategy fold (marginalize to CONDITIONAL) is not implemented yet. "
                "See docs/foundations/bp/inference.md and docs/foundations/gaia-ir/07-lowering.md §9."
            )
        for i, op in enumerate(s.formal_expr.operators):
            fid = _next_fid(f"fs_{s.strategy_id}_{i}", ctr)
            ft = _OPERATOR_MAP[op.operator]
            fg.add_factor(fid, ft, op.variables, op.conclusion)
            for vid in op.variables:
                _ensure_claim_var(fg, vid, priors, claim_ids)
            concl = op.conclusion
            if concl not in fg.variables:
                default = 1.0 - CROMWELL_EPS if op.operator in _RELATION_OPS else 0.5
                fg.add_variable(concl, priors.get(concl, default))
            elif op.operator in _RELATION_OPS and concl not in priors:
                # Variable was pre-registered with wrong default (0.5) by
                # _ensure_claim_var during auto-formalization.  Override to
                # assertion prior for relation operator conclusions.
                fg.variables[concl] = 1.0 - CROMWELL_EPS
        return

    # Leaf Strategy
    if s.conclusion is None:
        raise ValueError(f"Leaf strategy {s.strategy_id} requires a conclusion for lowering.")
    conc = s.conclusion
    _ensure_claim_var(fg, conc, priors, claim_ids)
    for p in s.premises:
        _ensure_claim_var(fg, p, priors, claim_ids)

    if s.type == StrategyType.INFER:
        cpt = strat_params.get(s.strategy_id)
        if not cpt:
            cpt = [0.5] * (1 << len(s.premises))
        if infer_degraded:
            if len(s.premises) == 1:
                p1 = float(cpt[1])
                p2 = 1.0 - float(cpt[0])
                fg.add_factor(
                    _next_fid("infer_deg", ctr),
                    FactorType.SOFT_ENTAILMENT,
                    [s.premises[0]],
                    conc,
                    p1=p1,
                    p2=p2,
                )
            else:
                full = (1 << len(s.premises)) - 1
                p1 = float(cpt[full])
                p2 = 1.0 - float(cpt[0])
                m = f"_m_infer_{s.strategy_id}"
                fg.add_variable(m, 0.5)
                fg.add_factor(
                    _next_fid("infer_conj", ctr),
                    FactorType.CONJUNCTION,
                    s.premises,
                    m,
                )
                fg.add_factor(
                    _next_fid("infer_se", ctr),
                    FactorType.SOFT_ENTAILMENT,
                    [m],
                    conc,
                    p1=p1,
                    p2=p2,
                )
        else:
            expected = 1 << len(s.premises)
            if len(cpt) != expected:
                raise ValueError(
                    f"infer strategy {s.strategy_id}: expected {expected} CPT entries, got {len(cpt)}"
                )
            fg.add_factor(
                _next_fid("infer", ctr),
                FactorType.CONDITIONAL,
                s.premises,
                conc,
                cpt=cpt,
            )
        return

    if s.type == StrategyType.NOISY_AND:
        raw = strat_params.get(s.strategy_id) or [0.5]
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
        else:
            m = f"_m_na_{s.strategy_id}"
            fg.add_variable(m, 0.5)
            fg.add_factor(_next_fid("na_conj", ctr), FactorType.CONJUNCTION, premises, m)
            fg.add_factor(
                _next_fid("na_se", ctr),
                FactorType.SOFT_ENTAILMENT,
                [m],
                conc,
                p1=p,
                p2=1.0 - CROMWELL_EPS,
            )
        return

    # Named leaf strategy (not yet formalized into FormalStrategy) — auto-formalize.
    # Supported: deduction, elimination, mathematical_induction, case_analysis,
    #            abduction, analogy, extrapolation  (all entries in _FORMAL_STRATEGY_TYPES).
    # Deferred per docs/foundations/gaia-ir/02-gaia-ir.md §3.3:
    #   reductio, toolcall, proof (not in _FORMAL_STRATEGY_TYPES),
    #   induction (not a StrategyType primitive).
    if s.type in _FORMAL_STRATEGY_TYPES:
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
        # Register generated intermediate and interface claims as variables.
        for k in result.knowledges:
            if k.id:
                _ensure_claim_var(fg, k.id, priors, claim_ids)
        # Lower the auto-generated FormalStrategy via the expand path.
        _lower_strategy(
            fg,
            result.strategy,
            strat_by_id,
            priors,
            strat_params,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            namespace,
            package_name,
        )
        return

    raise NotImplementedError(
        f"Leaf strategy type {s.type!r} is deferred in Gaia IR core "
        "(docs/foundations/gaia-ir/02-gaia-ir.md §3.3). "
        "Supply a pre-formalized FormalStrategy, or use infer/noisy_and."
    )


def lower_operator(graph: FactorGraph, op: Operator, factor_id: str) -> None:
    """Lower a single IR Operator into one factor (public helper for tests)."""
    ft = _OPERATOR_MAP[op.operator]
    graph.add_factor(factor_id, ft, op.variables, op.conclusion)
