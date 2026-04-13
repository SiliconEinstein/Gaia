"""Tests for the compare() DSL function."""

import pytest

from gaia.lang import claim, compare


def test_compare_basic():
    """compare() creates Strategy with type='compare' and auto-generated conclusion."""
    pred_h = claim("GR predicts 1.75 arcsec.")
    pred_alt = claim("Newtonian predicts 0.87 arcsec.")
    obs = claim("Observed 1.75 arcsec.")

    s = compare(pred_h, pred_alt, obs, reason="GR matches observation better", prior=0.9)
    assert s.type == "compare"
    assert len(s.premises) == 3
    assert s.premises[0] is pred_h
    assert s.premises[1] is pred_alt
    assert s.premises[2] is obs
    assert s.conclusion is not None
    assert s.conclusion.type == "claim"
    assert s.conclusion.metadata["helper_kind"] == "comparison_claim"
    assert s.conclusion.metadata["generated"] is True
    assert s.reason == "GR matches observation better"


def test_compare_conclusion_content():
    """compare() auto-generated conclusion references the inputs."""
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")
    obs = claim("Obs.")

    s = compare(pred_h, pred_alt, obs)
    assert "Pred H." in s.conclusion.content
    assert "Pred Alt." in s.conclusion.content
    assert "Obs." in s.conclusion.content


def test_compare_with_background():
    """compare() passes background through."""
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")
    obs = claim("Obs.")
    bg = claim("Background context.")

    s = compare(pred_h, pred_alt, obs, background=[bg])
    assert s.background == [bg]


def test_compare_attaches_to_conclusion():
    """compare() attaches strategy to auto-generated conclusion."""
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")
    obs = claim("Obs.")

    s = compare(pred_h, pred_alt, obs)
    assert s.conclusion.strategy is s


# ---------------------------------------------------------------------------
# reason + prior pairing
# ---------------------------------------------------------------------------


def test_compare_prior_stored():
    """compare() stores prior in metadata."""
    pred_h = claim("Pred H.")
    pred_alt = claim("Pred Alt.")
    obs = claim("Obs.")

    comp = compare(pred_h, pred_alt, obs, reason="same exp", prior=0.85)
    assert comp.metadata["prior"] == 0.85


def test_compare_reason_without_prior_raises():
    """compare() reason without prior raises ValueError."""
    with pytest.raises(ValueError, match="reason.*prior.*paired"):
        compare(claim("P1"), claim("P2"), claim("O"), reason="no prior")


def test_compare_no_reason_no_prior_ok():
    """compare() without reason or prior is fine."""
    comp = compare(claim("P1"), claim("P2"), claim("O"))
    assert "prior" not in comp.metadata
