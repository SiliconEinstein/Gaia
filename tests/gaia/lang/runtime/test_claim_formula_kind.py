"""Tests for additive Claim.formula and Claim.kind extensions."""

import pytest

from gaia.lang.formula.predicate import Equals
from gaia.lang.formula.term import Constant
from gaia.lang.runtime.knowledge import Claim, ClaimKind
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import Probability


def test_claim_default_formula_is_none():
    c = Claim(content="P", prior=0.5)
    assert c.formula is None


def test_claim_default_kind_is_general():
    c = Claim(content="P", prior=0.5)
    assert c.kind is ClaimKind.GENERAL


def test_claim_with_formula():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, Probability))
    c = Claim(content="Mendelian", formula=eq, prior=0.5)
    assert c.formula is eq


def test_claim_with_explicit_kind():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, Probability))
    c = Claim(content="Mendelian", formula=eq, kind=ClaimKind.PARAMETER, prior=0.5)
    assert c.kind is ClaimKind.PARAMETER


def test_claim_kind_enum_values():
    assert {k.value for k in ClaimKind} == {
        "general",
        "parameter",
        "quantified",
        "causal",
    }


def test_claim_formula_must_be_formula_or_none():
    with pytest.raises(TypeError, match="formula"):
        Claim(content="P", formula="not_a_formula", prior=0.5)  # type: ignore[arg-type]


def test_claim_kind_must_be_claimkind_member():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.75, Probability))
    with pytest.raises(TypeError, match="kind"):
        Claim(content="P", formula=eq, kind="parameter", prior=0.5)  # type: ignore[arg-type]


def test_existing_claim_construction_unchanged():
    """Plain Claim authoring like in v0.5 still works — formula/kind opt-in."""
    c = Claim(content="Mendelian 3:1 segregation holds.", prior=0.5)
    assert c.formula is None
    assert c.kind is ClaimKind.GENERAL
    assert c.prior == 0.5


def test_parameterized_claim_subclass_still_works():
    """Regression: docstring template + _param_fields path must not be disturbed.

    A parameterized Claim subclass renders content from its docstring, substituting
    [@param_name] for Knowledge-typed params and {param_name} for value params.
    """
    from gaia.lang.runtime.knowledge import Knowledge

    note = Knowledge(content="experiment X", type="note", label="exp_x")

    class MyClaim(Claim):
        """We observed {n} successes in [@exp]."""

        n: int = 0
        exp: Knowledge = None  # type: ignore[assignment]

    c = MyClaim(n=5, exp=note, prior=0.7)
    # template should have rendered
    assert "5" in c.content
    assert "exp_x" in c.content
    # prior preserved
    assert c.prior == 0.7
    # formula/kind defaults
    assert c.formula is None
    assert c.kind is ClaimKind.GENERAL
    # parameters list populated
    names = [p["name"] for p in c.parameters]
    assert "n" in names
    assert "exp" in names


def test_parameterized_claim_subclass_accepts_formula_and_kind():
    """The new fields work on subclasses too."""
    from gaia.lang.runtime.knowledge import Knowledge

    note = Knowledge(content="experiment X", type="note", label="exp_x")

    class MyClaim(Claim):
        """{n} hits in [@exp]."""

        n: int = 0
        exp: Knowledge = None  # type: ignore[assignment]

    p = Variable(symbol="p", domain=Probability)
    eq = Equals(left=p, right=Constant(0.5, Probability))
    c = MyClaim(n=3, exp=note, formula=eq, kind=ClaimKind.PARAMETER, prior=0.6)
    assert c.formula is eq
    assert c.kind is ClaimKind.PARAMETER
