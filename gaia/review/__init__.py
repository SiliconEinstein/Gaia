"""Gaia review sidecar DSL.

Review sidecars live next to a Gaia Lang package and provide agent-authored
parameterization metadata without mutating the package's structural IR.
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
