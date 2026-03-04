import pytest

from tests.conftest import load_fixture_embeddings
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, ModifyNodeOp, NewNode


async def test_nn_search_returns_neighbors(storage):
    """NNSearchOperator finds real neighbors from fixture embeddings."""
    embeddings = load_fixture_embeddings()
    if not embeddings:
        pytest.skip("No fixture embeddings available")

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
    # Use real fixture embeddings
    first_id = next(iter(embeddings))
    ctx.embeddings = {0: embeddings[first_id]}

    op = NNSearchOperator(vector_client=storage.vector, k=5)
    result = await op.execute(ctx)

    assert 0 in result.nn_results
    assert len(result.nn_results[0]) > 0
    # Results should be (node_id, distance) tuples with real node IDs
    for node_id, distance in result.nn_results[0]:
        assert isinstance(node_id, int)
        assert distance >= 0


async def test_nn_search_skips_if_no_embeddings(storage):
    """When context has no embeddings, operator is a no-op."""
    req = CommitRequest(
        message="t",
        operations=[ModifyNodeOp(node_id=1, changes={"x": 1})],
    )
    ctx = PipelineContext.from_commit_request(req)
    op = NNSearchOperator(vector_client=storage.vector, k=20)
    result = await op.execute(ctx)
    assert len(result.nn_results) == 0
