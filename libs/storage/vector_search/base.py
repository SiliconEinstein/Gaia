"""Abstract base class for vector search clients."""

from abc import ABC, abstractmethod


class VectorSearchClient(ABC):
    """Interface for vector similarity search backends."""

    @abstractmethod
    async def insert_batch(self, node_ids: list[int], embeddings: list[list[float]]) -> None:
        """Insert a batch of node embeddings into the vector index.

        Args:
            node_ids: Unique integer identifiers for each node.
            embeddings: Corresponding embedding vectors (must match len of node_ids).
        """
        ...

    @abstractmethod
    async def search(self, query: list[float], k: int = 50) -> list[tuple[int, float]]:
        """Find the k nearest neighbours to *query*.

        Args:
            query: Query embedding vector.
            k: Maximum number of results to return.

        Returns:
            List of (node_id, distance) tuples ordered by ascending distance.
            Returns an empty list if the index is empty.
        """
        ...

    @abstractmethod
    async def search_batch(
        self, queries: list[list[float]], k: int = 50
    ) -> list[list[tuple[int, float]]]:
        """Batch version of :meth:`search`.

        Args:
            queries: List of query embedding vectors.
            k: Maximum number of results per query.

        Returns:
            One result list per query, each containing (node_id, distance) tuples.
        """
        ...
