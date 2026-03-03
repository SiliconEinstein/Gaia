import pytest
from unittest.mock import AsyncMock, MagicMock
from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode, Node, HyperEdge


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(return_value=({1, 2, 3}, {10}))
    storage.graph.get_hyperedge = AsyncMock(
        return_value=HyperEdge(id=10, type="paper-extract", tail=[1, 2], head=[3])
    )
    storage.lance = MagicMock()
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="a", prior=0.9),
            Node(id=2, type="paper-extract", content="b", prior=0.8),
            Node(id=3, type="paper-extract", content="c", prior=0.5),
        ]
    )
    return storage


@pytest.fixture
def context_with_affected_nodes():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NewNode(content="c")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "x"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.affected_node_ids = [1, 2, 3]
    return ctx


async def test_bp_operator_computes_beliefs(mock_storage, context_with_affected_nodes):
    op = BPOperator(storage=mock_storage)
    result = await op.execute(context_with_affected_nodes)
    assert len(result.bp_results) > 0
    assert all(0 <= v <= 1 for v in result.bp_results.values())


async def test_bp_operator_skips_without_graph():
    storage = MagicMock()
    storage.graph = None
    req = CommitRequest(
        message="t",
        operations=[],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.affected_node_ids = [1]
    op = BPOperator(storage=storage)
    result = await op.execute(ctx)
    assert len(result.bp_results) == 0
