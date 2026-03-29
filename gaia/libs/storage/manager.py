"""StorageManager — unified facade delegating to ContentStore and optional GraphStore."""

from __future__ import annotations

from gaia.models.belief_state import BeliefState
from gaia.models.binding import CanonicalBinding
from gaia.models.graph_ir import FactorNode, KnowledgeNode
from gaia.models.parameterization import (
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)
from gaia.libs.storage.base import ContentStore, GraphStore
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.lance import LanceContentStore


class StorageManager:
    """Unified storage facade that delegates to ContentStore and optional GraphStore.

    Args:
        config: Storage configuration (LanceDB path, optional Neo4j settings).
    """

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self.content_store: ContentStore | None = None
        self.graph_store: GraphStore | None = None

    async def initialize(self) -> None:
        """Initialize all configured storage backends.

        Always creates a LanceContentStore. Optionally creates a Neo4jGraphStore
        if Neo4j is configured via ``config.has_neo4j``.
        """
        lance = LanceContentStore(path=self.config.effective_lancedb_connection)
        await lance.initialize()
        self.content_store = lance

        if self.config.has_neo4j:
            from gaia.libs.storage.neo4j import Neo4jGraphStore

            gs = Neo4jGraphStore(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user,
                password=self.config.neo4j_password,
                database=self.config.neo4j_database,
            )
            await gs.initialize()
            self.graph_store = gs

    # ── Private helpers ──

    def _cs(self) -> ContentStore:
        if self.content_store is None:
            raise RuntimeError("StorageManager not initialized. Call initialize() first.")
        return self.content_store

    # ── Write: Knowledge Nodes ──

    async def write_knowledge_nodes(self, nodes: list[KnowledgeNode]) -> None:
        """Write knowledge nodes to content store (and graph store if available)."""
        await self._cs().write_knowledge_nodes(nodes)
        if self.graph_store is not None:
            await self.graph_store.write_nodes(nodes)

    # ── Write: Factor Nodes ──

    async def write_factor_nodes(self, factors: list[FactorNode]) -> None:
        """Write factor nodes to content store (and graph store if available)."""
        await self._cs().write_factor_nodes(factors)
        if self.graph_store is not None:
            await self.graph_store.write_factors(factors)

    # ── Write: Bindings (content only) ──

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        """Write canonical bindings to content store."""
        await self._cs().write_bindings(bindings)

    # ── Write: Prior Records (content only) ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        """Write prior probability records to content store."""
        await self._cs().write_prior_records(records)

    # ── Write: Factor Param Records (content only) ──

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        """Write factor parameterization records to content store."""
        await self._cs().write_factor_param_records(records)

    # ── Write: Param Source (content only) ──

    async def write_param_source(self, source: ParameterizationSource) -> None:
        """Write parameterization source metadata to content store."""
        await self._cs().write_param_source(source)

    # ── Write: Belief State (content only) ──

    async def write_belief_state(self, state: BeliefState) -> None:
        """Write a belief propagation result snapshot to content store."""
        await self._cs().write_belief_state(state)

    # ── Write: Node Embedding (content only) ──

    async def write_node_embedding(self, gcn_id: str, vector: list[float], content: str) -> None:
        """Write a node embedding vector to content store."""
        await self._cs().write_node_embedding(gcn_id, vector, content)

    # ── Read: Knowledge Nodes ──

    async def get_node(self, node_id: str) -> KnowledgeNode | None:
        """Get a single knowledge node by ID."""
        return await self._cs().get_node(node_id)

    async def get_knowledge_nodes(self, prefix: str | None = None) -> list[KnowledgeNode]:
        """Get knowledge nodes, optionally filtered by ID prefix."""
        return await self._cs().get_knowledge_nodes(prefix)

    # ── Read: Factor Nodes ──

    async def get_factor_nodes(self, scope: str | None = None) -> list[FactorNode]:
        """Get factor nodes, optionally filtered by scope."""
        return await self._cs().get_factor_nodes(scope)

    # ── Read: Bindings ──

    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]:
        """Get canonical bindings, optionally filtered by package_id."""
        return await self._cs().get_bindings(package_id)

    # ── Read: Prior Records ──

    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]:
        """Get prior records, optionally filtered by gcn_id."""
        return await self._cs().get_prior_records(gcn_id)

    # ── Read: Factor Param Records ──

    async def get_factor_param_records(
        self, factor_id: str | None = None
    ) -> list[FactorParamRecord]:
        """Get factor param records, optionally filtered by factor_id."""
        return await self._cs().get_factor_param_records(factor_id)

    # ── Read: Belief States ──

    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]:
        """Get recent belief states, most recent first."""
        return await self._cs().get_belief_states(limit)

    # ── Read: Vector Search ──

    async def search_similar_nodes(
        self, query_vector: list[float], top_k: int = 10, type_filter: str | None = None
    ) -> list[tuple[str, float]]:
        """Search for similar nodes by vector similarity.

        Returns:
            List of ``(gcn_id, distance)`` pairs sorted by similarity.
        """
        return await self._cs().search_similar_nodes(query_vector, top_k, type_filter)

    # ── Lifecycle ──

    async def clean_all(self) -> None:
        """Drop and recreate all tables in all configured stores."""
        await self._cs().clean_all()
        if self.graph_store is not None:
            await self.graph_store.clean_all()
