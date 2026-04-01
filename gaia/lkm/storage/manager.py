"""StorageManager — unified facade for LKM storage operations."""

from __future__ import annotations

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
from gaia.lkm.storage.config import StorageConfig
from gaia.lkm.storage.lance_store import LanceContentStore


class StorageManager:
    """Unified storage facade for LKM.

    Delegates to LanceContentStore (required) and optional backends
    (GraphStore, VectorStore — added in later milestones).
    """

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._content: LanceContentStore | None = None

    @property
    def content(self) -> LanceContentStore:
        assert self._content is not None, "StorageManager not initialized — call initialize() first"
        return self._content

    async def initialize(self) -> None:
        """Initialize all storage backends."""
        self._content = LanceContentStore(self._config.effective_lancedb_uri)
        await self._content.initialize()

    async def close(self) -> None:
        """Close storage backends. LanceDB needs no explicit close."""
        pass

    # ── Ingest protocol ──

    async def ingest_local_graph(
        self,
        package_id: str,
        version: str,
        variable_nodes: list[LocalVariableNode],
        factor_nodes: list[LocalFactorNode],
    ) -> None:
        """Step 1: Write local nodes with ingest_status='preparing'."""
        await self.content.write_local_variables(variable_nodes)
        await self.content.write_local_factors(factor_nodes)

    async def commit_package(self, source_package: str, version: str = "") -> None:
        """Step 7: Flip ingest_status from 'preparing' to 'merged' for (package, version)."""
        await self.content.commit_ingest(source_package, version)

    async def integrate_global_graph(
        self,
        variable_nodes: list[GlobalVariableNode],
        factor_nodes: list[GlobalFactorNode],
        bindings: list[CanonicalBinding],
        prior_records: list[PriorRecord] | None = None,
        factor_param_records: list[FactorParamRecord] | None = None,
    ) -> None:
        """Steps 2-4: Write global nodes, bindings, and parameters."""
        await self.content.write_global_variables(variable_nodes)
        await self.content.write_global_factors(factor_nodes)
        await self.content.write_bindings(bindings)
        if prior_records:
            await self.content.write_prior_records(prior_records)
        if factor_param_records:
            await self.content.write_factor_param_records(factor_param_records)

    # ── Parameterization ──

    async def write_param_source(self, source: ParameterizationSource) -> None:
        await self.content.write_param_source(source)

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        await self.content.write_prior_records(records)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        await self.content.write_factor_param_records(records)

    # ── Reads: variables ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        return await self.content.get_local_variable(local_id)

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        return await self.content.get_global_variable(gcn_id)

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        return await self.content.find_global_by_content_hash(content_hash, visibility)

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

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        return await self.content.get_prior_records(variable_id)

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        return await self.content.get_param_source(source_id)

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        await self.content.update_global_variable_members(gcn_id, updated_node)
