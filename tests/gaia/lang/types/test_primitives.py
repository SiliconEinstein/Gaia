"""Tests for primitive type tokens."""

import pytest

from gaia.lang.types.primitives import Bool, Nat, PrimitiveType, Probability, Real


def test_primitives_are_distinct_singletons():
    assert Nat is Nat
    assert Nat is not Real
    assert Real is not Probability
    assert Probability is not Bool


def test_primitive_has_name():
    assert Nat.name == "Nat"
    assert Real.name == "Real"
    assert Probability.name == "Probability"
    assert Bool.name == "Bool"


def test_primitive_validates_value():
    assert Nat.accepts(0) is True
    assert Nat.accepts(395) is True
    assert Nat.accepts(-1) is False
    assert Nat.accepts(1.5) is False

    assert Real.accepts(1.5) is True
    assert Real.accepts(0) is True

    assert Probability.accepts(0.0) is True
    assert Probability.accepts(0.75) is True
    assert Probability.accepts(1.0) is True
    assert Probability.accepts(1.5) is False
    assert Probability.accepts(-0.1) is False

    assert Bool.accepts(True) is True
    assert Bool.accepts(False) is True
    assert Bool.accepts(0) is False  # strict bool, not int


def test_primitive_repr():
    assert repr(Nat) == "Nat"
    assert repr(Probability) == "Probability"


def test_primitive_type_is_sealed():
    """Cannot construct ad-hoc PrimitiveType outside the four built-ins."""
    with pytest.raises(TypeError):
        PrimitiveType("MadeUp", lambda v: True)
