"""Unit tests for discovery data models (M6 Semantic Discovery)."""

from __future__ import annotations

from datetime import datetime, timezone

from gaia.lkm.models.discovery import (
    ClusteringResult,
    ClusteringStats,
    DiscoveryConfig,
    SemanticCluster,
)


class TestSemanticClusterFields:
    def test_semantic_cluster_fields(self):
        cluster = SemanticCluster(
            cluster_id="cluster-001",
            node_type="claim",
            gcn_ids=["gcn-a", "gcn-b", "gcn-c"],
            centroid_gcn_id="gcn-b",
            avg_similarity=0.91,
            min_similarity=0.87,
        )
        assert cluster.cluster_id == "cluster-001"
        assert cluster.node_type == "claim"
        assert cluster.gcn_ids == ["gcn-a", "gcn-b", "gcn-c"]
        assert cluster.centroid_gcn_id == "gcn-b"
        assert cluster.avg_similarity == 0.91
        assert cluster.min_similarity == 0.87

    def test_semantic_cluster_node_types(self):
        """Each valid node_type should be storable without error."""
        for node_type in ("claim", "question", "setting", "action"):
            c = SemanticCluster(
                cluster_id="x",
                node_type=node_type,
                gcn_ids=["g1"],
                centroid_gcn_id="g1",
                avg_similarity=1.0,
                min_similarity=1.0,
            )
            assert c.node_type == node_type

    def test_semantic_cluster_gcn_ids_are_list(self):
        cluster = SemanticCluster(
            cluster_id="c",
            node_type="question",
            gcn_ids=[],
            centroid_gcn_id="",
            avg_similarity=0.0,
            min_similarity=0.0,
        )
        assert isinstance(cluster.gcn_ids, list)


class TestClusteringStatsDefaults:
    def test_clustering_stats_fields(self):
        stats = ClusteringStats(
            total_variables_scanned=1000,
            total_embeddings_computed=950,
            total_clusters=42,
            cluster_size_distribution={2: 10, 3: 5, 4: 2},
            elapsed_seconds=3.14,
        )
        assert stats.total_variables_scanned == 1000
        assert stats.total_embeddings_computed == 950
        assert stats.total_clusters == 42
        assert stats.cluster_size_distribution == {2: 10, 3: 5, 4: 2}
        assert stats.elapsed_seconds == 3.14

    def test_clustering_stats_distribution_type(self):
        stats = ClusteringStats(
            total_variables_scanned=0,
            total_embeddings_computed=0,
            total_clusters=0,
            cluster_size_distribution={},
            elapsed_seconds=0.0,
        )
        assert isinstance(stats.cluster_size_distribution, dict)


class TestClusteringResultRoundtrip:
    def test_clustering_result_roundtrip(self):
        ts = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)
        cluster = SemanticCluster(
            cluster_id="c1",
            node_type="claim",
            gcn_ids=["g1", "g2"],
            centroid_gcn_id="g1",
            avg_similarity=0.9,
            min_similarity=0.88,
        )
        stats = ClusteringStats(
            total_variables_scanned=100,
            total_embeddings_computed=98,
            total_clusters=1,
            cluster_size_distribution={2: 1},
            elapsed_seconds=1.5,
        )
        result = ClusteringResult(clusters=[cluster], stats=stats, timestamp=ts)

        assert len(result.clusters) == 1
        assert result.clusters[0].cluster_id == "c1"
        assert result.stats.total_clusters == 1
        assert result.timestamp == ts

    def test_clustering_result_empty_clusters(self):
        stats = ClusteringStats(
            total_variables_scanned=0,
            total_embeddings_computed=0,
            total_clusters=0,
            cluster_size_distribution={},
            elapsed_seconds=0.0,
        )
        result = ClusteringResult(
            clusters=[],
            stats=stats,
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert result.clusters == []


class TestDiscoveryConfigDefaults:
    def test_discovery_config_defaults(self):
        cfg = DiscoveryConfig()
        assert cfg.embedding_api_url == "https://openapi.dp.tech/openapi/v1/test/vectorize"
        assert cfg.embedding_provider == "dashscope"
        assert cfg.embedding_dim == 512
        assert cfg.embedding_concurrency == 15
        assert cfg.embedding_max_retries == 3
        assert cfg.embedding_http_timeout == 30
        assert cfg.similarity_threshold == 0.85
        assert cfg.faiss_k == 100
        assert cfg.max_cluster_size == 20
        assert cfg.exclude_same_factor is True
        assert cfg.faiss_index_type == "flat"

    def test_discovery_config_override(self):
        cfg = DiscoveryConfig(similarity_threshold=0.92, embedding_dim=1024)
        assert cfg.similarity_threshold == 0.92
        assert cfg.embedding_dim == 1024
        # other fields keep defaults
        assert cfg.faiss_k == 100
