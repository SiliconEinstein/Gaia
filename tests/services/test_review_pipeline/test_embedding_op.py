import pytest
from services.review_pipeline.operators.embedding import (
    EmbeddingOperator,
    StubEmbeddingModel,
)
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode


@pytest.fixture
def context_with_new_nodes():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                premises=[NewNode(content="premise A")],
                conclusions=[NewNode(content="conclusion B")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    return PipelineContext.from_commit_request(req)


async def test_embedding_operator_generates_vectors(context_with_new_nodes):
    op = EmbeddingOperator(model=StubEmbeddingModel(dim=128))
    result = await op.execute(context_with_new_nodes)
    assert 0 in result.embeddings
    assert 1 in result.embeddings
    assert len(result.embeddings[0]) == 128


async def test_embedding_operator_skips_if_no_new_nodes():
    from libs.models import ModifyNodeOp

    req = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    ctx = PipelineContext.from_commit_request(req)
    op = EmbeddingOperator(model=StubEmbeddingModel(dim=128))
    result = await op.execute(ctx)
    assert len(result.embeddings) == 0
