"""Clustering — discover groups of similar GlobalCanonicalNodes.

Uses dual-recall: embedding cosine similarity (primary) + TF-IDF (secondary).
Both signals are computed and their results merged (union). Pairs found by
both methods get method="both" and the max score.

Spec reference: §3.1 — "ANN + BM25 dual recall".

Clustering strategy: single-linkage on pairwise similarity above threshold.
"""

from __future__ import annotations

from uuid import uuid4

import numpy as np

from libs.embedding import EmbeddingModel
from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import compute_similarity_tfidf

from .models import ClusterGroup, SimilarityPair


def _build_clusters_from_pairs(pairs: list[SimilarityPair]) -> list[ClusterGroup]:
    """Build clusters from similarity pairs using union-find (single linkage)."""
    if not pairs:
        return []

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pair in pairs:
        parent.setdefault(pair.node_a_id, pair.node_a_id)
        parent.setdefault(pair.node_b_id, pair.node_b_id)
        union(pair.node_a_id, pair.node_b_id)

    # Group by root
    groups: dict[str, list[str]] = {}
    for node_id in parent:
        root = find(node_id)
        groups.setdefault(root, []).append(node_id)

    # Attach pairs to their cluster
    pair_index: dict[str, list[SimilarityPair]] = {}
    for pair in pairs:
        root = find(pair.node_a_id)
        pair_index.setdefault(root, []).append(pair)

    return [
        ClusterGroup(
            cluster_id=f"cluster_{uuid4().hex[:8]}",
            node_ids=sorted(members),
            pairs=pair_index.get(root, []),
        )
        for root, members in groups.items()
        if len(members) >= 2
    ]


def _merge_pair_sets(
    emb_pairs: dict[tuple[str, str], SimilarityPair],
    tfidf_pairs: dict[tuple[str, str], SimilarityPair],
) -> list[SimilarityPair]:
    """Merge embedding and TF-IDF pair results (union). Dual-recall."""
    all_keys = set(emb_pairs.keys()) | set(tfidf_pairs.keys())
    merged: list[SimilarityPair] = []
    for key in all_keys:
        ep = emb_pairs.get(key)
        tp = tfidf_pairs.get(key)
        if ep and tp:
            merged.append(
                SimilarityPair(
                    node_a_id=key[0],
                    node_b_id=key[1],
                    similarity_score=max(ep.similarity_score, tp.similarity_score),
                    method="both",
                )
            )
        elif ep:
            merged.append(ep)
        else:
            assert tp is not None
            merged.append(tp)
    return merged


async def cluster_similar_nodes(
    nodes: list[GlobalCanonicalNode],
    threshold: float = 0.90,
    embedding_model: EmbeddingModel | None = None,
) -> list[ClusterGroup]:
    """Find clusters of similar nodes via dual-recall: embedding + TF-IDF.

    Both signals are always computed (when embedding_model is available).
    Results are merged (union) so pairs caught by either method are included.

    Args:
        nodes: All GlobalCanonicalNodes to compare.
        threshold: Minimum similarity to consider a pair.
        embedding_model: For embedding computation. TF-IDF always runs as secondary.

    Returns:
        List of ClusterGroups, each containing ≥2 similar nodes.
    """
    if len(nodes) < 2:
        return []

    emb_pairs: dict[tuple[str, str], SimilarityPair] = {}
    tfidf_pairs: dict[tuple[str, str], SimilarityPair] = {}

    # Embedding recall (primary)
    if embedding_model is not None:
        texts = [n.representative_content for n in nodes]
        embeddings = await embedding_model.embed(texts)

        emb_matrix = np.array(embeddings)
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        normalized = emb_matrix / norms
        sim_matrix = normalized @ normalized.T

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if nodes[i].knowledge_type != nodes[j].knowledge_type:
                    continue
                score = float(sim_matrix[i, j])
                if score >= threshold:
                    key = (nodes[i].global_canonical_id, nodes[j].global_canonical_id)
                    emb_pairs[key] = SimilarityPair(
                        node_a_id=key[0],
                        node_b_id=key[1],
                        similarity_score=score,
                        method="embedding",
                    )

    # TF-IDF recall (secondary, always runs)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if nodes[i].knowledge_type != nodes[j].knowledge_type:
                continue
            score = compute_similarity_tfidf(
                nodes[i].representative_content,
                nodes[j].representative_content,
            )
            if score >= threshold:
                key = (nodes[i].global_canonical_id, nodes[j].global_canonical_id)
                tfidf_pairs[key] = SimilarityPair(
                    node_a_id=key[0],
                    node_b_id=key[1],
                    similarity_score=score,
                    method="bm25",
                )

    # Merge dual-recall results
    merged_pairs = _merge_pair_sets(emb_pairs, tfidf_pairs)
    return _build_clusters_from_pairs(merged_pairs)
