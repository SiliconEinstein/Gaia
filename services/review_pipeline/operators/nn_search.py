"""NNSearchOperator — find nearest neighbors for each new node embedding."""

from __future__ import annotations

from libs.storage.vector_search.base import VectorSearchClient
from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext


class NNSearchOperator(Operator):
    """Search k nearest neighbors for each new node's embedding."""

    def __init__(self, vector_client: VectorSearchClient, k: int = 20) -> None:
        self._client = vector_client
        self._k = k

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.embeddings:
            return context
        for idx, embedding in context.embeddings.items():
            results = await self._client.search(embedding, k=self._k)
            context.nn_results[idx] = results
        return context
