import pytest
from unittest.mock import AsyncMock
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode
from libs.storage.vector_search.base import VectorSearchClient


@pytest.fixture
def context_with_embeddings():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NewNode(content="conclusion")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.embeddings = {0: [0.1] * 128, 1: [0.2] * 128}
    return ctx


async def test_nn_search_returns_neighbors(context_with_embeddings):
    mock_client = AsyncMock(spec=VectorSearchClient)
    mock_client.search.return_value = [(100, 0.1), (200, 0.2), (300, 0.3)]

    op = NNSearchOperator(vector_client=mock_client, k=20)
    result = await op.execute(context_with_embeddings)

    assert 0 in result.nn_results
    assert 1 in result.nn_results
    assert len(result.nn_results[0]) == 3
    assert result.nn_results[0][0] == (100, 0.1)
    assert mock_client.search.call_count == 2


async def test_nn_search_skips_if_no_embeddings():
    from libs.models import ModifyNodeOp

    req = CommitRequest(
        message="t",
        operations=[ModifyNodeOp(node_id=1, changes={"x": 1})],
    )
    ctx = PipelineContext.from_commit_request(req)
    mock_client = AsyncMock(spec=VectorSearchClient)
    op = NNSearchOperator(vector_client=mock_client, k=20)
    result = await op.execute(ctx)
    assert len(result.nn_results) == 0
    mock_client.search.assert_not_called()
