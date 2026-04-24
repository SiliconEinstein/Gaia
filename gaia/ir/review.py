"""ReviewManifest — qualitative package-level review layer for Gaia IR v6."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INPUTS = "needs_inputs"


class Review(BaseModel):
    """Qualitative review record for a compiled Strategy or Operator target."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    action_label: str
    target_kind: Literal["strategy", "operator", "knowledge", "compose"]
    target_id: str
    status: ReviewStatus
    audit_question: str
    reviewer_notes: str | None = None
    timestamp: str | None = None
    round: int = 1


class ReviewManifest(BaseModel):
    """Collection of qualitative review records."""

    model_config = ConfigDict(extra="forbid")

    reviews: list[Review] = []

    def latest_status(self, target_id: str) -> ReviewStatus | None:
        relevant = [review for review in self.reviews if review.target_id == target_id]
        if not relevant:
            return None
        return max(relevant, key=lambda review: review.round).status
