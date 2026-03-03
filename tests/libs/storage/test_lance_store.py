# tests/libs/storage/test_lance_store.py
import pytest
from libs.models import Node
from libs.storage.lance_store import LanceStore


@pytest.fixture
async def store(tmp_path):
    s = LanceStore(db_path=str(tmp_path / "lance"))
    yield s
    await s.close()


def _make_node(id: int, content: str = "test node", type: str = "paper-extract") -> Node:
    return Node(id=id, type=type, content=content, keywords=["test"])


async def test_save_and_load_node(store):
    node = _make_node(1, "DFT predicts fcc YH10 stable")
    await store.save_nodes([node])
    loaded = await store.load_node(1)
    assert loaded is not None
    assert loaded.id == 1
    assert loaded.content == "DFT predicts fcc YH10 stable"


async def test_load_nonexistent(store):
    result = await store.load_node(999)
    assert result is None


async def test_load_nodes_bulk(store):
    nodes = [_make_node(i, f"node {i}") for i in range(1, 4)]
    await store.save_nodes(nodes)
    loaded = await store.load_nodes_bulk([1, 2, 3])
    assert len(loaded) == 3
    texts = {n.content for n in loaded}
    assert "node 1" in texts


async def test_load_nodes_bulk_partial(store):
    await store.save_nodes([_make_node(1)])
    loaded = await store.load_nodes_bulk([1, 999])
    assert len(loaded) == 1


async def test_update_node(store):
    await store.save_nodes([_make_node(1, "original")])
    await store.update_node(1, content="updated", status="deleted")
    loaded = await store.load_node(1)
    assert loaded.content == "updated"
    assert loaded.status == "deleted"


async def test_update_beliefs(store):
    await store.save_nodes([_make_node(1), _make_node(2, "second")])
    await store.update_beliefs({1: 0.8, 2: 0.6})
    beliefs = await store.get_beliefs_bulk([1, 2])
    assert beliefs[1] == pytest.approx(0.8)
    assert beliefs[2] == pytest.approx(0.6)


async def test_fts_search(store):
    await store.save_nodes(
        [
            _make_node(1, "YH10 superconductivity at high pressure 400GPa"),
            _make_node(2, "LaH10 high pressure experiment results"),
            _make_node(3, "Copper oxide cuprate superconductor mechanism"),
        ]
    )
    results = await store.fts_search("superconductivity", k=10)
    assert len(results) >= 1
    node_ids = [r[0] for r in results]
    assert 1 in node_ids
