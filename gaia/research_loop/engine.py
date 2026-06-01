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
    EvidenceRef,
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
    focuses_path = paths.explore_artifacts / "focuses.json"
    if not _gate_passed(explore_gate_path) and focuses_path.exists():
        gate = gate_payload(pkg, stage="explore")
        if gate.get("status") == "pass":
            return next_payload(pkg)
    if _gate_passed(explore_gate_path):
        assessment_context_path = paths.assess_artifacts / "assessment_context.json"
        evidence_diagnosis_path = paths.assess_artifacts / "evidence_diagnosis.json"
        if not assessment_context_path.exists():
            return emit_task(pkg, kind=TaskKind.ASSESSMENT_CONTEXT)
        if not evidence_diagnosis_path.exists():
            return emit_task(pkg, kind=TaskKind.EVIDENCE_DIAGNOSIS)
        assess_gate_path = paths.assess_artifacts / "assess_gate.json"
        if not _gate_passed(assess_gate_path):
            gate = gate_payload(pkg, stage="assess")
            if gate.get("status") != "pass":
                return emit_task(pkg, kind=TaskKind.EVIDENCE_DIAGNOSIS)
        return _done_payload()
    scope_path = paths.explore_artifacts / "scope.json"
    if not scope_path.exists():
        return emit_task(pkg, kind=TaskKind.SCOPE)
    if not focuses_path.exists():
        kind, round_number = _next_explore_task(paths)
        return emit_task(pkg, kind=kind, round_number=round_number)
    return emit_task(pkg, kind=TaskKind.SEARCH_EXECUTION, round_number=_next_round(paths))


def _done_payload() -> dict[str, Any]:
    return {
        "recommended_action": "done",
        "allowed_actions": ["done", "stop"],
        "rationale": "Explore and Assess gates passed.",
        "task_path": None,
        "submit_command": None,
    }


