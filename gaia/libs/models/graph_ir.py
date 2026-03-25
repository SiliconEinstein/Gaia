"""Graph IR models — KnowledgeNode, FactorNode, and graph containers.

Implements the unified data classes for local and global canonical graphs
as defined in docs/foundations/graph-ir/graph-ir.md.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KnowledgeType(StrEnum):
    """Knowledge node types (graph-ir.md section 1.2)."""

    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"
    TEMPLATE = "template"


class FactorCategory(StrEnum):
    """Factor category — how the conclusion was reached (section 2.2)."""

    INFER = "infer"
    TOOLCALL = "toolcall"
    PROOF = "proof"


class FactorStage(StrEnum):
    """Factor lifecycle stage (section 2.2)."""

    INITIAL = "initial"
    CANDIDATE = "candidate"
    PERMANENT = "permanent"


class ReasoningType(StrEnum):
    """Specific reasoning relation type (section 2.2)."""

    ENTAILMENT = "entailment"
    INDUCTION = "induction"
    ABDUCTION = "abduction"
    EQUIVALENT = "equivalent"
    CONTRADICT = "contradict"


# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------


class Parameter(BaseModel):
    """Template free variable."""

    name: str
    type: str


class SourceRef(BaseModel):
    """Reference to source package location."""

    package: str
    version: str
    module: str | None = None
    knowledge_name: str | None = None


class Step(BaseModel):
    """A single reasoning step within a factor."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical node."""

    local_canonical_id: str
    package_id: str
    version: str


class PackageRef(BaseModel):
    """Reference to a package version."""

    package_id: str
    version: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: str, length: int = 16) -> str:
    """Return first `length` hex chars of SHA-256 digest."""
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _compute_knowledge_id(type_: str, content: str, parameters: list[Parameter]) -> str:
    """Deterministic local canonical ID from type + content + sorted parameters."""
    sorted_params = sorted((p.name, p.type) for p in parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return f"lcn_{_sha256_hex(payload)}"


def _compute_factor_id(
    scope: str,
    category: str,
    premises: list[str],
    conclusion: str | None,
) -> str:
    """Deterministic factor ID from scope + category + sorted premises + conclusion."""
    prefix = "lcf_" if scope == "local" else "gcf_"
    payload = f"{scope}|{category}|{sorted(premises)}|{conclusion}"
    return f"{prefix}{_sha256_hex(payload)}"


# ---------------------------------------------------------------------------
# KnowledgeNode
# ---------------------------------------------------------------------------


class KnowledgeNode(BaseModel):
    """Knowledge node — unified data class for local and global layers.

    If `id` is not provided and `content` is not None, the ID is
    content-addressed: ``lcn_{sha256(type + content + sorted(parameters))[:16]}``.
    """

    id: str | None = None
    type: KnowledgeType
    content: str | None = None
    parameters: list[Parameter] = []
    source_refs: list[SourceRef]
    metadata: dict[str, Any] | None = None
    provenance: list[PackageRef] | None = None
    representative_lcn: LocalCanonicalRef | None = None
    member_local_nodes: list[LocalCanonicalRef] | None = None

    @model_validator(mode="after")
    def _compute_id(self) -> KnowledgeNode:
        if self.id is None:
            if self.content is not None:
                self.id = _compute_knowledge_id(self.type, self.content, self.parameters)
            else:
                raise ValueError(
                    "KnowledgeNode requires either an explicit `id` or `content` "
                    "for content-addressed ID computation."
                )
        return self


# ---------------------------------------------------------------------------
# FactorNode
# ---------------------------------------------------------------------------


class FactorNode(BaseModel):
    """Factor node — unified data class for local and global layers.

    The ``factor_id`` is auto-computed from
    ``scope + category + sorted(premises) + conclusion``.
    """

    factor_id: str | None = None
    scope: str  # "local" | "global"
    category: FactorCategory
    stage: FactorStage
    reasoning_type: ReasoningType | None = None
    premises: list[str]
    conclusion: str | None = None
    steps: list[Step] | None = None
    weak_points: list[str] | None = None
    subgraph: list[FactorNode] | None = None
    source_ref: SourceRef | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_and_compute_id(self) -> FactorNode:
        self._validate_invariants()

        # Compute factor_id if not provided
        if self.factor_id is None:
            self.factor_id = _compute_factor_id(
                self.scope, self.category, self.premises, self.conclusion
            )
        return self

    def _validate_invariants(self) -> None:
        """Validate FactorNode invariants from graph-ir.md §2.3."""
        # Invariant 1: candidate/permanent infer requires reasoning_type
        if (
            self.stage in (FactorStage.CANDIDATE, FactorStage.PERMANENT)
            and self.category == FactorCategory.INFER
            and self.reasoning_type is None
        ):
            raise ValueError(f"stage={self.stage} with category=infer requires reasoning_type")

        # §2.3: toolcall/proof have reasoning_type=None and stay at initial
        if self.category in (FactorCategory.TOOLCALL, FactorCategory.PROOF):
            if self.reasoning_type is not None:
                raise ValueError(
                    f"category={self.category} must have reasoning_type=None, "
                    f"got {self.reasoning_type}"
                )
            if self.stage in (FactorStage.CANDIDATE, FactorStage.PERMANENT):
                raise ValueError(
                    f"category={self.category} must stay at stage=initial, got stage={self.stage}"
                )

        # Invariant 6: bilateral types require conclusion=None and premises >= 2
        if self.reasoning_type in (ReasoningType.EQUIVALENT, ReasoningType.CONTRADICT):
            if self.conclusion is not None:
                raise ValueError(f"reasoning_type={self.reasoning_type} requires conclusion=None")
            if len(self.premises) < 2:
                raise ValueError(
                    f"reasoning_type={self.reasoning_type} requires at least 2 premises"
                )

        # §2.6: subgraph only allowed for permanent stage
        if self.subgraph is not None and self.stage != FactorStage.PERMANENT:
            raise ValueError(f"subgraph is only allowed at stage=permanent, got stage={self.stage}")

        # -- Deferred cross-object invariants (require graph-level context) --
        # §2.3 invariant 2: conclusion node type must be claim (needs node registry)
        # §2.3 invariant 3: premise types restricted to claim/setting/question/template
        #   (needs node registry)
        # §2.3 invariant 5: template may only appear as premise of entailment
        #   (needs node registry)


# ---------------------------------------------------------------------------
# Graph containers
# ---------------------------------------------------------------------------


def _canonical_json(knowledge_nodes: list[KnowledgeNode], factor_nodes: list[FactorNode]) -> str:
    """Produce canonical JSON for hashing."""
    data = {
        "knowledge_nodes": [n.model_dump(mode="json") for n in knowledge_nodes],
        "factor_nodes": [f.model_dump(mode="json") for f in factor_nodes],
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


class LocalCanonicalGraph(BaseModel):
    """Local canonical graph with content-addressed hash."""

    scope: str = "local"
    graph_hash: str | None = None
    knowledge_nodes: list[KnowledgeNode]
    factor_nodes: list[FactorNode]

    @model_validator(mode="after")
    def _compute_hash(self) -> LocalCanonicalGraph:
        if self.graph_hash is None:
            canonical = _canonical_json(self.knowledge_nodes, self.factor_nodes)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            self.graph_hash = f"sha256:{digest}"
        return self


class GlobalCanonicalGraph(BaseModel):
    """Global canonical graph."""

    scope: str = "global"
    knowledge_nodes: list[KnowledgeNode]
    factor_nodes: list[FactorNode]
