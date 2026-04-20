"""v6 review manifest models.

These models are IR-adjacent review state. They do not enter BP and do not
carry epistemic probability.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class WarrantStatus(StrEnum):
    """Review status for a v6 Strategy warrant."""

    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INPUTS = "needs_inputs"
    SUPERSEDED = "superseded"


class ReviewNote(BaseModel):
    """Human or agent note attached to a Warrant."""

    author: str | None = None
    note: str
    metadata: dict[str, Any] | None = None


class Warrant(BaseModel):
    """Review block attached to a Strategy.

    A Warrant controls whether a Strategy is included by review policy. It is
    not Knowledge, not a Claim, and not a probability parameter.
    """

    id: str
    subject_strategy_id: str
    subject_hash: str
    status: WarrantStatus
    blocking: bool = True
    review_question: str | None = None
    required_inputs: list[str] = []
    reviewer_notes: list[ReviewNote] = []
    resolution: str | None = None

    @model_validator(mode="after")
    def _validate_status_payload(self) -> Warrant:
        if self.status == WarrantStatus.NEEDS_INPUTS and not self.required_inputs:
            raise ValueError("needs_inputs warrant must list required_inputs")
        if self.status in {WarrantStatus.REJECTED, WarrantStatus.SUPERSEDED} and not self.resolution:
            raise ValueError(f"{self.status.value} warrant should include resolution")
        return self


class ReviewManifest(BaseModel):
    """Package-level v6 review layer."""

    warrants: list[Warrant] = []

