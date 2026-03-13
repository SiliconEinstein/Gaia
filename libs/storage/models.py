"""Pydantic v2 models for the storage v2 layer.

These models map directly to Gaia Language concepts: Knowledge, Chain, Module, Package.
See docs/foundations/server/storage-schema.md for the authoritative schema definition.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field


# ── References ──


class KnowledgeRef(BaseModel):
    """Versioned reference to a Knowledge object."""

    knowledge_id: str
    version: int


class ImportRef(BaseModel):
    """Cross-module dependency reference."""

    knowledge_id: str
    version: int
    strength: Literal["strong", "weak"]


class Parameter(BaseModel):
    """Parameter placeholder for schema/∀-quantified knowledge nodes."""

    name: str
    constraint: str


# ── Core Entities ──


class Knowledge(BaseModel):
    """Versioned knowledge object. Identity is (knowledge_id, version)."""

    knowledge_id: str
    version: int
    type: Literal["claim", "question", "setting", "action", "contradiction", "equivalence"]
    kind: str | None = None
    content: str
    parameters: list[Parameter] = []
    prior: float = Field(gt=0, le=1)
    keywords: list[str] = []
    source_package_id: str
    source_package_version: str = "0.1.0"
    source_module_id: str
    created_at: datetime
    embedding: list[float] | None = None

    @property
    def is_schema(self) -> bool:
        """True if this is a schema node (has parameters)."""
        return len(self.parameters) > 0


class ChainStep(BaseModel):
    """A single step within a Chain."""

    step_index: int
    premises: list[KnowledgeRef]
    reasoning: str
    conclusion: KnowledgeRef


class Chain(BaseModel):
    """Reasoning chain connecting knowledge objects within a module."""

    chain_id: str
    module_id: str
    package_id: str
    package_version: str = "0.1.0"
    type: Literal["deduction", "induction", "abstraction", "contradiction", "retraction"]
    steps: list[ChainStep]


class Module(BaseModel):
    """Cohesive knowledge unit grouping knowledge objects and chains."""

    module_id: str
    package_id: str
    package_version: str = "0.1.0"
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
    status: Literal["preparing", "submitted", "merged", "rejected"]


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
    """BP computation result for a versioned knowledge object."""

    knowledge_id: str
    version: int
    belief: float = Field(ge=0, le=1)
    bp_run_id: str
    computed_at: datetime


# ── Graph IR ──


class SourceRef(BaseModel):
    """Reference to the source of a factor in the authoring layer."""

    package: str
    version: str
    module: str
    knowledge_name: str


class FactorNode(BaseModel):
    """Persistent factor from Graph IR. Defines a constraint between knowledge nodes."""

    factor_id: str
    type: Literal["reasoning", "instantiation", "mutex_constraint", "equiv_constraint"]
    premises: list[str] = []
    contexts: list[str] = []
    conclusion: str
    package_id: str
    source_ref: SourceRef | None = None
    metadata: dict | None = None

    @property
    def is_gate_factor(self) -> bool:
        """True for constraint factors (mutex/equiv) where conclusion is gate variable."""
        return self.type in ("mutex_constraint", "equiv_constraint")

    @property
    def bp_participant_ids(self) -> list[str]:
        """Knowledge IDs that participate in BP message passing."""
        if self.is_gate_factor:
            return list(self.premises)
        return list(self.premises) + [self.conclusion]


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
    target_type: Literal["knowledge", "chain", "chain_step", "module", "package"]
    target_id: str
    role: Literal["evidence", "visualization", "implementation", "reproduction", "supplement"]
    description: str | None = None


# ── Query / Result Models ──


class ScoredKnowledge(BaseModel):
    """Knowledge object with a relevance score from search."""

    knowledge: Knowledge
    score: float


class Subgraph(BaseModel):
    """A subset of the knowledge graph returned by traversal queries."""

    knowledge_ids: set[str] = set()
    chain_ids: set[str] = set()


class KnowledgeEmbedding(BaseModel):
    """Embedding vector for a versioned knowledge object, used by VectorStore."""

    knowledge_id: str
    version: int
    embedding: list[float]


# ── Global Identity ──


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical node within a specific package version."""

    package: str
    version: str
    local_canonical_id: str


class PackageRef(BaseModel):
    """Reference to a specific package version."""

    package: str
    version: str


class CanonicalBinding(BaseModel):
    """Maps a local canonical node to a global canonical identity."""

    package: str
    version: str
    local_graph_hash: str
    local_canonical_id: str
    decision: Literal["match_existing", "create_new"]
    global_canonical_id: str
    decided_at: datetime
    decided_by: str
    reason: str | None = None


class GlobalCanonicalNode(BaseModel):
    """Registry-assigned global dedup identity for a knowledge concept."""

    global_canonical_id: str
    knowledge_type: str
    kind: str | None = None
    representative_content: str
    parameters: list[Parameter] = []
    member_local_nodes: list[LocalCanonicalRef] = []
    provenance: list[PackageRef] = []
    metadata: dict | None = None


class FactorParams(BaseModel):
    """Runtime parameters for a factor node."""

    conditional_probability: float


class GlobalInferenceState(BaseModel):
    """Registry-managed global inference state. Probabilities separated from structure."""

    graph_hash: str
    node_priors: dict[str, float] = {}
    factor_parameters: dict[str, FactorParams] = {}
    node_beliefs: dict[str, float] = {}
    updated_at: datetime


# ── Submission Artifact ──


class PackageSubmissionArtifact(BaseModel):
    """Immutable snapshot of a package submission for audit and re-verification."""

    package_name: str
    commit_hash: str
    source_files: dict[str, str]
    raw_graph: dict
    local_canonical_graph: dict
    canonicalization_log: list[dict]
    submitted_at: datetime


# ── Factor derivation ──


def factors_from_chains(chains: list[Chain], package_id: str) -> list[FactorNode]:
    """Derive reasoning factors from storage Chain objects.

    Each chain produces one factor whose premises are the union of all step
    premises and whose conclusion is the last step's conclusion.  This is the
    storage-layer equivalent of Graph IR's ``_build_chain_factor`` and can be
    used by any pipeline that has Chain data but no Graph IR artifacts.
    """
    factors: list[FactorNode] = []
    for chain in chains:
        if not chain.steps:
            continue
        seen: set[str] = set()
        premises: list[str] = []
        for step in chain.steps:
            for prem in step.premises:
                if prem.knowledge_id not in seen:
                    seen.add(prem.knowledge_id)
                    premises.append(prem.knowledge_id)
        conclusion = chain.steps[-1].conclusion.knowledge_id
        # Deterministic factor_id from chain_id
        digest = sha256(chain.chain_id.encode()).hexdigest()[:16]
        factor_id = f"f_{digest}"
        factors.append(
            FactorNode(
                factor_id=factor_id,
                type="reasoning",
                premises=premises,
                contexts=[],
                conclusion=conclusion,
                package_id=package_id,
                metadata={"edge_type": chain.type, "derived_from": "chain"},
            )
        )
    return factors
