"""Convert sampled remote LanceDB data to storage v2 format and seed local stores.

Each edge becomes a single-step Chain (premises → conclusion).
Premise nodes → Knowledge type=setting, Conclusion nodes → type=claim.

Usage:
    cd /Users/dp/Projects/Gaia
    python scripts/convert_to_v2.py          # convert only
    python scripts/convert_to_v2.py --seed   # convert + write to local LanceDB/Kuzu
"""

import argparse
import asyncio
import json
import random
from collections import defaultdict
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "remote_lancedb"
OUT_DIR = SRC_DIR / "v2"

NOW = "2026-03-12T00:00:00Z"


def slugify(s: str) -> str:
    return s.lower().replace(" ", "_").replace("–", "_").replace("'", "").replace(",", "")


def load(name: str) -> list[dict]:
    with open(SRC_DIR / f"{name}.json") as f:
        return json.load(f)


def make_knowledge_id(pkg_id: str, module_name: str, node: dict) -> str:
    slug = slugify(node["title"])[:60].rstrip("_")
    return f"{pkg_id}.{module_name}.{slug}"


def convert():
    """Convert remote LanceDB data → v2 models and return structured data."""
    nodes_raw = load("nodes")
    edges_raw = load("edges")
    embeddings_raw: dict[str, list[float]] = json.loads(
        (SRC_DIR / "embeddings.json").read_text()
    )

    nodes_by_id = {n["id"]: n for n in nodes_raw}

    # Group edges by topic
    edges_by_topic: dict[str, list[dict]] = defaultdict(list)
    for e in edges_raw:
        loc = e["metadata"].get("location", "")
        parts = loc.split("/")
        topic = "/".join(parts[:2]) if len(parts) >= 2 else loc
        edges_by_topic[topic].append(e)

    all_packages = []
    all_modules = []
    all_knowledge = []
    all_chains = []
    all_probabilities = []
    all_embeddings = []  # (knowledge_id, version, vector)

    node_to_kid: dict[int, str] = {}
    used_kids: set[str] = set()

    for topic, topic_edges in edges_by_topic.items():
        topic_slug = slugify(topic.split("/")[-1])
        pkg_id = topic_slug

        # Collect node IDs
        premise_ids = set()
        conclusion_ids = set()
        for e in topic_edges:
            premise_ids.update(e["initial_reasoning"]["tail"])
            conclusion_ids.update(e["initial_reasoning"]["head"])
        all_node_ids = premise_ids | conclusion_ids

        # Group edges by location → module
        edges_by_loc: dict[str, list[dict]] = defaultdict(list)
        for e in topic_edges:
            loc = e["metadata"].get("location", "unknown")
            edges_by_loc[loc].append(e)

        module_names = {}
        for loc in sorted(edges_by_loc.keys()):
            loc_id = loc.split("/")[-1] if "/" in loc else loc
            module_names[loc] = f"problem_{loc_id}"

        # === Knowledge items ===
        for nid in sorted(all_node_ids):
            node = nodes_by_id.get(nid)
            if not node or nid in node_to_kid:
                continue

            node_type = node["metadata"].get("node_type", "premise")
            node_loc = node["metadata"].get("location", "unknown")
            mod_name = module_names.get(node_loc, list(module_names.values())[0])

            kid = make_knowledge_id(pkg_id, mod_name, node)
            base_kid = kid
            counter = 1
            while kid in used_kids:
                kid = f"{base_kid}_{counter}"
                counter += 1
            used_kids.add(kid)
            node_to_kid[nid] = kid

            # premise → setting (given fact), conclusion → claim (derived)
            k_type = "claim" if node_type == "conclusion" else "setting"

            ki = {
                "knowledge_id": kid,
                "version": 1,
                "type": k_type,
                "content": node["content"],
                "prior": 1.0 if k_type == "setting" else 0.5,
                "keywords": node.get("keywords", []),
                "source_package_id": pkg_id,
                "source_package_version": "1.0.0",
                "source_module_id": f"{pkg_id}.{mod_name}",
                "created_at": NOW,
                "embedding": None,
            }
            all_knowledge.append(ki)

            # Embedding
            vec = embeddings_raw.get(str(nid))
            if vec:
                all_embeddings.append({
                    "knowledge_id": kid,
                    "version": 1,
                    "embedding": vec,
                })

        # === Chains: each edge → one single-step chain ===
        chain_ids_by_module: dict[str, list[str]] = defaultdict(list)
        export_ids_by_module: dict[str, list[str]] = defaultdict(list)

        for e in topic_edges:
            loc = e["metadata"].get("location", "unknown")
            mod_name = module_names.get(loc, "unknown")
            chain_id = f"{pkg_id}.{mod_name}.chain_{e['id']}"

            tail_ids = e["initial_reasoning"]["tail"]
            head_ids = e["initial_reasoning"]["head"]

            # Concatenate all reasoning steps into one
            reasoning_steps = e.get("reasoning", [])
            reasoning_text = "\n\n".join(
                f"**{rs['title']}**: {rs['content']}" if rs.get("title")
                else rs.get("content", "")
                for rs in reasoning_steps
            ) if reasoning_steps else ""

            # Build single step: all premises → first conclusion
            premises = [
                {"knowledge_id": node_to_kid[nid], "version": 1}
                for nid in tail_ids
                if nid in node_to_kid
            ]
            conclusion_nid = head_ids[0] if head_ids else None

            if not conclusion_nid or conclusion_nid not in node_to_kid:
                continue

            step = {
                "step_index": 0,
                "premises": premises,
                "reasoning": reasoning_text,
                "conclusion": {
                    "knowledge_id": node_to_kid[conclusion_nid],
                    "version": 1,
                },
            }

            chain = {
                "chain_id": chain_id,
                "module_id": f"{pkg_id}.{mod_name}",
                "package_id": pkg_id,
                "package_version": "1.0.0",
                "type": "deduction",
                "steps": [step],
            }
            all_chains.append(chain)
            chain_ids_by_module[mod_name].append(chain_id)

            for hid in head_ids:
                if hid in node_to_kid:
                    export_ids_by_module[mod_name].append(node_to_kid[hid])

            all_probabilities.append({
                "chain_id": chain_id,
                "step_index": 0,
                "value": 0.9,
                "source": "author",
                "source_detail": None,
                "recorded_at": NOW,
            })

        # === Modules ===
        for loc, mod_name in module_names.items():
            module_id = f"{pkg_id}.{mod_name}"
            mod_node_ids = set()
            for e in edges_by_loc[loc]:
                mod_node_ids.update(e["initial_reasoning"]["tail"])
                mod_node_ids.update(e["initial_reasoning"]["head"])

            mod_imports = [
                {"knowledge_id": node_to_kid[nid], "version": 1, "strength": "strong"}
                for nid in sorted(mod_node_ids)
                if nid in node_to_kid and nid in premise_ids
            ]

            module = {
                "module_id": module_id,
                "package_id": pkg_id,
                "package_version": "1.0.0",
                "name": mod_name,
                "role": "reasoning",
                "imports": mod_imports,
                "chain_ids": chain_ids_by_module.get(mod_name, []),
                "export_ids": list(set(export_ids_by_module.get(mod_name, []))),
            }
            all_modules.append(module)

        # === Package ===
        all_exports = []
        for ids in export_ids_by_module.values():
            all_exports.extend(ids)

        package = {
            "package_id": pkg_id,
            "name": topic_slug,
            "version": "1.0.0",
            "description": f"Knowledge package for {topic.replace('_', ' ')}",
            "modules": [f"{pkg_id}.{mn}" for mn in module_names.values()],
            "exports": list(set(all_exports)),
            "submitter": "propositional_logic_pipeline",
            "submitted_at": NOW,
            "status": "merged",
        }
        all_packages.append(package)

    return {
        "packages": all_packages,
        "modules": all_modules,
        "knowledge": all_knowledge,
        "chains": all_chains,
        "probabilities": all_probabilities,
        "embeddings": all_embeddings,
        "beliefs": [],
        "resources": [],
        "attachments": [],
    }


