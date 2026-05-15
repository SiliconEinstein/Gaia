"""Continuous Bayes distribution literals."""

from __future__ import annotations

import math
from typing import Any

from pydantic import model_validator

from gaia.engine.lang.bayes.adapters.scipy_backend import _to_scipy_dist
from gaia.engine.lang.bayes.distributions.base import _BaseDistribution, _is_concrete_number


class _ContinuousDistribution(_BaseDistribution):
    _support: tuple[float, float] = (-math.inf, math.inf)

    def logpdf(self, x: float) -> float:
        return float(_to_scipy_dist(self.kind, self._resolved_params()).logpdf(float(x)))

    def logpmf(self, k: int) -> float:
        del k
        raise TypeError(f"{self.__class__.__name__} is a continuous distribution; use .logpdf()")

    def support(self) -> tuple[float, float]:
        return self._support


class Normal(_ContinuousDistribution):
    """Normal distribution literal with mean and standard deviation."""

    kind: str = "normal"
    _support = (-math.inf, math.inf)

    def __init__(self, *, mu: Any, sigma: Any) -> None:
        """Create a Normal distribution literal."""
        super().__init__(kind="normal", params={"mu": mu, "sigma": sigma})

    @model_validator(mode="after")
    def _validate_normal(self) -> Normal:
        sigma = self.params["sigma"]
        if _is_concrete_number(sigma) and float(sigma) <= 0.0:
            raise ValueError(f"Normal sigma must be > 0, got {sigma!r}")
        return self


class Beta(_ContinuousDistribution):
    """Beta distribution literal over the unit interval."""

    kind: str = "beta"
    _support = (0.0, 1.0)

    def __init__(self, *, alpha: Any, beta: Any) -> None:
        """Create a Beta distribution literal."""
        super().__init__(kind="beta", params={"alpha": alpha, "beta": beta})

    @model_validator(mode="after")
    def _validate_beta(self) -> Beta:
        for name in ("alpha", "beta"):
            value = self.params[name]
            if _is_concrete_number(value) and float(value) <= 0.0:
                raise ValueError(f"Beta {name} must be > 0, got {value!r}")
        return self


class Exponential(_ContinuousDistribution):
    """Exponential distribution literal parameterized by rate."""

    kind: str = "exponential"
    _support = (0.0, math.inf)

    def __init__(self, *, rate: Any) -> None:
        """Create an Exponential distribution literal."""
        super().__init__(kind="exponential", params={"rate": rate})

    @model_validator(mode="after")
    def _validate_exponential(self) -> Exponential:
        rate = self.params["rate"]
        if _is_concrete_number(rate) and float(rate) <= 0.0:
            raise ValueError(f"Exponential rate must be > 0, got {rate!r}")
        return self


class LogNormal(_ContinuousDistribution):
    """Log-normal distribution literal with log-space mean and scale."""

    kind: str = "lognormal"
    _support = (0.0, math.inf)

    def __init__(self, *, mu: Any, sigma: Any) -> None:
        """Create a LogNormal distribution literal."""
        super().__init__(kind="lognormal", params={"mu": mu, "sigma": sigma})

    @model_validator(mode="after")
    def _validate_lognormal(self) -> LogNormal:
        sigma = self.params["sigma"]
        if _is_concrete_number(sigma) and float(sigma) <= 0.0:
            raise ValueError(f"LogNormal sigma must be > 0, got {sigma!r}")
        return self


class StudentT(_ContinuousDistribution):
    """Student's t distribution literal with location and scale."""

    kind: str = "studentt"
    _support = (-math.inf, math.inf)

    def __init__(self, *, df: Any, mu: Any = 0.0, sigma: Any = 1.0) -> None:
        """Create a StudentT distribution literal."""
        super().__init__(kind="studentt", params={"df": df, "mu": mu, "sigma": sigma})

    @model_validator(mode="after")
    def _validate_studentt(self) -> StudentT:
        for name in ("df", "sigma"):
            value = self.params[name]
            if _is_concrete_number(value) and float(value) <= 0.0:
                raise ValueError(f"StudentT {name} must be > 0, got {value!r}")
        return self


class Cauchy(_ContinuousDistribution):
    """Cauchy distribution literal with location and scale."""

    kind: str = "cauchy"
    _support = (-math.inf, math.inf)

    def __init__(self, *, mu: Any, gamma: Any) -> None:
        """Create a Cauchy distribution literal."""
        super().__init__(kind="cauchy", params={"mu": mu, "gamma": gamma})

    @model_validator(mode="after")
    def _validate_cauchy(self) -> Cauchy:
        gamma = self.params["gamma"]
        if _is_concrete_number(gamma) and float(gamma) <= 0.0:
            raise ValueError(f"Cauchy gamma must be > 0, got {gamma!r}")
        return self


class Gamma(_ContinuousDistribution):
    """Gamma distribution literal parameterized by shape and rate."""

    kind: str = "gamma"
    _support = (0.0, math.inf)

    def __init__(self, *, alpha: Any, rate: Any) -> None:
        """Create a Gamma distribution literal."""
        super().__init__(kind="gamma", params={"alpha": alpha, "rate": rate})

    @model_validator(mode="after")
    def _validate_gamma(self) -> Gamma:
        for name in ("alpha", "rate"):
            value = self.params[name]
            if _is_concrete_number(value) and float(value) <= 0.0:
                raise ValueError(f"Gamma {name} must be > 0, got {value!r}")
        return self


class ChiSquared(_ContinuousDistribution):
    """Chi-squared distribution literal parameterized by degrees of freedom."""

    kind: str = "chisquared"
    _support = (0.0, math.inf)

    def __init__(self, *, df: Any) -> None:
        """Create a ChiSquared distribution literal."""
        super().__init__(kind="chisquared", params={"df": df})

    @model_validator(mode="after")
    def _validate_chisquared(self) -> ChiSquared:
        df = self.params["df"]
        if _is_concrete_number(df) and float(df) <= 0.0:
            raise ValueError(f"ChiSquared df must be > 0, got {df!r}")
        return self
