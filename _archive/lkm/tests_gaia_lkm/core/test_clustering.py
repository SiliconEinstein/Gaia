"""Tests for FAISS-based semantic clustering with Union-Find.

Following TDD: tests written before implementation.
"""

from __future__ import annotations

import numpy as np

from gaia.lkm.models.discovery import DiscoveryConfig, SemanticCluster


def _make_config(**kwargs) -> DiscoveryConfig:
    """Create a DiscoveryConfig with test-friendly defaults."""
    defaults = {
        "similarity_threshold": 0.90,
        "faiss_k": 10,
        "max_cluster_size": 20,
        "exclude_same_factor": True,
    }
    defaults.update(kwargs)
    return DiscoveryConfig(**defaults)


def _make_similar_pair(dim: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Create two very similar vectors (high cosine similarity)."""
    np.random.seed(42)
    base = np.random.randn(dim).astype(np.float32)
    noise = np.random.randn(dim).astype(np.float32) * 0.05
    return base, base + noise


def _normalize(v: np.ndarray) -> np.ndarray:
    """L2-normalize a vector."""
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


# ─────────────────────────────────────────────────────────────────────────────
# RED tests — all must fail before implementation exists
# ─────────────────────────────────────────────────────────────────────────────


def test_similar_pairs_clustered():
    """Two very similar vectors are merged into the same cluster."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    config = _make_config(similarity_threshold=0.90)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    # Both nodes should end up in exactly one cluster together
    assert len(clusters) == 1
    cluster = clusters[0]
    assert set(cluster.gcn_ids) == {"node_a", "node_b"}


def test_dissimilar_not_clustered():
    """Opposite vectors (cosine ~ -1) produce no clusters of size >= 2."""
    from gaia.lkm.core._clustering import cluster_embeddings

    np.random.seed(42)
    v1 = np.random.randn(512).astype(np.float32)
    v2 = -v1  # opposite direction → cosine similarity ≈ -1

    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    config = _make_config(similarity_threshold=0.85)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    # No cluster should contain both nodes (size-1 clusters are dropped)
    assert len(clusters) == 0


def test_max_cluster_size_enforced():
    """30 near-identical vectors with max_cluster_size=10 → all clusters <= 10."""
    from gaia.lkm.core._clustering import cluster_embeddings

    np.random.seed(42)
    n = 30
    base = np.random.randn(512).astype(np.float32)
    # All vectors are very close to base
    matrix = np.stack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(n)])
    gcn_ids = [f"node_{i}" for i in range(n)]

    config = _make_config(
        similarity_threshold=0.80,
        max_cluster_size=10,
        faiss_k=30,
    )
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert len(clusters) > 0, "Expected at least one cluster"
    for cluster in clusters:
        assert len(cluster.gcn_ids) <= 10, f"Cluster too large: {len(cluster.gcn_ids)}"

    # All 30 nodes should be covered
    all_covered = {gcn_id for c in clusters for gcn_id in c.gcn_ids}
    assert all_covered == set(gcn_ids)


def test_max_cluster_size_no_dropped_remainder():
    """21 near-identical vectors with max_cluster_size=20 → no node is dropped.

    Regression test: a remainder of 1 node must be merged into the last chunk,
    not silently discarded.
    """
    from gaia.lkm.core._clustering import cluster_embeddings

    np.random.seed(99)
    n = 21
    base = np.random.randn(512).astype(np.float32)
    matrix = np.stack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(n)])
    gcn_ids = [f"node_{i}" for i in range(n)]

    config = _make_config(similarity_threshold=0.80, max_cluster_size=20, faiss_k=30)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    all_covered = {gid for c in clusters for gid in c.gcn_ids}
    assert all_covered == set(gcn_ids), f"Missing nodes: {set(gcn_ids) - all_covered}"


def test_exclude_same_factor():
    """Two similar vectors sharing a factor are NOT merged into a cluster."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    # Both nodes share factor "factor_x"
    factor_index = {
        "node_a": {"factor_x", "factor_y"},
        "node_b": {"factor_x", "factor_z"},
    }

    config = _make_config(similarity_threshold=0.90, exclude_same_factor=True)
    clusters = cluster_embeddings(gcn_ids, matrix, config, factor_index=factor_index)

    # Should not be clustered together because they share factor_x
    assert len(clusters) == 0


def test_exclude_same_factor_disabled():
    """When exclude_same_factor=False, shared factors don't prevent clustering."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    factor_index = {
        "node_a": {"factor_x"},
        "node_b": {"factor_x"},
    }

    config = _make_config(similarity_threshold=0.90, exclude_same_factor=False)
    clusters = cluster_embeddings(gcn_ids, matrix, config, factor_index=factor_index)

    # Shared factor ignored when exclude_same_factor=False
    assert len(clusters) == 1
    assert set(clusters[0].gcn_ids) == {"node_a", "node_b"}


def test_cluster_stats():
    """Cluster centroid_gcn_id is a valid member; similarity stats are in [0, 1]."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    config = _make_config(similarity_threshold=0.90)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert len(clusters) == 1
    cluster = clusters[0]

    # centroid must be a member of the cluster
    assert cluster.centroid_gcn_id in cluster.gcn_ids

    # similarity stats must be sensible
    assert 0.0 <= cluster.min_similarity <= cluster.avg_similarity <= 1.0


def test_cluster_id_format():
    """Each cluster has a unique cluster_id with the 'cl_' prefix."""
    from gaia.lkm.core._clustering import cluster_embeddings

    np.random.seed(7)
    n = 6
    base = np.random.randn(512).astype(np.float32)
    matrix = np.stack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(n)])
    gcn_ids = [f"node_{i}" for i in range(n)]

    config = _make_config(similarity_threshold=0.80, max_cluster_size=3, faiss_k=6)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert len(clusters) > 0
    ids = [c.cluster_id for c in clusters]
    # All unique
    assert len(ids) == len(set(ids))
    # All start with "cl_"
    for cid in ids:
        assert cid.startswith("cl_"), f"Bad cluster_id: {cid!r}"


def test_single_node_no_cluster():
    """A single node produces no clusters (minimum cluster size is 2)."""
    from gaia.lkm.core._clustering import cluster_embeddings

    np.random.seed(42)
    v = np.random.randn(512).astype(np.float32)
    gcn_ids = ["node_a"]
    matrix = v[np.newaxis, :]

    config = _make_config()
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert clusters == []


def test_empty_input():
    """Empty input returns an empty list."""
    from gaia.lkm.core._clustering import cluster_embeddings

    gcn_ids: list[str] = []
    matrix = np.empty((0, 512), dtype=np.float32)

    config = _make_config()
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert clusters == []


def test_node_type_empty_string():
    """node_type is empty string (filled by caller, not by cluster_embeddings)."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    config = _make_config(similarity_threshold=0.90)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert len(clusters) == 1
    assert clusters[0].node_type == ""


def test_return_type_is_semantic_cluster():
    """Return type is list[SemanticCluster]."""
    from gaia.lkm.core._clustering import cluster_embeddings

    v1, v2 = _make_similar_pair()
    gcn_ids = ["node_a", "node_b"]
    matrix = np.stack([v1, v2])

    config = _make_config(similarity_threshold=0.90)
    clusters = cluster_embeddings(gcn_ids, matrix, config)

    assert isinstance(clusters, list)
    for c in clusters:
        assert isinstance(c, SemanticCluster)
