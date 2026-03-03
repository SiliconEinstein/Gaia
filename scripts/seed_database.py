"""Seed Gaia databases (LanceDB + Neo4j + Vector Index) from fixture data."""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

# Allow running from repo root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.models import HyperEdge, Node
from libs.storage import StorageConfig, StorageManager


def load_nodes(fixtures_dir: Path) -> list[Node]:
    raw = json.loads((fixtures_dir / "nodes.json").read_text())
    return [Node(**item) for item in raw]


def load_edges(fixtures_dir: Path) -> list[HyperEdge]:
    raw = json.loads((fixtures_dir / "edges.json").read_text())
    return [HyperEdge(**item) for item in raw]


def load_embeddings(fixtures_dir: Path) -> tuple[list[int], list[list[float]]]:
    raw: dict[str, list[float]] = json.loads((fixtures_dir / "embeddings.json").read_text())
    node_ids = [int(k) for k in raw]
    vectors = [raw[k] for k in raw]
    return node_ids, vectors


async def seed(
    fixtures_dir: Path,
    db_path: str,
    neo4j_password: str,
    neo4j_uri: str,
    neo4j_database: str,
    batch_size: int,
) -> None:
    # ── Load fixtures ──
    print("Loading fixtures …")
    nodes = load_nodes(fixtures_dir)
    edges = load_edges(fixtures_dir)
    emb_ids, emb_vecs = load_embeddings(fixtures_dir)
    print(f"  nodes:      {len(nodes)}")
    print(f"  edges:      {len(edges)}")
    print(f"  embeddings: {len(emb_ids)}")

    # ── Init storage ──
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=db_path,
        neo4j_password=neo4j_password,
        neo4j_uri=neo4j_uri,
        neo4j_database=neo4j_database,
    )
    manager = StorageManager(config)

    try:
        # ── 1. LanceDB: save nodes ──
        print("\n[1/3] Saving nodes to LanceDB …")
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            await manager.lance.save_nodes(batch)
            print(f"  batch {i // batch_size + 1}: {len(batch)} nodes")
        print(f"  ✓ {len(nodes)} nodes saved")

        # ── 2. Neo4j: create hyperedges ──
        neo4j_ok = False
        if manager.graph is None:
            print("\n[2/3] Neo4j driver not created — skipping edges")
        else:
            print("\n[2/3] Creating hyperedges in Neo4j …")
            try:
                await manager.graph.initialize_schema()
                for i in range(0, len(edges), batch_size):
                    batch = edges[i : i + batch_size]
                    await manager.graph.create_hyperedges_bulk(batch)
                    print(f"  batch {i // batch_size + 1}: {len(batch)} edges")
                print(f"  ✓ {len(edges)} edges created")
                neo4j_ok = True
            except Exception as e:
                print(f"  ✗ Neo4j failed: {e}")
                print("  Continuing without Neo4j …")

        # ── 3. Vector index: insert embeddings ──
        print("\n[3/3] Inserting embeddings into vector index …")
        for i in range(0, len(emb_ids), batch_size):
            ids_batch = emb_ids[i : i + batch_size]
            vecs_batch = emb_vecs[i : i + batch_size]
            await manager.vector.insert_batch(ids_batch, vecs_batch)
            print(f"  batch {i // batch_size + 1}: {len(ids_batch)} embeddings")
        print(f"  ✓ {len(emb_ids)} embeddings inserted")

        # ── Verification ──
        print("\n── Verification ──")
        # Spot-check a few random nodes
        sample_ids = random.sample([n.id for n in nodes], min(3, len(nodes)))
        for nid in sample_ids:
            loaded = await manager.lance.load_node(nid)
            status = "OK" if loaded and loaded.id == nid else "MISSING"
            title = (loaded.title or loaded.content[:60]) if loaded else "—"
            print(f"  node {nid}: {status}  ({title})")

        # Spot-check edges
        if neo4j_ok:
            sample_eids = random.sample([e.id for e in edges], min(3, len(edges)))
            for eid in sample_eids:
                loaded = await manager.graph.get_hyperedge(eid)
                status = "OK" if loaded and loaded.id == eid else "MISSING"
                etype = loaded.type if loaded else "—"
                print(f"  edge {eid}: {status}  (type={etype})")

        # Spot-check vector search
        if emb_vecs:
            probe_idx = random.randint(0, len(emb_vecs) - 1)
            results = await manager.vector.search(emb_vecs[probe_idx], k=1)
            if results and results[0][0] == emb_ids[probe_idx]:
                print(f"  vector search for node {emb_ids[probe_idx]}: OK (top-1 match)")
            else:
                print(f"  vector search for node {emb_ids[probe_idx]}: top-1={results}")

        print("\nDone.")

    finally:
        await manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Gaia databases from fixtures")
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "fixtures",
        help="Path to fixture JSON files (default: tests/fixtures)",
    )
    parser.add_argument(
        "--db-path",
        default="/tmp/gaia_seed_test",
        help="LanceDB storage path (default: /tmp/gaia_seed_test)",
    )
    parser.add_argument(
        "--neo4j-password",
        default="",
        help="Neo4j password (default: empty)",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--neo4j-database",
        default="neo4j",
        help="Neo4j database name (default: neo4j)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for writes (default: 500)",
    )
    args = parser.parse_args()

    asyncio.run(
        seed(
            fixtures_dir=args.fixtures_dir,
            db_path=args.db_path,
            neo4j_password=args.neo4j_password,
            neo4j_uri=args.neo4j_uri,
            neo4j_database=args.neo4j_database,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
