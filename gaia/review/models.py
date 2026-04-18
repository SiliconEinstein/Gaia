"""Author-facing review sidecar models (DEPRECATED).

.. deprecated:: 0.4.2
    Use ``priors.py`` and inline ``reason+prior`` pairing instead.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

from gaia.lang.runtime import Knowledge, Strategy

_DEPRECATION_MSG = (
    "Review sidecars are deprecated since gaia-lang 0.4.2. "
    "Use priors.py and inline reason+prior pairing instead. "
    "See the gaia-cli skill for the recommended workflow."
)


@dataclass
class ClaimReview:
    """Review for an explicit claim Knowledge node."""

    subject: Knowledge
    prior: float | None = None
    judgment: str | None = None
    justification: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedClaimReview:
    """Review for a generated strategy-interface claim.

    These claims are introduced during IR formalization and therefore cannot be
    referenced as author-facing ``Knowledge`` objects in the main package module.
    They are instead addressed by the owning strategy plus an interface role.
    """

    subject: Strategy
    role: str
    prior: float | None = None
    occurrence: int = 0
    judgment: str | None = None
    justification: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyReview:
    """Review for a reasoning Strategy.

    Only parameterized strategies (``infer`` / ``noisy_and``) consume numeric
    parameters during BP. Formal strategies may still carry judgments and
    justifications for human review.
    """

    subject: Strategy
    conditional_probability: float | None = None
    conditional_probabilities: list[float] | None = None
    judgment: str | None = None
    justification: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.conditional_probability is not None and self.conditional_probabilities is not None:
            raise ValueError(
                "review_strategy() accepts either conditional_probability or "
                "conditional_probabilities, not both."
            )


@dataclass
class ReviewBundle:
    """Top-level review artifact exported from ``review.py``."""

    objects: list[ClaimReview | GeneratedClaimReview | StrategyReview]
    source_id: str = "self_review"
    model: str | None = None
    policy: str | None = None
    config: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        if not self.source_id:
            raise ValueError("ReviewBundle.source_id must be non-empty.")


def review_claim(
    subject: Knowledge,
    *,
    prior: float | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> ClaimReview:
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    return ClaimReview(
        subject=subject,
        prior=prior,
        judgment=judgment,
        justification=justification,
        metadata=dict(metadata or {}),
    )


def review_generated_claim(
    subject: Strategy,
    role: str,
    *,
    prior: float | None = None,
    occurrence: int = 0,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> GeneratedClaimReview:
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    if occurrence < 0:
        raise ValueError("occurrence must be >= 0")
    return GeneratedClaimReview(
        subject=subject,
        role=role,
        prior=prior,
        occurrence=occurrence,
        judgment=judgment,
        justification=justification,
        metadata=dict(metadata or {}),
    )


def review_strategy(
    subject: Strategy,
    *,
    conditional_probability: float | None = None,
    conditional_probabilities: list[float] | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> StrategyReview:
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    return StrategyReview(
        subject=subject,
        conditional_probability=conditional_probability,
        conditional_probabilities=list(conditional_probabilities)
        if conditional_probabilities is not None
        else None,
        judgment=judgment,
        justification=justification,
        metadata=dict(metadata or {}),
    )
