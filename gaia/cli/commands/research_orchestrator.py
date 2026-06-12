"""CLI runtime adapter for fixed research workflow orchestration."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from gaia.cli.commands.research_materialization import (
    _materialize_landscape_sources_or_exit,
    _materialize_lkm_papers_or_exit,
)
from gaia.cli.commands.research_providers import (
    _resolve_litellm_model,
    _run_analysis_provider_command,
    _run_analysis_provider_litellm,
)
from gaia.cli.commands.research_report_writing import _maybe_run_sectioned_report_writing
from gaia.cli.commands.research_runtime import (
    _emit_run_event,
    _record_run_cli_trace,
    _record_run_trace,
    _update_run_state,
)
from gaia.engine.research import (
    ResearchOrchestratorError,
    ResearchOrchestratorRuntime,
    ResearchPackage,
    ResearchSyncResult,
    append_research_event,
    sync_assessment_artifact,
    sync_focus_artifact,
    sync_landscape_artifact,
    write_research_artifact,
)
from gaia.engine.research.benchmark import write_research_benchmark_summary
from gaia.engine.research.orchestrator import (
    auto_plan_broad_queries_if_needed,
    execute_file_provider_run,
    execute_live_searches,
)
from gaia.engine.research.run import ResearchRunStart


@dataclass(frozen=True)
class CliResearchOrchestratorRuntime(ResearchOrchestratorRuntime):
    """CLI-backed runtime services for fixed research workflow orchestration."""

    def update_run_state(self, run: ResearchRunStart, payload: dict[str, object]) -> None:
        """Update persisted run state."""
        _update_run_state(run, payload)

    def read_search_json(self, ref: str) -> tuple[dict[str, object], str]:
        """Read one normalized search JSON reference and return payload plus label."""
        return _read_search_json(ref)

    def read_json_object_ref(self, ref: str, *, label: str) -> dict[str, object]:
        """Read one JSON object from a workflow reference."""
        return _read_json_object_ref(ref, label=label)

    def write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        """Write one JSON file."""
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def write_text_file(self, path: Path, text: str) -> None:
        """Write one text file."""
        path.write_text(text, encoding="utf-8")

    def write_artifact(
        self,
        research_pkg: ResearchPackage,
        category: str,
        stem: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write one package-local research artifact."""
        return write_research_artifact(research_pkg, category, stem, payload)

    def append_research_event(
        self,
        research_pkg: ResearchPackage,
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Append a package-local research event."""
        return append_research_event(research_pkg, event, payload)

    def emit_run_event(
        self,
        run: ResearchRunStart,
        *,
        event_type: str,
        phase: str,
        json_stream: bool,
        payload: dict[str, object],
    ) -> None:
        """Emit a UI-observable run event."""
        _emit_run_event(
            run,
            event_type=event_type,
            phase=phase,
            json_stream=json_stream,
            payload=payload,
        )

    def record_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        kind: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
        status: str = "ok",
    ) -> None:
        """Record a generic trace step."""
        _record_run_trace(
            research_pkg,
            run,
            start=start,
            name=name,
            kind=kind,
            mode=mode,
            inputs=inputs,
            outputs=outputs,
            metrics=metrics,
            status=status,
        )

    def record_cli_trace(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        start: float,
        name: str,
        mode: str,
        inputs: list[str],
        outputs: list[str],
        metrics: dict[str, object] | None = None,
    ) -> None:
        """Record a CLI workflow trace step."""
        _record_run_cli_trace(
            research_pkg,
            run,
            start=start,
            name=name,
            mode=mode,
            inputs=inputs,
            outputs=outputs,
            metrics=metrics,
        )

    def sync_landscape_artifact(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one landscape artifact into package state."""
        return sync_landscape_artifact(research_pkg, landscape, dry_run=dry_run)

    def sync_focus_artifact(
        self,
        research_pkg: ResearchPackage,
        focus_artifact: dict[str, Any],
        *,
        max_questions: int,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one focus artifact into package state."""
        return sync_focus_artifact(
            research_pkg,
            focus_artifact,
            max_questions=max_questions,
            dry_run=dry_run,
        )

    def sync_assessment_artifact(
        self,
        research_pkg: ResearchPackage,
        assessment: dict[str, Any],
        *,
        dry_run: bool,
    ) -> ResearchSyncResult:
        """Sync one assessment artifact into package state."""
        return sync_assessment_artifact(research_pkg, assessment, dry_run=dry_run)

    def write_benchmark_summary(
        self,
        research_pkg: ResearchPackage,
        trace_dir: Path,
    ) -> Path:
        """Write a benchmark summary from the run trace."""
        return write_research_benchmark_summary(research_pkg, trace_dir)

    def resolve_litellm_model(self, model: str | None) -> str:
        """Resolve the effective LiteLLM model for provider calls."""
        return _resolve_litellm_model(model)

    def maybe_run_sectioned_report_writing(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        topic: str,
        language: str,
        analysis_provider: str,
        research_mode: str,
        model: str | None,
        assess_model: str | None,
        focus: str,
        field_map_path: Path | None,
        focus_path: Path,
        landscape_paths: list[Path],
        selected_evidence_paths: list[Path],
        assessment_paths: list[Path],
        llm_temperature: float,
        llm_timeout: float,
        llm_max_retries: int,
        llm_max_tokens: int | None,
        report_section_concurrency: int,
        json_stream: bool,
    ) -> tuple[str | None, list[str]]:
        """Optionally run sectioned final report writing."""
        return _maybe_run_sectioned_report_writing(
            research_pkg,
            run,
            topic=topic,
            language=language,
            analysis_provider=analysis_provider,
            research_mode=research_mode,
            model=model,
            assess_model=assess_model,
            focus=focus,
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

    def search_lkm(
        self,
        query: str,
        *,
        index: str,
        limit: int,
        reasoning_only: bool,
    ) -> dict[str, object]:
        """Run one LKM search and return normalized search results."""
        return _run_lkm_knowledge_search(
            query,
            index=index,
            limit=limit,
            reasoning_only=reasoning_only,
        )

    def run_command_provider(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        phase: str,
        command: str,
        input_payload: dict[str, object],
        output_name: str,
        json_stream: bool,
    ) -> str:
        """Run command-backed analysis provider."""
        return _run_analysis_provider_command(
            research_pkg,
            run,
            phase=phase,
            command=command,
            input_payload=input_payload,
            output_name=output_name,
            json_stream=json_stream,
        )

    def run_litellm_provider(
        self,
        research_pkg: ResearchPackage,
        run: ResearchRunStart,
        *,
        phase: str,
        model: str,
        input_payload: dict[str, object],
        output_name: str,
        temperature: float,
        timeout: float,
        max_retries: int,
        max_tokens: int | None,
        json_stream: bool,
    ) -> str:
        """Run LiteLLM-backed analysis provider."""
        return _run_analysis_provider_litellm(
            research_pkg,
            run,
            phase=phase,
            model=model,
            input_payload=input_payload,
            output_name=output_name,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
            max_tokens=max_tokens,
            json_stream=json_stream,
        )

    def materialize_landscape_sources(
        self,
        research_pkg: ResearchPackage,
        landscape: dict[str, Any],
        *,
        landscape_artifact: Path,
        dry_run: bool,
    ) -> dict[str, object]:
        """Materialize shallow source packages for a landscape artifact."""
        return _materialize_landscape_sources_or_exit(
            research_pkg,
            landscape,
            landscape_artifact=landscape_artifact,
            dry_run=dry_run,
        )

    def materialize_lkm_deep_evidence(
        self,
        research_pkg: ResearchPackage,
        *,
        paper_ids: list[str],
        claim_ids: list[str],
        chain_claim_ids: list[str],
        lkm_index: str,
        dry_run: bool,
    ) -> dict[str, object]:
        """Materialize selected LKM paper graphs or reasoning chains."""
        return _materialize_lkm_papers_or_exit(
            research_pkg,
            paper_ids=paper_ids,
            claim_ids=claim_ids,
            chain_claim_ids=chain_claim_ids,
            lkm_index=lkm_index,
            dry_run=dry_run,
        )


DEFAULT_RUNTIME = CliResearchOrchestratorRuntime()


def _read_search_json(ref: str) -> tuple[dict[str, object], str]:
    if ref == "-":
        raw = sys.stdin.read()
        label = "<stdin>"
    else:
        path = Path(ref)
        label = str(path)
        if not path.exists():
            raise ResearchOrchestratorError(f"--search-json file not found: {ref}")
        raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchOrchestratorError(f"--search-json is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResearchOrchestratorError("--search-json must be a JSON object.")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ResearchOrchestratorError("--search-json must contain a results array.")
    return payload, label


def _read_json_object_ref(ref: str, *, label: str) -> dict[str, object]:
    if ref == "-":
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        path = Path(ref)
        source = str(path)
        if not path.exists():
            raise ResearchOrchestratorError(f"{label} file not found: {ref}")
        raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchOrchestratorError(f"{label} is not valid JSON: {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResearchOrchestratorError(f"{label} must contain a JSON object: {source}")
    return payload


def _run_lkm_knowledge_search(
    query: str,
    *,
    index: str,
    limit: int,
    reasoning_only: bool,
) -> dict[str, object]:
    from gaia.cli.commands.search.lkm._shared import run_request

    body: dict[str, object] = {
        "query": query,
        "retrieval_mode": "hybrid",
        "offset": 0,
        "limit": limit,
        "filters": {"visibility": "public"},
    }
    if reasoning_only:
        body["reasoning_only"] = True
    payload = run_request("POST", "/search", json_body=body, index_id=index)
    return _normalize_lkm_knowledge_search(payload, query=query, kind="knowledge", index_id=index)


def _normalize_lkm_knowledge_search(
    payload: dict[str, Any],
    *,
    query: str,
    kind: str,
    index_id: str,
) -> dict[str, object]:
    """Normalize LKM /search variables into the research search envelope."""
    data = _dict(payload.get("data"))
    variables = _list(data.get("variables")) or _list(payload.get("variables"))
    papers = _lkm_papers(payload)
    results = [
        _normalize_lkm_variable(variable, index=idx, papers=papers, index_id=index_id)
        for idx, variable in enumerate(variables)
        if isinstance(variable, dict)
    ]
    query_payload: dict[str, object] = {
        "text": query,
        "provider": "lkm",
        "kind": kind,
        "index_id": index_id,
    }
    return {
        "schema_version": 1,
        "query": query_payload,
        "results": results,
    }


def _normalize_lkm_variable(
    variable: dict[str, Any],
    *,
    index: int,
    papers: dict[str, dict[str, Any]],
    index_id: str,
) -> dict[str, object]:
    provider_id = (
        _string(variable.get("id")) or _string(variable.get("global_id")) or f"var_{index}"
    )
    source_package, local_id = _lkm_variable_source(variable)
    paper_id = _paper_id(source_package)
    paper = _paper_metadata(papers, source_package=source_package, paper_id=paper_id)
    paper_title = _paper_title(paper)
    doi = _string(paper.get("doi"))
    score = _number(variable.get("score"), variable.get("rerank_score"))
    object_kind = {"claim": "claim", "question": "question"}.get(
        _string(variable.get("type")) or "claim",
        "note",
    )
    return {
        "id": f"lkm:{index_id}:{provider_id}",
        "provider": "lkm",
        "kind": object_kind,
        "title": _string(variable.get("title")) or provider_id,
        "content": _string(variable.get("content")),
        "relevance_score": score,
        "rank": {"score": score, "score_kind": "retrieval"},
        "source": {
            "provider_id": provider_id,
            "index_id": index_id,
            "source_package": source_package,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "doi": doi,
            "local_id": local_id,
            "role": _string(variable.get("role")),
            "has_evidence": variable.get("has_evidence"),
            "has_reasoning": variable.get("has_reasoning"),
        },
        "raw": {"provider": "lkm", "payload": variable},
    }


def _lkm_variable_source(variable: dict[str, Any]) -> tuple[str | None, str | None]:
    provenance = _dict(variable.get("provenance"))
    representative = _dict(provenance.get("representative_lcn"))
    source_package = _string(representative.get("package_id"))
    local_id = _string(representative.get("local_id"))
    if source_package is None:
        source_packages = _list(provenance.get("source_packages"))
        first_source = source_packages[0] if source_packages else None
        source_package = _string(first_source)
    if source_package is None and local_id and "::" in local_id:
        source_package = local_id.split("::", 1)[0]
    return source_package, local_id


def _lkm_papers(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = _dict(payload.get("data"))
    raw_papers = data.get("papers", payload.get("papers"))
    if isinstance(raw_papers, dict):
        papers: dict[str, dict[str, Any]] = {}
        for key, value in raw_papers.items():
            if not isinstance(value, dict):
                continue
            paper = _dict(value.get("paper")) or value
            papers[str(key)] = paper
            paper_id = _string(paper.get("id")) or _paper_id(_string(paper.get("package_id")))
            if paper_id:
                papers[f"paper:{paper_id}"] = paper
        return papers
    if isinstance(raw_papers, list):
        papers = {}
        for item in raw_papers:
            if not isinstance(item, dict):
                continue
            paper = _dict(item.get("paper")) or item
            paper_id = _string(paper.get("id")) or _paper_id(_string(paper.get("package_id")))
            if paper_id:
                papers[f"paper:{paper_id}"] = paper
        return papers
    return {}


def _paper_metadata(
    papers: dict[str, dict[str, Any]],
    *,
    source_package: str | None,
    paper_id: str | None,
) -> dict[str, Any]:
    if source_package and source_package in papers:
        return papers[source_package]
    if paper_id and (paper := papers.get(f"paper:{paper_id}")):
        return paper
    return {}


def _paper_title(paper: dict[str, Any]) -> str | None:
    return (
        _string(paper.get("en_title"))
        or _string(paper.get("zh_title"))
        or _string(paper.get("title"))
        or _string(paper.get("paper_title"))
        or _string(paper.get("name"))
    )


def _paper_id(source_package: str | None) -> str | None:
    if not source_package or not source_package.startswith("paper:"):
        return None
    return source_package.split(":", 1)[1]


def _dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
    return None


__all__ = [
    "DEFAULT_RUNTIME",
    "CliResearchOrchestratorRuntime",
    "auto_plan_broad_queries_if_needed",
    "execute_file_provider_run",
    "execute_live_searches",
]
