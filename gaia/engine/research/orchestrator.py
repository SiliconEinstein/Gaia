"""Engine-level fixed workflow orchestration for research runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from gaia.engine.research import (
    AssessmentSchemaError,
    ResearchOrchestratorError,
    ResearchOrchestratorRuntime,
    ResearchPackage,
    ScanBatch,
    build_assessment_from_analysis,
    build_field_map_artifact,
    build_focus_synthesis_artifact,
    build_research_landscape,
    build_selected_evidence_artifact,
    evaluate_research_stop,
    render_final_research_report_markdown,
    research_contract,
)
from gaia.engine.research.run import ResearchRunStart


def _read_trace_records(trace_dir: Path) -> list[dict[str, object]]:
    trace_path = trace_dir / "trace.jsonl"
    if not trace_path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _collect_trace_json_artifacts(
    trace_dir: Path,
    *,
    kind: str,
) -> list[tuple[Path, dict[str, object]]]:
    artifacts: list[tuple[Path, dict[str, object]]] = []
    seen: set[Path] = set()
    for record in _read_trace_records(trace_dir):
        outputs = record.get("outputs")
        if not isinstance(outputs, list):
            continue
        for output in outputs:
            if not isinstance(output, str) or not output.endswith(".json"):
                continue
            path = Path(output)
            if not path.is_absolute():
                path = trace_dir / path
            if path in seen or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("kind") == kind:
                seen.add(path)
                artifacts.append((path, payload))
    return artifacts


def _latest_landscape_paths(pkg: ResearchPackage) -> list[Path]:
    landscape_dir = pkg.path / ".gaia" / "research" / "landscapes"
    if not landscape_dir.exists():
        return []
    paths = sorted(landscape_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)
    return paths[-1:] if paths else []


def _all_landscape_paths(pkg: ResearchPackage) -> list[Path]:
    landscape_dir = pkg.path / ".gaia" / "research" / "landscapes"
    if not landscape_dir.exists():
        return []
    return sorted(landscape_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)


def _scan_batches(
    refs: list[str],
    *,
    queries: list[str],
    sources: list[str],
    runtime: ResearchOrchestratorRuntime,
) -> list[ScanBatch]:
    batches: list[ScanBatch] = []
    for index, ref in enumerate(refs):
        payload, path_label = runtime.read_search_json(ref)
        batches.append(
            ScanBatch(
                search_results=payload,
                query=queries[index] if index < len(queries) else None,
                source_qid=sources[index] if index < len(sources) else None,
                path=path_label,
            )
        )
    return batches


def _relation_type_counts(relations: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(relations, list):
        return counts
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("type")
        if isinstance(relation_type, str) and relation_type:
            counts[relation_type] = counts.get(relation_type, 0) + 1
    return counts


def _count_payload_items(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else 0


def _research_mode(
    *,
    deep_materialization: bool = False,
) -> str:
    if deep_materialization:
        return "deep"
    return "fast_package_native"


def auto_plan_broad_queries_if_needed(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    profile: str,
    analysis_provider: str,
    model: str | None,
    existing_search_refs: list[str],
    existing_queries: list[str],
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> list[str]:
    """Run the query-plan provider when the run has no fixed broad inputs."""
    if existing_search_refs or existing_queries or analysis_provider != "litellm":
        return existing_queries
    resolved_model = runtime.resolve_litellm_model(model)
    query_plan_json = runtime.run_litellm_provider(
        research_pkg,
        run,
        phase="query_plan",
        model=resolved_model,
        input_payload=_query_plan_provider_input(
            topic=topic,
            language=language,
            profile=profile,
        ),
        output_name="query_plan",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    return _queries_from_query_plan(
        runtime.read_json_object_ref(query_plan_json, label="query-plan JSON")
    )


def _write_run_checkpoint(
    run: ResearchRunStart,
    *,
    phase: str,
    checkpoint_type: str,
    prompt: str,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> None:
    checkpoint_path = run.run_dir / "checkpoints" / f"{phase}.request.json"
    checkpoint = {
        "schema_version": 1,
        "type": checkpoint_type,
        "checkpoint_id": f"{phase}_001",
        "phase": phase,
        "prompt": prompt,
        "choices": [{"id": "continue", "label": "Continue when input is available"}],
        "default_action": {"action": "wait"},
    }
    runtime.write_json_file(checkpoint_path, checkpoint)
    runtime.update_run_state(
        run,
        {
            "status": "waiting_for_input",
            "phase": phase,
            "pending_checkpoint": str(checkpoint_path),
        },
    )
    runtime.emit_run_event(
        run,
        event_type="checkpoint.created",
        phase=phase,
        json_stream=json_stream,
        payload={"path": str(checkpoint_path), "checkpoint_type": checkpoint_type},
    )
    runtime.emit_run_event(
        run,
        event_type="run.waiting_for_input",
        phase=phase,
        json_stream=json_stream,
        payload={"pending_checkpoint": str(checkpoint_path)},
    )


def execute_live_searches(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    queries: list[str],
    prefix: str,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> list[str]:
    """Execute live LKM searches and persist normalized run-local results."""
    refs: list[str] = []
    searches_dir = run.run_dir / "searches"
    searches_dir.mkdir(parents=True, exist_ok=True)
    for index, query_text in enumerate(queries, start=1):
        output_path = searches_dir / f"{prefix}-{index:02d}.json"
        runtime.emit_run_event(
            run,
            event_type="search.started",
            phase="live_search",
            json_stream=json_stream,
            payload={"query": query_text, "output": str(output_path), "prefix": prefix},
        )
        start = perf_counter()
        try:
            payload = runtime.search_lkm(
                query_text,
                index=search_index,
                limit=search_limit,
                reasoning_only=reasoning_only,
            )
        except ResearchOrchestratorError:
            raise
        except Exception as exc:
            runtime.record_trace(
                research_pkg,
                run,
                start=start,
                name=f"search.lkm.{prefix}",
                kind="search",
                mode="lkm",
                inputs=[query_text],
                outputs=[],
                metrics={
                    "query": query_text,
                    "index": search_index,
                    "limit": search_limit,
                    "reasoning_only": reasoning_only,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                status="failed",
            )
            runtime.update_run_state(
                run,
                {
                    "status": "failed",
                    "phase": "live_search",
                    "error": str(exc),
                },
            )
            runtime.emit_run_event(
                run,
                event_type="run.failed",
                phase="live_search",
                json_stream=json_stream,
                payload={"query": query_text, "error": str(exc)},
            )
            raise ResearchOrchestratorError(
                f"live LKM search failed for {query_text!r}: {exc}"
            ) from exc
        runtime.write_json_file(output_path, payload)
        refs.append(str(output_path))
        results = payload.get("results")
        runtime.record_trace(
            research_pkg,
            run,
            start=start,
            name=f"search.lkm.{prefix}",
            kind="search",
            mode="lkm",
            inputs=[query_text],
            outputs=[str(output_path)],
            metrics={
                "query": query_text,
                "index": search_index,
                "limit": search_limit,
                "reasoning_only": reasoning_only,
                "results": len(results) if isinstance(results, list) else 0,
            },
        )
        runtime.emit_run_event(
            run,
            event_type="search.completed",
            phase="live_search",
            json_stream=json_stream,
            payload={
                "query": query_text,
                "output": str(output_path),
                "results": len(results) if isinstance(results, list) else 0,
            },
        )
    return refs


def _query_plan_provider_input(
    *,
    topic: str,
    language: str,
    profile: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "type": "gaia.research.query_plan_request",
        "phase": "query_plan",
        "topic": topic,
        "language": language,
        "profile": profile,
        "contract": {
            "required_top_level_keys": ["queries"],
            "queries": (
                "Return 3-5 broad live-search queries as strings or objects with "
                "`query` and optional `rationale`. Cover the evidence families, "
                "foundational theory, canonical models, diagnostics, experiments, "
                "and controversy axes needed for an autonomous review map."
            ),
        },
    }


def _queries_from_query_plan(payload: dict[str, object]) -> list[str]:
    raw_queries = payload.get("queries") or payload.get("broad_queries")
    if not isinstance(raw_queries, list):
        raise ResearchOrchestratorError("query_plan output must contain a `queries` list.")
    queries: list[str] = []
    seen: set[str] = set()
    for item in raw_queries:
        if isinstance(item, str):
            query = item
        elif isinstance(item, dict):
            raw = item.get("query") or item.get("text")
            query = raw if isinstance(raw, str) else ""
        else:
            query = ""
        normalized = " ".join(query.split())
        if normalized and normalized not in seen:
            queries.append(normalized)
            seen.add(normalized)
    if not queries:
        raise ResearchOrchestratorError("query_plan output did not contain any non-empty queries.")
    return queries


def _coverage_queries_from_field_map(
    field_map_artifact: dict[str, object],
    *,
    limit: int = 4,
) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for item in _field_map_coverage_query_candidates(field_map_artifact):
        _append_unique_query(queries, seen, item, limit=limit)
        if len(queries) >= limit:
            break
    return queries


def _field_map_coverage_query_candidates(
    field_map_artifact: dict[str, object],
) -> list[object]:
    candidates: list[object] = []
    statuses = {"missing", "thin", "partial"}

    buckets = field_map_artifact.get("buckets")
    if isinstance(buckets, list):
        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            required = bucket.get("required_for_review")
            status = bucket.get("coverage_status")
            if required is False or str(status) not in statuses:
                continue
            candidates.extend(_list_or_empty(bucket.get("recommended_queries")))

    gaps = field_map_artifact.get("coverage_gaps")
    if isinstance(gaps, list):
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            candidates.extend(_list_or_empty(gap.get("recommended_queries")))

    candidates.extend(_list_or_empty(field_map_artifact.get("recommended_expansions")))
    return candidates


def _append_unique_query(
    queries: list[str],
    seen: set[str],
    item: object,
    *,
    limit: int,
) -> None:
    if len(queries) >= limit:
        return
    query = _query_text(item)
    if query is None:
        return
    normalized = " ".join(query.split())
    if normalized and normalized not in seen:
        queries.append(normalized)
        seen.add(normalized)


def _list_or_empty(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _suggested_queries_for_focus(
    focus_artifact: dict[str, object],
    selected_focus: object,
) -> list[str]:
    selected_id = str(selected_focus)
    queries: list[str] = []
    seen: set[str] = set()

    focuses = focus_artifact.get("focuses")
    if isinstance(focuses, list):
        for focus_item in focuses:
            if not isinstance(focus_item, dict):
                continue
            if str(focus_item.get("id")) != selected_id:
                continue
            _extend_unique_queries(queries, seen, focus_item.get("suggested_queries"))

    coverage_gaps = focus_artifact.get("coverage_gaps")
    if isinstance(coverage_gaps, list):
        for gap in coverage_gaps:
            if isinstance(gap, dict):
                _extend_unique_queries(queries, seen, gap.get("suggested_queries"))
    return queries


def _extend_unique_queries(
    queries: list[str],
    seen: set[str],
    suggested: object,
) -> None:
    if not isinstance(suggested, list):
        return
    for item in suggested:
        value = _query_text(item)
        if value is None:
            continue
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            queries.append(normalized)
            seen.add(normalized)


def _query_text(item: object) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    raw = item.get("query") or item.get("text")
    return raw if isinstance(raw, str) else None


def _normalized_query_key(query: str) -> str:
    return " ".join(query.casefold().split())


def _previous_search_queries(run: ResearchRunStart) -> set[str]:
    queries: set[str] = set()
    for record in _read_trace_records(run.run_dir / "trace"):
        if record.get("kind") != "search":
            continue
        metrics = record.get("metrics")
        query = metrics.get("query") if isinstance(metrics, dict) else None
        if isinstance(query, str) and query.strip():
            queries.add(_normalized_query_key(query))
            continue
        inputs = record.get("inputs")
        if isinstance(inputs, list):
            for item in inputs:
                if isinstance(item, str) and item.strip():
                    queries.add(_normalized_query_key(item))
    return queries


def _filter_new_queries(
    queries: list[str],
    *,
    previous_queries: set[str],
) -> list[str]:
    filtered: list[str] = []
    seen = set(previous_queries)
    for query in queries:
        key = _normalized_query_key(query)
        if not key or key in seen:
            continue
        filtered.append(query)
        seen.add(key)
    return filtered


def _targeted_searches_after_focus(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    focus_artifact: dict[str, object],
    selected_focus: object,
    targeted_search_json: list[str],
    targeted_query: list[str],
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> tuple[list[str], list[str]]:
    if targeted_search_json:
        return targeted_search_json, targeted_query
    queries = targeted_query or _suggested_queries_for_focus(focus_artifact, selected_focus)
    queries = _filter_new_queries(
        queries,
        previous_queries=_previous_search_queries(run),
    )
    if not queries:
        return [], []
    prefix = f"targeted-{_safe_focus_suffix(str(selected_focus))}"
    search_refs = execute_live_searches(
        research_pkg,
        run,
        queries=queries,
        prefix=prefix,
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        json_stream=json_stream,
        runtime=runtime,
    )
    return search_refs, queries


def _analysis_provider_input(
    *,
    phase: str,
    topic: str,
    language: str,
    contract_kind: str,
    artifact_paths: list[Path],
    focus: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "type": "gaia.research.analysis_request",
        "phase": phase,
        "topic": topic,
        "language": language,
        "contract": research_contract(contract_kind, language=language),
        "artifacts": [str(path) for path in artifact_paths],
    }
    if focus is not None:
        payload["focus"] = focus
    return payload


def _maybe_run_field_map_and_coverage(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    analysis_provider: str,
    model: str | None,
    focus_model: str | None,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    research_mode: str,
    focus_analysis_json: str | None,
    scan_landscape: dict[str, Any],
    scan_path: Path,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> tuple[list[dict[str, Any]], list[Path], Path | None, int, dict[str, str]]:
    landscapes = [scan_landscape]
    landscape_paths = [scan_path]
    if focus_analysis_json is not None or analysis_provider != "litellm":
        return landscapes, landscape_paths, None, 0, {}

    field_map_path, field_map_artifact = _run_field_map_phase(
        research_pkg,
        run,
        topic=topic,
        language=language,
        model=runtime.resolve_litellm_model(focus_model or model),
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        research_mode=research_mode,
        scan_landscape=scan_landscape,
        scan_path=scan_path,
        json_stream=json_stream,
        runtime=runtime,
    )
    state_artifacts = {"field_map": str(field_map_path)}
    coverage_queries = _coverage_queries_from_field_map(field_map_artifact)
    if not coverage_queries:
        return landscapes, landscape_paths, field_map_path, 0, state_artifacts

    coverage_search_json = execute_live_searches(
        research_pkg,
        run,
        queries=coverage_queries,
        prefix="coverage",
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        json_stream=json_stream,
        runtime=runtime,
    )
    coverage_path, coverage_landscape = _run_coverage_landscape_phase(
        research_pkg,
        run,
        coverage_search_json=coverage_search_json,
        coverage_queries=coverage_queries,
        field_map_path=field_map_path,
        research_mode=research_mode,
        json_stream=json_stream,
        runtime=runtime,
    )
    landscapes.append(coverage_landscape)
    landscape_paths.append(coverage_path)
    state_artifacts["coverage_landscape"] = str(coverage_path)
    return landscapes, landscape_paths, field_map_path, len(coverage_search_json), state_artifacts


def _run_field_map_phase(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    model: str,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    research_mode: str,
    scan_landscape: dict[str, Any],
    scan_path: Path,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> tuple[Path, dict[str, Any]]:
    runtime.update_run_state(run, {"phase": "field_map_analysis"})
    field_map_json = runtime.run_litellm_provider(
        research_pkg,
        run,
        phase="field_map_analysis",
        model=model,
        input_payload=_analysis_provider_input(
            phase="field_map_analysis",
            topic=topic,
            language=language,
            contract_kind="field_map",
            artifact_paths=[scan_path],
        ),
        output_name="field_map_analysis",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    runtime.update_run_state(run, {"phase": "field_map_sync"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="field_map_sync",
        json_stream=json_stream,
        payload={"inputs": [str(scan_path), field_map_json]},
    )
    start = perf_counter()
    field_map_analysis = runtime.read_json_object_ref(field_map_json, label="field-map JSON")
    field_map_artifact = build_field_map_artifact(
        topic=topic,
        landscapes=[scan_landscape],
        analysis=field_map_analysis,
        language=language,
    )
    field_map_path = runtime.write_artifact(
        research_pkg,
        "field_maps",
        "field-map",
        field_map_artifact,
    )
    runtime.append_research_event(
        research_pkg,
        "run.field_map_sync.completed",
        {
            "artifact": str(field_map_path),
            "buckets": len(field_map_artifact["buckets"]),
            "coverage_gaps": len(field_map_artifact["coverage_gaps"]),
            "recommended_expansions": len(field_map_artifact["recommended_expansions"]),
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="field_map.synthesis",
        mode=research_mode,
        inputs=[str(scan_path), field_map_json],
        outputs=[str(field_map_path)],
        metrics={
            "buckets": len(field_map_artifact["buckets"]),
            "coverage_gaps": len(field_map_artifact["coverage_gaps"]),
            "recommended_expansions": len(field_map_artifact["recommended_expansions"]),
            "analysis_json": True,
        },
    )
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="field_map_sync",
        json_stream=json_stream,
        payload={"artifact": str(field_map_path), "buckets": len(field_map_artifact["buckets"])},
    )
    return field_map_path, field_map_artifact


def _run_coverage_landscape_phase(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    coverage_search_json: list[str],
    coverage_queries: list[str],
    field_map_path: Path,
    research_mode: str,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> tuple[Path, dict[str, Any]]:
    runtime.update_run_state(run, {"phase": "explore_coverage"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="explore_coverage",
        json_stream=json_stream,
        payload={"inputs": coverage_search_json, "field_map": str(field_map_path)},
    )
    start = perf_counter()
    coverage_landscape = build_research_landscape(
        _scan_batches(
            coverage_search_json,
            queries=coverage_queries,
            sources=[],
            runtime=runtime,
        ),
        pull_budget=0,
    )
    coverage_landscape["action"] = "explore.coverage"
    coverage_landscape["target"] = {"kind": "field_map", "id": str(field_map_path)}
    coverage_path = runtime.write_artifact(
        research_pkg,
        "landscapes",
        "coverage",
        coverage_landscape,
    )
    coverage_source_payload = runtime.materialize_landscape_sources(
        research_pkg,
        coverage_landscape,
        landscape_artifact=coverage_path,
        dry_run=False,
    )
    coverage_sync = runtime.sync_landscape_artifact(
        research_pkg,
        coverage_landscape,
        dry_run=False,
    )
    coverage_sync_payload = {**coverage_sync.to_payload(), **coverage_source_payload}
    runtime.append_research_event(
        research_pkg,
        "run.explore_coverage.completed",
        {
            "artifact": str(coverage_path),
            "target": {"kind": "field_map", "id": str(field_map_path)},
            "stats": coverage_landscape["stats"],
            **coverage_sync_payload,
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="explore.coverage",
        mode=research_mode,
        inputs=coverage_search_json,
        outputs=[str(coverage_path)],
        metrics={
            "query_batches": coverage_landscape["stats"]["query_batches"],
            "raw_results": coverage_landscape["stats"]["raw_results"],
            "paper_leads": coverage_landscape["stats"]["paper_leads"],
            "items": len(coverage_landscape.get("items", [])),
            "source_packages_added": _count_payload_items(
                coverage_sync_payload,
                "source_packages_added",
            ),
        },
    )
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="explore_coverage",
        json_stream=json_stream,
        payload={"artifact": str(coverage_path), "stats": coverage_landscape["stats"]},
    )
    return coverage_path, coverage_landscape


def _focus_payload_for_selection(
    focus_artifact: dict[str, Any],
    selected_focus: str,
) -> dict[str, Any]:
    focuses = focus_artifact.get("focuses")
    if isinstance(focuses, list):
        for focus in focuses:
            if isinstance(focus, dict) and str(focus.get("id")) == selected_focus:
                return dict(focus)
    return {"kind": "focus", "id": selected_focus}


def _focus_ids_for_assessment(
    focus_artifact: dict[str, Any],
    *,
    focus: str | None,
    focus_count: int,
) -> list[str]:
    if focus is not None:
        return [focus]
    focuses = focus_artifact.get("focuses")
    selected: list[str] = []
    if isinstance(focuses, list):
        for focus_payload in focuses:
            if not isinstance(focus_payload, dict):
                continue
            focus_id = focus_payload.get("id")
            if isinstance(focus_id, str) and focus_id and focus_id not in selected:
                selected.append(focus_id)
            if len(selected) >= focus_count:
                break
    return selected or ["focus"]


def _safe_focus_suffix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return safe[:80] or "focus"


def _run_evidence_select_and_deep_expand(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    focus_artifact: dict[str, Any],
    selected_focus: str,
    landscapes: list[dict[str, Any]],
    landscape_paths: list[Path],
    lkm_index: str,
    research_mode: str,
    evidence_selection_mode: str,
    evidence_max_items: int,
    evidence_max_papers: int,
    evidence_max_chains: int,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> tuple[Path, dict[str, Any]]:
    focus_payload = _focus_payload_for_selection(focus_artifact, selected_focus)
    runtime.update_run_state(run, {"phase": "evidence_select"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="evidence_select",
        json_stream=json_stream,
        payload={"focus": selected_focus, "inputs": [str(path) for path in landscape_paths]},
    )
    start = perf_counter()
    selected_evidence = build_selected_evidence_artifact(
        focus=focus_payload,
        landscapes=landscapes,
        selection_mode=evidence_selection_mode,
        max_items=evidence_max_items,
        max_papers=evidence_max_papers,
        max_chains=evidence_max_chains,
    )
    selected_evidence_path = runtime.write_artifact(
        research_pkg,
        "evidence",
        "selected-evidence",
        selected_evidence,
    )
    plan = cast(dict[str, list[str]], selected_evidence["materialization_plan"])
    selection = cast(dict[str, Any], selected_evidence["selection"])
    runtime.append_research_event(
        research_pkg,
        "run.evidence_select.completed",
        {
            "focus": selected_focus,
            "artifact": str(selected_evidence_path),
            "selection": selection,
            "coverage_audit": selected_evidence.get("coverage_audit"),
            "materialization_plan": plan,
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="evidence.select",
        mode=research_mode,
        inputs=[str(path) for path in landscape_paths],
        outputs=[str(selected_evidence_path)],
        metrics={
            **selection,
            "selection_mode": evidence_selection_mode,
            "omitted_relevant_evidence": len(
                cast(list[Any], selected_evidence.get("omitted_relevant_evidence") or [])
            ),
            "paper_materialize_requests": len(plan["paper_ids"]),
            "chain_materialize_requests": len(plan["chain_claim_ids"]),
        },
    )
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="evidence_select",
        json_stream=json_stream,
        payload={
            "artifact": str(selected_evidence_path),
            "selection": selection,
            "coverage_audit": selected_evidence.get("coverage_audit"),
            "materialization_plan": plan,
        },
    )

    runtime.update_run_state(run, {"phase": "deep_expand"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="deep_expand",
        json_stream=json_stream,
        payload={"focus": selected_focus, "artifact": str(selected_evidence_path), "plan": plan},
    )
    start = perf_counter()
    materialized = runtime.materialize_lkm_deep_evidence(
        research_pkg,
        paper_ids=list(plan["paper_ids"]),
        claim_ids=list(plan["claim_ids"]),
        chain_claim_ids=list(plan["chain_claim_ids"]),
        lkm_index=lkm_index,
        dry_run=False,
    )
    selected_evidence["materialization_result"] = materialized
    runtime.write_json_file(selected_evidence_path, selected_evidence)
    runtime.append_research_event(
        research_pkg,
        "run.deep_expand.completed",
        {
            "focus": selected_focus,
            "artifact": str(selected_evidence_path),
            **materialized,
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="deep.expand",
        mode=research_mode,
        inputs=[str(selected_evidence_path)],
        outputs=[str(selected_evidence_path)],
        metrics={
            "lkm_materialize_requests": _count_payload_items(
                materialized,
                "lkm_materialize_requests",
            ),
            "lkm_packages_materialized": _count_payload_items(
                materialized,
                "lkm_packages_materialized",
            ),
            "lkm_chains_materialized": _count_payload_items(
                materialized,
                "lkm_chains_materialized",
            ),
        },
    )
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="deep_expand",
        json_stream=json_stream,
        payload={"artifact": str(selected_evidence_path), **materialized},
    )
    return selected_evidence_path, selected_evidence


def _run_assessment_for_focus(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    focus_artifact: dict[str, Any],
    selected_focus: str,
    multi_focus: bool,
    base_landscapes: list[dict[str, Any]],
    base_landscape_paths: list[Path],
    targeted_search_json: list[str],
    targeted_query: list[str],
    assess_analysis_json: str | None,
    analysis_provider: str,
    model: str | None,
    assess_model: str | None,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    evidence_selection_mode: str,
    evidence_max_items: int,
    evidence_max_papers: int,
    evidence_max_chains: int,
    assess_analysis_command: str | None,
    research_mode: str,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> dict[str, Any]:
    focus_suffix = _safe_focus_suffix(selected_focus)
    assess_output_name = f"assess_analysis_{focus_suffix}" if multi_focus else "assess_analysis"
    landscapes = list(base_landscapes)
    landscape_paths = list(base_landscape_paths)
    targeted_search_json, targeted_query = _targeted_searches_after_focus(
        research_pkg,
        run,
        focus_artifact=focus_artifact,
        selected_focus=selected_focus,
        targeted_search_json=targeted_search_json,
        targeted_query=targeted_query,
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        json_stream=json_stream,
        runtime=runtime,
    )

    if targeted_search_json:
        runtime.update_run_state(run, {"phase": "explore_expand", "focus": selected_focus})
        runtime.emit_run_event(
            run,
            event_type="phase.started",
            phase="explore_expand",
            json_stream=json_stream,
            payload={"inputs": targeted_search_json, "focus": selected_focus},
        )
        start = perf_counter()
        expand_landscape = build_research_landscape(
            _scan_batches(
                targeted_search_json,
                queries=targeted_query,
                sources=[],
                runtime=runtime,
            ),
            pull_budget=0,
        )
        expand_landscape["action"] = "explore.expand"
        expand_landscape["target"] = {"kind": "focus", "id": selected_focus}
        expand_path = runtime.write_artifact(
            research_pkg,
            "landscapes",
            f"expand-{focus_suffix}",
            expand_landscape,
        )
        expand_source_payload = runtime.materialize_landscape_sources(
            research_pkg,
            expand_landscape,
            landscape_artifact=expand_path,
            dry_run=False,
        )
        expand_sync = runtime.sync_landscape_artifact(
            research_pkg,
            expand_landscape,
            dry_run=False,
        )
        expand_sync_payload = {**expand_sync.to_payload(), **expand_source_payload}
        runtime.append_research_event(
            research_pkg,
            "run.explore_expand.completed",
            {
                "artifact": str(expand_path),
                "target": {"kind": "focus", "id": selected_focus},
                "stats": expand_landscape["stats"],
                **expand_sync_payload,
            },
        )
        runtime.record_cli_trace(
            research_pkg,
            run,
            start=start,
            name="explore.expand",
            mode=research_mode,
            inputs=targeted_search_json,
            outputs=[str(expand_path)],
            metrics={
                "query_batches": expand_landscape["stats"]["query_batches"],
                "raw_results": expand_landscape["stats"]["raw_results"],
                "paper_leads": expand_landscape["stats"]["paper_leads"],
                "items": len(expand_landscape.get("items", [])),
                "source_packages_added": _count_payload_items(
                    expand_sync_payload, "source_packages_added"
                ),
            },
        )
        landscapes.append(expand_landscape)
        landscape_paths.append(expand_path)
        runtime.emit_run_event(
            run,
            event_type="phase.completed",
            phase="explore_expand",
            json_stream=json_stream,
            payload={"artifact": str(expand_path), "stats": expand_landscape["stats"]},
        )

    selected_evidence_path: Path | None = None
    selected_evidence_artifact: dict[str, Any] | None = None
    if assess_analysis_json is None and analysis_provider in {"command", "litellm"}:
        selected_evidence_path, selected_evidence_artifact = _run_evidence_select_and_deep_expand(
            research_pkg,
            run,
            focus_artifact=focus_artifact,
            selected_focus=selected_focus,
            landscapes=landscapes,
            landscape_paths=landscape_paths,
            lkm_index=search_index,
            research_mode=research_mode,
            evidence_selection_mode=evidence_selection_mode,
            evidence_max_items=evidence_max_items,
            evidence_max_papers=evidence_max_papers,
            evidence_max_chains=evidence_max_chains,
            json_stream=json_stream,
            runtime=runtime,
        )

    assessment_input_paths: list[Path] = (
        [selected_evidence_path] if selected_evidence_path is not None else landscape_paths
    )

    if assess_analysis_json is None:
        if analysis_provider == "command":
            if assess_analysis_command is None:
                raise ResearchOrchestratorError(
                    "--analysis-provider command requires --assess-analysis-command "
                    "when --assess-analysis-json is omitted."
                )
            assess_analysis_json = runtime.run_command_provider(
                research_pkg,
                run,
                phase="assess_analysis",
                command=assess_analysis_command,
                input_payload=_analysis_provider_input(
                    phase="assess_analysis",
                    topic=topic,
                    language=language,
                    contract_kind="assess",
                    artifact_paths=assessment_input_paths,
                    focus=selected_focus,
                ),
                output_name=assess_output_name,
                json_stream=json_stream,
            )
        elif analysis_provider == "litellm":
            resolved_model = runtime.resolve_litellm_model(assess_model or model)
            assess_analysis_json = runtime.run_litellm_provider(
                research_pkg,
                run,
                phase="assess_analysis",
                model=resolved_model,
                input_payload=_analysis_provider_input(
                    phase="assess_analysis",
                    topic=topic,
                    language=language,
                    contract_kind="assess",
                    artifact_paths=assessment_input_paths,
                    focus=selected_focus,
                ),
                output_name=assess_output_name,
                temperature=llm_temperature,
                timeout=llm_timeout,
                max_retries=llm_max_retries,
                max_tokens=llm_max_tokens,
                json_stream=json_stream,
            )
        else:
            _write_run_checkpoint(
                run,
                phase="assess_analysis",
                checkpoint_type="checkpoint.assess_analysis",
                prompt="Provide assessment JSON matching `gaia research contract assess`.",
                json_stream=json_stream,
                runtime=runtime,
            )
            raise ResearchOrchestratorError(exit_code=0)

    runtime.update_run_state(run, {"phase": "assess_sync", "focus": selected_focus})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="assess_sync",
        json_stream=json_stream,
        payload={
            "focus": selected_focus,
            "inputs": [*[str(path) for path in assessment_input_paths], assess_analysis_json],
        },
    )
    start = perf_counter()
    assess_analysis = runtime.read_json_object_ref(
        assess_analysis_json,
        label="--assess-analysis-json",
    )
    selected_evidence_packet = (
        selected_evidence_artifact.get("evidence_packet")
        if selected_evidence_artifact is not None
        else None
    )
    try:
        assessment = build_assessment_from_analysis(
            focus=_focus_payload_for_selection(focus_artifact, selected_focus),
            landscapes=landscapes,
            analysis=assess_analysis,
            evidence_packet=(
                cast(dict[str, Any], selected_evidence_packet)
                if isinstance(selected_evidence_packet, dict)
                else None
            ),
            strict_grounding=True,
        )
    except AssessmentSchemaError as exc:
        runtime.update_run_state(
            run,
            {"status": "failed", "phase": "assess_sync", "error": str(exc)},
        )
        runtime.emit_run_event(
            run,
            event_type="run.failed",
            phase="assess_sync",
            json_stream=json_stream,
            payload={"error": str(exc)},
        )
        raise ResearchOrchestratorError(f"invalid assessment artifact: {exc}") from exc
    assessment_path = runtime.write_artifact(
        research_pkg,
        "assessments",
        f"assessment-{focus_suffix}",
        assessment,
    )
    assess_sync = runtime.sync_assessment_artifact(
        research_pkg,
        assessment,
        dry_run=False,
    )
    assess_sync_payload = assess_sync.to_payload()
    relation_counts = _relation_type_counts(assessment["relations"])
    runtime.append_research_event(
        research_pkg,
        "run.assess_sync.completed",
        {
            "focus": selected_focus,
            "artifact": str(assessment_path),
            "landscapes": [str(path) for path in landscape_paths],
            "selected_evidence": str(selected_evidence_path) if selected_evidence_path else None,
            "items": len(assessment["evidence_packet"]["items"]),
            "relations": len(assessment["relations"]),
            "relation_type_counts": relation_counts,
            "candidate_obligations": len(assessment["candidate_obligations"]),
            "analysis_json": True,
            "review": "review" in assessment,
            **assess_sync_payload,
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="assess",
        mode=research_mode,
        inputs=[*[str(path) for path in assessment_input_paths], assess_analysis_json],
        outputs=[str(assessment_path)],
        metrics={
            "items": len(assessment["evidence_packet"]["items"]),
            "relations": len(assessment["relations"]),
            "candidate_obligations": len(assessment["candidate_obligations"]),
            "analysis_json": True,
            "review": "review" in assessment,
            "notes_written": _count_payload_items(assess_sync_payload, "notes_written"),
            "candidate_relations_written": _count_payload_items(
                assess_sync_payload, "candidate_relations_written"
            ),
            "obligations_added": _count_payload_items(assess_sync_payload, "obligations_added"),
            "hypotheses_added": _count_payload_items(assess_sync_payload, "hypotheses_added"),
        },
    )
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="assess_sync",
        json_stream=json_stream,
        payload={"artifact": str(assessment_path), "relations": len(assessment["relations"])},
    )
    return {
        "focus": selected_focus,
        "landscapes": landscapes,
        "landscape_paths": landscape_paths,
        "targeted_search_json": targeted_search_json,
        "selected_evidence_path": selected_evidence_path,
        "assessment": assessment,
        "assessment_path": assessment_path,
    }


def execute_file_provider_run(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    **kwargs: Any,
) -> None:
    """Execute the fixed workflow and keep UI state accurate on failures."""
    runtime = cast(ResearchOrchestratorRuntime, kwargs["runtime"])
    json_stream = bool(kwargs.get("json_stream", False))
    try:
        _execute_file_provider_run_impl(research_pkg, run, **kwargs)
    except ResearchOrchestratorError as exc:
        if exc.exit_code != 0:
            _mark_run_failed(
                run,
                runtime=runtime,
                json_stream=json_stream,
                phase="failed",
                error=str(exc),
            )
        raise
    except Exception as exc:
        _mark_run_failed(
            run,
            runtime=runtime,
            json_stream=json_stream,
            phase="failed",
            error=str(exc),
        )
        raise


def _mark_run_failed(
    run: ResearchRunStart,
    *,
    runtime: ResearchOrchestratorRuntime,
    json_stream: bool,
    phase: str,
    error: str,
) -> None:
    if run.state_path.exists():
        try:
            state = json.loads(run.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
        if isinstance(state, dict) and state.get("status") == "failed":
            return
    runtime.update_run_state(run, {"status": "failed", "phase": phase, "error": error})
    runtime.emit_run_event(
        run,
        event_type="run.failed",
        phase=phase,
        json_stream=json_stream,
        payload={"error": error},
    )


def _execute_file_provider_run_impl(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    mode: str,
    language: str,
    search_json: list[str],
    focus_analysis_json: str | None,
    targeted_search_json: list[str],
    targeted_query: list[str],
    focus: str | None,
    focus_count: int,
    assess_analysis_json: str | None,
    analysis_provider: str,
    model: str | None,
    focus_model: str | None,
    assess_model: str | None,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    evidence_selection_mode: str,
    evidence_max_items: int,
    evidence_max_papers: int,
    evidence_max_chains: int,
    focus_analysis_command: str | None,
    assess_analysis_command: str | None,
    json_stream: bool,
    runtime: ResearchOrchestratorRuntime,
) -> None:
    """Execute the fixed package-native research workflow for existing search inputs."""
    _ = mode
    research_mode = _research_mode()
    state_artifacts: dict[str, object] = {}
    state_metrics: dict[str, object] = {"searches": len(search_json) + len(targeted_search_json)}

    runtime.update_run_state(run, {"status": "running", "phase": "explore_scan"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="explore_scan",
        json_stream=json_stream,
        payload={"inputs": search_json},
    )
    start = perf_counter()
    scan_landscape = build_research_landscape(
        _scan_batches(search_json, queries=[], sources=[], runtime=runtime),
        pull_budget=0,
    )
    scan_path = runtime.write_artifact(research_pkg, "landscapes", "scan", scan_landscape)
    source_payload = runtime.materialize_landscape_sources(
        research_pkg,
        scan_landscape,
        landscape_artifact=scan_path,
        dry_run=False,
    )
    sync = runtime.sync_landscape_artifact(
        research_pkg,
        scan_landscape,
        dry_run=False,
    )
    sync_payload = {**sync.to_payload(), **source_payload}
    runtime.append_research_event(
        research_pkg,
        "run.explore_scan.completed",
        {"artifact": str(scan_path), "stats": scan_landscape["stats"], **sync_payload},
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="explore.scan",
        mode=research_mode,
        inputs=search_json,
        outputs=[str(scan_path)],
        metrics={
            "query_batches": scan_landscape["stats"]["query_batches"],
            "raw_results": scan_landscape["stats"]["raw_results"],
            "paper_leads": scan_landscape["stats"]["paper_leads"],
            "items": len(scan_landscape.get("items", [])),
            "source_packages_added": _count_payload_items(sync_payload, "source_packages_added"),
        },
    )
    state_artifacts["scan_landscape"] = str(scan_path)
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="explore_scan",
        json_stream=json_stream,
        payload={"artifact": str(scan_path), "stats": scan_landscape["stats"]},
    )

    (
        landscapes,
        landscape_paths,
        field_map_path,
        coverage_searches,
        field_map_artifacts,
    ) = _maybe_run_field_map_and_coverage(
        research_pkg,
        run,
        topic=topic,
        language=language,
        analysis_provider=analysis_provider,
        model=model,
        focus_model=focus_model,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        research_mode=research_mode,
        focus_analysis_json=focus_analysis_json,
        scan_landscape=scan_landscape,
        scan_path=scan_path,
        json_stream=json_stream,
        runtime=runtime,
    )
    state_artifacts.update(field_map_artifacts)

    if focus_analysis_json is None:
        if analysis_provider == "command":
            if focus_analysis_command is None:
                raise ResearchOrchestratorError(
                    "--analysis-provider command requires --focus-analysis-command "
                    "when --focus-analysis-json is omitted."
                )
            focus_analysis_json = runtime.run_command_provider(
                research_pkg,
                run,
                phase="focus_analysis",
                command=focus_analysis_command,
                input_payload=_analysis_provider_input(
                    phase="focus_analysis",
                    topic=topic,
                    language=language,
                    contract_kind="focus",
                    artifact_paths=landscape_paths,
                ),
                output_name="focus_analysis",
                json_stream=json_stream,
            )
        elif analysis_provider == "litellm":
            resolved_model = runtime.resolve_litellm_model(focus_model or model)
            focus_analysis_json = runtime.run_litellm_provider(
                research_pkg,
                run,
                phase="focus_analysis",
                model=resolved_model,
                input_payload=_analysis_provider_input(
                    phase="focus_analysis",
                    topic=topic,
                    language=language,
                    contract_kind="focus",
                    artifact_paths=[
                        *landscape_paths,
                        *([field_map_path] if field_map_path is not None else []),
                    ],
                ),
                output_name="focus_analysis",
                temperature=llm_temperature,
                timeout=llm_timeout,
                max_retries=llm_max_retries,
                max_tokens=llm_max_tokens,
                json_stream=json_stream,
            )
        else:
            _write_run_checkpoint(
                run,
                phase="focus_analysis",
                checkpoint_type="checkpoint.focus_analysis",
                prompt="Provide focus-analysis JSON matching `gaia research contract focus`.",
                json_stream=json_stream,
                runtime=runtime,
            )
            return

    runtime.update_run_state(run, {"phase": "focus_sync"})
    runtime.emit_run_event(
        run,
        event_type="phase.started",
        phase="focus_sync",
        json_stream=json_stream,
        payload={"inputs": [str(scan_path), focus_analysis_json]},
    )
    start = perf_counter()
    focus_analysis = runtime.read_json_object_ref(
        focus_analysis_json,
        label="--focus-analysis-json",
    )
    focus_artifact = build_focus_synthesis_artifact(
        landscapes=landscapes,
        analysis=focus_analysis,
        language=language,
    )
    focus_path = runtime.write_artifact(research_pkg, "focuses", "focuses", focus_artifact)
    focus_sync = runtime.sync_focus_artifact(
        research_pkg,
        focus_artifact,
        max_questions=3,
        dry_run=False,
    )
    focus_sync_payload = focus_sync.to_payload()
    runtime.append_research_event(
        research_pkg,
        "run.focus_sync.completed",
        {
            "artifact": str(focus_path),
            "landscapes": [str(path) for path in landscape_paths],
            "focuses": len(focus_artifact["focuses"]),
            "coverage_gaps": len(focus_artifact["coverage_gaps"]),
            "analysis_json": True,
            "language": language,
            **focus_sync_payload,
        },
    )
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="focus.synthesis",
        mode=research_mode,
        inputs=[*[str(path) for path in landscape_paths], focus_analysis_json],
        outputs=[str(focus_path)],
        metrics={
            "focuses": len(focus_artifact["focuses"]),
            "coverage_gaps": len(focus_artifact["coverage_gaps"]),
            "analysis_json": True,
            "questions_written": _count_payload_items(focus_sync_payload, "questions_written"),
            "obligations_added": _count_payload_items(focus_sync_payload, "obligations_added"),
            "hypotheses_added": _count_payload_items(focus_sync_payload, "hypotheses_added"),
        },
    )
    state_artifacts["focus"] = str(focus_path)
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="focus_sync",
        json_stream=json_stream,
        payload={"artifact": str(focus_path), "focuses": len(focus_artifact["focuses"])},
    )
    selected_focus_ids = _focus_ids_for_assessment(
        focus_artifact,
        focus=focus,
        focus_count=focus_count,
    )
    if assess_analysis_json is not None and len(selected_focus_ids) > 1:
        raise ResearchOrchestratorError(
            "--assess-analysis-json can only be used with one selected focus."
        )

    assessment_results: list[dict[str, Any]] = []
    for index, selected_focus in enumerate(selected_focus_ids):
        result = _run_assessment_for_focus(
            research_pkg,
            run,
            topic=topic,
            language=language,
            focus_artifact=focus_artifact,
            selected_focus=selected_focus,
            multi_focus=len(selected_focus_ids) > 1,
            base_landscapes=landscapes,
            base_landscape_paths=landscape_paths,
            targeted_search_json=targeted_search_json if index == 0 else [],
            targeted_query=targeted_query if index == 0 else [],
            assess_analysis_json=assess_analysis_json,
            analysis_provider=analysis_provider,
            model=model,
            assess_model=assess_model,
            llm_temperature=llm_temperature,
            llm_timeout=llm_timeout,
            llm_max_retries=llm_max_retries,
            llm_max_tokens=llm_max_tokens,
            search_index=search_index,
            search_limit=search_limit,
            reasoning_only=reasoning_only,
            evidence_selection_mode=evidence_selection_mode,
            evidence_max_items=evidence_max_items,
            evidence_max_papers=evidence_max_papers,
            evidence_max_chains=evidence_max_chains,
            assess_analysis_command=assess_analysis_command,
            research_mode=research_mode,
            json_stream=json_stream,
            runtime=runtime,
        )
        assessment_results.append(result)

    assessment_paths = [cast(Path, result["assessment_path"]) for result in assessment_results]
    assessments = [cast(dict[str, Any], result["assessment"]) for result in assessment_results]
    all_landscape_paths = [
        Path(path)
        for path in dict.fromkeys(
            str(path)
            for result in assessment_results
            for path in cast(list[Path], result["landscape_paths"])
        )
    ]
    selected_evidence_paths: list[Path] = [
        cast(Path, path)
        for result in assessment_results
        if (path := result.get("selected_evidence_path")) is not None
    ]
    total_targeted_searches = sum(
        len(cast(list[str], result["targeted_search_json"])) for result in assessment_results
    )
    state_metrics["searches"] = len(search_json) + coverage_searches + total_targeted_searches
    state_artifacts["assessments"] = [str(path) for path in assessment_paths]
    if assessment_paths:
        state_artifacts["assessment"] = str(assessment_paths[0])
    if selected_evidence_paths:
        state_artifacts["selected_evidence"] = str(selected_evidence_paths[0])
        state_artifacts["selected_evidence_by_focus"] = [
            str(path) for path in selected_evidence_paths
        ]

    selected_focus = selected_focus_ids[0]
    assessment = assessments[0]
    assessment_path = assessment_paths[0]
    landscapes = cast(list[dict[str, Any]], assessment_results[0]["landscapes"])
    landscape_paths = all_landscape_paths

    runtime.update_run_state(run, {"phase": "reports_stop"})
    start = perf_counter()
    stop_payload = evaluate_research_stop(
        focus_artifact=focus_artifact,
        assessment=assessment,
        landscapes=[landscapes[-1]],
        previous_landscapes=landscapes[:-1],
    )
    stop_path = run.run_dir / "trace" / "stop.json"
    runtime.write_json_file(stop_path, stop_payload)
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="stop",
        mode="evaluation",
        inputs=[str(focus_path), str(assessment_path), *[str(path) for path in landscape_paths]],
        outputs=[str(stop_path)],
        metrics={
            "recommendation": stop_payload.get("recommendation"),
            "should_stop": stop_payload.get("should_stop"),
            **dict(stop_payload.get("metrics") or {}),
        },
    )

    sectioned_markdown, sectioned_report_inputs = runtime.maybe_run_sectioned_report_writing(
        research_pkg,
        run,
        topic=topic,
        language=language,
        analysis_provider=analysis_provider,
        research_mode=research_mode,
        model=model,
        assess_model=assess_model,
        focus=", ".join(selected_focus_ids),
        field_map_path=field_map_path,
        focus_path=focus_path,
        landscape_paths=landscape_paths,
        selected_evidence_paths=selected_evidence_paths,
        assessment_paths=assessment_paths,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        report_section_concurrency=report_section_concurrency,
        json_stream=json_stream,
    )

    runtime.update_run_state(run, {"phase": "reports_stop"})
    start = perf_counter()
    trace_dir = run.run_dir / "trace"
    focus_trace_artifacts = _collect_trace_json_artifacts(trace_dir, kind="focus_synthesis")
    assessment_trace_artifacts = _collect_trace_json_artifacts(trace_dir, kind="assessment")
    final_focus_inputs = [path for path, _payload in focus_trace_artifacts] or [focus_path]
    final_assessment_inputs = [path for path, _payload in assessment_trace_artifacts] or [
        assessment_path
    ]
    final_focus_payloads = [
        cast(dict[str, Any], payload) for _path, payload in focus_trace_artifacts
    ] or [focus_artifact]
    final_assessment_payloads = [
        cast(dict[str, Any], payload) for _path, payload in assessment_trace_artifacts
    ] or [assessment]
    final_report_path = trace_dir / "final_report.md"
    final_markdown = sectioned_markdown or render_final_research_report_markdown(
        focus_artifacts=final_focus_payloads,
        assessments=final_assessment_payloads,
    )
    runtime.write_text_file(final_report_path, final_markdown)
    runtime.record_cli_trace(
        research_pkg,
        run,
        start=start,
        name="report.final",
        mode=research_mode,
        inputs=[
            *[str(path) for path in final_focus_inputs],
            *[str(path) for path in final_assessment_inputs],
            *sectioned_report_inputs,
        ],
        outputs=[str(final_report_path)],
        metrics={
            "assessments": len(final_assessment_payloads),
            "focus_artifacts": len(final_focus_payloads),
            "markdown_chars": len(final_markdown),
            "writes_file": True,
        },
    )
    state_artifacts["stop"] = str(stop_path)
    state_artifacts["final_report"] = str(final_report_path)
    runtime.emit_run_event(
        run,
        event_type="phase.completed",
        phase="reports_stop",
        json_stream=json_stream,
        payload={
            "final_report": str(final_report_path),
            "stop": str(stop_path),
            "recommendation": stop_payload.get("recommendation"),
            "should_stop": stop_payload.get("should_stop"),
        },
    )

    benchmark_path = runtime.write_benchmark_summary(research_pkg, run.run_dir / "trace")
    runtime.append_research_event(
        research_pkg,
        "run.trace.summary.rebuilt",
        {"benchmark_summary": str(benchmark_path)},
    )
    state_artifacts["benchmark"] = str(benchmark_path)
    state_metrics.update(
        {
            "focuses_assessed": len(assessments),
            "landscapes": len(landscape_paths),
            "relations": sum(len(item["relations"]) for item in assessments),
            "candidate_obligations": sum(
                len(item["candidate_obligations"]) for item in assessments
            ),
        }
    )
    runtime.update_run_state(
        run,
        {
            "status": "completed",
            "phase": "complete",
            "pending_checkpoint": None,
            "artifacts": state_artifacts,
            "metrics": state_metrics,
        },
    )
    runtime.emit_run_event(
        run,
        event_type="run.completed",
        phase="complete",
        json_stream=json_stream,
        payload={
            "benchmark": str(benchmark_path),
            "stop": str(stop_path),
            "recommendation": stop_payload.get("recommendation"),
        },
    )


__all__ = [
    "auto_plan_broad_queries_if_needed",
    "execute_file_provider_run",
    "execute_live_searches",
]
