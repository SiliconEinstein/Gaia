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
                tail=[NewNode(content="premise A")],
                head=[NewNode(content="conclusion B")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    return PipelineContext.from_commit_request(req)


async def test_stub_embedding_model():
    model = StubEmbeddingModel(dim=128)
    vecs = await model.embed(["hello", "world"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 128
    assert all(isinstance(v, float) for v in vecs[0])


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
