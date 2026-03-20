#!/usr/bin/env python3
"""Run the 6-step curation pipeline reading from / writing to DB via StorageManager.

Reads global graph data (nodes + factors) from storage, runs the full curation
pipeline (clustering, dedup, abstraction, conflict detection, structure inspection,
cleanup), writes curated results back to DB, and saves a local JSON report.

Usage:
    python scripts/pipeline/run_curation_db.py \
        --db-path ./data/lancedb/gaia \
        --graph-backend kuzu \
        --report-path output/curation_report.json \
        --llm-model openai/chenkun/gpt-5-mini
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

import libs.llm  # noqa: E402, F401 — initializes litellm config

from libs.curation.abstraction import AbstractionAgent  # noqa: E402
from libs.curation.audit import AuditLog  # noqa: E402
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan  # noqa: E402
from libs.curation.clustering import cluster_similar_nodes  # noqa: E402
from libs.curation.conflict import detect_conflicts_level1, detect_conflicts_level2  # noqa: E402
from libs.curation.dedup import deduplicate_by_hash  # noqa: E402
from libs.curation.models import ConflictCandidate  # noqa: E402
from libs.curation.structure import inspect_structure  # noqa: E402
from libs.embedding import DPEmbeddingModel  # noqa: E402
from libs.global_graph.models import GlobalCanonicalNode as GGNode  # noqa: E402
from libs.inference.bp import BeliefPropagation  # noqa: E402
from libs.inference.factor_graph import FactorGraph  # noqa: E402
from libs.storage.config import StorageConfig  # noqa: E402
from libs.storage.manager import StorageManager  # noqa: E402
from libs.storage.models import FactorNode  # noqa: E402
from libs.storage.models import GlobalCanonicalNode as StorageNode  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("run_curation_db")

DEFAULT_LLM_MODEL = "openai/chenkun/gpt-5-mini"


# ── Model conversion helpers ──


def storage_to_curation(node: StorageNode) -> GGNode:
    """Convert storage GlobalCanonicalNode to global_graph GlobalCanonicalNode."""
    return GGNode.model_validate(node.model_dump())


def curation_to_storage(node: GGNode) -> StorageNode:
    """Convert global_graph GlobalCanonicalNode to storage GlobalCanonicalNode."""
    return StorageNode.model_validate(node.model_dump())


def _node_summary(node: GGNode) -> dict:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run curation pipeline on global graph from DB")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("./data/lancedb/gaia"),
        help="Path to LanceDB database",
    )
    parser.add_argument(
        "--graph-backend",
        choices=["kuzu", "neo4j", "none"],
        default="kuzu",
        help="Graph backend to use (default: kuzu)",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("output/curation_report.json"),
        help="Path for the output report JSON",
    )
    parser.add_argument(
        "--llm-model",
        default=DEFAULT_LLM_MODEL,
        help=f"LLM model for abstraction agent (default: {DEFAULT_LLM_MODEL})",
    )
    return parser.parse_args()


async def create_storage_manager(args: argparse.Namespace) -> StorageManager:
    """Create and initialize a StorageManager from CLI args."""
    graph_backend = args.graph_backend if args.graph_backend != "none" else None
    config = StorageConfig(
        lancedb_path=str(args.db_path),
        graph_backend=graph_backend,
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


async def main() -> None:
    args = parse_args()
    report: dict = {"timestamp": datetime.now(timezone.utc).isoformat(), "steps": {}}

    # ── Initialize storage ──
    logger.info("Connecting to DB at %s (graph: %s)", args.db_path, args.graph_backend)
    mgr = await create_storage_manager(args)

    # ── Read from DB ──
    logger.info("Loading global nodes and factors from DB...")
    storage_nodes = await mgr.list_global_nodes()
    factors = await mgr.list_factors()

    # Convert storage nodes to curation (global_graph) nodes
    nodes = [storage_to_curation(n) for n in storage_nodes]
    node_map: dict[str, GGNode] = {n.global_canonical_id: n for n in nodes}
    mutable_factors: list[FactorNode] = list(factors)

    logger.info("Loaded %d nodes, %d factors from DB", len(nodes), len(factors))

    if not nodes:
        logger.warning("No global nodes found in DB. Nothing to curate.")
        return

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
    agent = AbstractionAgent(model=args.llm_model)
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
    result = await execute_cleanup(plan, node_map, mutable_factors, audit_log, args.llm_model)
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

    # ── Write results back to DB ──
    logger.info("--- Writing curated results back to DB ---")
    t0 = time.monotonic()

    # Compute diff: which nodes/factors were removed during curation
    original_node_ids = {n.global_canonical_id for n in storage_nodes}
    final_node_ids = set(node_map.keys())
    removed_node_ids = list(original_node_ids - final_node_ids)

    original_factor_ids = {f.factor_id for f in factors}
    final_factor_ids = {f.factor_id for f in mutable_factors}
    removed_factor_ids = list(original_factor_ids - final_factor_ids)

    # Delete removed nodes and factors
    if removed_node_ids:
        await mgr.delete_global_nodes(removed_node_ids)
        logger.info("Deleted %d removed global nodes from DB", len(removed_node_ids))
    if removed_factor_ids:
        await mgr.delete_factors(removed_factor_ids)
        logger.info("Deleted %d removed factors from DB", len(removed_factor_ids))

    # Upsert remaining/new nodes and factors
    final_storage_nodes = [curation_to_storage(n) for n in node_map.values()]
    await mgr.upsert_global_nodes(final_storage_nodes)
    logger.info("Upserted %d global nodes to DB", len(final_storage_nodes))

    await mgr.write_factors(mutable_factors)
    logger.info("Wrote %d factors to DB", len(mutable_factors))

    t_writeback = time.monotonic() - t0
    logger.info("DB writeback completed (%.1fs)", t_writeback)

    # ── Final state ──
    total_sec = (
        t_clustering + t_dedup + t_abstraction + t_conflict + t_structure + t_cleanup + t_writeback
    )
    report["output"] = {
        "node_count": len(node_map),
        "factor_count": len(mutable_factors),
        "new_nodes_added": len(node_map) - report["input"]["node_count"],
        "new_factors_added": len(mutable_factors) - report["input"]["factor_count"],
        "total_duration_sec": round(total_sec, 2),
        "writeback_duration_sec": round(t_writeback, 2),
    }

    # Write report
    report_path = args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("=== Report written to %s ===", report_path)

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
