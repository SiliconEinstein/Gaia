#!/usr/bin/env python3
"""Extract a small representative test fixture subset from the full dataset.

Edge-first selection: pick 9 edges covering all 4 types, collect referenced
nodes, extract embeddings, copy source papers.

Usage:
    python scripts/extract_subset.py
"""

import json
import shutil
import sqlite3
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_DATA_DIR = REPO_ROOT / "data" / "full"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
EMBEDDINGS_DB = Path("/tmp/entailment_test_graph/embeddings.db")
PAPERS_SRC = Path.home() / "project" / "test_claude" / "超导文章" / "High-Tc"

# 9 edges covering all 4 types: paper-extract, join, contradiction, meet
SELECTED_EDGE_IDS = {10, 13, 40, 325, 365, 529, 734, 806, 807}

# 3 source papers referenced by nodes in the selected subgraph
SELECTED_PAPERS = [
    "10.1038332139a0_1988_Natu",
    "10.1038s41467-021-25372-2",
    "363056a0",
]


def load_embeddings_from_db(db_path: Path, node_ids: set[int]) -> dict[str, list[float]]:
    """Load embeddings for specific node IDs from the SQLite database."""
    if not db_path.exists():
        print(f"  WARNING: {db_path} not found, skipping embeddings")
        return {}
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT node_id, dim, vector FROM embeddings")
    result = {}
    for node_id, dim, blob in cur.fetchall():
        if node_id in node_ids:
            vec = list(struct.unpack(f"{dim}f", blob))
            result[str(node_id)] = vec
    conn.close()
    return result


def main() -> None:
    # ── Load full data ──
    print("Loading full dataset from data/full/ ...")
    all_edges = json.loads((FULL_DATA_DIR / "edges.json").read_text())
    all_nodes = json.loads((FULL_DATA_DIR / "nodes.json").read_text())
    all_contradictions = json.loads((FULL_DATA_DIR / "contradictions.json").read_text())
    print(f"  {len(all_nodes)} nodes, {len(all_edges)} edges, {len(all_contradictions)} contradictions")

    # ── Filter edges ──
    edges_by_id = {e["id"]: e for e in all_edges}
    selected_edges = []
    for eid in sorted(SELECTED_EDGE_IDS):
        if eid not in edges_by_id:
            print(f"  ERROR: edge {eid} not found in dataset")
            sys.exit(1)
        selected_edges.append(edges_by_id[eid])
    print(f"\nSelected {len(selected_edges)} edges:")
    for e in selected_edges:
        print(f"  edge {e['id']:>4d}  type={e['type']:<18s}  tail={e['tail']} → head={e['head']}")

    # ── Collect node IDs from tail/head ──
    node_ids: set[int] = set()
    for e in selected_edges:
        node_ids.update(e["tail"])
        node_ids.update(e["head"])
    print(f"\n{len(node_ids)} unique node IDs: {sorted(node_ids)}")

    # ── Filter nodes ──
    nodes_by_id = {n["id"]: n for n in all_nodes}
    selected_nodes = []
    missing_nodes = []
    for nid in sorted(node_ids):
        if nid in nodes_by_id:
            selected_nodes.append(nodes_by_id[nid])
        else:
            missing_nodes.append(nid)
    if missing_nodes:
        print(f"  WARNING: {len(missing_nodes)} nodes not found: {missing_nodes}")
    print(f"Selected {len(selected_nodes)} nodes")

    # Node type/subtype stats
    type_counts: dict[str, int] = {}
    subtype_counts: dict[str, int] = {}
    for n in selected_nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
        st = n.get("subtype") or "none"
        subtype_counts[st] = subtype_counts.get(st, 0) + 1
    print(f"  types: {type_counts}")
    print(f"  subtypes: {subtype_counts}")

    # ── Filter contradictions ──
    selected_contradictions = []
    for c in all_contradictions:
        c_nodes = set(c["nodes"])
        c_join = c.get("join_node")
        if c_nodes.issubset(node_ids) and (c_join is None or c_join in node_ids):
            selected_contradictions.append(c)
    print(f"\nSelected {len(selected_contradictions)} contradictions")

    # ── Load embeddings from SQLite ──
    print(f"\nLoading embeddings from {EMBEDDINGS_DB} ...")
    embeddings = load_embeddings_from_db(EMBEDDINGS_DB, node_ids)
    nodes_without_emb = node_ids - {int(k) for k in embeddings}
    print(f"  {len(embeddings)} embeddings loaded")
    if nodes_without_emb:
        print(f"  nodes without embeddings: {sorted(nodes_without_emb)}")

    # ── Verify: no dangling references ──
    print("\nVerifying referential integrity ...")
    ok = True
    for e in selected_edges:
        for nid in e["tail"] + e["head"]:
            if nid not in node_ids:
                print(f"  ERROR: edge {e['id']} references node {nid} not in subset")
                ok = False
    if ok:
        print("  All edges reference valid nodes")

    # ── Write subset fixtures ──
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting {FIXTURES_DIR / 'nodes.json'} ...")
    with open(FIXTURES_DIR / "nodes.json", "w") as f:
        json.dump(selected_nodes, f, ensure_ascii=False, indent=2)

    print(f"Writing {FIXTURES_DIR / 'edges.json'} ...")
    with open(FIXTURES_DIR / "edges.json", "w") as f:
        json.dump(selected_edges, f, ensure_ascii=False, indent=2)

    print(f"Writing {FIXTURES_DIR / 'contradictions.json'} ...")
    with open(FIXTURES_DIR / "contradictions.json", "w") as f:
        json.dump(selected_contradictions, f, ensure_ascii=False, indent=2)

    print(f"Writing {FIXTURES_DIR / 'embeddings.json'} ...")
    with open(FIXTURES_DIR / "embeddings.json", "w") as f:
        json.dump(embeddings, f)

    # ── Copy papers ──
    papers_dir = FIXTURES_DIR / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCopying {len(SELECTED_PAPERS)} paper directories to {papers_dir} ...")
    for paper in SELECTED_PAPERS:
        src = PAPERS_SRC / paper
        dst = papers_dir / paper
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  {paper} → OK")
        else:
            print(f"  {paper} → NOT FOUND at {src}")

    # ── Summary ──
    print(f"\nDone! Subset fixtures written to {FIXTURES_DIR}")
    print(f"  nodes.json:          {len(selected_nodes)} nodes")
    print(f"  edges.json:          {len(selected_edges)} edges")
    print(f"  contradictions.json: {len(selected_contradictions)} contradictions")
    print(f"  embeddings.json:     {len(embeddings)} embeddings")
    edge_types = {}
    for e in selected_edges:
        edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1
    print(f"  edge types:          {edge_types}")


if __name__ == "__main__":
    main()
