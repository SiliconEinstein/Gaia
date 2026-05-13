"""Tests for the prior_dissent / prior_overridden diagnostics.

Both detectors operate on IR-shape dicts (not lang Knowledge) so they can be
unit-tested without a full compile pipeline. The diagnostics are wired into
``gaia inquiry review`` via ``gaia/inquiry/review.py`` (see review.py imports).
"""

from __future__ import annotations

from gaia.inquiry.diagnostics import (
    PRIOR_DISSENT_THRESHOLD,
    detect_prior_dissent,
    detect_prior_overridden,
)


def _claim_with_records(records: list[dict], *, prior: float | None = None) -> dict:
    metadata: dict = {"prior_records": records}
    if prior is not None:
        metadata["prior"] = prior
    return {
        "id": "test::c",
        "label": "c",
        "type": "claim",
        "content": "Test claim",
        "metadata": metadata,
    }


def _ir(claim: dict) -> dict:
    return {"knowledges": [claim]}


# --------------------------------------------------------------------------- #
# prior_dissent                                                               #
# --------------------------------------------------------------------------- #


def test_prior_dissent_fires_when_spread_exceeds_threshold():
    claim = _claim_with_records(
        [
            {"value": 0.30, "source_id": "user_priors", "justification": "literature"},
            {"value": 0.85, "source_id": "continuous_inference", "justification": "engine"},
        ],
        prior=0.30,
    )
    diags = detect_prior_dissent(_ir(claim))
    assert len(diags) == 1
    assert diags[0].kind == "prior_dissent"
    assert diags[0].severity == "warning"
    assert diags[0].data["spread"] > PRIOR_DISSENT_THRESHOLD


def test_prior_dissent_silent_when_spread_below_threshold():
    claim = _claim_with_records(
        [
            {"value": 0.30, "source_id": "user_priors", "justification": "x"},
            {"value": 0.40, "source_id": "continuous_inference", "justification": "y"},
        ],
        prior=0.30,
    )
    diags = detect_prior_dissent(_ir(claim))
    assert diags == []


def test_prior_dissent_silent_with_single_record():
    claim = _claim_with_records(
        [{"value": 0.30, "source_id": "user_priors", "justification": "x"}],
        prior=0.30,
    )
    assert detect_prior_dissent(_ir(claim)) == []


def test_prior_dissent_message_lists_all_records():
    claim = _claim_with_records(
        [
            {"value": 0.20, "source_id": "user_priors", "justification": "a"},
            {"value": 0.50, "source_id": "reviewer_alice", "justification": "b"},
            {"value": 0.80, "source_id": "agent_xyz", "justification": "c"},
        ],
        prior=0.20,
    )
    diags = detect_prior_dissent(_ir(claim))
    assert len(diags) == 1
    msg = diags[0].message
    assert "user_priors" in msg
    assert "reviewer_alice" in msg
    assert "agent_xyz" in msg


def test_prior_dissent_skips_non_claim_knowledges():
    """type=note knowledges with prior_records (shouldn't happen but safety) skip."""
    note = {
        "id": "test::n",
        "label": "n",
        "type": "note",
        "metadata": {
            "prior_records": [
                {"value": 0.1, "source_id": "x", "justification": ""},
                {"value": 0.9, "source_id": "y", "justification": ""},
            ]
        },
    }
    assert detect_prior_dissent({"knowledges": [note]}) == []


# --------------------------------------------------------------------------- #
# prior_overridden                                                            #
# --------------------------------------------------------------------------- #


def test_prior_overridden_fires_when_loser_present():
    claim = _claim_with_records(
        [
            {"value": 0.70, "source_id": "user_priors", "justification": "winner"},
            {"value": 0.45, "source_id": "continuous_inference", "justification": "loser"},
        ],
        prior=0.70,
    )
    diags = detect_prior_overridden(_ir(claim))
    assert len(diags) == 1
    assert diags[0].kind == "prior_overridden"
    assert diags[0].severity == "info"
    assert diags[0].data["n_overridden"] == 1
    assert "continuous_inference" in diags[0].message


def test_prior_overridden_silent_with_single_record():
    claim = _claim_with_records(
        [{"value": 0.70, "source_id": "user_priors", "justification": "x"}],
        prior=0.70,
    )
    assert detect_prior_overridden(_ir(claim)) == []


def test_prior_overridden_silent_when_all_records_share_winning_value():
    """Two records with identical values to the winner are not flagged."""
    claim = _claim_with_records(
        [
            {"value": 0.50, "source_id": "user_priors", "justification": "x"},
            {"value": 0.50, "source_id": "claim_inline", "justification": "y"},
        ],
        prior=0.50,
    )
    assert detect_prior_overridden(_ir(claim)) == []


def test_prior_overridden_silent_when_winning_prior_missing():
    """Without metadata['prior'] no winner can be identified."""
    claim = _claim_with_records(
        [
            {"value": 0.30, "source_id": "user_priors", "justification": "x"},
            {"value": 0.70, "source_id": "continuous_inference", "justification": "y"},
        ],
        prior=None,
    )
    assert detect_prior_overridden(_ir(claim)) == []
