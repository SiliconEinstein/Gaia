"""BeliefState model — BP output on the GlobalCanonicalGraph.

Implements the schema defined in docs/foundations/graph-ir/belief-state.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class BeliefState(BaseModel):
    """BP run output — posterior beliefs on claim nodes.

    Records both the belief values and the reproduction conditions
    (resolution_policy + prior_cutoff) so that the run can be replayed.
    Only nodes with ``type=claim`` appear in ``beliefs``.
    """

    bp_run_id: str
    created_at: datetime = Field(default_factory=_utc_now)

    # Reproduction conditions
    resolution_policy: str  # "latest" | "source:<source_id>"
    prior_cutoff: datetime  # Only records before this timestamp were used

    # Beliefs: gcn_ ID → posterior probability (claims only)
    beliefs: dict[str, float]

    # Diagnostics
    converged: bool
    iterations: int
    max_residual: float
