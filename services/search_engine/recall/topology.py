"""TopologyRecall — discover related nodes by traversing the Join tree."""

from __future__ import annotations

from libs.storage.neo4j_store import Neo4jGraphStore


class TopologyRecall:
    """Traverse join-type hyperedges from seed nodes to find related propositions.

    Scores are assigned based on hop distance:
    - Seed nodes receive a score of 1.0
    - All other discovered nodes receive 1.0 / (1 + hops) as a uniform lower score

    Precise distance-based scoring is unnecessary because the
    :class:`ResultMerger` combines topology scores with vector and BM25 scores.
    """

    def __init__(self, graph_store: Neo4jGraphStore) -> None:
        self._store = graph_store

    async def recall(self, seed_node_ids: list[int], hops: int = 3) -> list[tuple[int, float]]:
        """Traverse Join tree from seeds.

        Returns ``[(node_id, score), ...]`` where score is inversely
        proportional to hop distance.  Seeds themselves get ``score=1.0``,
        other discovered nodes get a uniform lower score.
        """
        if not seed_node_ids:
            return []

        node_ids, _ = await self._store.get_subgraph(
            seed_node_ids, hops=hops, edge_types=["abstraction"]
        )

        seed_set = set(seed_node_ids)
        results: list[tuple[int, float]] = []
        for nid in node_ids:
            score = 1.0 if nid in seed_set else 1.0 / (1 + hops)
            results.append((nid, score))

        # Sort by score descending, then by node id for deterministic order
        results.sort(key=lambda x: (-x[1], x[0]))
        return results
