"""Tests for the simplified curation reviewer."""

from libs.curation.models import CurationSuggestion
from libs.curation.reviewer import CurationReviewer


def test_reviewer_approves_high_similarity_equivalence():
    """Equivalence with similarity > 0.85 should be approved."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_equivalence",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.88,
        reason="Semantically similar",
        evidence={"cosine": 0.88},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"


def test_reviewer_rejects_low_evidence_merge():
    """Merge without strong evidence should be rejected."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.75,
        reason="Might be duplicate",
        evidence={"cosine": 0.75},
    )
    decision = reviewer.review(suggestion)
    assert decision == "reject"


def test_reviewer_approves_high_confidence_contradiction():
    """Contradiction with high strength should be approved."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_contradiction",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.85,
        reason="Strong conflict signal",
        evidence={"belief_drop": 0.3},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"


def test_reviewer_rejects_weak_contradiction():
    """Contradiction with weak signal should be rejected."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="create_contradiction",
        target_ids=["gcn_a", "gcn_b"],
        confidence=0.72,
        reason="Weak conflict",
        evidence={"belief_drop": 0.05},
    )
    decision = reviewer.review(suggestion)
    assert decision == "reject"


def test_reviewer_approves_orphan_archive():
    """Orphan archival is low-risk, should approve."""
    reviewer = CurationReviewer()
    suggestion = CurationSuggestion(
        operation="archive_orphan",
        target_ids=["gcn_orphan"],
        confidence=0.80,
        reason="No connections",
        evidence={},
    )
    decision = reviewer.review(suggestion)
    assert decision == "approve"
