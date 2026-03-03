import pytest
from services.review_pipeline.base import Operator, Pipeline, ParallelStep
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, ModifyNodeOp


class IncrementOperator(Operator):
    """Test operator that appends its name to step_results."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, context: PipelineContext) -> PipelineContext:
        context.step_results[self.name] = {"done": True}
        return context


class FailingOperator(Operator):
    async def execute(self, context: PipelineContext) -> PipelineContext:
        raise ValueError("operator failed")


@pytest.fixture
def empty_context():
    req = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    return PipelineContext.from_commit_request(req)


async def test_pipeline_sequential(empty_context):
    pipeline = Pipeline(steps=[IncrementOperator("a"), IncrementOperator("b")])
    result = await pipeline.execute(empty_context)
    assert "a" in result.step_results
    assert "b" in result.step_results


async def test_pipeline_parallel_step(empty_context):
    pipeline = Pipeline(
        steps=[
            ParallelStep(IncrementOperator("x"), IncrementOperator("y")),
        ]
    )
    result = await pipeline.execute(empty_context)
    assert "x" in result.step_results
    assert "y" in result.step_results


async def test_pipeline_skips_after_cancel(empty_context):
    empty_context.cancelled = True
    pipeline = Pipeline(steps=[IncrementOperator("a")])
    result = await pipeline.execute(empty_context)
    assert "a" not in result.step_results


async def test_pipeline_cancel_propagates(empty_context):
    pipeline = Pipeline(steps=[IncrementOperator("a"), IncrementOperator("b")])
    await pipeline.cancel()
    result = await pipeline.execute(empty_context)
    assert "a" not in result.step_results
