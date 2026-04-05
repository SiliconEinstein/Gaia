"""Pipeline: M6 semantic discovery — embedding + FAISS clustering.

Thin adapter over core/discovery. Handles ByteHouse setup and teardown.

Usage: python -m gaia.lkm.pipelines.discovery [--threshold 0.85] [--dry-run]
"""

from __future__ import annotations

import asyncio
import json
import logging

from gaia.lkm.core.discovery import run_semantic_discovery
from gaia.lkm.models.discovery import ClusteringResult, DiscoveryConfig
from gaia.lkm.storage import StorageConfig, StorageManager

logger = logging.getLogger(__name__)


async def run_discovery_pipeline(
    storage: StorageManager,
    config: DiscoveryConfig | None = None,
) -> ClusteringResult:
    """Run the full semantic discovery pipeline.

    1. Create and initialize ByteHouse store
    2. Run embedding computation + FAISS clustering
    3. Results are auto-saved to ByteHouse by run_semantic_discovery()

    Args:
        storage: Initialized StorageManager.
        config: Discovery configuration. Uses defaults if None.

    Returns:
        ClusteringResult with all clusters and stats.
    """
    storage_config = storage._config
    bytehouse = storage.create_bytehouse_store()
    if bytehouse is None:
        raise RuntimeError("ByteHouse not configured — set BYTEHOUSE_HOST env var")

    bytehouse.ensure_table()
    bytehouse.ensure_discovery_tables()

    if config is None:
        config = DiscoveryConfig()

    try:
        result = await run_semantic_discovery(
            storage,
            bytehouse,
            config,
            access_key=storage_config.embedding_access_key,
        )
        return result
    finally:
        bytehouse.close()


async def dry_run(storage: StorageManager) -> dict:
    """Report embedding status without running discovery.

    Returns dict with counts: {public_globals, already_embedded, pending}.
    """
    bytehouse = storage.create_bytehouse_store()
    if bytehouse is None:
        raise RuntimeError("ByteHouse not configured — set BYTEHOUSE_HOST env var")

    bytehouse.ensure_table()

    try:
        ids = await storage.list_all_public_global_ids()
        loop = asyncio.get_running_loop()
        existing = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)
        return {
            "public_globals": len(ids),
            "already_embedded": len(existing),
            "pending": len(ids) - len(existing),
        }
    finally:
        bytehouse.close()


async def main(threshold: float = 0.85, is_dry_run: bool = False) -> None:
    """CLI entry point."""
    config = StorageConfig()
    storage = StorageManager(config)
    await storage.initialize()

    try:
        if is_dry_run:
            stats = await dry_run(storage)
            logger.info(
                "Public globals: %d, already embedded: %d, pending: %d",
                stats["public_globals"],
                stats["already_embedded"],
                stats["pending"],
            )
            return

        discovery_config = DiscoveryConfig(similarity_threshold=threshold)
        result = await run_discovery_pipeline(storage, discovery_config)

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
    finally:
        await storage.close()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run M6 semantic discovery")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(threshold=args.threshold, is_dry_run=args.dry_run))
