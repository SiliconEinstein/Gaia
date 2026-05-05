"""Bayes distribution literals."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest
import scipy.stats as stats


@dataclass(frozen=True)
class Deferred:
    symbol: str
    domain: str = "Probability"
    label: str | None = "theta_var"


def test_public_distribution_surface_imports_from_gaia_lang_namespace():
    from gaia.lang import bayes
    from gaia.lang import Binomial, Normal

    required = {
        "Beta",
        "Binomial",
        "Cauchy",
        "ChiSquared",
        "Exponential",
        "Gamma",
        "LogNormal",
        "Normal",
        "Poisson",
        "StudentT",
    }
    assert required.issubset(set(bayes.__all__))
    assert Binomial is bayes.Binomial
    assert Normal is bayes.Normal
    assert bayes.Binomial(n=10, p=0.5).logpmf(5) == pytest.approx(stats.binom.logpmf(5, 10, 0.5))
    assert bayes.Normal(mu=0.0, sigma=1.0).logpdf(0.0) == pytest.approx(stats.norm.logpdf(0.0))


@pytest.mark.parametrize(
    ("dist", "kind", "method", "x", "expected"),
    [
        (
            lambda bayes: bayes.Binomial(n=395, p=0.75),
            "binomial",
            "logpmf",
            295,
            stats.binom.logpmf(295, 395, 0.75),
        ),
        (
            lambda bayes: bayes.Poisson(rate=3.0),
            "poisson",
            "logpmf",
            4,
            stats.poisson.logpmf(4, 3.0),
        ),
        (
            lambda bayes: bayes.Normal(mu=1.0, sigma=2.0),
            "normal",
            "logpdf",
            1.5,
            stats.norm.logpdf(1.5, loc=1.0, scale=2.0),
        ),
        (
            lambda bayes: bayes.Beta(alpha=2.0, beta=5.0),
            "beta",
            "logpdf",
            0.4,
            stats.beta.logpdf(0.4, a=2.0, b=5.0),
        ),
        (
            lambda bayes: bayes.Exponential(rate=2.0),
            "exponential",
            "logpdf",
            0.4,
            stats.expon.logpdf(0.4, scale=0.5),
        ),
        (
            lambda bayes: bayes.LogNormal(mu=0.1, sigma=0.7),
            "lognormal",
            "logpdf",
            1.2,
            stats.lognorm.logpdf(1.2, s=0.7, scale=math.exp(0.1)),
        ),
        (
            lambda bayes: bayes.StudentT(df=5.0, mu=1.0, sigma=2.0),
            "studentt",
            "logpdf",
            0.2,
            stats.t.logpdf(0.2, df=5.0, loc=1.0, scale=2.0),
        ),
        (
            lambda bayes: bayes.Cauchy(mu=1.0, gamma=2.0),
            "cauchy",
            "logpdf",
            0.2,
            stats.cauchy.logpdf(0.2, loc=1.0, scale=2.0),
        ),
        (
            lambda bayes: bayes.Gamma(alpha=2.0, rate=3.0),
            "gamma",
            "logpdf",
            0.7,
            stats.gamma.logpdf(0.7, a=2.0, scale=1 / 3.0),
        ),
        (
            lambda bayes: bayes.ChiSquared(df=4.0),
            "chisquared",
            "logpdf",
            2.0,
            stats.chi2.logpdf(2.0, df=4.0),
        ),
    ],
)
def test_distribution_values_match_scipy(dist, kind, method, x, expected):
    from gaia.lang import bayes

    d = dist(bayes)
    assert d.kind == kind
    assert getattr(d, method)(x) == pytest.approx(expected, rel=1e-12, abs=1e-15)


def test_deferred_distribution_params_are_audit_descriptors_not_binding_keys():
    from gaia.lang import bayes
    from gaia.lang.bayes import UnresolvedParameterError

    theta = Deferred("theta")
    d = bayes.Binomial(n=10, p=theta)

    assert d.model_dump() == {
        "kind": "binomial",
        "params": {"n": 10},
        "deferred_params": {
            "p": {"symbol": "theta", "domain": "Probability", "label": "theta_var"}
        },
    }
    with pytest.raises(UnresolvedParameterError) as excinfo:
        d.logpmf(5)
    assert excinfo.value.deferred_params == ["p"]


def test_distribution_validation_rejects_invalid_parameters():
    from gaia.lang import bayes

    with pytest.raises(ValueError, match="Binomial.*p.*\\[0, 1\\]"):
        bayes.Binomial(n=10, p=1.1)
    with pytest.raises(ValueError, match="Normal.*sigma.*> 0"):
        bayes.Normal(mu=0.0, sigma=0.0)
    with pytest.raises(TypeError, match="discrete"):
        bayes.Binomial(n=10, p=0.5).logpdf(5)
    with pytest.raises(TypeError, match="continuous"):
        bayes.Normal(mu=0.0, sigma=1.0).logpmf(0)
