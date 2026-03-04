from unittest.mock import AsyncMock, MagicMock

from libs.models import HyperEdge, Node
from services.search_engine.engine import SearchEngine
from services.search_engine.models import EdgeFilters, NodeFilters


def _make_mock_storage(tmp_path):
    """Create a mock StorageManager with all needed attributes."""
    storage = MagicMock()

    # Mock lance store
    storage.lance = MagicMock()
    storage.lance.fts_search = AsyncMock(return_value=[(1, 5.0), (2, 3.0)])
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="YH10 superconductivity", status="active"),
            Node(id=2, type="paper-extract", content="LaH10 experiment", status="active"),
            Node(id=3, type="abstraction", content="merged proposition", status="active"),
        ]
    )

    # Mock vector
    storage.vector = MagicMock()
    storage.vector.search = AsyncMock(return_value=[(1, 0.1), (3, 0.3)])

    # Mock graph (None = Neo4j not available)
    storage.graph = None

    return storage


async def test_search_nodes_basic():
    storage = _make_mock_storage(None)
    engine = SearchEngine(storage)
    results = await engine.search_nodes(
        query="superconductivity",
        embedding=[0.1] * 1024,
        k=10,
    )
    assert len(results) > 0
    # All results should be ScoredNode
    for r in results:
        assert hasattr(r, "node")
        assert hasattr(r, "score")
        assert hasattr(r, "sources")


async def test_search_nodes_with_filters():
    storage = _make_mock_storage(None)
    engine = SearchEngine(storage)
    filters = NodeFilters(type=["paper-extract"])
    results = await engine.search_nodes(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.node.type == "paper-extract"


async def test_search_nodes_specific_paths():
    storage = _make_mock_storage(None)
    engine = SearchEngine(storage)
    results = await engine.search_nodes(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
        paths=["vector"],
    )
    assert len(results) > 0
    # Should only have vector as source
    for r in results:
        assert "vector" in r.sources


async def test_search_edges_no_graph():
    """When graph is None (Neo4j unavailable), search_edges returns empty."""
    storage = _make_mock_storage(None)
    engine = SearchEngine(storage)
    results = await engine.search_edges(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
    )
    assert results == []


async def test_search_nodes_min_belief_filter():
    """Nodes below min_belief should be filtered out."""
    storage = _make_mock_storage(None)
    # Give nodes different belief values
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="high belief", status="active", belief=0.9),
            Node(id=2, type="paper-extract", content="low belief", status="active", belief=0.2),
            Node(id=3, type="abstraction", content="no belief", status="active", belief=None),
        ]
    )
    engine = SearchEngine(storage)
    filters = NodeFilters(min_belief=0.5)
    results = await engine.search_nodes(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.node.belief is not None and r.node.belief >= 0.5


async def test_search_nodes_status_filter():
    """Deleted nodes should be filtered out by default."""
    storage = _make_mock_storage(None)
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="active one", status="active"),
            Node(id=2, type="paper-extract", content="deleted one", status="deleted"),
        ]
    )
    engine = SearchEngine(storage)
    # Default filters have status=["active"]
    results = await engine.search_nodes(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
        filters=NodeFilters(),
    )
    for r in results:
        assert r.node.status == "active"


async def test_search_edges_with_graph():
    """When graph is available, search_edges should return edges."""
    storage = _make_mock_storage(None)

    # Provide a mock graph
    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(
        return_value=(
            {1, 2, 3},  # node_ids
            {100, 101},  # edge_ids
        )
    )
    storage.graph.get_hyperedge = AsyncMock(
        side_effect=lambda eid: HyperEdge(
            id=eid,
            type="abstraction",
            tail=[1],
            head=[2],
            verified=False,
        )
    )

    engine = SearchEngine(storage)
    results = await engine.search_edges(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
    )
    assert len(results) > 0
    for r in results:
        assert hasattr(r, "edge")
        assert hasattr(r, "score")
        assert hasattr(r, "sources")


async def test_search_edges_with_filters():
    """EdgeFilters should be applied."""
    storage = _make_mock_storage(None)

    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(
        return_value=(
            {1, 2},
            {100, 101},
        )
    )
    storage.graph.get_hyperedge = AsyncMock(
        side_effect=[
            HyperEdge(id=100, type="abstraction", tail=[1], head=[2], verified=True),
            HyperEdge(id=101, type="contradiction", tail=[1], head=[2], verified=False),
        ]
    )

    engine = SearchEngine(storage)
    filters = EdgeFilters(type=["abstraction"])
    results = await engine.search_edges(
        query="test",
        embedding=[0.1] * 1024,
        k=10,
        filters=filters,
    )
    for r in results:
        assert r.edge.type == "abstraction"
