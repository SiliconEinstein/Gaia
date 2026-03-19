#!/usr/bin/env python3
"""Run local belief propagation on a package's Graph IR.

Reads graph_ir/local_canonical_graph.json + local_parameterization.json,
runs loopy BP, writes graph_ir/local_beliefs.json.

Usage:
    python scripts/run_local_bp.py tests/fixtures/gaia_language_packages/galileo_falling_bodies
    python scripts/run_local_bp.py tests/fixtures/gaia_language_packages/*
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph


def run_bp_on_package(pkg_dir: Path, damping: float = 0.3, max_iter: int = 100) -> bool:
    """Run BP on a single package. Returns True if beliefs were written."""
    graph_dir = pkg_dir / "graph_ir"
    lcg_path = graph_dir / "local_canonical_graph.json"
    params_path = graph_dir / "local_parameterization.json"

    if not lcg_path.exists():
        print(f"  SKIP: no local_canonical_graph.json in {pkg_dir.name}")
        return False
    if not params_path.exists():
        print(f"  SKIP: no local_parameterization.json in {pkg_dir.name}")
        return False

    lcg = LocalCanonicalGraph.model_validate_json(lcg_path.read_text())
    params = LocalParameterization.model_validate_json(params_path.read_text())

    # Build FactorGraph: map string IDs to int IDs for BP engine
    fg = FactorGraph()
    id_to_int: dict[str, int] = {}
    int_to_id: dict[int, str] = {}

    for i, node in enumerate(lcg.knowledge_nodes):
        nid = node.local_canonical_id
        id_to_int[nid] = i
        int_to_id[i] = nid
        fg.add_variable(i, params.node_priors.get(nid, 0.5))

    for fi, factor in enumerate(lcg.factor_nodes):
        # Skip factors with ext: cross-package refs (not resolvable in local BP)
        all_refs = factor.premises + factor.contexts + [factor.conclusion]
        if any(r.startswith("ext:") for r in all_refs):
            continue
        premises_int = [id_to_int[p] for p in factor.premises if p in id_to_int]
        conclusion_int = id_to_int.get(factor.conclusion)
        if conclusion_int is None or not premises_int:
            continue

        edge_type = (factor.metadata or {}).get("edge_type", "deduction")
        cp = params.factor_parameters.get(factor.factor_id)
        prob = cp.conditional_probability if cp else 0.5

        gate_var = None
        if factor.type in ("mutex_constraint", "equiv_constraint"):
            gate_var = conclusion_int
            edge_type = (
                "relation_contradiction"
                if factor.type == "mutex_constraint"
                else "relation_equivalence"
            )
            fg.add_factor(fi, premises_int, [], prob, edge_type, gate_var=gate_var)
        else:
            fg.add_factor(fi, premises_int, [conclusion_int], prob, edge_type)

    # Run BP
    bp = BeliefPropagation(damping=damping, max_iterations=max_iter)
    beliefs = bp.run(fg)

    # Map back to string IDs
    belief_map = {int_to_id[k]: round(v, 6) for k, v in beliefs.items()}

    # Print summary
    for node in lcg.knowledge_nodes:
        nid = node.local_canonical_id
        name = node.source_refs[0].knowledge_name if node.source_refs else nid[:16]
        prior = params.node_priors.get(nid, 0.5)
        b = belief_map.get(nid, prior)
        delta = b - prior
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "="
        print(f"  {arrow} {name:40} prior={prior:.3f} -> belief={b:.3f} ({delta:+.3f})")

    # Write beliefs
    output = {"graph_hash": lcg.graph_hash(), "node_beliefs": belief_map}
    (graph_dir / "local_beliefs.json").write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2)
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Run local BP on package Graph IR")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    parser.add_argument("--damping", type=float, default=0.3, help="BP damping (default: 0.3)")
    parser.add_argument(
        "--max-iter", type=int, default=100, help="Max BP iterations (default: 100)"
    )
    args = parser.parse_args()

    succeeded = 0
    for pkg_dir in args.pkg_dirs:
        if not pkg_dir.is_dir():
            continue
        print(f"Processing: {pkg_dir.name}")
        if run_bp_on_package(pkg_dir, args.damping, args.max_iter):
            succeeded += 1

    print(f"\nDone: {succeeded}/{len(args.pkg_dirs)} packages.")


if __name__ == "__main__":
    main()
