import pytest
from services.review_pipeline.operators.abstraction import (
    CCAbstractionOperator,
    CPAbstractionOperator,
    StubAbstractionLLM,
)
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode


@pytest.fixture
def context_with_nn():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="premise")],
                conclusions=[NewNode(content="conclusion")],
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


async def test_cc_abstraction_with_stub_returns_empty(context_with_nn):
    """With stub LLM, CC abstraction returns empty trees (no real LLM)."""
    op = CCAbstractionOperator(abstraction_llm=StubAbstractionLLM())
    result = await op.execute(context_with_nn)
    assert result.cc_abstraction_trees == []  # stub produces no abstractions


async def test_cp_abstraction_with_stub_returns_empty(context_with_nn):
    """With stub LLM, CP abstraction returns empty trees (no real LLM)."""
    op = CPAbstractionOperator(abstraction_llm=StubAbstractionLLM())
    result = await op.execute(context_with_nn)
    assert result.cp_abstraction_trees == []  # stub produces no abstractions
