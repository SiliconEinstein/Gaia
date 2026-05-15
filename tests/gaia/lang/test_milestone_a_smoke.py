"""Milestone A AST smoke — build Mendel + universal + causal with raw constructors."""

from gaia.engine.lang import (
    Causes,
    Claim,
    ClaimKind,
    Constant,
    Domain,
    Equals,
    Forall,
    FunctionApp,
    FunctionSymbol,
    Greater,
    Land,
    Lnot,
    Nat,
    Probability,
    Real,
    UserPredicate,
    Variable,
    is_formula,
)
from gaia.engine.lang.formula.symbols import PredicateSymbol


def test_mendel_parameter_assertion():
    """H asserts P(dominant) = 0.75 via Equals(p, 0.75)."""
    p = Variable(symbol="p", domain=Probability)
    H = Claim(
        content="Mendelian 3:1 segregation: P(dominant) = 0.75.",
        formula=Equals(left=p, right=Constant(0.75, Probability)),
        kind=ClaimKind.PARAMETER,
        prior=0.5,
    )
    assert H.kind is ClaimKind.PARAMETER
    assert is_formula(H.formula)
    assert H.formula.left is p


def test_mendel_data_formula():
    """D records count data via conjunction of Equals; observation is an action."""
    n_obs = Variable(symbol="n_obs", domain=Nat, value=395)
    k_obs = Variable(symbol="k_obs", domain=Nat, value=295)
    n = Variable(symbol="n", domain=Nat)
    k = Variable(symbol="k", domain=Nat)
    formula = Land(
        operands=(
            Equals(left=n, right=n_obs),
            Equals(left=k, right=k_obs),
        )
    )
    D = Claim(
        content="295 of 395 F2 plants are dominant.",
        formula=formula,
        kind=ClaimKind.GENERAL,
        prior=0.95,
    )
    assert D.kind is ClaimKind.GENERAL
    assert len(D.formula.operands) == 2


def test_universal_law_with_quantifier():
    """All particles have positive energy: Forall(x, E(x) > 0)."""
    Particle = Domain(content="Subatomic particles", members=["p1", "p2", "p3"])
    x = Variable(symbol="x", domain=Particle)
    E = FunctionSymbol(name="E", arg_domains=(Particle,), result_domain=Real)
    body = Greater(
        left=FunctionApp(symbol=E, args=(x,)),
        right=Constant(0, Real),
    )
    universal = Claim(
        content="All particles have positive energy.",
        formula=Forall(variable=x, body=body),
        kind=ClaimKind.QUANTIFIED,
        prior=0.95,
    )
    assert universal.kind is ClaimKind.QUANTIFIED
    assert universal.formula.variable is x


def test_causal_claim():
    """Causal predicate marker."""
    co2 = Variable(symbol="co2", domain=Real)
    temp = Variable(symbol="temp", domain=Real)
    C = Claim(
        content="Rising CO2 causes increased global mean temperature.",
        formula=Causes(cause=co2, effect=temp),
        kind=ClaimKind.CAUSAL,
        prior=0.9,
    )
    assert C.kind is ClaimKind.CAUSAL
    assert C.formula.cause is co2


def test_compound_formula_round_trip():
    """Not (P and not Q) — connective composition."""
    P = Equals(left=Constant(1, Nat), right=Constant(1, Nat))
    Q = Equals(left=Constant(2, Nat), right=Constant(2, Nat))
    f = Lnot(operand=Land(operands=(P, Lnot(operand=Q))))
    assert is_formula(f)


def test_user_predicate_in_compound():
    """Land(Stable(a), Stable(b))."""
    a = Variable(symbol="a", domain=Nat)
    b = Variable(symbol="b", domain=Nat)
    Stable = PredicateSymbol(name="Stable", arg_domains=(Nat,))
    f = Land(
        operands=(
            UserPredicate(symbol=Stable, args=(a,)),
            UserPredicate(symbol=Stable, args=(b,)),
        )
    )
    assert is_formula(f)
    assert len(f.operands) == 2
