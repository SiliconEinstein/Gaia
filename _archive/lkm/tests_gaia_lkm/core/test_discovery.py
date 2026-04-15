"""Tests for the Discovery Orchestrator (run_semantic_discovery).

Following TDD: tests written before implementation.
All ByteHouse and embedding calls are mocked to avoid real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from gaia.lkm.models.discovery import ClusteringResult, DiscoveryConfig


def _make_config(**kwargs) -> DiscoveryConfig:
    """Create a DiscoveryConfig with test-friendly defaults."""
    defaults = {
        "similarity_threshold": 0.85,
        "faiss_k": 10,
        "max_cluster_size": 20,
        "exclude_same_factor": False,
    }
    defaults.update(kwargs)
    return DiscoveryConfig(**defaults)


def _make_storage(graph=None) -> MagicMock:
    """Create a mock StorageManager."""
    storage = MagicMock()
    storage.graph = graph
    storage.list_all_public_global_ids = AsyncMock(return_value=[])
    return storage


def _make_bytehouse(embeddings_by_type: dict | None = None) -> MagicMock:
    """Create a mock ByteHouseEmbeddingStore.

    Args:
        embeddings_by_type: dict mapping node_type -> (gcn_ids, matrix).
            Types not listed return ([], np.array([])).
    """
    bytehouse = MagicMock()
    embeddings_by_type = embeddings_by_type or {}

    def _load_by_type(node_type: str):
        return embeddings_by_type.get(node_type, ([], np.array([])))

    bytehouse.load_embeddings_by_type = MagicMock(side_effect=_load_by_type)
    return bytehouse


def _similar_embeddings(n: int, dim: int = 512, seed: int = 42) -> np.ndarray:
    """Create n very similar embedding vectors that should cluster together."""
    np.random.seed(seed)
    base = np.random.randn(dim).astype(np.float32)
    noise_scale = 0.02  # very small noise → very high cosine similarity
    matrix = np.stack(
        [base + np.random.randn(dim).astype(np.float32) * noise_scale for _ in range(n)]
    )
    return matrix


# ─────────────────────────────────────────────────────────────────────────────
# RED tests — all must fail before implementation exists
# ─────────────────────────────────────────────────────────────────────────────


async def test_run_semantic_discovery_returns_clustering_result():
    """run_semantic_discovery returns a ClusteringResult instance."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    storage = _make_storage()
    bytehouse = _make_bytehouse()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 0, "computed": 0, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert isinstance(result, ClusteringResult)


async def test_run_semantic_discovery_empty():
    """When storage has no globals, the result has zero clusters."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    storage = _make_storage()
    bytehouse = _make_bytehouse()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 0, "computed": 0, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert result.clusters == []
    assert result.stats.total_clusters == 0
    assert result.stats.total_variables_scanned == 0


async def test_run_semantic_discovery_clusters_by_type():
    """Similar claim embeddings produce clusters with node_type='claim'."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    dim = 512
    n = 5
    gcn_ids = [f"gcn_{i}" for i in range(n)]
    matrix = _similar_embeddings(n, dim=dim, seed=42)

    bytehouse = _make_bytehouse({"claim": (gcn_ids, matrix)})
    storage = _make_storage()
    config = _make_config(similarity_threshold=0.85, faiss_k=10)

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": n, "computed": n, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert len(result.clusters) > 0, "Expected at least one cluster from similar embeddings"
    for cluster in result.clusters:
        assert cluster.node_type == "claim", (
            f"Expected node_type='claim', got '{cluster.node_type}'"
        )
        assert len(cluster.gcn_ids) >= 2


async def test_run_semantic_discovery_stats_match_clusters():
    """ClusteringStats.total_clusters matches actual number of clusters returned."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    n = 4
    gcn_ids = [f"gcn_{i}" for i in range(n)]
    matrix = _similar_embeddings(n, dim=512, seed=7)

    bytehouse = _make_bytehouse({"question": (gcn_ids, matrix)})
    storage = _make_storage()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": n, "computed": n, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert result.stats.total_clusters == len(result.clusters)


async def test_run_semantic_discovery_skips_types_with_less_than_2_vectors():
    """Node types with fewer than 2 embeddings produce no clusters."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    # Only 1 vector for "setting" — should be skipped
    single_vec = np.random.randn(512).astype(np.float32).reshape(1, -1)
    bytehouse = _make_bytehouse({"setting": (["gcn_only"], single_vec)})
    storage = _make_storage()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 1, "computed": 1, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    # Only "setting" has data and it has < 2 vectors → no clusters
    assert result.clusters == []


async def test_run_semantic_discovery_no_graph_graceful():
    """When storage.graph is None, factor_index is empty and no error is raised."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    storage = _make_storage(graph=None)
    bytehouse = _make_bytehouse()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 0, "computed": 0, "skipped": 0, "failed": 0},
    ):
        # Should not raise
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert isinstance(result, ClusteringResult)


async def test_run_semantic_discovery_graph_exception_graceful():
    """When graph.get_variable_factor_index raises, factor_index falls back to {}."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    mock_graph = MagicMock()
    mock_graph.get_variable_factor_index = AsyncMock(side_effect=AttributeError("not implemented"))
    storage = _make_storage(graph=mock_graph)
    bytehouse = _make_bytehouse()
    config = _make_config()

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 0, "computed": 0, "skipped": 0, "failed": 0},
    ):
        # Should not raise — falls back gracefully
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    assert isinstance(result, ClusteringResult)


async def test_idempotent_result():
    """Running twice with same mocked data produces the same cluster count."""
    from gaia.lkm.core.discovery import run_semantic_discovery

    n = 5
    gcn_ids = [f"gcn_{i}" for i in range(n)]
    matrix = _similar_embeddings(n, dim=512, seed=99)

    storage = _make_storage()
    config = _make_config()

    embed_stats = {"total": n, "computed": n, "skipped": 0, "failed": 0}

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value=embed_stats,
    ):
        bytehouse1 = _make_bytehouse({"claim": (gcn_ids, matrix)})
        result1 = await run_semantic_discovery(storage, bytehouse1, config, access_key="key")

        bytehouse2 = _make_bytehouse({"claim": (gcn_ids, matrix)})
        result2 = await run_semantic_discovery(storage, bytehouse2, config, access_key="key")

    assert len(result1.clusters) == len(result2.clusters), (
        f"First run: {len(result1.clusters)}, second run: {len(result2.clusters)}"
    )


async def test_run_semantic_discovery_result_has_timestamp():
    """ClusteringResult.timestamp is a datetime set to roughly now."""
    from datetime import datetime, timezone

    from gaia.lkm.core.discovery import run_semantic_discovery

    storage = _make_storage()
    bytehouse = _make_bytehouse()
    config = _make_config()

    before = datetime.now(timezone.utc)

    with patch(
        "gaia.lkm.core.discovery.compute_embeddings",
        new_callable=AsyncMock,
        return_value={"total": 0, "computed": 0, "skipped": 0, "failed": 0},
    ):
        result = await run_semantic_discovery(storage, bytehouse, config, access_key="test-key")

    after = datetime.now(timezone.utc)

    assert before <= result.timestamp <= after
