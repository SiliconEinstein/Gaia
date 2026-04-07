"""Pipeline: M6 semantic discovery — embedding + FAISS clustering.

Two modes:
- full: compute embeddings (needs LanceDB + ByteHouse) then cluster
- cluster-only: just cluster from existing ByteHouse embeddings (fast, no LanceDB)

Usage:
    python -m gaia.lkm.pipelines.discovery                     # full
    python -m gaia.lkm.pipelines.discovery --cluster-only       # cluster-only
    python -m gaia.lkm.pipelines.discovery --dry-run            # check status
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone

from gaia.lkm.models.discovery import (
    ClusteringResult,
    ClusteringStats,
    DiscoveryConfig,
    SemanticCluster,
)

logger = logging.getLogger(__name__)

_NODE_TYPES = ("claim", "question", "setting", "action")


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


async def run_discovery_pipeline(
    storage,
    config: DiscoveryConfig | None = None,
) -> ClusteringResult:
    """Full pipeline: compute embeddings + cluster + save.

    Requires initialized StorageManager (LanceDB + optional Neo4j).
    Use this when new variables have been integrated and need embedding.
    """
    from gaia.lkm.core.discovery import run_semantic_discovery

    storage_config = storage._config
    bytehouse, _ = _create_bytehouse(storage_config)
    bytehouse.ensure_table()
    bytehouse.ensure_discovery_tables()

    if config is None:
        config = DiscoveryConfig()

    try:
        return await run_semantic_discovery(
            storage,
            bytehouse,
            config,
            access_key=storage_config.embedding_access_key,
        )
    finally:
        bytehouse.close()


def run_cluster_only(
    config: DiscoveryConfig | None = None,
) -> ClusteringResult:
    """Cluster-only mode: load embeddings from ByteHouse, cluster, save.

    No LanceDB or Neo4j needed. Fast (~15s for 10k embeddings).
    Use this when embeddings are already computed and you want to
    re-cluster with different parameters.
    """
    from gaia.lkm.core._clustering import cluster_embeddings

    t0 = time.monotonic()
    if config is None:
        config = DiscoveryConfig()

    bytehouse, _ = _create_bytehouse()
    bytehouse.ensure_table()
    bytehouse.ensure_discovery_tables()

    try:
        all_clusters: list[SemanticCluster] = []
        total_scanned = 0
        type_counts: dict[str, int] = {}

        for node_type in _NODE_TYPES:
            gcn_ids, matrix = bytehouse.load_embeddings_by_type(node_type)
            total_scanned += len(gcn_ids)
            if gcn_ids:
                type_counts[node_type] = len(gcn_ids)
            if len(gcn_ids) < 2:
                continue
            clusters = cluster_embeddings(gcn_ids, matrix, config)
            for c in clusters:
                c.node_type = node_type
            all_clusters.extend(clusters)
            logger.info("%s: %d embeddings → %d clusters", node_type, len(gcn_ids), len(clusters))

        elapsed = time.monotonic() - t0
        size_dist = Counter(len(c.gcn_ids) for c in all_clusters)

        result = ClusteringResult(
            clusters=all_clusters,
            stats=ClusteringStats(
                total_variables_scanned=total_scanned,
                total_embeddings_computed=0,
                total_clusters=len(all_clusters),
                cluster_size_distribution=dict(size_dist),
                elapsed_seconds=round(elapsed, 2),
            ),
            timestamp=datetime.now(timezone.utc),
        )

        if all_clusters:
            run_id = bytehouse.save_discovery_result(
                result,
                config,
                scope="full",
                type_counts=type_counts,
            )
            logger.info("Saved run_id=%s, %d clusters in %.1fs", run_id, len(all_clusters), elapsed)

        return result
    finally:
        bytehouse.close()


async def dry_run() -> dict:
    """Report embedding status without running anything."""
    from gaia.lkm.storage import StorageConfig, StorageManager

    cfg = StorageConfig()
    storage = StorageManager(cfg)
    await storage.initialize()

    bytehouse, _ = _create_bytehouse(cfg)
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
        await storage.close()


async def main(
    threshold: float = 0.85,
    is_dry_run: bool = False,
    cluster_only: bool = False,
) -> None:
    """CLI entry point."""
    if is_dry_run:
        stats = await dry_run()
        logger.info(
            "Public globals: %d, already embedded: %d, pending: %d",
            stats["public_globals"],
            stats["already_embedded"],
            stats["pending"],
        )
        return

    if cluster_only:
        config = DiscoveryConfig(similarity_threshold=threshold)
        result = run_cluster_only(config)
    else:
        from gaia.lkm.storage import StorageConfig, StorageManager

        cfg = StorageConfig()
        storage = StorageManager(cfg)
        await storage.initialize()
        try:
            config = DiscoveryConfig(similarity_threshold=threshold)
            result = await run_discovery_pipeline(storage, config)
        finally:
            await storage.close()

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


if __name__ == "__main__":
    import argparse
    import os
    import time

    _LOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
    )
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, f"discovery-{time.strftime('%Y%m%d-%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(_LOG_FILE),
        ],
    )
    parser = argparse.ArgumentParser(description="Run M6 semantic discovery")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cluster-only",
        action="store_true",
        help="Skip embedding, just cluster from existing ByteHouse data",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            threshold=args.threshold,
            is_dry_run=args.dry_run,
            cluster_only=args.cluster_only,
        )
    )
