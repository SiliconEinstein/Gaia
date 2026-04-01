"""CanonicalBinding — local-to-global node mapping."""

from __future__ import annotations

from pydantic import BaseModel


class CanonicalBinding(BaseModel):
    """Records how a local node was mapped to a global node.

    Immutable after write — new package versions append new records.
    Covers both variable (QID → gcn_id) and factor (lfac_ → gfac_id) bindings.
    """

    local_id: str  # variable QID or lfac_ ID
    global_id: str  # gcn_id or gfac_id
    binding_type: str  # "variable" | "factor"
    package_id: str
    version: str
    decision: str  # "match_existing" | "create_new" | "equivalent_candidate"
    reason: str
