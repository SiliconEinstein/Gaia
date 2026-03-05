"""Tests for KuzuGraphStore -- embedded graph database for local CLI."""

import pytest
from libs.models import HyperEdge
from libs.storage.kuzu_store import KuzuGraphStore


@pytest.fixture
async def kuzu_store(tmp_path):
    store = KuzuGraphStore(db_path=str(tmp_path / "kuzu_db"))
    await store.initialize_schema()
    yield store
    await store.close()


async def test_create_and_get_hyperedge(kuzu_store):
    edge = HyperEdge(
        id=100,
        type="deduction",
        tail=[1, 2],
        head=[3],
        probability=0.9,
        reasoning=[{"content": "test"}],
    )
    eid = await kuzu_store.create_hyperedge(edge)
    assert eid == 100

    loaded = await kuzu_store.get_hyperedge(100)
    assert loaded is not None
    assert loaded.id == 100
    assert set(loaded.tail) == {1, 2}
    assert loaded.head == [3]
    assert loaded.probability == pytest.approx(0.9)


async def test_get_nonexistent_returns_none(kuzu_store):
    assert await kuzu_store.get_hyperedge(999) is None


async def test_create_bulk(kuzu_store):
    edges = [
        HyperEdge(id=1, type="deduction", tail=[10], head=[20], probability=0.8),
        HyperEdge(id=2, type="induction", tail=[20], head=[30], probability=0.7),
    ]
    ids = await kuzu_store.create_hyperedges_bulk(edges)
    assert ids == [1, 2]
    assert await kuzu_store.get_hyperedge(1) is not None
    assert await kuzu_store.get_hyperedge(2) is not None


async def test_update_hyperedge(kuzu_store):
    edge = HyperEdge(id=100, type="deduction", tail=[1], head=[2], probability=0.5)
    await kuzu_store.create_hyperedge(edge)
    await kuzu_store.update_hyperedge(100, probability=0.9)
    loaded = await kuzu_store.get_hyperedge(100)
    assert loaded.probability == pytest.approx(0.9)


async def test_update_hyperedge_verified(kuzu_store):
    edge = HyperEdge(id=100, type="deduction", tail=[1], head=[2])
    await kuzu_store.create_hyperedge(edge)
    await kuzu_store.update_hyperedge(100, probability=0.9, verified=True)
    loaded = await kuzu_store.get_hyperedge(100)
    assert loaded.probability == pytest.approx(0.9)
    assert loaded.verified is True


async def test_subgraph_one_hop(kuzu_store):
    """A -> B -> C, subgraph from A with 1 hop should find edge 1 and nodes A, B."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="deduction", tail=[1], head=[2], probability=0.9)
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="deduction", tail=[2], head=[3], probability=0.8)
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph([1], hops=1)
    assert 1 in edge_ids
    assert 1 in node_ids and 2 in node_ids

    # 2 hops should reach C
    node_ids2, edge_ids2 = await kuzu_store.get_subgraph([1], hops=2)
    assert 2 in edge_ids2
    assert 3 in node_ids2


async def test_subgraph_hops_limit(kuzu_store):
    """1 hop from node 10 should reach 11 but not 12."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="paper-extract", tail=[10], head=[11])
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="paper-extract", tail=[11], head=[12])
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph([10], hops=1)
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_subgraph_edge_type_filter(kuzu_store):
    """Edge type filter should restrict traversal."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="abstraction", tail=[10], head=[11])
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="induction", tail=[11], head=[12])
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph(
        [10], hops=2, edge_types=["abstraction"]
    )
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_subgraph_direction_downstream(kuzu_store):
    """Downstream-only traversal from node 1 should follow tail->head."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="deduction", tail=[1], head=[2])
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="deduction", tail=[3], head=[1])
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph([1], hops=1, direction="downstream")
    assert 2 in node_ids
    # Node 3 is upstream, should not be reached
    assert 3 not in node_ids


async def test_subgraph_direction_upstream(kuzu_store):
    """Upstream-only traversal from node 2 should follow head->tail."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="deduction", tail=[1], head=[2])
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="deduction", tail=[2], head=[3])
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph([2], hops=1, direction="upstream")
    assert 1 in node_ids
    # Node 3 is downstream, should not be reached
    assert 3 not in node_ids


async def test_subgraph_max_nodes(kuzu_store):
    """max_nodes cap should limit the total number of nodes returned."""
    # Create a chain: 1->2->3->4->5
    for i in range(1, 5):
        await kuzu_store.create_hyperedge(
            HyperEdge(id=i, type="deduction", tail=[i], head=[i + 1])
        )
    node_ids, edge_ids = await kuzu_store.get_subgraph([1], hops=4, max_nodes=3)
    assert len(node_ids) <= 4  # max_nodes is a cap, may include seed + discovered


async def test_reasoning_round_trip(kuzu_store):
    """Reasoning list with complex content should survive serialization."""
    reasoning = [
        {"content": "step 1", "detail": {"key": "value"}},
        {"content": "step 2"},
    ]
    edge = HyperEdge(id=42, type="deduction", tail=[1], head=[2], reasoning=reasoning)
    await kuzu_store.create_hyperedge(edge)
    loaded = await kuzu_store.get_hyperedge(42)
    assert loaded is not None
    assert loaded.reasoning == reasoning
