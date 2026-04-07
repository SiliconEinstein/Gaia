"""Quick trial run of M6 semantic discovery on a small subset.

Usage: python scripts/try_discovery.py [--limit 10000] [--dry-run]
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gaia.lkm.models.discovery import DiscoveryConfig  # noqa: E402
from gaia.lkm.storage import StorageConfig, StorageManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main(limit: int = 10000, dry_run: bool = False, threshold: float = 0.85) -> None:
    config = StorageConfig()
    logger.info("LanceDB URI: %s", config.effective_lancedb_uri)
    logger.info("ByteHouse host: %s", config.bytehouse_host)

    storage = StorageManager(config)
    await storage.initialize()

    # Step 1: Count data
    content = storage.content
    gvar_count = await content.count("global_variable_nodes")
    lvar_count = await content.count("local_variable_nodes")
    logger.info("Data: %d global variables, %d local variables", gvar_count, lvar_count)

    # Step 2: Get public globals
    all_public = await storage.list_all_public_global_ids()
    logger.info("Public globals: %d", len(all_public))

    # Show type distribution
    from collections import Counter

    type_dist = Counter(g["type"] for g in all_public)
    logger.info("Type distribution: %s", dict(type_dist))

    if dry_run:
        # Just check ByteHouse connection
        bytehouse = storage.create_bytehouse_store()
        if bytehouse is None:
            logger.error("ByteHouse not configured")
            return
        try:
            bytehouse.ensure_table()
            existing = bytehouse.get_existing_gcn_ids()
            logger.info("ByteHouse existing embeddings: %d", len(existing))
            logger.info("Pending: %d", len(all_public) - len(existing))
        except Exception as e:
            logger.error("ByteHouse error: %s", e)
        finally:
            bytehouse.close()
        await storage.close()
        return

    # Step 3: Run discovery on subset
    subset = all_public[:limit]
    logger.info("Running on subset of %d/%d public globals", len(subset), len(all_public))

    bytehouse = storage.create_bytehouse_store()
    if bytehouse is None:
        logger.error("ByteHouse not configured")
        await storage.close()
        return

    bytehouse.ensure_table()

    # Check how many already have embeddings
    existing = bytehouse.get_existing_gcn_ids()
    subset_ids = {g["id"] for g in subset}
    pending_ids = subset_ids - existing
    logger.info(
        "Subset: %d total, %d already embedded, %d pending",
        len(subset),
        len(subset_ids) - len(pending_ids),
        len(pending_ids),
    )

    # Compute embeddings for pending
    discovery_config = DiscoveryConfig(
        similarity_threshold=threshold,
        embedding_concurrency=24,
    )

    from gaia.lkm.core._embedding import compute_embeddings

    # Override list_all_public_global_ids to return only our subset
    original_method = storage.list_all_public_global_ids

    async def limited_list():
        return subset

    storage.list_all_public_global_ids = limited_list

    t0 = time.time()
    emb_stats = await compute_embeddings(
        storage,
        bytehouse,
        discovery_config,
        access_key=config.embedding_access_key,
    )
    t_emb = time.time() - t0
    logger.info("Embedding stats: %s (%.1fs)", emb_stats, t_emb)

    # Run clustering per type
    from gaia.lkm.core._clustering import cluster_embeddings
    from gaia.lkm.models.discovery import SemanticCluster

    node_types = ("claim", "question", "setting", "action")
    all_clusters: list[SemanticCluster] = []

    loop = asyncio.get_running_loop()
    for node_type in node_types:
        gcn_ids, matrix = await loop.run_in_executor(
            None, bytehouse.load_embeddings_by_type, node_type
        )
        # Filter to our subset
        if gcn_ids:
            mask = [i for i, gid in enumerate(gcn_ids) if gid in subset_ids]
            if len(mask) < 2:
                continue
            gcn_ids = [gcn_ids[i] for i in mask]
            matrix = matrix[mask]

        if len(gcn_ids) < 2:
            continue

        logger.info("Clustering %d %s variables...", len(gcn_ids), node_type)
        t1 = time.time()
        clusters = cluster_embeddings(gcn_ids, matrix, discovery_config)
        for c in clusters:
            c.node_type = node_type
        all_clusters.extend(clusters)
        logger.info("  → %d clusters in %.1fs", len(clusters), time.time() - t1)

    # Print results
    total_time = time.time() - t0
    print("\n" + "=" * 60)
    print(f"RESULTS: {len(all_clusters)} clusters from {len(subset)} variables")
    print(f"Time: {total_time:.1f}s (embedding: {t_emb:.1f}s)")
    print(f"Embedding: {emb_stats}")

    # Cluster size distribution
    size_dist = Counter(len(c.gcn_ids) for c in all_clusters)
    print(f"Cluster sizes: {dict(sorted(size_dist.items()))}")

    # Show sample clusters with content
    print("\n--- Sample clusters (first 10) ---")
    for c in all_clusters[:10]:
        print(
            f"\nCluster {c.cluster_id} ({c.node_type}): "
            f"{len(c.gcn_ids)} nodes, avg_sim={c.avg_similarity:.3f}, "
            f"min_sim={c.min_similarity:.3f}"
        )
        # Load content for first 3 members
        for gid in c.gcn_ids[:3]:
            gvar = await storage.get_global_variable(gid)
            if gvar and gvar.representative_lcn:
                lvar = await storage.get_local_variable(gvar.representative_lcn.local_id)
                content = lvar.content[:100] if lvar else "(no content)"
            else:
                content = "(no gvar)"
            print(f"  [{gid}] {content}")

    bytehouse.close()
    await storage.close()

    # Restore
    storage.list_all_public_global_ids = original_method


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, dry_run=args.dry_run, threshold=args.threshold))
