import pytest
from services.review_pipeline.operators.join import (
    CCJoinOperator,
    CPJoinOperator,
    StubJoinLLM,
)
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode


@pytest.fixture
def context_with_nn():
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
    ctx.nn_results = {
        0: [(100, 0.05), (200, 0.1)],
        1: [(300, 0.02), (400, 0.15)],
    }
    return ctx


async def test_stub_join_llm():
    llm = StubJoinLLM()
    trees = await llm.find_joins("new content", [(100, "existing content")])
    assert isinstance(trees, list)


async def test_cc_join_produces_trees(context_with_nn):
    op = CCJoinOperator(join_llm=StubJoinLLM())
    result = await op.execute(context_with_nn)
    assert isinstance(result.cc_join_trees, list)


async def test_cp_join_produces_trees(context_with_nn):
    op = CPJoinOperator(join_llm=StubJoinLLM())
    result = await op.execute(context_with_nn)
    assert isinstance(result.cp_join_trees, list)
