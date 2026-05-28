"""State-machine helpers for the Gaia research loop CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from gaia.research_loop.lkm_adapter import build_landscape_from_raw_results
from gaia.research_loop.schemas import (
    AssessmentContextCandidatePayload,
    CandidateEnvelope,
    EvidenceDiagnosisCandidatePayload,
    FocusSynthesisCandidatePayload,
    QueryPlanCandidatePayload,
    RepairContext,
    ResearchLoopTask,
    ScopeCandidatePayload,
    SearchExecutionCandidatePayload,
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
    build_assessment_context_task,
    build_evidence_diagnosis_task,
    build_focus_synthesis_task,
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
    explore_gate_path = paths.explore_artifacts / "explore_gate.json"
    if _gate_passed(explore_gate_path):
        assessment_context_path = paths.assess_artifacts / "assessment_context.json"
        evidence_diagnosis_path = paths.assess_artifacts / "evidence_diagnosis.json"
        if not assessment_context_path.exists():
            return emit_task(pkg, kind=TaskKind.ASSESSMENT_CONTEXT)
        if not evidence_diagnosis_path.exists():
            return emit_task(pkg, kind=TaskKind.EVIDENCE_DIAGNOSIS)
    scope_path = paths.explore_artifacts / "scope.json"
    query_plan_path = paths.explore_artifacts / "query_plan.json"
    landscape_path = paths.explore_artifacts / "landscape-0000.json"
    focuses_path = paths.explore_artifacts / "focuses.json"
    if not scope_path.exists():
        return emit_task(pkg, kind=TaskKind.SCOPE)
    if not query_plan_path.exists():
        return emit_task(pkg, kind=TaskKind.QUERY_PLAN)
    if landscape_path.exists() and not focuses_path.exists():
        return emit_task(pkg, kind=TaskKind.FOCUS_SYNTHESIS)
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
    elif kind == TaskKind.FOCUS_SYNTHESIS:
        landscape_path = paths.explore_artifacts / "landscape-0000.json"
        if not landscape_path.exists():
            raise FileNotFoundError("landscape-0000.json is required for focus-synthesis task")
        task, task_path = build_focus_synthesis_task(paths, read_json(landscape_path))
    elif kind == TaskKind.ASSESSMENT_CONTEXT:
        focuses_path = paths.explore_artifacts / "focuses.json"
        if not focuses_path.exists():
            raise FileNotFoundError("focuses.json is required for assessment-context task")
        task, task_path = build_assessment_context_task(paths, read_json(focuses_path))
    elif kind == TaskKind.EVIDENCE_DIAGNOSIS:
        context_path = paths.assess_artifacts / "assessment_context.json"
        if not context_path.exists():
            raise FileNotFoundError(
                "assessment_context.json is required for evidence-diagnosis task"
            )
        task, task_path = build_evidence_diagnosis_task(paths, read_json(context_path))
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
    if task.kind == TaskKind.SEARCH_EXECUTION:
        search_payload = SearchExecutionCandidatePayload.model_validate(candidate.payload)
        raw_results: list[tuple[str, Path]] = []
        manifest_results: list[dict[str, str]] = []
        for result in search_payload.results:
            raw_path = Path(result.path)
            if not raw_path.exists():
                raise FileNotFoundError(f"Search result path does not exist: {raw_path}")
            raw_results.append((result.query, raw_path))
            manifest_results.append({"query": result.query, "path": str(raw_path)})
        manifest_path = paths.explore_artifacts / "raw_search_manifest.json"
        write_json(manifest_path, {"results": manifest_results})
        artifact_path = paths.explore_artifacts / "landscape-0000.json"
        landscape = build_landscape_from_raw_results(
            paths.pkg,
            raw_results=raw_results,
            round_number=0,
        )
        write_json(artifact_path, landscape)
        return artifact_path
    if task.kind == TaskKind.FOCUS_SYNTHESIS:
        focus_payload = FocusSynthesisCandidatePayload.model_validate(candidate.payload)
        artifact_path = paths.explore_artifacts / "focuses.json"
        write_json(artifact_path, focus_payload.model_dump(mode="json"))
        return artifact_path
    if task.kind == TaskKind.ASSESSMENT_CONTEXT:
        context_payload = AssessmentContextCandidatePayload.model_validate(candidate.payload)
        artifact_path = paths.assess_artifacts / "assessment_context.json"
        write_json(artifact_path, context_payload.model_dump(mode="json"))
        return artifact_path
    if task.kind == TaskKind.EVIDENCE_DIAGNOSIS:
        diagnosis_payload = EvidenceDiagnosisCandidatePayload.model_validate(candidate.payload)
        artifact_path = paths.assess_artifacts / "evidence_diagnosis.json"
        write_json(artifact_path, diagnosis_payload.model_dump(mode="json"))
        return artifact_path
    raise ValueError(f"No payload validator for {task.kind.value}")


def gate_payload(pkg: str | Path, *, stage: str) -> dict[str, Any]:
    """Run a structural stage gate."""
    paths = ensure_loop_dirs(pkg)
    if stage == "assess":
        return _assess_gate_payload(paths)
    if stage != "explore":
        raise ValueError(f"Unsupported gate stage: {stage}")
    focuses_path = paths.explore_artifacts / "focuses.json"
    if not focuses_path.exists():
        payload = {"schema": "gaia.research_loop.gate.v1", "stage": stage, "status": "revise"}
        write_json(paths.explore_artifacts / "explore_gate.json", payload)
        return payload
    focuses = read_json(focuses_path)
    status = "pass" if _has_selected_ready_focus(focuses) else "revise"
    payload = {"schema": "gaia.research_loop.gate.v1", "stage": stage, "status": status}
    write_json(paths.explore_artifacts / "explore_gate.json", payload)
    return payload


def _assess_gate_payload(paths: ResearchLoopPaths) -> dict[str, Any]:
    diagnosis_path = paths.assess_artifacts / "evidence_diagnosis.json"
    if not diagnosis_path.exists():
        payload = {"schema": "gaia.research_loop.gate.v1", "stage": "assess", "status": "revise"}
        write_json(paths.assess_artifacts / "assess_gate.json", payload)
        return payload
    diagnosis = read_json(diagnosis_path)
    status = "pass" if _diagnosis_is_complete(diagnosis) else "revise"
    payload = {"schema": "gaia.research_loop.gate.v1", "stage": "assess", "status": status}
    write_json(paths.assess_artifacts / "assess_gate.json", payload)
    return payload


def _has_selected_ready_focus(focuses: dict[str, Any]) -> bool:
    selection = focuses.get("selection")
    selected_ids = set()
    if isinstance(selection, dict):
        selected = selection.get("selected_focus_ids", [])
        if isinstance(selected, list):
            selected_ids = {item for item in selected if isinstance(item, str)}
    for focus in focuses.get("focuses", []):
        if not isinstance(focus, dict):
            continue
        if focus.get("focus_id") not in selected_ids:
            continue
        refs = focus.get("evidence_refs", [])
        if focus.get("ready_for_assess") is True and isinstance(refs, list) and refs:
            return True
    return False


def _gate_passed(path: Path) -> bool:
    return path.exists() and read_json(path).get("status") == "pass"


def _diagnosis_is_complete(diagnosis: dict[str, Any]) -> bool:
    evidence_items = diagnosis.get("evidence_items", [])
    limitations = diagnosis.get("limitations", [])
    gaps = diagnosis.get("gap_map", [])
    next_tests = diagnosis.get("next_tests", [])
    if not all(isinstance(value, list) and value for value in [evidence_items, limitations, gaps]):
        return False
    gap_ids = {
        gap.get("gap_id")
        for gap in gaps
        if isinstance(gap, dict) and isinstance(gap.get("gap_id"), str)
    }
    for item in evidence_items:
        if not isinstance(item, dict):
            return False
        refs = item.get("refs")
        if not isinstance(refs, list) or not refs:
            return False
    if not isinstance(next_tests, list) or not next_tests:
        return False
    return all(isinstance(test, dict) and test.get("gap_id") in gap_ids for test in next_tests)


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
