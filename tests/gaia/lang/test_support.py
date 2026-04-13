"""Tests for the support() DSL function."""

import pytest

from gaia.lang import claim, support


def test_support_basic():
    """support() creates Strategy with type='support', stores reverse_reason in metadata."""
    a = claim("A.")
    b = claim("B.")
    s = support(
        premises=[a],
        conclusion=b,
        reason="A implies B",
        prior=0.9,
        reverse_reason="B implies A",
        reverse_prior=0.9,
    )
    assert s.type == "support"
    assert s.conclusion is b
    assert len(s.premises) == 1
    assert s.reason == "A implies B"
    assert s.metadata["reverse_reason"] == "B implies A"


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


def test_support_default_reverse_reason():
    """support() defaults reverse_reason to empty string."""
    a = claim("A.")
    b = claim("B.")
    s = support(premises=[a], conclusion=b)
    assert s.metadata["reverse_reason"] == ""


# ---------------------------------------------------------------------------
# reason + prior pairing
# ---------------------------------------------------------------------------


def test_support_prior_stored():
    """support() stores prior and reverse_prior in metadata."""
    s = support(
        [claim("H")],
        claim("O"),
        reason="H predicts",
        prior=0.95,
        reverse_reason="O confirms",
        reverse_prior=0.8,
    )
    assert s.metadata["prior"] == 0.95
    assert s.metadata["reverse_prior"] == 0.8


def test_support_reason_without_prior_raises():
    """support() reason without prior raises ValueError."""
    with pytest.raises(ValueError, match="reason.*prior.*paired"):
        support([claim("H")], claim("O"), reason="no prior given")


def test_support_reverse_reason_without_reverse_prior_raises():
    """support() reverse_reason without reverse_prior raises ValueError."""
    with pytest.raises(ValueError, match="reason.*prior.*paired"):
        support(
            [claim("H")],
            claim("O"),
            reverse_reason="no reverse prior",
        )


def test_support_no_reason_no_prior_ok():
    """support() without reason or prior is fine."""
    s = support([claim("H")], claim("O"))
    assert "prior" not in s.metadata
    assert "reverse_prior" not in s.metadata


def test_support_forward_only_prior():
    """support() with forward reason+prior, no reverse, is ok."""
    s = support(
        [claim("H")],
        claim("O"),
        reason="H predicts",
        prior=0.9,
    )
    assert s.metadata["prior"] == 0.9
    assert "reverse_prior" not in s.metadata
