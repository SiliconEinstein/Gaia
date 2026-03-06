# tests/libs/storage/test_manager.py
from libs.storage import StorageManager, StorageConfig
from libs.storage.lance_store import LanceStore
from libs.storage.id_generator import IDGenerator
from libs.storage.vector_search.base import VectorSearchClient
from tests.conftest import load_fixture_nodes


async def test_manager_creates_local_stores(tmp_path):
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
    )
    manager = StorageManager(config)
    assert isinstance(manager.lance, LanceStore)
    assert isinstance(manager.ids, IDGenerator)
    assert isinstance(manager.vector, VectorSearchClient)
    await manager.close()


async def test_manager_ids_work(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    manager = StorageManager(config)
    nid = await manager.ids.alloc_node_id()
    assert nid >= 1
    await manager.close()


async def test_manager_lance_works(tmp_path):
    from libs.models import Node

    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    manager = StorageManager(config)
    node = Node(id=1, type="paper-extract", content="test")
    await manager.lance.save_nodes([node])
    loaded = await manager.lance.load_node(1)
    assert loaded is not None
    assert loaded.content == "test"
    await manager.close()


async def test_manager_with_fixture_data(tmp_path):
    """StorageManager can ingest and retrieve fixture nodes."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    manager = StorageManager(config)

    nodes = load_fixture_nodes()
    await manager.lance.save_nodes(nodes)

    # Verify nodes are retrievable
    loaded = await manager.lance.load_node(nodes[0].id)
    assert loaded is not None
    assert loaded.content == nodes[0].content

    # Verify bulk load
    ids = [n.id for n in nodes[:5]]
    bulk = await manager.lance.load_nodes_bulk(ids)
    assert len(bulk) == 5

    await manager.close()
