"""Tests for curation data models."""

from libs.curation.models import (
    AuditEntry,
    ClusterGroup,
    ConflictCandidate,
    CurationPlan,
    CurationResult,
    CurationSuggestion,
    SimilarityPair,
    StructureIssue,
    StructureReport,
)


def test_similarity_pair_defaults():
    pair = SimilarityPair(
        node_a_id="gcn_aaa",
        node_b_id="gcn_bbb",
        similarity_score=0.95,
        method="embedding",
    )
    assert pair.node_a_id == "gcn_aaa"
    assert pair.method == "embedding"


def test_cluster_group():
    group = ClusterGroup(
        cluster_id="cluster_001",
        node_ids=["gcn_aaa", "gcn_bbb", "gcn_ccc"],
        pairs=[
            SimilarityPair(
                node_a_id="gcn_aaa",
                node_b_id="gcn_bbb",
                similarity_score=0.96,
                method="embedding",
            )
        ],
    )
    assert len(group.node_ids) == 3
    assert len(group.pairs) == 1


def test_curation_suggestion_types():
    merge = CurationSuggestion(
        suggestion_id="sug_001",
        operation="merge",
        target_ids=["gcn_aaa", "gcn_bbb"],
        confidence=0.97,
        reason="Embedding cosine 0.97",
        evidence={"cosine": 0.97},
    )
    assert merge.operation == "merge"
    assert merge.confidence == 0.97

    constraint = CurationSuggestion(
        suggestion_id="sug_002",
        operation="create_equivalence",
        target_ids=["gcn_ccc", "gcn_ddd"],
        confidence=0.82,
        reason="Semantically equivalent, different angle",
        evidence={"cosine": 0.82},
    )
    assert constraint.operation == "create_equivalence"


def test_conflict_candidate():
    c = ConflictCandidate(
        node_a_id="gcn_aaa",
        node_b_id="gcn_bbb",
        signal_type="oscillation",
        strength=0.8,
        detail={"iterations_oscillating": 12},
    )
    assert c.signal_type == "oscillation"


def test_structure_issue():
    issue = StructureIssue(
        issue_type="orphan_node",
        severity="warning",
        node_ids=["gcn_orphan"],
        detail="Node has no factor connections",
    )
    assert issue.severity == "warning"


def test_structure_report():
    report = StructureReport(
        issues=[
            StructureIssue(
                issue_type="orphan_node",
                severity="warning",
                node_ids=["gcn_orphan"],
                detail="No factor connections",
            ),
            StructureIssue(
                issue_type="dangling_factor",
                severity="error",
                node_ids=["gcn_deleted"],
                detail="Factor references deleted node",
                factor_ids=["f_abc"],
            ),
        ]
    )
    assert len(report.errors) == 1
    assert len(report.warnings) == 1


def test_audit_entry():
    entry = AuditEntry(
        entry_id="audit_001",
        operation="merge",
        target_ids=["gcn_aaa", "gcn_bbb"],
        suggestion_id="sug_001",
        rollback_data={"removed_node": "gcn_bbb", "redirected_factors": ["f_123"]},
    )
    assert entry.operation == "merge"
    assert entry.rollback_data["removed_node"] == "gcn_bbb"


def test_curation_plan():
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="sug_001",
                operation="merge",
                target_ids=["gcn_aaa", "gcn_bbb"],
                confidence=0.98,
                reason="Near-identical content",
                evidence={},
            ),
            CurationSuggestion(
                suggestion_id="sug_002",
                operation="create_equivalence",
                target_ids=["gcn_ccc", "gcn_ddd"],
                confidence=0.80,
                reason="Equivalent claims",
                evidence={},
            ),
            CurationSuggestion(
                suggestion_id="sug_003",
                operation="merge",
                target_ids=["gcn_eee", "gcn_fff"],
                confidence=0.60,
                reason="Low confidence",
                evidence={},
            ),
        ]
    )
    assert len(plan.auto_approve) == 1  # confidence > 0.95
    assert len(plan.needs_review) == 1  # 0.7 <= confidence <= 0.95
    assert len(plan.discard) == 1  # confidence < 0.7


def test_curation_plan_boundary_at_095():
    """Confidence == 0.95 falls into needs_review (> 0.95 for auto, not >=)."""
    plan = CurationPlan(
        suggestions=[
            CurationSuggestion(
                suggestion_id="sug_boundary",
                operation="merge",
                target_ids=["gcn_x", "gcn_y"],
                confidence=0.95,
                reason="Boundary case",
                evidence={},
            ),
        ]
    )
    assert len(plan.auto_approve) == 0
    assert len(plan.needs_review) == 1


def test_curation_result():
    result = CurationResult(
        executed=[],
        skipped=[],
        audit_entries=[],
        structure_report=StructureReport(issues=[]),
    )
    assert len(result.executed) == 0
