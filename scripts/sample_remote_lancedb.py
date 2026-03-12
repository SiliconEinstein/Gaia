"""Sample data from remote LanceDB and save as test fixtures.

Usage:
    cd /Users/dp/Projects/Gaia
    python scripts/sample_remote_lancedb.py
"""

import json
import os
from pathlib import Path

import lancedb
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TOPICS = [
    "aerospace_cfd_graduate/Courant–Friedrichs–Lewy_condition",
    "aerospace_cfd_graduate/Arrhenius_kinetics_and_reaction_mechanisms",
    "aerospace_cfd_graduate/Delaunay_triangulation_for_mesh_generation",
]

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "remote_lancedb"


def connect():
    bucket = "datainfra-prod"
    base_path = "propositional_logic_analysis"
    uri = f"s3://{bucket}/{base_path}"
    opts = {
        "access_key_id": os.getenv("TOS_ACCESS_KEY"),
        "secret_access_key": os.getenv("TOS_SECRET_KEY"),
        "endpoint": f"https://{bucket}.{os.getenv('TOS_ENDPOINT')}",
        "virtual_hosted_style_request": "true",
    }
    return lancedb.connect(uri, storage_options=opts)


def convert(obj):
    """Convert numpy types to JSON-serializable Python types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert(v) for v in obj]
    return obj


def clean(records):
    """Remove LanceDB search artifacts and convert types."""
    return [convert({k: v for k, v in r.items() if k != "_distance"}) for r in records]


def main():
    db = connect()

    nodes_tbl = db.open_table("nodes")
    edges_tbl = db.open_table("edges")
    graph_tbl = db.open_table("graph")
    node_rel_tbl = db.open_table("node_relation")
    meta_tbl = db.open_table("metadata")

    all_nodes = []
    all_edges = []
    all_graph = []
    all_node_ids = set()

    for topic in TOPICS:
        print(f"\n=== {topic} ===")
        edges = edges_tbl.search().where(f"metadata.location LIKE '{topic}/%'").limit(5000).to_list()
        print(f"  edges: {len(edges)}")

        topic_node_ids = set()
        for e in edges:
            for nid in e["initial_reasoning"]["tail"]:
                topic_node_ids.add(nid)
            for nid in e["initial_reasoning"]["head"]:
                topic_node_ids.add(nid)

        print(f"  node IDs referenced: {len(topic_node_ids)}")

        if topic_node_ids:
            id_str = ",".join(str(n) for n in topic_node_ids)
            nodes = nodes_tbl.search().where(f"id IN ({id_str})").limit(len(topic_node_ids) + 100).to_list()
            print(f"  nodes fetched: {len(nodes)}")
            all_nodes.extend(nodes)
            all_node_ids.update(topic_node_ids)

        all_edges.extend(edges)

        edge_ids = {e["id"] for e in edges}
        eid_str = ",".join(str(e) for e in edge_ids)
        graph_entries = graph_tbl.search().where(f"edge_id IN ({eid_str})").limit(len(edge_ids) + 100).to_list()
        print(f"  graph entries: {len(graph_entries)}")
        all_graph.extend(graph_entries)

    # Fetch node_relation in batches
    print(f"\n=== node_relation for {len(all_node_ids)} nodes ===")
    node_rels = []
    batch_ids = list(all_node_ids)
    for i in range(0, len(batch_ids), 500):
        batch = batch_ids[i : i + 500]
        id_str = ",".join(str(n) for n in batch)
        results = node_rel_tbl.search().where(f"node_id IN ({id_str})").limit(len(batch) + 100).to_list()
        node_rels.extend(results)
    print(f"  fetched: {len(node_rels)}")

    # Metadata (small table)
    meta = meta_tbl.to_pandas().to_dict(orient="records")

    # === Save ===
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Separate embeddings from nodes
    embeddings = {}
    nodes_out = []
    for n in all_nodes:
        n = convert(n)
        vec = n.pop("content_vector", None)
        n.pop("_distance", None)
        if vec and n.get("id") is not None:
            embeddings[str(n["id"])] = vec
        nodes_out.append(n)

    for name, data in [
        ("nodes", nodes_out),
        ("edges", clean(all_edges)),
        ("graph", clean(all_graph)),
        ("node_relation", clean(node_rels)),
        ("metadata", [convert(m) for m in meta]),
    ]:
        path = OUT_DIR / f"{name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  {name}.json: {len(data)} records")

    emb_path = OUT_DIR / "embeddings.json"
    with open(emb_path, "w") as f:
        json.dump(embeddings, f, ensure_ascii=False)
    print(f"  embeddings.json: {len(embeddings)} vectors")

    manifest = {
        "source": "remote LanceDB (datainfra-prod/propositional_logic_analysis)",
        "sampled_topics": TOPICS,
        "counts": {
            "nodes": len(nodes_out),
            "edges": len(clean(all_edges)),
            "graph": len(clean(all_graph)),
            "node_relation": len(clean(node_rels)),
            "metadata": len(meta),
            "embeddings": len(embeddings),
        },
    }
    with open(OUT_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Fixtures saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
