"""ByteHouse-backed LKM content store.

Implements :class:`gaia.lkm.storage.protocol.LkmContentStore` against a
ByteHouse (ClickHouse-compatible) cluster, mirroring the public surface of
:class:`gaia.lkm.storage.lance_store.LanceContentStore` so that
``StorageManager`` can switch backends transparently.

Design notes
------------

* The underlying ``clickhouse_connect`` driver is synchronous; every public
  method wraps the call in ``run_in_executor`` to remain async-compatible.
* Tables are prefixed with ``lkm_`` to avoid colliding with the existing
  embedding tables managed by :class:`ByteHouseEmbeddingStore`.
* Premises columns use ``Array(String)`` natively (instead of JSON strings),
  enabling fast ``has(premises, 'gcn_xxx')`` lookups.
* Idempotent upserts are achieved via ``HaUniqueMergeTree``: re-inserting a
  row with the same ``UNIQUE KEY`` replaces the previous row on merge.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from functools import partial
from typing import Any

import clickhouse_connect

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
from gaia.lkm.storage._bytehouse_schemas import COLUMN_ORDER, LKM_TABLES
from gaia.lkm.storage._serialization import (
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


# Map LanceDB-style table names (used by callers like ``count()``) to the
# corresponding ByteHouse table names.
LANCE_TO_BH_TABLE: dict[str, str] = {
    "local_variable_nodes": "lkm_local_variables",
    "local_factor_nodes": "lkm_local_factors",
    "global_variable_nodes": "lkm_global_variables",
    "global_factor_nodes": "lkm_global_factors",
    "canonical_bindings": "lkm_canonical_bindings",
    "prior_records": "lkm_prior_records",
    "factor_param_records": "lkm_factor_param_records",
    "param_sources": "lkm_param_sources",
    "import_status": "lkm_import_status",
}


_IN_BATCH = 500


class BytehouseLkmStore:
    """ByteHouse-backed implementation of :class:`LkmContentStore`."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str = "paper_data",
        secure: bool = True,
        replication_root: str = "",
        table_prefix: str = "lkm_",
    ) -> None:
        self._database = database
        self._replication_root = replication_root
        self._table_prefix = table_prefix
        # Map canonical (DDL key) name → actual physical table name in ByteHouse.
        # The DDL keys all start with ``lkm_``; we substitute that prefix with
        # the configured ``table_prefix`` so integration tests can isolate.
        self._physical: dict[str, str] = {
            ddl_key: table_prefix + ddl_key[len("lkm_") :] for ddl_key in LKM_TABLES
        }
        # Convenient short aliases for SQL string interpolation.
        self.t_lvars = self._physical["lkm_local_variables"]
        self.t_lfacs = self._physical["lkm_local_factors"]
        self.t_gvars = self._physical["lkm_global_variables"]
        self.t_gfacs = self._physical["lkm_global_factors"]
        self.t_bindings = self._physical["lkm_canonical_bindings"]
        self.t_priors = self._physical["lkm_prior_records"]
        self.t_fparams = self._physical["lkm_factor_param_records"]
        self.t_psources = self._physical["lkm_param_sources"]
        self.t_istatus = self._physical["lkm_import_status"]
        self._client = clickhouse_connect.get_client(
            host=host,
            user=user,
            password=password,
            database=database,
            secure=secure,
            compress=False,
        )

    def _phys(self, ddl_key: str) -> str:
        return self._physical[ddl_key]

    # ── Internals ──

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    def _require_replication_root(self) -> None:
        if not self._replication_root:
            raise ValueError(
                "bytehouse_replication_root is required for HaUniqueMergeTree DDL. "
                "Set BYTEHOUSE_REPLICATION_ROOT env var."
            )

    def _engine_clause(self, table: str) -> str:
        self._require_replication_root()
        return (
            f"ENGINE = HaUniqueMergeTree("
            f"'{self._replication_root}/{self._database}.{table}/{{shard}}', "
            f"'{{replica}}')"
        )

    def _bh_table(self, lance_name: str) -> str:
        try:
            ddl_key = LANCE_TO_BH_TABLE[lance_name]
        except KeyError as exc:
            raise KeyError(f"Unknown LKM table: {lance_name}") from exc
        return self._phys(ddl_key)

    # ── Initialization ──

    async def initialize(self) -> None:
        """Create all LKM tables if they don't already exist."""
        for ddl_key, ddl_template in LKM_TABLES.items():
            physical = self._phys(ddl_key)
            ddl = ddl_template.format(table=physical, engine=self._engine_clause(physical))
            await self._run(self._client.command, ddl)

    # ── Row builders (premises Array conversion) ──

    @staticmethod
    def _row_to_values(row: dict, table: str) -> list:
        return [row[c] for c in COLUMN_ORDER[table]]

    @staticmethod
    def _local_var_values(node: LocalVariableNode, ingest_status: str) -> list:
        row = local_variable_to_row(node, ingest_status=ingest_status)
        return BytehouseLkmStore._row_to_values(row, "lkm_local_variables")

    @staticmethod
    def _local_factor_values(node: LocalFactorNode, ingest_status: str) -> list:
        row = local_factor_to_row(node, ingest_status=ingest_status)
        # premises: JSON string → list[str] (Array(String))
        row["premises"] = list(node.premises)
        return BytehouseLkmStore._row_to_values(row, "lkm_local_factors")

    @staticmethod
    def _global_var_values(node: GlobalVariableNode) -> list:
        row = global_variable_to_row(node)
        return BytehouseLkmStore._row_to_values(row, "lkm_global_variables")

    @staticmethod
    def _global_factor_values(node: GlobalFactorNode) -> list:
        row = global_factor_to_row(node)
        row["premises"] = list(node.premises)
        return BytehouseLkmStore._row_to_values(row, "lkm_global_factors")

    @staticmethod
    def _binding_values(b: CanonicalBinding) -> list:
        return BytehouseLkmStore._row_to_values(binding_to_row(b), "lkm_canonical_bindings")

    @staticmethod
    def _prior_values(r: PriorRecord) -> list:
        return BytehouseLkmStore._row_to_values(prior_to_row(r), "lkm_prior_records")

    @staticmethod
    def _factor_param_values(r: FactorParamRecord) -> list:
        return BytehouseLkmStore._row_to_values(factor_param_to_row(r), "lkm_factor_param_records")

    @staticmethod
    def _param_source_values(s: ParameterizationSource) -> list:
        return BytehouseLkmStore._row_to_values(param_source_to_row(s), "lkm_param_sources")

    @staticmethod
    def _import_status_values(r: ImportStatusRecord) -> list:
        return BytehouseLkmStore._row_to_values(import_status_to_row(r), "lkm_import_status")

    def _insert_sync(self, ddl_key: str, data: list[list]) -> None:
        if not data:
            return
        self._client.insert(self._phys(ddl_key), data, column_names=COLUMN_ORDER[ddl_key])

    # ── Result helpers ──

    @staticmethod
    def _row_with_premises_as_json(row: dict) -> dict:
        """Convert premises Array(String) → JSON string for ``row_to_*_factor``."""
        row["premises"] = _json.dumps(list(row.get("premises") or []))
        return row

    def _query_dicts(self, sql: str, parameters: dict | None = None) -> list[dict]:
        result = self._client.query(sql, parameters=parameters or {})
        cols = result.column_names
        return [dict(zip(cols, row, strict=False)) for row in result.result_rows]

    # ── Local node writes ──

    async def write_local_variables(self, nodes: list[LocalVariableNode]) -> None:
        if not nodes:
            return
        data = [self._local_var_values(n, ingest_status="preparing") for n in nodes]
        await self._run(self._insert_sync, "lkm_local_variables", data)

    async def write_local_factors(self, nodes: list[LocalFactorNode]) -> None:
        if not nodes:
            return
        data = [self._local_factor_values(n, ingest_status="preparing") for n in nodes]
        await self._run(self._insert_sync, "lkm_local_factors", data)

    async def commit_ingest(self, source_package: str, version: str) -> None:
        """Flip ingest_status from 'preparing' to 'merged' for (package, version).

        Implemented as SELECT-then-INSERT — HaUniqueMergeTree dedup on
        ``UNIQUE KEY id`` overwrites the existing row with the merged copy.
        """
        for ddl_key in ("lkm_local_variables", "lkm_local_factors"):
            sql = (
                f"SELECT * FROM {self._phys(ddl_key)} "
                f"WHERE source_package = %(pkg)s "
                f"AND version = %(ver)s "
                f"AND ingest_status = 'preparing'"
            )
            rows = await self._run(self._query_dicts, sql, {"pkg": source_package, "ver": version})
            if not rows:
                continue
            for r in rows:
                r["ingest_status"] = "merged"
            data = [self._row_to_values(r, ddl_key) for r in rows]
            await self._run(self._insert_sync, ddl_key, data)

    async def batch_upsert_local_nodes(
        self,
        variables: list[LocalVariableNode],
        factors: list[LocalFactorNode],
    ) -> None:
        if variables:
            data = [self._local_var_values(v, ingest_status="merged") for v in variables]
            await self._run(self._insert_sync, "lkm_local_variables", data)
        if factors:
            data = [self._local_factor_values(f, ingest_status="merged") for f in factors]
            await self._run(self._insert_sync, "lkm_local_factors", data)

    # ── Global node writes ──

    async def write_global_variables(self, nodes: list[GlobalVariableNode]) -> None:
        if not nodes:
            return
        data = [self._global_var_values(n) for n in nodes]
        await self._run(self._insert_sync, "lkm_global_variables", data)

    async def write_global_factors(self, nodes: list[GlobalFactorNode]) -> None:
        if not nodes:
            return
        data = [self._global_factor_values(n) for n in nodes]
        await self._run(self._insert_sync, "lkm_global_factors", data)

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        if not bindings:
            return
        data = [self._binding_values(b) for b in bindings]
        await self._run(self._insert_sync, "lkm_canonical_bindings", data)

    # ── Parameterization writes ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        if not records:
            return
        data = [self._prior_values(r) for r in records]
        await self._run(self._insert_sync, "lkm_prior_records", data)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        if not records:
            return
        data = [self._factor_param_values(r) for r in records]
        await self._run(self._insert_sync, "lkm_factor_param_records", data)

    async def write_param_source(self, source: ParameterizationSource) -> None:
        data = [self._param_source_values(source)]
        await self._run(self._insert_sync, "lkm_param_sources", data)

    async def write_param_sources_batch(self, sources: list[ParameterizationSource]) -> None:
        if not sources:
            return
        data = [self._param_source_values(s) for s in sources]
        await self._run(self._insert_sync, "lkm_param_sources", data)

    # ── Batch reads ──

    async def find_globals_by_content_hashes(
        self, hashes: set[str]
    ) -> dict[str, GlobalVariableNode]:
        if not hashes:
            return {}
        result_map: dict[str, GlobalVariableNode] = {}
        hash_list = list(hashes)
        for i in range(0, len(hash_list), _IN_BATCH):
            batch = hash_list[i : i + _IN_BATCH]
            sql = f"SELECT * FROM {self.t_gvars} WHERE content_hash IN %(hashes)s"
            rows = await self._run(self._query_dicts, sql, {"hashes": batch})
            for r in rows:
                gv = row_to_global_variable(r)
                result_map[gv.content_hash] = gv
        logger.info("Batch content_hash lookup: %d queried, %d found", len(hashes), len(result_map))
        return result_map

    async def find_bindings_by_local_ids(self, local_ids: set[str]) -> dict[str, CanonicalBinding]:
        if not local_ids:
            return {}
        result_map: dict[str, CanonicalBinding] = {}
        id_list = list(local_ids)
        for i in range(0, len(id_list), _IN_BATCH):
            batch = id_list[i : i + _IN_BATCH]
            sql = f"SELECT * FROM {self.t_bindings} WHERE local_id IN %(ids)s"
            rows = await self._run(self._query_dicts, sql, {"ids": batch})
            for r in rows:
                b = row_to_binding(r)
                result_map[b.local_id] = b
        return result_map

    async def find_global_factors_by_conclusions(
        self, conclusions: set[str]
    ) -> list[GlobalFactorNode]:
        if not conclusions:
            return []
        all_results: list[GlobalFactorNode] = []
        conc_list = list(conclusions)
        for i in range(0, len(conc_list), _IN_BATCH):
            batch = conc_list[i : i + _IN_BATCH]
            sql = f"SELECT * FROM {self.t_gfacs} WHERE conclusion IN %(concs)s"
            rows = await self._run(self._query_dicts, sql, {"concs": batch})
            all_results.extend(
                row_to_global_factor(self._row_with_premises_as_json(r)) for r in rows
            )
        logger.info(
            "Batch factor lookup: %d conclusions queried, %d factors found",
            len(conclusions),
            len(all_results),
        )
        return all_results

    # ── Reads: local nodes ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        sql = f"SELECT * FROM {self.t_lvars} WHERE id = %(id)s AND ingest_status = 'merged' LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": local_id})
        return row_to_local_variable(rows[0]) if rows else None

    async def get_local_variables_by_ids(
        self, local_ids: list[str], concurrency: int = 4
    ) -> dict[str, LocalVariableNode]:
        if not local_ids:
            return {}
        result_map: dict[str, LocalVariableNode] = {}
        sem = asyncio.Semaphore(concurrency)

        async def _fetch(batch: list[str]) -> list[LocalVariableNode]:
            sql = f"SELECT * FROM {self.t_lvars} WHERE id IN %(ids)s AND ingest_status = 'merged'"
            async with sem:
                rows = await self._run(self._query_dicts, sql, {"ids": batch})
            return [row_to_local_variable(r) for r in rows]

        batches = [local_ids[i : i + _IN_BATCH] for i in range(0, len(local_ids), _IN_BATCH)]
        results = await asyncio.gather(*[_fetch(b) for b in batches])
        for lvs in results:
            for lv in lvs:
                result_map[lv.id] = lv
        logger.info(
            "Batch local variable lookup: %d queried, %d found (%d batches)",
            len(local_ids),
            len(result_map),
            len(batches),
        )
        return result_map

    async def get_local_variables_by_package(
        self, source_package: str, merged_only: bool = True
    ) -> list[LocalVariableNode]:
        sql = f"SELECT * FROM {self.t_lvars} WHERE source_package = %(pkg)s"
        if merged_only:
            sql += " AND ingest_status = 'merged'"
        rows = await self._run(self._query_dicts, sql, {"pkg": source_package})
        return [row_to_local_variable(r) for r in rows]

    async def get_local_factor(self, factor_id: str) -> LocalFactorNode | None:
        sql = f"SELECT * FROM {self.t_lfacs} WHERE id = %(id)s AND ingest_status = 'merged' LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": factor_id})
        if not rows:
            return None
        return row_to_local_factor(self._row_with_premises_as_json(rows[0]))

    # ── Reads: global nodes ──

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        sql = f"SELECT * FROM {self.t_gvars} WHERE id = %(id)s LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": gcn_id})
        return row_to_global_variable(rows[0]) if rows else None

    async def list_global_variables(
        self,
        type_filter: str | None = None,
        visibility: str = "public",
        limit: int = 100,
    ) -> list[GlobalVariableNode]:
        params: dict[str, Any] = {"vis": visibility, "lim": limit}
        sql = f"SELECT * FROM {self.t_gvars} WHERE visibility = %(vis)s"
        if type_filter:
            sql += " AND type = %(t)s"
            params["t"] = type_filter
        sql += " LIMIT %(lim)s"
        rows = await self._run(self._query_dicts, sql, params)
        return [row_to_global_variable(r) for r in rows]

    async def list_all_public_global_ids(self) -> list[dict]:
        sql = f"SELECT id, type, representative_lcn FROM {self.t_gvars} WHERE visibility = 'public'"
        rows = await self._run(self._query_dicts, sql)
        return [
            {
                "id": r["id"],
                "type": r["type"],
                "representative_lcn": r["representative_lcn"],
            }
            for r in rows
        ]

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        sql = (
            f"SELECT * FROM {self.t_gvars} "
            "WHERE content_hash = %(h)s AND visibility = %(vis)s LIMIT 1"
        )
        rows = await self._run(self._query_dicts, sql, {"h": content_hash, "vis": visibility})
        return row_to_global_variable(rows[0]) if rows else None

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None:
        sql = f"SELECT * FROM {self.t_gfacs} WHERE id = %(id)s LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": gfac_id})
        if not rows:
            return None
        return row_to_global_factor(self._row_with_premises_as_json(rows[0]))

    async def list_global_factors(
        self,
        factor_type: str | None = None,
        limit: int = 100,
    ) -> list[GlobalFactorNode]:
        params: dict[str, Any] = {"lim": limit}
        sql = f"SELECT * FROM {self.t_gfacs}"
        if factor_type:
            sql += " WHERE factor_type = %(t)s"
            params["t"] = factor_type
        sql += " LIMIT %(lim)s"
        rows = await self._run(self._query_dicts, sql, params)
        return [row_to_global_factor(self._row_with_premises_as_json(r)) for r in rows]

    async def find_global_factor_exact(
        self,
        premises: list[str],
        conclusion: str,
        factor_type: str,
        subtype: str,
    ) -> GlobalFactorNode | None:
        sql = (
            f"SELECT * FROM {self.t_gfacs} "
            "WHERE conclusion = %(c)s AND factor_type = %(t)s AND subtype = %(s)s"
        )
        rows = await self._run(
            self._query_dicts,
            sql,
            {"c": conclusion, "t": factor_type, "s": subtype},
        )
        sorted_premises = sorted(premises)
        for r in rows:
            if sorted(list(r.get("premises") or [])) == sorted_premises:
                return row_to_global_factor(self._row_with_premises_as_json(r))
        return None

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None:
        sql = f"SELECT * FROM {self.t_bindings} WHERE local_id = %(id)s LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": local_id})
        return row_to_binding(rows[0]) if rows else None

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]:
        sql = f"SELECT * FROM {self.t_bindings} WHERE global_id = %(id)s"
        rows = await self._run(self._query_dicts, sql, {"id": global_id})
        return [row_to_binding(r) for r in rows]

    async def list_bindings(
        self,
        package_id: str | None = None,
        binding_type: str | None = None,
        limit: int = 200,
    ) -> list[CanonicalBinding]:
        clauses = []
        params: dict[str, Any] = {"lim": limit}
        if package_id:
            clauses.append("package_id = %(pkg)s")
            params["pkg"] = package_id
        if binding_type:
            clauses.append("binding_type = %(bt)s")
            params["bt"] = binding_type
        sql = f"SELECT * FROM {self.t_bindings}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " LIMIT %(lim)s"
        rows = await self._run(self._query_dicts, sql, params)
        return [row_to_binding(r) for r in rows]

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        sql = f"SELECT * FROM {self.t_priors} WHERE variable_id = %(id)s"
        rows = await self._run(self._query_dicts, sql, {"id": variable_id})
        return [row_to_prior(r) for r in rows]

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        sql = f"SELECT * FROM {self.t_psources} WHERE source_id = %(id)s LIMIT 1"
        rows = await self._run(self._query_dicts, sql, {"id": source_id})
        return row_to_param_source(rows[0]) if rows else None

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        # HaUniqueMergeTree dedupes on UNIQUE KEY id — re-inserting overwrites.
        if updated_node.id != gcn_id:
            raise ValueError(
                f"update_global_variable_members: gcn_id mismatch ({gcn_id} != {updated_node.id})"
            )
        await self.write_global_variables([updated_node])

    # ── Import status ──

    async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None:
        if not records:
            return
        data = [self._import_status_values(r) for r in records]
        await self._run(self._insert_sync, "lkm_import_status", data)

    async def get_import_status(self, package_id: str) -> ImportStatusRecord | None:
        """Return the latest ingest attempt for ``package_id``.

        import_status is an attempt log (composite UNIQUE KEY
        ``(package_id, started_at)``): a package may have multiple rows
        corresponding to retries. This method returns the row with the
        greatest ``started_at`` — that is, the most recent attempt,
        regardless of whether it succeeded or failed.
        """
        sql = (
            f"SELECT * FROM {self.t_istatus} "
            "WHERE package_id = %(id)s "
            "ORDER BY started_at DESC LIMIT 1"
        )
        rows = await self._run(self._query_dicts, sql, {"id": package_id})
        return row_to_import_status(rows[0]) if rows else None

    async def list_ingested_package_ids(self) -> list[str]:
        """Return the unique set of package_ids whose latest attempt succeeded.

        Because the table is an attempt log, DISTINCT is required to avoid
        duplicate package_ids from multiple ``status='ingested'`` rows
        (possible when a package is re-ingested later).
        """
        sql = f"SELECT DISTINCT package_id FROM {self.t_istatus} WHERE status = 'ingested'"
        rows = await self._run(self._query_dicts, sql)
        return [r["package_id"] for r in rows]

    # ── Counts ──

    async def count(self, table_name: str) -> int:
        bh_table = self._bh_table(table_name)
        sql = f"SELECT count() AS n FROM {bh_table}"
        rows = await self._run(self._query_dicts, sql)
        return int(rows[0]["n"]) if rows else 0

    # ── Cleanup ──

    def close(self) -> None:
        self._client.close()

    # ── Test helpers ──

    async def drop_all_tables(self) -> None:
        """Drop every LKM table managed by this store. Test/integration only.

        Uses ``DROP TABLE ... SYNC`` so that HaUniqueMergeTree replica
        data in ZooKeeper is fully cleaned up before returning. Without
        SYNC, a subsequent ``CREATE TABLE IF NOT EXISTS`` with the same
        ZK path would silently re-attach to the old replica, bringing
        back both the old data and the old schema — a nasty footgun.
        """
        for ddl_key in LKM_TABLES:
            physical = self._phys(ddl_key)
            await self._run(self._client.command, f"DROP TABLE IF EXISTS {physical} SYNC")


__all__ = ["BytehouseLkmStore", "LANCE_TO_BH_TABLE"]
