"""Knowledge — propositions in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §1.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator

_QID_RE = re.compile(r"^[a-z][a-z0-9_]*:[a-z0-9][a-z0-9_\-]*::[a-z_][a-z0-9_]*$")


def make_qid(namespace: str, package_name: str, label: str) -> str:
    """Compose a Qualified Node ID: {namespace}:{package_name}::{label}."""
    return f"{namespace}:{package_name}::{label}"


def is_qid(id_: str) -> bool:
    """Check if an ID string matches QID format."""
    return bool(_QID_RE.match(id_))


class KnowledgeType(StrEnum):
    """Knowledge types (§1.2)."""

    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"


class Parameter(BaseModel):
    """Quantified variable in a universal claim."""

    name: str
    type: str


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


class Knowledge(BaseModel):
    """Knowledge node — a proposition in the Gaia reasoning hypergraph.

    id is a QID ({namespace}:{package_name}::{label}), content is populated.
    """

    id: str | None = None
    label: str | None = None
    title: str | None = None
    type: KnowledgeType
    content: str | None = None
    content_hash: str | None = None
    parameters: list[Parameter] = []
    metadata: dict[str, Any] | None = None

    # provenance
    provenance: list[PackageRef] | None = None

    # narrative (presentational, excluded from content hash)
    module: str | None = None
    declaration_index: int | None = None
    exported: bool = False

    @model_validator(mode="after")
    def _compute_derived_fields(self) -> Knowledge:
        # Knowledge is valid if it has id OR label (or both).
        if self.id is None and self.label is None:
            raise ValueError("Knowledge requires at least one of `id` or `label`.")

        # Content_hash is a derived fingerprint and must stay consistent
        # with the node's actual content.
        if self.content is not None:
            expected_content_hash = _compute_content_hash(self.type, self.content, self.parameters)
            if self.content_hash is not None and self.content_hash != expected_content_hash:
                raise ValueError("content_hash must match the derived content fingerprint")
            self.content_hash = expected_content_hash

        return self
