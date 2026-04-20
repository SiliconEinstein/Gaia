"""Tests for v6 ReviewManifest/Warrant models."""

import pytest

from gaia.ir import ReviewManifest, ReviewNote, Warrant, WarrantStatus


def test_review_manifest_round_trip():
    manifest = ReviewManifest(
        warrants=[
            Warrant(
                id="warrant_1",
                subject_strategy_id="lcs_abc",
                subject_hash="sha256:abc",
                status="accepted",
                review_question="Is this likelihood use acceptable?",
                reviewer_notes=[ReviewNote(author="reviewer", note="Looks good.")],
            )
        ]
    )

    loaded = ReviewManifest.model_validate(manifest.model_dump(mode="json"))
    assert loaded.warrants[0].status == WarrantStatus.ACCEPTED
    assert loaded.warrants[0].reviewer_notes[0].note == "Looks good."


def test_needs_inputs_requires_required_inputs():
    with pytest.raises(ValueError, match="required_inputs"):
        Warrant(
            id="warrant_1",
            subject_strategy_id="lcs_abc",
            subject_hash="sha256:abc",
            status="needs_inputs",
        )


def test_rejected_requires_resolution():
    with pytest.raises(ValueError, match="resolution"):
        Warrant(
            id="warrant_1",
            subject_strategy_id="lcs_abc",
            subject_hash="sha256:abc",
            status="rejected",
        )

