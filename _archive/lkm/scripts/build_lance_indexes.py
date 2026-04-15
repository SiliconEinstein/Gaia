"""Build scalar indexes on LanceDB tables (one-off maintenance script).

Indexes needed for M6 embedding pipeline:
- global_factor_nodes.conclusion (for role_map IN queries)
- global_variable_nodes.visibility (for public filter)
- All others from LanceContentStore._ensure_indexes()

Usage: python scripts/build_lance_indexes.py
"""

from __future__ import annotations

import logging
import os
import time

import lancedb
from dotenv import load_dotenv

load_dotenv()

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"build-indexes-{time.strftime('%Y%m%d-%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(_LOG_FILE)],
    force=True,
)
logger = logging.getLogger(__name__)
logger.info("Log file: %s", _LOG_FILE)


def main():
    from gaia.lkm.storage.config import StorageConfig

    cfg = StorageConfig()
    logger.info("Connecting to LanceDB: %s", cfg.effective_lancedb_uri)
    db = lancedb.connect(cfg.effective_lancedb_uri, storage_options=cfg.storage_options)

    # (table, column) pairs
    indexes = [
        ("global_variable_nodes", "id"),
        ("global_variable_nodes", "visibility"),
        ("global_variable_nodes", "content_hash"),
        ("global_factor_nodes", "id"),
        ("global_factor_nodes", "conclusion"),
        ("local_variable_nodes", "id"),
        ("local_variable_nodes", "content_hash"),
        ("local_factor_nodes", "id"),
    ]

    t0 = time.time()
    for table_name, column in indexes:
        try:
            logger.info("[%.0fs] Creating index on %s.%s ...", time.time() - t0, table_name, column)
            table = db.open_table(table_name)
            table.create_scalar_index(column, replace=True)
            logger.info("[%.0fs] DONE: %s.%s", time.time() - t0, table_name, column)
        except Exception as e:
            logger.warning("[%.0fs] FAILED %s.%s: %s", time.time() - t0, table_name, column, e)

    logger.info("[%.0fs] All done", time.time() - t0)


if __name__ == "__main__":
    main()
