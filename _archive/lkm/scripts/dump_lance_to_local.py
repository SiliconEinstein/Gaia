"""Dump every LKM table from the remote LanceDB (TOS/S3) to a local path.

Phase 3 step A of docs/plans/2026-04-09-bytehouse-as-primary-store.md.

Rationale: we want to run the ByteHouse backfill multiple times without
paying the remote-S3 read cost on every iteration. This script copies
the raw LanceDB dataset from S3/TOS to a local directory, preserving
lance's on-disk layout so that ``lancedb.connect(local_path)`` sees the
same data.

Usage::

    uv run --with pylance python scripts/dump_lance_to_local.py \
        --dest ~/gaia-lance-snapshot/gaia_server_test

Run in background — it's a long I/O-bound job (12–15 GB over the WAN).
Requires pylance (the Python binding on top of the Rust lance library),
which is *not* a default project dependency. Use ``uv run --with pylance``.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

import lance
import lancedb

from gaia.lkm.storage.config import StorageConfig

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _setup_logging() -> Path:
    log_file = _LOG_DIR / f"dump-lance-to-local-{time.strftime('%Y%m%d-%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
        force=True,
    )
    logging.info("Log file: %s", log_file)
    return log_file


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _dump_table(
    *,
    name: str,
    src_uri_base: str,
    dest_uri_base: str,
    storage_options: dict[str, str] | None,
    batch_size: int,
    overwrite: bool,
) -> tuple[int, float]:
    src_uri = f"{src_uri_base.rstrip('/')}/{name}.lance"
    dest_path = Path(dest_uri_base).expanduser() / f"{name}.lance"

    if dest_path.exists() and not overwrite:
        # Already dumped — compare row count. If local matches remote, skip.
        try:
            local_ds = lance.dataset(str(dest_path))
            local_n = local_ds.count_rows()
        except Exception:
            local_n = -1
        try:
            src_ds = lance.dataset(src_uri, storage_options=storage_options)
            remote_n = src_ds.count_rows()
        except Exception as exc:
            logging.warning("[%s] couldn't check remote: %s; skipping", name, exc)
            return 0, 0.0
        if local_n == remote_n and local_n >= 0:
            logging.info(
                "[%s] SKIP (already present): local=%d == remote=%d",
                name,
                local_n,
                remote_n,
            )
            return local_n, 0.0
        logging.info("[%s] REDO (mismatch or corrupt): local=%d remote=%d", name, local_n, remote_n)

    logging.info("[%s] opening remote %s", name, src_uri)
    src_ds = lance.dataset(src_uri, storage_options=storage_options)
    total = src_ds.count_rows()
    schema = src_ds.schema
    logging.info("[%s] remote has %d rows, schema has %d fields", name, total, len(schema))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "overwrite" if overwrite else "create"
    if dest_path.exists() and overwrite:
        import shutil

        shutil.rmtree(dest_path)

    t0 = time.time()

    # Streaming reader: iterator of RecordBatch across fragments
    reader = src_ds.to_batches(batch_size=batch_size)
    lance.write_dataset(
        reader,
        str(dest_path),
        schema=schema,
        mode=mode,
        max_rows_per_file=1_000_000,
    )

    elapsed = time.time() - t0

    # Verify row count matches
    local_ds = lance.dataset(str(dest_path))
    local_n = local_ds.count_rows()
    size = _dir_size(dest_path)
    marker = "✓" if local_n == total else "✗ MISMATCH"
    logging.info(
        "[%s] DONE %s %d rows in %.1fs (local size %s)",
        name,
        marker,
        local_n,
        elapsed,
        _format_bytes(size),
    )
    return local_n, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--dest",
        default="~/gaia-lance-snapshot/gaia_server_test",
        help="Local directory root for the dumped lance dataset.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="RecordBatch size for the streaming copy (default: 50000).",
    )
    parser.add_argument(
        "--tables",
        default=None,
        help="Comma-separated lance table names to dump (default: all).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and re-dump tables that already exist locally.",
    )
    args = parser.parse_args()

    log_file = _setup_logging()
    logging.info("Args: %s", args)

    config = StorageConfig()
    src_uri_base = config.effective_lancedb_uri
    dest_base = Path(os.path.expanduser(args.dest))
    logging.info("Source: %s", src_uri_base)
    logging.info("Dest:   %s", dest_base)
    dest_base.mkdir(parents=True, exist_ok=True)

    # Determine storage options (TOS / S3), augmented with generous
    # timeouts and retries. TOS has been seen to time out range reads
    # during long sustained transfers; defaults (~30s, 3 retries) are
    # too tight for this workload.
    storage_options = dict(config.storage_options or {})
    storage_options.setdefault("request_timeout", "300s")
    storage_options.setdefault("connect_timeout", "60s")
    storage_options.setdefault("aws_request_timeout", "300s")
    storage_options.setdefault("aws_connect_timeout", "60s")
    if storage_options:
        masked = {k: ("***" if "key" in k else v) for k, v in storage_options.items()}
        logging.info("Storage options: %s", masked)

    # Enumerate tables through lancedb (works against remote TOS)
    src_db = lancedb.connect(src_uri_base, storage_options=storage_options)
    all_tables = sorted(src_db.table_names())
    if args.tables:
        requested = [t.strip() for t in args.tables.split(",") if t.strip()]
        missing = set(requested) - set(all_tables)
        if missing:
            logging.error("Unknown tables: %s", missing)
            raise SystemExit(2)
        tables = requested
    else:
        tables = all_tables
    logging.info("Dumping %d tables: %s", len(tables), tables)

    summary: list[tuple[str, int, float]] = []
    grand_t0 = time.time()
    for name in tables:
        try:
            n, secs = _dump_table(
                name=name,
                src_uri_base=src_uri_base,
                dest_uri_base=str(dest_base),
                storage_options=storage_options,
                batch_size=args.batch_size,
                overwrite=args.overwrite,
            )
            summary.append((name, n, secs))
        except Exception as exc:
            logging.exception("[%s] FAILED: %s", name, exc)
            summary.append((name, -1, 0.0))

    grand_elapsed = time.time() - grand_t0
    logging.info("=== Summary ===")
    total_rows = 0
    for name, n, secs in summary:
        marker = "✓" if n >= 0 else "✗"
        logging.info("  %s %-24s %12s rows  %8.1fs", marker, name, n, secs)
        if n > 0:
            total_rows += n
    total_size = _dir_size(dest_base)
    logging.info(
        "TOTAL: %d rows, %s, %.1fs (%.1f min)",
        total_rows,
        _format_bytes(total_size),
        grand_elapsed,
        grand_elapsed / 60,
    )
    logging.info("Log file: %s", log_file)


if __name__ == "__main__":
    main()
