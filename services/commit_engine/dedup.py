"""DedupChecker — finds potential duplicate nodes before committing."""

from __future__ import annotations

from libs.models import DedupCandidate
from services.search_engine.engine import SearchEngine


class DedupChecker:
    """Check for potential duplicates when new nodes are submitted.

    Uses the SearchEngine to find existing nodes similar to proposed content,
    returning candidates that exceed a similarity threshold.
    """

    def __init__(self, search_engine: SearchEngine) -> None:
        self._search_engine = search_engine

    async def check(
        self,
        contents: list[str],
        threshold: float = 0.8,
    ) -> list[list[DedupCandidate]]:
        """For each content string, find potential duplicates.

        Returns a list of candidate lists (one per input content).
        Only includes candidates with score >= threshold.
        """
        results: list[list[DedupCandidate]] = []

        for content in contents:
            scored_nodes = await self._search_engine.search_nodes(
                text=content,
                k=10,
                paths=["vector", "bm25"],
            )

            candidates = [
                DedupCandidate(
                    node_id=sn.node.id,
                    content=str(sn.node.content),
                    score=sn.score,
                )
                for sn in scored_nodes
                if sn.score >= threshold
            ]
            results.append(candidates)

        return results
