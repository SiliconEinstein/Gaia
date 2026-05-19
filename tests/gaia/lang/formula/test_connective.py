"""Tests for Formula AST connectives."""

import pytest

from gaia.engine.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.engine.lang.formula.predicate import Equals, is_formula
from gaia.engine.lang.formula.primitives import Nat
from gaia.engine.lang.formula.term import Constant


def _atom(v: int) -> Equals:
    return Equals(left=Constant(v, Nat), right=Constant(v, Nat))


def test_land_two_args():
    a, b = _atom(1), _atom(2)
    f = Land(operands=(a, b))
    assert f.operands == (a, b)
    assert is_formula(f)


def test_land_n_args():
    f = Land(operands=tuple(_atom(i) for i in range(5)))
    assert len(f.operands) == 5


def test_land_requires_at_least_two():
    with pytest.raises(ValueError, match="at least two"):
        Land(operands=(_atom(1),))


def test_land_operands_must_be_formulas():
    with pytest.raises(TypeError, match="not a Formula"):
        Land(operands=(_atom(1), "not_a_formula"))  # type: ignore[arg-type]


def test_lor_basic():
    a, b = _atom(1), _atom(2)
    f = Lor(operands=(a, b))
    assert is_formula(f)


def test_lnot_single_operand():
    a = _atom(1)
    f = Lnot(operand=a)
    assert f.operand is a
    assert is_formula(f)


def test_lnot_operand_must_be_formula():
    with pytest.raises(TypeError, match="not a Formula"):
        Lnot(operand="x")  # type: ignore[arg-type]


def test_implies_basic():
    a, b = _atom(1), _atom(2)
    f = Implies(antecedent=a, consequent=b)
    assert f.antecedent is a
    assert f.consequent is b
    assert is_formula(f)


def test_iff_basic():
    a, b = _atom(1), _atom(2)
    f = Iff(left=a, right=b)
    assert is_formula(f)


def test_nested_compound():
    a, b, c = _atom(1), _atom(2), _atom(3)
    inner = Lor(operands=(a, b))
    outer = Land(operands=(inner, Lnot(operand=c)))
    assert is_formula(outer)
    assert outer.operands[0].operands[0] is a
