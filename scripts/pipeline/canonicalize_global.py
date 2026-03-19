#!/usr/bin/env python3
"""Canonicalize packages into a shared global graph.

Reads each package's graph_ir/local_canonical_graph.json +
local_parameterization.json, maps local nodes to global nodes,
saves global_graph/global_graph.json.

Usage:
    python scripts/pipeline/canonicalize_global.py \
        tests/fixtures/gaia_language_packages/galileo_falling_bodies \
        tests/fixtures/gaia_language_packages/newton_principia \
        -o tests/fixtures/global_graph

    # With embedding service (env: API_URL, ACCESS_KEY)
    python scripts/pipeline/canonicalize_global.py ... --use-embedding
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.global_graph.canonicalize import canonicalize_package  # noqa: E402
from libs.global_graph.serialize import load_global_graph, save_global_graph  # noqa: E402
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(description="Canonicalize packages into global graph")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("global_graph"),
        help="Output directory for global graph (default: global_graph/)",
    )
    parser.add_argument(
        "--use-embedding",
        action="store_true",
        help="Use DP embedding service (requires API_URL and ACCESS_KEY env vars)",
    )
    args = parser.parse_args()

    # Load embedding model if requested
    embedding_model = None
    if args.use_embedding:
        from libs.embedding import DPEmbeddingModel

        embedding_model = DPEmbeddingModel()
        print("Using DP embedding service for similarity matching")
    else:
        print("Using TF-IDF fallback for similarity matching")

    global_graph_path = args.output_dir / "global_graph.json"
    global_graph = load_global_graph(global_graph_path)
    print(f"Loaded global graph: {len(global_graph.knowledge_nodes)} existing nodes")

    for pkg_dir in args.pkg_dirs:
        graph_ir_dir = pkg_dir / "graph_ir"
        lcg_path = graph_ir_dir / "local_canonical_graph.json"
        params_path = graph_ir_dir / "local_parameterization.json"

        if not lcg_path.exists():
            print(f"  SKIP {pkg_dir.name}: no local_canonical_graph.json")
            continue
        if not params_path.exists():
            print(f"  SKIP {pkg_dir.name}: no local_parameterization.json")
            continue

        local_graph = LocalCanonicalGraph.model_validate_json(lcg_path.read_text())
        local_params = LocalParameterization.model_validate_json(params_path.read_text())

        print(f"Processing: {pkg_dir.name} ({len(local_graph.knowledge_nodes)} local nodes)")
        result = await canonicalize_package(
            local_graph,
            local_params,
            global_graph,
            embedding_model=embedding_model,
        )

        for gcn in result.new_global_nodes:
            global_graph.add_node(gcn)
        global_graph.bindings.extend(result.bindings)
        # Deduplicate factors by factor_id (re-canonicalizing a package produces same IDs)
        existing_fids = {f.factor_id for f in global_graph.factor_nodes}
        for f in result.global_factors:
            if f.factor_id not in existing_fids:
                global_graph.factor_nodes.append(f)
                existing_fids.add(f.factor_id)

        created = sum(1 for b in result.bindings if b.decision == "create_new")
        matched = sum(1 for b in result.bindings if b.decision == "match_existing")
        n_factors = len(result.global_factors)
        n_unresolved = len(result.unresolved_cross_refs)
        print(f"  -> {created} new, {matched} matched, {n_factors} factors")
        if n_unresolved:
            print(f"     {n_unresolved} unresolved cross-package refs")

    save_global_graph(global_graph, args.output_dir)
    print(
        f"\nGlobal graph: {len(global_graph.knowledge_nodes)} nodes, "
        f"{len(global_graph.factor_nodes)} factors, "
        f"{len(global_graph.bindings)} bindings"
    )
    print(f"Saved to: {args.output_dir / 'global_graph.json'}")


if __name__ == "__main__":
    asyncio.run(main())
