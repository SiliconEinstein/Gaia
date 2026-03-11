"""Tests for StorageManager — unified storage facade."""

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager


@pytest.fixture
async def full_manager(tmp_path) -> StorageManager:
    """Manager with all three stores."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu"),
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.fixture
async def no_graph_manager(tmp_path) -> StorageManager:
    """Manager with graph_backend=none."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="none",
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


class TestInitialization:
    async def test_full_init(self, full_manager):
        assert full_manager.content_store is not None
        assert full_manager.graph_store is not None
        assert full_manager.vector_store is not None

    async def test_no_graph_init(self, no_graph_manager):
        assert no_graph_manager.content_store is not None
        assert no_graph_manager.graph_store is None
        assert no_graph_manager.vector_store is not None

    async def test_close_idempotent(self, full_manager):
        await full_manager.close()
        await full_manager.close()  # should not raise
