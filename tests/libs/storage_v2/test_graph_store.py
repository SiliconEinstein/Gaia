"""Tests for KuzuGraphStore schema initialisation."""

import pytest

from libs.storage_v2.kuzu_graph_store import KuzuGraphStore


@pytest.fixture
async def graph_store(tmp_path):
    """Create a KuzuGraphStore in a temporary directory with schema initialized."""
    store = KuzuGraphStore(tmp_path / "kuzu_db")
    await store.initialize_schema()
    yield store
    await store.close()


def _table_names(store: KuzuGraphStore) -> set[str]:
    """Return the set of table names in the database."""
    result = store._execute("CALL show_tables() RETURN *")
    names: set[str] = set()
    while result.has_next():
        row = result.get_next()
        names.add(row[1])
    return names


class TestInitializeSchema:
    """Verify that initialize_schema creates the expected tables."""

    async def test_initialize_creates_tables(self, graph_store: KuzuGraphStore):
        tables = _table_names(graph_store)
        assert "Closure" in tables
        assert "Chain" in tables
        assert "PREMISE" in tables
        assert "CONCLUSION" in tables

    async def test_initialize_idempotent(self, graph_store: KuzuGraphStore):
        """Calling initialize_schema a second time should not raise."""
        await graph_store.initialize_schema()
        tables = _table_names(graph_store)
        assert "Closure" in tables
        assert "Chain" in tables
