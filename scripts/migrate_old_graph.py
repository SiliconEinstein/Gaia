#!/usr/bin/env python3
"""Migrate old propositional logic graph data to Gaia format.

Reads from the old graph directory structure and outputs JSON fixtures
compatible with the new Gaia Node/HyperEdge data models.

Usage:
    python scripts/migrate_old_graph.py /tmp/entailment_test_graph tests/fixtures
"""

import json
import glob
import struct
import sqlite3
import sys
from pathlib import Path


def load_old_nodes(graph_dir: Path) -> list[dict]:
    """Load all node JSON files from the old directory structure."""
    nodes = []
    for f in sorted(glob.glob(str(graph_dir / "nodes" / "*" / "*" / "*.json"))):
        with open(f) as fh:
            nodes.append(json.load(fh))
    return nodes


def load_old_edges(graph_dir: Path) -> list[dict]:
    """Load all edge JSON files from the old directory structure."""
    edges = []
    for f in sorted(glob.glob(str(graph_dir / "edges" / "*" / "*" / "*.json"))):
        with open(f) as fh:
            edges.append(json.load(fh))
    return edges


def load_graph_topology(graph_dir: Path) -> dict:
    """Load graph.json for current topology (active edges with tail/head)."""
    with open(graph_dir / "graph.json") as f:
        return json.load(f)


def load_embeddings(graph_dir: Path) -> dict[int, list[float]]:
    """Load embeddings from SQLite, returns {node_id: [float, ...]}."""
    db_path = graph_dir / "embeddings.db"
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT node_id, dim, vector FROM embeddings")
    result = {}
    for node_id, dim, blob in cur.fetchall():
        vec = list(struct.unpack(f"{dim}f", blob))
        result[node_id] = vec
    conn.close()
    return result


def load_contradictions(graph_dir: Path) -> list[dict]:
    """Load contradictions.json."""
    path = graph_dir / "contradictions.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def map_node_type(old_metadata_type: str) -> str:
    """Map old metadata.type to new Gaia Node.type."""
    mapping = {
        "paper-extract": "paper-extract",
        "merged proposition": "abstraction",
    }
    return mapping.get(old_metadata_type, old_metadata_type)


def convert_node(old: dict) -> dict:
    """Convert an old node dict to new Gaia Node format."""
    meta = old.get("metadata", {})

    # Build extra from fields that are no longer top-level
    extra = {}
    if old.get("notations"):
        extra["notations"] = old["notations"]
    if old.get("assumption"):
        extra["assumption"] = old["assumption"]

    # Normalize keywords: old data has "" (empty string) or list
    keywords = old.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    # Build clean metadata (remove fields that map to typed fields)
    new_metadata = {}
    for k, v in meta.items():
        if k not in ("type", "node_type"):
            new_metadata[k] = v

    return {
        "id": old["id"],
        "type": map_node_type(meta.get("type", "paper-extract")),
        "subtype": meta.get("node_type"),  # premise, conclusion, conjecture, deduction, join
        "title": old.get("title"),
        "content": old.get("content", ""),
        "keywords": keywords,
        "prior": 1.0,
        "belief": None,
        "status": "active",
        "metadata": new_metadata,
        "extra": extra,
        "created_at": None,
    }


