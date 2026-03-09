import pytest

from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode


async def test_bp_operator_computes_beliefs(storage):
    """BPOperator computes real beliefs from fixture graph topology."""
    if not storage.graph:
        pytest.skip("Neo4j not available")

    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="p")],
                conclusions=[NewNode(content="c")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "x"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    # Use fixture node IDs that have edges in Neo4j
    ctx.affected_node_ids = [67, 68]

    op = BPOperator(storage=storage)
    result = await op.execute(ctx)
    assert len(result.bp_results) > 0
    for belief in result.bp_results.values():
        assert 0.0 <= belief <= 1.0


async def test_bp_operator_skips_without_graph(storage_empty):
    """When graph is unavailable, BP operator returns empty results."""
    storage_empty.graph = None
    req = CommitRequest(
        message="t",
        operations=[],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.affected_node_ids = [1]
    op = BPOperator(storage=storage_empty)
    result = await op.execute(ctx)
    assert len(result.bp_results) == 0
