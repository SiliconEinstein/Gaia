"""LanceDB storage backend for LKM."""

from __future__ import annotations

import asyncio
import json as _json
from functools import partial
from typing import Any

import lancedb

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
from gaia.lkm.storage._schemas import TABLE_SCHEMAS
from gaia.lkm.storage._serialization import (
    _q,
    binding_to_row,
    factor_param_to_row,
    global_factor_to_row,
    global_variable_to_row,
    local_factor_to_row,
    local_variable_to_row,
    param_source_to_row,
    prior_to_row,
    row_to_binding,
    row_to_global_factor,
    row_to_global_variable,
    row_to_local_factor,
    row_to_local_variable,
    row_to_param_source,
    row_to_prior,
)

_MAX_SCAN = 100_000


class LanceContentStore:
    """LanceDB-backed content store for LKM.

    All LanceDB calls are synchronous — wrapped via run_in_executor.
    """

    def __init__(self, uri: str) -> None:
        self._db = lancedb.connect(uri)

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous function in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ── Initialization ──

    async def initialize(self) -> None:
        """Create all tables if they don't exist, then ensure indexes."""
        existing = set(self._db.list_tables().tables)
        for table_name, schema in TABLE_SCHEMAS.items():
            if table_name not in existing:
                await self._run(self._db.create_table, table_name, schema=schema)
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        """Create scalar indexes on key columns. Safe to call repeatedly."""
        index_specs = [
            ("local_variable_nodes", "content_hash"),
            ("global_variable_nodes", "content_hash"),
            ("canonical_bindings", "local_id"),
            ("canonical_bindings", "global_id"),
            ("canonical_bindings", "binding_type"),
            ("prior_records", "variable_id"),
            ("factor_param_records", "factor_id"),
        ]
        for table_name, column in index_specs:
            try:
                table = self._db.open_table(table_name)
                await self._run(table.create_scalar_index, column, replace=True)
            except Exception:
                pass

    # ── Local node writes (idempotent: delete-then-add) ──

    async def write_local_variables(self, nodes: list[LocalVariableNode]) -> None:
        """Batch write local variable nodes with ingest_status='preparing'.

        Idempotent: deletes any existing rows for the same (source_package, version)
        before writing, so retries and re-seeds don't produce duplicates.
        """
        if not nodes:
            return
        table = self._db.open_table("local_variable_nodes")
        # Delete existing rows for this (package, version) to ensure idempotency
        pkg = _q(nodes[0].source_package)
        ver = _q(nodes[0].version)
        await self._run(table.delete, f"source_package = '{pkg}' AND version = '{ver}'")
        rows = [local_variable_to_row(n, ingest_status="preparing") for n in nodes]
        await self._run(table.add, rows)

    async def write_local_factors(self, nodes: list[LocalFactorNode]) -> None:
        """Batch write local factor nodes with ingest_status='preparing'.

        Idempotent: deletes any existing rows for the same (source_package, version).
        """
        if not nodes:
            return
        table = self._db.open_table("local_factor_nodes")
        pkg = _q(nodes[0].source_package)
        ver = _q(nodes[0].version)
        await self._run(table.delete, f"source_package = '{pkg}' AND version = '{ver}'")
        rows = [local_factor_to_row(n, ingest_status="preparing") for n in nodes]
        await self._run(table.add, rows)

    async def commit_ingest(self, source_package: str, version: str) -> None:
        """Flip ingest_status from 'preparing' to 'merged' for a specific (package, version)."""
        escaped_pkg = _q(source_package)
        escaped_ver = _q(version)
        where = (
            f"source_package = '{escaped_pkg}' AND version = '{escaped_ver}' "
            f"AND ingest_status = 'preparing'"
        )
        for table_name in ("local_variable_nodes", "local_factor_nodes"):
            table = self._db.open_table(table_name)
            preparing = await self._run(
                lambda t=table, w=where: t.search().where(w).limit(_MAX_SCAN).to_list()
            )
            if preparing:
                for row in preparing:
                    row["ingest_status"] = "merged"
                await self._run(table.delete, where)
                await self._run(table.add, preparing)

    # ── Global node writes ──

    async def write_global_variables(self, nodes: list[GlobalVariableNode]) -> None:
        if not nodes:
            return
        table = self._db.open_table("global_variable_nodes")
        rows = [global_variable_to_row(n) for n in nodes]
        await self._run(table.add, rows)

    async def write_global_factors(self, nodes: list[GlobalFactorNode]) -> None:
        if not nodes:
            return
        table = self._db.open_table("global_factor_nodes")
        rows = [global_factor_to_row(n) for n in nodes]
        await self._run(table.add, rows)

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        if not bindings:
            return
        table = self._db.open_table("canonical_bindings")
        rows = [binding_to_row(b) for b in bindings]
        await self._run(table.add, rows)

    # ── Parameterization writes ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("prior_records")
        rows = [prior_to_row(r) for r in records]
        await self._run(table.add, rows)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("factor_param_records")
        rows = [factor_param_to_row(r) for r in records]
        await self._run(table.add, rows)

    async def write_param_source(self, source: ParameterizationSource) -> None:
        table = self._db.open_table("param_sources")
        await self._run(table.add, [param_source_to_row(source)])

    # ── Reads: local nodes ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        table = self._db.open_table("local_variable_nodes")
        escaped = _q(local_id)
        results = await self._run(
            lambda: (
                table.search()
                .where(f"id = '{escaped}' AND ingest_status = 'merged'")
                .limit(1)
                .to_list()
            )
        )
        return row_to_local_variable(results[0]) if results else None

    async def get_local_variables_by_package(
        self, source_package: str, merged_only: bool = True
    ) -> list[LocalVariableNode]:
        table = self._db.open_table("local_variable_nodes")
        escaped = _q(source_package)
        where = f"source_package = '{escaped}'"
        if merged_only:
            where += " AND ingest_status = 'merged'"
        results = await self._run(lambda: table.search().where(where).limit(_MAX_SCAN).to_list())
        return [row_to_local_variable(r) for r in results]

    async def get_local_factor(self, factor_id: str) -> LocalFactorNode | None:
        table = self._db.open_table("local_factor_nodes")
        escaped = _q(factor_id)
        results = await self._run(
            lambda: (
                table.search()
                .where(f"id = '{escaped}' AND ingest_status = 'merged'")
                .limit(1)
                .to_list()
            )
        )
        return row_to_local_factor(results[0]) if results else None

    # ── Reads: global nodes ──

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(gcn_id)
        results = await self._run(
            lambda: table.search().where(f"id = '{escaped}'").limit(1).to_list()
        )
        return row_to_global_variable(results[0]) if results else None

    async def list_global_variables(
        self,
        type_filter: str | None = None,
        visibility: str = "public",
        limit: int = 100,
    ) -> list[GlobalVariableNode]:
        """List global variables with optional filters. Async-safe."""
        table = self._db.open_table("global_variable_nodes")
        where = f"visibility = '{_q(visibility)}'"
        if type_filter:
            where += f" AND type = '{_q(type_filter)}'"
        results = await self._run(lambda: table.search().where(where).limit(limit).to_list())
        return [row_to_global_variable(r) for r in results]

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(content_hash)
        results = await self._run(
            lambda: (
                table.search()
                .where(f"content_hash = '{escaped}' AND visibility = '{visibility}'")
                .limit(1)
                .to_list()
            )
        )
        return row_to_global_variable(results[0]) if results else None

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None:
        table = self._db.open_table("global_factor_nodes")
        escaped = _q(gfac_id)
        results = await self._run(
            lambda: table.search().where(f"id = '{escaped}'").limit(1).to_list()
        )
        return row_to_global_factor(results[0]) if results else None

    async def list_global_factors(
        self,
        factor_type: str | None = None,
        limit: int = 100,
    ) -> list[GlobalFactorNode]:
        """List global factors with optional filter. Async-safe."""
        table = self._db.open_table("global_factor_nodes")
        if factor_type:
            where = f"factor_type = '{_q(factor_type)}'"
            results = await self._run(lambda: table.search().where(where).limit(limit).to_list())
        else:
            results = await self._run(lambda: table.search().limit(limit).to_list())
        return [row_to_global_factor(r) for r in results]

    async def find_global_factor_exact(
        self,
        premises: list[str],
        conclusion: str,
        factor_type: str,
        subtype: str,
    ) -> GlobalFactorNode | None:
        table = self._db.open_table("global_factor_nodes")
        escaped_conclusion = _q(conclusion)
        escaped_type = _q(factor_type)
        escaped_subtype = _q(subtype)
        results = await self._run(
            lambda: (
                table.search()
                .where(
                    f"conclusion = '{escaped_conclusion}' AND "
                    f"factor_type = '{escaped_type}' AND "
                    f"subtype = '{escaped_subtype}'"
                )
                .limit(_MAX_SCAN)
                .to_list()
            )
        )
        sorted_premises = sorted(premises)
        for r in results:
            if sorted(_json.loads(r["premises"])) == sorted_premises:
                return row_to_global_factor(r)
        return None

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None:
        table = self._db.open_table("canonical_bindings")
        escaped = _q(local_id)
        results = await self._run(
            lambda: table.search().where(f"local_id = '{escaped}'").limit(1).to_list()
        )
        return row_to_binding(results[0]) if results else None

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]:
        table = self._db.open_table("canonical_bindings")
        escaped = _q(global_id)
        results = await self._run(
            lambda: table.search().where(f"global_id = '{escaped}'").limit(_MAX_SCAN).to_list()
        )
        return [row_to_binding(r) for r in results]

    async def list_bindings(
        self,
        package_id: str | None = None,
        binding_type: str | None = None,
        limit: int = 200,
    ) -> list[CanonicalBinding]:
        """List bindings with optional filters. Async-safe."""
        table = self._db.open_table("canonical_bindings")
        conditions = []
        if package_id:
            conditions.append(f"package_id = '{_q(package_id)}'")
        if binding_type:
            conditions.append(f"binding_type = '{_q(binding_type)}'")
        if conditions:
            where = " AND ".join(conditions)
            results = await self._run(lambda: table.search().where(where).limit(limit).to_list())
        else:
            results = await self._run(lambda: table.search().limit(limit).to_list())
        return [row_to_binding(r) for r in results]

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        table = self._db.open_table("prior_records")
        escaped = _q(variable_id)
        results = await self._run(
            lambda: table.search().where(f"variable_id = '{escaped}'").limit(_MAX_SCAN).to_list()
        )
        return [row_to_prior(r) for r in results]

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        table = self._db.open_table("param_sources")
        escaped = _q(source_id)
        results = await self._run(
            lambda: table.search().where(f"source_id = '{escaped}'").limit(1).to_list()
        )
        return row_to_param_source(results[0]) if results else None

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(gcn_id)
        await self._run(table.delete, f"id = '{escaped}'")
        await self._run(table.add, [global_variable_to_row(updated_node)])

    # ── Table counts ──

    async def count(self, table_name: str) -> int:
        table = self._db.open_table(table_name)
        return await self._run(lambda: table.count_rows())
