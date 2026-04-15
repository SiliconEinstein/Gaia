"""Discovery Orchestrator for M6 Semantic Discovery.

Entry point that wires together embedding computation and FAISS clustering.
Processes each node type separately and aggregates results into a
ClusteringResult with summary statistics.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import numpy as np

from gaia.lkm.core._clustering import cluster_embeddings
from gaia.lkm.core._embedding import compute_embeddings
from gaia.lkm.models.discovery import (
    ClusteringResult,
    ClusteringStats,
    DiscoveryConfig,
    SemanticCluster,
)

logger = logging.getLogger(__name__)

_NODE_TYPES = ("claim", "question", "setting", "action")


async def _build_factor_index(storage) -> dict[str, set[str]]:
    """Build {gcn_id: set(gfac_ids)} from Neo4j if available.

    Args:
        storage: A StorageManager instance.

    Returns:
        A mapping from GCN ID to its set of factor IDs, or an empty dict
        if the graph store is unavailable or the method is not implemented.
    """
    if storage.graph is None:
        return {}
    try:
        return await storage.graph.get_variable_factor_index()
    except Exception:
        logger.warning("Failed to build factor index", exc_info=True)
        return {}


async def run_semantic_discovery(
    storage,
    bytehouse,
    config: DiscoveryConfig,
    access_key: str,
) -> ClusteringResult:
    """Run the full semantic discovery pipeline.

    Steps:
    1. Compute embeddings for all un-embedded public global variable nodes.
    2. Build a factor index from Neo4j (graceful fallback to empty dict).
    3. For each node type (claim, question, setting, action):
       a. Load embeddings from ByteHouse.
       b. Skip if fewer than 2 vectors.
       c. Cluster embeddings with FAISS + Union-Find.
       d. Stamp each cluster with its node_type.
    4. Aggregate and return ClusteringResult with stats.

    Args:
        storage: A StorageManager instance with async read methods.
        bytehouse: A ByteHouseEmbeddingStore instance (sync methods).
        config: Discovery pipeline configuration.
        access_key: API access key for the embedding endpoint.

    Returns:
        A ClusteringResult with all clusters and summary statistics.
    """
    start = time.monotonic()
    loop = asyncio.get_event_loop()

    # Step 1: Compute embeddings for pending nodes
    embed_stats = await compute_embeddings(storage, bytehouse, config, access_key)
    total_variables_scanned = embed_stats.get("total", 0)
    total_embeddings_computed = embed_stats.get("computed", 0)

    # Step 2: Build factor index from Neo4j (optional)
    factor_index = await _build_factor_index(storage)

    # Step 3: Cluster by node type
    all_clusters: list[SemanticCluster] = []

    for node_type in _NODE_TYPES:
        # Load embeddings synchronously via run_in_executor
        gcn_ids, matrix = await loop.run_in_executor(
            None, bytehouse.load_embeddings_by_type, node_type
        )

        # Skip if fewer than 2 vectors (nothing to cluster)
        if len(gcn_ids) < 2 or matrix.size == 0:
            logger.debug("Skipping node_type=%s: only %d vectors", node_type, len(gcn_ids))
            continue

        # Ensure matrix is float32 for FAISS
        matrix = np.asarray(matrix, dtype=np.float32)

        # Cluster using FAISS + Union-Find
        clusters = cluster_embeddings(gcn_ids, matrix, config, factor_index)

        # Stamp each cluster with its node type
        for cluster in clusters:
            cluster.node_type = node_type

        all_clusters.extend(clusters)
        logger.info(
            "node_type=%s: %d embeddings → %d clusters",
            node_type,
            len(gcn_ids),
            len(clusters),
        )

    # Step 4: Build stats and result
    cluster_size_distribution: dict[int, int] = {}
    for cluster in all_clusters:
        size = len(cluster.gcn_ids)
        cluster_size_distribution[size] = cluster_size_distribution.get(size, 0) + 1

    elapsed = time.monotonic() - start

    stats = ClusteringStats(
        total_variables_scanned=total_variables_scanned,
        total_embeddings_computed=total_embeddings_computed,
        total_clusters=len(all_clusters),
        cluster_size_distribution=cluster_size_distribution,
        elapsed_seconds=elapsed,
    )

    result = ClusteringResult(
        clusters=all_clusters,
        stats=stats,
        timestamp=datetime.now(timezone.utc),
    )

    # Persist result to ByteHouse
    if all_clusters:
        try:
            run_id = await loop.run_in_executor(
                None, bytehouse.save_discovery_result, result, config
            )
            logger.info("Discovery result saved: run_id=%s, %d clusters", run_id, len(all_clusters))
        except Exception:
            logger.warning("Failed to save discovery result to ByteHouse", exc_info=True)

    return result
