#!/usr/bin/env python3
"""Convert graph_ir/ (old pipeline output) to gaia_ir/ (v2 spec) and run new BP engine.

Pipeline position:
    build_graph_ir.py  →  graph_ir/   (step 1, standard Typst compiler)
    build_gaia_ir.py   →  gaia_ir/    (step 2, THIS SCRIPT)

Reads:
    {pkg}/graph_ir/local_canonical_graph.json
    {pkg}/graph_ir/local_parameterization.json
    {pkg}/factor_params.json  (optional, maps conclusion-name → conditional_probability)

Writes:
    {pkg}/gaia_ir/local_canonical_graph.json
    {pkg}/gaia_ir/local_parameterization.json
    {pkg}/gaia_ir/local_belief_state.json

Usage:
    python scripts/pipeline/build_gaia_ir.py tests/fixtures/gaia_language_packages/galileo_coarse_v4
    python scripts/pipeline/build_gaia_ir.py tests/fixtures/gaia_language_packages/*
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gaia.bp import CROMWELL_EPS, FactorGraph, FactorType, InferenceEngine
from gaia.gaia_ir.belief_state import BeliefState
from gaia.gaia_ir.graphs import LocalCanonicalGraph as NewLocalCanonicalGraph
from gaia.gaia_ir.knowledge import Knowledge, KnowledgeType
from gaia.gaia_ir.operator import Operator, OperatorType
from gaia.gaia_ir.parameterization import PriorRecord, StrategyParamRecord
from gaia.gaia_ir.strategy import Strategy, StrategyType
from libs.graph_ir.models import LocalCanonicalGraph as OldLocalCanonicalGraph
from libs.graph_ir.models import LocalParameterization as OldLocalParameterization

_KNOWLEDGE_TYPE_MAP = {
    "claim": KnowledgeType.CLAIM,
    "setting": KnowledgeType.SETTING,
    "question": KnowledgeType.QUESTION,
    "contradiction": KnowledgeType.CLAIM,
    "equivalence": KnowledgeType.CLAIM,
    "action": KnowledgeType.CLAIM,
}

SOURCE_ID = "pipeline:build_gaia_ir"


def _knowledge_name(node) -> str:
    """Extract the knowledge_name from old-format node source_refs."""
    if node.source_refs:
        return node.source_refs[0].knowledge_name
    return node.local_canonical_id


def convert_package(pkg_dir: Path, *, model: str = "noisy_and", output_suffix: str = "") -> bool:
    """Convert a single package from graph_ir/ to gaia_ir/. Returns True on success.

    model: "noisy_and" — all infer factors use INDUCTION (noisy-AND + leak, target model).
           "silence"   — deterministic infer factors use ENTAILMENT (silence, current impl),
                         soft infer factors use INDUCTION.
    output_suffix: appended to "gaia_ir" for the output directory name.
    """
    graph_dir = pkg_dir / "graph_ir"
    lcg_path = graph_dir / "local_canonical_graph.json"
    params_path = graph_dir / "local_parameterization.json"

    if not lcg_path.exists() or not params_path.exists():
        print(f"  SKIP: missing graph_ir/ outputs in {pkg_dir.name}")
        return False

    old_lcg = OldLocalCanonicalGraph.model_validate_json(lcg_path.read_text())
    old_params = OldLocalParameterization.model_validate_json(params_path.read_text())

    factor_params_path = pkg_dir / "factor_params.json"
    factor_overrides: dict[str, float] = {}
    if factor_params_path.exists():
        factor_overrides = json.loads(factor_params_path.read_text())
        print(f"  Loaded factor_params.json: {len(factor_overrides)} overrides")

    package_id = old_lcg.package

    # Build ID maps
    old_id_to_name: dict[str, str] = {}
    old_id_to_node: dict[str, object] = {}
    for node in old_lcg.knowledge_nodes:
        old_id_to_name[node.local_canonical_id] = _knowledge_name(node)
        old_id_to_node[node.local_canonical_id] = node

    # Identify relation nodes (conclusion of contradiction/equivalence factors)
    relation_node_ids: set[str] = set()
    for factor in old_lcg.factor_nodes:
        if factor.type in ("contradiction", "equivalence") and factor.conclusion:
            relation_node_ids.add(factor.conclusion)

    # --- 1. Build new Knowledge nodes ---
    new_knowledges: list[Knowledge] = []
    old_to_new_id: dict[str, str] = {}

    for node in old_lcg.knowledge_nodes:
        ktype = _KNOWLEDGE_TYPE_MAP.get(node.knowledge_type, KnowledgeType.CLAIM)
        k = Knowledge(
            type=ktype,
            content=node.representative_content,
            package_id=package_id,
        )
        old_to_new_id[node.local_canonical_id] = k.id
        new_knowledges.append(k)

    # --- 2. Build new Operators and Strategies ---
    new_operators: list[Operator] = []
    new_strategies: list[Strategy] = []

    # Map old IDs of relation nodes to new IDs for prior override
    new_relation_ids: set[str] = set()
    for old_id in relation_node_ids:
        if old_id in old_to_new_id:
            new_relation_ids.add(old_to_new_id[old_id])

    # BP factor graph
    fg = FactorGraph()
    for node in old_lcg.knowledge_nodes:
        new_id = old_to_new_id[node.local_canonical_id]
        prior = old_params.node_priors.get(node.local_canonical_id, 0.5)
        if new_id in new_relation_ids:
            prior = 1.0 - CROMWELL_EPS
        fg.add_variable(new_id, prior)

    prior_records: list[PriorRecord] = []
    strategy_params: list[StrategyParamRecord] = []
    now = datetime.now(timezone.utc)

    for node in old_lcg.knowledge_nodes:
        new_id = old_to_new_id[node.local_canonical_id]
        ktype = _KNOWLEDGE_TYPE_MAP.get(node.knowledge_type, KnowledgeType.CLAIM)
        if ktype == KnowledgeType.CLAIM:
            prior = old_params.node_priors.get(node.local_canonical_id, 0.5)
            prior_records.append(
                PriorRecord(gcn_id=new_id, value=prior, source_id=SOURCE_ID, created_at=now)
            )

    for factor in old_lcg.factor_nodes:
        premise_new_ids = [old_to_new_id[p] for p in factor.premises if p in old_to_new_id]
        conclusion_new_id = old_to_new_id.get(factor.conclusion) if factor.conclusion else None
        conclusion_name = old_id_to_name.get(factor.conclusion, "") if factor.conclusion else ""

        fp = old_params.factor_parameters.get(factor.factor_id)
        base_prob = fp.conditional_probability if fp else 1.0
        if conclusion_name in factor_overrides:
            base_prob = factor_overrides[conclusion_name]

        if factor.type == "infer":
            if not premise_new_ids or conclusion_new_id is None:
                continue

            is_soft = base_prob < (1.0 - CROMWELL_EPS)

            if model == "noisy_and":
                # Target model: all infer factors use INDUCTION (noisy-AND + leak).
                # See docs/foundations/bp/potentials.md and
                # specs/2026-03-27-entailment-silence-analysis.md §2.3-§2.4.
                stype = StrategyType.NOISY_AND if is_soft else StrategyType.INFER
                bp_type = FactorType.INDUCTION
            else:
                # Silence model (current impl): deterministic → ENTAILMENT,
                # soft → INDUCTION.
                if is_soft:
                    stype = StrategyType.NOISY_AND
                    bp_type = FactorType.INDUCTION
                else:
                    stype = StrategyType.INFER
                    bp_type = FactorType.ENTAILMENT

            s = Strategy(
                scope="local",
                type=stype,
                premises=premise_new_ids,
                conclusion=conclusion_new_id,
            )
            new_strategies.append(s)
            strategy_params.append(
                StrategyParamRecord(
                    strategy_id=s.strategy_id,
                    conditional_probabilities=[base_prob],
                    source_id=SOURCE_ID,
                    created_at=now,
                )
            )

            fg.add_factor(
                factor_id=s.strategy_id,
                factor_type=bp_type,
                premises=premise_new_ids,
                conclusions=[conclusion_new_id],
                p=base_prob,
            )

        elif factor.type in ("contradiction", "equivalence"):
            if len(premise_new_ids) < 2:
                continue
            op_type = (
                OperatorType.CONTRADICTION
                if factor.type == "contradiction"
                else OperatorType.EQUIVALENCE
            )
            op = Operator(
                scope="local",
                operator=op_type,
                variables=premise_new_ids,
                conclusion=None,
            )
            new_operators.append(op)

            relation_var_id = conclusion_new_id
            if relation_var_id is None:
                relation_var_id = f"rel_{factor.factor_id}"
                fg.add_variable(relation_var_id, 1.0 - CROMWELL_EPS)

            bp_ftype = (
                FactorType.CONTRADICTION
                if factor.type == "contradiction"
                else FactorType.EQUIVALENCE
            )
            fg.add_factor(
                factor_id=factor.factor_id,
                factor_type=bp_ftype,
                premises=premise_new_ids,
                conclusions=[],
                p=1.0,
                relation_var=relation_var_id,
            )

    # --- 3. Run new BP engine ---
    engine = InferenceEngine()
    result = engine.run(fg)
    print(
        f"  BP: method={result.method_used}, treewidth={result.treewidth}, "
        f"exact={result.is_exact}, {result.elapsed_ms:.1f}ms"
    )

    # --- 4. Build output models ---
    new_graph = NewLocalCanonicalGraph(
        knowledges=new_knowledges,
        operators=new_operators,
        strategies=new_strategies,
    )

    belief_state = BeliefState(
        bp_run_id=str(uuid.uuid4()),
        resolution_policy="latest",
        prior_cutoff=now,
        beliefs={
            vid: round(b, 6) for vid, b in result.beliefs.items() if vid in old_to_new_id.values()
        },
        converged=result.diagnostics.converged,
        iterations=getattr(result.diagnostics, "iterations", 0),
        max_residual=getattr(result.diagnostics, "max_change_at_stop", 0.0),
    )

    # --- 5. Write outputs ---
    dir_name = f"gaia_ir{output_suffix}" if output_suffix else "gaia_ir"
    gaia_dir = pkg_dir / dir_name
    gaia_dir.mkdir(exist_ok=True)

    def _dump(obj, path):
        path.write_text(
            json.dumps(obj.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
        )

    _dump(new_graph, gaia_dir / "local_canonical_graph.json")

    param_output = {
        "prior_records": [r.model_dump(mode="json") for r in prior_records],
        "strategy_param_records": [r.model_dump(mode="json") for r in strategy_params],
    }
    (gaia_dir / "local_parameterization.json").write_text(
        json.dumps(param_output, ensure_ascii=False, sort_keys=True, indent=2)
    )

    _dump(belief_state, gaia_dir / "local_belief_state.json")

    # Print belief summary
    for node in old_lcg.knowledge_nodes:
        name = _knowledge_name(node)
        new_id = old_to_new_id[node.local_canonical_id]
        prior = old_params.node_priors.get(node.local_canonical_id, 0.5)
        b = result.beliefs.get(new_id, prior)
        delta = b - prior
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "="
        print(f"  {arrow} {name:40} prior={prior:.3f} -> belief={b:.3f} ({delta:+.3f})")

    return True


def main():
    parser = argparse.ArgumentParser(description="Convert graph_ir/ to gaia_ir/ with new BP engine")
    parser.add_argument("pkg_dirs", type=Path, nargs="+", help="Package directories")
    parser.add_argument(
        "--model",
        choices=["noisy_and", "silence"],
        default="noisy_and",
        help="Factor model: noisy_and (target, all INDUCTION) or silence (ENTAILMENT for deterministic)",
    )
    parser.add_argument(
        "--output-suffix",
        default="",
        help="Suffix appended to 'gaia_ir' for output directory (e.g. '_silence' → gaia_ir_silence/)",
    )
    args = parser.parse_args()

    succeeded = 0
    failed = []
    for pkg_dir in args.pkg_dirs:
        if not pkg_dir.is_dir():
            continue
        print(f"Processing: {pkg_dir.name} (model={args.model})")
        try:
            if convert_package(pkg_dir, model=args.model, output_suffix=args.output_suffix):
                succeeded += 1
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"  ERROR: {e}")
            failed.append(pkg_dir.name)

    total = succeeded + len(failed)
    print(f"\nDone: {succeeded}/{total} packages.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
