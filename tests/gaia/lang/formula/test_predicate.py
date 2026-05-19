"""Tests for Formula AST Predicate hierarchy (typed)."""

import pytest

from gaia.engine.lang.formula.predicate import (
    ClaimAtom,
    Equals,
    Formula,  # noqa: F401
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
    is_formula,
)
from gaia.engine.lang.formula.primitives import Nat, Probability, Real
from gaia.engine.lang.formula.symbols import PredicateSymbol
from gaia.engine.lang.formula.term import Constant
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable


def test_equals_basic():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(value=0.75, primitive=Probability))
    assert eq.left is p
    assert eq.right.value == 0.75


def test_equals_is_formula():
    eq = Equals(left=Constant(1, Nat), right=Constant(1, Nat))
    assert is_formula(eq)


def test_equals_args_must_be_terms():
    with pytest.raises(TypeError):
        Equals(left="not_a_term", right=Constant(1, Nat))  # type: ignore[arg-type]


def test_comparisons():
    n = Variable(symbol="n", domain=Nat, value=395)
    z = Constant(value=0, primitive=Nat)
    assert is_formula(Greater(left=n, right=z))
    assert is_formula(Less(left=n, right=z))
    assert is_formula(GreaterEqual(left=n, right=z))
    assert is_formula(LessEqual(left=n, right=z))
    assert is_formula(NotEquals(left=n, right=z))


def test_claim_atom_holds_a_claim_reference():
    c = Claim(content="P", prior=0.5)
    atom = ClaimAtom(claim=c)
    assert atom.claim is c


def test_claim_atom_is_formula():
    c = Claim(content="P", prior=0.5)
    atom = ClaimAtom(claim=c)
    assert is_formula(atom)


def test_claim_atom_rejects_non_claim():
    with pytest.raises(TypeError, match="Claim"):
        ClaimAtom(claim="not_a_claim")  # type: ignore[arg-type]


def test_user_predicate_typed():
    n = Variable(symbol="n", domain=Nat)
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    pred = UserPredicate(symbol=Stable, args=(n,))
    assert pred.symbol is Stable
    assert pred.args == (n,)


def test_user_predicate_arity_mismatch_rejected():
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    with pytest.raises(ValueError, match="arity"):
        UserPredicate(symbol=Stable, args=())
    with pytest.raises(ValueError, match="arity"):
        UserPredicate(symbol=Stable, args=(Constant(1, Nat), Constant(2, Nat)))


def test_user_predicate_arg_domain_mismatch_rejected():
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    real_var = Variable(symbol="r", domain=Real)
    with pytest.raises(TypeError, match="domain"):
        UserPredicate(symbol=Stable, args=(real_var,))


def test_user_predicate_is_formula():
    P = PredicateSymbol(name="P", arg_domains=(Nat,))
    pred = UserPredicate(symbol=P, args=(Constant(1, Nat),))
    assert is_formula(pred)


def test_user_predicate_args_must_be_terms():
    P = PredicateSymbol(name="P", arg_domains=(Nat,))
    with pytest.raises(TypeError, match="argument"):
        UserPredicate(symbol=P, args=(123,))  # type: ignore[arg-type]


def test_is_formula_rejects_terms():
    """A Term alone is not a Formula — it has no truth value."""
    assert not is_formula(Constant(1, Nat))
    assert not is_formula(Variable(symbol="x", domain=Nat))


def test_is_formula_rejects_arbitrary():
    assert not is_formula("hello")
    assert not is_formula(42)
    assert not is_formula([Equals(Constant(1, Nat), Constant(1, Nat))])


def test_marker_only_causes_predicate_is_not_exported():
    import gaia.engine.lang.formula.predicate as predicate

    assert not hasattr(predicate, "Causes")
