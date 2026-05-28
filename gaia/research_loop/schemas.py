"""Schemas for the agent-facing Gaia research loop protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TASK_SCHEMA: Literal["gaia.research_loop.task.v1"] = "gaia.research_loop.task.v1"
CANDIDATE_SCHEMA: Literal["gaia.research_loop.candidate.v1"] = "gaia.research_loop.candidate.v1"
ARTIFACT_SCHEMA = "gaia.research_loop.artifact.v1"
GATE_SCHEMA = "gaia.research_loop.gate.v1"
EVENT_SCHEMA: Literal["gaia.research_loop.event.v1"] = "gaia.research_loop.event.v1"
STATE_SCHEMA: Literal["gaia.research_loop.state.v1"] = "gaia.research_loop.state.v1"

Stage = Literal["explore", "assess"]


def utcnow() -> str:
    """Return a compact UTC timestamp for artifacts and events."""
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class TaskKind(StrEnum):
    """Research loop task kinds."""

    SCOPE = "scope"
    QUERY_PLAN = "query_plan"
    SEARCH_EXECUTION = "search_execution"
    FOCUS_SYNTHESIS = "focus_synthesis"
    EXPLORE_GATE = "explore_gate"
    ASSESSMENT_CONTEXT = "assessment_context"
    EVIDENCE_DIAGNOSIS = "evidence_diagnosis"
    ASSESS_GATE = "assess_gate"


class EvidenceRef(BaseModel):
    """A grounded source reference that a task or candidate may cite."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str
    role: str | None = None


class RepairContext(BaseModel):
    """Validation failure context for retrying the same task."""

    model_config = ConfigDict(extra="forbid")

    failed_candidate_path: str
    errors: list[dict[str, Any]]
    instruction: str
    preserved_fields: dict[str, Any] = Field(default_factory=dict)


class ResearchLoopTask(BaseModel):
    """Self-contained task envelope emitted to an external agent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["gaia.research_loop.task.v1"] = Field(default=TASK_SCHEMA, alias="schema")
    task_id: str
    stage: Stage
    kind: TaskKind
    objective: str
    inputs: dict[str, Any]
    instructions: list[str]
    allowed_actions: list[str]
    recommended_action: str
    output_contract: dict[str, Any]
    allowed_refs: list[EvidenceRef] = Field(default_factory=list)
    minimal_example: dict[str, Any]
    submit_command: str
    validation: dict[str, Any] = Field(default_factory=dict)
    repair_context: RepairContext | None = None


class CandidateEnvelope(BaseModel):
    """Candidate output submitted for a research loop task."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["gaia.research_loop.candidate.v1"] = Field(
        default=CANDIDATE_SCHEMA,
        alias="schema",
    )
    task_id: str
    stage: Stage
    kind: TaskKind
    selected_action: str
    override_rationale: str | None = None
    payload: dict[str, Any]

    def validate_against_actions(
        self,
        *,
        recommended_action: str,
        allowed_actions: list[str],
    ) -> None:
        """Validate action choice against the task recommendation."""
        if self.selected_action not in allowed_actions:
            raise ValueError(f"selected_action {self.selected_action!r} is not allowed")
        if self.selected_action != recommended_action and not self.override_rationale:
            raise ValueError("override_rationale is required when overriding recommendation")


class ScopeCandidatePayload(BaseModel):
    """Structured scope proposed by an agent or human."""

    model_config = ConfigDict(extra="forbid")

    seed_question: str
    domain_profile: str | None = None
    scope_dimensions: dict[str, list[str]] = Field(default_factory=dict)
    search_budget: int = 5


class PlannedQuery(BaseModel):
    """One planned LKM query."""

    model_config = ConfigDict(extra="forbid")

    query: str
    purpose: str
    expected_evidence_family: str | None = None
    source_ref: EvidenceRef | None = None


class QueryPlanCandidatePayload(BaseModel):
    """Agent-proposed query plan for the next landscape round."""

    model_config = ConfigDict(extra="forbid")

    queries: list[PlannedQuery]
    rationale: str


class ResearchLoopEvent(BaseModel):
    """Append-only audit event for research loop activity."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["gaia.research_loop.event.v1"] = Field(default=EVENT_SCHEMA, alias="schema")
    created_at: str = Field(default_factory=utcnow)
    event_type: str
    stage: Stage | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ResearchLoopState(BaseModel):
    """Rebuildable navigation state for a research loop package."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["gaia.research_loop.state.v1"] = Field(default=STATE_SCHEMA, alias="schema")
    phase: str = "idle"
    latest_task_by_stage: dict[str, str] = Field(default_factory=dict)
    latest_artifact_by_stage: dict[str, str] = Field(default_factory=dict)
    last_validation_error: dict[str, Any] | None = None
