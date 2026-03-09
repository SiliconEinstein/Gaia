from libs.embedding import StubEmbeddingModel
from libs.models import AddEdgeOp, CommitRequest, ModifyNodeOp, NewNode
from services.review_pipeline.context import PipelineContext
from services.review_pipeline.operators.nn_search import NNSearchOperator

_embedding_model = StubEmbeddingModel()


async def test_nn_search_returns_neighbors(storage):
    """NNSearchOperator finds real neighbors from seeded embeddings."""
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
    # Generate a query embedding with the same model conftest used to seed
    ctx.embeddings = {0: (await _embedding_model.embed(["superconductor"]))[0]}

    op = NNSearchOperator(vector_client=storage.vector, k=5)
    result = await op.execute(ctx)

    assert 0 in result.nn_results
    assert len(result.nn_results[0]) > 0
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
