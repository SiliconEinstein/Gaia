"""LanceDB storage backend for LKM."""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from functools import partial
from typing import Any

import lancedb
import pyarrow as pa

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
from gaia.lkm.storage._schemas import TABLE_SCHEMAS
from gaia.lkm.storage._serialization import (
    _q,
    binding_to_row,
    factor_param_to_row,
    global_factor_to_row,
    global_variable_to_row,
    import_status_to_row,
    local_factor_to_row,
    local_variable_to_row,
    param_source_to_row,
    prior_to_row,
    row_to_binding,
    row_to_global_factor,
    row_to_global_variable,
    row_to_import_status,
    row_to_local_factor,
    row_to_local_variable,
    row_to_param_source,
    row_to_prior,
)

logger = logging.getLogger(__name__)

_MAX_SCAN = 100_000
_MAX_BATCH_BYTES = 100 * 1024 * 1024  # 100 MB per merge_insert batch


class LanceContentStore:
    """LanceDB-backed content store for LKM.

    All LanceDB calls are synchronous — wrapped via run_in_executor.
    """

    def __init__(self, uri: str, storage_options: dict[str, str] | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if storage_options:
            kwargs["storage_options"] = storage_options
        self._db = lancedb.connect(uri, **kwargs)

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
            ("local_variable_nodes", "id"),
            ("local_variable_nodes", "content_hash"),
            ("local_factor_nodes", "id"),
            ("global_variable_nodes", "id"),
            ("global_variable_nodes", "content_hash"),
            ("global_factor_nodes", "id"),
            ("canonical_bindings", "local_id"),
            ("canonical_bindings", "global_id"),
            ("canonical_bindings", "binding_type"),
            ("prior_records", "id"),
            ("prior_records", "variable_id"),
            ("factor_param_records", "id"),
            ("factor_param_records", "factor_id"),
            ("param_sources", "source_id"),
            ("import_status", "package_id"),
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

    # ── Batch upsert infrastructure ──

    @staticmethod
    def _split_rows_by_size(
        rows: list[dict],
        schema: pa.Schema,
        max_bytes: int = _MAX_BATCH_BYTES,
    ) -> list[pa.Table]:
        """Split rows into pa.Table batches of at most max_bytes each."""
        if not rows:
            return []
        batch_table = pa.Table.from_pylist(rows, schema=schema)
        if batch_table.nbytes <= max_bytes:
            return [batch_table]
        avg_row_bytes = max(1, batch_table.nbytes // len(rows))
        rows_per_batch = max(1, max_bytes // avg_row_bytes)
        batches = []
        for i in range(0, len(rows), rows_per_batch):
            batches.append(pa.Table.from_pylist(rows[i : i + rows_per_batch], schema=schema))
        return batches

    @staticmethod
    def _wait_for_index_ready(
        table: Any,
        index_name: str,
        max_unindexed: int = 10_000,
        sleep_seconds: float = 5.0,
    ) -> None:
        """Block until the index has fewer than max_unindexed unindexed rows."""
        while True:
            try:
                stats = table.index_stats(index_name)
                if stats.get("num_unindexed_rows", 0) < max_unindexed:
                    return
                time.sleep(sleep_seconds)
            except Exception:
                return

    def _upsert_sync(
        self,
        table_name: str,
        schema: pa.Schema,
        rows: list[dict],
        merge_key: str = "id",
    ) -> None:
        """Synchronous batch upsert via merge_insert. Called from executor.

        If the target table is empty, uses plain add() (faster, no HashJoin).
        Otherwise uses merge_insert for idempotent upsert.
        """
        if not rows:
            return
        # Deduplicate rows by merge_key (last wins) — merge_insert rejects
        # batches where multiple source rows match the same target key.
        seen: dict[str, int] = {}
        for i, row in enumerate(rows):
            seen[row[merge_key]] = i
        if len(seen) < len(rows):
            logger.info(
                "Deduped %d → %d rows by %s for %s",
                len(rows),
                len(seen),
                merge_key,
                table_name,
            )
            rows = [rows[i] for i in sorted(seen.values())]

        table = self._db.open_table(table_name)
        is_empty = table.count_rows() == 0

        if is_empty:
            # Fast path: empty table, just add
            batches = self._split_rows_by_size(rows, schema)
            for batch_table in batches:
                table.add(batch_table)
            try:
                table.optimize()
            except Exception:
                pass
        else:
            # Incremental path: merge_insert for idempotent upsert
            batches = self._split_rows_by_size(rows, schema)
            idx_name = f"{merge_key}_idx"
            for batch_table in batches:
                self._wait_for_index_ready(table, idx_name)
                (
                    table.merge_insert(merge_key)
                    .when_matched_update_all()
                    .when_not_matched_insert_all()
                    .execute(batch_table)
                )
                try:
                    table.optimize()
                except Exception:
                    pass

        logger.info(
            "Upserted %d rows into %s (%d batches, %s)",
            len(rows),
            table_name,
            len(batches),
            "add" if is_empty else "merge_insert",
        )

    async def _upsert(
        self,
        table_name: str,
        schema: pa.Schema,
        rows: list[dict],
        merge_key: str = "id",
    ) -> None:
        """Async batch upsert via merge_insert."""
        if not rows:
            return
        await self._run(self._upsert_sync, table_name, schema, rows, merge_key)

    # ── Batch local node writes (for batch import) ──

    async def batch_upsert_local_nodes(
        self,
        variables: list[LocalVariableNode],
        factors: list[LocalFactorNode],
    ) -> None:
        """Batch upsert local nodes directly as 'merged' via merge_insert.

        Use this for batch import instead of per-package
        write_local_variables + write_local_factors + commit_ingest.
        """
        if variables:
            rows = [local_variable_to_row(v, ingest_status="merged") for v in variables]
            await self._upsert("local_variable_nodes", TABLE_SCHEMAS["local_variable_nodes"], rows)
        if factors:
            rows = [local_factor_to_row(f, ingest_status="merged") for f in factors]
            await self._upsert("local_factor_nodes", TABLE_SCHEMAS["local_factor_nodes"], rows)

    # ── Global node writes ──

    async def write_global_variables(self, nodes: list[GlobalVariableNode]) -> None:
        if not nodes:
            return
        rows = [global_variable_to_row(n) for n in nodes]
        await self._upsert("global_variable_nodes", TABLE_SCHEMAS["global_variable_nodes"], rows)

    async def write_global_factors(self, nodes: list[GlobalFactorNode]) -> None:
        if not nodes:
            return
        rows = [global_factor_to_row(n) for n in nodes]
        await self._upsert("global_factor_nodes", TABLE_SCHEMAS["global_factor_nodes"], rows)

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        if not bindings:
            return
        rows = [binding_to_row(b) for b in bindings]
        await self._upsert(
            "canonical_bindings", TABLE_SCHEMAS["canonical_bindings"], rows, merge_key="local_id"
        )

    # ── Parameterization writes ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        if not records:
            return
        rows = [prior_to_row(r) for r in records]
        await self._upsert("prior_records", TABLE_SCHEMAS["prior_records"], rows)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        if not records:
            return
        rows = [factor_param_to_row(r) for r in records]
        await self._upsert("factor_param_records", TABLE_SCHEMAS["factor_param_records"], rows)

    async def write_param_source(self, source: ParameterizationSource) -> None:
        table = self._db.open_table("param_sources")
        await self._run(table.add, [param_source_to_row(source)])

    async def write_param_sources_batch(self, sources: list[ParameterizationSource]) -> None:
        if not sources:
            return
        rows = [param_source_to_row(s) for s in sources]
        await self._upsert(
            "param_sources", TABLE_SCHEMAS["param_sources"], rows, merge_key="source_id"
        )

    # ── Batch reads (for batch_integrate) ──

    async def find_globals_by_content_hashes(
        self, hashes: set[str]
    ) -> dict[str, GlobalVariableNode]:
        """Find existing global variables for a set of content_hashes. One query."""
        if not hashes:
            return {}
        table = self._db.open_table("global_variable_nodes")
        # Build IN clause in batches of 500 to avoid query size limits
        result_map: dict[str, GlobalVariableNode] = {}
        hash_list = list(hashes)
        for i in range(0, len(hash_list), 500):
            batch = hash_list[i : i + 500]
            in_clause = ", ".join(f"'{_q(h)}'" for h in batch)
            results = await self._run(
                lambda ic=in_clause: (
                    table.search()
                    .where(f"content_hash IN ({ic})")
                    .limit(len(batch) + 100)
                    .to_list()
                )
            )
            for r in results:
                gv = row_to_global_variable(r)
                result_map[gv.content_hash] = gv
        logger.info("Batch content_hash lookup: %d queried, %d found", len(hashes), len(result_map))
        return result_map

    async def find_bindings_by_local_ids(self, local_ids: set[str]) -> dict[str, CanonicalBinding]:
        """Find existing bindings for a set of local_ids. One query."""
        if not local_ids:
            return {}
        table = self._db.open_table("canonical_bindings")
        result_map: dict[str, CanonicalBinding] = {}
        id_list = list(local_ids)
        for i in range(0, len(id_list), 500):
            batch = id_list[i : i + 500]
            in_clause = ", ".join(f"'{_q(lid)}'" for lid in batch)
            results = await self._run(
                lambda ic=in_clause: (
                    table.search().where(f"local_id IN ({ic})").limit(len(batch) + 100).to_list()
                )
            )
            for r in results:
                b = row_to_binding(r)
                result_map[b.local_id] = b
        return result_map

    async def find_global_factors_by_conclusions(
        self, conclusions: set[str]
    ) -> list[GlobalFactorNode]:
        """Find existing global factors by conclusion set. Memory filter for premises."""
        if not conclusions:
            return []
        table = self._db.open_table("global_factor_nodes")
        all_results: list[GlobalFactorNode] = []
        conc_list = list(conclusions)
        for i in range(0, len(conc_list), 500):
            batch = conc_list[i : i + 500]
            in_clause = ", ".join(f"'{_q(c)}'" for c in batch)
            results = await self._run(
                lambda ic=in_clause: (
                    table.search().where(f"conclusion IN ({ic})").limit(_MAX_SCAN).to_list()
                )
            )
            all_results.extend(row_to_global_factor(r) for r in results)
        logger.info(
            "Batch factor lookup: %d conclusions queried, %d factors found",
            len(conclusions),
            len(all_results),
        )
        return all_results

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

    # ── Import status ──

    async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None:
        """Batch upsert import status records (idempotent by package_id)."""
        if not records:
            return
        rows = [import_status_to_row(r) for r in records]
        await self._upsert(
            "import_status", TABLE_SCHEMAS["import_status"], rows, merge_key="package_id"
        )

    async def get_import_status(self, package_id: str) -> ImportStatusRecord | None:
        table = self._db.open_table("import_status")
        escaped = _q(package_id)
        results = await self._run(
            lambda: table.search().where(f"package_id = '{escaped}'").limit(1).to_list()
        )
        return row_to_import_status(results[0]) if results else None

    async def list_ingested_package_ids(self) -> list[str]:
        """Return all package_ids with status='ingested' from import_status."""
        table = self._db.open_table("import_status")

        def _read() -> list[str]:
            df = (
                table.search()
                .select(["package_id", "status"])
                .limit(table.count_rows())
                .to_pandas()
            )
            return df.loc[df["status"] == "ingested", "package_id"].tolist()

        return await self._run(_read)

    # ── Table counts ──

    async def count(self, table_name: str) -> int:
        table = self._db.open_table(table_name)
        return await self._run(lambda: table.count_rows())