def save_fixtures(data: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("packages", "modules", "knowledge", "chains",
                 "probabilities", "beliefs", "resources", "attachments"):
        path = OUT_DIR / f"{name}.json"
        with open(path, "w") as f:
            json.dump(data[name], f, indent=2, ensure_ascii=False)
        print(f"  {name}.json: {len(data[name])} records")

    # Embeddings saved separately (large)
    emb_path = OUT_DIR / "embeddings.json"
    with open(emb_path, "w") as f:
        json.dump(data["embeddings"], f, ensure_ascii=False)
    print(f"  embeddings.json: {len(data['embeddings'])} vectors")


async def seed(data: dict) -> None:
    """Write v2 data to local LanceDB + Kuzu using StorageManager.ingest_package()."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from libs.storage_v2.config import StorageConfig
    from libs.storage_v2.manager import StorageManager
    from libs.storage_v2.models import (
        Chain, ChainStep, Knowledge, KnowledgeEmbedding, KnowledgeRef,
        Module, Package, ProbabilityRecord, ImportRef,
    )

    config = StorageConfig(
        lancedb_path="./data/lancedb/gaia_v2",
        graph_backend="kuzu",
    )
    manager = StorageManager(config)
    await manager.initialize()

    try:
        # Group by package
        pkg_map = {p["package_id"]: p for p in data["packages"]}
        mod_by_pkg = defaultdict(list)
        for m in data["modules"]:
            mod_by_pkg[m["package_id"]].append(m)
        know_by_pkg = defaultdict(list)
        for k in data["knowledge"]:
            know_by_pkg[k["source_package_id"]].append(k)
        chain_by_pkg = defaultdict(list)
        for c in data["chains"]:
            chain_by_pkg[c["package_id"]].append(c)
        emb_by_kid = {e["knowledge_id"]: e for e in data["embeddings"]}
        prob_by_pkg = defaultdict(list)
        for p in data["probabilities"]:
            chain_pkg = p["chain_id"].split(".")[0]
            prob_by_pkg[chain_pkg].append(p)

        for pkg_id, pkg_data in pkg_map.items():
            print(f"\n=== Ingesting package: {pkg_id} ===")

            package = Package(**pkg_data)
            modules = [Module(**m) for m in mod_by_pkg[pkg_id]]
            knowledge_items = [Knowledge(**k) for k in know_by_pkg[pkg_id]]

            chains = []
            for c in chain_by_pkg[pkg_id]:
                steps = [
                    ChainStep(
                        step_index=s["step_index"],
                        premises=[KnowledgeRef(**p) for p in s["premises"]],
                        reasoning=s["reasoning"],
                        conclusion=KnowledgeRef(**s["conclusion"]),
                    )
                    for s in c["steps"]
                ]
                chains.append(Chain(
                    chain_id=c["chain_id"],
                    module_id=c["module_id"],
                    package_id=c["package_id"],
                    package_version=c["package_version"],
                    type=c["type"],
                    steps=steps,
                ))

            embeddings = [
                KnowledgeEmbedding(**emb_by_kid[k.knowledge_id])
                for k in knowledge_items
                if k.knowledge_id in emb_by_kid
            ]

            print(f"  modules: {len(modules)}")
            print(f"  knowledge: {len(knowledge_items)}")
            print(f"  chains: {len(chains)}")
            print(f"  embeddings: {len(embeddings)}")

            await manager.ingest_package(
                package=package,
                modules=modules,
                knowledge_items=knowledge_items,
                chains=chains,
                embeddings=embeddings,
            )

            # Write probabilities
            probs = [ProbabilityRecord(**p) for p in prob_by_pkg[pkg_id]]
            if probs:
                await manager.add_probabilities(probs)
                print(f"  probabilities: {len(probs)}")

            print(f"  ✓ {pkg_id} ingested")

        # Verification
        print("\n── Verification ──")
        sample_kids = random.sample(
            [k["knowledge_id"] for k in data["knowledge"]],
            min(3, len(data["knowledge"]))
        )
        for kid in sample_kids:
            k = await manager.get_knowledge(kid, version=1)
            status = "OK" if k else "MISSING"
            content = (k.content[:60] + "…") if k else "—"
            print(f"  {kid}: {status}  ({content})")

        for pkg_id in pkg_map:
            p = await manager.get_package(pkg_id)
            status = "OK" if p else "MISSING"
            print(f"  package {pkg_id}: {status} (status={p.status if p else '—'})")

        if data["embeddings"]:
            probe = data["embeddings"][0]
            results = await manager.search_vector(probe["embedding"], top_k=1)
            if results:
                print(f"  vector search: OK (top-1={results[0].knowledge.knowledge_id})")
            else:
                print(f"  vector search: no results")

        print("\n✓ Done.")

    finally:
        await manager.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Also seed local stores")
    args = parser.parse_args()

    print("Converting remote LanceDB data → v2 format …")
    data = convert()
    save_fixtures(data)

    print(f"\nPackages: {[p['package_id'] for p in data['packages']]}")
    for p in data["packages"]:
        print(f"  {p['package_id']}: {len(p['modules'])} modules, {len(p['exports'])} exports")

    if args.seed:
        print("\n=== Seeding local stores ===")
        asyncio.run(seed(data))


if __name__ == "__main__":
    main()
