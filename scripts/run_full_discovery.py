"""Run full M6 discovery: embed all pending variables + cluster + save.

Usage: python scripts/run_full_discovery.py
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

# Log to both console and file
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
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("Log file: %s", _LOG_FILE)


async def main():
    from gaia.lkm.core._clustering import cluster_embeddings
    from gaia.lkm.core._embedding import compute_embeddings
    from gaia.lkm.models.discovery import (
        ClusteringResult,
        ClusteringStats,
        DiscoveryConfig,
        SemanticCluster,
    )
    from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore
    from gaia.lkm.storage.config import StorageConfig
    from gaia.lkm.storage.lance_store import LanceContentStore
    from collections import Counter
    from datetime import datetime, timezone

    t0 = time.time()
    cfg = StorageConfig()

    # Init LanceDB only (skip Neo4j)
    lance = LanceContentStore(cfg.effective_lancedb_uri, storage_options=cfg.storage_options)
    await lance.initialize()
    logger.info("[%.0fs] LanceDB ready", time.time() - t0)

    # Create a minimal StorageManager-like object for compute_embeddings
    # (it needs list_all_public_global_ids and get_local_variables_by_ids)
    class _LanceOnlyStorage:
        def __init__(self, content):
            self._content = content
            self._config = cfg
            self.graph = None

        @property
        def content(self):
            return self._content

        async def list_all_public_global_ids(self):
            return await self._content.list_all_public_global_ids()

        async def get_local_variables_by_ids(self, local_ids):
            return await self._content.get_local_variables_by_ids(local_ids)

    storage = _LanceOnlyStorage(lance)

    # ByteHouse
    bh = ByteHouseEmbeddingStore(
        host=cfg.bytehouse_host,
        user=cfg.bytehouse_user,
        password=cfg.bytehouse_password,
        database=cfg.bytehouse_database,
        replication_root=cfg.bytehouse_replication_root,
    )
    bh.ensure_table()
    bh.ensure_discovery_tables()
    logger.info("[%.0fs] ByteHouse ready", time.time() - t0)

    # Phase 1: Compute embeddings (concurrency=150)
    config = DiscoveryConfig(similarity_threshold=0.85, embedding_concurrency=150)
    emb_stats = await compute_embeddings(storage, bh, config, access_key=cfg.embedding_access_key)
    logger.info("[%.0fs] Embedding done: %s", time.time() - t0, emb_stats)

    # Phase 2: Cluster
    all_clusters: list[SemanticCluster] = []
    total_scanned = 0
    type_counts: dict[str, int] = {}

    for node_type in ("claim", "question", "setting", "action"):
        gcn_ids, matrix = bh.load_embeddings_by_type(node_type)
        total_scanned += len(gcn_ids)
        if gcn_ids:
            type_counts[node_type] = len(gcn_ids)
        logger.info("[%.0fs] %s: %d embeddings", time.time() - t0, node_type, len(gcn_ids))
        if len(gcn_ids) < 2:
            continue
        clusters = cluster_embeddings(gcn_ids, matrix, config)
        for c in clusters:
            c.node_type = node_type
        all_clusters.extend(clusters)
        logger.info("[%.0fs] %s: %d clusters", time.time() - t0, node_type, len(clusters))

    elapsed = time.time() - t0
    size_dist = Counter(len(c.gcn_ids) for c in all_clusters)

    result = ClusteringResult(
        clusters=all_clusters,
        stats=ClusteringStats(
            total_variables_scanned=total_scanned,
            total_embeddings_computed=emb_stats.get("computed", 0),
            total_clusters=len(all_clusters),
            cluster_size_distribution=dict(size_dist),
            elapsed_seconds=elapsed,
        ),
        timestamp=datetime.now(timezone.utc),
    )

    # Phase 3: Save
    run_id = bh.save_discovery_result(result, config, scope="full", type_counts=type_counts)
    logger.info("[%.0fs] Saved run_id=%s", time.time() - t0, run_id)

    print(
        json.dumps(
            {
                "run_id": run_id,
                "scope": "full",
                "total_scanned": total_scanned,
                "embeddings_computed": emb_stats.get("computed", 0),
                "embeddings_skipped": emb_stats.get("skipped", 0),
                "embeddings_failed": emb_stats.get("failed", 0),
                "total_clusters": len(all_clusters),
                "type_counts": type_counts,
                "cluster_sizes": dict(sorted(size_dist.items())),
                "elapsed_seconds": round(elapsed, 1),
            },
            indent=2,
        )
    )

    bh.close()


if __name__ == "__main__":
    asyncio.run(main())
