"""Internal scipy-backed distribution literals at ``gaia.engine.bayes.distributions``.

These tests cover the pydantic ``_BaseDistribution`` subclasses that act as
the computational backend for the user-facing :class:`Distribution`
Knowledge factories in :mod:`gaia.engine.lang`. The subpackage is
internal — authors should import distribution factories from
``gaia.engine.lang`` — but the implementations still need to match
``scipy.stats`` numerically and validate parameters at construction time.
"""

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


def test_distribution_factories_not_exported_on_top_level_bayes_namespace():
    """The clean-break design removes typed-value re-exports from ``gaia.engine.bayes``.

    Distribution factories live exclusively in :mod:`gaia.engine.lang`
    (which wraps each pydantic backend in a Knowledge node). The bare
    pydantic classes are reachable through the internal
    :mod:`gaia.engine.bayes.distributions` module for backend testing
    only.
    """
    import gaia.engine.bayes as bayes

    for removed in ("Normal", "Binomial", "BetaBinomial", "Beta", "Poisson"):
        assert not hasattr(bayes, removed), (
            f"gaia.engine.bayes.{removed} should be removed (use gaia.engine.lang.{removed})"
        )
        assert removed not in bayes.__all__


def test_internal_distribution_backends_still_importable():
    """The internal pydantic backends remain at ``gaia.engine.bayes.distributions``."""
    from gaia.engine.bayes.distributions import (
        Beta,
        BetaBinomial,
        Binomial,
        Cauchy,
        ChiSquared,
        Exponential,
        Gamma,
        LogNormal,
        Normal,
        Poisson,
        StudentT,
    )

    assert Binomial(n=10, p=0.5).logpmf(5) == pytest.approx(stats.binom.logpmf(5, 10, 0.5))
    assert BetaBinomial(n=10, alpha=1, beta=1).logpmf(5) == pytest.approx(
        stats.betabinom.logpmf(5, n=10, a=1, b=1)
    )
    assert Normal(mu=0.0, sigma=1.0).logpdf(0.0) == pytest.approx(stats.norm.logpdf(0.0))
    # Just exercise constructors for the other families so import wiring is covered.
    Beta(alpha=1.0, beta=1.0)
    Cauchy(mu=0.0, gamma=1.0)
    ChiSquared(df=1.0)
    Exponential(rate=1.0)
    Gamma(alpha=1.0, rate=1.0)
    LogNormal(mu=0.0, sigma=1.0)
    Poisson(rate=1.0)
    StudentT(df=2.0, mu=0.0, sigma=1.0)


@pytest.mark.parametrize(
    ("dist", "kind", "method", "x", "expected"),
    [
        (
            lambda d: d.Binomial(n=395, p=0.75),
            "binomial",
            "logpmf",
            295,
            stats.binom.logpmf(295, 395, 0.75),
        ),
        (
            lambda d: d.BetaBinomial(n=395, alpha=1.0, beta=1.0),
            "betabinomial",
            "logpmf",
            295,
            stats.betabinom.logpmf(295, n=395, a=1.0, b=1.0),
        ),
        (
            lambda d: d.Poisson(rate=3.0),
            "poisson",
            "logpmf",
            4,
            stats.poisson.logpmf(4, 3.0),
        ),
        (
            lambda d: d.Normal(mu=1.0, sigma=2.0),
            "normal",
            "logpdf",
            1.5,
            stats.norm.logpdf(1.5, loc=1.0, scale=2.0),
        ),
        (
            lambda d: d.Beta(alpha=2.0, beta=5.0),
            "beta",
            "logpdf",
            0.4,
            stats.beta.logpdf(0.4, a=2.0, b=5.0),
        ),
        (
            lambda d: d.Exponential(rate=2.0),
            "exponential",
            "logpdf",
            0.4,
            stats.expon.logpdf(0.4, scale=0.5),
        ),
        (
            lambda d: d.LogNormal(mu=0.1, sigma=0.7),
            "lognormal",
            "logpdf",
            1.2,
            stats.lognorm.logpdf(1.2, s=0.7, scale=math.exp(0.1)),
        ),
        (
            lambda d: d.StudentT(df=5.0, mu=1.0, sigma=2.0),
            "studentt",
            "logpdf",
            0.2,
            stats.t.logpdf(0.2, df=5.0, loc=1.0, scale=2.0),
        ),
        (
            lambda d: d.Cauchy(mu=1.0, gamma=2.0),
            "cauchy",
            "logpdf",
            0.2,
            stats.cauchy.logpdf(0.2, loc=1.0, scale=2.0),
        ),
        (
            lambda d: d.Gamma(alpha=2.0, rate=3.0),
            "gamma",
            "logpdf",
            0.7,
            stats.gamma.logpdf(0.7, a=2.0, scale=1 / 3.0),
        ),
        (
            lambda d: d.ChiSquared(df=4.0),
            "chisquared",
            "logpdf",
            2.0,
            stats.chi2.logpdf(2.0, df=4.0),
        ),
    ],
)
def test_distribution_values_match_scipy(dist, kind, method, x, expected):
    import gaia.engine.bayes.distributions as d

    instance = dist(d)
    assert instance.kind == kind
    assert getattr(instance, method)(x) == pytest.approx(expected, rel=1e-12, abs=1e-15)


