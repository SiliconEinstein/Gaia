"""Shared data models for Gaia — Node, HyperEdge, and commit operations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ── Core Graph Entities ──


class Node(BaseModel):
    id: int
    type: str  # paper-extract | abstraction | deduction | conjecture | ...
    subtype: str | None = None
    title: str | None = None
    content: str | dict | list
    keywords: list[str] = []
    prior: float = 1.0
    belief: float | None = None
    status: Literal["active", "deleted"] = "active"
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None


class HyperEdge(BaseModel):
    id: int
    type: str  # paper-extract | abstraction | induction | contradiction | retraction
    subtype: str | None = None
    premises: list[int]
    conclusions: list[int]
    probability: float | None = None
    verified: bool = False
    reasoning: list = []
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None


# ── Commit Operations ──


class NewNode(BaseModel):
    content: str | dict | list
    keywords: list[str] = []
    extra: dict = {}


class NodeRef(BaseModel):
    node_id: int


class AddEdgeOp(BaseModel):
    op: Literal["add_edge"] = "add_edge"
    premises: list[NewNode | NodeRef]
    conclusions: list[NewNode | NodeRef]
    type: str
    reasoning: list


class ModifyEdgeOp(BaseModel):
    op: Literal["modify_edge"] = "modify_edge"
    edge_id: int
    changes: dict


class ModifyNodeOp(BaseModel):
    op: Literal["modify_node"] = "modify_node"
    node_id: int
    changes: dict


# ── Commit Workflow ──


class CommitRequest(BaseModel):
    """Inbound request to submit a commit."""

    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]


class ValidationResult(BaseModel):
    """Result of structural validation for one operation."""

    op_index: int
    valid: bool
    errors: list[str] = []


class DedupCandidate(BaseModel):
    """A potential duplicate found during dedup checking."""

    node_id: int
    content: str
    score: float


class ReviewResult(BaseModel):
    """Result of LLM review."""

    approved: bool
    issues: list[str] = []
    suggestions: list[str] = []


# ── Detailed Review Models (v3) ──


class NNCandidate(BaseModel):
    node_id: str
    similarity: float


class QualityMetrics(BaseModel):
    reasoning_valid: bool
    tightness: float
    substantiveness: float
    novelty: float


class AbstractionTreeResults(BaseModel):
    cc: list[dict] = []
    cp: list[dict] = []


class ContradictionResult(BaseModel):
    node_id: str
    edge_id: str
    description: str


class OverlapResult(BaseModel):
    existing_node_id: str
    similarity: float
    recommendation: str  # "merge" | "keep_both"


class OperationReviewDetail(BaseModel):
    op_index: int
    verdict: str  # "pass" | "has_overlap" | "rejected"
    embedding_generated: bool
    nn_candidates: list[NNCandidate] = []
    quality: QualityMetrics | None = None
    abstraction_trees: AbstractionTreeResults = AbstractionTreeResults()
    contradictions: list[ContradictionResult] = []
    overlaps: list[OverlapResult] = []


class BPResults(BaseModel):
    belief_updates: dict[str, float] = {}
    iterations: int = 0
    converged: bool = False
    affected_nodes: list[str] = []


class DetailedReviewResult(BaseModel):
    overall_verdict: str  # "pass" | "has_overlap" | "rejected"
    operations: list[OperationReviewDetail] = []
    bp_results: BPResults | None = None


class MergeResult(BaseModel):
    """Result of merging a commit into the graph."""

    success: bool
    new_node_ids: list[int] = []
    new_edge_ids: list[int] = []
    errors: list[str] = []
    bp_results: BPResults | None = None
    abstraction_edges_created: list[str] = []
    beliefs_persisted: dict[str, float] = {}


class Commit(BaseModel):
    """A commit representing a batch of graph operations."""

    commit_id: str
    status: Literal["pending_review", "reviewed", "rejected", "merged"] = "pending_review"
    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]
    check_results: dict | None = None
    review_results: dict | None = None
    merge_results: dict | None = None
    review_job_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommitResponse(BaseModel):
    """Response after submitting a commit."""

    commit_id: str
    status: str
    check_results: dict | None = None
