#!/usr/bin/env python3
"""Build Graph IR from a Gaia Language YAML package.

Reads package.yaml + module YAMLs, generates:
  graph_ir/raw_graph.json
  graph_ir/local_canonical_graph.json
  graph_ir/canonicalization_log.json
  graph_ir/local_parameterization.json

Usage:
    python scripts/pipeline/build_graph_ir.py tests/fixtures/gaia_language_packages/galileo_falling_bodies
    python scripts/pipeline/build_graph_ir.py tests/fixtures/gaia_language_packages/*
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.graph_ir.build import (
    build_raw_graph,
    build_singleton_local_graph,
    derive_local_parameterization,
)
from libs.lang.loader import load_package


def build_package_graph_ir(pkg_dir: Path) -> bool:
    """Build Graph IR for a single package. Returns True on success."""
    package_yaml = pkg_dir / "package.yaml"
    if not package_yaml.exists():
        print(f"  SKIP: no package.yaml in {pkg_dir.name}")
        return False

    pkg = load_package(pkg_dir)
    raw_graph = build_raw_graph(pkg)
    result = build_singleton_local_graph(raw_graph)
    local_graph = result.local_graph
    params = derive_local_parameterization(pkg, local_graph)

    graph_dir = pkg_dir / "graph_ir"
    graph_dir.mkdir(exist_ok=True)

    (graph_dir / "raw_graph.json").write_text(
        json.dumps(raw_graph.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    )
    (graph_dir / "local_canonical_graph.json").write_text(
        json.dumps(
            local_graph.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
        )
    )
    (graph_dir / "canonicalization_log.json").write_text(
        json.dumps(
            {"canonicalization_log": [e.model_dump(mode="json") for e in result.log]},
            ensure_ascii=False,
            indent=2,
        )
    )
    (graph_dir / "local_parameterization.json").write_text(
        json.dumps(params.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    )

    # Summary
    from collections import Counter

    types = Counter(n.knowledge_type for n in raw_graph.knowledge_nodes)
    factor_types = Counter(f.type for f in raw_graph.factor_nodes)
    print(
        f"  OK: {len(raw_graph.knowledge_nodes)} nodes ({dict(types)}), "
        f"{len(raw_graph.factor_nodes)} factors ({dict(factor_types)})"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Build Graph IR from YAML package")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    args = parser.parse_args()

    succeeded = 0
    for pkg_dir in args.pkg_dirs:
        if not pkg_dir.is_dir():
            continue
        print(f"Processing: {pkg_dir.name}")
        if build_package_graph_ir(pkg_dir):
            succeeded += 1

    print(f"\nDone: {succeeded}/{len(args.pkg_dirs)} packages.")


if __name__ == "__main__":
    main()
