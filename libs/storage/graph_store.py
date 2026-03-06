"""Abstract base class for hypergraph stores."""

from __future__ import annotations

import abc
from typing import Any

from libs.models import HyperEdge


class GraphStore(abc.ABC):
    """Backend-agnostic interface for hypergraph storage.

    Every concrete implementation (Neo4j, Kuzu, ...) must implement
    these seven methods so that the rest of the system can work with
    any graph backend interchangeably.
    """

    @abc.abstractmethod
    async def initialize_schema(self) -> None:
        """Create tables / constraints (idempotent)."""

    @abc.abstractmethod
    async def create_hyperedge(self, edge: HyperEdge) -> int:
        """Persist a single hyperedge and return its id."""

    @abc.abstractmethod
    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        """Persist many hyperedges in one transaction and return their ids."""

    @abc.abstractmethod
    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        """Load a hyperedge by id, or return None."""

    @abc.abstractmethod
    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None:
        """Update scalar fields on an existing hyperedge."""

    @abc.abstractmethod
    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]:
        """Return (node_ids, edge_ids) reachable within *hops* knowledge hops."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release resources."""
