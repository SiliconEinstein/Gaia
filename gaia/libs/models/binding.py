"""CanonicalBinding model — local-to-global node mapping decision.

Implements the schema defined in docs/foundations/graph-ir/graph-ir.md §3.4.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class BindingDecision(StrEnum):
    """Outcome of the canonicalization matching step (graph-ir.md §3.4)."""

    MATCH_EXISTING = "match_existing"
    CREATE_NEW = "create_new"
    EQUIVALENT_CANDIDATE = "equivalent_candidate"


class CanonicalBinding(BaseModel):
    """Records how a local canonical node was mapped to a global canonical node.

    Created during ``canonicalize_package()`` for every local knowledge node.
    The ``decision`` field captures whether the node was merged with an existing
    global node, created fresh, or linked via a candidate equivalent factor.
    """

    local_canonical_id: str
    global_canonical_id: str
    package_id: str
    version: str
    decision: BindingDecision
    reason: str  # e.g. "cosine similarity 0.95" or "no matching global node found"
