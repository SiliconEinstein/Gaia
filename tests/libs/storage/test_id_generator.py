import pytest
from libs.storage.id_generator import IDGenerator


@pytest.fixture
def gen(tmp_path):
    return IDGenerator(storage_path=str(tmp_path / "ids"))


async def test_alloc_node_id(gen):
    id1 = await gen.alloc_node_id()
    id2 = await gen.alloc_node_id()
    assert id1 >= 1
    assert id2 == id1 + 1


async def test_alloc_hyperedge_id(gen):
    id1 = await gen.alloc_hyperedge_id()
    id2 = await gen.alloc_hyperedge_id()
    assert id1 >= 1
    assert id2 == id1 + 1


async def test_alloc_node_ids_bulk(gen):
    ids = await gen.alloc_node_ids_bulk(5)
    assert len(ids) == 5
    assert ids == list(range(ids[0], ids[0] + 5))


async def test_alloc_hyperedge_ids_bulk(gen):
    ids = await gen.alloc_hyperedge_ids_bulk(3)
    assert len(ids) == 3
    assert ids == list(range(ids[0], ids[0] + 3))


async def test_node_and_edge_ids_independent(gen):
    nid = await gen.alloc_node_id()
    eid = await gen.alloc_hyperedge_id()
    assert nid == 1
    assert eid == 1


async def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "ids")
    gen1 = IDGenerator(storage_path=path)
    await gen1.alloc_node_ids_bulk(10)

    gen2 = IDGenerator(storage_path=path)
    next_id = await gen2.alloc_node_id()
    assert next_id == 11
