import pytest
from unittest.mock import AsyncMock, MagicMock
from services.search_engine.recall.topology import TopologyRecall


@pytest.fixture
def mock_graph_store():
    store = MagicMock()
    # get_subgraph returns (node_ids_set, edge_ids_set)
    store.get_subgraph = AsyncMock(return_value=({10, 11, 12, 13}, {1, 2, 3}))
    return store


async def test_recall_returns_discovered_nodes(mock_graph_store):
    recall = TopologyRecall(mock_graph_store)
    results = await recall.recall([10, 11], hops=3)
    node_ids = [r[0] for r in results]
    # Should include seeds and discovered nodes
    assert 10 in node_ids
    assert 11 in node_ids
    assert 12 in node_ids
    assert 13 in node_ids


async def test_recall_seeds_have_higher_score(mock_graph_store):
    recall = TopologyRecall(mock_graph_store)
    results = await recall.recall([10], hops=3)
    scores = {nid: score for nid, score in results}
    # Seed should have highest score
    assert scores[10] >= scores[11]
    assert scores[10] >= scores[12]


async def test_recall_calls_get_subgraph_with_join_filter(mock_graph_store):
    recall = TopologyRecall(mock_graph_store)
    await recall.recall([10], hops=2)
    mock_graph_store.get_subgraph.assert_called_once_with([10], hops=2, edge_types=["abstraction"])


async def test_recall_empty_graph(mock_graph_store):
    mock_graph_store.get_subgraph.return_value = ({10}, set())
    recall = TopologyRecall(mock_graph_store)
    results = await recall.recall([10], hops=3)
    assert len(results) == 1
    assert results[0][0] == 10


async def test_recall_no_seeds():
    store = MagicMock()
    store.get_subgraph = AsyncMock(return_value=(set(), set()))
    recall = TopologyRecall(store)
    results = await recall.recall([], hops=3)
    assert results == []
