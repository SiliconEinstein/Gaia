"""BeliefState — BP output on GlobalCanonicalGraph.

Implements docs/foundations/gaia-ir/belief-state.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BeliefState(BaseModel):
    """BP run output — posterior beliefs on claim Knowledge.

    Records reproduction conditions (resolution_policy + prior_cutoff) so the
    run can be replayed. Only type=claim Knowledge appears in beliefs.
    """

    bp_run_id: str
    created_at: datetime = Field(default_factory=_utc_now)

    # reproduction conditions
    resolution_policy: str  # "latest" | "source:<source_id>"
    prior_cutoff: datetime

    # beliefs: gcn_ ID → posterior probability (claims only)
    beliefs: dict[str, float]

    # compilation info (optional diagnostics)
    compilation_summary: dict[str, Any] | None = None  # strategy_id → compilation path

    # diagnostics
    converged: bool
    iterations: int
    max_residual: float