def emit_task(
    pkg: str | Path, *, kind: TaskKind, round_number: int | None = None
) -> dict[str, Any]:
    """Emit one specific task envelope without consulting the full loop router."""
    paths = ensure_loop_dirs(pkg)
    if kind == TaskKind.SCOPE:
        task, task_path = build_scope_task(paths)
    elif kind == TaskKind.QUERY_PLAN:
        scope_path = paths.explore_artifacts / "scope.json"
        if not scope_path.exists():
            raise FileNotFoundError("scope.json is required for query-plan task")
        selected_round = _next_round(paths) if round_number is None else round_number
        task, task_path = build_query_plan_task(
            paths,
            read_json(scope_path),
            round_number=selected_round,
            prior_focus_synthesis=_latest_focus_synthesis(paths),
        )
    elif kind == TaskKind.SEARCH_EXECUTION:
        selected_round = _latest_query_plan_round(paths) if round_number is None else round_number
        query_plan_path = _query_plan_path(paths, selected_round)
        if not query_plan_path.exists():
            raise FileNotFoundError(f"{query_plan_path.name} is required for search-execution task")
        task, task_path = build_search_execution_task(
            paths,
            read_json(query_plan_path),
            round_number=selected_round,
        )
    elif kind == TaskKind.FOCUS_SYNTHESIS:
        selected_round = _latest_landscape_round(paths) if round_number is None else round_number
        landscape_path = _landscape_path(paths, selected_round)
        if not landscape_path.exists():
            raise FileNotFoundError(f"{landscape_path.name} is required for focus-synthesis task")
        task, task_path = build_focus_synthesis_task(
            paths,
            _cumulative_landscape(paths, selected_round),
            round_number=selected_round,
        )
    elif kind == TaskKind.ASSESSMENT_CONTEXT:
        focuses_path = paths.explore_artifacts / "focuses.json"
        if not focuses_path.exists():
            raise FileNotFoundError("focuses.json is required for assessment-context task")
        focuses = read_json(focuses_path)
        task, task_path = build_assessment_context_task(
            paths,
            focuses,
            evidence_context=_evidence_context_for_focuses(paths, focuses),
        )
    elif kind == TaskKind.EVIDENCE_DIAGNOSIS:
        context_path = paths.assess_artifacts / "assessment_context.json"
        if not context_path.exists():
            raise FileNotFoundError(
                "assessment_context.json is required for evidence-diagnosis task"
            )
        assessment_context = read_json(context_path)
        task, task_path = build_evidence_diagnosis_task(
            paths,
            assessment_context,
            evidence_context=_evidence_context_for_refs(
                paths,
                assessment_context.get("evidence_refs", []),
            ),
        )
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
        _ensure_refs_allowed(
            task,
            [query.source_ref for query in query_payload.queries if query.source_ref is not None],
        )
        round_number = _round_from_task_id(task.task_id)
        artifact_path = _query_plan_write_path(paths, round_number)
        payload = query_payload.model_dump(mode="json")
        write_json(artifact_path, payload)
        write_json(paths.explore_artifacts / "query_plan.json", payload)
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
        round_number = _round_from_task_id(task.task_id)
        manifest_path = paths.explore_artifacts / f"raw_search_manifest-{round_number:04d}.json"
        write_json(manifest_path, {"results": manifest_results})
        write_json(
            paths.explore_artifacts / "raw_search_manifest.json", {"results": manifest_results}
        )
        artifact_path = _landscape_path(paths, round_number)
        landscape = build_landscape_from_raw_results(
            paths.pkg,
            raw_results=raw_results,
            round_number=round_number,
        )
        write_json(artifact_path, landscape)
        return artifact_path
    if task.kind == TaskKind.FOCUS_SYNTHESIS:
        focus_payload = FocusSynthesisCandidatePayload.model_validate(candidate.payload)
        _ensure_refs_allowed(
            task,
            [ref for focus in focus_payload.focuses for ref in focus.evidence_refs],
        )
        round_number = _round_from_task_id(task.task_id)
        payload = focus_payload.model_dump(mode="json")
        round_path = paths.explore_artifacts / f"focus_synthesis-{round_number:04d}.json"
        write_json(round_path, payload)
        if candidate.selected_action == "needs_more_landscape":
            artifact_path = paths.explore_artifacts / "explore_decision.json"
            write_json(
                artifact_path,
                {
                    "schema": "gaia.research_loop.artifact.v1",
                    "stage": "explore",
                    "action": "needs_more_landscape",
                    "round": round_number,
                    "next_round": round_number + 1,
                    "focus_synthesis_path": str(round_path),
                    "continue_rationale": focus_payload.continue_rationale,
                    "next_queries": [
                        query.model_dump(mode="json") for query in focus_payload.next_queries
                    ],
                },
            )
            return artifact_path
        artifact_path = paths.explore_artifacts / "focuses.json"
        write_json(artifact_path, payload)
        write_json(
            paths.explore_artifacts / "explore_decision.json",
            {
                "schema": "gaia.research_loop.artifact.v1",
                "stage": "explore",
                "action": "submit_focuses",
                "round": round_number,
                "focuses_path": str(artifact_path),
            },
        )
        return artifact_path
    if task.kind == TaskKind.ASSESSMENT_CONTEXT:
        context_payload = AssessmentContextCandidatePayload.model_validate(candidate.payload)
        _ensure_refs_allowed(
            task,
            [
                *context_payload.evidence_refs,
                *context_payload.supporting_refs,
                *context_payload.opposing_refs,
            ],
        )
        artifact_path = paths.assess_artifacts / "assessment_context.json"
        write_json(artifact_path, context_payload.model_dump(mode="json"))
        return artifact_path
    if task.kind == TaskKind.EVIDENCE_DIAGNOSIS:
        diagnosis_payload = EvidenceDiagnosisCandidatePayload.model_validate(candidate.payload)
        _ensure_refs_allowed(
            task,
            [ref for item in diagnosis_payload.evidence_items for ref in item.refs],
        )
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
    context_path = paths.assess_artifacts / "assessment_context.json"
    context = read_json(context_path) if context_path.exists() else None
    status = "pass" if _diagnosis_is_complete(diagnosis, context=context) else "revise"
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


