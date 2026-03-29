"""Similarity matching engine for knowledge node deduplication.

Implements the matching strategy from docs/foundations/graph-ir/graph-ir.md §3.3:
- Embedding cosine similarity (primary) when an EmbeddingModel is provided
- TF-IDF cosine similarity (fallback) when no embedding model
- Type filter: only same-type candidates are eligible
- Template filter: additionally compares parameter structure
"""

from __future__ import annotations

import math

from gaia.libs.embedding import EmbeddingModel
from gaia.models.graph_ir import KnowledgeNode, KnowledgeType


async def find_best_match(
    query_node: KnowledgeNode,
    candidates: list[KnowledgeNode],
    embedding_model: EmbeddingModel | None = None,
    threshold: float = 0.90,
) -> tuple[KnowledgeNode, float] | None:
    """Find the best matching candidate for a query node.

    Args:
        query_node: Local node to match (must have content).
        candidates: Global nodes to match against.
        embedding_model: If provided, use embedding cosine similarity. Otherwise TF-IDF.
        threshold: Minimum similarity score to accept a match.

    Returns:
        (matched_node, similarity_score) or None if no match above threshold.
    """
    # Filter: same type only
    eligible = [c for c in candidates if c.type == query_node.type]

    # Template filter: require identical parameter structure
    if query_node.type == KnowledgeType.TEMPLATE:
        query_params = _parameter_signature(query_node)
        eligible = [c for c in eligible if _parameter_signature(c) == query_params]

    if not eligible:
        return None

    # Compute similarities
    if embedding_model is not None:
        scores = await _embedding_similarities(query_node, eligible, embedding_model)
    else:
        scores = _tfidf_similarities(query_node, eligible)

    # Find best above threshold
    best_idx = -1
    best_score = -1.0
    for i, score in enumerate(scores):
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= threshold:
        return eligible[best_idx], best_score

    return None


def compute_similarity(text_a: str, text_b: str, method: str = "tfidf") -> float:
    """Compute similarity between two texts. Returns score in [0, 1].

    Args:
        text_a: First text.
        text_b: Second text.
        method: Similarity method. Currently only "tfidf" is supported.

    Returns:
        Cosine similarity score between 0.0 and 1.0.
    """
    if method != "tfidf":
        raise ValueError(f"Unsupported similarity method: {method}")

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
    sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return float(sim[0, 0])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parameter_signature(node: KnowledgeNode) -> frozenset[tuple[str, str]]:
    """Extract a comparable parameter structure from a node."""
    return frozenset((p.name, p.type) for p in node.parameters)


async def _embedding_similarities(
    query: KnowledgeNode,
    candidates: list[KnowledgeNode],
    model: EmbeddingModel,
) -> list[float]:
    """Compute cosine similarities using embedding model."""
    assert query.content is not None
    texts = [query.content] + [c.content for c in candidates if c.content is not None]
    vectors = await model.embed(texts)

    query_vec = vectors[0]
    scores = []
    for i in range(1, len(vectors)):
        scores.append(_cosine_similarity(query_vec, vectors[i]))
    return scores


def _tfidf_similarities(
    query: KnowledgeNode,
    candidates: list[KnowledgeNode],
) -> list[float]:
    """Compute TF-IDF cosine similarities."""
    assert query.content is not None
    return [
        compute_similarity(query.content, c.content) for c in candidates if c.content is not None
    ]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)
