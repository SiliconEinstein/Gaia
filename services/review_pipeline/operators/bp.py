"""BPOperator — run belief propagation on affected subgraph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph
from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager


class BPOperator(Operator):
    """Run local belief propagation on the subgraph around affected nodes."""

    def __init__(self, storage: StorageManager, hops: int = 3) -> None:
        self._storage = storage
        self._hops = hops
        self._bp = BeliefPropagation()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not self._storage.graph:
            return context

        seed_ids = context.affected_node_ids
        if not seed_ids:
            return context

        node_ids, edge_ids = await self._storage.graph.get_subgraph(seed_ids, hops=self._hops)
        if not edge_ids:
            return context

        edges = []
        for eid in edge_ids:
            edge = await self._storage.graph.get_hyperedge(eid)
            if edge:
                edges.append(edge)

        nodes = await self._storage.lance.load_nodes_bulk(list(node_ids))
        fg = FactorGraph.from_subgraph(nodes, edges)
        beliefs = self._bp.run(fg)
        context.bp_results = beliefs
        return context
