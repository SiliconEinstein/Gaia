"""Deduplicate S3 LanceDB tables in place.

Removes duplicate rows by primary key, keeping the first occurrence.
Also dedupes the nested local_members list inside global_variable_nodes.

Usage:
    uv run python scripts/dedupe-s3-lance.py \
        --s3-uri s3://datainfra-test/gaia_server_test \
        [--dry-run]

SAFETY:
    - Stop all import/upload processes before running this!
    - Requires exclusive access to the S3 LanceDB.
    - Drops and recreates tables — plan for downtime.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass

import lancedb
import pyarrow as pa
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TableSpec:
    name: str
    primary_key: str


# Tables with row-level duplicates (dedupe by primary key)
DUPE_TABLES = [
    TableSpec("import_status", "package_id"),
    TableSpec("param_sources", "source_id"),
    TableSpec("local_variable_nodes", "id"),
    TableSpec("local_factor_nodes", "id"),
    TableSpec("canonical_bindings", "local_id"),
]

# Tables with no row dupes but nested list dupes in local_members
GLOBAL_TABLE = "global_variable_nodes"


def connect_s3(uri: str) -> lancedb.DBConnection:
    ak = os.environ["TOS_ACCESS_KEY"]
    sk = os.environ["TOS_SECRET_KEY"]
    ep = os.environ["TOS_ENDPOINT"]
    bucket = uri.split("/")[2]
    opts = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "endpoint": f"https://{bucket}.{ep}",
        "virtual_hosted_style_request": "true",
    }
    return lancedb.connect(uri, storage_options=opts)


def dedupe_table(db: lancedb.DBConnection, spec: TableSpec, *, dry_run: bool) -> None:
    table = db.open_table(spec.name)
    total = table.count_rows()
    logger.info("── %s ──", spec.name)
    logger.info("  Reading %d rows...", total)

    # Read full table
    df = table.to_pandas()
    before = len(df)

    # Dedupe, keep first
    df = df.drop_duplicates(subset=[spec.primary_key], keep="first")
    after = len(df)
    removed = before - after

    logger.info(
        "  Deduped: %d → %d rows (%d removed, %.1f%%)",
        before,
        after,
        removed,
        100 * removed / before if before else 0,
    )

    if removed == 0:
        logger.info("  Already clean, skipping rewrite")
        return

    if dry_run:
        logger.info("  [DRY RUN] Would rewrite table with %d rows", after)
        return

    # Get original schema
    schema = table.schema

    # Convert back to arrow
    arrow_table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)

    # Drop and recreate
    logger.info("  Dropping old table...")
    db.drop_table(spec.name)

    logger.info("  Creating new table with %d rows...", after)
    db.create_table(spec.name, arrow_table)

    # Verify
    new_total = db.open_table(spec.name).count_rows()
    if new_total != after:
        logger.error("  ✗ Row count mismatch: expected %d, got %d", after, new_total)
        sys.exit(1)
    logger.info("  ✓ %s: %d rows (was %d)", spec.name, new_total, before)


def dedupe_global_members(db: lancedb.DBConnection, *, dry_run: bool) -> None:
    """Dedupe the local_members list inside each global_variable_nodes row."""
    table = db.open_table(GLOBAL_TABLE)
    total = table.count_rows()
    logger.info("── %s (nested local_members dedupe) ──", GLOBAL_TABLE)
    logger.info("  Reading %d rows...", total)

    df = table.to_pandas()

    dirty_count = 0
    total_refs_before = 0
    total_refs_after = 0

    def _dedupe_members(raw: str) -> str:
        nonlocal dirty_count, total_refs_before, total_refs_after
        if not raw:
            return raw
        try:
            members = json.loads(raw)
        except Exception:
            return raw
        before = len(members)
        seen = set()
        deduped = []
        for m in members:
            lid = m.get("local_id")
            if lid in seen:
                continue
            seen.add(lid)
            deduped.append(m)
        after = len(deduped)
        total_refs_before += before
        total_refs_after += after
        if after < before:
            dirty_count += 1
            return json.dumps(deduped)
        return raw

    df["local_members"] = df["local_members"].map(_dedupe_members)

    logger.info("  Rows with duplicate members: %d", dirty_count)
    logger.info(
        "  Total local_id refs: %d → %d (%d removed)",
        total_refs_before,
        total_refs_after,
        total_refs_before - total_refs_after,
    )

    if dirty_count == 0:
        logger.info("  Already clean, skipping rewrite")
        return

    if dry_run:
        logger.info("  [DRY RUN] Would rewrite %s with deduped members", GLOBAL_TABLE)
        return

    schema = table.schema
    arrow_table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)

    logger.info("  Dropping old table...")
    db.drop_table(GLOBAL_TABLE)

    logger.info("  Creating new table with %d rows...", len(df))
    db.create_table(GLOBAL_TABLE, arrow_table)

    new_total = db.open_table(GLOBAL_TABLE).count_rows()
    if new_total != len(df):
        logger.error("  ✗ Row count mismatch: expected %d, got %d", len(df), new_total)
        sys.exit(1)
    logger.info("  ✓ %s: %d rows (local_members deduped)", GLOBAL_TABLE, new_total)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-uri", required=True, help="S3 LanceDB URI")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    parser.add_argument(
        "--skip-members",
        action="store_true",
        help="Skip global_variable_nodes.local_members dedupe (faster)",
    )
    args = parser.parse_args()

    load_dotenv()

    logger.info("Connecting to %s", args.s3_uri)
    db = connect_s3(args.s3_uri)

    if not args.dry_run:
        logger.warning("=" * 60)
        logger.warning("THIS WILL DROP AND RECREATE TABLES IN PRODUCTION S3!")
        logger.warning("Make sure no import/upload is running.")
        logger.warning("=" * 60)
        reply = input("Type 'yes' to continue: ")
        if reply != "yes":
            logger.info("Aborted")
            return

    for spec in DUPE_TABLES:
        dedupe_table(db, spec, dry_run=args.dry_run)

    if not args.skip_members:
        dedupe_global_members(db, dry_run=args.dry_run)

    logger.info("Done")


if __name__ == "__main__":
    main()