def convert_edge(old: dict, topology: dict) -> dict:
    """Convert an old edge dict to new Gaia HyperEdge format."""
    meta = old.get("metadata", {})
    edge_id = old["id"]
    edge_id_str = str(edge_id)

    # Determine tail/head: prefer initial_reasoning, fall back to top-level, then topology
    if "initial_reasoning" in old:
        tail = old["initial_reasoning"]["tail"]
        head = old["initial_reasoning"]["head"]
    elif "tail" in old and "head" in old:
        tail = old["tail"]
        head = old["head"]
    elif edge_id_str in topology.get("edges", {}):
        tail = topology["edges"][edge_id_str]["tail"]
        head = topology["edges"][edge_id_str]["head"]
    else:
        tail = []
        head = []

    # Reasoning: keep as-is (could be string or list of dicts)
    reasoning = old.get("reasoning", [])
    if isinstance(reasoning, str):
        reasoning = [reasoning]

    # Extract typed fields from metadata
    probability = meta.get("probability")
    verified = meta.get("verified", False)
    subtype = meta.get("conclusion_type")  # e.g., "deduction" for meet edges

    # Build extra from non-metadata fields
    extra = {}
    if old.get("notations"):
        extra["notations"] = old["notations"]
    if old.get("assumption"):
        extra["assumption"] = old["assumption"]
    # Preserve quality info from metadata in extra
    if meta.get("quality"):
        extra["quality"] = meta["quality"]
    if meta.get("reliability_reasoning"):
        extra["reliability_reasoning"] = meta["reliability_reasoning"]
    if meta.get("reliability") is not None:
        extra["reliability"] = meta["reliability"]

    # Build clean metadata (remove fields that map to typed fields or extra)
    skip_keys = {
        "type",
        "conclusion_type",
        "probability",
        "verified",
        "quality",
        "reliability",
        "reliability_reasoning",
    }
    new_metadata = {k: v for k, v in meta.items() if k not in skip_keys}

    return {
        "id": edge_id,
        "type": meta.get("type", "paper-extract"),
        "subtype": subtype,
        "tail": tail,
        "head": head,
        "probability": probability,
        "verified": verified,
        "reasoning": reasoning,
        "metadata": new_metadata,
        "extra": extra,
        "created_at": None,
    }


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <old_graph_dir> <output_dir>")
        sys.exit(1)

    graph_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading from: {graph_dir}")
    print(f"Writing to: {output_dir}")

    # Load old data
    print("Loading nodes...")
    old_nodes = load_old_nodes(graph_dir)
    print(f"  Found {len(old_nodes)} nodes")

    print("Loading edges...")
    old_edges = load_old_edges(graph_dir)
    print(f"  Found {len(old_edges)} edges")

    print("Loading graph topology...")
    topology = load_graph_topology(graph_dir)
    topo_edge_count = len(topology.get("edges", {}))
    print(f"  {topo_edge_count} edges in topology")

    print("Loading embeddings...")
    embeddings = load_embeddings(graph_dir)
    print(
        f"  Found {len(embeddings)} embeddings (dim={len(next(iter(embeddings.values())))})"
        if embeddings
        else "  No embeddings"
    )

    print("Loading contradictions...")
    contradictions = load_contradictions(graph_dir)
    print(f"  Found {len(contradictions)} contradictions")

    # Convert
    print("\nConverting nodes...")
    new_nodes = [convert_node(n) for n in old_nodes]

    print("Converting edges...")
    new_edges = [convert_edge(e, topology) for e in old_edges]

    # Stats
    node_types = {}
    for n in new_nodes:
        node_types[n["type"]] = node_types.get(n["type"], 0) + 1
    print(f"\nNode type distribution: {node_types}")

    edge_types = {}
    for e in new_edges:
        edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1
    print(f"Edge type distribution: {edge_types}")

    node_subtypes = {}
    for n in new_nodes:
        st = n.get("subtype") or "none"
        node_subtypes[st] = node_subtypes.get(st, 0) + 1
    print(f"Node subtype distribution: {node_subtypes}")

    # Write output
    print(f"\nWriting {output_dir / 'nodes.json'}...")
    with open(output_dir / "nodes.json", "w") as f:
        json.dump(new_nodes, f, ensure_ascii=False, indent=2)

    print(f"Writing {output_dir / 'edges.json'}...")
    with open(output_dir / "edges.json", "w") as f:
        json.dump(new_edges, f, ensure_ascii=False, indent=2)

    print(f"Writing {output_dir / 'contradictions.json'}...")
    with open(output_dir / "contradictions.json", "w") as f:
        json.dump(contradictions, f, ensure_ascii=False, indent=2)

    # Embeddings: save as {node_id: [floats]} JSON
    # (For large scale, would use numpy/parquet, but 1637 x 512d is ~3MB JSON)
    print(f"Writing {output_dir / 'embeddings.json'}...")
    with open(output_dir / "embeddings.json", "w") as f:
        # Convert int keys to string for JSON
        json.dump({str(k): v for k, v in embeddings.items()}, f)

    # Summary
    print("\nDone! Output files:")
    print(f"  {output_dir / 'nodes.json'}: {len(new_nodes)} nodes")
    print(f"  {output_dir / 'edges.json'}: {len(new_edges)} edges")
    print(f"  {output_dir / 'embeddings.json'}: {len(embeddings)} vectors")
    print(f"  {output_dir / 'contradictions.json'}: {len(contradictions)} contradictions")


if __name__ == "__main__":
    main()
