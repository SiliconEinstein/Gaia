"""Pipeline: FAISS clustering from existing ByteHouse embeddings.

No LanceDB or Neo4j needed. Loads embeddings from ByteHouse,
clusters per node_type, saves results.

Usage:
    python -m gaia.lkm.pipelines.cluster
    python -m gaia.lkm.pipelines.cluster --threshold 0.80
"""

from __future__ import annotations

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


def run_clustering(
    config: DiscoveryConfig | None = None,
) -> ClusteringResult:
    """Load embeddings from ByteHouse, cluster, save results.

    No LanceDB or Neo4j needed. Fast (~15s for 10k, ~60s for 250k embeddings).
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


if __name__ == "__main__":
    import argparse
    import os

    _LOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
    )
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, f"cluster-{time.strftime('%Y%m%d-%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(_LOG_FILE),
        ],
        force=True,
    )

    parser = argparse.ArgumentParser(description="Run FAISS clustering on existing embeddings")
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    config = DiscoveryConfig(similarity_threshold=args.threshold)
    result = run_clustering(config)

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
