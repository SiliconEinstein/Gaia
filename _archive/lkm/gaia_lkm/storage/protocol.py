"""Storage protocol abstraction for the LKM content layer.

``LkmContentStore`` describes the interface that any LKM content backend
must satisfy. Both :class:`LanceContentStore` and :class:`BytehouseLkmStore`
implement this protocol so that ``StorageManager`` can switch backends
without changing call sites.

The protocol mirrors the public surface of the existing
``LanceContentStore`` 1:1 — async-only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


@runtime_checkable
class LkmContentStore(Protocol):
    """Protocol describing the LKM content-store contract."""

    # ── Initialization ──

    async def initialize(self) -> None: ...

    # ── Local node writes ──

    async def write_local_variables(self, nodes: list[LocalVariableNode]) -> None: ...

    async def write_local_factors(self, nodes: list[LocalFactorNode]) -> None: ...

    async def commit_ingest(self, source_package: str, version: str) -> None: ...

    async def batch_upsert_local_nodes(
        self,
        variables: list[LocalVariableNode],
        factors: list[LocalFactorNode],
    ) -> None: ...

    # ── Global node writes ──

    async def write_global_variables(self, nodes: list[GlobalVariableNode]) -> None: ...

    async def write_global_factors(self, nodes: list[GlobalFactorNode]) -> None: ...

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None: ...

    # ── Parameterization writes ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None: ...

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None: ...

    async def write_param_source(self, source: ParameterizationSource) -> None: ...

    async def write_param_sources_batch(self, sources: list[ParameterizationSource]) -> None: ...

    # ── Batch reads ──

    async def find_globals_by_content_hashes(
        self, hashes: set[str]
    ) -> dict[str, GlobalVariableNode]: ...

    async def find_bindings_by_local_ids(
        self, local_ids: set[str]
    ) -> dict[str, CanonicalBinding]: ...

    async def find_global_factors_by_conclusions(
        self, conclusions: set[str]
    ) -> list[GlobalFactorNode]: ...

    # ── Reads: local nodes ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None: ...

    async def get_local_variables_by_ids(
        self, local_ids: list[str], concurrency: int = 4
    ) -> dict[str, LocalVariableNode]: ...

    async def get_local_variables_by_package(
        self, source_package: str, merged_only: bool = True
    ) -> list[LocalVariableNode]: ...

    async def get_local_factor(self, factor_id: str) -> LocalFactorNode | None: ...

    # ── Reads: global nodes ──

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None: ...

    async def list_global_variables(
        self,
        type_filter: str | None = None,
        visibility: str = "public",
        limit: int = 100,
    ) -> list[GlobalVariableNode]: ...

    async def list_all_public_global_ids(self) -> list[dict]: ...

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None: ...

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None: ...

    async def list_global_factors(
        self,
        factor_type: str | None = None,
        limit: int = 100,
    ) -> list[GlobalFactorNode]: ...

    async def find_global_factor_exact(
        self,
        premises: list[str],
        conclusion: str,
        factor_type: str,
        subtype: str,
    ) -> GlobalFactorNode | None: ...

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None: ...

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]: ...

    async def list_bindings(
        self,
        package_id: str | None = None,
        binding_type: str | None = None,
        limit: int = 200,
    ) -> list[CanonicalBinding]: ...

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]: ...

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None: ...

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None: ...

    # ── Import status ──

    async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None: ...

    async def get_import_status(self, package_id: str) -> ImportStatusRecord | None: ...

    async def list_ingested_package_ids(self) -> list[str]: ...

    # ── Counts ──

    async def count(self, table_name: str) -> int: ...
