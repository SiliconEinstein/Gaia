"""VectorStore ABC — embedding similarity search contract."""

from abc import ABC, abstractmethod

from libs.storage_v2.models import ClosureEmbedding, ScoredClosure


class VectorStore(ABC):
    """Vector search backend — write embeddings and search by similarity."""

    @abstractmethod
    async def write_embeddings(self, items: list[ClosureEmbedding]) -> None:
        """Write or upsert embedding vectors for closures."""

    @abstractmethod
    async def search(self, embedding: list[float], top_k: int) -> list[ScoredClosure]:
        """Find the top_k most similar closures by embedding distance."""
