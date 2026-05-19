"""Distribution wrapper + operator overloading tests.

Distribution is a Lang-only Knowledge subclass that composes a
``_BaseDistribution`` (the existing scipy-backed pydantic literal) and adds
identity, content, and operator-based predicate / equation construction.
"""

from __future__ import annotations

import math

import pytest

from gaia.engine.bayes.distributions.continuous import Normal as _BaseNormal
from gaia.engine.lang import (
    Beta,
    Binomial,
    BoolExpr,
    DerivedDistribution,
    Distribution,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Poisson,
)
from gaia.engine.lang.runtime.knowledge import Knowledge


def test_normal_factory_returns_distribution_with_content():
    n = Normal("T_c of H3S", mu=200, sigma=50)
    assert isinstance(n, Distribution)
    assert isinstance(n, Knowledge)
    assert n.content == "T_c of H3S"
    assert n.kind == "normal"
    assert n.params == {"mu": 200, "sigma": 50}


def test_distribution_delegates_logpdf_cdf_support_to_impl():
    n = Normal("X", mu=0, sigma=1)
    # Standard normal: logpdf(0) = -log(sqrt(2*pi)) ≈ -0.919
    assert math.isclose(n.logpdf(0.0), -math.log(math.sqrt(2 * math.pi)), rel_tol=1e-6)
    # cdf(0) = 0.5
    assert math.isclose(n.cdf(0.0), 0.5, rel_tol=1e-6)
    # Support is the whole real line for Normal
    assert n.support() == (-math.inf, math.inf)


def test_distribution_rejects_non_basedistribution_impl():
    with pytest.raises(TypeError, match="must be a _BaseDistribution"):
        Distribution("bad", impl="not a distribution")  # type: ignore[arg-type]


def test_distribution_can_be_constructed_with_explicit_impl():
    impl = _BaseNormal(mu=5, sigma=2)
    d = Distribution("explicit form", impl=impl)
    assert d.params == {"mu": 5, "sigma": 2}
    assert d.impl is impl


def test_factories_for_all_distribution_families():
    assert Normal("n", mu=0, sigma=1).kind == "normal"
    assert LogNormal("ln", mu=0, sigma=1).kind == "lognormal"
    assert Beta("b", alpha=2, beta=2).kind == "beta"
    assert Exponential("e", rate=1).kind == "exponential"
    assert Gamma("g", alpha=2, rate=1).kind == "gamma"
    assert Binomial("bn", n=10, p=0.5).kind == "binomial"
    assert Poisson("p", rate=3).kind == "poisson"


# --------------------------------------------------------------------------- #
# Operator overloading                                                        #
# --------------------------------------------------------------------------- #


def test_inequality_returns_boolexpr():
    k = LogNormal("k", mu=0, sigma=1)
    expr = k > 1.5
    assert isinstance(expr, BoolExpr)
    assert expr.op == ">"
    assert expr.left is k
    assert expr.right == 1.5


def test_all_inequality_operators_produce_boolexpr():
    k = Normal("k", mu=0, sigma=1)
    for op_str, expr in {
        ">": k > 1,
        ">=": k >= 1,
        "<": k < 1,
        "<=": k <= 1,
        "==": k == 1,
        "!=": k != 1,
    }.items():
        assert isinstance(expr, BoolExpr)
        assert expr.op == op_str


def test_arithmetic_returns_derived_distribution():
    A = LogNormal("A", mu=0, sigma=1)
    expr = A * 2 + 3
    assert isinstance(expr, DerivedDistribution)


def test_arithmetic_chains_correctly():
    A = Normal("A", mu=10, sigma=1)
    Ea = Normal("Ea", mu=50, sigma=10)
    R = 8.314
    T = 298.15
    expr = A * (-Ea / (R * T))
    assert isinstance(expr, DerivedDistribution)


def test_distribution_eq_with_derived_returns_boolexpr_equation_op():
    A = Normal("A", mu=10, sigma=1)
    B = Normal("B", mu=10, sigma=1)
    expr = A == B
    assert isinstance(expr, BoolExpr)
    assert expr.op == "=="


# --------------------------------------------------------------------------- #
# BoolExpr semantics                                                          #
# --------------------------------------------------------------------------- #


def test_boolexpr_bool_raises():
    k = Normal("k", mu=0, sigma=1)
    expr = k > 0
    with pytest.raises(TypeError, match="does not have a Python truth value"):
        bool(expr)
    # The most common author mistake: `if k > 0:` —  same path:
    with pytest.raises(TypeError):
        if k > 0:  # type: ignore[truthy-iterable]
            pass


def test_boolexpr_invalid_op_rejected():
    with pytest.raises(ValueError, match="BoolExpr op must be"):
        BoolExpr("invalid", 1, 2)  # type: ignore[arg-type]


def test_derived_distribution_invalid_op_rejected():
    with pytest.raises(ValueError, match="op must be one of"):
        DerivedDistribution("bad", 1, 2)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Identity / hash semantics                                                   #
# --------------------------------------------------------------------------- #


def test_distribution_hash_is_identity_based():
    a = Normal("X", mu=0, sigma=1)
    b = Normal("X", mu=0, sigma=1)
    assert hash(a) != hash(b)
    assert hash(a) == hash(a)


def test_distribution_can_sit_in_sets():
    a = Normal("X", mu=0, sigma=1)
    b = Normal("Y", mu=0, sigma=1)
    s = {a, b, a}
    assert len(s) == 2
    assert a in s
    assert b in s


def test_distribution_eq_returns_boolexpr_not_bool():
    a = Normal("X", mu=0, sigma=1)
    b = Normal("Y", mu=0, sigma=1)
    result = a == b
    assert isinstance(result, BoolExpr)
    # Identity check requires `is`
    assert a is not b
    assert a is a


def test_distribution_ne_returns_boolexpr():
    a = Normal("X", mu=0, sigma=1)
    b = Normal("Y", mu=0, sigma=1)
    result = a != b
    assert isinstance(result, BoolExpr)


def test_boolexpr_hash_is_identity_based():
    k = Normal("k", mu=0, sigma=1)
    e1 = k > 1
    e2 = k > 1
    # Different BoolExpr instances even though structurally identical.
    assert hash(e1) != hash(e2)
    assert {e1, e2, e1} == {e1, e2}


# --------------------------------------------------------------------------- #
# Lang-only registration                                                      #
# --------------------------------------------------------------------------- #


def test_distribution_does_not_enter_ir_knowledge_map():
    """Distribution mirrors Variable's Lang-only treatment.

    It associates with the active package for provenance but is NOT registered
    in the package's knowledge map (no IR Knowledge node).
    """
    from gaia.engine.lang.runtime.knowledge import _current_package
    from gaia.engine.lang.runtime.package import CollectedPackage

    pkg = CollectedPackage(name="dist_lang_only_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        T_c = Normal("T_c", mu=200, sigma=50)
    finally:
        _current_package.reset(token)
    # T_c associated with the package for provenance
    assert T_c._package is pkg
    # but does NOT appear in the package's IR-bound knowledge list
    assert T_c not in pkg.knowledge


def test_distribution_radd_rsub_rmul_rtruediv():
    """Arithmetic with constant on the left side."""
    A = Normal("A", mu=10, sigma=1)
    assert isinstance(2 + A, DerivedDistribution)
    assert isinstance(2 - A, DerivedDistribution)
    assert isinstance(2 * A, DerivedDistribution)
    assert isinstance(2 / A, DerivedDistribution)
    assert isinstance(-A, DerivedDistribution)
