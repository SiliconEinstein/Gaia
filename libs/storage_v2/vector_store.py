"""VectorStore ABC — embedding similarity search contract."""

from abc import ABC, abstractmethod

from libs.storage_v2.models import KnowledgeEmbedding, ScoredKnowledge


class VectorStore(ABC):
    """Vector search backend — write embeddings and search by similarity."""

    @abstractmethod
    async def write_embeddings(self, items: list[KnowledgeEmbedding]) -> None:
        """Write or upsert embedding vectors for knowledge items."""

    @abstractmethod
    async def search(self, embedding: list[float], top_k: int) -> list[ScoredKnowledge]:
        """Find the top_k most similar knowledge items by embedding distance."""
