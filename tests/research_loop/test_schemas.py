from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaia.research_loop.schemas import (
    CandidateEnvelope,
    EvidenceRef,
    ResearchLoopTask,
    TaskKind,
)


def test_task_embeds_contract_and_minimal_example() -> None:
    task = ResearchLoopTask(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        objective="Plan the next LKM searches.",
        inputs={"scope": {"seed": "aspirin primary prevention"}},
        instructions=["Return two focused queries."],
        allowed_actions=["submit_query_plan", "stop"],
        recommended_action="submit_query_plan",
        output_contract={"type": "object", "required": ["queries"]},
        allowed_refs=[EvidenceRef(kind="scope", id="scope-1")],
        minimal_example={"queries": [{"query": "example query", "purpose": "shape only"}]},
        submit_command="gaia-research-loop submit /tmp/pkg candidate.json",
    )

    assert task.model_dump(by_alias=True)["schema"] == "gaia.research_loop.task.v1"
    assert task.stage == "explore"
    assert task.kind == TaskKind.QUERY_PLAN
    assert task.repair_context is None


def test_candidate_selected_action_must_be_allowed_or_recommended() -> None:
    candidate = CandidateEnvelope(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        selected_action="stop",
        override_rationale="Budget exhausted.",
        payload={"reason": "No more searches."},
    )

    candidate.validate_against_actions(
        recommended_action="submit_query_plan",
        allowed_actions=["submit_query_plan", "stop"],
    )


def test_candidate_override_requires_rationale() -> None:
    candidate = CandidateEnvelope(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        selected_action="stop",
        payload={"reason": "No more searches."},
    )

    with pytest.raises(ValueError, match="override_rationale"):
        candidate.validate_against_actions(
            recommended_action="submit_query_plan",
            allowed_actions=["submit_query_plan", "stop"],
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ResearchLoopTask.model_validate(
            {
                "task_id": "task-query-plan-1",
                "stage": "explore",
                "kind": TaskKind.QUERY_PLAN,
                "objective": "Plan.",
                "inputs": {},
                "instructions": [],
                "allowed_actions": ["submit_query_plan"],
                "recommended_action": "submit_query_plan",
                "output_contract": {},
                "allowed_refs": [],
                "minimal_example": {},
                "submit_command": "gaia-research-loop submit /tmp/pkg candidate.json",
                "unexpected": True,
            }
        )
