"""Internal scipy-backed distribution implementations.

This module is **internal** to the Gaia engine. Authors should import
distribution factories from :mod:`gaia.engine.lang` (which wraps these
pydantic ``_BaseDistribution`` subclasses in :class:`Distribution`
Knowledge nodes for identity, provenance, and metadata).

The internal contents are still re-exported here so that the Knowledge
factories in :mod:`gaia.engine.lang.runtime.distribution` can locate
their implementation backend without a deep relative import path. New
code that needs a distribution should reach for
:func:`gaia.engine.lang.Normal` / :func:`Binomial` / ... etc., not for
the unwrapped pydantic class here.
"""

from __future__ import annotations

from gaia.engine.bayes.distributions.continuous import (
    Beta,
    Cauchy,
    ChiSquared,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    StudentT,
)
from gaia.engine.bayes.distributions.discrete import BetaBinomial, Binomial, Poisson
from gaia.engine.bayes.distributions.protocol import (
    DistParam,
    Distribution,
    UnresolvedParameterError,
)

__all__ = [
    "Beta",
    "BetaBinomial",
    "Binomial",
    "Cauchy",
    "ChiSquared",
    "DistParam",
    "Distribution",
    "Exponential",
    "Gamma",
    "LogNormal",
    "Normal",
    "Poisson",
    "StudentT",
    "UnresolvedParameterError",
]
