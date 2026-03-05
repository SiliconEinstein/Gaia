"""Abstract base class for graph storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from libs.models import HyperEdge


class GraphStore(ABC):
    """Abstract graph store for the Gaia hypergraph.

    Implementations must support hyperedge CRUD and subgraph traversal.
    """

    @abstractmethod
    async def initialize_schema(self) -> None: ...

    @abstractmethod
    async def create_hyperedge(self, edge: HyperEdge) -> int: ...

    @abstractmethod
    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]: ...

    @abstractmethod
    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None: ...

    @abstractmethod
    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None: ...

    @abstractmethod
    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]: ...

    @abstractmethod
    async def close(self) -> None: ...
