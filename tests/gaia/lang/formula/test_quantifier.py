"""Tests for Formula AST quantifiers."""

import pytest

from gaia.lang.formula.predicate import Equals, is_formula
from gaia.lang.formula.quantifier import Exists, Forall
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Nat


def _body() -> Equals:
    return Equals(left=Constant(1, Nat), right=Constant(1, Nat))


def test_forall_with_primitive_domain_variable():
    x = Variable(symbol="x", domain=Nat)
    q = Forall(variable=x, body=_body())
    assert q.variable is x
    assert is_formula(q)


def test_forall_with_custom_domain_variable():
    Particle = Domain(content="x", members=["p1", "p2"])
    x = Variable(symbol="x", domain=Particle)
    q = Forall(variable=x, body=_body())
    assert q.variable is x


def test_forall_variable_must_be_variable():
    with pytest.raises(TypeError, match="Variable"):
        Forall(variable="x", body=_body())  # type: ignore[arg-type]


def test_forall_body_must_be_formula():
    x = Variable(symbol="x", domain=Nat)
    with pytest.raises(TypeError, match="body"):
        Forall(variable=x, body="not_formula")  # type: ignore[arg-type]


def test_forall_with_bound_variable_rejected():
    """Spec §3: a variable that already has a value can't be quantifier-bound."""
    x = Variable(symbol="x", domain=Nat, value=0)
    with pytest.raises(ValueError, match="bound"):
        Forall(variable=x, body=_body())


def test_exists_basic():
    x = Variable(symbol="x", domain=Nat)
    q = Exists(variable=x, body=_body())
    assert is_formula(q)


def test_exists_same_validations():
    x = Variable(symbol="x", domain=Nat, value=0)
    with pytest.raises(ValueError, match="bound"):
        Exists(variable=x, body=_body())
