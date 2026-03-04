# tests/services/test_search_engine/test_engine.py
"""SearchEngine tests — real storage instead of mocks."""

import pytest

from libs.embedding import StubEmbeddingModel
from services.search_engine.engine import SearchEngine
from services.search_engine.models import EdgeFilters, NodeFilters


@pytest.fixture
async def search(storage):
    return SearchEngine(storage, embedding_model=StubEmbeddingModel())


async def test_search_nodes_basic(search):
    results = await search.search_nodes(
        text="superconductivity",
        k=10,
    )
    assert len(results) > 0
    for r in results:
        assert r.node is not None
        assert r.score > 0
        assert len(r.sources) > 0


async def test_search_nodes_with_type_filter(search):
    filters = NodeFilters(type=["paper-extract"])
    results = await search.search_nodes(
        text="superconductor",
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.node.type == "paper-extract"


async def test_search_nodes_bm25_only(search):
    results = await search.search_nodes(
        text="thallium oxide",
        k=10,
        paths=["bm25"],
    )
    assert len(results) > 0
    for r in results:
        assert "bm25" in r.sources


async def test_search_nodes_vector_only(search):
    results = await search.search_nodes(
        text="test",
        k=10,
        paths=["vector"],
    )
    # Vector recall may or may not find results depending on embeddings
    for r in results:
        assert "vector" in r.sources


async def test_search_edges_no_graph(storage_empty):
    """When graph is None, search_edges returns empty."""
    storage_empty.graph = None
    engine = SearchEngine(storage_empty, embedding_model=StubEmbeddingModel())
    results = await engine.search_edges(
        text="test",
        k=10,
    )
    assert results == []


async def test_search_nodes_min_belief_filter(search):
    """Only nodes with belief >= threshold should pass."""
    filters = NodeFilters(min_belief=0.5)
    results = await search.search_nodes(
        text="superconductor",
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.node.belief is not None and r.node.belief >= 0.5


async def test_search_nodes_status_filter(search):
    """Default status filter is ['active']."""
    filters = NodeFilters()  # defaults to status=["active"]
    results = await search.search_nodes(
        text="superconductor",
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.node.status == "active"


async def test_search_edges_with_graph(search, storage):
    """When graph is available, search_edges should return edges."""
    if not storage.graph:
        pytest.skip("Neo4j not available")
    results = await search.search_edges(
        text="superconductor",
        k=10,
    )
    assert len(results) > 0
    for r in results:
        assert r.edge is not None
        assert r.score >= 0


async def test_search_edges_with_type_filter(search, storage):
    """EdgeFilters type filter should be applied."""
    if not storage.graph:
        pytest.skip("Neo4j not available")
    filters = EdgeFilters(type=["abstraction"])
    results = await search.search_edges(
        text="superconductor",
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.edge.type == "abstraction"


def test_node_filters_new_fields():
    f = NodeFilters(paper_id="arxiv:2301.12345", min_quality=3.0, edge_type=["abstraction"])
    assert f.paper_id == "arxiv:2301.12345"
    assert f.min_quality == 3.0
    assert f.edge_type == ["abstraction"]


def test_node_filters_new_fields_default_none():
    f = NodeFilters()
    assert f.paper_id is None
    assert f.min_quality is None
    assert f.edge_type is None
