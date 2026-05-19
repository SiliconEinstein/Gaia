"""Quantity-aware Distribution / predicate / observe tests.

Distribution factories accept either bare numeric scalars or
:class:`gaia.unit.Quantity` values; predicate thresholds and observation
``value=`` / ``error=`` follow the same rule with dimensional consistency
checks against the target distribution's unit.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from gaia.engine.lang import (
    Beta,
    Cauchy,
    ChiSquared,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Poisson,
    Real,
    StudentT,
    Variable,
    claim,
    observe,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.unit import q


def _compile_with(make: Callable[[], Any]) -> dict[str, Any]:
    pkg = CollectedPackage(name="quantity_test_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        make()
    finally:
        _current_package.reset(token)
    artifact = compile_package_artifact(pkg)
    return {k.label: k for k in artifact.graph.knowledges if k.label}


# --------------------------------------------------------------------------- #
# Factory unit handling                                                       #
# --------------------------------------------------------------------------- #


def test_normal_accepts_quantity_params_and_records_unit():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    assert T_c.metadata == {
        "units": {"mu": "kelvin", "sigma": "kelvin"},
        "unit": "kelvin",
    }
    # The pydantic _impl receives raw magnitudes
    assert T_c.params == {"mu": 200.0, "sigma": 50.0}


def test_normal_unitless_keeps_metadata_empty():
    n = Normal("plain", mu=0, sigma=1)
    assert n.metadata is None or "unit" not in (n.metadata or {})


def test_normal_rejects_unit_mismatch():
    with pytest.raises(ValueError, match="must share a single unit"):
        Normal("mixed", mu=q(200, "K"), sigma=q(50, "celsius"))


def test_normal_rejects_half_typed_params():
    with pytest.raises(ValueError, match="disagree on unit-aware-ness"):
        Normal("half", mu=q(200, "K"), sigma=50)


def test_studentt_accepts_quantity_for_location_scale():
    t = StudentT("t", df=5, mu=q(0, "K"), sigma=q(1, "K"))
    assert t.metadata["unit"] == "kelvin"
    assert t.metadata["units"] == {"mu": "kelvin", "sigma": "kelvin"}


def test_studentt_rejects_quantity_on_df():
    with pytest.raises(ValueError, match="dimensionless"):
        StudentT("t", df=q(5, "dimensionless"), mu=0, sigma=1)


def test_cauchy_accepts_quantity_for_location_scale():
    c = Cauchy("c", mu=q(0, "m"), gamma=q(1, "m"))
    assert c.metadata["unit"] == "meter"


def test_exponential_records_rate_unit():
    e = Exponential("decay", rate=q(2, "1/s"))
    assert e.metadata == {
        "units": {"rate": "1 / second"},
        "unit": "second",
    }


def test_gamma_alpha_dimensionless_rate_unit():
    g = Gamma("g", alpha=2, rate=q(1, "1/s"))
    assert g.metadata == {
        "units": {"rate": "1 / second"},
        "unit": "second",
    }


def test_gamma_rejects_quantity_on_alpha():
    with pytest.raises(ValueError, match="dimensionless"):
        Gamma("bad", alpha=q(2, "K"), rate=1)


def test_poisson_records_rate_unit():
    with pytest.raises(ValueError, match="dimensionless"):
        Poisson("counts", rate=q(3, "count / second"))


def test_lognormal_rejects_quantity_on_log_space_params():
    with pytest.raises(ValueError, match="dimensionless"):
        LogNormal("ln", mu=q(0, "K"), sigma=1)


def test_beta_rejects_quantity():
    with pytest.raises(ValueError, match="dimensionless"):
        Beta("b", alpha=q(2, "K"), beta=2)


def test_chisquared_rejects_quantity():
    with pytest.raises(ValueError, match="dimensionless"):
        ChiSquared("c", df=q(5, "K"))


# --------------------------------------------------------------------------- #
# Predicate threshold unit handling                                           #
# --------------------------------------------------------------------------- #


def test_predicate_with_quantity_threshold_lowers_to_cdf_prior():
    def make() -> None:
        T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
        c = claim("high T_c", T_c > q(77, "K"))
        c.label = "high_Tc"

    knowledges = _compile_with(make)
    assert math.isclose(knowledges["high_Tc"].metadata["prior"], 0.9931, abs_tol=1e-3)


def test_predicate_threshold_auto_converts_compatible_unit():
    """26.85 C = 300 K, so P(Normal(200, 50) > 26.85 C) = P(>300 K) ~ 0.023."""

    def make() -> None:
        T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
        c = claim("over 300 K", T_c > q(26.85, "celsius"))
        c.label = "over_300"

    knowledges = _compile_with(make)
    assert math.isclose(knowledges["over_300"].metadata["prior"], 0.0228, abs_tol=1e-3)


def test_predicate_rejects_bare_scalar_against_unit_typed_dist():
    def make() -> None:
        T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
        c = claim("bad", T_c > 77)
        c.label = "bad"

    with pytest.raises(TypeError, match="must be a Quantity in 'kelvin'"):
        _compile_with(make)


def test_predicate_rejects_quantity_against_unitless_dist():
    def make() -> None:
        T_c = Normal("T_c", mu=200, sigma=50)
        c = claim("bad", T_c > q(77, "K"))
        c.label = "bad"

    with pytest.raises(TypeError, match=r"LHS distribution.*unitless"):
        _compile_with(make)


def test_predicate_rejects_dimensionally_incompatible_threshold():
    def make() -> None:
        T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
        c = claim("bad", T_c > q(77, "meter"))
        c.label = "bad"

    with pytest.raises(ValueError, match="not compatible with"):
        _compile_with(make)


def test_predicate_quantity_threshold_serialises_to_ir():
    def make() -> None:
        T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
        c = claim("high T_c", T_c > q(77, "K"))
        c.label = "high_Tc"

    knowledges = _compile_with(make)
    rhs = knowledges["high_Tc"].metadata["predicate"]["rhs"]
    assert rhs == {"kind": "quantity", "value": 77.0, "unit": "kelvin"}


def test_exponential_rate_unit_uses_random_variable_unit_for_predicates():
    def make() -> None:
        lifetime = Exponential("lifetime", rate=q(2, "1/s"))
        c = claim("lifetime exceeds one second", lifetime > q(1, "s"))
        c.label = "long_lived"

    knowledges = _compile_with(make)
    assert math.isclose(knowledges["long_lived"].metadata["prior"], math.exp(-2), abs_tol=1e-3)


def test_gamma_rate_unit_uses_random_variable_unit_for_observations():
    lifetime = Gamma("lifetime", alpha=2, rate=q(1, "1/s"))
    obs = observe(lifetime, value=q(2, "s"), error=q(0.1, "s"))
    payload = obs.metadata["observation"]
    assert payload["value"] == 2.0
    # Scalar ``error=q(0.1, "s")`` is sugared into an anonymous
    # Normal(mu=0 s, sigma=0.1 s) noise Distribution under the unified
    # observe() schema.
    noise = payload["noise"]
    assert noise.kind == "normal"
    assert payload["unit"] == "second"


def test_observe_unit_typed_variable_converts_quantity_value_and_error() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    obs = observe(temperature, value=q(26.85, "celsius"), error=q(5, "K"))
    payload = obs.metadata["observation"]
    assert math.isclose(payload["value"], 300.0, abs_tol=1e-6)
    assert payload["unit"] == "kelvin"
    noise = payload["noise"]
    assert noise.kind == "normal"
    assert noise.metadata["unit"] == "kelvin"
    assert noise.params["sigma"] == 5.0


def test_observe_unit_typed_variable_rejects_bare_scalar_value() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    with pytest.raises(TypeError, match=r"must be a gaia\.unit\.Quantity in 'kelvin'"):
        observe(temperature, value=203)


def test_observe_unitless_variable_rejects_quantity_value() -> None:
    temperature = Variable(symbol="T", domain=Real)
    with pytest.raises(TypeError, match="unitless"):
        observe(temperature, value=q(203, "K"))


def test_observe_unit_typed_variable_rejects_incompatible_error_distribution() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    noise = Normal("length noise", mu=q(0, "m"), sigma=q(1, "m"))
    with pytest.raises(ValueError, match="noise distribution unit"):
        observe(temperature, value=q(203, "K"), error=noise)


def test_observe_unitless_variable_rejects_unit_typed_error_distribution() -> None:
    temperature = Variable(symbol="T", domain=Real)
    noise = Normal("temperature noise", mu=q(0, "K"), sigma=q(1, "K"))
    with pytest.raises(TypeError, match="unit-typed noise distribution"):
        observe(temperature, value=203, error=noise)


# --------------------------------------------------------------------------- #
# observe() with Quantity                                                     #
# --------------------------------------------------------------------------- #


def test_observe_with_quantity_value_and_error():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    obs = observe(T_c, value=q(203, "K"), error=q(5, "K"))
    payload = obs.metadata["observation"]
    assert payload["value"] == 203.0
    noise = payload["noise"]
    assert noise.kind == "normal"
    assert payload["unit"] == "kelvin"
    assert "kelvin" in obs.content


def test_observe_auto_converts_compatible_unit():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    # 26.85 C ≡ 300 K
    obs = observe(T_c, value=q(26.85, "celsius"), error=q(5, "K"))
    payload = obs.metadata["observation"]
    assert math.isclose(payload["value"], 300.0, abs_tol=1e-6)
    assert payload["unit"] == "kelvin"


def test_observe_rejects_bare_scalar_against_unit_typed_dist():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    with pytest.raises(TypeError, match="must be a Quantity in 'kelvin'"):
        observe(T_c, value=203, error=q(5, "K"))


def test_observe_rejects_quantity_against_unitless_dist():
    T_c = Normal("T_c", mu=200, sigma=50)
    with pytest.raises(TypeError, match=r"target distribution.*is unitless"):
        observe(T_c, value=q(203, "K"))


def test_observe_rejects_dimensionally_incompatible_value():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    with pytest.raises(ValueError, match="not compatible with"):
        observe(T_c, value=q(203, "meter"))


def test_observe_rejects_dimensionally_incompatible_error():
    T_c = Normal("T_c", mu=q(200, "K"), sigma=q(50, "K"))
    with pytest.raises(ValueError, match="not compatible with"):
        observe(T_c, value=q(203, "K"), error=q(5, "meter"))


def test_observe_unitless_path_unchanged():
    """Existing scalar observe API still works on unitless distributions."""
    T_c = Normal("T_c", mu=200, sigma=50)
    obs = observe(T_c, value=203, error=5)
    payload = obs.metadata["observation"]
    assert payload["value"] == 203.0
    noise = payload["noise"]
    assert noise.kind == "normal"
    assert noise.params["sigma"] == 5.0
    assert payload["unit"] is None
