"""Pipeline: compute embeddings for all pending public global variables.

Incremental: skips gcn_ids already in ByteHouse.
Writes embedding with package_id and role (conclusion/premise).
After completion, refreshes embedding_status table.

Usage:
    python -m gaia.lkm.pipelines.embedding                    # full run
    python -m gaia.lkm.pipelines.embedding --limit 1000        # small test
    python -m gaia.lkm.pipelines.embedding --dry-run           # check status
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import lancedb

from gaia.lkm.models.discovery import DiscoveryConfig

logger = logging.getLogger(__name__)


def _create_bytehouse(config=None):
    """Create ByteHouseEmbeddingStore from env config."""
    from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore
    from gaia.lkm.storage.config import StorageConfig

    cfg = config or StorageConfig()
    if not cfg.bytehouse_host:
        raise RuntimeError("ByteHouse not configured — set BYTEHOUSE_HOST env var")
    return ByteHouseEmbeddingStore(
        host=cfg.bytehouse_host,
        user=cfg.bytehouse_user,
        password=cfg.bytehouse_password,
        database=cfg.bytehouse_database,
        replication_root=cfg.bytehouse_replication_root,
    ), cfg


def _build_role_map(db, gcn_set: set[str], t0: float) -> dict[str, str]:
    """Build {gcn_id: role} for the given gcn_set.

    Strategy: query global_factor_nodes WHERE conclusion IN (gcn_set) — fast,
    avoids scanning the full factor table. Defaults all gcn_ids to "premise"
    and overrides matches to "conclusion".

    Rationale: every public gcn_id is either a premise or a conclusion of
    some factor (variables don't exist in isolation). We can't query the
    premises array column directly (stored as JSON string), so we default
    to "premise" and use conclusion-IN query to identify the conclusions.

    This may slightly mis-label fully orphan variables as "premise", which
    is acceptable.
    """
    logger.info("[%.0fs] Building role map for %d gcn_ids...", time.time() - t0, len(gcn_set))
    gfac_table = db.open_table("global_factor_nodes")

    conclusions: set[str] = set()
    gcn_list = list(gcn_set)
    batch_size = 500
    n_batches = (len(gcn_list) + batch_size - 1) // batch_size

    for i in range(0, len(gcn_list), batch_size):
        batch = gcn_list[i : i + batch_size]
        in_clause = ", ".join(f"'{g}'" for g in batch)
        rows = (
            gfac_table.search()
            .where(f"conclusion IN ({in_clause})")
            .select(["conclusion"])
            .limit(len(batch) * 2 + 100)
            .to_list()
        )
        for r in rows:
            c = r.get("conclusion")
            if c:
                conclusions.add(c)
        if (i // batch_size + 1) % 10 == 0 or i + batch_size >= len(gcn_list):
            logger.info(
                "[%.0fs] role map: %d/%d batches, %d conclusions found",
                time.time() - t0,
                i // batch_size + 1,
                n_batches,
                len(conclusions),
            )

    # Default everyone to "premise", override matches to "conclusion"
    role_map = {gcn_id: "premise" for gcn_id in gcn_set}
    for gcn_id in conclusions:
        role_map[gcn_id] = "conclusion"

    logger.info(
        "[%.0fs] Role map built: %d total (%d conclusions, %d premise default)",
        time.time() - t0,
        len(role_map),
        len(conclusions),
        len(role_map) - len(conclusions),
    )
    return role_map


async def run_embedding_pipeline(
    config: DiscoveryConfig | None = None,
    limit: int | None = None,
) -> dict:
    """Compute embeddings for all pending public global variables.

    Args:
        config: Discovery config. Uses defaults if None.
        limit: If set, only process first N pending variables (for testing).

    Returns stats dict: {total, computed, skipped, failed}.
    """
    from gaia.lkm.core._embedding import compute_embeddings
    from gaia.lkm.storage.config import StorageConfig

    t0 = time.time()
    if config is None:
        config = DiscoveryConfig()

    cfg = StorageConfig()
    logger.info("Starting embedding pipeline. LanceDB: %s", cfg.effective_lancedb_uri)

    # Direct LanceDB connect (no initialize() — slow index creation on remote S3)
    logger.info("Connecting to LanceDB...")
    db = lancedb.connect(cfg.effective_lancedb_uri, storage_options=cfg.storage_options)
    logger.info("[%.0fs] LanceDB connected", time.time() - t0)

    bytehouse, _ = _create_bytehouse(cfg)
    bytehouse.ensure_all_tables()
    logger.info("[%.0fs] ByteHouse ready", time.time() - t0)

    # Build storage wrapper
    class _LanceStorage:
        def __init__(self, lance_db, limit_val):
            self._db = lance_db
            self._limit = limit_val

        async def list_all_public_global_ids(self) -> list[dict]:
            logger.info("[%.0fs] Listing public global variables...", time.time() - t0)
            t = self._db.open_table("global_variable_nodes")
            total = t.count_rows()
            logger.info("[%.0fs] Total global_variable_nodes: %d", time.time() - t0, total)

            q = (
                t.search()
                .where("visibility = 'public'")
                .select(["id", "type", "representative_lcn"])
                .limit(self._limit if self._limit else max(total, 100000))
            )
            result = q.to_list()
            logger.info("[%.0fs] Loaded %d public global ids", time.time() - t0, len(result))
            return [
                {"id": r["id"], "type": r["type"], "representative_lcn": r["representative_lcn"]}
                for r in result
            ]

        async def get_local_variables_by_ids(self, local_ids, concurrency=4):
            # Import lazily to avoid LanceContentStore.initialize()
            from gaia.lkm.storage._serialization import row_to_local_variable

            if not local_ids:
                return {}

            t = self._db.open_table("local_variable_nodes")
            result_map = {}
            loop = asyncio.get_running_loop()

            async def fetch_batch(batch_ids):
                in_clause = ", ".join(f"'{lid}'" for lid in batch_ids)

                def q():
                    return (
                        t.search()
                        .where(f"id IN ({in_clause}) AND ingest_status = 'merged'")
                        .limit(len(batch_ids) + 100)
                        .to_list()
                    )

                rows = await loop.run_in_executor(None, q)
                return [row_to_local_variable(r) for r in rows]

            sem = asyncio.Semaphore(concurrency)

            async def bounded(batch_ids):
                async with sem:
                    return await fetch_batch(batch_ids)

            batches = [local_ids[i : i + 500] for i in range(0, len(local_ids), 500)]
            batch_results = await asyncio.gather(*[bounded(b) for b in batches])
            for lvs in batch_results:
                for lv in lvs:
                    result_map[lv.id] = lv
            return result_map

    storage = _LanceStorage(db, limit)

    try:
        # Build role_map first (before embedding, so we can tag each record)
        pending_list = await storage.list_all_public_global_ids()
        existing = bytehouse.get_existing_gcn_ids()
        pending_gcn_ids = {g["id"] for g in pending_list if g["id"] not in existing}
        logger.info(
            "[%.0fs] Pending: %d (total: %d, existing: %d)",
            time.time() - t0,
            len(pending_gcn_ids),
            len(pending_list),
            len(existing),
        )

        if not pending_gcn_ids:
            logger.info("Nothing to embed")
            return {
                "total": len(pending_list),
                "computed": 0,
                "skipped": len(existing),
                "failed": 0,
            }

        role_map = _build_role_map(db, pending_gcn_ids, t0)

        # Now compute embeddings
        stats = await compute_embeddings(
            storage,
            bytehouse,
            config,
            access_key=cfg.embedding_access_key,
            role_map=role_map,
        )
        logger.info("[%.0fs] Embedding complete: %s", time.time() - t0, stats)

        # Refresh per-package status
        loop = asyncio.get_running_loop()
        status = await loop.run_in_executor(None, bytehouse.refresh_embedding_status)
        logger.info("[%.0fs] Embedding status refreshed: %s", time.time() - t0, status)

        return stats
    finally:
        bytehouse.close()


async def dry_run() -> dict:
    """Report embedding status without computing anything."""
    from gaia.lkm.storage.config import StorageConfig

    cfg = StorageConfig()
    db = lancedb.connect(cfg.effective_lancedb_uri, storage_options=cfg.storage_options)

    bytehouse, _ = _create_bytehouse(cfg)
    bytehouse.ensure_table()

    try:
        t = db.open_table("global_variable_nodes")
        total = t.count_rows()
        public = t.search().where("visibility = 'public'").select(["id"]).limit(total).to_list()
        existing = bytehouse.get_existing_gcn_ids()

        summary = bytehouse.get_embedding_status_summary()

        return {
            "public_globals": len(public),
            "already_embedded": len(existing),
            "pending": len(public) - len(existing),
            "packages_tracked": summary.get("total_packages", 0),
        }
    finally:
        bytehouse.close()


if __name__ == "__main__":
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    # Resolve log dir to project root (4 levels up from gaia/lkm/pipelines/embedding.py)
    _LOG_DIR = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "logs",
    )
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, f"embedding-{time.strftime('%Y%m%d-%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(_LOG_FILE)],
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger.info("Log file: %s", _LOG_FILE)

    parser = argparse.ArgumentParser(description="Compute embeddings for pending variables")
    parser.add_argument("--dry-run", action="store_true", help="Report status without computing")
    parser.add_argument(
        "--limit", type=int, default=None, help="Only process first N pending (test)"
    )
    args = parser.parse_args()

    async def main():
        if args.dry_run:
            stats = await dry_run()
            print(json.dumps(stats, indent=2))
        else:
            stats = await run_embedding_pipeline(limit=args.limit)
            print(json.dumps(stats, indent=2))

    asyncio.run(main())
