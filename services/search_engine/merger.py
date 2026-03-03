"""ResultMerger — normalize, weight, and deduplicate scores from multiple recall paths."""

from __future__ import annotations


class ResultMerger:
    """Merge results from vector, BM25, and topology recall paths.

    Each path produces ``[(node_id, raw_score), ...]``.  The merger:
    1. Min-max normalizes each path's scores to [0, 1].
    2. For the vector path (distance-based), inverts: ``1 - normalized_distance``.
    3. Applies per-path weights.
    4. Sums weighted scores for each node, deduplicating across paths.
    5. Returns the top-k results sorted by merged score descending.
    """

    DEFAULT_WEIGHTS: dict[str, float] = {
        "vector": 0.5,
        "bm25": 0.3,
        "topology": 0.2,
    }

    # Paths where lower raw score means better result (distance-based)
    _INVERT_PATHS: set[str] = {"vector"}

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)

    async def merge(
        self,
        results: dict[str, list[tuple[int, float]]],
        k: int = 50,
    ) -> list[tuple[int, float, list[str]]]:
        """Normalize, weight, merge, dedup, and return top-k.

        Returns
        -------
        list[tuple[int, float, list[str]]]
            ``[(node_id, merged_score, sources), ...]`` sorted by score descending.
        """
        if not results:
            return []

        # Accumulator: node_id -> (total_weighted_score, set_of_sources)
        merged: dict[int, tuple[float, set[str]]] = {}

        for path_name, pairs in results.items():
            if not pairs:
                continue

            weight = self._weights.get(path_name, 0.0)
            normalized = self._normalize(pairs, invert=path_name in self._INVERT_PATHS)

            for node_id, norm_score in normalized:
                weighted = norm_score * weight
                if node_id in merged:
                    prev_score, prev_sources = merged[node_id]
                    prev_sources.add(path_name)
                    merged[node_id] = (prev_score + weighted, prev_sources)
                else:
                    merged[node_id] = (weighted, {path_name})

        # Sort by score descending, then node_id ascending for determinism
        ranked = sorted(merged.items(), key=lambda x: (-x[1][0], x[0]))

        return [(node_id, score, sorted(sources)) for node_id, (score, sources) in ranked[:k]]

    @staticmethod
    def _normalize(pairs: list[tuple[int, float]], *, invert: bool) -> list[tuple[int, float]]:
        """Min-max normalize scores to [0, 1].

        If *invert* is True, the result is ``1 - normalized`` so that lower
        raw scores (e.g. vector distances) map to higher normalized scores.
        If all raw scores are equal, every item receives 1.0.
        """
        if not pairs:
            return []

        scores = [s for _, s in pairs]
        min_s = min(scores)
        max_s = max(scores)
        span = max_s - min_s

        result: list[tuple[int, float]] = []
        for node_id, raw in pairs:
            if span == 0.0:
                norm = 1.0
            else:
                norm = (raw - min_s) / span

            if invert:
                norm = 1.0 - norm

            result.append((node_id, norm))

        return result
