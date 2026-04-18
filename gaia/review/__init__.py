"""Gaia review sidecar DSL (DEPRECATED).

.. deprecated:: 0.4.2
    Review sidecars are superseded by ``priors.py`` and inline ``reason+prior``
    pairing in the DSL.  Use ``priors.py`` (exports ``PRIORS: dict``) for leaf
    claim priors, and the ``prior=`` keyword on strategies for warrant priors.
    This module is retained for backward compatibility and will be removed in a
    future major release.
"""

from gaia.review.models import (
    ClaimReview,
    GeneratedClaimReview,
    ReviewBundle,
    StrategyReview,
    review_claim,
    review_generated_claim,
    review_strategy,
)

__all__ = [
    "ClaimReview",
    "GeneratedClaimReview",
    "ReviewBundle",
    "StrategyReview",
    "review_claim",
    "review_generated_claim",
    "review_strategy",
]
