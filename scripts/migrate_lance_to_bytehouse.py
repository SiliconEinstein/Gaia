"""Backfill LKM data from LanceDB to ByteHouse.

Phase 3 of docs/plans/2026-04-09-bytehouse-as-primary-store.md.

The script reads each LKM table from LanceDB (local file or remote S3/TOS),
transforms each row (only ``premises`` JSON-string → ``Array(String)`` is
non-trivial), and inserts into the corresponding ``lkm_*`` table on
ByteHouse via ``clickhouse_connect``.

A source_package filter was considered and deliberately removed: lance
tables have no scalar index on ``source_package``, so filtering forces a
full-table scan per package — *slower* than a single full scan for the
whole dataset. Backfill is therefore whole-table only, with optional
``--limit-per-table`` for smoke tests.

Examples
--------

    # Smoke test: 100 rows per table, all 9 tables
    uv run python scripts/migrate_lance_to_bytehouse.py --limit-per-table 100

    # Full backfill, larger batches
    uv run python scripts/migrate_lance_to_bytehouse.py --batch-size 10000

    # Subset of tables
    uv run python scripts/migrate_lance_to_bytehouse.py --tables import_status,param_sources
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

import lancedb

from gaia.lkm.storage._bytehouse_schemas import COLUMN_ORDER
from gaia.lkm.storage.bytehouse_lkm_store import LANCE_TO_BH_TABLE, BytehouseLkmStore
from gaia.lkm.storage.config import StorageConfig

# Tables whose `premises` field is stored as a JSON string in LanceDB but as
# Array(String) in ByteHouse — needs in-flight conversion.
ARRAY_PREMISES_TABLES = {"local_factor_nodes", "global_factor_nodes"}

# Tables that have an `ingest_status` column with default 'merged'.
INGEST_STATUS_TABLES = {"local_variable_nodes", "local_factor_nodes"}

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _setup_logging() -> Path:
    log_file = _LOG_DIR / f"migrate-lance-to-bytehouse-{time.strftime('%Y%m%d-%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
        force=True,
    )
    logging.info("Log file: %s", log_file)
    return log_file


def _transform_row(lance_table: str, row: dict, ddl_key: str) -> list:
    """Convert one LanceDB row dict into a list ordered by BH column order."""
    cols = COLUMN_ORDER[ddl_key]
    # premises JSON-string → list[str] for the two factor tables
    if lance_table in ARRAY_PREMISES_TABLES:
        raw = row.get("premises") or "[]"
        try:
            row["premises"] = json.loads(raw) if isinstance(raw, str) else list(raw)
        except json.JSONDecodeError:
            row["premises"] = []
    # Default ingest_status if missing (lance schema always has it, defensive)
    if lance_table in INGEST_STATUS_TABLES and not row.get("ingest_status"):
        row["ingest_status"] = "merged"
    return [row.get(c) for c in cols]


def _scan_table(
    ldb: lancedb.LanceDBConnection,
    lance_table: str,
    *,
    limit: int | None,
) -> list[dict]:
    """Read rows from a LanceDB table, whole-table or capped by ``limit``."""
    table = ldb.open_table(lance_table)
    query = table.search()
    if limit:
        query = query.limit(limit)
    else:
        # Lance requires an explicit limit; pass total rows.
        query = query.limit(table.count_rows() or 1)
    return query.to_list()


def _migrate_table(
    *,
    ldb: lancedb.LanceDBConnection,
    bh_store: BytehouseLkmStore,
    lance_table: str,
    ddl_key: str,
    limit: int | None,
    batch_size: int,
    dry_run: bool,
) -> tuple[int, float]:
    cols = COLUMN_ORDER[ddl_key]
    bh_phys = bh_store._phys(ddl_key)

    t_read = time.time()
    rows = _scan_table(ldb, lance_table, limit=limit)
    read_secs = time.time() - t_read
    logging.info(
        "[%s] read %d rows from lance in %.2fs (limit=%s)",
        lance_table,
        len(rows),
        read_secs,
        limit,
    )
    if not rows:
        return 0, 0.0
    if dry_run:
        logging.info("[%s] dry-run: skipping ByteHouse insert", lance_table)
        return len(rows), 0.0

    written = 0
    t_write = time.time()
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        data = [_transform_row(lance_table, dict(r), ddl_key) for r in chunk]
        bh_store._client.insert(bh_phys, data, column_names=cols)
        written += len(data)
        logging.info("[%s] wrote %d/%d → %s", lance_table, written, len(rows), bh_phys)
    write_secs = time.time() - t_write
    return written, write_secs


def _verify_counts(
    bh_store: BytehouseLkmStore,
    ldb: lancedb.LanceDBConnection,
    requested: list[str],
) -> None:
    """Compare lance vs ByteHouse row counts for each processed table."""
    logging.info("=== Count verification ===")
    for lance_table in requested:
        ddl_key = LANCE_TO_BH_TABLE[lance_table]
        bh_phys = bh_store._phys(ddl_key)
        lt = ldb.open_table(lance_table)
        lance_n = lt.count_rows()
        bh_n = bh_store._client.query(f"SELECT count() FROM {bh_phys}").result_rows[0][0]
        marker = "✓" if lance_n == bh_n else "✗ MISMATCH"
        logging.info("  %-22s lance=%-12d bh=%-12d %s", lance_table, lance_n, bh_n, marker)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--limit-per-table",
        type=int,
        default=None,
        help="Cap rows per table (default: no limit). Useful for smoke tests.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per ByteHouse INSERT batch (default: 5000).",
    )
    parser.add_argument(
        "--tables",
        default=",".join(LANCE_TO_BH_TABLE.keys()),
        help="Comma-separated lance table names to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and transform but do not write to ByteHouse.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-backfill count comparison.",
    )
    parser.add_argument(
        "--init-tables",
        action="store_true",
        help="Run BytehouseLkmStore.initialize() to create tables before backfilling.",
    )
    args = parser.parse_args()

    log_file = _setup_logging()
    logging.info("Args: %s", args)

    config = StorageConfig()
    logging.info("Source LanceDB: %s", config.effective_lancedb_uri)
    logging.info(
        "Target ByteHouse: host=%s database=%s table_prefix=%s",
        config.bytehouse_host,
        config.bytehouse_database,
        config.bytehouse_table_prefix,
    )

    ldb_kwargs: dict = {}
    if config.storage_options:
        ldb_kwargs["storage_options"] = config.storage_options
    ldb = lancedb.connect(config.effective_lancedb_uri, **ldb_kwargs)

    bh_store = BytehouseLkmStore(
        host=config.bytehouse_host,
        user=config.bytehouse_user,
        password=config.bytehouse_password,
        database=config.bytehouse_database,
        replication_root=config.bytehouse_replication_root,
        table_prefix=config.bytehouse_table_prefix,
    )

    if args.init_tables and not args.dry_run:
        logging.info("Initializing ByteHouse tables (idempotent)...")
        await bh_store.initialize()

    requested = [t.strip() for t in args.tables.split(",") if t.strip()]
    summary: dict[str, tuple[int, float, float]] = {}
    for lance_table in requested:
        if lance_table not in LANCE_TO_BH_TABLE:
            logging.warning("skipping unknown table: %s", lance_table)
            continue
        ddl_key = LANCE_TO_BH_TABLE[lance_table]
        t0 = time.time()
        written, write_secs = _migrate_table(
            ldb=ldb,
            bh_store=bh_store,
            lance_table=lance_table,
            ddl_key=ddl_key,
            limit=args.limit_per_table,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        elapsed = time.time() - t0
        summary[lance_table] = (written, elapsed, write_secs)
        logging.info(
            "[%s] DONE: %d rows in %.2fs (write %.2fs)",
            lance_table,
            written,
            elapsed,
            write_secs,
        )

    logging.info("=== Summary ===")
    total_rows = 0
    total_secs = 0.0
    for tbl, (n, total, _w) in summary.items():
        logging.info("  %-22s %10d rows  %7.2fs", tbl, n, total)
        total_rows += n
        total_secs += total
    logging.info("  TOTAL                  %10d rows  %7.2fs", total_rows, total_secs)

    if not args.dry_run and not args.skip_verify:
        if args.limit_per_table:
            logging.info(
                "Skipping count verification (--limit-per-table=%d in effect; "
                "lance and bh counts are not comparable)",
                args.limit_per_table,
            )
        else:
            try:
                processed_tables = list(summary.keys())
                _verify_counts(bh_store, ldb, processed_tables)
            except Exception as exc:
                logging.exception("count verification failed: %s", exc)

    bh_store.close()
    logging.info("Log file: %s", log_file)


if __name__ == "__main__":
    asyncio.run(main())
