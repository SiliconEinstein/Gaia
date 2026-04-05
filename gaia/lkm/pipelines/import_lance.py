"""Batch import: ByteHouse query → TOS download → extract → integrate.

Processes papers in chunked batches to stay memory-bounded at any scale.

Usage:
    # Fast local import (空表 → add() 快路径, ~100s/1000篇)
    python -m gaia.lkm.pipelines.import_lance \
        --lkm-db-uri ./data/lancedb/lkm-bulk \
        --max-papers 300000

    # Upload local LanceDB to S3 after import
    python -m gaia.lkm.pipelines.import_lance upload \
        --local-path ./data/lancedb/lkm-bulk \
        --s3-uri s3://datainfra-test/gaia_server_test

    # Direct S3 import (slower, for incremental updates)
    python -m gaia.lkm.pipelines.import_lance \
        --lkm-db-uri s3://datainfra-test/gaia_server_test \
        --max-papers 100

    # Dry run
    python -m gaia.lkm.pipelines.import_lance \
        --lkm-db-uri ./data/lancedb/lkm-bulk \
        --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gaia.lkm.core.extract import ExtractionResult, extract
from gaia.lkm.models import ImportStatusRecord
from gaia.lkm.pipelines.extract import run_extract_batch
from gaia.lkm.storage import StorageConfig, StorageManager
from gaia.lkm.storage.source_lance import (
    ByteHouseConfig,
    TOSConfig,
    connect_bytehouse,
    download_paper_xmls,
    merge_xmls,
    search_papers,
)

logger = logging.getLogger("gaia.lkm.pipelines.import_lance")


# ── Checkpoint ──


class Checkpoint:
    """JSON-backed per-paper status tracker with atomic writes.

    For large imports (>100K papers) the JSON file grows but remains manageable
    (~50MB for 1M entries). Writes are batched via flush() to avoid per-paper I/O.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        if path.exists():
            self._data: dict[str, str] = json.loads(path.read_text())
        else:
            self._data = {}
        self._dirty = False

    def status(self, paper_id: str) -> str | None:
        return self._data.get(paper_id)

    def update(self, paper_id: str, status: str) -> None:
        self._data[paper_id] = status
        self._dirty = True

    def flush(self) -> None:
        """Write checkpoint to disk if dirty."""
        if not self._dirty:
            return
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.rename(self._path)
        self._dirty = False

    def pending(self, paper_ids: list[str]) -> list[str]:
        return [p for p in paper_ids if self._data.get(p) != "ingested"]

    @property
    def ingested_count(self) -> int:
        return sum(1 for v in self._data.values() if v == "ingested")


# ── Stats ──


@dataclass
class ImportStats:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: dict[str, str] = field(default_factory=dict)


def _fmt_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m}m"


# ── Graceful shutdown ──

_shutdown_requested = False


def _request_shutdown(signum: int, frame: object) -> None:
    """Signal handler: finish current chunk, then exit."""
    global _shutdown_requested  # noqa: PLW0603
    _shutdown_requested = True
    logger.info("Shutdown requested (signal %d). Will exit after current chunk.", signum)


# ── Checkpoint seeding ──


async def _seed_checkpoint_from_import_status(
    storage: StorageManager,
    checkpoint: Checkpoint,
) -> int:
    """Seed an empty checkpoint from the import_status table in LanceDB.

    Returns the number of papers seeded.
    """
    ingested_ids = await storage.list_ingested_package_ids()
    for pkg_id in ingested_ids:
        # import_status stores "paper:123", checkpoint stores "123"
        paper_id = pkg_id.removeprefix("paper:")
        checkpoint.update(paper_id, "ingested")
    if ingested_ids:
        checkpoint.flush()
    return len(ingested_ids)


# ── Chunk processor ──


