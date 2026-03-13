#!/usr/bin/env python3
"""Upload v2 fixtures to LanceDB + graph store, then print what was stored.

Usage:
    # Upload all paper fixtures (default)
    python scripts/upload_v2_fixtures.py

    # Upload from a specific fixture directory
    python scripts/upload_v2_fixtures.py --fixtures-dir tests/fixtures/remote_lancedb/v2

    # Upload a single package slug
    python scripts/upload_v2_fixtures.py paper_363056a0

    # Override storage config via env vars
    GAIA_LANCEDB_PATH=./data/lancedb/gaia_v2 python scripts/upload_v2_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager
from libs.storage.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    Module,
    Package,
    ProbabilityRecord,
)

DEFAULT_FIXTURES_DIR = Path("tests/fixtures/storage/papers")


def load_fixture(fixtures_dir: Path, slug: str) -> dict:
    d = fixtures_dir / slug
    data = {
        "package": Package.model_validate_json((d / "package.json").read_text()),
        "modules": [Module.model_validate(m) for m in json.loads((d / "modules.json").read_text())],
        "knowledge": [
            Knowledge.model_validate(k) for k in json.loads((d / "knowledge.json").read_text())
        ],
        "chains": [Chain.model_validate(c) for c in json.loads((d / "chains.json").read_text())],
        "probabilities": [
            ProbabilityRecord.model_validate(p)
            for p in json.loads((d / "probabilities.json").read_text())
        ],
        "beliefs": [
            BeliefSnapshot.model_validate(b) for b in json.loads((d / "beliefs.json").read_text())
        ],
    }
    # Optional: embeddings
    emb_path = d / "embeddings.json"
    if emb_path.exists():
        from libs.storage.models import KnowledgeEmbedding

        data["embeddings"] = [
            KnowledgeEmbedding.model_validate(e) for e in json.loads(emb_path.read_text())
        ]
    else:
        data["embeddings"] = []
    return data


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Upload v2 fixtures to storage")
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help=f"Directory containing package subdirectories (default: {DEFAULT_FIXTURES_DIR})",
    )
    parser.add_argument("slugs", nargs="*", help="Specific package slugs to upload (default: all)")
    args = parser.parse_args()

    fixtures_dir = args.fixtures_dir
    if args.slugs:
        slugs = args.slugs
    else:
        slugs = sorted([d.name for d in fixtures_dir.iterdir() if d.is_dir()])

    if not slugs:
        print("ERROR: No fixture directories found in", fixtures_dir)
        sys.exit(1)

    print(f"Fixtures dir : {fixtures_dir}")
    print(f"Packages     : {slugs}")

    # Initialize StorageManager from env / defaults
    config = StorageConfig()
    print(f"LanceDB path : {config.lancedb_path}")
    print(f"Graph backend : {config.graph_backend}")
    if config.graph_backend == "neo4j":
        print(f"Neo4j URI     : {config.neo4j_uri}")
        print(f"Neo4j database: {config.neo4j_database}")

    mgr = StorageManager(config)
    await mgr.initialize()
    print("Storage initialized.\n")

    # ── Upload ──
    for slug in slugs:
        print_section(f"Uploading: {slug}")
        data = load_fixture(fixtures_dir, slug)
        pkg = data["package"]
        modules = data["modules"]
        knowledge = data["knowledge"]
        chains = data["chains"]

        print(f"  Package : {pkg.package_id} v{pkg.version}")
        print(f"  Modules : {len(modules)}")
        print(f"  Knowledge: {len(knowledge)}")
        print(f"  Chains  : {len(chains)}")
        print(f"  Probs   : {len(data['probabilities'])}")
        print(f"  Beliefs : {len(data['beliefs'])}")

        await mgr.ingest_package(
            package=pkg,
            modules=modules,
            knowledge_items=knowledge,
            chains=chains,
            embeddings=data.get("embeddings") or None,
        )
        if data["probabilities"]:
            await mgr.add_probabilities(data["probabilities"])
        if data["beliefs"]:
            await mgr.write_beliefs(data["beliefs"])

        print(f"  ✓ Ingested {slug}")

    # ── Read back and print ──
    for slug in slugs:
        data = load_fixture(fixtures_dir, slug)
        pkg_id = data["package"].package_id

        print_section(f"Stored: {slug}")

        # Package
        pkg = await mgr.get_package(pkg_id)
        if pkg:
            print(f"\n  [Package] {pkg.package_id}")
            print(f"    version : {pkg.version}")
            print(f"    status  : {pkg.status}")
            print(f"    modules : {pkg.modules}")
            print(f"    exports : {len(pkg.exports)} items")
        else:
            print(f"\n  [Package] {pkg_id} — NOT FOUND")
            continue

        # Modules
        for m_data in data["modules"]:
            m = await mgr.get_module(m_data.module_id)
            if m:
                print(f"\n  [Module] {m.module_id}")
                print(f"    role     : {m.role}")
                print(f"    chains   : {len(m.chain_ids)}")
                print(f"    exports  : {len(m.export_ids)}")

        # Knowledge (summary)
        print(f"\n  [Knowledge] {len(data['knowledge'])} items:")
        for k_data in data["knowledge"]:
            k = await mgr.get_knowledge(k_data.knowledge_id)
            if k:
                content_preview = k.content[:80].replace("\n", " ")
                print(f"    • {k.knowledge_id} (v{k.version}, prior={k.prior})")
                print(f"      {content_preview}...")

        # Chains
        for m_data in data["modules"]:
            chains = await mgr.get_chains_by_module(m_data.module_id)
            print(f"\n  [Chains] {len(chains)} chains in {m_data.module_id}:")
            for ch in chains:
                print(f"    • {ch.chain_id} ({ch.type}, {len(ch.steps)} steps)")
                for step in ch.steps[:3]:  # first 3 steps
                    reasoning_preview = step.reasoning[:60].replace("\n", " ")
                    prem_ids = [p.knowledge_id.split("/")[-1] for p in step.premises]
                    print(
                        f"      step {step.step_index}: [{', '.join(prem_ids)}] → {reasoning_preview}"
                    )
                if len(ch.steps) > 3:
                    print(f"      ... and {len(ch.steps) - 3} more steps")

        # Probabilities (sample)
        if data["chains"]:
            first_chain_id = data["chains"][0].chain_id
            probs = await mgr.get_probability_history(first_chain_id)
            print(f"\n  [Probabilities] {len(probs)} records for {first_chain_id}:")
            for p in probs[:5]:
                print(f"    step {p.step_index}: {p.value} (source={p.source})")

        # Beliefs (sample)
        if data["knowledge"]:
            first_kid = data["knowledge"][0].knowledge_id
            beliefs = await mgr.get_belief_history(first_kid)
            print(f"\n  [Beliefs] {len(beliefs)} records for {first_kid}:")
            for b in beliefs:
                print(f"    v{b.version}: belief={b.belief} (run={b.bp_run_id})")

    # Graph topology sample (if available)
    if mgr.graph_store is not None:
        print_section("Graph Topology Sample")
        # Use a conclusion node as seed — it connects to more premises via chains
        for slug in slugs:
            data = load_fixture(fixtures_dir, slug)
            if not data["chains"]:
                continue
            # Pick the conclusion of the first chain (richest connectivity)
            first_chain = data["chains"][0]
            sample_kid = first_chain.steps[-1].conclusion.knowledge_id
            sub = await mgr.get_subgraph(sample_kid, max_knowledge=50)
            print(f"\n  [{slug}] Subgraph from {sample_kid}:")
            print(f"    knowledge_ids: {len(sub.knowledge_ids)}")
            print(f"    chain_ids    : {len(sub.chain_ids)}")
            for kid in sorted(sub.knowledge_ids):
                print(f"      • {kid}")

    await mgr.close()
    print("\n✓ Done.")


if __name__ == "__main__":
    asyncio.run(main())
