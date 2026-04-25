"""Probability calculations for the Mendel v0.5 example package.

The statistical comparison is between two clearly identified alternatives:

* Mendelian segregation: a point hypothesis with a known dominant probability
  ``p = 3/4`` under a single-factor cross.
* A diffuse alternative: the dominant probability ``p`` is unknown and assigned
  a uniform prior on ``[0, 1]``. Its marginal likelihood for any specific
  dominant count ``k`` in ``N`` trials has the closed-form value ``1 / (N + 1)``
  (since ``∫₀¹ C(N, k) p^k (1 - p)^(N - k) dp = 1 / (N + 1)``).

Every number produced by this module is therefore traceable to ``MENDELIAN_P``
and the uniform-over-``p`` reference measure. There is no tolerance window,
no post-hoc ratio band, and no strawman binomial with an arbitrary second
``p``. The likelihood handed to ``associate`` is the pointwise binomial PMF
evaluated at the observed count.
"""

from __future__ import annotations

from math import comb
from typing import NamedTuple


DOMINANT_COUNT = 295
RECESSIVE_COUNT = 100
TOTAL_COUNT = DOMINANT_COUNT + RECESSIVE_COUNT

MENDELIAN_DOMINANT_PROBABILITY = 3 / 4
PRIOR_MENDELIAN_MODEL = 0.5


class MendelCountAssociation(NamedTuple):
    p_count_given_mendelian: float
    p_count_given_diffuse: float
    prior_mendelian: float
    prior_count: float
    p_mendelian_given_count: float


def binomial_pmf(*, n: int, k: int, p: float) -> float:
    """Pointwise binomial probability ``P(X = k | n, p)``."""
    return comb(n, k) * p**k * (1 - p) ** (n - k)


def diffuse_count_marginal(*, n: int) -> float:
    """Marginal likelihood of any single count under ``p ~ Uniform[0, 1]``.

    Using ``∫₀¹ C(n, k) p^k (1 - p)^(n - k) dp = 1 / (n + 1)``, this is the
    probability of observing any specific ``k`` when ``p`` is unknown and
    uniformly distributed on ``[0, 1]``. It is independent of ``k``.
    """
    return 1.0 / (n + 1)


def mendel_count_association_parameters() -> MendelCountAssociation:
    """Compute Bayes-consistent ``associate`` parameters for the Mendel ↔ count relation.

    The posterior is formed by marginalising over the Mendelian point hypothesis
    and the diffuse alternative:

    ``P(count) = P(M) · P(count | M) + (1 − P(M)) · P(count | diffuse)``
    """
    p_count_given_mendelian = binomial_pmf(
        n=TOTAL_COUNT,
        k=DOMINANT_COUNT,
        p=MENDELIAN_DOMINANT_PROBABILITY,
    )
    p_count_given_diffuse = diffuse_count_marginal(n=TOTAL_COUNT)

    prior_count = (
        PRIOR_MENDELIAN_MODEL * p_count_given_mendelian
        + (1.0 - PRIOR_MENDELIAN_MODEL) * p_count_given_diffuse
    )
    p_mendelian_given_count = PRIOR_MENDELIAN_MODEL * p_count_given_mendelian / prior_count

    return MendelCountAssociation(
        p_count_given_mendelian=p_count_given_mendelian,
        p_count_given_diffuse=p_count_given_diffuse,
        prior_mendelian=PRIOR_MENDELIAN_MODEL,
        prior_count=prior_count,
        p_mendelian_given_count=p_mendelian_given_count,
    )
