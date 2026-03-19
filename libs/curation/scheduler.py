"""Curation scheduler — main pipeline orchestrator.

Pipeline: cluster → classify → abstract → detect conflicts → inspect structure → cleanup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from libs.embedding import EmbeddingModel
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph

from .audit import AuditLog
from .classification import classify_clusters
from .cleanup import execute_cleanup, generate_cleanup_plan
from .clustering import cluster_similar_nodes
from .conflict import detect_conflicts_level1, detect_conflicts_level2
from .abstraction import AbstractionAgent
from .models import ConflictCandidate, CurationResult, StructureReport
from .structure import inspect_structure

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager

logger = logging.getLogger(__name__)


def _build_factor_graph_from_storage(
    nodes: dict[str, object],
    factors: list,
) -> tuple[FactorGraph, dict[str, int], dict[int, str]]:
    """Build a FactorGraph from storage models.

    Returns the graph plus bidirectional ID mappings (str <-> int).
    """
    graph = FactorGraph()
    str_to_int: dict[str, int] = {}
    int_to_str: dict[int, str] = {}

    # Assign integer IDs to nodes
    for idx, node_id in enumerate(nodes.keys()):
        str_to_int[node_id] = idx
        int_to_str[idx] = node_id
        graph.add_variable(idx, 0.5)  # Neutral prior for curation analysis

    # Add factors
    for fi, factor in enumerate(factors):
        premises_int = [str_to_int[p] for p in factor.premises if p in str_to_int]
        conclusion_int = str_to_int.get(factor.conclusion)

        if not premises_int:
            continue

        edge_type = (factor.metadata or {}).get("edge_type", "deduction")

        if factor.type in ("mutex_constraint", "equiv_constraint"):
            # Constraint factors: no conclusion in BP
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


async def run_curation(
    storage: StorageManager,
    embedding_model: EmbeddingModel | None = None,
    similarity_threshold: float = 0.90,
    skip_conflict_detection: bool = False,
    skip_abstraction: bool = False,
    bp_max_iterations: int = 50,
    bp_damping: float = 0.5,
    reviewer_model: str | None = None,
    abstraction_model: str | None = None,
) -> CurationResult:
    """Run the full curation pipeline.

    Steps:
    1. Load all global nodes and factors
    2. Cluster similar nodes
    3. Classify clusters (duplicate / equivalence)
    3b. Abstract clusters (extract common conclusions) — optional
    4. Detect conflicts (BP Level 1 + 2) — optional
    5. Inspect structure
    6. Generate and execute cleanup plan

    Args:
        storage: StorageManager to read/write data.
        embedding_model: For similarity computation. Falls back to TF-IDF if None.
        similarity_threshold: Minimum similarity for clustering.
        skip_conflict_detection: Skip BP-based conflict detection (faster).
        skip_abstraction: Skip abstraction agent (faster).
        bp_max_iterations: Max BP iterations for conflict detection.
        bp_damping: BP damping factor.
        reviewer_model: Model for curation reviewer.
        abstraction_model: Model for abstraction agent. Defaults to reviewer_model.

    Returns:
        CurationResult with executed operations and audit trail.
    """
    # Step 1: Load data
    all_nodes = await storage.list_global_nodes()
    all_factors = await storage.list_factors()

    if not all_nodes:
        logger.info("No global nodes found, nothing to curate")
        return CurationResult(structure_report=StructureReport())

    node_map = {n.global_canonical_id: n for n in all_nodes}
    logger.info("Loaded %d global nodes and %d factors", len(all_nodes), len(all_factors))

    # Step 2: Cluster similar nodes
    clusters = await cluster_similar_nodes(
        all_nodes,
        threshold=similarity_threshold,
        embedding_model=embedding_model,
    )
    logger.info("Found %d clusters", len(clusters))

    # Step 3: Classify clusters
    cluster_suggestions = classify_clusters(clusters, node_map)
    logger.info("Generated %d cluster suggestions", len(cluster_suggestions))

    # Step 3b: Abstraction
    mutable_factors = list(all_factors)
    if not skip_abstraction:
        abs_model = abstraction_model or reviewer_model
        agent = AbstractionAgent(model=abs_model)
        abs_result = await agent.run(clusters, node_map)

        # Integrate new schema nodes into node_map
        for node in abs_result.new_nodes:
            node_map[node.global_canonical_id] = node
        mutable_factors.extend(abs_result.new_factors)
        cluster_suggestions.extend(abs_result.suggestions)
        logger.info(
            "Abstraction: %d new nodes, %d new factors, %d contradictions",
            len(abs_result.new_nodes),
            len(abs_result.new_factors),
            len(abs_result.contradiction_candidates),
        )
    else:
        abs_result = None

    # Step 4: Detect conflicts
    conflict_candidates: list[ConflictCandidate] = []
    if abs_result and abs_result.contradiction_candidates:
        conflict_candidates.extend(abs_result.contradiction_candidates)
    if not skip_conflict_detection and len(all_nodes) >= 2 and all_factors:
        bp = BeliefPropagation(
            max_iterations=bp_max_iterations,
            damping=bp_damping,
        )
        fg, str_to_int, int_to_str = _build_factor_graph_from_storage(node_map, all_factors)

        if fg.factors:
            # Level 1: Oscillation detection
            baseline_beliefs, diag = bp.run_with_diagnostics(fg)
            level1 = detect_conflicts_level1(diag)

            # Map int IDs back to string IDs
            for c in level1:
                c.node_a_id = int_to_str.get(int(c.node_a_id), c.node_a_id)
                c.node_b_id = int_to_str.get(int(c.node_b_id), c.node_b_id)
            conflict_candidates.extend(level1)

            # Level 2: Sensitivity analysis on Level 1 candidates
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

        logger.info("Found %d conflict candidates", len(conflict_candidates))

    # Step 5: Structure inspection
    structure_report = inspect_structure(all_nodes, all_factors)
    logger.info(
        "Structure: %d errors, %d warnings, %d info",
        len(structure_report.errors),
        len(structure_report.warnings),
        len(structure_report.infos),
    )

    # Step 6: Generate and execute cleanup plan
    plan = generate_cleanup_plan(cluster_suggestions, conflict_candidates, structure_report)
    logger.info(
        "Plan: %d auto-approve, %d needs review, %d discard",
        len(plan.auto_approve),
        len(plan.needs_review),
        len(plan.discard),
    )

    audit_log = AuditLog()
    result = await execute_cleanup(plan, node_map, mutable_factors, audit_log, reviewer_model)
    result.structure_report = structure_report

    # Step 7: Persist changes if any operations were executed
    if result.executed:
        updated_nodes = list(node_map.values())
        await storage.upsert_global_nodes(updated_nodes)
        await storage.write_factors(mutable_factors)
        logger.info(
            "Persisted %d node updates and %d factor updates",
            len(updated_nodes),
            len(mutable_factors),
        )

    return result
