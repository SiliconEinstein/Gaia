"""GraphStore ABC — graph topology backend contract (Neo4j / Kuzu)."""

from abc import ABC, abstractmethod

from libs.storage.models import (
    CanonicalBinding,
    Chain,
    FactorNode,
    GlobalCanonicalNode,
    Knowledge,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)


class GraphStore(ABC):
    """Graph backend — topology storage, traversal, and BP-related updates."""

    # ── Schema setup ──

    @abstractmethod
    async def initialize_schema(self) -> None:
        """Create indexes, constraints, and node labels."""

    # ── Delete ──

    @abstractmethod
    async def delete_package(self, package_id: str) -> None:
        """Delete all nodes and relationships belonging to a package."""

    # ── Write ──

    @abstractmethod
    async def write_topology(self, knowledge_items: list[Knowledge], chains: list[Chain]) -> None:
        """Write knowledge nodes, chain nodes, and PREMISE/CONCLUSION relationships."""

    @abstractmethod
    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
        """Write ATTACHED_TO relationships for resources."""

    @abstractmethod
    async def write_factor_topology(self, factors: list[FactorNode]) -> None:
        """Write Factor nodes and FACTOR_PREMISE/FACTOR_CONTEXT/FACTOR_CONCLUSION relationships."""

    @abstractmethod
    async def write_global_topology(
        self,
        bindings: list[CanonicalBinding],
        global_nodes: list[GlobalCanonicalNode],
    ) -> None:
        """Write GlobalCanonicalNode nodes and CANONICAL_BINDING relationships."""

    # ── Query ──

    @abstractmethod
    async def get_neighbors(
        self,
        knowledge_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        """Get neighboring knowledge items and chains within max_hops."""

    @abstractmethod
    async def get_subgraph(self, knowledge_id: str, max_knowledge: int = 500) -> Subgraph:
        """Get a subgraph rooted at a knowledge item, up to max_knowledge."""

    @abstractmethod
    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredKnowledge]:
        """Expand from seed knowledge items by graph traversal, returning scored results."""

    # ── Lifecycle ──

    @abstractmethod
    async def close(self) -> None:
        """Release connections and resources."""
