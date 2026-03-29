"""Global BP — parameter assembly and execution on GlobalCanonicalGraph.

Bridges the new Graph IR models (KnowledgeNode, FactorNode, GlobalCanonicalGraph)
to the old libs.inference FactorGraph/BeliefPropagation engine via an adapter layer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
from gaia.models.belief_state import BeliefState
from gaia.models.graph_ir import (
    GlobalCanonicalGraph,
    KnowledgeType,
    ReasoningType,
)
from gaia.models.parameterization import (
    FactorParamRecord,
    PriorRecord,
    ResolutionPolicy,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping: new ReasoningType -> old edge_type string
# ---------------------------------------------------------------------------

_REASONING_TYPE_TO_EDGE_TYPE: dict[ReasoningType | None, str] = {
    ReasoningType.ENTAILMENT: "deduction",
    ReasoningType.INDUCTION: "deduction",
    ReasoningType.ABDUCTION: "deduction",
    ReasoningType.EQUIVALENT: "relation_equivalence",
    ReasoningType.CONTRADICT: "relation_contradiction",
    None: "deduction",
}

_BILATERAL_TYPES = {ReasoningType.EQUIVALENT, ReasoningType.CONTRADICT}


# ---------------------------------------------------------------------------
# Parameter assembly
# ---------------------------------------------------------------------------


def assemble_parameterization(
    prior_records: list[PriorRecord],
    factor_records: list[FactorParamRecord],
    policy: ResolutionPolicy,
) -> dict:
    """Apply resolution policy to select per-node/factor values.

    Returns:
        {"node_priors": {gcn_id: float}, "factor_params": {factor_id: float}}

    Raises ValueError if policy strategy is invalid.
    """
    if policy.strategy not in ("latest", "source"):
        raise ValueError(f"Invalid resolution strategy: {policy.strategy!r}")

    cutoff = policy.prior_cutoff

    # --- Resolve priors ---
    filtered_priors = list(prior_records)
    if cutoff is not None:
        filtered_priors = [r for r in filtered_priors if r.created_at <= cutoff]
    if policy.strategy == "source":
        filtered_priors = [r for r in filtered_priors if r.source_id == policy.source_id]

    # Group by gcn_id, pick latest
    node_priors: dict[str, float] = {}
    latest_prior_ts: dict[str, datetime] = {}
    for r in filtered_priors:
        prev_ts = latest_prior_ts.get(r.gcn_id)
        if prev_ts is None or r.created_at > prev_ts:
            node_priors[r.gcn_id] = r.value
            latest_prior_ts[r.gcn_id] = r.created_at

    # --- Resolve factor params ---
    filtered_factors = list(factor_records)
    if cutoff is not None:
        filtered_factors = [r for r in filtered_factors if r.created_at <= cutoff]
    if policy.strategy == "source":
        filtered_factors = [r for r in filtered_factors if r.source_id == policy.source_id]

    factor_params: dict[str, float] = {}
    latest_factor_ts: dict[str, datetime] = {}
    for r in filtered_factors:
        prev_ts = latest_factor_ts.get(r.factor_id)
        if prev_ts is None or r.created_at > prev_ts:
            factor_params[r.factor_id] = r.probability
            latest_factor_ts[r.factor_id] = r.created_at

    return {"node_priors": node_priors, "factor_params": factor_params}


# ---------------------------------------------------------------------------
# BP execution
# ---------------------------------------------------------------------------


async def run_global_bp(
    global_graph: GlobalCanonicalGraph,
    prior_records: list[PriorRecord],
    factor_records: list[FactorParamRecord],
    policy: ResolutionPolicy,
    damping: float = 0.5,
    max_iterations: int = 50,
    threshold: float = 1e-6,
) -> BeliefState:
    """Run belief propagation on a GlobalCanonicalGraph.

    Steps:
    1. Assemble parameterization (resolve priors and factor params).
    2. Build old-format FactorGraph via adapter.
    3. Run BeliefPropagation.
    4. Wrap result in BeliefState.
    """
    # Step 1: Assemble parameters
    assembled = assemble_parameterization(prior_records, factor_records, policy)
    node_priors = assembled["node_priors"]
    factor_params = assembled["factor_params"]

    # Step 2: Build FactorGraph adapter
    fg = FactorGraph()

    # Build node type lookup and str->int ID mapping
    node_type_map: dict[str, KnowledgeType] = {}
    for node in global_graph.knowledge_nodes:
        node_type_map[node.id] = node.type

    # Only claim nodes with gcn_ prefix participate as BP variables
    claim_ids: list[str] = []
    for node in global_graph.knowledge_nodes:
        if node.type == KnowledgeType.CLAIM and node.id is not None and node.id.startswith("gcn_"):
            claim_ids.append(node.id)

    # Create stable str->int mapping (old FactorGraph uses int IDs)
    str_to_int: dict[str, int] = {}
    for i, cid in enumerate(claim_ids):
        str_to_int[cid] = i

    # Add variables
    for cid in claim_ids:
        prior = node_priors.get(cid)
        if prior is None:
            logger.warning("No prior for claim node %s, using default 0.5", cid)
            prior = 0.5
        fg.add_variable(str_to_int[cid], prior)

    # Add factors
    for fi, factor in enumerate(global_graph.factor_nodes):
        edge_type = _REASONING_TYPE_TO_EDGE_TYPE.get(factor.reasoning_type, "deduction")
        is_bilateral = factor.reasoning_type in _BILATERAL_TYPES

        # Filter premises to only claim nodes in our variable set
        claim_premises = [p for p in factor.premises if p in str_to_int]
        if not claim_premises:
            logger.warning(
                "Factor %s has no claim premises after filtering, skipping", factor.factor_id
            )
            continue

        prob = factor_params.get(factor.factor_id)
        if prob is None:
            logger.warning("No factor param for %s, using default 0.8", factor.factor_id)
            prob = 0.8

        int_premises = [str_to_int[p] for p in claim_premises]

        if is_bilateral:
            # Bilateral: premises are the two nodes, no conclusion
            fg.add_factor(
                edge_id=fi,
                premises=int_premises,
                conclusions=[],
                probability=prob,
                edge_type=edge_type,
            )
        else:
            # Standard: premises -> conclusion (if conclusion is a claim)
            int_conclusions = []
            if factor.conclusion is not None and factor.conclusion in str_to_int:
                int_conclusions = [str_to_int[factor.conclusion]]

            fg.add_factor(
                edge_id=fi,
                premises=int_premises,
                conclusions=int_conclusions,
                probability=prob,
                edge_type=edge_type,
            )

    # Step 3: Run BP
    bp = BeliefPropagation(
        damping=damping,
        max_iterations=max_iterations,
        convergence_threshold=threshold,
    )
    beliefs_int, diagnostics = bp.run_with_diagnostics(fg)

    # Step 4: Map int IDs back to str and build BeliefState
    int_to_str = {v: k for k, v in str_to_int.items()}
    beliefs_str: dict[str, float] = {}
    for int_id, belief in beliefs_int.items():
        str_id = int_to_str.get(int_id)
        if str_id is not None:
            beliefs_str[str_id] = belief

    # Build resolution_policy string for BeliefState
    if policy.strategy == "source":
        resolution_policy_str = f"source:{policy.source_id}"
    else:
        resolution_policy_str = policy.strategy

    return BeliefState(
        bp_run_id=str(uuid.uuid4()),
        resolution_policy=resolution_policy_str,
        prior_cutoff=policy.prior_cutoff or datetime.now(timezone.utc),
        beliefs=beliefs_str,
        converged=diagnostics.converged,
        iterations=diagnostics.iterations_run,
        max_residual=diagnostics.max_change_at_stop,
    )
