"""SearchEngine — multi-path recall with result merging and filtering."""

from __future__ import annotations

import asyncio

from libs.embedding import EmbeddingModel
from libs.storage.manager import StorageManager
from services.search_engine.merger import ResultMerger
from services.search_engine.models import (
    EdgeFilters,
    NodeFilters,
    ScoredHyperEdge,
    ScoredNode,
)
from services.search_engine.recall.bm25 import BM25Recall
from services.search_engine.recall.topology import TopologyRecall
from services.search_engine.recall.vector import VectorRecall


class SearchEngine:
    """Orchestrates vector, BM25, and topology recall paths.

    The engine runs selected recall paths in parallel, merges and deduplicates
    scores via :class:`ResultMerger`, loads full node/edge details from storage,
    and applies caller-supplied filters.
    """

    def __init__(
        self, storage: StorageManager, embedding_model: EmbeddingModel | None = None
    ) -> None:
        self._storage = storage
        self._embedding_model = embedding_model
        self._vector_recall = VectorRecall(storage.vector)
        self._bm25_recall = BM25Recall(storage.lance)
        self._topology_recall = TopologyRecall(storage.graph) if storage.graph else None
        self._merger = ResultMerger()

    # ── Node search ───────────────────────────────────────────────────────

    async def search_nodes(
        self,
        text: str,
        k: int = 50,
        filters: NodeFilters | None = None,
        paths: list[str] | None = None,
    ) -> list[ScoredNode]:
        """Run multi-path recall, merge, load nodes, filter, and return scored results."""
        if not self._embedding_model:
            raise ValueError("No embedding model configured")
        embedding = (await self._embedding_model.embed([text]))[0]

        active_paths = paths or ["vector", "bm25", "topology"]
        raw_results: dict[str, list[tuple[int, float]]] = {}

        # 1. Parallel vector + bm25 recall
        coros: list[tuple[str, asyncio.Task]] = []
        if "vector" in active_paths:
            coros.append(("vector", self._vector_recall.recall(embedding, k=100)))
        if "bm25" in active_paths:
            coros.append(("bm25", self._bm25_recall.recall(text, k=100)))

        if coros:
            gathered = await asyncio.gather(*(coro for _, coro in coros))
            for (name, _), result in zip(coros, gathered):
                raw_results[name] = result

        # 2. Topology: use vector top-10 as seeds
        if "topology" in active_paths and self._topology_recall:
            seeds = [nid for nid, _ in raw_results.get("vector", [])[:10]]
            if seeds:
                raw_results["topology"] = await self._topology_recall.recall(seeds, hops=3)

        # 3. Merge
        merged = await self._merger.merge(raw_results, k=k)

        # 4. Load node details
        node_ids = [nid for nid, _, _ in merged]
        nodes = await self._storage.lance.load_nodes_bulk(node_ids)
        node_map = {n.id: n for n in nodes}

        # 5. Build scored results and apply filters
        results: list[ScoredNode] = []
        for nid, score, sources in merged:
            node = node_map.get(nid)
            if node is None:
                continue
            if not self._passes_node_filters(node, filters):
                continue
            results.append(ScoredNode(node=node, score=score, sources=sources))

        return results

    # ── Edge search ───────────────────────────────────────────────────────

    async def search_edges(
        self,
        text: str,
        k: int = 50,
        filters: EdgeFilters | None = None,
        paths: list[str] | None = None,
    ) -> list[ScoredHyperEdge]:
        """Find edges connected to top-scoring nodes.

        Returns an empty list if the graph store (Neo4j) is unavailable.
        """
        if self._storage.graph is None:
            return []

        # 1. Find relevant nodes
        scored_nodes = await self.search_nodes(text=text, k=k, paths=paths)
        if not scored_nodes:
            return []

        # Build score map for ranking edges
        node_score_map: dict[int, tuple[float, list[str]]] = {
            sn.node.id: (sn.score, sn.sources) for sn in scored_nodes
        }
        node_ids = list(node_score_map.keys())

        # 2. Get connected edge IDs via subgraph traversal
        _, edge_ids = await self._storage.graph.get_subgraph(node_ids, hops=1)

        if not edge_ids:
            return []

        # 3. Load edge details
        edges = await asyncio.gather(*(self._storage.graph.get_hyperedge(eid) for eid in edge_ids))

        # 4. Filter and rank
        results: list[ScoredHyperEdge] = []
        for edge in edges:
            if edge is None:
                continue
            if not self._passes_edge_filters(edge, filters):
                continue

            # Score = max score of connected nodes
            connected_ids = set(edge.tail) | set(edge.head)
            best_score = 0.0
            all_sources: set[str] = set()
            for cid in connected_ids:
                if cid in node_score_map:
                    s, srcs = node_score_map[cid]
                    if s > best_score:
                        best_score = s
                    all_sources.update(srcs)

            results.append(
                ScoredHyperEdge(
                    edge=edge,
                    score=best_score,
                    sources=sorted(all_sources),
                )
            )

        # Sort by score descending
        results.sort(key=lambda x: -x.score)
        return results[:k]

    # ── Filters ───────────────────────────────────────────────────────────

    @staticmethod
    def _passes_node_filters(node, filters: NodeFilters | None) -> bool:
        """Return True if the node passes all filter criteria."""
        if filters is None:
            return True
        if filters.type and node.type not in filters.type:
            return False
        if filters.status and node.status not in filters.status:
            return False
        if filters.min_belief is not None and (node.belief or 0) < filters.min_belief:
            return False
        if filters.keywords:
            node_kw_set = set(node.keywords) if node.keywords else set()
            if not node_kw_set & set(filters.keywords):
                return False
        if filters.paper_id:
            node_paper = (node.metadata or {}).get("paper_id")
            if node_paper != filters.paper_id:
                return False
        if filters.min_quality is not None:
            node_quality = (node.metadata or {}).get("quality")
            if node_quality is None or node_quality < filters.min_quality:
                return False
        # edge_type filter requires graph join — skip in filter pass
        return True

    @staticmethod
    def _passes_edge_filters(edge, filters: EdgeFilters | None) -> bool:
        """Return True if the edge passes all filter criteria."""
        if filters is None:
            return True
        if filters.type and edge.type not in filters.type:
            return False
        if filters.verified is not None and edge.verified != filters.verified:
            return False
        return True
