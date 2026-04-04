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
        )
        mock_get.assert_called_once_with(
            host="bh-host",
            user="admin",
            password="pw",
            database="mydb",
            secure=False,
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


def test_close(store):
    """close() calls client.close()."""
    s, mock_client = store
    s.close()
    mock_client.close.assert_called_once()
