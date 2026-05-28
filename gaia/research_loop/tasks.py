"""Task envelope builders for the Gaia research loop."""

from __future__ import annotations

from pathlib import Path
from shlex import quote
from typing import Any

from gaia.research_loop.schemas import (
    EvidenceRef,
    QueryPlanCandidatePayload,
    ResearchLoopTask,
    ScopeCandidatePayload,
    SearchExecutionCandidatePayload,
    TaskKind,
)
from gaia.research_loop.storage import ResearchLoopPaths, write_json


def _task_path(paths: ResearchLoopPaths, task_id: str) -> Path:
    return paths.explore_tasks / f"{task_id}.json"


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
) -> tuple[ResearchLoopTask, Path]:
    """Build a task asking the agent to plan the next LKM searches."""
    task_id = "task-query-plan-0001"
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        objective="Plan the next LKM searches from the current scope and coverage.",
        inputs={"scope": scope},
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
) -> tuple[ResearchLoopTask, Path]:
    """Build a mechanical task for running planned LKM searches."""
    task_id = "task-search-execution-0001"
    commands: list[dict[str, str]] = []
    for index, item in enumerate(query_plan.get("queries", [])):
        if not isinstance(item, dict):
            continue
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            continue
        output_path = paths.explore_artifacts / f"raw-search-0001-{index}.json"
        command = f"gaia search lkm knowledge {quote(query)} --json > {quote(str(output_path))}"
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
        inputs={"query_plan": query_plan, "commands": commands},
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


def write_task(task: ResearchLoopTask, path: Path) -> None:
    """Write a task envelope to disk."""
    write_json(path, task.model_dump(mode="json", by_alias=True))
