"""EmbeddingOperator — generate embeddings for new nodes."""

from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod

from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext


class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        ...


class StubEmbeddingModel(EmbeddingModel):
    """Deterministic stub: hashes text to produce reproducible vectors."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            # Repeat digest bytes to fill dim floats
            raw = digest * ((self._dim * 4 // len(digest)) + 1)
            floats = list(struct.unpack(f"<{self._dim}f", raw[: self._dim * 4]))
            # Normalize to reasonable range
            mag = max(abs(f) for f in floats) or 1.0
            results.append([f / mag for f in floats])
        return results


class EmbeddingOperator(Operator):
    """Generate embeddings for all new nodes in the context."""

    def __init__(self, model: EmbeddingModel) -> None:
        self._model = model

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.new_nodes:
            return context
        texts = [node.content for node in context.new_nodes]
        vectors = await self._model.embed(texts)
        for i, vec in enumerate(vectors):
            context.embeddings[i] = vec
        return context
