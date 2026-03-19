#!/usr/bin/env python3
"""Smoke test: run the curation pipeline step-by-step on the global_graph fixture.

Usage:
    uv run python scripts/smoke_curation.py

Runs each pipeline step individually to capture intermediate results.
Dumps full report to scripts/smoke_report.json.

Requires .env with OPENAI_API_KEY, API_URL, ACCESS_KEY.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import libs.llm  # noqa: E402, F401 — initializes litellm config

from libs.curation.abstraction import AbstractionAgent  # noqa: E402
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan  # noqa: E402
from libs.curation.clustering import cluster_similar_nodes  # noqa: E402
from libs.curation.conflict import detect_conflicts_level1, detect_conflicts_level2  # noqa: E402
from libs.curation.dedup import deduplicate_by_hash  # noqa: E402
from libs.curation.audit import AuditLog  # noqa: E402
from libs.curation.models import ConflictCandidate  # noqa: E402
from libs.curation.structure import inspect_structure  # noqa: E402
from libs.embedding import DPEmbeddingModel  # noqa: E402
from libs.global_graph.models import GlobalCanonicalNode, GlobalGraph  # noqa: E402
from libs.inference.bp import BeliefPropagation  # noqa: E402
from libs.inference.factor_graph import FactorGraph  # noqa: E402
from libs.storage.models import FactorNode  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("smoke_curation")

FIXTURE_PATH = Path("tests/fixtures/global_graph/global_graph.json")
REPORT_PATH = Path("scripts/smoke_report.json")

LLM_MODEL = "chenkun/gpt-5-mini"


def load_fixture() -> tuple[list[GlobalCanonicalNode], list[FactorNode]]:
    data = json.loads(FIXTURE_PATH.read_text())
    graph = GlobalGraph.model_validate(data)
    logger.info(
        "Loaded fixture: %d nodes, %d factors", len(graph.knowledge_nodes), len(graph.factor_nodes)
    )
    return graph.knowledge_nodes, graph.factor_nodes


def _node_summary(node: GlobalCanonicalNode) -> dict:
    return {
        "id": node.global_canonical_id,
        "type": node.knowledge_type,
        "kind": node.kind,
        "content": node.representative_content[:200],
    }


def _factor_summary(factor: FactorNode) -> dict:
    return {
        "id": factor.factor_id,
        "type": factor.type,
        "premises": factor.premises,
        "conclusion": factor.conclusion,
        "package_id": factor.package_id,
    }


async def main() -> None:
    report: dict = {"timestamp": datetime.now(timezone.utc).isoformat(), "steps": {}}

    nodes, factors = load_fixture()
    node_map = {n.global_canonical_id: n for n in nodes}
    mutable_factors = list(factors)

    report["input"] = {
        "node_count": len(nodes),
        "factor_count": len(factors),
    }

    # ── Step 1: Clustering ──
    logger.info("--- Step 1: Clustering ---")
    t0 = time.monotonic()
    embedding_model = DPEmbeddingModel()
    # Exclude schema nodes and already-connected pairs
    clusterable_nodes = [n for n in nodes if n.kind != "schema"]
    connected_pairs: set[tuple[str, str]] = set()
    for f in factors:
        for p in f.premises:
            if f.conclusion:
                connected_pairs.add((min(p, f.conclusion), max(p, f.conclusion)))
    logger.info(
        "Clustering: %d nodes (excluded %d schema), %d connected pairs excluded",
        len(clusterable_nodes),
        len(nodes) - len(clusterable_nodes),
        len(connected_pairs),
    )
    clusters = await cluster_similar_nodes(
        clusterable_nodes,
        threshold=0.85,
        embedding_model=embedding_model,
        exclude_pairs=connected_pairs,
    )
    t_clustering = time.monotonic() - t0
    logger.info("Found %d clusters (%.1fs)", len(clusters), t_clustering)

    report["steps"]["clustering"] = {
        "duration_sec": round(t_clustering, 2),
        "cluster_count": len(clusters),
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "node_ids": c.node_ids,
                "node_contents": {
                    nid: node_map[nid].representative_content[:150]
                    for nid in c.node_ids
                    if nid in node_map
                },
                "pairs": [
                    {
                        "a": p.node_a_id,
                        "b": p.node_b_id,
                        "score": round(p.similarity_score, 4),
                        "method": p.method,
                    }
                    for p in c.pairs
                ],
            }
            for c in clusters
        ],
    }

    # ── Step 2: Dedup ──
    logger.info("--- Step 2: Dedup ---")
    t0 = time.monotonic()
    dedup_suggestions = deduplicate_by_hash(node_map)
    t_dedup = time.monotonic() - t0
    logger.info("Found %d duplicate groups (%.1fs)", len(dedup_suggestions), t_dedup)

    report["steps"]["dedup"] = {
        "duration_sec": round(t_dedup, 2),
        "duplicate_groups": len(dedup_suggestions),
        "suggestions": [
            {
                "target_ids": s.target_ids,
                "reason": s.reason,
                "evidence": s.evidence,
            }
            for s in dedup_suggestions
        ],
    }

    all_suggestions = list(dedup_suggestions)

    # ── Step 3: Abstraction ──
    logger.info("--- Step 3: Abstraction ---")
    t0 = time.monotonic()
    agent = AbstractionAgent(model=LLM_MODEL)
    abs_result = await agent.run(clusters, node_map)
    t_abstraction = time.monotonic() - t0

    for node in abs_result.new_nodes:
        node_map[node.global_canonical_id] = node
    mutable_factors.extend(abs_result.new_factors)
    all_suggestions.extend(abs_result.suggestions)

    logger.info(
        "Abstraction: %d new nodes, %d new factors, %d contradictions (%.1fs)",
        len(abs_result.new_nodes),
        len(abs_result.new_factors),
        len(abs_result.contradiction_candidates),
        t_abstraction,
    )

    report["steps"]["abstraction"] = {
        "duration_sec": round(t_abstraction, 2),
        "new_node_count": len(abs_result.new_nodes),
        "new_factor_count": len(abs_result.new_factors),
        "contradiction_count": len(abs_result.contradiction_candidates),
        "new_nodes": [_node_summary(n) for n in abs_result.new_nodes],
        "new_factors": [_factor_summary(f) for f in abs_result.new_factors],
        "contradiction_candidates": [
            {
                "node_a": c.node_a_id,
                "node_b": c.node_b_id,
                "node_a_content": node_map.get(c.node_a_id, None)
                and node_map[c.node_a_id].representative_content[:150],
                "node_b_content": node_map.get(c.node_b_id, None)
                and node_map[c.node_b_id].representative_content[:150],
                "strength": round(c.strength, 4),
                "detail": c.detail,
            }
            for c in abs_result.contradiction_candidates
        ],
        "suggestions": [
            {
                "operation": s.operation,
                "target_ids": s.target_ids,
                "confidence": round(s.confidence, 4),
                "reason": s.reason,
                "abstraction_content": s.evidence.get("abstraction", ""),
            }
            for s in abs_result.suggestions
        ],
    }

    # ── Step 4: Conflict Detection ──
    logger.info("--- Step 4: Conflict Detection ---")
    t0 = time.monotonic()
    conflict_candidates: list[ConflictCandidate] = []
    conflict_candidates.extend(abs_result.contradiction_candidates)

    # Build factor graph for BP
    fg = FactorGraph()
    str_to_int: dict[str, int] = {}
    int_to_str: dict[int, str] = {}
    for idx, nid in enumerate(node_map.keys()):
        str_to_int[nid] = idx
        int_to_str[idx] = nid
        fg.add_variable(idx, 0.5)

    for fi, factor in enumerate(mutable_factors):
        premises_int = [str_to_int[p] for p in factor.premises if p in str_to_int]
        conclusion_int = str_to_int.get(factor.conclusion)
        if not premises_int:
            continue
        edge_type = (factor.metadata or {}).get("edge_type", "deduction")
        if factor.type in ("mutex_constraint", "equiv_constraint"):
            fg.add_factor(
                fi,
                premises_int,
                [],
                0.9,
                f"relation_{edge_type.split('_')[-1] if 'relation_' in edge_type else edge_type}",
            )
        elif conclusion_int is not None:
            fg.add_factor(fi, premises_int, [conclusion_int], 0.9, edge_type)

    if fg.factors:
        bp = BeliefPropagation(max_iterations=30, damping=0.5)
        baseline_beliefs, diag = bp.run_with_diagnostics(fg)
        level1 = detect_conflicts_level1(diag)
        for c in level1:
            c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
            c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
        conflict_candidates.extend(level1)

        probe_ids = set()
        for c in level1:
            probe_ids.add(str_to_int.get(c.node_a_id, -1))
            probe_ids.add(str_to_int.get(c.node_b_id, -1))
        probe_ids.discard(-1)
        if probe_ids:
            level2 = detect_conflicts_level2(fg, list(probe_ids), baseline_beliefs, bp)
            for c in level2:
                c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
                c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
            conflict_candidates.extend(level2)

    t_conflict = time.monotonic() - t0
    logger.info("Found %d conflict candidates (%.1fs)", len(conflict_candidates), t_conflict)

    report["steps"]["conflict_detection"] = {
        "duration_sec": round(t_conflict, 2),
        "candidate_count": len(conflict_candidates),
        "candidates": [
            {
                "node_a": c.node_a_id,
                "node_b": c.node_b_id,
                "node_a_content": node_map.get(c.node_a_id, None)
                and node_map[c.node_a_id].representative_content[:150],
                "node_b_content": node_map.get(c.node_b_id, None)
                and node_map[c.node_b_id].representative_content[:150],
                "signal_type": c.signal_type,
                "strength": round(c.strength, 4),
            }
            for c in conflict_candidates
        ],
    }

    # ── Step 5: Structure Inspection ──
    logger.info("--- Step 5: Structure Inspection ---")
    t0 = time.monotonic()
    all_nodes_list = list(node_map.values())
    structure_report = inspect_structure(all_nodes_list, mutable_factors)
    t_structure = time.monotonic() - t0
    logger.info(
        "Structure: %d errors, %d warnings, %d info",
        len(structure_report.errors),
        len(structure_report.warnings),
        len(structure_report.infos),
    )

    report["steps"]["structure"] = {
        "duration_sec": round(t_structure, 2),
        "error_count": len(structure_report.errors),
        "warning_count": len(structure_report.warnings),
        "info_count": len(structure_report.infos),
        "issues": [
            {
                "type": i.issue_type,
                "severity": i.severity,
                "node_ids": i.node_ids,
                "factor_ids": i.factor_ids,
                "detail": i.detail,
            }
            for i in structure_report.issues
        ],
    }

    # ── Step 6: Cleanup ──
    logger.info("--- Step 6: Cleanup ---")
    t0 = time.monotonic()
    plan = generate_cleanup_plan(all_suggestions, conflict_candidates, structure_report)
    logger.info(
        "Plan: %d auto-approve, %d needs review, %d discard",
        len(plan.auto_approve),
        len(plan.needs_review),
        len(plan.discard),
    )

    audit_log = AuditLog()
    result = await execute_cleanup(plan, node_map, mutable_factors, audit_log, LLM_MODEL)
    result.structure_report = structure_report

    t_cleanup = time.monotonic() - t0

    report["steps"]["cleanup"] = {
        "duration_sec": round(t_cleanup, 2),
        "auto_approve_count": len(plan.auto_approve),
        "needs_review_count": len(plan.needs_review),
        "discard_count": len(plan.discard),
        "executed": [
            {
                "operation": s.operation,
                "target_ids": s.target_ids,
                "confidence": round(s.confidence, 4),
                "reason": s.reason,
                "evidence": s.evidence,
            }
            for s in result.executed
        ],
        "skipped": [
            {
                "operation": s.operation,
                "target_ids": s.target_ids,
                "confidence": round(s.confidence, 4),
                "reason": s.reason,
            }
            for s in result.skipped
        ],
        "audit_entries": [
            {
                "operation": e.operation,
                "target_ids": e.target_ids,
                "suggestion_id": e.suggestion_id,
            }
            for e in result.audit_entries
        ],
    }

    # ── Final state ──
    total_sec = t_clustering + t_dedup + t_abstraction + t_conflict + t_structure + t_cleanup
    report["output"] = {
        "node_count": len(node_map),
        "factor_count": len(mutable_factors),
        "new_nodes_added": len(node_map) - report["input"]["node_count"],
        "new_factors_added": len(mutable_factors) - report["input"]["factor_count"],
        "total_duration_sec": round(total_sec, 2),
    }

    # Write report
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("=== Report written to %s ===", REPORT_PATH)

    # Print summary
    logger.info(
        "Input: %d nodes, %d factors",
        report["input"]["node_count"],
        report["input"]["factor_count"],
    )
    logger.info("Clusters: %d", report["steps"]["clustering"]["cluster_count"])
    logger.info("Dedup: %d duplicate groups", report["steps"]["dedup"]["duplicate_groups"])
    logger.info(
        "Abstraction: %d new nodes, %d new factors",
        report["steps"]["abstraction"]["new_node_count"],
        report["steps"]["abstraction"]["new_factor_count"],
    )
    logger.info(
        "Conflicts: %d candidates", report["steps"]["conflict_detection"]["candidate_count"]
    )
    logger.info("Cleanup: %d executed, %d skipped", len(result.executed), len(result.skipped))
    logger.info(
        "Output: %d nodes, %d factors",
        report["output"]["node_count"],
        report["output"]["factor_count"],
    )


if __name__ == "__main__":
    asyncio.run(main())
