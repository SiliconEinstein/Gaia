"""Variable node models — local and global layers."""

from __future__ import annotations

from pydantic import BaseModel

from gaia.lkm.models._hash import compute_content_hash


class Parameter(BaseModel):
    """Quantified variable in a universal claim."""

    name: str
    type: str


class LocalCanonicalRef(BaseModel):
    """Reference to a local variable node."""

    local_id: str  # QID format
    package_id: str
    version: str


class LocalVariableNode(BaseModel):
    """Local layer variable node — stores content.

    Corresponds to a Knowledge in Gaia IR, flattened for LKM storage.
    """

    id: str  # QID: {namespace}:{package_name}::{label}
    type: str  # "claim" | "setting" | "question"
    visibility: str  # "public" | "private"
    content: str
    content_hash: str  # SHA-256, excludes package_id
    parameters: list[Parameter] = []
    source_package: str
    metadata: dict | None = None

    def recompute_content_hash(self) -> str:
        """Recompute content_hash from current fields. For verification only."""
        return compute_content_hash(
            self.type,
            self.content,
            [(p.name, p.type) for p in self.parameters],
        )


class GlobalVariableNode(BaseModel):
    """Global layer variable node — structure only, no content.

    Content is retrieved via representative_lcn → local_variable_nodes[local_id].content.
    """

    id: str  # gcn_id: "gcn_{uuid4_hex[:16]}"
    type: str  # "claim" | "setting" | "question"
    visibility: str  # "public" | "private"
    content_hash: str  # denormalized from representative_lcn
    parameters: list[Parameter] = []
    representative_lcn: LocalCanonicalRef
    local_members: list[LocalCanonicalRef] = []
    metadata: dict | None = None
