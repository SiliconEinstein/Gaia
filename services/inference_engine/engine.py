"""InferenceEngine — orchestrates local and global belief propagation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager

__all__ = ["InferenceEngine"]


class InferenceEngine:
    """High-level orchestrator for belief propagation on the Gaia hypergraph.

    Wraps :class:`BeliefPropagation` and coordinates with storage backends to:
    1. Extract a local subgraph around seed nodes.
    2. Build a :class:`FactorGraph` from the retrieved nodes and edges.
    3. Run loopy BP to compute posterior beliefs.
    4. Write updated beliefs back to persistent storage.
    """

    def __init__(self, storage: StorageManager, bp_params: dict | None = None) -> None:
        self._storage = storage
        params = bp_params or {}
        self._bp = BeliefPropagation(**params)

    async def compute_local_bp(self, center_node_ids: list[int], hops: int = 3) -> dict[int, float]:
        """Run local BP around given nodes.

        Steps:
            1. Get subgraph topology from Neo4j.
            2. Load full hyperedge objects for each edge id.
            3. Load node objects (with priors) from LanceDB.
            4. Build a :class:`FactorGraph` from the retrieved data.
            5. Run belief propagation.
            6. Write posterior beliefs back to LanceDB.

        Returns
        -------
        dict[int, float]
            Mapping from node id to posterior belief in ``[0, 1]``.
            Returns ``{}`` if the graph store is unavailable.
        """
        if not self._storage.graph:
            return {}

        # 1. Get subgraph topology
        node_ids, edge_ids = await self._storage.graph.get_subgraph(center_node_ids, hops=hops)

        if not edge_ids:
            return {}

        # 2. Load edges
        edges = []
        for eid in edge_ids:
            edge = await self._storage.graph.get_hyperedge(eid)
            if edge:
                edges.append(edge)

        # 3. Load nodes
        nodes = await self._storage.lance.load_nodes_bulk(list(node_ids))

        # 4. Build factor graph
        fg = FactorGraph.from_subgraph(nodes, edges)

        # 5. Run BP
        beliefs = self._bp.run(fg)

        # 6. Write back
        await self._storage.lance.update_beliefs(beliefs)

        return beliefs

    async def run_global_bp(self) -> None:
        """Run global belief propagation across the entire graph.

        .. note::
            Phase 1: not implemented.

        Raises
        ------
        NotImplementedError
            Always, in Phase 1.
        """
        raise NotImplementedError("Global BP is not implemented in Phase 1")
