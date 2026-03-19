"""Tests for cleanup plan generation and execution."""

from libs.curation.audit import AuditLog
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan
from libs.curation.models import (
    ConflictCandidate,
    CurationPlan,
    CurationSuggestion,
    StructureIssue,
    StructureReport,
)
from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


# ── generate_cleanup_plan ──


def test_generate_plan_combines_sources():
    """Plan combines cluster suggestions, conflict suggestions, and structure suggestions."""
    cluster_suggestions = [
        CurationSuggestion(
            suggestion_id="s1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.98,
            reason="Duplicate",
            evidence={},
        ),
    ]
    conflict_candidates = [
        ConflictCandidate(
            node_a_id="gcn_c",
            node_b_id="gcn_d",
            signal_type="sensitivity",
            strength=0.85,
        ),
    ]
    structure_report = StructureReport(
        issues=[
            StructureIssue(
                issue_type="dangling_factor",
                severity="error",
                node_ids=["gcn_deleted"],
                factor_ids=["f_bad"],
                detail="Dangling",
            ),
        ]
    )

    plan = generate_cleanup_plan(cluster_suggestions, conflict_candidates, structure_report)
    assert isinstance(plan, CurationPlan)
    # Should have merge + contradiction + fix suggestions
    ops = {s.operation for s in plan.suggestions}
    assert "merge" in ops
    assert "create_contradiction" in ops
    assert "fix_dangling_factor" in ops


def test_generate_plan_empty_inputs():
    """No inputs produce empty plan."""
    plan = generate_cleanup_plan([], [], StructureReport())
    assert plan.suggestions == []


# ── execute_cleanup ──


async def test_execute_cleanup_auto_merges():
    """High-confidence merge suggestions are auto-executed."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="s1",
                operation="merge",
                target_ids=["gcn_a", "gcn_b"],
                confidence=0.98,
                reason="Duplicate",
                evidence={},
            ),
        ]
    )
    nodes = {
        "gcn_a": GlobalCanonicalNode(
            global_canonical_id="gcn_a",
            knowledge_type="claim",
            representative_content="Earth orbits Sun",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg1", version="0.1.0", local_canonical_id="lcn_a")
            ],
            provenance=[PackageRef(package="pkg1", version="0.1.0")],
        ),
        "gcn_b": GlobalCanonicalNode(
            global_canonical_id="gcn_b",
            knowledge_type="claim",
            representative_content="Earth orbits Sun",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg2", version="0.1.0", local_canonical_id="lcn_b")
            ],
            provenance=[PackageRef(package="pkg2", version="0.1.0")],
        ),
    }
    factors: list[FactorNode] = []
    audit_log = AuditLog()

    result = await execute_cleanup(plan, nodes, factors, audit_log)
    assert len(result.executed) == 1
    assert result.executed[0].operation == "merge"
    assert len(audit_log.entries) == 1


async def test_execute_cleanup_skips_low_confidence():
    """Low-confidence suggestions are skipped (discarded)."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="s1",
                operation="merge",
                target_ids=["gcn_a", "gcn_b"],
                confidence=0.50,  # Below review threshold
                reason="Low confidence",
                evidence={},
            ),
        ]
    )
    audit_log = AuditLog()
    result = await execute_cleanup(plan, {}, [], audit_log)
    assert len(result.executed) == 0
    assert len(result.skipped) == 1
    assert len(audit_log.entries) == 0
