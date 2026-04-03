#!/usr/bin/env python3
"""Upload packages to LanceDB + graph store via the full pipeline or from JSON fixtures.

Two modes:
  pipeline (default) — run build→review→infer→publish on YAML packages
  fixtures           — load pre-built JSON fixture files (legacy, fast)

Usage:
    # Pipeline mode: run all YAML packages through the full pipeline
    python scripts/upload_fixtures.py

    # Pipeline mode: single package slug
    python scripts/upload_fixtures.py paper_10_1038332139a0_1988_natu

    # Pipeline mode: specific packages dir
    python scripts/upload_fixtures.py --packages-dir tests/fixtures/ir

    # Fixtures mode: load JSON fixtures (backward compat)
    python scripts/upload_fixtures.py --from-fixtures
    python scripts/upload_fixtures.py --from-fixtures --fixtures-dir tests/fixtures/storage/papers

    # Append mode (skip cleaning existing data)
    python scripts/upload_fixtures.py --no-clean

    # Override storage via env vars
    GAIA_LANCEDB_PATH=./data/lancedb/gaia python scripts/upload_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

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
    factors_from_chains,
)

DEFAULT_PACKAGES_DIR = Path("tests/fixtures/ir")
DEFAULT_FIXTURES_DIR = Path("tests/fixtures/storage/papers")


# ── Pipeline mode ──────────────────────────────────────────


async def run_pipeline_for_package(pkg_path: Path, mgr: StorageManager) -> dict:
    """Run full build→review→infer→publish for one YAML package, reusing mgr."""
    from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

    build = await pipeline_build(pkg_path)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, storage_manager=mgr)
    return result.stats


async def pipeline_mode(packages_dir: Path, slugs: list[str], clean: bool) -> None:
    """Upload YAML packages via the full Gaia Language pipeline."""
    if slugs:
        pkg_dirs = [packages_dir / s for s in slugs]
    else:
        pkg_dirs = sorted([d for d in packages_dir.iterdir() if d.is_dir()])

    if not pkg_dirs:
        print(f"ERROR: No package directories found in {packages_dir}")
        sys.exit(1)

    print(f"Packages dir : {packages_dir}")
    print(f"Packages     : {[d.name for d in pkg_dirs]}")

    config = StorageConfig()
    _print_config(config)

    if clean:
        _clean_storage(config)

    mgr = StorageManager(config)
    await mgr.initialize()
    print("Storage initialized.\n")

    try:
        for pkg_path in pkg_dirs:
            if not pkg_path.exists():
                print(f"  ERROR: {pkg_path} not found")
                continue
            print(f"  Running pipeline: {pkg_path.name} …")
            stats = await run_pipeline_for_package(pkg_path, mgr)
            print(
                f"  ✓ {pkg_path.name}: "
                f"{stats['knowledge_items']} knowledge, "
                f"{stats['chains']} chains, "
                f"{stats['factors']} factors"
            )
    finally:
        await mgr.close()

    print("\n✓ Done.")


# ── Fixtures mode (legacy) ─────────────────────────────────


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
    emb_path = d / "embeddings.json"
    if emb_path.exists():
        from libs.storage.models import KnowledgeEmbedding

        data["embeddings"] = [
            KnowledgeEmbedding.model_validate(e) for e in json.loads(emb_path.read_text())
        ]
    else:
        data["embeddings"] = []
    factors_path = d / "factors.json"
    if factors_path.exists():
        from libs.storage.models import FactorNode

        data["factors"] = [
            FactorNode.model_validate(f) for f in json.loads(factors_path.read_text())
        ]
    else:
        data["factors"] = factors_from_chains(data["chains"], data["package"].package_id)
    return data


async def fixtures_mode(fixtures_dir: Path, slugs: list[str], clean: bool) -> None:
    """Upload pre-built JSON fixtures (legacy path)."""
    if slugs:
        all_slugs = slugs
    else:
        all_slugs = sorted([d.name for d in fixtures_dir.iterdir() if d.is_dir()])

    if not all_slugs:
        print(f"ERROR: No fixture directories found in {fixtures_dir}")
        sys.exit(1)

    print(f"Fixtures dir : {fixtures_dir}")
    print(f"Packages     : {all_slugs}")

    config = StorageConfig()
    _print_config(config)

    if clean:
        _clean_storage(config)

    mgr = StorageManager(config)
    await mgr.initialize()
    print("Storage initialized.\n")

    try:
        for slug in all_slugs:
            print(f"  Uploading: {slug} …")
            data = load_fixture(fixtures_dir, slug)
            pkg = data["package"]
            await mgr.ingest_package(
                package=pkg,
                modules=data["modules"],
                knowledge_items=data["knowledge"],
                chains=data["chains"],
                embeddings=data.get("embeddings") or None,
                factors=data["factors"] or None,
            )
            if data["probabilities"]:
                await mgr.add_probabilities(data["probabilities"])
            if data["beliefs"]:
                await mgr.write_beliefs(data["beliefs"])
            print(
                f"  ✓ {slug}: "
                f"{len(data['knowledge'])} knowledge, "
                f"{len(data['chains'])} chains, "
                f"{len(data['factors'])} factors"
            )
    finally:
        await mgr.close()

    print("\n✓ Done.")


# ── Helpers ────────────────────────────────────────────────


def _print_config(config: StorageConfig) -> None:
    print(f"LanceDB path  : {config.lancedb_path}")
    print(f"Graph backend : {config.graph_backend}")
    if config.graph_backend == "neo4j":
        print(f"Neo4j URI     : {config.neo4j_uri}")
        print(f"Neo4j database: {config.neo4j_database}")


def _clean_storage(config: StorageConfig) -> None:
    import shutil

    lance_path = Path(config.lancedb_path)
    if lance_path.exists():
        shutil.rmtree(lance_path)
        print(f"  Cleaned LanceDB: {lance_path}")
    kuzu_path = (
        Path(config.kuzu_path)
        if config.kuzu_path
        else lance_path.parent / (lance_path.name + "_kuzu")
    )
    if kuzu_path.exists():
        if kuzu_path.is_dir():
            shutil.rmtree(kuzu_path)
        else:
            kuzu_path.unlink()
        print(f"  Cleaned Kuzu: {kuzu_path}")
    print()


# ── CLI ────────────────────────────────────────────────────


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Upload packages to storage")
    parser.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Load from pre-built JSON fixtures (legacy mode)",
    )
    parser.add_argument(
        "--packages-dir",
        type=Path,
        default=DEFAULT_PACKAGES_DIR,
        help=f"YAML packages directory (pipeline mode, default: {DEFAULT_PACKAGES_DIR})",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help=f"JSON fixtures directory (fixtures mode, default: {DEFAULT_FIXTURES_DIR})",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip cleaning existing data (append mode)",
    )
    parser.add_argument("slugs", nargs="*", help="Specific package slugs (default: all)")
    args = parser.parse_args()

    clean = not args.no_clean

    if args.from_fixtures:
        await fixtures_mode(args.fixtures_dir, args.slugs, clean)
    else:
        await pipeline_mode(args.packages_dir, args.slugs, clean)


if __name__ == "__main__":
    asyncio.run(main())
