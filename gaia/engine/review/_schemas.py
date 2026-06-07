"""Review report schemas — pydantic models for gaia review output.

These schemas define the structured output format for all gaia review commands.
Design follows gaia-discovery's contract-first approach: define schema before
implementing the review logic.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewSeverity(StrEnum):
    """Severity levels for review findings."""

    ERROR = "error"  # Must fix before accept
    WARNING = "warning"  # Should fix, not blocking
    INFO = "info"  # Informational, can ignore
    PASS = "pass"  # No issue


class ReviewFinding(BaseModel):
    """A single finding from a review."""

    severity: ReviewSeverity
    category: str = Field(
        ...,
        description="Category: 'prior' / 'calibration' / 'redteam' / 'structural' / 'trace'",
    )
    location: str = Field(
        ..., description="Where: claim_qid / strategy_id / operator_id / 'global'"
    )
    message: str = Field(..., description="Human-readable description")
    detector: str = Field(..., description="Which detector triggered this finding")
    details: dict[str, Any] = Field(default_factory=dict, description="Detector-specific metadata")


class ReviewRecommendation(BaseModel):
    """Actionable recommendation from a review."""

    priority: Literal["high", "medium", "low"]
    action: str = Field(
        ...,
        description="What to do: 'add_evidence' / 'revise_prior' / 'strengthen_rationale' / ...",
    )
    target: str = Field(..., description="Which node/edge to act on")
    rationale: str = Field(..., description="Why this recommendation")
    example: str | None = Field(None, description="Optional example fix")


class ReviewReport(BaseModel):
    """Unified review report across all gaia review commands."""

    review_id: str = Field(..., description="Unique review snapshot ID")
    review_type: Literal[
        "package",
        "node",
        "calibration",
        "redteam",
        "gate",
        "manifest",
        "diff",
        "status",
        "query",
    ]
    created_at: str = Field(..., description="ISO 8601 UTC timestamp")
    path: str = Field(..., description="Path to reviewed package")
    status: Literal["pass", "warning", "error"]
    summary: str = Field(..., description="1-2 sentence summary")
    findings: list[ReviewFinding] = Field(default_factory=list)
    recommendations: list[ReviewRecommendation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Review-type-specific metadata"
    )


class CalibrationDelta(BaseModel):
    """Single claim's prior-to-posterior delta."""

    claim_qid: str
    claim_label: str
    prior: float
    posterior: float
    delta: float = Field(..., description="posterior - prior")
    abs_delta: float = Field(..., description="|delta|")


class CalibrationReport(BaseModel):
    """Calibration audit report — Δ_qid ranking + convergence."""

    review_id: str
    created_at: str
    path: str
    converged: bool
    iterations: int
    top_deltas: list[CalibrationDelta] = Field(..., description="Top-K by |Δ|, descending")
    honesty_check: dict[str, Any] | None = Field(
        None, description="Git diff results if --honesty used"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeBeliefContext(BaseModel):
    """Prior/posterior context for a reviewed node when available."""

    claim_qid: str
    claim_label: str
    prior: float
    posterior: float
    delta: float
    abs_delta: float


class NodeReviewReport(BaseModel):
    """Single-node review report."""

    review_id: str
    created_at: str
    path: str
    node_id: str
    node_kind: Literal["claim", "strategy", "operator", "observe"]
    status: Literal["pass", "warning", "error"]
    belief: NodeBeliefContext | None = None
    findings: list[ReviewFinding] = Field(default_factory=list)
    recommendations: list[ReviewRecommendation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
