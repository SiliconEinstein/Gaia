"""Unit tests for ByteHouseEmbeddingStore — mocked clickhouse_connect."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def store(mock_client):
    with patch("clickhouse_connect.get_client", return_value=mock_client):
        s = ByteHouseEmbeddingStore(
            host="localhost",
            user="default",
            password="secret",
            database="paper_data",
            secure=True,
            replication_root="/clickhouse/test/root",
        )
    return s, mock_client


def test_constructor_connects():
    """Constructor calls clickhouse_connect.get_client with correct args."""
    mock_client = MagicMock()
    with patch("clickhouse_connect.get_client", return_value=mock_client) as mock_get:
        store = ByteHouseEmbeddingStore(
            host="bh-host",
            user="admin",
            password="pw",
            database="mydb",
            secure=False,
            replication_root="/clickhouse/test/root",
        )
        mock_get.assert_called_once_with(
            host="bh-host",
            user="admin",
            password="pw",
            database="mydb",
            secure=False,
            compress=False,
        )
    assert store._client is mock_client


def test_ensure_table_executes_ddl(store):
    """ensure_table calls client.command with DDL containing required identifiers."""
    s, mock_client = store
    s.ensure_table()
    mock_client.command.assert_called_once()
    ddl = mock_client.command.call_args[0][0]
    assert "node_embeddings" in ddl
    assert "HaUniqueMergeTree" in ddl


def test_get_existing_gcn_ids(store):
    """get_existing_gcn_ids returns a set of gcn_id strings from the table."""
    s, mock_client = store
    mock_client.query.return_value.result_rows = [("id1",), ("id2",), ("id3",)]
    result = s.get_existing_gcn_ids()
    assert result == {"id1", "id2", "id3"}
    mock_client.query.assert_called_once()
    sql = mock_client.query.call_args[0][0]
    assert "gcn_id" in sql
    assert "node_embeddings" in sql


def test_upsert_embeddings(store):
    """upsert_embeddings calls client.insert with correct table and data."""
    s, mock_client = store
    records = [
        {
            "gcn_id": "node1",
            "content": "some content",
            "node_type": "claim",
            "embedding": [0.1] * 512,
            "source_id": "src1",
        },
        {
            "gcn_id": "node2",
            "content": "other content",
            "node_type": "question",
            "embedding": [0.2] * 512,
            "source_id": "src2",
        },
    ]
    s.upsert_embeddings(records)
    mock_client.insert.assert_called_once()
    call_kwargs = mock_client.insert.call_args
    # First positional arg is table name
    assert call_kwargs[0][0] == ByteHouseEmbeddingStore.TABLE
    # Second positional arg is the data rows
    data = call_kwargs[0][1]
    assert len(data) == 2
    # column_names kwarg present
    assert "column_names" in call_kwargs[1]


def test_load_embeddings_by_type(store):
    """load_embeddings_by_type returns (gcn_ids, matrix) with correct shape."""
    s, mock_client = store
    emb1 = [0.1] * 512
    emb2 = [0.2] * 512
    mock_client.query.return_value.result_rows = [
        ("node1", emb1),
        ("node2", emb2),
    ]
    gcn_ids, matrix = s.load_embeddings_by_type("claim")
    assert gcn_ids == ["node1", "node2"]
    assert matrix.shape == (2, 512)
    assert matrix.dtype == np.float32
    mock_client.query.assert_called_once()
    call_args = mock_client.query.call_args
    # Should filter by node_type
    sql = call_args[0][0]
    assert "node_type" in sql


def test_load_embeddings_empty(store):
    """load_embeddings_by_type returns ([], empty array) when no rows."""
    s, mock_client = store
    mock_client.query.return_value.result_rows = []
    gcn_ids, matrix = s.load_embeddings_by_type("claim")
    assert gcn_ids == []
    assert matrix.shape == (0,)


def test_ensure_discovery_tables(store):
    """ensure_discovery_tables creates both runs and clusters tables."""
    s, mock_client = store
    s.ensure_discovery_tables()
    assert mock_client.command.call_count == 2
    ddls = [call[0][0] for call in mock_client.command.call_args_list]
    assert any("discovery_runs" in d for d in ddls)
    assert any("discovery_clusters" in d for d in ddls)


def test_save_discovery_result(store):
    """save_discovery_result writes run metadata and cluster rows."""
    from datetime import datetime, timezone
    from gaia.lkm.models.discovery import (
        ClusteringResult,
        ClusteringStats,
        DiscoveryConfig,
        SemanticCluster,
    )

    s, mock_client = store
    result = ClusteringResult(
        clusters=[
            SemanticCluster(
                cluster_id="cl_001",
                node_type="claim",
                gcn_ids=["gcn_a", "gcn_b"],
                centroid_gcn_id="gcn_a",
                avg_similarity=0.9,
                min_similarity=0.85,
            ),
        ],
        stats=ClusteringStats(
            total_variables_scanned=100,
            total_embeddings_computed=10,
            total_clusters=1,
            cluster_size_distribution={2: 1},
            elapsed_seconds=5.0,
        ),
        timestamp=datetime.now(timezone.utc),
    )
    config = DiscoveryConfig(similarity_threshold=0.85, faiss_k=100)

    run_id = s.save_discovery_result(result, config)

    assert len(run_id) == 16
    # Should have 2 insert calls: 1 for run, 1 for clusters
    assert mock_client.insert.call_count == 2


def test_load_clusters_by_run(store):
    """load_clusters_by_run returns cluster dicts."""
    s, mock_client = store
    mock_client.query.return_value.result_rows = [
        ("cl_001", "claim", ["gcn_a", "gcn_b"], "gcn_a", 0.9, 0.85),
    ]
    clusters = s.load_clusters_by_run("run123")
    assert len(clusters) == 1
    assert clusters[0]["cluster_id"] == "cl_001"
    assert clusters[0]["gcn_ids"] == ["gcn_a", "gcn_b"]


def test_close(store):
    """close() calls client.close()."""
    s, mock_client = store
    s.close()
    mock_client.close.assert_called_once()
