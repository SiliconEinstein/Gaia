#!/usr/bin/env python3
# ruff: noqa: E402
"""Generate before/after JSON fixtures for curation testing.

Runs the full curation pipeline on the physics knowledge graph and saves:
  - before.json: the graph as loaded (11 nodes, 7 factors)
  - after.json:  the graph after curation (merged nodes, redirected factors, new constraints)
  - curation_result.json: the CurationResult with executed/skipped suggestions and audit trail

Usage:
    python scripts/generate_curation_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env from project root (real .env is in the main repo, not the worktree)
_env_path = ROOT / ".env"
if not _env_path.exists():
    _env_path = ROOT.parent.parent / ".env"  # worktree → main repo
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from libs.curation.audit import AuditLog
from libs.curation.classification import classify_clusters
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan
from libs.curation.clustering import cluster_similar_nodes
from libs.curation.conflict import detect_conflicts_level1, detect_conflicts_level2
from libs.curation.models import ConflictCandidate
from libs.curation.structure import inspect_structure
from libs.global_graph.models import GlobalCanonicalNode
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
from libs.storage.models import FactorNode
from tests.libs.curation.conftest import build_physics_graph

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "curation"

# LLM model — use openai/ prefix so litellm routes to OPENAI_API_BASE
LLM_MODEL = "openai/azure/gpt-5-mini"


def _serialize_nodes(nodes: list[GlobalCanonicalNode]) -> list[dict]:
    return [n.model_dump(mode="json") for n in nodes]


def _serialize_factors(factors: list[FactorNode]) -> list[dict]:
    return [f.model_dump(mode="json") for f in factors]


def _build_factor_graph(
    node_map: dict[str, GlobalCanonicalNode],
    factors: list[FactorNode],
) -> tuple[FactorGraph, dict[str, int], dict[int, str]]:
    """Build FactorGraph with bidirectional ID mappings."""
    graph = FactorGraph()
    str_to_int: dict[str, int] = {}
    int_to_str: dict[int, str] = {}

    for idx, node_id in enumerate(node_map.keys()):
        str_to_int[node_id] = idx
        int_to_str[idx] = node_id
        graph.add_variable(idx, 0.5)

    for fi, factor in enumerate(factors):
        premises_int = [str_to_int[p] for p in factor.premises if p in str_to_int]
        conclusion_int = str_to_int.get(factor.conclusion)

        if not premises_int:
            continue

        edge_type = (factor.metadata or {}).get("edge_type", "deduction")

        if factor.type in ("mutex_constraint", "equiv_constraint"):
            graph.add_factor(
                fi,
                premises_int,
                [],
                0.9,
                f"relation_{edge_type.split('_')[-1] if 'relation_' in edge_type else edge_type}",
            )
        elif conclusion_int is not None:
            graph.add_factor(fi, premises_int, [conclusion_int], 0.9, edge_type)

    return graph, str_to_int, int_to_str


async def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Build the graph ──
    all_nodes, all_factors = build_physics_graph()
    node_map = {n.global_canonical_id: n for n in all_nodes}

    # ── Save BEFORE ──
    before = {
        "description": "Physics knowledge graph BEFORE curation",
        "node_count": len(all_nodes),
        "factor_count": len(all_factors),
        "nodes": _serialize_nodes(all_nodes),
        "factors": _serialize_factors(all_factors),
    }
    (FIXTURES_DIR / "before.json").write_text(json.dumps(before, indent=2, ensure_ascii=False))
    print(f"✓ Saved before.json ({len(all_nodes)} nodes, {len(all_factors)} factors)")

    # ── Step 2: Run clustering ──
    from libs.embedding import DPEmbeddingModel

    emb = DPEmbeddingModel()
    clusters = await cluster_similar_nodes(all_nodes, threshold=0.60, embedding_model=emb)
    print(f"  Clustering: {len(clusters)} clusters found")
    for c in clusters:
        print(f"    {c.cluster_id}: {c.node_ids} ({len(c.pairs)} pairs)")

    # ── Step 3: Classify ──
    cluster_suggestions = classify_clusters(clusters, node_map)
    print(f"  Classification: {len(cluster_suggestions)} suggestions")
    for s in cluster_suggestions:
        print(f"    {s.operation}: {s.target_ids} (confidence={s.confidence:.3f})")

    # ── Step 4: Conflict detection ──
    conflict_candidates: list[ConflictCandidate] = []
    bp = BeliefPropagation(max_iterations=50, damping=0.3)
    fg, str_to_int, int_to_str = _build_factor_graph(node_map, all_factors)

    if fg.factors:
        baseline_beliefs, diag = bp.run_with_diagnostics(fg)
        print(f"  BP: converged={diag.converged}, iterations={diag.iterations_run}")
        print(f"  BP beliefs: { {int_to_str[k]: f'{v:.3f}' for k, v in baseline_beliefs.items()} }")
        print(
            f"  Direction changes: { {int_to_str[k]: v for k, v in diag.direction_changes.items() if v > 0} }"
        )

        level1 = detect_conflicts_level1(diag, min_direction_changes=1, belief_range=(0.0, 1.0))
        for c in level1:
            c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
            c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
        conflict_candidates.extend(level1)
        print(f"  Conflict L1: {len(level1)} candidates")

        probe_ids = set()
        for c in level1:
            probe_ids.add(str_to_int.get(c.node_a_id, -1))
            probe_ids.add(str_to_int.get(c.node_b_id, -1))
        probe_ids.discard(-1)

        if probe_ids:
            level2 = detect_conflicts_level2(
                fg, list(probe_ids), baseline_beliefs, bp, min_drop=0.01
            )
            for c in level2:
                c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
                c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
            conflict_candidates.extend(level2)
            print(f"  Conflict L2: {len(level2)} candidates")

    # ── Step 5: Structure inspection ──
    structure_report = inspect_structure(all_nodes, all_factors)
    print(
        f"  Structure: {len(structure_report.errors)} errors, "
        f"{len(structure_report.warnings)} warnings, {len(structure_report.infos)} info"
    )
    for issue in structure_report.issues:
        print(f"    [{issue.severity}] {issue.issue_type}: {issue.detail[:80]}")

    # ── Step 6: Generate plan ──
    # Temporarily lower review threshold so equivalence suggestions enter LLM review
    import libs.curation.models as curation_models

    original_threshold = curation_models.REVIEW_THRESHOLD
    curation_models.REVIEW_THRESHOLD = 0.50

    plan = generate_cleanup_plan(cluster_suggestions, conflict_candidates, structure_report)
    print(
        f"  Plan: {len(plan.auto_approve)} auto, "
        f"{len(plan.needs_review)} review, {len(plan.discard)} discard"
    )

    # ── Step 7: Review needs_review suggestions via LLM ──
    review_traces: list[dict] = []
    from libs.curation.reviewer import CurationReviewer

    reviewer = CurationReviewer(model=LLM_MODEL, nodes=node_map)
    for suggestion in plan.needs_review:
        user_msg = reviewer._build_user_message(suggestion)
        print(f"\n  ── LLM Review: {suggestion.operation} {suggestion.target_ids} ──")
        print(f"  Input:\n{user_msg}")

        reviewer._last_llm_input = None
        reviewer._last_llm_output = None
        decision = await reviewer.areview(suggestion)
        llm_output = getattr(reviewer, "_last_llm_output", None)
        print(f"  LLM output: {llm_output}")
        print(f"  Decision: {decision}")

        review_traces.append(
            {
                "suggestion_id": suggestion.suggestion_id,
                "operation": suggestion.operation,
                "target_ids": suggestion.target_ids,
                "confidence": suggestion.confidence,
                "input": user_msg,
                "llm_output": llm_output,
                "decision": decision,
            }
        )

    # Save review traces
    (FIXTURES_DIR / "curation_review_traces.json").write_text(
        json.dumps(review_traces, indent=2, ensure_ascii=False)
    )
    print(f"\n✓ Saved curation_review_traces.json ({len(review_traces)} reviews)")

    # ── Step 8: Execute cleanup (with LLM reviewer) ──
    mutable_factors = list(all_factors)
    audit_log = AuditLog()
    result = await execute_cleanup(
        plan, node_map, mutable_factors, audit_log, reviewer_model=LLM_MODEL
    )
    result.structure_report = structure_report

    # Restore original threshold
    curation_models.REVIEW_THRESHOLD = original_threshold

    print(f"  Executed: {len(result.executed)} operations")
    for s in result.executed:
        print(f"    ✓ {s.operation}: {s.target_ids}")
    print(f"  Skipped: {len(result.skipped)} suggestions")
    for s in result.skipped:
        print(f"    ✗ {s.operation}: {s.target_ids} (confidence={s.confidence:.3f})")

    # ── Save AFTER ──
    after_nodes = list(node_map.values())
    after = {
        "description": "Physics knowledge graph AFTER curation",
        "node_count": len(after_nodes),
        "factor_count": len(mutable_factors),
        "nodes": _serialize_nodes(after_nodes),
        "factors": _serialize_factors(mutable_factors),
    }
    (FIXTURES_DIR / "after.json").write_text(json.dumps(after, indent=2, ensure_ascii=False))
    print(f"\n✓ Saved after.json ({len(after_nodes)} nodes, {len(mutable_factors)} factors)")

    # ── Save curation result ──
    curation_result = {
        "description": "Curation pipeline result",
        "executed": [s.model_dump(mode="json") for s in result.executed],
        "skipped": [s.model_dump(mode="json") for s in result.skipped],
        "audit_entries": audit_log.to_dicts(),
        "structure_report": {
            "issues": [i.model_dump(mode="json") for i in structure_report.issues],
        },
        "conflict_candidates": [c.model_dump(mode="json") for c in conflict_candidates],
    }
    (FIXTURES_DIR / "curation_result.json").write_text(
        json.dumps(curation_result, indent=2, ensure_ascii=False)
    )
    print("✓ Saved curation_result.json")

    # ── Summary of changes ──
    before_ids = {n["global_canonical_id"] for n in before["nodes"]}
    after_ids = {n["global_canonical_id"] for n in after["nodes"]}
    removed = before_ids - after_ids
    added = after_ids - before_ids

    before_factor_ids = {f["factor_id"] for f in before["factors"]}
    after_factor_ids = {f["factor_id"] for f in after["factors"]}
    new_factors = after_factor_ids - before_factor_ids
    removed_factors = before_factor_ids - after_factor_ids

    print("\n═══ DIFF SUMMARY ═══")
    print(f"  Nodes removed: {removed or '(none)'}")
    print(f"  Nodes added:   {added or '(none)'}")
    print(f"  Factors added:   {new_factors or '(none)'}")
    print(f"  Factors removed: {removed_factors or '(none)'}")

    # Check factor redirects
    for f in mutable_factors:
        for orig_f in all_factors:
            if f.factor_id == orig_f.factor_id:
                if f.premises != orig_f.premises or f.conclusion != orig_f.conclusion:
                    print(f"  Factor {f.factor_id} REDIRECTED:")
                    print(f"    before: premises={orig_f.premises} → {orig_f.conclusion}")
                    print(f"    after:  premises={f.premises} → {f.conclusion}")


if __name__ == "__main__":
    asyncio.run(main())
