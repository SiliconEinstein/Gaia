"""Batch import: Lance query → TOS download → extract → integrate.

Usage:
    python -m gaia.lkm.pipelines.import_lance \
        --categories cond-mat.stat-mech \
        --lkm-db-uri s3://bucket/lkm \
        --output-dir ./output/stat-mech \
        --max-papers 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from datetime import datetime, timezone

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

logger = logging.getLogger(__name__)


# ── Checkpoint ──


class Checkpoint:
    """JSON-backed per-paper status tracker with atomic writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        if path.exists():
            self._data: dict[str, str] = json.loads(path.read_text())
        else:
            self._data = {}

    def status(self, paper_id: str) -> str | None:
        return self._data.get(paper_id)

    def update(self, paper_id: str, status: str) -> None:
        self._data[paper_id] = status
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.rename(self._path)

    def pending(self, paper_ids: list[str]) -> list[str]:
        return [p for p in paper_ids if self._data.get(p) != "ingested"]


# ── Stats ──


@dataclass
class ImportStats:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: dict[str, str] = field(default_factory=dict)


# ── Orchestrator ──


async def run_batch_import(
    lkm_db_uri: str,
    output_dir: Path,
    *,
    keywords: str | None = None,
    areas: str | None = None,
    bytehouse_config: ByteHouseConfig | None = None,
    tos_config: TOSConfig | None = None,
    concurrency: int = 10,
    max_papers: int | None = None,
    dry_run: bool = False,
) -> ImportStats:
    """Batch import papers from ByteHouse/TOS into LKM.

    1. Search ByteHouse paper_data.paper_metadata
    2. Filter via checkpoint → skip already ingested
    3. Batch download XMLs from TOS (in-memory)
    4. Init shared StorageManager (target LKM)
    5. For each paper (semaphore limited):
       merge XMLs → run_extract() → checkpoint
    6. Return summary stats
    """
    batch_started_at = datetime.now(timezone.utc)
    failed_statuses: list[ImportStatusRecord] = []
    stats = ImportStats()

    # 1. Search ByteHouse
    if bytehouse_config is None:
        bytehouse_config = ByteHouseConfig.from_env()
    bh_client = connect_bytehouse(bytehouse_config)
    papers = search_papers(bh_client, keywords=keywords, areas=areas, limit=max_papers or 1000)
    logger.info(
        "ByteHouse returned %d papers (keywords=%s, areas=%s)", len(papers), keywords, areas
    )

    paper_ids = [str(p["id"]) for p in papers]
    stats.total = len(paper_ids)

    if dry_run:
        for p in papers[:10]:
            print(f"  {p['id']}: {p.get('en_title', '')[:80]}")
        print(f"\nTotal: {len(papers)} papers (dry run, no import)")
        return stats

    # 2. Filter via checkpoint
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = Checkpoint(output_dir / "checkpoint.json")
    pending = checkpoint.pending(paper_ids)
    stats.skipped = len(paper_ids) - len(pending)
    if stats.skipped:
        logger.info("Skipping %d already-ingested papers", stats.skipped)

    if not pending:
        logger.info("All papers already ingested")
        return stats

    # 3. Batch download XMLs from TOS
    if tos_config is None:
        tos_config = TOSConfig.from_env()
    logger.info("Downloading XMLs for %d papers...", len(pending))
    downloaded = await download_paper_xmls(tos_config, pending)

    # 4. Init target StorageManager (picks up TOS_* creds from env)
    config = StorageConfig(lancedb_uri=lkm_db_uri)
    storage = StorageManager(config)
    await storage.initialize()

    # 5. Extract all papers (pure computation, safe to parallelize)
    extraction_results: list[ExtractionResult] = []
    extracted_ids: list[str] = []
    for i, pid in enumerate(pending):
        if i > 0 and i % 100 == 0:
            logger.info("Extraction progress: %d/%d papers", i, len(pending))
        xmls = downloaded.get(pid)
        if xmls is None:
            logger.warning("No XMLs downloaded for %s, skipping", pid)
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

    # 6. Batch integrate (dedup within batch + against existing globals)
    if extraction_results:
        logger.info("Integrating %d papers (batch dedup)...", len(extraction_results))
        batch_result = await run_extract_batch(extraction_results, storage)
        logger.info(
            "Batch integrate: %d new globals, %d new factors, "
            "%d dedup within batch, %d dedup with existing",
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
        logger.info("Wrote %d import_status records", len(status_records))
        stats.succeeded = len(extracted_ids)
        for pid in extracted_ids:
            checkpoint.update(pid, "ingested")

    if failed_statuses:
        await storage.write_import_status_batch(failed_statuses)
        logger.info("Wrote %d failed import_status records", len(failed_statuses))

    # 7. Summary
    await storage.close()
    logger.info(
        "Done: %d succeeded, %d failed, %d skipped (of %d total)",
        stats.succeeded,
        stats.failed,
        stats.skipped,
        stats.total,
    )
    return stats


# ── CLI ──


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch import papers from Lance/TOS into LKM")
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
        required=True,
        help="Target LKM LanceDB URI (local path or s3://...)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output/import"),
        help="Output directory for checkpoint (default: ./output/import)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent extract+integrate tasks (default: 10)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Limit number of papers to import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query and print matching papers without importing",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    from gaia.lkm.logging import configure_logging

    configure_logging(level="INFO", log_file=args.output_dir / "import.log")

    stats = asyncio.run(
        run_batch_import(
            lkm_db_uri=args.lkm_db_uri,
            output_dir=args.output_dir,
            keywords=args.keywords,
            areas=args.areas,
            concurrency=args.concurrency,
            max_papers=args.max_papers,
            dry_run=args.dry_run,
        )
    )

    print(f"\nImport complete: {stats.succeeded}/{stats.total} succeeded")
    if stats.errors:
        print(f"Errors ({len(stats.errors)}):")
        for pid, err in list(stats.errors.items())[:10]:
            print(f"  {pid}: {err}")


if __name__ == "__main__":
    main()
