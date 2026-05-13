"""A_p distribution — "probability of probability" (Jaynes PTLoS Ch. 18).

A_p is Jaynes' device for representing meta-uncertainty: instead of
committing to a single class-IV prior pi = P(A=1), we carry a
distribution over the value of pi itself.

Formally, A_p is the proposition "the long-run probability of A is p",
and f(p | I) is the density of this propositional parameter under our
information state I. The predictive probability is then

    P(A=1 | I) = integral_0^1 p * f(p | I) dp.

This module discretises theta in [0,1] into M bins and works with arrays.
That is enough for cross-checking and for feeding a class-IV prior into
the rest of jaynes_ref (use predictive_probability and write it as
unary_priors[v]).

This implementation handles only a single propositional variable; joint
A_p over multiple variables (and correlations among meta-distributions)
is not supported here — that needs continuous-variable Layer 1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "ApDistribution",
    "beta_ap",
    "credible_interval",
    "entropy_ap",
    "predictive_probability",
    "uniform_ap",
    "update_with_bernoulli",
]


@dataclass(frozen=True)
class ApDistribution:
    """Discretised meta-distribution over theta in [0, 1].

    The grid is midpoint-based: theta_grid[k] = (k + 0.5) / M, k=0..M-1.
    density[k] is the probability mass on bin k (sum to 1).
    """

    label: str
    theta_grid: np.ndarray
    density: np.ndarray

    def __post_init__(self) -> None:
        if self.theta_grid.shape != self.density.shape:
            raise ValueError("theta_grid and density must have same shape")
        if self.theta_grid.ndim != 1:
            raise ValueError("theta_grid must be 1D")
        if np.any(self.theta_grid < 0.0) or np.any(self.theta_grid > 1.0):
            raise ValueError("theta_grid values must lie in [0, 1]")
        if np.any(self.density < 0.0):
            raise ValueError("density must be non-negative")
        s = float(self.density.sum())
        if not np.isclose(s, 1.0, atol=1e-9):
            raise ValueError(f"density must sum to 1, got {s}")


def _midpoint_grid(M: int) -> np.ndarray:
    if M < 2:
        raise ValueError(f"M must be >= 2, got {M}")
    return (np.arange(M, dtype=np.float64) + 0.5) / float(M)


def uniform_ap(M: int = 101, label: str = "uniform") -> ApDistribution:
    """Indifference prior: uniform on [0, 1]."""
    grid = _midpoint_grid(M)
    density = np.full(M, 1.0 / M, dtype=np.float64)
    return ApDistribution(label=label, theta_grid=grid, density=density)


def beta_ap(a: float, b: float, M: int = 101, label: str | None = None) -> ApDistribution:
    """Discretised Beta(a, b) prior. a, b > 0."""
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"a, b must be positive, got a={a}, b={b}")
    grid = _midpoint_grid(M)
    # Unnormalised log-Beta on the grid (avoids overflow for large a,b).
    # log p(theta) = (a-1)log theta + (b-1)log(1-theta) + const
    log_dens = (a - 1.0) * np.log(grid) + (b - 1.0) * np.log1p(-grid)
    log_dens -= log_dens.max()
    raw = np.exp(log_dens)
    density = raw / raw.sum()
    return ApDistribution(
        label=label or f"Beta({a},{b})",
        theta_grid=grid,
        density=density,
    )


def update_with_bernoulli(
    prior: ApDistribution,
    n_success: int,
    n_fail: int,
    *,
    label: str | None = None,
) -> ApDistribution:
    """Posterior after observing K successes / N-K failures.

    Likelihood at grid point theta_k: theta_k^K * (1 - theta_k)^(N-K).
    """
    if n_success < 0 or n_fail < 0:
        raise ValueError("counts must be non-negative")
    theta = prior.theta_grid
    log_lik = n_success * np.log(theta) + n_fail * np.log1p(-theta)
    log_post = np.log(prior.density + 1e-300) + log_lik
    log_post -= log_post.max()
    raw = np.exp(log_post)
    post = raw / raw.sum()
    return ApDistribution(
        label=label or f"{prior.label}+S{n_success}F{n_fail}",
        theta_grid=theta,
        density=post,
    )


def predictive_probability(ap: ApDistribution) -> float:
    """P(A=1 | I) = E_f[theta] under the meta-distribution."""
    return float(np.sum(ap.theta_grid * ap.density))


def entropy_ap(ap: ApDistribution) -> float:
    """Shannon entropy of the discrete meta-distribution in nats."""
    d = ap.density
    nz = d > 0
    return float(-np.sum(d[nz] * np.log(d[nz])))


def credible_interval(ap: ApDistribution, mass: float = 0.95) -> tuple[float, float]:
    """Equal-tailed credible interval (lo, hi) holding 'mass' total probability."""
    if not (0.0 < mass < 1.0):
        raise ValueError("mass must be in (0, 1)")
    tail = (1.0 - mass) / 2.0
    cdf = np.cumsum(ap.density)
    lo_idx = int(np.searchsorted(cdf, tail))
    hi_idx = int(np.searchsorted(cdf, 1.0 - tail))
    lo_idx = min(lo_idx, len(ap.theta_grid) - 1)
    hi_idx = min(hi_idx, len(ap.theta_grid) - 1)
    return float(ap.theta_grid[lo_idx]), float(ap.theta_grid[hi_idx])
