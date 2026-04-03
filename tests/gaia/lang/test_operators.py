"""Tests for Gaia Lang v5 operator functions."""

from gaia.lang import claim, contradiction, complement, disjunction, equivalence


def test_contradiction_creates_helper_claim():
    a = claim("A is true.")
    b = claim("B is true.")
    helper = contradiction(a, b, reason="A and B cannot both be true")
    assert helper.type == "claim"
    assert "not_both_true" in helper.content


def test_contradiction_helper_usable_in_given():
    a = claim("A.")
    b = claim("B.")
    contra = contradiction(a, b, reason="conflict")
    c = claim("C.", given=[contra])
    assert contra in c.strategy.premises


def test_equivalence_creates_helper_claim():
    a = claim("Predicted obs.")
    b = claim("Actual obs.")
    helper = equivalence(a, b, reason="Match")
    assert "same_truth" in helper.content


def test_complement_creates_helper_claim():
    a = claim("Classical.")
    b = claim("Quantum.")
    helper = complement(a, b, reason="Opposite")
    assert "opposite_truth" in helper.content


def test_disjunction_creates_helper_claim():
    a = claim("Mechanism A.")
    b = claim("Mechanism B.")
    c = claim("Mechanism C.")
    helper = disjunction(a, b, c, reason="At least one")
    assert "any_true" in helper.content
