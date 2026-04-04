"""CLI script to run M6 semantic discovery.

Usage: python -m gaia.lkm.scripts.discovery [--threshold 0.85] [--dry-run]
"""

import asyncio
import json
import logging
import sys

from gaia.lkm.models.discovery import DiscoveryConfig
from gaia.lkm.storage import StorageConfig, StorageManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(threshold: float = 0.85, dry_run: bool = False) -> None:
    config = StorageConfig()
    storage = StorageManager(config)
    await storage.initialize()

    bytehouse = storage.create_bytehouse_store()
    if bytehouse is None:
        logger.error("ByteHouse not configured — set BYTEHOUSE_HOST env var")
        sys.exit(1)
    bytehouse.ensure_table()

    discovery_config = DiscoveryConfig(similarity_threshold=threshold)

    if dry_run:
        ids = await storage.list_all_public_global_ids()
        existing = await asyncio.get_running_loop().run_in_executor(
            None, bytehouse.get_existing_gcn_ids
        )
        logger.info(
            "Public globals: %d, already embedded: %d, pending: %d",
            len(ids),
            len(existing),
            len(ids) - len(existing),
        )
        return

    from gaia.lkm.core.discovery import run_semantic_discovery

    result = await run_semantic_discovery(
        storage,
        bytehouse,
        discovery_config,
        access_key=config.embedding_access_key,
    )

    print(
        json.dumps(
            {
                "total_clusters": result.stats.total_clusters,
                "total_scanned": result.stats.total_variables_scanned,
                "embeddings_computed": result.stats.total_embeddings_computed,
                "elapsed_seconds": result.stats.elapsed_seconds,
                "cluster_sizes": result.stats.cluster_size_distribution,
            },
            indent=2,
        )
    )

    for c in result.clusters[:5]:
        print(
            f"\nCluster {c.cluster_id} ({c.node_type}): {len(c.gcn_ids)} nodes, "
            f"avg_sim={c.avg_similarity:.3f}"
        )
        for gid in c.gcn_ids[:3]:
            print(f"  - {gid}")

    await storage.close()
    bytehouse.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run M6 semantic discovery")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(threshold=args.threshold, dry_run=args.dry_run))
