"""Task envelope builders for the Gaia research loop."""

from __future__ import annotations

from pathlib import Path
from shlex import quote
from typing import Any

from gaia.research_loop.schemas import (
    AssessmentContextCandidatePayload,
    EvidenceDiagnosisCandidatePayload,
    EvidenceRef,
    FocusSynthesisCandidatePayload,
    QueryPlanCandidatePayload,
    ResearchLoopTask,
    ScopeCandidatePayload,
    SearchExecutionCandidatePayload,
    TaskKind,
)
from gaia.research_loop.storage import ResearchLoopPaths, write_json


def _task_path(paths: ResearchLoopPaths, task_id: str) -> Path:
    return paths.explore_tasks / f"{task_id}.json"


def _assess_task_path(paths: ResearchLoopPaths, task_id: str) -> Path:
    return paths.assess_tasks / f"{task_id}.json"


def build_scope_task(paths: ResearchLoopPaths) -> tuple[ResearchLoopTask, Path]:
    """Build a task asking the agent to create a structured scope."""
    task_id = "task-scope-0001"
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.SCOPE,
        objective="Turn the seed research question into a structured exploration scope.",
        inputs={"pkg": str(paths.pkg)},
        instructions=[
            "Identify the seed question and any obvious scope dimensions.",
            "Keep this lightweight; do not assess evidence yet.",
        ],
        allowed_actions=["submit_scope", "stop"],
        recommended_action="submit_scope",
        output_contract=ScopeCandidatePayload.model_json_schema(),
        allowed_refs=[],
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "scope",
            "selected_action": "submit_scope",
            "payload": {"seed_question": "example topic", "search_budget": 3},
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def build_query_plan_task(
    paths: ResearchLoopPaths,
    scope: dict[str, Any],
    *,
    round_number: int = 0,
    prior_focus_synthesis: dict[str, Any] | None = None,
) -> tuple[ResearchLoopTask, Path]:
    """Build a task asking the agent to plan the next LKM searches."""
    task_id = f"task-query-plan-{round_number + 1:04d}"
    inputs: dict[str, Any] = {"scope": scope, "round": round_number}
    if prior_focus_synthesis is not None:
        inputs["prior_focus_synthesis"] = prior_focus_synthesis
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        objective="Plan the next LKM searches from the current scope and coverage.",
        inputs=inputs,
        instructions=[
            "Propose a small set of LKM search queries.",
            "Prefer breadth-first coverage over deep paper analysis.",
        ],
        allowed_actions=["submit_query_plan", "stop"],
        recommended_action="submit_query_plan",
        output_contract=QueryPlanCandidatePayload.model_json_schema(),
        allowed_refs=[EvidenceRef(kind="scope", id="scope")],
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "query_plan",
            "selected_action": "submit_query_plan",
            "payload": {
                "queries": [{"query": "example query", "purpose": "cover one evidence family"}],
                "rationale": "Tiny shape example only.",
            },
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def build_search_execution_task(
    paths: ResearchLoopPaths,
    query_plan: dict[str, Any],
    *,
    round_number: int = 0,
) -> tuple[ResearchLoopTask, Path]:
    """Build a mechanical task for running planned LKM searches."""
    task_id = f"task-search-execution-{round_number + 1:04d}"
    commands: list[dict[str, str]] = []
    for index, item in enumerate(query_plan.get("queries", [])):
        if not isinstance(item, dict):
            continue
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            continue
        output_path = paths.explore_artifacts / f"raw-search-{round_number + 1:04d}-{index}.json"
        command = (
            "gaia search lkm knowledge "
            f"{quote(query)} --format gaia-json --out {quote(str(output_path))}"
        )
        commands.append(
            {
                "query": query,
                "command": command,
                "output_path": str(output_path),
            }
        )

    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.SEARCH_EXECUTION,
        objective="Run the planned LKM searches and submit raw JSON result paths.",
        inputs={"query_plan": query_plan, "round": round_number, "commands": commands},
        instructions=[
            "Run each command exactly as written.",
            "Do not summarize or transform the raw LKM JSON.",
            "Submit the output paths after all commands finish.",
        ],
        allowed_actions=["submit_search_results", "stop"],
        recommended_action="submit_search_results",
        output_contract=SearchExecutionCandidatePayload.model_json_schema(),
        allowed_refs=[EvidenceRef(kind="query_plan", id="query_plan")],
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "search_execution",
            "selected_action": "submit_search_results",
            "payload": {"results": [{"query": "example query", "path": "/tmp/raw-search.json"}]},
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def build_focus_synthesis_task(
    paths: ResearchLoopPaths,
    landscape: dict[str, Any],
    *,
    round_number: int = 0,
) -> tuple[ResearchLoopTask, Path]:
    """Build a semantic task for synthesizing assessment focuses."""
    task_id = f"task-focus-synthesis-{round_number + 1:04d}"
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.FOCUS_SYNTHESIS,
        objective="Synthesize assessment focuses from the cumulative landscape through this round.",
        inputs={"landscape": landscape, "round": round_number},
        instructions=[
            "Generate research questions, not paper clusters.",
            "Use the cumulative landscape to preserve cross-round evidence context.",
            "Ground every evidence ref in the allowed refs.",
            "Select ready focuses only when they have enough refs for assessment.",
        ],
        allowed_actions=["submit_focuses", "needs_more_landscape", "stop"],
        recommended_action="submit_focuses",
        output_contract=FocusSynthesisCandidatePayload.model_json_schema(),
        allowed_refs=_paper_refs_from_landscape(landscape),
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "focus_synthesis",
            "selected_action": "submit_focuses",
            "payload": {
                "focuses": [
                    {
                        "focus_id": "focus-example",
                        "research_question": "Example question?",
                        "evidence_refs": [{"kind": "paper", "id": "P1"}],
                    }
                ]
            },
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def build_assessment_context_task(
    paths: ResearchLoopPaths,
    focuses: dict[str, Any],
    *,
    evidence_context: list[dict[str, Any]] | None = None,
) -> tuple[ResearchLoopTask, Path]:
    """Build an assessment-context task from selected Explore focuses."""
    task_id = "task-assessment-context-0001"
    selected_focus = _selected_focus(focuses)
    inputs: dict[str, Any] = {"focus": selected_focus, "focuses": focuses}
    if evidence_context is not None:
        inputs["evidence_context"] = evidence_context
    task = ResearchLoopTask(
        task_id=task_id,
        stage="assess",
        kind=TaskKind.ASSESSMENT_CONTEXT,
        objective="Package the selected focus for evidence diagnosis.",
        inputs=inputs,
        instructions=[
            "Preserve the selected focus id.",
            "Carry forward only evidence refs grounded by the selected focus.",
            "Read evidence_context snippets before assigning support, opposition, or gaps.",
            "Separate supporting refs, opposing refs, known gaps, and assessment mode when known.",
        ],
        allowed_actions=["submit_assessment_context", "stop"],
        recommended_action="submit_assessment_context",
        output_contract=AssessmentContextCandidatePayload.model_json_schema(),
        allowed_refs=_refs_from_focus(selected_focus),
        minimal_example={
            "task_id": task_id,
            "stage": "assess",
            "kind": "assessment_context",
            "selected_action": "submit_assessment_context",
            "payload": {
                "focus_id": "focus-example",
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
                "supporting_refs": [{"kind": "paper", "id": "P1"}],
                "opposing_refs": [],
                "known_gaps": ["Example gap."],
                "assessment_mode": "evidence_diagnosis",
            },
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _assess_task_path(paths, task_id)


def build_evidence_diagnosis_task(
    paths: ResearchLoopPaths,
    assessment_context: dict[str, Any],
    *,
    evidence_context: list[dict[str, Any]] | None = None,
) -> tuple[ResearchLoopTask, Path]:
    """Build an evidence-diagnosis task from an assessment context."""
    task_id = "task-evidence-diagnosis-0001"
    inputs: dict[str, Any] = {"assessment_context": assessment_context}
    if evidence_context is not None:
        inputs["evidence_context"] = evidence_context
    task = ResearchLoopTask(
        task_id=task_id,
        stage="assess",
        kind=TaskKind.EVIDENCE_DIAGNOSIS,
        objective="Diagnose the evidence, tensions, limitations, gaps, and next tests.",
        inputs=inputs,
        instructions=[
            "Ground every evidence item in allowed refs.",
            "Use evidence_context snippets as the primary content to analyze.",
            "Tie each next test to a gap id.",
            "Preserve the assessment context focus id.",
            "When listing a contradiction or tension, link at least two evidence items or claims.",
            "Use limitations, missing_evidence, and confidence_notes "
            "to explain residual uncertainty.",
        ],
        allowed_actions=["submit_evidence_diagnosis", "stop"],
        recommended_action="submit_evidence_diagnosis",
        output_contract=EvidenceDiagnosisCandidatePayload.model_json_schema(),
        allowed_refs=[
            EvidenceRef.model_validate(ref)
            for ref in assessment_context.get("evidence_refs", [])
            if isinstance(ref, dict)
        ],
        minimal_example={
            "task_id": task_id,
            "stage": "assess",
            "kind": "evidence_diagnosis",
            "selected_action": "submit_evidence_diagnosis",
            "payload": {
                "focus_id": "focus-example",
                "evidence_items": [
                    {
                        "id": "e1",
                        "refs": [{"kind": "paper", "id": "P1"}],
                        "summary": "Example evidence item.",
                    }
                ],
                "candidate_claims": [{"id": "c1", "claim": "Example candidate claim."}],
                "limitations": ["Example limitation."],
                "missing_evidence": ["Example missing evidence."],
                "gap_map": [{"gap_id": "g1", "description": "Example gap."}],
                "next_tests": [{"gap_id": "g1", "test": "Example test."}],
                "confidence_notes": ["Example confidence note."],
            },
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _assess_task_path(paths, task_id)


def _paper_refs_from_landscape(landscape: dict[str, Any]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for lead in landscape.get("paper_leads", []):
        if not isinstance(lead, dict):
            continue
        paper_id = lead.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            refs.append(EvidenceRef(kind="paper", id=paper_id))
    return refs


def _selected_focus(focuses: dict[str, Any]) -> dict[str, Any]:
    selected_ids: set[str] = set()
    selection = focuses.get("selection")
    if isinstance(selection, dict):
        selected = selection.get("selected_focus_ids")
        if isinstance(selected, list):
            selected_ids = {item for item in selected if isinstance(item, str)}
    for focus in focuses.get("focuses", []):
        if isinstance(focus, dict) and focus.get("focus_id") in selected_ids:
            return focus
    return {}


def _refs_from_focus(focus: dict[str, Any]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for ref in focus.get("evidence_refs", []):
        if isinstance(ref, dict):
            refs.append(EvidenceRef.model_validate(ref))
    return refs


def write_task(task: ResearchLoopTask, path: Path) -> None:
    """Write a task envelope to disk."""
    write_json(path, task.model_dump(mode="json", by_alias=True))
