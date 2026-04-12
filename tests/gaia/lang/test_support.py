"""Tests for the support() DSL function."""

import pytest

from gaia.lang import claim, support


def test_support_basic():
    """support() creates Strategy with type='support', stores reverse_reason in metadata."""
    a = claim("A.")
    b = claim("B.")
    s = support(premises=[a], conclusion=b, reason="A implies B", reverse_reason="B implies A")
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
