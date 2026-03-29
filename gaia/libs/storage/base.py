"""Abstract base classes for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gaia.models.belief_state import BeliefState
from gaia.models.binding import CanonicalBinding
from gaia.models.graph_ir import FactorNode, KnowledgeNode
from gaia.models.parameterization import (
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)


class ContentStore(ABC):
    """LanceDB content store — source of truth for all entities.

    Unified tables: knowledge_nodes and factor_nodes hold both local and global
    entries, distinguished by id prefix (lcn_/gcn_ for nodes, lcf_/gcf_ for factors)
    and scope field (for factors).
    """

    # ── Write ──

    @abstractmethod
    async def write_knowledge_nodes(self, nodes: list[KnowledgeNode]) -> None: ...

    @abstractmethod
    async def write_factor_nodes(self, factors: list[FactorNode]) -> None: ...

    @abstractmethod
    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None: ...

    @abstractmethod
    async def write_prior_records(self, records: list[PriorRecord]) -> None: ...

    @abstractmethod
    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None: ...

    @abstractmethod
    async def write_param_source(self, source: ParameterizationSource) -> None: ...

    @abstractmethod
    async def write_belief_state(self, state: BeliefState) -> None: ...

    @abstractmethod
    async def write_node_embedding(
        self, gcn_id: str, vector: list[float], content: str
    ) -> None: ...

    # ── Read ──

    @abstractmethod
    async def get_node(self, node_id: str) -> KnowledgeNode | None: ...

    @abstractmethod
    async def get_knowledge_nodes(self, prefix: str | None = None) -> list[KnowledgeNode]: ...

    @abstractmethod
    async def get_factor_nodes(self, scope: str | None = None) -> list[FactorNode]: ...

    @abstractmethod
    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]: ...

    @abstractmethod
    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]: ...

    @abstractmethod
    async def get_factor_param_records(
        self, factor_id: str | None = None
    ) -> list[FactorParamRecord]: ...

    @abstractmethod
    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]: ...

    @abstractmethod
    async def search_similar_nodes(
        self, query_vector: list[float], top_k: int = 10, type_filter: str | None = None
    ) -> list[tuple[str, float]]:
        """Return list of (gcn_id, similarity_score) pairs."""
        ...

    # ── Lifecycle ──

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def clean_all(self) -> None: ...


class GraphStore(ABC):
    """Graph topology store — optional, for traversal queries."""

    @abstractmethod
    async def write_nodes(self, nodes: list[KnowledgeNode]) -> None: ...

    @abstractmethod
    async def write_factors(self, factors: list[FactorNode]) -> None: ...

    @abstractmethod
    async def get_neighbors(self, node_id: str) -> list[str]: ...

    @abstractmethod
    async def get_subgraph(
        self, node_ids: list[str], depth: int = 1
    ) -> tuple[list[str], list[str]]:
        """Return (node_ids, factor_ids) reachable within depth."""
        ...

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def clean_all(self) -> None: ...
