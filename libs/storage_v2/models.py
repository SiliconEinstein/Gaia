"""Pydantic v2 models for the storage v2 layer.

These models map directly to Gaia Language concepts: Closure, Chain, Module, Package.
See docs/foundations/server/storage-schema.md for the authoritative schema definition.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── References ──


class ClosureRef(BaseModel):
    """Versioned reference to a Closure."""

    closure_id: str
    version: int


class ImportRef(BaseModel):
    """Cross-module dependency reference."""

    closure_id: str
    version: int
    strength: Literal["strong", "weak"]


# ── Core Entities ──


class Closure(BaseModel):
    """Versioned knowledge object. Identity is (closure_id, version)."""

    closure_id: str
    version: int
    type: Literal["claim", "question", "setting", "action"]
    content: str
    prior: float = Field(gt=0, le=1)
    keywords: list[str] = []
    source_package_id: str
    source_module_id: str
    created_at: datetime
    embedding: list[float] | None = None


class ChainStep(BaseModel):
    """A single step within a Chain."""

    step_index: int
    premises: list[ClosureRef]
    reasoning: str
    conclusion: ClosureRef


class Chain(BaseModel):
    """Reasoning chain connecting closures within a module."""

    chain_id: str
    module_id: str
    package_id: str
    type: Literal["deduction", "induction", "abstraction", "contradiction", "retraction"]
    steps: list[ChainStep]


class Module(BaseModel):
    """Cohesive knowledge unit grouping closures and chains."""

    module_id: str
    package_id: str
    name: str
    role: Literal["reasoning", "setting", "motivation", "follow_up_question", "other"]
    imports: list[ImportRef] = []
    chain_ids: list[str] = []
    export_ids: list[str] = []


class Package(BaseModel):
    """Reusable knowledge container, analogous to a git repo."""

    package_id: str
    name: str
    version: str
    description: str | None = None
    modules: list[str] = []
    exports: list[str] = []
    submitter: str
    submitted_at: datetime
    status: Literal["submitted", "merged", "rejected"]


# ── Probability & Belief ──


class ProbabilityRecord(BaseModel):
    """Reliability of a reasoning step, keyed by (chain_id, step_index)."""

    chain_id: str
    step_index: int
    value: float = Field(gt=0, le=1)
    source: Literal["author", "llm_review", "lean_verify", "code_verify"]
    source_detail: str | None = None
    recorded_at: datetime


class BeliefSnapshot(BaseModel):
    """BP computation result for a versioned closure."""

    closure_id: str
    version: int
    belief: float = Field(ge=0, le=1)
    bp_run_id: str
    computed_at: datetime


# ── Resources ──


class Resource(BaseModel):
    """Metadata for an attached resource (actual file lives in TOS)."""

    resource_id: str
    type: Literal["image", "code", "notebook", "dataset", "checkpoint", "tool_output", "other"]
    format: str
    title: str | None = None
    description: str | None = None
    storage_backend: str
    storage_path: str
    size_bytes: int | None = None
    checksum: str | None = None
    metadata: dict = {}
    created_at: datetime
    source_package_id: str


class ResourceAttachment(BaseModel):
    """Many-to-many link between a Resource and a target entity."""

    resource_id: str
    target_type: Literal["closure", "chain", "chain_step", "module", "package"]
    target_id: str
    role: Literal["evidence", "visualization", "implementation", "reproduction", "supplement"]
    description: str | None = None


# ── Query / Result Models ──


class ScoredClosure(BaseModel):
    """Closure with a relevance score from search."""

    closure: Closure
    score: float


class Subgraph(BaseModel):
    """A subset of the knowledge graph returned by traversal queries."""

    closure_ids: set[str] = set()
    chain_ids: set[str] = set()


class ClosureEmbedding(BaseModel):
    """Embedding vector for a versioned closure, used by VectorStore."""

    closure_id: str
    version: int
    embedding: list[float]