def test_deferred_distribution_params_are_audit_descriptors_not_binding_keys():
    import gaia.engine.bayes.distributions as d
    from gaia.engine.bayes.distributions import UnresolvedParameterError

    theta = Deferred("theta")
    binomial = d.Binomial(n=10, p=theta)

    assert binomial.model_dump() == {
        "kind": "binomial",
        "params": {"n": 10},
        "deferred_params": {
            "p": {"symbol": "theta", "domain": "Probability", "label": "theta_var"}
        },
    }
    with pytest.raises(UnresolvedParameterError) as excinfo:
        binomial.logpmf(5)
    assert excinfo.value.deferred_params == ["p"]


def test_distribution_validation_rejects_invalid_parameters():
    import gaia.engine.bayes.distributions as d

    with pytest.raises(ValueError, match=r"Binomial.*p.*\[0, 1\]"):
        d.Binomial(n=10, p=1.1)
    with pytest.raises(ValueError, match=r"BetaBinomial.*alpha.*> 0"):
        d.BetaBinomial(n=10, alpha=0.0, beta=1.0)
    with pytest.raises(ValueError, match=r"Normal.*sigma.*> 0"):
        d.Normal(mu=0.0, sigma=0.0)
    with pytest.raises(TypeError, match="discrete"):
        d.BetaBinomial(n=10, alpha=1.0, beta=1.0).logpdf(5)
    with pytest.raises(TypeError, match="discrete"):
        d.Binomial(n=10, p=0.5).logpdf(5)
    with pytest.raises(TypeError, match="continuous"):
        d.Normal(mu=0.0, sigma=1.0).logpmf(0)


def test_betabinomial_uniform_alpha_beta_equals_one_over_n_plus_one():
    """BetaBinomial(n, 1, 1) recovers the integrate-over-Uniform[0, 1] marginal 1/(n+1).

    This identity is the mathematical foundation of the Mendel example's
    diffuse alternative: the closed-form uniform marginal ``P(k) = 1/(n+1)``
    is exactly ``BetaBinomial(n, alpha=1, beta=1)`` evaluated at any
    ``k ∈ [0, n]``. Pin the invariant here so future scipy / numerical
    changes cannot silently break the example's stated derivation.
    """
    import gaia.engine.bayes.distributions as d

    for n in (10, 100, 395):
        bb = d.BetaBinomial(n=n, alpha=1.0, beta=1.0)
        expected_logpmf = -math.log(n + 1)
        for k in (0, n // 3, n // 2, n - 1, n):
            assert bb.logpmf(k) == pytest.approx(expected_logpmf), (
                f"BetaBinomial({n}, 1, 1).logpmf({k}) should equal -log({n + 1})"
            )
        assert bb.logpmf(n + 1) == -math.inf
        assert bb.logpmf(-1) == -math.inf
