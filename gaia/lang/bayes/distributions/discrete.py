"""Discrete Bayes distribution literals."""

from __future__ import annotations

import math
from typing import Any

from pydantic import model_validator

from gaia.lang.bayes.adapters.scipy_backend import _to_scipy_dist
from gaia.lang.bayes.distributions.base import _BaseDistribution, _is_concrete_number


class Binomial(_BaseDistribution):
    """Binomial distribution literal for integer success counts."""

    kind: str = "binomial"

    def __init__(self, *, n: Any, p: Any) -> None:
        """Create a Binomial distribution literal."""
        super().__init__(kind="binomial", params={"n": n, "p": p})

    @model_validator(mode="after")
    def _validate_binomial(self) -> Binomial:
        n = self.params["n"]
        p = self.params["p"]
        if _is_concrete_number(n):
            if isinstance(n, float) and not n.is_integer():
                raise ValueError(f"Binomial n must be an integer, got {n!r}")
            if int(n) < 0:
                raise ValueError(f"Binomial n must be >= 0, got {n!r}")
        if _is_concrete_number(p) and not 0.0 <= float(p) <= 1.0:
            raise ValueError(f"Binomial p must be in [0, 1], got {p!r}")
        return self

    def logpmf(self, k: int) -> float:
        """Evaluate the log probability mass at integer count ``k``."""
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"Binomial.logpmf(k): k must be integer, got {type(k).__name__}")
        resolved = self._resolved_params()
        n = int(resolved["n"])
        if k < 0 or k > n:
            return -math.inf
        return float(_to_scipy_dist(self.kind, resolved).logpmf(k))

    def logpdf(self, x: float) -> float:
        """Reject density evaluation for the discrete Binomial distribution."""
        del x
        raise TypeError("Binomial is a discrete distribution; use .logpmf()")

    def support(self) -> tuple[int, int]:
        """Return the inclusive integer support bounds."""
        resolved = self._resolved_params()
        return (0, int(resolved["n"]))


class BetaBinomial(_BaseDistribution):
    """Beta-binomial distribution literal for integer success counts.

    Predictive distribution obtained by integrating ``Binomial(n, p)`` over
    ``p ~ Beta(alpha, beta)``. Useful as a model-comparison reference when
    the success probability has a Beta prior rather than a fixed value.

    The special case ``BetaBinomial(n, alpha=1, beta=1)`` corresponds to
    ``p ~ Uniform[0, 1]`` and gives the closed-form uniform marginal
    ``P(k) = 1 / (n + 1)`` for every ``k ∈ [0, n]``.
    """

    kind: str = "betabinomial"

    def __init__(self, *, n: Any, alpha: Any, beta: Any) -> None:
        """Create a BetaBinomial distribution literal."""
        super().__init__(kind="betabinomial", params={"n": n, "alpha": alpha, "beta": beta})

    @model_validator(mode="after")
    def _validate_betabinomial(self) -> BetaBinomial:
        n = self.params["n"]
        if _is_concrete_number(n):
            if isinstance(n, float) and not n.is_integer():
                raise ValueError(f"BetaBinomial n must be an integer, got {n!r}")
            if int(n) < 0:
                raise ValueError(f"BetaBinomial n must be >= 0, got {n!r}")
        for name in ("alpha", "beta"):
            value = self.params[name]
            if _is_concrete_number(value) and float(value) <= 0.0:
                raise ValueError(f"BetaBinomial {name} must be > 0, got {value!r}")
        return self

    def logpmf(self, k: int) -> float:
        """Evaluate the log probability mass at integer count ``k``."""
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"BetaBinomial.logpmf(k): k must be integer, got {type(k).__name__}")
        resolved = self._resolved_params()
        n = int(resolved["n"])
        if k < 0 or k > n:
            return -math.inf
        return float(_to_scipy_dist(self.kind, resolved).logpmf(k))

    def logpdf(self, x: float) -> float:
        """Reject density evaluation for the discrete BetaBinomial distribution."""
        del x
        raise TypeError("BetaBinomial is a discrete distribution; use .logpmf()")

    def support(self) -> tuple[int, int]:
        """Return the inclusive integer support bounds."""
        resolved = self._resolved_params()
        return (0, int(resolved["n"]))


class Poisson(_BaseDistribution):
    """Poisson distribution literal for non-negative integer counts."""

    kind: str = "poisson"

    def __init__(self, *, rate: Any) -> None:
        """Create a Poisson distribution literal."""
        super().__init__(kind="poisson", params={"rate": rate})

    @model_validator(mode="after")
    def _validate_poisson(self) -> Poisson:
        rate = self.params["rate"]
        if _is_concrete_number(rate) and float(rate) <= 0.0:
            raise ValueError(f"Poisson rate must be > 0, got {rate!r}")
        return self

    def logpmf(self, k: int) -> float:
        """Evaluate the log probability mass at integer count ``k``."""
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"Poisson.logpmf(k): k must be integer, got {type(k).__name__}")
        if k < 0:
            return -math.inf
        return float(_to_scipy_dist(self.kind, self._resolved_params()).logpmf(k))

    def logpdf(self, x: float) -> float:
        """Reject density evaluation for the discrete Poisson distribution."""
        del x
        raise TypeError("Poisson is a discrete distribution; use .logpmf()")

    def support(self) -> tuple[int, float]:
        """Return the support bounds for non-negative counts."""
        self._resolved_params()
        return (0, math.inf)
