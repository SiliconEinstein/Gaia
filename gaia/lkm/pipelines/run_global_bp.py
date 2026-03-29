"""Orchestrate global BP: load graph + params from storage, run BP, persist BeliefState."""

from __future__ import annotations

from gaia.core.global_bp import run_global_bp as _run_bp
from gaia.models.graph_ir import GlobalCanonicalGraph
from gaia.models.parameterization import ResolutionPolicy
from gaia.models.belief_state import BeliefState
from gaia.libs.storage.manager import StorageManager


async def run_global_bp(
    storage: StorageManager,
    policy: ResolutionPolicy | None = None,
) -> BeliefState:
    """Load global graph and params from storage, run BP, persist result."""
    if policy is None:
        policy = ResolutionPolicy(strategy="latest")

    nodes = await storage.get_knowledge_nodes(prefix="gcn_")
    factors = await storage.get_factor_nodes(scope="global")
    global_graph = GlobalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)

    prior_records = await storage.get_prior_records()
    factor_records = await storage.get_factor_param_records()

    belief_state = await _run_bp(
        global_graph=global_graph,
        prior_records=prior_records,
        factor_records=factor_records,
        policy=policy,
    )

    await storage.write_belief_state(belief_state)
    return belief_state