async def _process_chunk(
    chunk_ids: list[str],
    tos_config: TOSConfig,
    storage: StorageManager,
    checkpoint: Checkpoint,
    stats: ImportStats,
    batch_started_at: datetime,
) -> None:
    """Download → extract → integrate one chunk of papers."""
    # Download XMLs for this chunk
    downloaded = await download_paper_xmls(tos_config, chunk_ids)

    # Extract
    extraction_results: list[ExtractionResult] = []
    extracted_ids: list[str] = []
    failed_statuses: list[ImportStatusRecord] = []

    for pid in chunk_ids:
        xmls = downloaded.get(pid)
        if xmls is None:
            checkpoint.update(pid, "failed:download")
            failed_statuses.append(
                ImportStatusRecord(
                    package_id=f"paper:{pid}",
                    status="failed:download",
                    started_at=batch_started_at,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            stats.failed += 1
            continue
        try:
            review_xml = merge_xmls(xmls.review_xmls) if xmls.review_xmls else None
            reasoning_xml = merge_xmls(xmls.reasoning_chain_xmls)
            result = extract(review_xml, reasoning_xml, xmls.select_conclusion_xml, pid)
            extraction_results.append(result)
            extracted_ids.append(pid)
        except Exception as e:
            logger.error("Extract failed %s: %s", pid, e)
            checkpoint.update(pid, f"failed:{e.__class__.__name__}")
            failed_statuses.append(
                ImportStatusRecord(
                    package_id=f"paper:{pid}",
                    status=f"failed:{e.__class__.__name__}",
                    error=str(e),
                    started_at=batch_started_at,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            stats.errors[pid] = str(e)
            stats.failed += 1

    # Batch integrate
    if extraction_results:
        batch_result = await run_extract_batch(extraction_results, storage)
        logger.info(
            "Chunk integrate: %d papers → %d new globals, %d new factors, "
            "%d dedup batch, %d dedup existing",
            len(extraction_results),
            batch_result.new_global_variables,
            batch_result.new_global_factors,
            batch_result.dedup_within_batch,
            batch_result.dedup_with_existing,
        )

        status_records = [
            ImportStatusRecord(
                package_id=ext_result.package_id,
                status="ingested",
                variable_count=len(ext_result.local_variables),
                factor_count=len(ext_result.local_factors),
                prior_count=len(ext_result.prior_records),
                factor_param_count=len(ext_result.factor_param_records),
                started_at=batch_started_at,
                completed_at=datetime.now(timezone.utc),
            )
            for ext_result in extraction_results
        ]
        await storage.write_import_status_batch(status_records)
        stats.succeeded += len(extracted_ids)
        for pid in extracted_ids:
            checkpoint.update(pid, "ingested")

    if failed_statuses:
        await storage.write_import_status_batch(failed_statuses)

    # Flush checkpoint after each chunk
    checkpoint.flush()


# ── Orchestrator ──


async def run_batch_import(
    lkm_db_uri: str,
    output_dir: Path,
    *,
    keywords: str | None = None,
    areas: str | None = None,
    bytehouse_config: ByteHouseConfig | None = None,
    tos_config: TOSConfig | None = None,
    max_papers: int | None = None,
    chunk_size: int = 1000,
    min_disk_gb: int = 0,
    dry_run: bool = False,
) -> ImportStats:
    """Batch import papers from ByteHouse/TOS into LKM.

    Processes papers in chunks of `chunk_size` to stay memory-bounded.
    Each chunk: download XMLs → extract → batch integrate → checkpoint.
    Resumable via checkpoint file.
    """
    wall_start = time.monotonic()
    batch_started_at = datetime.now(timezone.utc)
    stats = ImportStats()

    # 1. Search ByteHouse
    if bytehouse_config is None:
        bytehouse_config = ByteHouseConfig.from_env()
    bh_client = connect_bytehouse(bytehouse_config)
    limit = max_papers or 500_000
    papers = search_papers(bh_client, keywords=keywords, areas=areas, limit=limit)
    logger.info(
        "ByteHouse returned %d papers (keywords=%s, areas=%s)", len(papers), keywords, areas
    )

    paper_ids = [str(p["id"]) for p in papers]
    stats.total = len(paper_ids)

    if dry_run:
        for p in papers[:20]:
            print(f"  {p['id']}: {p.get('en_title', '')[:80]}")
        if len(papers) > 20:
            print(f"  ... and {len(papers) - 20} more")
        print(f"\nTotal: {len(papers)} papers (dry run, no import)")
        return stats

    # 2. Filter via checkpoint (seed from import_status if empty)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = Checkpoint(output_dir / "checkpoint.json")
    if checkpoint.ingested_count == 0:
        config = StorageConfig(lancedb_uri=lkm_db_uri)
        storage_for_seed = StorageManager(config)
        await storage_for_seed.initialize()
        seeded = await _seed_checkpoint_from_import_status(storage_for_seed, checkpoint)
        await storage_for_seed.close()
        if seeded:
            logger.info("Seeded checkpoint from import_status: %d papers already ingested", seeded)
    pending = checkpoint.pending(paper_ids)
    stats.skipped = len(paper_ids) - len(pending)
    if stats.skipped:
        logger.info("Skipping %d already-ingested papers", stats.skipped)

    if not pending:
        logger.info("All papers already ingested")
        return stats

    logger.info("Will process %d pending papers in chunks of %d", len(pending), chunk_size)

    # 3. Init resources
    if tos_config is None:
        tos_config = TOSConfig.from_env()
    config = StorageConfig(lancedb_uri=lkm_db_uri)
    storage = StorageManager(config)
    await storage.initialize()

    # 4. Install signal handlers for graceful shutdown
    global _shutdown_requested  # noqa: PLW0603
    _shutdown_requested = False
    prev_sigint = signal.signal(signal.SIGINT, _request_shutdown)
    prev_sigterm = signal.signal(signal.SIGTERM, _request_shutdown)

    # 5. Process in chunks
    n_chunks = (len(pending) + chunk_size - 1) // chunk_size
    for i in range(0, len(pending), chunk_size):
        if _shutdown_requested:
            logger.info("Shutdown requested — stopping before chunk %d", i // chunk_size + 1)
            break

        # Check disk space before each chunk
        if min_disk_gb > 0:
            free_bytes = shutil.disk_usage(Path(lkm_db_uri).resolve().parent).free
            free_gb = free_bytes / (1024**3)
            if free_gb < min_disk_gb:
                logger.info(
                    "Disk space low (%.1fGB < %dGB) — stopping before chunk %d",
                    free_gb,
                    min_disk_gb,
                    i // chunk_size + 1,
                )
                break

        chunk = pending[i : i + chunk_size]
        chunk_num = i // chunk_size + 1
        chunk_start = time.monotonic()

        logger.info(
            "── Chunk %d/%d: %d papers (total progress: %d/%d) ──",
            chunk_num,
            n_chunks,
            len(chunk),
            stats.succeeded + stats.failed + stats.skipped,
            stats.total,
        )

        await _process_chunk(chunk, tos_config, storage, checkpoint, stats, batch_started_at)

        chunk_elapsed = time.monotonic() - chunk_start
        total_elapsed = time.monotonic() - wall_start
        papers_done = stats.succeeded + stats.failed
        if papers_done > 0:
            rate = papers_done / total_elapsed
            remaining = len(pending) - (i + len(chunk))
            eta = remaining / rate if rate > 0 else 0
            logger.info(
                "Chunk %d done in %s | Rate: %.1f papers/s | "
                "ETA for remaining %d: %s | Elapsed: %s",
                chunk_num,
                _fmt_duration(chunk_elapsed),
                rate,
                remaining,
                _fmt_duration(eta),
                _fmt_duration(total_elapsed),
            )

    # 6. Restore signal handlers
    signal.signal(signal.SIGINT, prev_sigint)
    signal.signal(signal.SIGTERM, prev_sigterm)

    # 7. Summary
    await storage.close()
    total_elapsed = time.monotonic() - wall_start
    logger.info(
        "Done in %s: %d succeeded, %d failed, %d skipped (of %d total)",
        _fmt_duration(total_elapsed),
        stats.succeeded,
        stats.failed,
        stats.skipped,
        stats.total,
    )
    return stats


# ── Upload local → S3 ──


_UPLOAD_BATCH_SIZE = 50_000  # rows per upload batch to avoid OOM


def upload_local_to_s3(local_path: str, s3_uri: str, *, append: bool = False) -> None:
    """Upload a local LanceDB directory to S3 by streaming table data in batches.

    Reads each table in batches of _UPLOAD_BATCH_SIZE rows to stay memory-bounded,
    even for tables with millions of rows.

    Args:
        append: If True, append to existing remote tables (safe when checkpoint
                guarantees no duplicate data between rounds).
    """
    import lancedb as _lancedb

    from gaia.lkm.storage.config import StorageConfig

    config = StorageConfig(lancedb_uri=s3_uri)
    opts = config.storage_options

    local_db = _lancedb.connect(local_path)
    remote_db = _lancedb.connect(s3_uri, storage_options=opts) if opts else _lancedb.connect(s3_uri)

    local_tables = local_db.list_tables().tables
    remote_tables = set(remote_db.list_tables().tables)

    for table_name in local_tables:
        local_table = local_db.open_table(table_name)
        row_count = local_table.count_rows()
        if row_count == 0:
            logger.info("Skipping empty table: %s", table_name)
            continue

        if table_name in remote_tables and not append:
            remote_table = remote_db.open_table(table_name)
            existing = remote_table.count_rows()
            if existing > 0:
                logger.warning(
                    "Remote table %s already has %d rows. "
                    "Use --append to add data, or clear remote first. Skipping.",
                    table_name,
                    existing,
                )
                continue

        logger.info(
            "Uploading %s: %d rows in batches of %d...", table_name, row_count, _UPLOAD_BATCH_SIZE
        )
        uploaded = 0
        offset = 0
        while offset < row_count:
            batch_table = local_table.search().offset(offset).limit(_UPLOAD_BATCH_SIZE).to_arrow()
            if batch_table.num_rows == 0:
                break
            if table_name not in remote_tables:
                remote_db.create_table(table_name, batch_table)
                remote_tables.add(table_name)
            else:
                remote_db.open_table(table_name).add(batch_table)
            uploaded += batch_table.num_rows
            offset += _UPLOAD_BATCH_SIZE
            logger.info("  %s: %d/%d rows uploaded", table_name, uploaded, row_count)

        logger.info("Uploaded %s ✓ (%d rows)", table_name, uploaded)

    logger.info("Upload complete: %d tables", len(local_tables))


# ── CLI ──


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch import papers from ByteHouse/TOS into LKM")
    sub = parser.add_subparsers(dest="command")

    # ── import: args on main parser so bare invocation works ──
    parser.add_argument(
        "--keywords",
        default=None,
        help="Token search on en_title (e.g. 'nuclear fusion')",
    )
    parser.add_argument(
        "--areas",
        default=None,
        help="Filter by areas partition (e.g. 'Physics')",
    )
    parser.add_argument(
        "--lkm-db-uri",
        default=None,
        help="Target LanceDB URI (local path for fast import, or s3://...)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output/import"),
        help="Output directory for checkpoint and logs (default: ./output/import)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Papers per chunk (download+extract+integrate) (default: 1000)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Limit number of papers to import",
    )
    parser.add_argument(
        "--min-disk-gb",
        type=int,
        default=10,
        help="Stop importing when free disk drops below this (GB, default: 10, 0=disable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query and print matching papers without importing",
    )

    # ── upload subcommand ──
    p_upload = sub.add_parser("upload", help="Upload local LanceDB to S3")
    p_upload.add_argument(
        "--local-path",
        required=True,
        help="Local LanceDB path (e.g. ./data/lancedb/lkm-bulk)",
    )
    p_upload.add_argument(
        "--s3-uri",
        required=True,
        help="Target S3 URI (e.g. s3://datainfra-test/gaia_server_test)",
    )
    p_upload.add_argument(
        "--append",
        action="store_true",
        help="Append to existing remote tables (safe with checkpoint-based dedup)",
    )

    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    if args.command == "upload":
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        upload_local_to_s3(args.local_path, args.s3_uri, append=args.append)
        return

    # command is None or "import" → run import
    if not args.lkm_db_uri:
        parser.error("--lkm-db-uri is required for import")

    from gaia.lkm.logging import configure_logging

    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(level="INFO", log_file=args.output_dir / "import.log")

    stats = asyncio.run(
        run_batch_import(
            lkm_db_uri=args.lkm_db_uri,
            output_dir=args.output_dir,
            keywords=args.keywords,
            areas=args.areas,
            chunk_size=args.chunk_size,
            max_papers=args.max_papers,
            min_disk_gb=args.min_disk_gb,
            dry_run=args.dry_run,
        )
    )

    print(f"\nImport complete: {stats.succeeded}/{stats.total} succeeded, {stats.failed} failed")
    if stats.errors:
        print(f"Errors ({len(stats.errors)}):")
        for pid, err in list(stats.errors.items())[:20]:
            print(f"  {pid}: {err}")


if __name__ == "__main__":
    main()
