# tests/libs/storage/test_neo4j_store.py
import os
import pytest
from libs.models import HyperEdge
from libs.storage.neo4j_store import Neo4jGraphStore
from tests.conftest import load_fixture_edges

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "neo4j")


@pytest.fixture
async def store():
    import neo4j

    auth = ("neo4j", NEO4J_PASSWORD) if NEO4J_PASSWORD else None
    driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=auth)
    s = Neo4jGraphStore(driver=driver, database=NEO4J_DB)
    await s.initialize_schema()
    yield s
    async with driver.session(database=NEO4J_DB) as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await driver.close()


def _edge(
    id: int, premises: list[int], conclusions: list[int], type: str = "paper-extract"
) -> HyperEdge:
    return HyperEdge(
        id=id, type=type, premises=premises, conclusions=conclusions, reasoning=["test"]
    )


async def test_create_and_get_hyperedge(store):
    edge = _edge(1, premises=[10, 11], conclusions=[12])
    eid = await store.create_hyperedge(edge)
    assert eid == 1
    loaded = await store.get_hyperedge(1)
    assert loaded is not None
    assert set(loaded.premises) == {10, 11}
    assert loaded.conclusions == [12]


async def test_create_hyperedges_bulk(store):
    edges = [_edge(1, premises=[10], conclusions=[11]), _edge(2, premises=[11], conclusions=[12])]
    ids = await store.create_hyperedges_bulk(edges)
    assert ids == [1, 2]


async def test_get_nonexistent_hyperedge(store):
    result = await store.get_hyperedge(999)
    assert result is None


async def test_update_hyperedge(store):
    await store.create_hyperedge(_edge(1, premises=[10], conclusions=[11]))
    await store.update_hyperedge(1, probability=0.9, verified=True)
    loaded = await store.get_hyperedge(1)
    assert loaded.probability == pytest.approx(0.9)
    assert loaded.verified is True


async def test_get_subgraph_basic(store):
    await store.create_hyperedge(_edge(1, premises=[10], conclusions=[11]))
    await store.create_hyperedge(_edge(2, premises=[11], conclusions=[12]))
    node_ids, edge_ids = await store.get_subgraph([10], hops=2)
    assert 10 in node_ids
    assert 11 in node_ids
    assert 12 in node_ids
    assert 1 in edge_ids
    assert 2 in edge_ids


async def test_get_subgraph_hops_limit(store):
    await store.create_hyperedge(_edge(1, premises=[10], conclusions=[11]))
    await store.create_hyperedge(_edge(2, premises=[11], conclusions=[12]))
    node_ids, edge_ids = await store.get_subgraph([10], hops=1)
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_get_subgraph_edge_type_filter(store):
    await store.create_hyperedge(_edge(1, premises=[10], conclusions=[11], type="abstraction"))
    await store.create_hyperedge(_edge(2, premises=[11], conclusions=[12], type="induction"))
    node_ids, edge_ids = await store.get_subgraph([10], hops=2, edge_types=["abstraction"])
    assert 11 in node_ids
    assert 12 not in node_ids


# -- Fixture-data tests -------------------------------------------------------


async def test_create_fixture_edges(store):
    """Create real fixture edges and verify topology."""
    edges = load_fixture_edges()
    for edge in edges:
        await store.create_hyperedge(edge)

    loaded = await store.get_hyperedge(edges[0].id)
    assert loaded is not None
    assert set(loaded.premises) == set(edges[0].premises)
    assert set(loaded.conclusions) == set(edges[0].conclusions)


async def test_subgraph_with_fixture_topology(store):
    """Subgraph traversal over real fixture edge topology."""
    edges = load_fixture_edges()
    for edge in edges:
        await store.create_hyperedge(edge)

    seed = edges[0].premises[0]
    node_ids, edge_ids = await store.get_subgraph([seed], hops=2)
    assert seed in node_ids
    assert edges[0].id in edge_ids
    assert len(node_ids) > 1
