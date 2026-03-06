"""Tests for StorageManager with Kuzu graph backend."""

from libs.models import HyperEdge
from libs.storage import StorageConfig, StorageManager
from libs.storage.kuzu_store import KuzuGraphStore


async def test_manager_with_kuzu(tmp_path):
    """StorageManager should instantiate KuzuGraphStore when graph_backend='kuzu'."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
    )
    manager = StorageManager(config)
    assert manager.graph is not None
    assert isinstance(manager.graph, KuzuGraphStore)
    await manager.close()


async def test_manager_kuzu_custom_path(tmp_path):
    """StorageManager should respect kuzu_path config."""
    custom_kuzu = str(tmp_path / "custom_kuzu")
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=custom_kuzu,
    )
    manager = StorageManager(config)
    assert manager.graph is not None
    assert isinstance(manager.graph, KuzuGraphStore)
    await manager.close()


async def test_manager_kuzu_auto_schema_init(tmp_path):
    """Schema should be auto-initialized — no manual initialize_schema() needed."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
    )
    manager = StorageManager(config)

    # Should work immediately without calling initialize_schema()
    edge = HyperEdge(id=1, type="deduction", tail=[10], head=[20], probability=0.8, reasoning=[])
    await manager.graph.create_hyperedge(edge)
    loaded = await manager.graph.get_hyperedge(1)
    assert loaded is not None
    assert loaded.tail == [10]
    assert loaded.head == [20]

    await manager.close()


async def test_manager_graph_backend_none(tmp_path):
    """StorageManager with graph_backend='none' should have graph=None."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="none",
    )
    manager = StorageManager(config)
    assert manager.graph is None
    await manager.close()
