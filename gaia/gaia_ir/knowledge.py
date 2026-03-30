"""Knowledge — propositions in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §1.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class KnowledgeType(StrEnum):
    """Knowledge types (§1.2)."""

    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"


class Parameter(BaseModel):
    """Quantified variable in a universal claim."""

    name: str
    type: str


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical Knowledge."""

    local_canonical_id: str
    package_id: str
    version: str


class PackageRef(BaseModel):
    """Reference to a package version."""

    package_id: str
    version: str


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _compute_content_hash(type_: str, content: str, parameters: list[Parameter]) -> str:
    """Content fingerprint: SHA-256(type + content + sorted(parameters)), no package_id.

    Same content in different packages produces the same content_hash.
    Used for canonicalization fast-path (exact match) and curation dedup.
    """
    sorted_params = sorted((p.name, p.type) for p in parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return _sha256_hex(payload, length=64)


def _compute_knowledge_id(
    package_id: str, type_: str, content: str, parameters: list[Parameter]
) -> str:
    """Deterministic local canonical ID: lcn_{sha256(package_id + type + content + sorted(params))[:16]}."""
    sorted_params = sorted((p.name, p.type) for p in parameters)
    payload = f"{package_id}|{type_}|{content}|{sorted_params}"
    return f"lcn_{_sha256_hex(payload)}"


class Knowledge(BaseModel):
    """Knowledge node — unified data class for local and global layers.

    Local layer: id has lcn_ prefix, content is populated.
    Global layer: id has gcn_ prefix, content is usually None (retrieved via representative_lcn).
    """

    id: str | None = None
    type: KnowledgeType
    content: str | None = None
    content_hash: str | None = None
    parameters: list[Parameter] = []
    metadata: dict[str, Any] | None = None

    # local layer
    package_id: str | None = None  # needed for ID computation

    # provenance
    provenance: list[PackageRef] | None = None

    # global layer
    representative_lcn: LocalCanonicalRef | None = None
    local_members: list[LocalCanonicalRef] | None = None

    @model_validator(mode="after")
    def _compute_derived_fields(self) -> Knowledge:
        # Auto-compute content_hash when content is available
        if self.content_hash is None and self.content is not None:
            self.content_hash = _compute_content_hash(self.type, self.content, self.parameters)

        # Auto-compute ID for local nodes
        if self.id is None:
            if self.content is not None and self.package_id is not None:
                self.id = _compute_knowledge_id(
                    self.package_id, self.type, self.content, self.parameters
                )
            else:
                raise ValueError(
                    "Knowledge requires either an explicit `id` or both `content` and "
                    "`package_id` for content-addressed ID computation."
                )
        return self
