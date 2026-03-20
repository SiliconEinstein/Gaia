#!/usr/bin/env python3
"""Build Graph IR from a Gaia Language package (YAML or Typst).

Reads package.yaml (YAML path) or typst.toml (Typst path), generates:
  graph_ir/raw_graph.json
  graph_ir/local_canonical_graph.json
  graph_ir/canonicalization_log.json
  graph_ir/local_parameterization.json

Usage:
    python scripts/pipeline/build_graph_ir.py tests/fixtures/gaia_language_packages/galileo_falling_bodies
    python scripts/pipeline/build_graph_ir.py tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst
    python scripts/pipeline/build_graph_ir.py tests/fixtures/gaia_language_packages/*
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.graph_ir.build import (
    CanonicalizationResult,
    build_raw_graph,
    build_singleton_local_graph,
    derive_local_parameterization,
    derive_local_parameterization_from_raw,
)
from libs.graph_ir.models import LocalParameterization, RawGraph
from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph
from libs.lang.loader import load_package
from libs.lang.typst_loader import load_typst_package


def _write_graph_ir_outputs(
    pkg_dir: Path,
    raw_graph: RawGraph,
    result: CanonicalizationResult,
    params: LocalParameterization,
) -> None:
    """Write the standard set of graph_ir/ output files."""
    local_graph = result.local_graph

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


def _print_summary(raw_graph) -> None:
    """Print a summary of the built graph."""
    types = Counter(n.knowledge_type for n in raw_graph.knowledge_nodes)
    factor_types = Counter(f.type for f in raw_graph.factor_nodes)
    print(
        f"  OK: {len(raw_graph.knowledge_nodes)} nodes ({dict(types)}), "
        f"{len(raw_graph.factor_nodes)} factors ({dict(factor_types)})"
    )


def _build_from_yaml(pkg_dir: Path) -> bool:
    """Build Graph IR from a YAML package. Returns True on success."""
    pkg = load_package(pkg_dir)
    raw_graph = build_raw_graph(pkg)
    result = build_singleton_local_graph(raw_graph)
    params = derive_local_parameterization(pkg, result.local_graph)

    _write_graph_ir_outputs(pkg_dir, raw_graph, result, params)
    _print_summary(raw_graph)
    return True


def _build_from_typst(pkg_dir: Path) -> bool:
    """Build Graph IR from a Typst package. Returns True on success."""
    graph_data = load_typst_package(pkg_dir)
    raw_graph = compile_typst_to_raw_graph(graph_data)
    result = build_singleton_local_graph(raw_graph)
    params = derive_local_parameterization_from_raw(raw_graph, result.local_graph)

    _write_graph_ir_outputs(pkg_dir, raw_graph, result, params)
    _print_summary(raw_graph)
    return True


def build_package_graph_ir(pkg_dir: Path) -> bool:
    """Build Graph IR for a single package. Returns True on success.

    Detects package type by presence of typst.toml (Typst) or package.yaml (YAML).
    """
    has_typst = (pkg_dir / "typst.toml").exists()
    has_yaml = (pkg_dir / "package.yaml").exists()

    if has_typst:
        return _build_from_typst(pkg_dir)
    elif has_yaml:
        return _build_from_yaml(pkg_dir)
    else:
        print(f"  SKIP: no package.yaml or typst.toml in {pkg_dir.name}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build Graph IR from a Gaia package")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    args = parser.parse_args()

    succeeded = 0
    failed = []
    for pkg_dir in args.pkg_dirs:
        if not pkg_dir.is_dir():
            continue
        print(f"Processing: {pkg_dir.name}")
        try:
            if build_package_graph_ir(pkg_dir):
                succeeded += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append(pkg_dir.name)

    total = succeeded + len(failed)
    print(f"\nDone: {succeeded}/{total} packages.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
