"""Adapter: Gaia LocalCanonicalGraph -> jaynes_ref InformationSet.

Layer-0 coverage:

* claim knowledges      -> universe variables (class V by default)
* metadata['prior']     -> class IV unary_priors (interior values only);
                           boundary values (0, 1) route to class I hard_evidence
* node_priors override  -> same routing, overrides metadata.prior
* assertional operators -> class I hard_evidence[concl]=1 + LogicalConstraint
                           (EQUIVALENCE / CONTRADICTION / COMPLEMENT / IMPLICATION)
* compositional ops     -> LogicalConstraint over (operands, conclusion),
                           conclusion stays class V
                           (CONJUNCTION / DISJUNCTION / NEGATION)
* strategies            -> dispatched to jaynes_ref.strategies.lower_strategy:
                           - CompositeStrategy: recurse
                           - FormalStrategy DEDUCTION+IMPL: A → C (helper dropped)
                           - FormalStrategy SUPPORT+IMPL: ternary (helper ∧ A → C)
                           - FormalStrategy other ops: same as graph.operators
                           - Leaf INFER:       CPT(parents=premises, child=concl)
                           - Leaf NOISY_AND:   CPT([0, ..., 0, p])
                           - Leaf ASSOCIATE:   WeightedFactor + marginal π_a/π_b
"""

from __future__ import annotations

from jaynes_ref import (
    CPT,
    InformationSet,
)
from jaynes_ref.strategies import (
    StrategyLoweringContext,
    _logical_constraint_for_op,
    lower_strategy,
)


def from_local_graph(
    graph,
    *,
    node_priors: dict[str, float] | None = None,
    cpts: list[CPT] | None = None,
    metadata_priors: dict[str, float] | None = None,
    strat_params: dict[str, list[float]] | None = None,
) -> InformationSet:
    """Translate a LocalCanonicalGraph to a Jaynes-Layer-0 InformationSet.

    Parameters
    ----------
    graph:
        gaia.ir.graphs.LocalCanonicalGraph
    node_priors:
        Author-supplied class-IV unary priors; overrides metadata['prior'].
        Values {0, 1} route to class-I hard_evidence.
    cpts:
        Optional pre-built class-III CPTs to attach directly (in addition to
        those derived from strategies).
    metadata_priors:
        Alternative external supply of class-IV priors (used when metadata
        is carried out-of-band rather than on Knowledge objects themselves).
    strat_params:
        Optional map strategy_id → CPT list overriding
        Strategy.conditional_probabilities (for parameter sweeps).
    """
    from gaia.ir.knowledge import KnowledgeType

    node_priors = node_priors or {}
    metadata_priors = metadata_priors or {}
    strat_params = strat_params or {}

    ctx = StrategyLoweringContext()

    # Merge metadata_priors derived from knowledge metadata into the
    # external metadata_priors dict (external overrides are rare but
    # allowed for testing).
    combined_meta: dict[str, float] = {}
    for k in graph.knowledges:
        if k.type != KnowledgeType.CLAIM:
            raise NotImplementedError(
                f"Knowledge type {k.type!r} not in Jaynes Layer 0; only CLAIM is supported."
            )
        if not k.id:
            raise ValueError("Every CLAIM knowledge must have an id.")
        ctx.variables.add(k.id)
        meta_prior = (k.metadata or {}).get("prior") if k.metadata else None
        if meta_prior is not None:
            combined_meta[k.id] = float(meta_prior)
    combined_meta.update(metadata_priors)

    # Resolve each declared variable's prior: node_priors > metadata.prior.
    for vid in ctx.variables:
        prior = node_priors.get(vid, combined_meta.get(vid))
        if prior is None:
            continue
        prior = float(prior)
        if prior in (0.0, 1.0):
            ctx.hard_evidence[vid] = int(prior)
        elif 0.0 < prior < 1.0:
            ctx.unary_priors[vid] = prior
        else:
            raise ValueError(f"Prior {prior} for {vid!r} out of [0,1].")

    # graph.operators — same logic as the jaynes_ref strategies dispatcher.
    for op in graph.operators:
        for v in op.variables:
            if v not in ctx.variables:
                raise ValueError(f"Operator references undeclared variable {v!r}.")
        if op.conclusion not in ctx.variables:
            raise ValueError(f"Operator conclusion {op.conclusion!r} is not a CLAIM.")

        kind, constraint = _logical_constraint_for_op(op)
        ctx.constraints.append(constraint)
        if kind == "asserted":
            existing = ctx.hard_evidence.get(op.conclusion)
            if existing is not None and existing != 1:
                raise ValueError(
                    f"D1 conflict: operator asserts {op.conclusion!r}=1 but "
                    f"existing hard_evidence pins it to {existing}."
                )
            if op.conclusion in ctx.unary_priors:
                del ctx.unary_priors[op.conclusion]
            ctx.hard_evidence[op.conclusion] = 1

    # graph.strategies — full Jaynes-strict lowering.
    strat_by_id = {s.strategy_id: s for s in graph.strategies if s.strategy_id}
    for s in graph.strategies:
        lower_strategy(
            s,
            ctx=ctx,
            strat_by_id=strat_by_id,
            priors=node_priors,
            metadata_priors=combined_meta,
            strat_params=strat_params,
        )

    return InformationSet(
        variables=set(ctx.variables),
        hard_evidence=dict(ctx.hard_evidence),
        unary_priors=dict(ctx.unary_priors),
        constraints=list(ctx.constraints),
        cpts=list(ctx.cpts) + (list(cpts) if cpts else []),
        weighted_factors=list(ctx.weighted_factors),
    )
