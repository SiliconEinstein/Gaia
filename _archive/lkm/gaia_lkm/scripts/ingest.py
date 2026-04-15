"""Ingest data into LKM via Pipeline A (Gaia IR) and Pipeline B (Paper XML).

Usage:
    # Ingest Gaia IR packages
    python -m gaia.lkm.scripts.ingest --pipeline a --source tests/fixtures/ir/galileo_falling_bodies_v4/gaia_ir_fine

    # Ingest paper XMLs
    python -m gaia.lkm.scripts.ingest --pipeline b --source tests/fixtures/inputs/papers/363056a0

    # Ingest all fixtures (for demo/testing)
    python -m gaia.lkm.scripts.ingest --all

    # Custom database path
    python -m gaia.lkm.scripts.ingest --all --db-path ./data/lancedb/lkm
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from gaia.lkm.core.integrate import integrate
from gaia.lkm.storage import StorageConfig, StorageManager


# ── Default fixture paths ──

GAIA_IR_PACKAGES = [
    ("galileo_falling_bodies_v4", "4.0.0"),
    ("einstein_gravity_v4", "4.0.0"),
    ("newton_principia_v4", "4.0.0"),
    ("dark_energy_v4", "1.0.0"),
]

PAPER_DIRS = [
    "10.1038332139a0_1988_Natu",
    "363056a0",
    "10.1038s41467-021-25372-2",
    "Sak-1977",
    "2512_Superconductivity",
]


async def ingest_gaia_ir(storage: StorageManager, ir_dir: Path, version: str) -> None:
    """Pipeline A: Gaia IR → lower → integrate."""
    import json

    from gaia.ir.graphs import LocalCanonicalGraph
    from gaia.lkm.core.lower import lower

    graph_path = ir_dir / "local_canonical_graph.json"
    with open(graph_path, encoding="utf-8") as f:
        data = json.load(f)

    graph = LocalCanonicalGraph.model_validate(data)
    lowered = lower(graph, version=version)

    result = await integrate(
        storage,
        lowered.package_id,
        lowered.version,
        lowered.local_variables,
        lowered.local_factors,
    )

    match_count = sum(1 for b in result.bindings if b.decision == "match_existing")
    create_count = sum(1 for b in result.bindings if b.decision == "create_new")
    print(
        f"  [A] {lowered.package_id}@{version}: "
        f"{len(lowered.local_variables)}V {len(lowered.local_factors)}F → "
        f"{create_count} new, {match_count} dedup"
    )


async def ingest_paper(storage: StorageManager, paper_dir: Path) -> None:
    """Pipeline B: Paper XML → extract → integrate."""
    from gaia.lkm.core.extract import extract

    metadata_id = paper_dir.name
    review_xml = (paper_dir / "review.xml").read_text(encoding="utf-8")
    reasoning_xml = (paper_dir / "reasoning_chain.xml").read_text(encoding="utf-8")
    select_xml = (paper_dir / "select_conclusion.xml").read_text(encoding="utf-8")

    extracted = extract(review_xml, reasoning_xml, select_xml, metadata_id)

    result = await integrate(
        storage,
        extracted.package_id,
        extracted.version,
        extracted.local_variables,
        extracted.local_factors,
        extracted.prior_records,
        extracted.factor_param_records,
        param_sources=extracted.param_sources,
    )

    match_count = sum(1 for b in result.bindings if b.decision == "match_existing")
    create_count = sum(1 for b in result.bindings if b.decision == "create_new")
    print(
        f"  [B] paper:{metadata_id}: "
        f"{len(extracted.local_variables)}V {len(extracted.local_factors)}F "
        f"{len(extracted.prior_records)} priors → "
        f"{create_count} new, {match_count} dedup"
    )


async def ingest_all(db_path: str) -> None:
    """Ingest all fixture data via Pipeline A and B."""
    config = StorageConfig(lancedb_path=db_path)
    storage = StorageManager(config)
    await storage.initialize()

    fixtures_root = Path("tests/fixtures")

    # Pipeline A: Gaia IR packages
    print("Pipeline A (Gaia IR):")
    for pkg_dir, version in GAIA_IR_PACKAGES:
        ir_dir = fixtures_root / "ir" / pkg_dir / "gaia_ir_fine"
        await ingest_gaia_ir(storage, ir_dir, version)

    # Pipeline B: Paper XMLs
    print("\nPipeline B (Paper XML):")
    papers_root = fixtures_root / "inputs" / "papers"
    for paper_name in PAPER_DIRS:
        paper_dir = papers_root / paper_name
        if (paper_dir / "review.xml").exists():
            await ingest_paper(storage, paper_dir)

    # Print final stats
    print("\n--- Final counts ---")
    for t in [
        "local_variable_nodes",
        "global_variable_nodes",
        "local_factor_nodes",
        "global_factor_nodes",
        "canonical_bindings",
        "prior_records",
        "param_sources",
    ]:
        count = await storage.content.count(t)
        print(f"  {t}: {count}")


async def ingest_single(db_path: str, pipeline: str, source: str, version: str) -> None:
    """Ingest a single source via specified pipeline."""
    config = StorageConfig(lancedb_path=db_path)
    storage = StorageManager(config)
    await storage.initialize()

    source_path = Path(source)
    if pipeline == "a":
        await ingest_gaia_ir(storage, source_path, version)
    elif pipeline == "b":
        await ingest_paper(storage, source_path)
    else:
        raise ValueError(f"Unknown pipeline: {pipeline}")


def main():
    parser = argparse.ArgumentParser(description="Ingest data into LKM")
    parser.add_argument("--db-path", default="./data/lancedb/lkm", help="LanceDB path")
    parser.add_argument("--all", action="store_true", help="Ingest all fixtures")
    parser.add_argument("--pipeline", choices=["a", "b"], help="Pipeline to run")
    parser.add_argument("--source", help="Source directory path")
    parser.add_argument("--version", default="1.0.0", help="Package version (Pipeline A only)")
    parser.add_argument("--clean", action="store_true", help="Delete existing DB before ingest")
    args = parser.parse_args()

    if args.clean:
        import shutil

        shutil.rmtree(args.db_path, ignore_errors=True)
        print(f"Cleaned {args.db_path}")

    if args.all:
        print(f"Ingesting all fixtures into {args.db_path}...")
        asyncio.run(ingest_all(args.db_path))
    elif args.pipeline and args.source:
        asyncio.run(ingest_single(args.db_path, args.pipeline, args.source, args.version))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
