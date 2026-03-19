"""Pydantic models for the curation service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SimilarityPair(BaseModel):
    """A pair of GlobalCanonicalNodes with measured similarity."""

    node_a_id: str
    node_b_id: str
    similarity_score: float
    method: Literal["embedding", "bm25", "both"]


class ClusterGroup(BaseModel):
    """A group of similar GlobalCanonicalNodes discovered by clustering."""

    cluster_id: str
    node_ids: list[str]
    pairs: list[SimilarityPair] = Field(default_factory=list)


class CurationSuggestion(BaseModel):
    """A suggested curation operation with confidence score."""

    suggestion_id: str = Field(default_factory=lambda: f"sug_{uuid4().hex[:12]}")
    operation: Literal[
        "merge",
        "create_equivalence",
        "create_contradiction",
        "create_abstraction",
        "fix_dangling_factor",
        "archive_orphan",
    ]
    target_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: dict = Field(default_factory=dict)


class ConflictCandidate(BaseModel):
    """A candidate contradiction discovered via BP signals or sensitivity analysis."""

    node_a_id: str
    node_b_id: str
    signal_type: Literal["oscillation", "sensitivity", "both"]
    strength: float = Field(ge=0.0, le=1.0)
    detail: dict = Field(default_factory=dict)


class StructureIssue(BaseModel):
    """A structural issue found during graph inspection."""

    issue_type: Literal[
        "orphan_node",
        "dangling_factor",
        "high_degree",
        "disconnected_component",
    ]
    severity: Literal["error", "warning", "info"]
    node_ids: list[str] = Field(default_factory=list)
    factor_ids: list[str] = Field(default_factory=list)
    detail: str = ""


class StructureReport(BaseModel):
    """Result of structure inspection."""

    issues: list[StructureIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[StructureIssue]:
        return [i for i in self.issues if i.severity == "info"]


class AuditEntry(BaseModel):
    """Immutable record of a curation operation for audit and rollback."""

    entry_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex[:12]}")
    operation: str
    target_ids: list[str]
    suggestion_id: str
    rollback_data: dict = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Abstraction pipeline models ──


class AbstractionGroup(BaseModel):
    """A group of claims sharing a common weaker conclusion."""

    group_id: str
    abstraction_content: str
    member_node_ids: list[str]
    reason: str
    contradiction_pairs: list[tuple[str, str]] = Field(default_factory=list)
    confidence: float = 0.0
    refine_history: list[dict] = Field(default_factory=list)


class VerificationCheck(BaseModel):
    """Per-member entailment check result."""

    member_id: str
    entails: bool
    reason: str = ""


class VerificationResult(BaseModel):
    """Result of verifying an abstraction group."""

    group_id: str
    passed: bool
    checks: list[VerificationCheck] = Field(default_factory=list)
    union_error: bool = False
    union_error_detail: str = ""


class AbstractionResult(BaseModel):
    """Result of the full abstraction pipeline."""

    new_nodes: list = Field(default_factory=list)
    new_factors: list = Field(default_factory=list)
    contradiction_candidates: list[ConflictCandidate] = Field(default_factory=list)
    suggestions: list[CurationSuggestion] = Field(default_factory=list)


# ── Three-tier thresholds ──

AUTO_APPROVE_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.70


class CurationPlan(BaseModel):
    """Aggregated curation suggestions with three-tier classification."""

    suggestions: list[CurationSuggestion] = Field(default_factory=list)

    @property
    def auto_approve(self) -> list[CurationSuggestion]:
        return [s for s in self.suggestions if s.confidence > AUTO_APPROVE_THRESHOLD]

    @property
    def needs_review(self) -> list[CurationSuggestion]:
        return [
            s
            for s in self.suggestions
            if REVIEW_THRESHOLD <= s.confidence <= AUTO_APPROVE_THRESHOLD
        ]

    @property
    def discard(self) -> list[CurationSuggestion]:
        return [s for s in self.suggestions if s.confidence < REVIEW_THRESHOLD]


class CurationResult(BaseModel):
    """Result of executing a curation plan."""

    executed: list[CurationSuggestion] = Field(default_factory=list)
    skipped: list[CurationSuggestion] = Field(default_factory=list)
    audit_entries: list[AuditEntry] = Field(default_factory=list)
    structure_report: StructureReport = Field(default_factory=StructureReport)
