"""Internal scipy.stats backend for Bayes distribution literals."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import scipy.stats as stats

_BUILDERS: dict[str, Callable[[dict[str, float]], Any]] = {
    "beta": lambda p: stats.beta(a=p["alpha"], b=p["beta"]),
    "binomial": lambda p: stats.binom(n=int(p["n"]), p=p["p"]),
    "cauchy": lambda p: stats.cauchy(loc=p["mu"], scale=p["gamma"]),
    "chisquared": lambda p: stats.chi2(df=p["df"]),
    "exponential": lambda p: stats.expon(scale=1.0 / p["rate"]),
    "gamma": lambda p: stats.gamma(a=p["alpha"], scale=1.0 / p["rate"]),
    "lognormal": lambda p: stats.lognorm(s=p["sigma"], scale=math.exp(p["mu"])),
    "normal": lambda p: stats.norm(loc=p["mu"], scale=p["sigma"]),
    "poisson": lambda p: stats.poisson(mu=p["rate"]),
    "studentt": lambda p: stats.t(df=p["df"], loc=p["mu"], scale=p["sigma"]),
}


def _to_scipy_dist(kind: str, resolved_params: dict[str, float]) -> Any:
    return _BUILDERS[kind](resolved_params)
