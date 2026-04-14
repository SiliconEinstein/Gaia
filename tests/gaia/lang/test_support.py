"""Tests for the support() DSL function."""

import pytest

from gaia.lang import claim, support


def test_support_basic():
    """support() creates Strategy with type='support'."""
    a = claim("A.")
    b = claim("B.")
    s = support(
        premises=[a],
        conclusion=b,
        reason="A implies B",
        prior=0.9,
    )
    assert s.type == "support"
    assert s.conclusion is b
    assert len(s.premises) == 1
    assert s.reason == "A implies B"
    assert s.metadata["prior"] == 0.9


def test_support_requires_premise():
    """support() raises ValueError for empty premises."""
    b = claim("B.")
    with pytest.raises(ValueError, match="at least 1 premise"):
        support(premises=[], conclusion=b)


def test_support_multi_premise():
    """support() works with multiple premises."""
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    s = support(premises=[a, b], conclusion=c)
    assert s.type == "support"
    assert len(s.premises) == 2
    assert s.conclusion is c


# ---------------------------------------------------------------------------
# reason + prior pairing
# ---------------------------------------------------------------------------


def test_support_prior_stored():
    """support() stores prior in metadata."""
    s = support(
        [claim("H")],
        claim("O"),
        reason="H predicts",
        prior=0.95,
    )
    assert s.metadata["prior"] == 0.95


def test_support_reason_without_prior_raises():
    """support() reason without prior raises ValueError."""
    with pytest.raises(ValueError, match="reason.*prior.*paired"):
        support([claim("H")], claim("O"), reason="no prior given")


def test_support_no_reason_no_prior_ok():
    """support() without reason or prior is fine."""
    s = support([claim("H")], claim("O"))
    assert "prior" not in s.metadata
