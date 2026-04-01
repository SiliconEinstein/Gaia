"""Factor node models — local and global layers.

Unifies upstream Strategy and Operator into a single factor concept,
distinguished by factor_type field.
"""

from __future__ import annotations

from pydantic import BaseModel


class Step(BaseModel):
    """A single reasoning step (local layer only)."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class LocalFactorNode(BaseModel):
    """Local layer factor node — stores steps for strategies.

    Unifies Strategy and Operator from Gaia IR.
    """

    id: str  # "lfac_{sha256[:16]}"
    factor_type: str  # "strategy" | "operator"
    subtype: str  # see spec subtype table
    premises: list[str]  # premise variable IDs (QIDs)
    conclusion: str  # conclusion variable ID (QID)
    background: list[str] | None = None  # context IDs (strategy only)
    steps: list[Step] | None = None  # reasoning steps (strategy only)
    source_package: str
    metadata: dict | None = None


class GlobalFactorNode(BaseModel):
    """Global layer factor node — structure only, no steps.

    Steps are retrieved via representative_lfn → local_factor_nodes[lfn_id].steps.
    """

    id: str  # "gfac_{sha256[:16]}"
    factor_type: str  # "strategy" | "operator"
    subtype: str
    premises: list[str]  # premise gcn_ids
    conclusion: str  # conclusion gcn_id
    representative_lfn: str  # local factor ID (lfac_ prefix)
    source_package: str
    metadata: dict | None = None
