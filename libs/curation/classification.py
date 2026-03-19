"""Classification — determine relationship type for clustered node pairs.

V1 supports two classifications:
- merge (duplicate): very high similarity, similar content length
- create_equivalence: high similarity but different enough to keep both
"""

from __future__ import annotations

from libs.global_graph.models import GlobalCanonicalNode

from .models import ClusterGroup, CurationSuggestion, SimilarityPair

# Threshold above which a pair is classified as duplicate (merge)
MERGE_THRESHOLD = 0.95


def _classify_pair(
    pair: SimilarityPair,
    nodes: dict[str, GlobalCanonicalNode],
) -> CurationSuggestion:
    """Classify a single similarity pair as merge or equivalence."""
    node_a = nodes.get(pair.node_a_id)
    node_b = nodes.get(pair.node_b_id)

    score = pair.similarity_score

    # Clamp score to [0, 1] to handle floating-point precision issues
    score = max(0.0, min(1.0, score))

    # High similarity → merge candidate
    if score >= MERGE_THRESHOLD:
        # Additional heuristic: content length ratio close to 1.0 suggests true duplicate
        if node_a and node_b:
            len_a = len(node_a.representative_content)
            len_b = len(node_b.representative_content)
            length_ratio = min(len_a, len_b) / max(len_a, len_b) if max(len_a, len_b) > 0 else 1.0
            # Even with very high embedding similarity, if length ratio is very low
            # it's more likely paraphrase than duplicate
            if length_ratio < 0.5:
                return CurationSuggestion(
                    operation="create_equivalence",
                    target_ids=[pair.node_a_id, pair.node_b_id],
                    confidence=score * 0.9,
                    reason=(
                        f"High similarity ({score:.3f}) but length ratio"
                        f" {length_ratio:.2f} suggests paraphrase"
                    ),
                    evidence={
                        "cosine": score,
                        "length_ratio": length_ratio,
                        "method": pair.method,
                    },
                )

        return CurationSuggestion(
            operation="merge",
            target_ids=[pair.node_a_id, pair.node_b_id],
            confidence=score,
            reason=f"Near-identical content (similarity {score:.3f})",
            evidence={"cosine": score, "method": pair.method},
        )

    # Below merge threshold → equivalence
    return CurationSuggestion(
        operation="create_equivalence",
        target_ids=[pair.node_a_id, pair.node_b_id],
        confidence=score * 0.9,  # Discount: lower confidence for equivalence
        reason=f"Semantically similar but distinct (similarity {score:.3f})",
        evidence={"cosine": score, "method": pair.method},
    )


def classify_clusters(
    clusters: list[ClusterGroup],
    nodes: dict[str, GlobalCanonicalNode],
) -> list[CurationSuggestion]:
    """Classify all pairs within clusters into merge or equivalence suggestions.

    Args:
        clusters: Cluster groups from clustering step.
        nodes: Mapping from global_canonical_id → GlobalCanonicalNode for content lookup.

    Returns:
        List of CurationSuggestions, one per pair.
    """
    suggestions: list[CurationSuggestion] = []
    for cluster in clusters:
        for pair in cluster.pairs:
            suggestions.append(_classify_pair(pair, nodes))
    return suggestions
