"""Probability calculations for the Mendel v0.5 example package."""

from __future__ import annotations

from math import comb
from typing import NamedTuple


DOMINANT_COUNT = 295
RECESSIVE_COUNT = 100
RATIO_TOLERANCE = 0.15

MENDELIAN_DOMINANT_PROBABILITY = 3 / 4
BLENDING_ALTERNATIVE_DOMINANT_PROBABILITY = 2 / 3
PRIOR_MENDELIAN_MODEL = 0.5
PRIOR_BLENDING_MODEL = 0.5


class RatioLikelihoods(NamedTuple):
    p_ratio_given_mendelian: float
    p_ratio_given_blending: float


class MendelDataAssociation(NamedTuple):
    p_ratio_given_mendelian: float
    p_ratio_given_blending: float
    prior_mendelian: float
    prior_blending: float
    prior_ratio: float
    p_mendelian_given_ratio: float
    p_blending_given_ratio: float


def binomial_ratio_window_likelihood(
    *,
    dominant_count: int,
    recessive_count: int,
    dominant_probability: float,
    ratio_tolerance: float,
) -> float:
    """Probability of seeing a dominant:recessive ratio near the observed ratio."""
    total = dominant_count + recessive_count
    observed_ratio = dominant_count / recessive_count
    lower = observed_ratio - ratio_tolerance
    upper = observed_ratio + ratio_tolerance

    probability = 0.0
    for dominant in range(total + 1):
        recessive = total - dominant
        if recessive == 0:
            continue
        ratio = dominant / recessive
        if lower <= ratio <= upper:
            probability += (
                comb(total, dominant)
                * dominant_probability**dominant
                * (1 - dominant_probability) ** recessive
            )
    return probability


def mendel_ratio_likelihoods() -> RatioLikelihoods:
    """Compute likelihoods for the observed 2.95:1 F2 ratio."""
    return RatioLikelihoods(
        p_ratio_given_mendelian=binomial_ratio_window_likelihood(
            dominant_count=DOMINANT_COUNT,
            recessive_count=RECESSIVE_COUNT,
            dominant_probability=MENDELIAN_DOMINANT_PROBABILITY,
            ratio_tolerance=RATIO_TOLERANCE,
        ),
        p_ratio_given_blending=binomial_ratio_window_likelihood(
            dominant_count=DOMINANT_COUNT,
            recessive_count=RECESSIVE_COUNT,
            dominant_probability=BLENDING_ALTERNATIVE_DOMINANT_PROBABILITY,
            ratio_tolerance=RATIO_TOLERANCE,
        ),
    )


def mendel_data_association_parameters() -> MendelDataAssociation:
    """Compute Bayes-consistent associate() parameters for model-data comparison."""
    likelihoods = mendel_ratio_likelihoods()
    p_ratio = (
        PRIOR_MENDELIAN_MODEL * likelihoods.p_ratio_given_mendelian
        + PRIOR_BLENDING_MODEL * likelihoods.p_ratio_given_blending
    )
    p_mendel_given_ratio = PRIOR_MENDELIAN_MODEL * likelihoods.p_ratio_given_mendelian / p_ratio
    p_blending_given_ratio = PRIOR_BLENDING_MODEL * likelihoods.p_ratio_given_blending / p_ratio

    return MendelDataAssociation(
        p_ratio_given_mendelian=likelihoods.p_ratio_given_mendelian,
        p_ratio_given_blending=likelihoods.p_ratio_given_blending,
        prior_mendelian=PRIOR_MENDELIAN_MODEL,
        prior_blending=PRIOR_BLENDING_MODEL,
        prior_ratio=p_ratio,
        p_mendelian_given_ratio=p_mendel_given_ratio,
        p_blending_given_ratio=p_blending_given_ratio,
    )
