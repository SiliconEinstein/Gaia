"""Run full M6 discovery: embed all pending variables + cluster + save.

Calls embedding pipeline then clustering pipeline sequentially.

Usage: python scripts/run_full_discovery.py
       python scripts/run_full_discovery.py --embedding-only
       python scripts/run_full_discovery.py --cluster-only
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"discovery-{time.strftime('%Y%m%d-%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_FILE),
    ],
    force=True,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main(embedding_only: bool = False, cluster_only: bool = False) -> None:
    t0 = time.time()

    if not cluster_only:
        from gaia.lkm.pipelines.embedding import run_embedding_pipeline

        logger.info("=== Phase 1: Embedding ===")
        emb_stats = await run_embedding_pipeline()
        logger.info("Embedding done in %.0fs: %s", time.time() - t0, emb_stats)

    if not embedding_only:
        from gaia.lkm.pipelines.cluster import run_clustering

        logger.info("=== Phase 2: Clustering ===")
        t1 = time.time()
        result = run_clustering()
        logger.info("Clustering done in %.0fs", time.time() - t1)

        print(
            json.dumps(
                {
                    "total_clusters": result.stats.total_clusters,
                    "total_scanned": result.stats.total_variables_scanned,
                    "elapsed_seconds": result.stats.elapsed_seconds,
                    "cluster_sizes": result.stats.cluster_size_distribution,
                },
                indent=2,
            )
        )

    logger.info("Total elapsed: %.0fs", time.time() - t0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run M6 embedding + clustering")
    parser.add_argument("--embedding-only", action="store_true", help="Only compute embeddings")
    parser.add_argument("--cluster-only", action="store_true", help="Only run clustering")
    args = parser.parse_args()
    asyncio.run(main(embedding_only=args.embedding_only, cluster_only=args.cluster_only))
