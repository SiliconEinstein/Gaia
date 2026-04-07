"""Backfill Neo4j from existing LanceDB global graph data.

Reads all global variables and factors from LanceDB, writes them
to Neo4j in batches. Idempotent — safe to re-run (MERGE semantics).

Usage:
    python -m gaia.lkm.pipelines.backfill_neo4j
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from argparse import ArgumentParser

import neo4j

from gaia.lkm.storage.config import StorageConfig
from gaia.lkm.storage.lance_store import LanceContentStore
from gaia.lkm.storage.neo4j_store import Neo4jGraphStore
from gaia.lkm.storage._serialization import row_to_global_factor, row_to_global_variable

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def backfill(config: StorageConfig, *, dry_run: bool = False) -> dict[str, int]:
    """Read LanceDB globals → write to Neo4j. Returns counts."""
    lance = LanceContentStore(
        config.effective_lancedb_uri,
        storage_options=config.storage_options,
    )
    await lance.initialize()

    # Read all global variables (no visibility filter)
    table_vars = lance._db.open_table("global_variable_nodes")
    all_var_rows = table_vars.search().limit(500_000).to_list()
    variables = [row_to_global_variable(r) for r in all_var_rows]
    logger.info("Read %d global variables from LanceDB", len(variables))

    # Read all global factors
    table_facs = lance._db.open_table("global_factor_nodes")
    all_fac_rows = table_facs.search().limit(500_000).to_list()
    factors = [row_to_global_factor(r) for r in all_fac_rows]
    logger.info("Read %d global factors from LanceDB", len(factors))

    if dry_run:
        logger.info("Dry run — skipping Neo4j writes")
        return {"variables": len(variables), "factors": len(factors)}

    # Connect to Neo4j
    driver = neo4j.AsyncGraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password),
    )
    graph = Neo4jGraphStore(driver, database=config.neo4j_database)
    await graph.initialize_schema()

    # Write in batches
    for i in range(0, len(variables), BATCH_SIZE):
        batch = variables[i : i + BATCH_SIZE]
        await graph.write_variables(batch)
        logger.info("Wrote variables %d-%d / %d", i, i + len(batch), len(variables))

    for i in range(0, len(factors), BATCH_SIZE):
        batch = factors[i : i + BATCH_SIZE]
        await graph.write_factors(batch)
        await graph.write_edges([], batch)
        logger.info("Wrote factors + edges %d-%d / %d", i, i + len(batch), len(factors))

    # Verify
    counts = await graph.count_nodes()
    logger.info("Neo4j after backfill: %s", counts)

    await graph.close()
    return {"variables": len(variables), "factors": len(factors), "neo4j": counts}


def main() -> None:
    parser = ArgumentParser(description="Backfill Neo4j from LanceDB")
    parser.add_argument("--dry-run", action="store_true", help="Read LanceDB only, skip writes")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    _LOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
    )
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, f"backfill_neo4j-{time.strftime('%Y%m%d-%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(_LOG_FILE),
        ],
    )

    config = StorageConfig()
    logger.info(
        "LanceDB: %s → Neo4j: %s (db=%s)",
        config.effective_lancedb_uri,
        config.neo4j_uri,
        config.neo4j_database,
    )

    result = asyncio.run(backfill(config, dry_run=args.dry_run))
    print(f"\nBackfill complete: {result}")


if __name__ == "__main__":
    main()
