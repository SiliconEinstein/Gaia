"""State-machine helpers for the Gaia research loop CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia.research_loop.schemas import TaskKind
from gaia.research_loop.storage import (
    append_event,
    ensure_loop_dirs,
    load_events,
    read_json,
    rebuild_state,
)
from gaia.research_loop.tasks import build_query_plan_task, build_scope_task, write_task


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
    scope_path = paths.explore_artifacts / "scope.json"
    if scope_path.exists():
        return emit_task(pkg, kind=TaskKind.QUERY_PLAN)
    return emit_task(pkg, kind=TaskKind.SCOPE)


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
