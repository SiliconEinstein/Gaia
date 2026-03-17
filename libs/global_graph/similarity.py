"""Content similarity for global canonicalization.

Uses embedding cosine similarity as primary signal via EmbeddingModel.
Falls back to TF-IDF if no embedding model is provided.
"""

from __future__ import annotations

import numpy as np

from libs.embedding import EmbeddingModel

from .models import GlobalCanonicalNode

# Types that are package-local relations — never match across packages
_RELATION_TYPES = {"contradiction", "equivalence"}
# Types that require kind match
_KIND_REQUIRED_TYPES = {"question", "action"}


def cosine_similarity_vectors(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a)
    vb = np.array(b)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm < 1e-10:
        return 0.0
    return float(dot / norm)


def compute_similarity_tfidf(text_a: str, text_b: str) -> float:
    """Compute TF-IDF cosine similarity (fallback when no embedding model)."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform([text_a, text_b])
    sim = sklearn_cosine(tfidf[0:1], tfidf[1:2])[0][0]
    return float(sim)


async def find_best_match(
    content: str,
    knowledge_type: str,
    kind: str | None,
    candidates: list[GlobalCanonicalNode],
    threshold: float = 0.90,
    embedding_model: EmbeddingModel | None = None,
) -> tuple[str, float] | None:
    """Find the best matching GlobalCanonicalNode for a local node.

    Returns (global_canonical_id, similarity_score) or None if no match.
    Uses batch embedding when an embedding model is provided.
    Falls back to TF-IDF otherwise.
    """
    if knowledge_type in _RELATION_TYPES:
        return None

    if not candidates or not content.strip():
        return None

    # Filter candidates by type/kind constraints
    eligible = []
    for c in candidates:
        if c.knowledge_type != knowledge_type:
            continue
        if knowledge_type in _KIND_REQUIRED_TYPES and c.kind != kind:
            continue
        eligible.append(c)

    if not eligible:
        return None

    # Embedding path: batch embed query + all candidates
    if embedding_model is not None:  # pragma: no cover
        candidate_texts = [c.representative_content for c in eligible]
        all_texts = [content] + candidate_texts
        embeddings = await embedding_model.embed(all_texts)

        query_emb = embeddings[0]
        best_id: str | None = None
        best_score: float = 0.0
        for i, c in enumerate(eligible):
            score = cosine_similarity_vectors(query_emb, embeddings[i + 1])
            if score > best_score:
                best_score = score
                best_id = c.global_canonical_id
        if best_id is not None and best_score >= threshold:
            return (best_id, best_score)
        return None

    # Fallback: per-pair TF-IDF
    best_id = None
    best_score = 0.0
    for c in eligible:
        score = compute_similarity_tfidf(content, c.representative_content)
        if score > best_score:
            best_score = score
            best_id = c.global_canonical_id

    if best_id is not None and best_score >= threshold:
        return (best_id, best_score)
    return None
