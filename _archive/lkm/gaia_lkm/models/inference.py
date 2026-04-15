"""BeliefSnapshot — BP inference result."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BeliefSnapshot(BaseModel):
    """Snapshot of a global BP run.

    beliefs contains only visibility=public, type=claim variables.
    Reproducibility: graph_hash + resolution_policy + prior_cutoff uniquely
    determine the BP run.
    """

    snapshot_id: str
    timestamp: datetime
    graph_hash: str  # deterministic hash of graph structure
    resolution_policy: str  # "latest" | "source:<source_id>"
    prior_cutoff: datetime  # parameter timestamp cutoff
    beliefs: dict[str, float]  # gcn_id → belief value
    converged: bool
    iterations: int
    max_residual: float
