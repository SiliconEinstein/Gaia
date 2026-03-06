"""Unified GraphStore ABC compliance tests — parametrized over Kuzu and Neo4j.

Kuzu tests always run. Neo4j tests require a running Neo4j instance and are
auto-skipped if unavailable.
"""

import os

import pytest

from libs.models import HyperEdge
from libs.storage.graph_store import GraphStore
from libs.storage.kuzu_store import KuzuGraphStore
from tests.conftest import load_fixture_edges

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "neo4j")


async def _neo4j_available() -> bool:
    try:
        import neo4j

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        async with driver.session(database=NEO4J_DB) as session:
            await session.run("RETURN 1")
        await driver.close()
        return True
    except Exception:
        return False


@pytest.fixture(params=["kuzu", "neo4j"])
async def graph_store(request, tmp_path) -> GraphStore:
    """Yield a GraphStore instance — Kuzu always available, Neo4j skipped if down."""
    if request.param == "kuzu":
        store = KuzuGraphStore(db_path=str(tmp_path / "kuzu_db"))
        await store.initialize_schema()
        yield store
        await store.close()

    elif request.param == "neo4j":
        if not await _neo4j_available():
            pytest.skip("Neo4j not available")
        import neo4j
        from libs.storage.neo4j_store import Neo4jGraphStore

        auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
        driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
        store = Neo4jGraphStore(driver=driver, database=NEO4J_DB)
        await store.initialize_schema()
        yield store
        async with driver.session(database=NEO4J_DB) as session:
            await session.run("MATCH (n) DETACH DELETE n")
        await driver.close()


def _edge(
    id: int, tail: list[int], head: list[int], type: str = "paper-extract", **kw
) -> HyperEdge:
    return HyperEdge(id=id, type=type, tail=tail, head=head, reasoning=["test"], **kw)


# ── CRUD ────────────────────────────────────────────────────────────────


async def test_create_and_get(graph_store):
    edge = _edge(1, tail=[10, 11], head=[12])
    eid = await graph_store.create_hyperedge(edge)
    assert eid == 1

    loaded = await graph_store.get_hyperedge(1)
    assert loaded is not None
    assert set(loaded.tail) == {10, 11}
    assert loaded.head == [12]


async def test_create_with_probability(graph_store):
    edge = HyperEdge(
        id=100,
        type="deduction",
        tail=[1, 2],
        head=[3],
        probability=0.9,
        reasoning=[{"content": "test"}],
    )
    await graph_store.create_hyperedge(edge)
    loaded = await graph_store.get_hyperedge(100)
    assert loaded is not None
    assert loaded.probability == pytest.approx(0.9)


async def test_bulk_create(graph_store):
    edges = [_edge(1, [10], [11]), _edge(2, [11], [12])]
    ids = await graph_store.create_hyperedges_bulk(edges)
    assert ids == [1, 2]
    assert await graph_store.get_hyperedge(1) is not None
    assert await graph_store.get_hyperedge(2) is not None


async def test_get_nonexistent_returns_none(graph_store):
    assert await graph_store.get_hyperedge(999) is None


async def test_update_probability(graph_store):
    await graph_store.create_hyperedge(_edge(1, [10], [11]))
    await graph_store.update_hyperedge(1, probability=0.9)
    loaded = await graph_store.get_hyperedge(1)
    assert loaded.probability == pytest.approx(0.9)


async def test_update_verified(graph_store):
    await graph_store.create_hyperedge(_edge(1, [10], [11]))
    await graph_store.update_hyperedge(1, probability=0.9, verified=True)
    loaded = await graph_store.get_hyperedge(1)
    assert loaded.probability == pytest.approx(0.9)
    assert loaded.verified is True


async def test_reasoning_round_trip(graph_store):
    """Reasoning list with complex content should survive serialization."""
    reasoning = [
        {"content": "step 1", "detail": {"key": "value"}},
        {"content": "step 2"},
    ]
    edge = HyperEdge(id=42, type="deduction", tail=[1], head=[2], reasoning=reasoning)
    await graph_store.create_hyperedge(edge)
    loaded = await graph_store.get_hyperedge(42)
    assert loaded is not None
    assert loaded.reasoning == reasoning


# ── Subgraph traversal ──────────────────────────────────────────────────


async def test_subgraph_basic_2hop(graph_store):
    """10→11→12 chain, 2 hops from 10 should reach all three."""
    await graph_store.create_hyperedge(_edge(1, [10], [11]))
    await graph_store.create_hyperedge(_edge(2, [11], [12]))
    node_ids, edge_ids = await graph_store.get_subgraph([10], hops=2)
    assert {10, 11, 12}.issubset(node_ids)
    assert {1, 2}.issubset(edge_ids)


async def test_subgraph_hops_limit(graph_store):
    """1 hop from 10 should reach 11 but NOT 12."""
    await graph_store.create_hyperedge(_edge(1, [10], [11]))
    await graph_store.create_hyperedge(_edge(2, [11], [12]))
    node_ids, _ = await graph_store.get_subgraph([10], hops=1)
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_subgraph_edge_type_filter(graph_store):
    """Filter by edge type should restrict traversal."""
    await graph_store.create_hyperedge(_edge(1, [10], [11], type="abstraction"))
    await graph_store.create_hyperedge(_edge(2, [11], [12], type="induction"))
    node_ids, _ = await graph_store.get_subgraph([10], hops=2, edge_types=["abstraction"])
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_subgraph_direction_downstream(graph_store):
    """Downstream-only from node 1 should follow tail→head, not find upstream."""
    await graph_store.create_hyperedge(_edge(1, [1], [2]))
    await graph_store.create_hyperedge(_edge(2, [3], [1]))  # 3→1 is upstream of 1
    node_ids, _ = await graph_store.get_subgraph([1], hops=1, direction="downstream")
    assert 2 in node_ids
    assert 3 not in node_ids


async def test_subgraph_direction_upstream(graph_store):
    """Upstream-only from node 2 should follow head→tail, not find downstream."""
    await graph_store.create_hyperedge(_edge(1, [1], [2]))
    await graph_store.create_hyperedge(_edge(2, [2], [3]))  # 2→3 is downstream of 2
    node_ids, _ = await graph_store.get_subgraph([2], hops=1, direction="upstream")
    assert 1 in node_ids
    assert 3 not in node_ids


async def test_subgraph_max_nodes(graph_store):
    """max_nodes cap should limit traversal."""
    for i in range(1, 6):
        await graph_store.create_hyperedge(_edge(i, [i], [i + 1]))
    node_ids, _ = await graph_store.get_subgraph([1], hops=5, max_nodes=3)
    assert len(node_ids) <= 4  # seed + discovered, capped


# ── Fixture data (real superconductor paper data) ───────────────────────


async def test_fixture_edges_create_and_read(graph_store):
    """Load real fixture edges, verify topology round-trips."""
    edges = load_fixture_edges()
    for edge in edges:
        await graph_store.create_hyperedge(edge)

    loaded = await graph_store.get_hyperedge(edges[0].id)
    assert loaded is not None
    assert set(loaded.tail) == set(edges[0].tail)
    assert set(loaded.head) == set(edges[0].head)


async def test_fixture_subgraph_traversal(graph_store):
    """Subgraph traversal over real superconductor fixture topology."""
    edges = load_fixture_edges()
    for edge in edges:
        await graph_store.create_hyperedge(edge)

    seed = edges[0].tail[0]
    node_ids, edge_ids = await graph_store.get_subgraph([seed], hops=2)
    assert seed in node_ids
    assert edges[0].id in edge_ids
    assert len(node_ids) > 1
