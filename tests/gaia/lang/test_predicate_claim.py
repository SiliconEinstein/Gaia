"""``claim(content, BoolExpr)`` predicate-claim tests.

A predicate claim wraps a BoolExpr proposition; the compiler reads
``metadata['predicate']`` and computes the prior from the underlying
Distribution's CDF. Equation propositions (``==`` / ``!=``) route to
``metadata['equation']`` and follow a separate (deferred-to-PR2) lowering.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from gaia.lang import LogNormal, Normal, claim
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.knowledge import _current_package
from gaia.lang.runtime.package import CollectedPackage


def _compile_with(make: Callable[[], Any]) -> dict[str, Any]:
    pkg = CollectedPackage(name="predicate_test_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        make()
    finally:
        _current_package.reset(token)
    artifact = compile_package_artifact(pkg)
    return {k.label: k for k in artifact.graph.knowledges if k.label}


def test_predicate_claim_stores_boolexpr_in_metadata():
    """Before compile, the BoolExpr lives on Lang Claim metadata."""
    from gaia.lang.dsl.bool_expr import BoolExpr

    T_c = Normal("T_c", mu=200, sigma=50)
    high_Tc = claim("high Tc", T_c > 77)
    assert isinstance(high_Tc.metadata["predicate"], BoolExpr)
    # No prior set yet — lowering happens at compile.
    assert high_Tc.prior is None


def test_predicate_claim_inequality_lowers_to_cdf_prior():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("high Tc", T_c > 77)
        c.label = "high_Tc"

    knowledges = _compile_with(make)
    # P(T_c > 77) for Normal(200, 50) ≈ 0.993
    assert math.isclose(knowledges["high_Tc"].metadata["prior"], 0.9931, abs_tol=1e-3)


def test_predicate_claim_less_than_lowers_to_cdf_prior():
    def make() -> None:
        T = Normal("T", mu=10, sigma=2)
        c = claim("low T", T < 8)
        c.label = "low_T"

    knowledges = _compile_with(make)
    # P(T < 8) for Normal(10, 2) ≈ 0.159
    assert math.isclose(knowledges["low_T"].metadata["prior"], 0.1587, abs_tol=1e-3)


def test_predicate_claim_lognormal_cdf():
    def make() -> None:
        k = LogNormal("k", mu=math.log(1e-3), sigma=2.0)
        fast = claim("fast reaction", k > 1e-2)
        fast.label = "fast"

    knowledges = _compile_with(make)
    # Roughly 12.5% probability that LogNormal(log(1e-3), 2) > 1e-2
    prior = knowledges["fast"].metadata["prior"]
    assert 0.05 < prior < 0.25


def test_predicate_claim_explicit_prior_overrides_cdf():
    """If author sets prior= alongside a predicate, author wins.

    The CDF-derived value is stashed in audit metadata for review.
    """

    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("high Tc explicit", T_c > 77, prior=0.5)
        c.label = "high_Tc_explicit"

    knowledges = _compile_with(make)
    assert knowledges["high_Tc_explicit"].metadata["prior"] == 0.5
    # CDF-derived value still computed and recorded for audit
    audit = knowledges["high_Tc_explicit"].metadata.get("predicate_audit", {})
    assert "cdf_derived_prior" in audit


def test_predicate_metadata_serializes_to_ir_dict():
    """The IR dict contains the structured BoolExpr (op + lhs + rhs).

    Useful for `gaia check --hole` rendering and for post-hoc audit.
    """
    import json

    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("high Tc", T_c > 77)
        c.label = "high_Tc"

    knowledges = _compile_with(make)
    pred = knowledges["high_Tc"].metadata["predicate"]
    assert pred["kind"] == "bool_expr"
    assert pred["op"] == ">"
    assert pred["lhs"]["kind"] == "distribution"
    assert pred["lhs"]["distribution_kind"] == "normal"
    assert pred["rhs"] == 77
    # Round-trips through JSON
    json.dumps(knowledges["high_Tc"].model_dump(mode="json"))


def test_claim_rejects_non_boolexpr_proposition():
    with pytest.raises(TypeError, match="must be a BoolExpr"):
        claim("bad", "not a BoolExpr")  # type: ignore[arg-type]


def test_claim_rejects_proposition_alongside_explicit_predicate_metadata():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(TypeError, match="pick one"):
        claim("conflict", T_c > 77, predicate={"manual": "metadata"})


def test_claim_tolerance_requires_proposition():
    with pytest.raises(TypeError, match="requires a proposition"):
        claim("prose only", tolerance=0.5)


def test_claim_tolerance_rejects_inequality_predicate():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(TypeError, match="only applies to equation"):
        claim("bad", T_c > 77, tolerance=0.5)


def test_claim_tolerance_rejects_non_positive():
    A = Normal("A", mu=10, sigma=1)
    B = Normal("B", mu=10, sigma=1)
    with pytest.raises(ValueError, match="positive number"):
        claim("eq", A == B, tolerance=-0.1)


def test_predicate_lhs_must_be_distribution():
    """RHS-only predicates (constant > Distribution) are not currently supported.

    A Distribution operand on the LHS is required for CDF lookup.
    """
    T_c = Normal("T_c", mu=200, sigma=50)
    bad = claim("bad", T_c > 77)
    # The operator overload returns BoolExpr regardless; CDF query at compile
    # time validates LHS shape.
    pkg = CollectedPackage(name="lhs_check_pkg", namespace="t")
    bad._package = pkg
    pkg.knowledge.append(bad)
    # When the LHS isn't a Distribution, lowering raises TypeError.
    # In this particular case, `77 < T_c` is rewritten to T_c > 77 by Python's
    # reflected protocol, so it ACTUALLY works. The negative case below uses
    # a literal LHS via the BoolExpr constructor directly.
    from gaia.lang.dsl.bool_expr import BoolExpr

    fake = claim("fake", BoolExpr(">", 1, 2))
    pkg2 = CollectedPackage(name="lhs_fail_pkg", namespace="t")
    fake._package = pkg2
    pkg2.knowledge.append(fake)
    from gaia.lang.compiler.predicate_lowering import lower_predicate_priors

    with pytest.raises(TypeError, match="left-hand side must be a Distribution"):
        lower_predicate_priors(pkg2)


def test_equation_claim_routes_to_equation_metadata():
    A = Normal("A", mu=10, sigma=1)
    B = Normal("B", mu=10, sigma=1)
    eq = claim("A equals B", A == B, tolerance=0.5)
    assert "equation" in eq.metadata
    assert "predicate" not in eq.metadata
    assert eq.metadata["equation_tolerance"] == 0.5


def test_equation_claim_default_prior_when_not_set():
    """Equations carry an author-belief prior.

    PR1 defaults it to 0.5 when the author does not set one, since the
    equation's truth claim is not derivable from the underlying distributions.
    """

    def make() -> None:
        A = Normal("A", mu=10, sigma=1)
        B = Normal("B", mu=10, sigma=1)
        eq = claim("A equals B", A == B)
        eq.label = "eq"

    knowledges = _compile_with(make)
    # PR1 default for equations is 0.5 (neutral until author sets explicit prior).
    assert knowledges["eq"].metadata["prior"] == 0.5


def test_equation_claim_explicit_prior_kept():
    def make() -> None:
        A = Normal("A", mu=10, sigma=1)
        B = Normal("B", mu=10, sigma=1)
        eq = claim("A equals B", A == B, prior=0.85)
        eq.label = "eq"

    knowledges = _compile_with(make)
    assert knowledges["eq"].metadata["prior"] == 0.85
