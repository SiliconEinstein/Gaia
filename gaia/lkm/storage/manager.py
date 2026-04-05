"""StorageManager — unified facade for LKM storage operations."""

from __future__ import annotations

import logging
from typing import Any

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalFactorNode,
    LocalVariableNode,
    ParameterizationSource,
    PriorRecord,
)
from gaia.lkm.models.import_status import ImportStatusRecord
from gaia.lkm.storage.config import StorageConfig
from gaia.lkm.storage.lance_store import LanceContentStore

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage facade for LKM.

    Delegates to LanceContentStore (required) and optional Neo4j graph store.
    """

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._content: LanceContentStore | None = None
        self._graph: Any | None = None  # Neo4jGraphStore or None

    @property
    def content(self) -> LanceContentStore:
        assert self._content is not None, "StorageManager not initialized — call initialize() first"
        return self._content

    @property
    def graph(self) -> Any | None:
        """Neo4j graph store, or None if graph_backend='none'."""
        return self._graph

    async def initialize(self) -> None:
        """Initialize all storage backends."""
        self._content = LanceContentStore(
            self._config.effective_lancedb_uri,
            storage_options=self._config.storage_options,
        )
        await self._content.initialize()

        if self._config.graph_backend == "neo4j":
            import neo4j

            from gaia.lkm.storage.neo4j_store import Neo4jGraphStore

            driver = neo4j.AsyncGraphDatabase.driver(
                self._config.neo4j_uri,
                auth=(self._config.neo4j_user, self._config.neo4j_password),
            )
            self._graph = Neo4jGraphStore(driver, self._config.neo4j_database)
            await self._graph.initialize_schema()

    async def close(self) -> None:
        """Close storage backends."""
        if self._graph is not None:
            await self._graph.close()

    # ── Ingest protocol ──

    async def ingest_local_graph(
        self,
        package_id: str,
        version: str,
        variable_nodes: list[LocalVariableNode],
        factor_nodes: list[LocalFactorNode],
    ) -> None:
        """Step 1: Write local nodes with ingest_status='preparing'."""
        logger.info(
            "Ingesting local graph %s@%s: %d variables, %d factors",
            package_id,
            version,
            len(variable_nodes),
            len(factor_nodes),
        )
        await self.content.write_local_variables(variable_nodes)
        await self.content.write_local_factors(factor_nodes)

    async def commit_package(self, source_package: str, version: str = "") -> None:
        """Step 7: Flip ingest_status from 'preparing' to 'merged' for (package, version)."""
        await self.content.commit_ingest(source_package, version)

    async def batch_upsert_local_nodes(
        self,
        variables: list[LocalVariableNode],
        factors: list[LocalFactorNode],
    ) -> None:
        """Batch upsert local nodes directly as 'merged'. For batch import."""
        logger.info(
            "Batch upserting local nodes: %d variables, %d factors",
            len(variables),
            len(factors),
        )
        await self.content.batch_upsert_local_nodes(variables, factors)

    async def integrate_global_graph(
        self,
        variable_nodes: list[GlobalVariableNode],
        factor_nodes: list[GlobalFactorNode],
        bindings: list[CanonicalBinding],
        prior_records: list[PriorRecord] | None = None,
        factor_param_records: list[FactorParamRecord] | None = None,
    ) -> None:
        """Steps 2-4: Write global nodes, bindings, parameters, and graph topology."""
        logger.info(
            "Integrating global graph: %d variables, %d factors, %d bindings",
            len(variable_nodes),
            len(factor_nodes),
            len(bindings),
        )
        await self.content.write_global_variables(variable_nodes)
        await self.content.write_global_factors(factor_nodes)
        await self.content.write_bindings(bindings)
        if prior_records:
            await self.content.write_prior_records(prior_records)
        if factor_param_records:
            await self.content.write_factor_param_records(factor_param_records)

        # Write to graph store if configured
        if self._graph is not None:
            await self._graph.write_global_graph(variable_nodes, factor_nodes)

    # ── Parameterization ──

    async def write_param_source(self, source: ParameterizationSource) -> None:
        await self.content.write_param_source(source)

    async def write_param_sources_batch(self, sources: list[ParameterizationSource]) -> None:
        await self.content.write_param_sources_batch(sources)

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        await self.content.write_prior_records(records)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        await self.content.write_factor_param_records(records)

    # ── Reads: variables ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        return await self.content.get_local_variable(local_id)

    async def get_local_variables_by_ids(
        self, local_ids: list[str]
    ) -> dict[str, LocalVariableNode]:
        """Batch-fetch local variables by ID list."""
        return await self.content.get_local_variables_by_ids(local_ids)

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        return await self.content.get_global_variable(gcn_id)

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        return await self.content.find_global_by_content_hash(content_hash, visibility)

    async def list_all_public_global_ids(self) -> list[dict]:
        """List all public global variable IDs with type and representative_lcn."""
        return await self.content.list_all_public_global_ids()

    # ── Reads: factors ──

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None:
        return await self.content.get_global_factor(gfac_id)

    async def find_global_factor_exact(
        self, premises: list[str], conclusion: str, factor_type: str, subtype: str
    ) -> GlobalFactorNode | None:
        return await self.content.find_global_factor_exact(
            premises, conclusion, factor_type, subtype
        )

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None:
        return await self.content.find_canonical_binding(local_id)

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]:
        return await self.content.find_bindings_by_global_id(global_id)

    # ── Batch reads (for batch_integrate) ──

    async def find_globals_by_content_hashes(
        self, hashes: set[str]
    ) -> dict[str, GlobalVariableNode]:
        return await self.content.find_globals_by_content_hashes(hashes)

    async def find_bindings_by_local_ids(self, local_ids: set[str]) -> dict[str, CanonicalBinding]:
        return await self.content.find_bindings_by_local_ids(local_ids)

    async def find_global_factors_by_conclusions(
        self, conclusions: set[str]
    ) -> list[GlobalFactorNode]:
        return await self.content.find_global_factors_by_conclusions(conclusions)

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        return await self.content.get_prior_records(variable_id)

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        return await self.content.get_param_source(source_id)

    # ── Import status ──

    async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None:
        await self.content.write_import_status_batch(records)

    async def get_import_status(self, package_id: str) -> ImportStatusRecord | None:
        return await self.content.get_import_status(package_id)

    async def list_ingested_package_ids(self) -> list[str]:
        return await self.content.list_ingested_package_ids()

    # ── Reads: graph ──

    async def get_subgraph(self, gcn_id: str, hops: int = 2) -> dict:
        """Get N-hop subgraph. Uses Neo4j if available, else empty."""
        if self._graph is not None:
            return await self._graph.get_subgraph(gcn_id, hops)
        return {"nodes": [], "edges": []}

    async def get_neighbors(self, gcn_id: str, direction: str = "both") -> list[dict]:
        """Get direct neighbors. Uses Neo4j if available, else empty."""
        if self._graph is not None:
            return await self._graph.get_neighbors(gcn_id, direction)
        return []

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        await self.content.update_global_variable_members(gcn_id, updated_node)

    # ── ByteHouse ──

    def create_bytehouse_store(self):
        """Create a ByteHouseEmbeddingStore from config. Returns None if not configured."""
        from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore

        if not self._config.bytehouse_host:
            return None
        return ByteHouseEmbeddingStore(
            host=self._config.bytehouse_host,
            user=self._config.bytehouse_user,
            password=self._config.bytehouse_password,
            database=self._config.bytehouse_database,
            replication_root=self._config.bytehouse_replication_root,
        )
