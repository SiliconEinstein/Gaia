"""Cleanup — generate and execute curation plans.

generate_cleanup_plan: Combine analysis results into a CurationPlan.
execute_cleanup: Execute approved operations (auto-approve > 0.95, skip < 0.70).
"""

from __future__ import annotations

import logging

from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode

from .audit import AuditLog
from .models import (
    AuditEntry,
    ConflictCandidate,
    CurationPlan,
    CurationResult,
    CurationSuggestion,
    StructureReport,
)
from .operations import create_constraint, merge_nodes
from .reviewer import CurationReviewer

logger = logging.getLogger(__name__)


def generate_cleanup_plan(
    cluster_suggestions: list[CurationSuggestion],
    conflict_candidates: list[ConflictCandidate],
    structure_report: StructureReport,
) -> CurationPlan:
    """Combine all analysis outputs into a unified CurationPlan.

    Args:
        cluster_suggestions: From classification step (merge/equivalence).
        conflict_candidates: From conflict discovery (Level 1 + 2).
        structure_report: From structure inspection.

    Returns:
        CurationPlan with all suggestions combined.
    """
    suggestions: list[CurationSuggestion] = list(cluster_suggestions)

    # Convert conflict candidates to create_contradiction suggestions
    for candidate in conflict_candidates:
        suggestions.append(
            CurationSuggestion(
                operation="create_contradiction",
                target_ids=[candidate.node_a_id, candidate.node_b_id],
                confidence=candidate.strength,
                reason=(
                    f"Conflict detected via {candidate.signal_type}"
                    f" (strength {candidate.strength:.3f})"
                ),
                evidence=candidate.detail,
            )
        )

    # Convert structure issues to fix suggestions
    for issue in structure_report.issues:
        if issue.issue_type == "dangling_factor" and issue.severity == "error":
            suggestions.append(
                CurationSuggestion(
                    operation="fix_dangling_factor",
                    target_ids=issue.factor_ids,
                    confidence=1.0,  # Structural errors are certain
                    reason=issue.detail,
                    evidence={"issue_type": issue.issue_type},
                )
            )
        elif issue.issue_type == "orphan_node" and issue.severity == "warning":
            suggestions.append(
                CurationSuggestion(
                    operation="archive_orphan",
                    target_ids=issue.node_ids,
                    confidence=0.8,
                    reason=issue.detail,
                    evidence={"issue_type": issue.issue_type},
                )
            )

    return CurationPlan(suggestions=suggestions)


async def execute_cleanup(
    plan: CurationPlan,
    nodes: dict[str, GlobalCanonicalNode],
    factors: list[FactorNode],
    audit_log: AuditLog,
    reviewer_model: str | None = None,
) -> CurationResult:
    """Execute a curation plan: auto-approve high confidence, skip low confidence.

    Args:
        plan: The curation plan to execute.
        nodes: Global nodes by ID (mutable — will be updated in place).
        factors: All factors (mutable — will be updated in place).
        audit_log: Audit log to record operations.
        reviewer_model: LLM model for reviewing medium-confidence suggestions.
            If None, uses rule-based fallback only.

    Returns:
        CurationResult with executed and skipped suggestions.
    """
    executed: list[CurationSuggestion] = []
    skipped: list[CurationSuggestion] = []
    audit_entries: list[AuditEntry] = []

    for suggestion in plan.auto_approve:
        entry = _execute_suggestion(suggestion, nodes, factors)
        if entry is not None:
            audit_log.append(entry)
            audit_entries.append(entry)
            executed.append(suggestion)
        else:
            skipped.append(suggestion)

    # needs_review items go through LLM reviewer (with rule-based fallback)
    reviewer = CurationReviewer(model=reviewer_model, nodes=nodes)
    for suggestion in plan.needs_review:
        decision = await reviewer.areview(suggestion)
        if decision in ("approve", "modify"):
            entry = _execute_suggestion(suggestion, nodes, factors)
            if entry is not None:
                audit_log.append(entry)
                audit_entries.append(entry)
                executed.append(suggestion)
                continue
        skipped.append(suggestion)
        logger.info("Reviewer %s: %s — %s", decision, suggestion.suggestion_id, suggestion.reason)

    # discard items are dropped
    for suggestion in plan.discard:
        skipped.append(suggestion)

    return CurationResult(
        executed=executed,
        skipped=skipped,
        audit_entries=audit_entries,
        structure_report=StructureReport(),
    )


def _execute_suggestion(
    suggestion: CurationSuggestion,
    nodes: dict[str, GlobalCanonicalNode],
    factors: list[FactorNode],
) -> AuditEntry | None:
    """Execute a single suggestion and return an audit entry, or None on failure."""
    if suggestion.operation == "merge":
        if len(suggestion.target_ids) != 2:
            return None
        source_id, target_id = suggestion.target_ids
        source = nodes.get(source_id)
        target = nodes.get(target_id)
        if source is None or target is None:
            return None

        result = merge_nodes(source_id, target_id, source, target, factors)
        # Apply: replace target in nodes, remove source, update factors
        nodes[target_id] = result.merged_node
        nodes.pop(source_id, None)
        factors.clear()
        factors.extend(result.updated_factors)

        return AuditEntry(
            operation="merge",
            target_ids=[source_id, target_id],
            suggestion_id=suggestion.suggestion_id,
            rollback_data=result.rollback_data,
        )

    if suggestion.operation in ("create_equivalence", "create_contradiction"):
        if len(suggestion.target_ids) != 2:
            return None
        constraint_type = (
            "equivalence" if suggestion.operation == "create_equivalence" else "contradiction"
        )
        factor = create_constraint(
            suggestion.target_ids[0], suggestion.target_ids[1], constraint_type
        )
        factors.append(factor)

        return AuditEntry(
            operation=suggestion.operation,
            target_ids=list(suggestion.target_ids),
            suggestion_id=suggestion.suggestion_id,
            rollback_data={"created_factor_id": factor.factor_id},
        )

    if suggestion.operation == "fix_dangling_factor":
        # Remove dangling factors
        removed_ids = set(suggestion.target_ids)
        original_factors = [f.model_dump() for f in factors if f.factor_id in removed_ids]
        factors[:] = [f for f in factors if f.factor_id not in removed_ids]

        return AuditEntry(
            operation="fix_dangling_factor",
            target_ids=list(suggestion.target_ids),
            suggestion_id=suggestion.suggestion_id,
            rollback_data={"removed_factors": original_factors},
        )

    logger.warning("Unknown operation: %s", suggestion.operation)
    return None
