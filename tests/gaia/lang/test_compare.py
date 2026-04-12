"""Tests for the compare() DSL function."""

from gaia.lang import claim, compare


def test_compare_basic():
    """compare() creates Strategy with auto-generated comparison claim."""
    pred_h = claim("Prediction H.")
    pred_h.label = "H"
    pred_alt = claim("Prediction Alt.")
    pred_alt.label = "Alt"
    obs = claim("Observation.")
    obs.label = "Obs"

    s = compare(pred_h, pred_alt, obs)
    assert s.type == "compare"
    assert len(s.premises) == 3
    assert s.premises[0] is pred_h
    assert s.premises[1] is pred_alt
    assert s.premises[2] is obs
    assert s.conclusion is not None
    assert "comparison" in s.conclusion.content


def test_compare_conclusion_is_comparison_claim():
    """compare() conclusion has helper_kind='comparison_result'."""
    pred_h = claim("Prediction H.")
    pred_h.label = "H"
    pred_alt = claim("Prediction Alt.")
    pred_alt.label = "Alt"
    obs = claim("Observation.")
    obs.label = "Obs"

    s = compare(pred_h, pred_alt, obs)
    assert s.conclusion.type == "claim"
    assert s.conclusion.metadata["helper_kind"] == "comparison_result"
    assert s.conclusion.metadata["generated"] is True


def test_compare_uses_labels_in_content():
    """compare() uses labels in auto-generated content when available."""
    pred_h = claim("Prediction H.")
    pred_h.label = "pred_h"
    pred_alt = claim("Prediction Alt.")
    pred_alt.label = "pred_alt"
    obs = claim("Observation.")
    obs.label = "obs"

    s = compare(pred_h, pred_alt, obs)
    assert "pred_h" in s.conclusion.content
    assert "pred_alt" in s.conclusion.content
    assert "obs" in s.conclusion.content


def test_compare_fallback_labels():
    """compare() uses 'H', 'Alt', 'Obs' fallback when labels are None."""
    pred_h = claim("Prediction H.")
    pred_alt = claim("Prediction Alt.")
    obs = claim("Observation.")

    s = compare(pred_h, pred_alt, obs)
    assert "H" in s.conclusion.content
    assert "Alt" in s.conclusion.content
    assert "Obs" in s.conclusion.content
