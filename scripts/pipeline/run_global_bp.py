#!/usr/bin/env python3
"""Run belief propagation on the global canonical graph.

Reads global_graph/global_graph.json, collects priors from each package's
local_parameterization.json, runs BP, saves beliefs back to global graph.

Usage:
    python scripts/pipeline/run_global_bp.py tests/fixtures/global_graph \
        --packages-dir tests/fixtures/gaia_language_packages
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.global_graph.models import GlobalGraph
from libs.global_graph.serialize import load_global_graph, save_global_graph
from libs.graph_ir.models import FactorParams, LocalParameterization
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph


def _collect_priors(
    global_graph: GlobalGraph, packages_dir: Path
) -> tuple[dict[str, float], dict[str, float]]:
    """Collect node priors and factor conditional_probabilities from local parameterizations.

    For nodes with multiple contributing packages, takes weighted average of priors.
    """
    node_priors: dict[str, list[float]] = {}
    factor_params: dict[str, float] = {}

    # Load each package's local parameterization
    for binding in global_graph.bindings:
        pkg_dir = packages_dir / binding.package
        params_path = pkg_dir / "graph_ir" / "local_parameterization.json"
        if not params_path.exists():
            continue
        local_params = LocalParameterization.model_validate_json(params_path.read_text())

        # Map local prior to global node
        gcn_id = binding.global_canonical_id
        local_prior = local_params.node_priors.get(binding.local_canonical_id)
        if local_prior is not None:
            node_priors.setdefault(gcn_id, []).append(local_prior)

    # Collect factor conditional_probabilities
    pkg_params_cache: dict[str, LocalParameterization] = {}
    for factor in global_graph.factor_nodes:
        if factor.type != "reasoning" or factor.source_ref is None:
            continue
        pkg_name = factor.source_ref.package
        if pkg_name not in pkg_params_cache:
            params_path = packages_dir / pkg_name / "graph_ir" / "local_parameterization.json"
            if params_path.exists():
                pkg_params_cache[pkg_name] = LocalParameterization.model_validate_json(
                    params_path.read_text()
                )
        local_params = pkg_params_cache.get(pkg_name)
        if local_params and factor.factor_id in local_params.factor_parameters:
            factor_params[factor.factor_id] = local_params.factor_parameters[
                factor.factor_id
            ].conditional_probability

    # Average priors for multi-package nodes
    averaged_priors = {gcn_id: sum(ps) / len(ps) for gcn_id, ps in node_priors.items()}

    return averaged_priors, factor_params


def run_global_bp(
    global_graph_dir: Path,
    packages_dir: Path,
    damping: float = 0.3,
    max_iter: int = 100,
) -> None:
    global_graph_path = global_graph_dir / "global_graph.json"
    global_graph = load_global_graph(global_graph_path)

    if not global_graph.knowledge_nodes:
        print("Empty global graph, nothing to do.")
        return

    print(
        f"Global graph: {len(global_graph.knowledge_nodes)} nodes, "
        f"{len(global_graph.factor_nodes)} factors"
    )

    # Collect priors from local parameterizations
    node_priors, factor_params = _collect_priors(global_graph, packages_dir)
    print(f"Collected priors: {len(node_priors)} nodes, {len(factor_params)} factors")

    # Build FactorGraph
    fg = FactorGraph()
    id_to_int: dict[str, int] = {}
    int_to_id: dict[int, str] = {}

    for i, node in enumerate(global_graph.knowledge_nodes):
        gcn_id = node.global_canonical_id
        id_to_int[gcn_id] = i
        int_to_id[i] = gcn_id
        prior = node_priors.get(gcn_id, 0.5)
        fg.add_variable(i, prior)

    for fi, factor in enumerate(global_graph.factor_nodes):
        premises_int = [id_to_int[p] for p in factor.premises if p in id_to_int]
        conclusion_int = id_to_int.get(factor.conclusion)
        if conclusion_int is None or not premises_int:
            continue

        edge_type = (factor.metadata or {}).get("edge_type", "deduction")
        prob = factor_params.get(factor.factor_id, 0.5)

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

    # Map back and display
    belief_map = {int_to_id[k]: round(v, 6) for k, v in beliefs.items()}

    for node in global_graph.knowledge_nodes:
        gcn_id = node.global_canonical_id
        meta = node.metadata or {}
        source_names = meta.get("source_knowledge_names", [])
        name = source_names[0].split(".")[-1] if source_names else gcn_id[:16]
        pkgs = [p.package for p in (node.provenance or [])]
        prior = node_priors.get(gcn_id, 0.5)
        b = belief_map.get(gcn_id, prior)
        delta = b - prior
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "="
        print(
            f"  {arrow} {name:40} prior={prior:.3f} -> belief={b:.3f} ({delta:+.3f}) [{','.join(pkgs)}]"
        )

    # Save beliefs into global graph inference state
    global_graph.inference_state.node_priors = node_priors
    global_graph.inference_state.factor_parameters = {
        k: FactorParams(conditional_probability=v) for k, v in factor_params.items()
    }
    global_graph.inference_state.node_beliefs = belief_map
    save_global_graph(global_graph, global_graph_dir)
    print(f"\nSaved global beliefs to {global_graph_path}")


def main():
    parser = argparse.ArgumentParser(description="Run global BP on canonical graph")
    parser.add_argument("global_graph_dir", type=Path, help="Directory with global_graph.json")
    parser.add_argument(
        "--packages-dir",
        type=Path,
        default=Path("tests/fixtures/gaia_language_packages"),
        help="Directory containing package fixtures",
    )
    parser.add_argument("--damping", type=float, default=0.3)
    parser.add_argument("--max-iter", type=int, default=100)
    args = parser.parse_args()

    run_global_bp(args.global_graph_dir, args.packages_dir, args.damping, args.max_iter)


if __name__ == "__main__":
    main()
