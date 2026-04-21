import pytest
from pydantic import ValidationError

from gaia.ir.review import Review, ReviewManifest, ReviewStatus


def test_review_status_enum():
    assert ReviewStatus.UNREVIEWED == "unreviewed"
    assert ReviewStatus.ACCEPTED == "accepted"
    assert ReviewStatus.REJECTED == "rejected"
    assert ReviewStatus.NEEDS_INPUTS == "needs_inputs"


def test_review_creation():
    review = Review(
        review_id="rev_001",
        action_label="github:blackbody::action::planck_resolves",
        target_kind="strategy",
        target_id="lcs_abc123",
        status=ReviewStatus.UNREVIEWED,
        audit_question="Do premises suffice to establish [@quantum_hyp]?",
        round=1,
    )
    assert review.status == "unreviewed"
    assert review.action_label == "github:blackbody::action::planck_resolves"


def test_review_manifest_latest_status():
    r1 = Review(
        review_id="rev_001",
        action_label="a",
        target_kind="strategy",
        target_id="lcs_1",
        status="unreviewed",
        audit_question="?",
        round=1,
    )
    r2 = Review(
        review_id="rev_002",
        action_label="a",
        target_kind="strategy",
        target_id="lcs_1",
        status="accepted",
        audit_question="?",
        round=2,
    )
    manifest = ReviewManifest(reviews=[r1, r2])
    assert manifest.latest_status("lcs_1") == "accepted"


def test_review_manifest_missing_status():
    assert ReviewManifest().latest_status("missing") is None


def test_review_rejects_probability_fields():
    with pytest.raises(ValidationError):
        Review(
            review_id="rev_bad",
            action_label="a",
            target_kind="strategy",
            target_id="lcs_1",
            status="accepted",
            audit_question="?",
            prior=0.9,
        )
