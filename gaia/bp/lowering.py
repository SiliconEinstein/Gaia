"""Lower Gaia IR (LocalCanonicalGraph) to gaia.bp.FactorGraph.

Spec: docs/foundations/gaia-ir/07-lowering.md
"""

from __future__ import annotations

from dataclasses import replace

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

# Deduction and support implication operators are lowered as proper CPTs
# (SOFT_ENTAILMENT) instead of ternary constraint factors.  The author's
# prior on the implication warrant is marginalized into p1_eff:
#   p1_eff = π(H) · (1-ε) + (1-π(H)) · 0.5
# with p2 = 0.5 (MaxEnt default: "no information when premises fail").
# This eliminates the fan-out penalty (rows sum to 1) while preserving
# backward inference (weak syllogism / Jaynes).
_CPT_IMPLICATION_TYPES = frozenset({StrategyType.DEDUCTION, StrategyType.SUPPORT})

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
    # Auto-formalized helper claims (labels starting with ``__``, e.g.
    # ``__disjunction_result_<hash>``, ``__equivalence_result_<hash>``)
    # are persisted into ``ir["knowledges"]`` and consequently appear in
    # most callers' ``node_priors`` (which default-fill every claim id).
    # Their priors should NOT come from the user — they're determined by
    # the operator semantics (relation operators → asserted; compositional
    # operators → neutral 0.5).  Filter them out so the lowering branches
    # below can apply the correct default.
    helper_ids = {
        k.id for k in canonical.knowledges if k.id and k.label and k.label.startswith("__")
    }
    if helper_ids:
        priors = {k: v for k, v in priors.items() if k not in helper_ids}
    metadata_priors = {
        k.id: float(k.metadata["prior"])
        for k in canonical.knowledges
        if k.id and k.metadata and "prior" in k.metadata
    }
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
        # Priority: node_priors > metadata["prior"] > structural default
        metadata_prior = (k.metadata or {}).get("prior") if k.metadata else None
        if k.id in relation_concl_ids and k.id not in priors:
            fg.add_variable(k.id, 1.0 - CROMWELL_EPS)
        elif k.id in priors:
            fg.add_variable(k.id, priors[k.id])
        elif metadata_prior is not None:
            fg.add_variable(k.id, float(metadata_prior))
        else:
            fg.add_variable(k.id, 0.5)

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

    seen_strategies: set[str] = set()
    for s in canonical.strategies:
        _lower_strategy(
            fg,
            s,
            strat_by_id,
            priors,
            strat_params,
            metadata_priors,
            expand_formal,
            infer_use_degraded_noisy_and,
            ctr,
            claim_ids,
            canonical.namespace,
            canonical.package_name,
            seen_strategies=seen_strategies,
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
    """Compute the effective CPT of a CompositeStrategy via tensor contraction.

    Layer-by-layer variable elimination: each sub-strategy's CPT is computed
    recursively (cached by strategy_id), then child CPTs are contracted along
    shared bridge variables.  Exact, no BP iterations.

    Returns a list of 2^k floats (k = number of premises), indexed by the
    binary encoding of the premise assignment (bit 0 = first premise).
    """
    from gaia.bp.contraction import cpt_tensor_to_list, strategy_cpt

    if not expand_formal:
        raise NotImplementedError(
            "fold_composite_to_cpt with expand_formal=False is not supported "
            "by the tensor-contraction path. See "
            "docs/foundations/gaia-ir/07-lowering.md §9."
        )

    cache: dict = {}
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
) -> None:
    # Dedup: when ``seen_strategies`` is provided (lower_local_graph
    # passes a fresh set), skip strategies that have already been
    # lowered.  Composite strategies recursively lower their
    # sub-strategies, but those subs are also top-level entries in
    # ``canonical.strategies``, so without dedup the same strategy's
    # factors get added twice.
    if seen_strategies is not None and s.strategy_id:
        if s.strategy_id in seen_strategies:
            return
        seen_strategies.add(s.strategy_id)
    metadata_priors = metadata_priors or {}

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
                metadata_priors,
                expand_formal,
                infer_degraded,
                ctr,
                claim_ids,
                namespace,
                package_name,
                seen_strategies=seen_strategies,
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

            # Support/deduction implication operators → SOFT_ENTAILMENT CPT.
            # The ternary implication factor (antecedent, conclusion, helper)
            # is replaced by a binary CPT (antecedent → conclusion) with the
            # helper's prior marginalized into p1_eff.
            if s.type in _CPT_IMPLICATION_TYPES and op.operator == OperatorType.IMPLICATION:
                # Helper claim prior: use author-set prior if available,
                # otherwise the relation assertion default (1-ε) since the
                # implication helper is a relation operator conclusion.
                helper_prior = priors.get(
                    op.conclusion,
                    metadata_priors.get(op.conclusion, 1.0 - CROMWELL_EPS),
                )
                p1_eff = helper_prior * (1.0 - CROMWELL_EPS) + (1.0 - helper_prior) * 0.5
                # op.variables = [antecedent, actual_conclusion]
                antecedent = op.variables[0]
                consequent = op.variables[1]
                _ensure_claim_var(fg, antecedent, priors, claim_ids)
                _ensure_claim_var(fg, consequent, priors, claim_ids)
                fg.add_factor(
                    fid, FactorType.SOFT_ENTAILMENT, [antecedent], consequent, p1=p1_eff, p2=0.5
                )
                # Helper claim variable is marginalized into p1_eff, so it
                # should not remain as an orphan in the factor graph.
                fg.variables.pop(op.conclusion, None)
                continue

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
        # If a helper claim has an author-set prior (from priors.py or DSL
        # reason+prior pairing), inject it into the priors dict so lowering
        # uses it instead of the structural default (1-eps for relation ops,
        # 0.5 otherwise).
        for k in result.knowledges:
            if k.id and k.metadata and "prior" in k.metadata:
                priors[k.id] = float(k.metadata["prior"])
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
            metadata_priors,
            expand_formal,
            infer_degraded,
            ctr,
            claim_ids,
            namespace,
            package_name,
            seen_strategies=seen_strategies,
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

    Returns
    -------
    A merged :class:`FactorGraph` where shared QIDs map to a single
    variable (dep-owned prior takes precedence for dep nodes) and all
    factors coexist with prefixed IDs to avoid collision.
    """
    merged = FactorGraph()

    # 1. Add dep variables first. A dep graph is authoritative only for
    # variables it owns; foreign references may carry neutral placeholder priors.
    for dep_name, dep_fg, dep_prefix in dep_graphs:
        for var_id, prior in dep_fg.variables.items():
            if var_id.startswith(dep_prefix) or var_id not in merged.variables:
                merged.add_variable(var_id, prior)

    # 2. Add local variables — overwrite only for locally-owned nodes
    for var_id, prior in local_fg.variables.items():
        if var_id.startswith(local_prefix):
            # Local owns this node — always use local prior
            merged.add_variable(var_id, prior)
        elif var_id not in merged.variables:
            # New variable only seen locally (e.g. intermediate _m_ vars)
            merged.add_variable(var_id, prior)
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
