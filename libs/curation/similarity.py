"""Shared similarity function for curation.

find_similar() is the 1-vs-N similarity lookup used by both global
canonicalization (1 local node vs global graph) and curation clustering
(N:N via repeated 1-vs-N calls or matrix approach).

Spec reference: §4 shared bottom functions.
"""

from __future__ import annotations

from libs.embedding import EmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import (
    compute_similarity_tfidf,
    cosine_similarity_vectors,
)

# Types that are package-local — never match across packages
_RELATION_TYPES = {"contradiction", "equivalence"}
_KIND_REQUIRED_TYPES = {"question", "action"}


async def find_similar(
    node: GlobalCanonicalNode,
    candidates: list[GlobalCanonicalNode],
    threshold: float = 0.90,
    embedding_model: EmbeddingModel | None = None,
) -> list[tuple[str, float]]:
    """Find candidates similar to node above threshold.

    Args:
        node: The query node.
        candidates: Nodes to compare against.
        threshold: Minimum similarity score.
        embedding_model: For embedding-based similarity. Falls back to TF-IDF if None.

    Returns:
        List of (global_canonical_id, similarity_score) sorted by score descending.
    """
    if not candidates or not node.representative_content.strip():
        return []

    if node.knowledge_type in _RELATION_TYPES:
        return []

    # Filter by type/kind constraints
    eligible = []
    for c in candidates:
        if c.global_canonical_id == node.global_canonical_id:
            continue  # Skip self
        if c.knowledge_type != node.knowledge_type:
            continue
        if node.knowledge_type in _KIND_REQUIRED_TYPES and c.kind != node.kind:
            continue
        eligible.append(c)

    if not eligible:
        return []

    results: list[tuple[str, float]] = []

    if embedding_model is not None:
        texts = [node.representative_content] + [c.representative_content for c in eligible]
        embeddings = await embedding_model.embed(texts)
        query_emb = embeddings[0]
        for i, c in enumerate(eligible):
            score = cosine_similarity_vectors(query_emb, embeddings[i + 1])
            if score >= threshold:
                results.append((c.global_canonical_id, score))
    else:
        for c in eligible:
            score = compute_similarity_tfidf(node.representative_content, c.representative_content)
            if score >= threshold:
                results.append((c.global_canonical_id, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