def _diagnosis_is_complete(
    diagnosis: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> bool:
    if context is not None and diagnosis.get("focus_id") != context.get("focus_id"):
        return False
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
    if not _tensions_are_linked(diagnosis.get("contradictions_or_tensions", [])):
        return False
    if not isinstance(next_tests, list) or not next_tests:
        return False
    return all(isinstance(test, dict) and test.get("gap_id") in gap_ids for test in next_tests)


def _tensions_are_linked(tensions: Any) -> bool:
    if not isinstance(tensions, list):
        return False
    for tension in tensions:
        if not isinstance(tension, dict):
            return False
        linked: set[str] = set()
        for field in ["evidence_item_ids", "evidence_ids", "claim_ids", "refs"]:
            value = tension.get(field, [])
            if isinstance(value, list):
                linked.update(str(item) for item in value)
        if len(linked) < 2:
            return False
    return True


def _ensure_refs_allowed(task: ResearchLoopTask, refs: list[EvidenceRef]) -> None:
    allowed = {(ref.kind, ref.id) for ref in task.allowed_refs}
    for ref in refs:
        if (ref.kind, ref.id) not in allowed:
            raise ValueError(f"Reference {ref.kind}:{ref.id} is not allowed by task")


def _next_explore_task(paths: ResearchLoopPaths) -> tuple[TaskKind, int]:
    latest_query = _latest_round(paths, "query_plan")
    latest_landscape = _latest_round(paths, "landscape")
    latest_focus = _latest_round(paths, "focus_synthesis")
    if latest_query is None:
        return TaskKind.QUERY_PLAN, 0
    if latest_landscape is None or latest_query > latest_landscape:
        return TaskKind.SEARCH_EXECUTION, latest_query
    if latest_focus is None or latest_landscape > latest_focus:
        return TaskKind.FOCUS_SYNTHESIS, latest_landscape
    decision_path = paths.explore_artifacts / "explore_decision.json"
    if decision_path.exists():
        decision = read_json(decision_path)
        if decision.get("action") == "needs_more_landscape":
            next_round = int(decision.get("next_round", latest_landscape + 1))
            if latest_query < next_round:
                return TaskKind.QUERY_PLAN, next_round
            if latest_landscape < next_round:
                return TaskKind.SEARCH_EXECUTION, next_round
            return TaskKind.FOCUS_SYNTHESIS, next_round
    return TaskKind.FOCUS_SYNTHESIS, latest_landscape


def _next_round(paths: ResearchLoopPaths) -> int:
    latest_landscape = _latest_landscape_round(paths)
    decision_path = paths.explore_artifacts / "explore_decision.json"
    if decision_path.exists():
        decision = read_json(decision_path)
        if decision.get("action") == "needs_more_landscape":
            return int(decision.get("next_round", latest_landscape + 1))
    return 0 if latest_landscape < 0 else latest_landscape + 1


def _latest_query_plan_round(paths: ResearchLoopPaths) -> int:
    return _latest_round(paths, "query_plan") or 0


def _latest_landscape_round(paths: ResearchLoopPaths) -> int:
    latest = _latest_round(paths, "landscape")
    return -1 if latest is None else latest


def _latest_focus_synthesis(paths: ResearchLoopPaths) -> dict[str, Any] | None:
    latest = _latest_round(paths, "focus_synthesis")
    if latest is None:
        return None
    return read_json(paths.explore_artifacts / f"focus_synthesis-{latest:04d}.json")


def _query_plan_path(paths: ResearchLoopPaths, round_number: int) -> Path:
    numbered = paths.explore_artifacts / f"query_plan-{round_number:04d}.json"
    if numbered.exists() or round_number != 0:
        return numbered
    return paths.explore_artifacts / "query_plan.json"


def _query_plan_write_path(paths: ResearchLoopPaths, round_number: int) -> Path:
    return paths.explore_artifacts / f"query_plan-{round_number:04d}.json"


def _landscape_path(paths: ResearchLoopPaths, round_number: int) -> Path:
    return paths.explore_artifacts / f"landscape-{round_number:04d}.json"


def _cumulative_landscape(paths: ResearchLoopPaths, round_number: int) -> dict[str, Any]:
    landscape = dict(read_json(_landscape_path(paths, round_number)))
    paper_leads: list[dict[str, Any]] = []
    claim_leads: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    evidence_snippets: list[dict[str, Any]] = []
    seen_papers: set[str] = set()
    seen_claims: set[str] = set()
    seen_snippets: set[str] = set()
    source_rounds: list[int] = []
    for current_round in range(round_number + 1):
        path = _landscape_path(paths, current_round)
        if not path.exists():
            continue
        source_rounds.append(current_round)
        current = read_json(path)
        _append_unique_leads(
            paper_leads,
            current.get("paper_leads", []),
            id_field="paper_id",
            seen=seen_papers,
        )
        _append_unique_leads(
            claim_leads,
            current.get("claim_leads", []),
            id_field="claim_id",
            seen=seen_claims,
            fallback_id_field="id",
        )
        raw_results.extend(
            raw_result
            for raw_result in current.get("raw_results", [])
            if isinstance(raw_result, dict)
        )
        _append_unique_snippets(
            evidence_snippets, current.get("evidence_snippets", []), seen_snippets
        )
    landscape["paper_leads"] = paper_leads
    landscape["claim_leads"] = claim_leads
    landscape["raw_results"] = raw_results
    landscape["evidence_snippets"] = evidence_snippets
    landscape["source_landscape_rounds"] = source_rounds
    return landscape


def _append_unique_leads(
    target: list[dict[str, Any]],
    source: Any,
    *,
    id_field: str,
    seen: set[str],
    fallback_id_field: str | None = None,
) -> None:
    if not isinstance(source, list):
        return
    for lead in source:
        if not isinstance(lead, dict):
            continue
        lead_id = lead.get(id_field)
        if not isinstance(lead_id, str) and fallback_id_field is not None:
            lead_id = lead.get(fallback_id_field)
        if not isinstance(lead_id, str) or lead_id in seen:
            continue
        seen.add(lead_id)
        target.append(lead)


def _append_unique_snippets(
    target: list[dict[str, Any]],
    source: Any,
    seen: set[str],
) -> None:
    if not isinstance(source, list):
        return
    for snippet in source:
        if not isinstance(snippet, dict):
            continue
        snippet_key = _snippet_key(snippet)
        if snippet_key in seen:
            continue
        seen.add(snippet_key)
        target.append(snippet)


def _evidence_context_for_focuses(
    paths: ResearchLoopPaths,
    focuses: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_focus = _selected_focus_from_focuses(focuses)
    return _evidence_context_for_refs(paths, selected_focus.get("evidence_refs", []))


def _selected_focus_from_focuses(focuses: dict[str, Any]) -> dict[str, Any]:
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


def _evidence_context_for_refs(
    paths: ResearchLoopPaths,
    refs: Any,
) -> list[dict[str, Any]]:
    paper_ids = {
        ref.get("id")
        for ref in refs
        if isinstance(ref, dict) and ref.get("kind") == "paper" and isinstance(ref.get("id"), str)
    }
    if not paper_ids:
        return []
    context: list[dict[str, Any]] = []
    seen: set[str] = set()
    latest = _latest_landscape_round(paths)
    if latest < 0:
        return context
    for round_number in range(latest + 1):
        path = _landscape_path(paths, round_number)
        if not path.exists():
            continue
        landscape = read_json(path)
        for snippet in landscape.get("evidence_snippets", []):
            if not isinstance(snippet, dict) or snippet.get("paper_id") not in paper_ids:
                continue
            snippet_key = _snippet_key(snippet)
            if snippet_key in seen:
                continue
            seen.add(snippet_key)
            context.append(snippet)
    return context


def _snippet_key(snippet: dict[str, Any]) -> str:
    node_id = snippet.get("lkm_node_id")
    if isinstance(node_id, str) and node_id:
        return node_id
    return f"{snippet.get('paper_id')}::{snippet.get('content')}"


def _latest_round(paths: ResearchLoopPaths, prefix: str) -> int | None:
    rounds: list[int] = []
    for path in paths.explore_artifacts.glob(f"{prefix}-[0-9][0-9][0-9][0-9].json"):
        try:
            rounds.append(int(path.stem.rsplit("-", maxsplit=1)[1]))
        except (IndexError, ValueError):
            continue
    if (
        prefix == "query_plan"
        and not rounds
        and (paths.explore_artifacts / "query_plan.json").exists()
    ):
        rounds.append(0)
    return max(rounds) if rounds else None


def _round_from_task_id(task_id: str) -> int:
    try:
        return int(task_id.rsplit("-", maxsplit=1)[1]) - 1
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Task id does not include a round ordinal: {task_id}") from exc


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
