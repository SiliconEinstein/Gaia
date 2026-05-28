"""State-machine helpers for the Gaia research loop CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from gaia.research_loop.schemas import (
    CandidateEnvelope,
    QueryPlanCandidatePayload,
    RepairContext,
    ResearchLoopTask,
    ScopeCandidatePayload,
    TaskKind,
)
from gaia.research_loop.storage import (
    ResearchLoopPaths,
    append_event,
    candidate_destination,
    ensure_loop_dirs,
    find_task,
    load_events,
    load_state,
    read_json,
    rebuild_state,
    write_json,
)
from gaia.research_loop.tasks import (
    build_query_plan_task,
    build_scope_task,
    build_search_execution_task,
    write_task,
)


def status_payload(pkg: str | Path) -> dict[str, Any]:
    """Return a JSON-compatible research-loop status payload."""
    paths = ensure_loop_dirs(pkg)
    state = rebuild_state(paths)
    events = load_events(paths)
    return {
        "schema": state.schema_id,
        "phase": state.phase,
        "root": str(paths.root),
        "latest_task_by_stage": state.latest_task_by_stage,
        "latest_artifact_by_stage": state.latest_artifact_by_stage,
        "event_count": len(events),
        "recommended_next": "gaia-research-loop next",
    }


def next_payload(pkg: str | Path) -> dict[str, Any]:
    """Emit the next recommended task envelope."""
    paths = ensure_loop_dirs(pkg)
    state = load_state(paths)
    if state.last_validation_error is not None:
        return _repair_task_payload(paths, state.last_validation_error)
    scope_path = paths.explore_artifacts / "scope.json"
    query_plan_path = paths.explore_artifacts / "query_plan.json"
    if not scope_path.exists():
        return emit_task(pkg, kind=TaskKind.SCOPE)
    if not query_plan_path.exists():
        return emit_task(pkg, kind=TaskKind.QUERY_PLAN)
    return emit_task(pkg, kind=TaskKind.SEARCH_EXECUTION)


def emit_task(pkg: str | Path, *, kind: TaskKind) -> dict[str, Any]:
    """Emit one specific task envelope without consulting the full loop router."""
    paths = ensure_loop_dirs(pkg)
    if kind == TaskKind.SCOPE:
        task, task_path = build_scope_task(paths)
    elif kind == TaskKind.QUERY_PLAN:
        scope_path = paths.explore_artifacts / "scope.json"
        if not scope_path.exists():
            raise FileNotFoundError("scope.json is required for query-plan task")
        task, task_path = build_query_plan_task(paths, read_json(scope_path))
    elif kind == TaskKind.SEARCH_EXECUTION:
        query_plan_path = paths.explore_artifacts / "query_plan.json"
        if not query_plan_path.exists():
            raise FileNotFoundError("query_plan.json is required for search-execution task")
        task, task_path = build_search_execution_task(paths, read_json(query_plan_path))
    else:
        raise ValueError(f"Primitive task {kind.value} is not implemented yet")
    write_task(task, task_path)
    append_event(
        paths,
        event_type="task_emitted",
        stage=task.stage,
        data={"task_id": task.task_id, "kind": task.kind.value, "task_path": str(task_path)},
    )
    rebuild_state(paths)
    return {
        "recommended_action": task.recommended_action,
        "allowed_actions": task.allowed_actions,
        "task_path": str(task_path),
        "submit_command": task.submit_command,
        "rationale": task.objective,
    }


def submit_candidate(pkg: str | Path, candidate_path: str | Path) -> dict[str, Any]:
    """Validate a candidate JSON file and persist the accepted artifact."""
    paths = ensure_loop_dirs(pkg)
    source_path = Path(candidate_path).resolve()
    try:
        candidate = CandidateEnvelope.model_validate_json(source_path.read_text(encoding="utf-8"))
        task_path = find_task(paths, candidate.task_id)
        task = ResearchLoopTask.model_validate_json(task_path.read_text(encoding="utf-8"))
        if candidate.stage != task.stage or candidate.kind != task.kind:
            raise ValueError("candidate stage/kind does not match task")
        candidate.validate_against_actions(
            recommended_action=task.recommended_action,
            allowed_actions=task.allowed_actions,
        )
        artifact_path = _write_candidate_artifact(paths, task, candidate)
    except (ValidationError, ValueError, FileNotFoundError, OSError) as exc:
        errors: list[dict[str, Any]] = (
            [dict(error) for error in exc.errors()]
            if isinstance(exc, ValidationError)
            else [{"msg": str(exc)}]
        )
        _record_validation_failure(paths, source_path, errors)
        raise

    copied_candidate = candidate_destination(paths, candidate.stage, source_path)
    write_json(copied_candidate, candidate.model_dump(mode="json", by_alias=True))
    append_event(
        paths,
        event_type="candidate_submitted",
        stage=candidate.stage,
        data={"task_id": candidate.task_id, "candidate_path": str(copied_candidate)},
    )
    rebuild_state(paths)
    return {"status": "accepted", "artifact_path": str(artifact_path)}


def _write_candidate_artifact(
    paths: ResearchLoopPaths,
    task: ResearchLoopTask,
    candidate: CandidateEnvelope,
) -> Path:
    if task.kind == TaskKind.SCOPE:
        scope_payload = ScopeCandidatePayload.model_validate(candidate.payload)
        artifact_path = paths.explore_artifacts / "scope.json"
        write_json(artifact_path, scope_payload.model_dump(mode="json"))
        return artifact_path
    if task.kind == TaskKind.QUERY_PLAN:
        query_payload = QueryPlanCandidatePayload.model_validate(candidate.payload)
        artifact_path = paths.explore_artifacts / "query_plan.json"
        write_json(artifact_path, query_payload.model_dump(mode="json"))
        return artifact_path
    raise ValueError(f"No payload validator for {task.kind.value}")


def _record_validation_failure(
    paths: ResearchLoopPaths,
    failed_candidate_path: Path,
    errors: list[dict[str, Any]],
) -> None:
    state = rebuild_state(paths)
    state.last_validation_error = {
        "failed_candidate_path": str(failed_candidate_path),
        "errors": errors,
        "instruction": "Repair the candidate JSON so it satisfies the same task contract.",
    }
    write_json(paths.state, state.model_dump(mode="json", by_alias=True))
    append_event(
        paths,
        event_type="validation_failed",
        stage=None,
        data=state.last_validation_error,
    )


def _repair_task_payload(
    paths: ResearchLoopPaths,
    validation_error: dict[str, Any],
) -> dict[str, Any]:
    failed_path = Path(str(validation_error["failed_candidate_path"]))
    candidate = CandidateEnvelope.model_validate_json(failed_path.read_text(encoding="utf-8"))
    task_path = find_task(paths, candidate.task_id)
    task = ResearchLoopTask.model_validate_json(task_path.read_text(encoding="utf-8"))
    errors = validation_error.get("errors", [])
    task.repair_context = RepairContext(
        failed_candidate_path=str(failed_path),
        errors=errors if isinstance(errors, list) else [{"msg": str(errors)}],
        instruction=str(validation_error["instruction"]),
    )
    write_task(task, task_path)
    return {
        "recommended_action": task.recommended_action,
        "allowed_actions": task.allowed_actions,
        "task_path": str(task_path),
        "submit_command": task.submit_command,
        "rationale": task.objective,
    }
