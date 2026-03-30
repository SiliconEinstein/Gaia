#!/usr/bin/env python3
"""Run local belief propagation on a package's Graph IR.

Reads graph_ir/local_canonical_graph.json + local_parameterization.json,
runs BP via gaia.bp.InferenceEngine (auto-selects JT/GBP/loopy-BP),
writes graph_ir/local_beliefs.json.

The --target-model flag switches reasoning factors from the current
ENTAILMENT (silence) model to the target INDUCTION (noisy-AND + leak)
model per docs/foundations/bp/potentials.md.

Usage:
    python scripts/pipeline/run_local_bp.py tests/fixtures/gaia_language_packages/galileo_coarse_v4
    python scripts/pipeline/run_local_bp.py --target-model tests/fixtures/gaia_language_packages/*
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gaia.bp.engine import InferenceEngine
from gaia.bp.factor_graph import FactorGraph, FactorType
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization

# Mapping from graph_ir factor.type to gaia.bp FactorType.
# potentials.md "当前实现": all reasoning factors use ENTAILMENT (silence).
# potentials.md "目标模型": all reasoning factors use INDUCTION (noisy-AND + leak).
_CURRENT_MAP: dict[str, FactorType] = {
    "infer": FactorType.ENTAILMENT,
    "deduction": FactorType.ENTAILMENT,
    "abstraction": FactorType.ENTAILMENT,
    "contradiction": FactorType.CONTRADICTION,
    "equivalence": FactorType.EQUIVALENCE,
}
_TARGET_MAP: dict[str, FactorType] = {
    "infer": FactorType.INDUCTION,
    "deduction": FactorType.INDUCTION,
    "abstraction": FactorType.INDUCTION,
    "contradiction": FactorType.CONTRADICTION,
    "equivalence": FactorType.EQUIVALENCE,
}


def run_bp_on_package(
    pkg_dir: Path,
    *,
    target_model: bool = False,
    output_suffix: str = "",
) -> bool:
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
    type_map = _TARGET_MAP if target_model else _CURRENT_MAP
    model_label = "target (noisy-AND)" if target_model else "current (silence)"

    fg = FactorGraph()

    for node in lcg.knowledge_nodes:
        nid = node.local_canonical_id
        fg.add_variable(nid, params.node_priors.get(nid, 0.5))

    for factor in lcg.factor_nodes:
        all_refs = (
            factor.premises + factor.contexts + ([factor.conclusion] if factor.conclusion else [])
        )
        if any(r.startswith("ext:") for r in all_refs):
            continue

        premises = [p for p in factor.premises if p in fg.variables]
        if not premises:
            continue

        cp = params.factor_parameters.get(factor.factor_id)
        prob = cp.conditional_probability if cp else 1.0

        bp_type = type_map.get(factor.type)
        if bp_type is None:
            continue

        if factor.type in ("contradiction", "equivalence"):
            conclusion_id = factor.conclusion
            fg.add_factor(
                factor_id=factor.factor_id,
                factor_type=bp_type,
                premises=premises,
                conclusions=[],
                p=1.0,
                relation_var=conclusion_id,
            )
        else:
            conclusion = factor.conclusion
            if conclusion and conclusion in fg.variables:
                fg.add_factor(
                    factor_id=factor.factor_id,
                    factor_type=bp_type,
                    premises=premises,
                    conclusions=[conclusion],
                    p=prob,
                )

    engine = InferenceEngine()
    result = engine.run(fg)
    print(
        f"  BP ({model_label}): method={result.method_used}, "
        f"treewidth={result.treewidth}, exact={result.is_exact}, "
        f"{result.elapsed_ms:.1f}ms"
    )

    belief_map = {k: round(v, 6) for k, v in result.beliefs.items()}

    for node in lcg.knowledge_nodes:
        nid = node.local_canonical_id
        name = node.source_refs[0].knowledge_name if node.source_refs else nid[:16]
        prior = params.node_priors.get(nid, 0.5)
        b = belief_map.get(nid, prior)
        delta = b - prior
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "="
        print(f"  {arrow} {name:40} prior={prior:.3f} -> belief={b:.3f} ({delta:+.3f})")

    filename = f"local_beliefs{output_suffix}.json"
    output = {"graph_hash": lcg.graph_hash(), "node_beliefs": belief_map}
    (graph_dir / filename).write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2)
    )
    print(f"  -> {graph_dir.name}/{filename}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run local BP on package Graph IR")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    parser.add_argument(
        "--target-model",
        action="store_true",
        help="Use target model (INDUCTION/noisy-AND) instead of current (ENTAILMENT/silence)",
    )
    parser.add_argument(
        "--output-suffix",
        default="",
        help="Suffix for output filename (e.g. '_target' -> local_beliefs_target.json)",
    )
    args = parser.parse_args()

    succeeded = 0
    for pkg_dir in args.pkg_dirs:
        if not pkg_dir.is_dir():
            continue
        print(f"Processing: {pkg_dir.name}")
        try:
            if run_bp_on_package(
                pkg_dir,
                target_model=args.target_model,
                output_suffix=args.output_suffix,
            ):
                succeeded += 1
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"  ERROR: {e}")

    print(f"\nDone: {succeeded}/{len(args.pkg_dirs)} packages.")


if __name__ == "__main__":
    main()
