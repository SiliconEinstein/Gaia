"""Shared data models for Gaia — Node, HyperEdge, and commit operations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ── Core Graph Entities ──


class Node(BaseModel):
    id: int
    type: str  # paper-extract | join | deduction | conjecture | ...
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
    type: str  # paper-extract | join | meet | contradiction | retraction
    subtype: str | None = None
    tail: list[int]
    head: list[int]
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
    tail: list[NewNode | NodeRef]
    head: list[NewNode | NodeRef]
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


class MergeResult(BaseModel):
    """Result of merging a commit into the graph."""

    success: bool
    new_node_ids: list[int] = []
    new_edge_ids: list[int] = []
    errors: list[str] = []


class Commit(BaseModel):
    """A commit representing a batch of graph operations."""

    commit_id: str
    status: Literal["pending_review", "reviewed", "rejected", "merged"] = "pending_review"
    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]
    check_results: dict | None = None
    review_results: dict | None = None
    merge_results: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommitResponse(BaseModel):
    """Response after submitting a commit."""

    commit_id: str
    status: str
    check_results: dict | None = None
