"""``gaia research`` — package-native research action skeleton."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, NoReturn

import typer
from pydantic import ValidationError

from gaia.cli.commands.research_materialization import (
    _materialize_landscape_sources_or_exit,
    _materialize_lkm_papers_or_exit,
)
from gaia.cli.commands.research_orchestrator import (
    DEFAULT_RUNTIME,
    auto_plan_broad_queries_if_needed,
    execute_file_provider_run,
    execute_live_searches,
)
from gaia.cli.commands.research_providers import (
    _load_research_env_files_or_exit,
)
from gaia.cli.commands.research_runtime import (
    _read_json_object_path,
)
from gaia.cli.commands.search.lkm._indexes import DEFAULT_LKM_INDEX_ID
from gaia.engine.research import (
    AssessmentSchemaError,
    ProposalSchemaError,
    ResearchOrchestratorError,
    ResearchPackage,
    ResearchReportError,
    ResearchRunConfig,
    ResearchTargetError,
    ScanBatch,
    append_research_event,
    build_assessment_from_analysis,
    build_assessment_from_landscapes,
    build_focus_synthesis_artifact,
    build_proposal_from_assessment,
    build_research_landscape,
    ensure_research_manifest,
    evaluate_research_stop,
    load_research_package,
    render_research_artifact_markdown,
    research_contract,
    resolve_research_run_config,
    sync_assessment_artifact,
    sync_focus_artifact,
    sync_landscape_artifact,
    sync_materialization,
    sync_proposal_artifact,
    validate_proposal_artifact,
    write_research_artifact,
)
from gaia.engine.research.benchmark import (
    append_research_trace_step,
    write_research_benchmark_summary,
)
from gaia.engine.research.run import RUN_MODES, start_research_run

research_app = typer.Typer(
    name="research",
    help="Package-native research actions (explore / assess / propose / promote).",
    no_args_is_help=True,
)

trace_app = typer.Typer(
    name="trace",
    help="Record research run trace steps and rebuild derived benchmark summaries.",
    no_args_is_help=True,
)


def _load_or_exit(pkg: str) -> ResearchPackage:
    try:
        return load_research_package(pkg)
    except ResearchTargetError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _print_inquiry_suggestions(pkg: ResearchPackage) -> None:
    typer.echo("Next:")
    typer.echo(
        "  gaia inquiry obligation add "
        f'{pkg.import_name}:target "Describe the missing evidence or coverage gap."'
    )
    typer.echo("  gaia build check " + str(pkg.path))


def _validate_run_options(
    *,
    mode: str,
    analysis_provider: str,
    search_limit: int,
    focus_count: int,
    evidence_selection_mode: str,
) -> None:
    if mode not in RUN_MODES:
        typer.echo(
            f"Error: --mode must be one of: {', '.join(sorted(RUN_MODES))}.",
            err=True,
        )
        raise typer.Exit(2)
    if analysis_provider not in {"checkpoint", "command", "litellm"}:
        typer.echo(
            "Error: --analysis-provider must be one of: checkpoint, command, litellm.",
            err=True,
        )
        raise typer.Exit(2)
    if search_limit < 1 or search_limit > 100:
        typer.echo("Error: --search-limit must be between 1 and 100.", err=True)
        raise typer.Exit(2)
    if focus_count < 1 or focus_count > 8:
        typer.echo("Error: --focus-count must be between 1 and 8.", err=True)
        raise typer.Exit(2)
    if evidence_selection_mode not in {"fast", "review"}:
        typer.echo(
            "Error: --evidence-selection-mode must be one of: fast, review.",
            err=True,
        )
        raise typer.Exit(2)


def _validate_evidence_selection_limits(
    *,
    max_items: int,
    max_papers: int,
    max_chains: int,
) -> None:
    if max_items < 1 or max_items > 200:
        typer.echo("Error: --evidence-max-items must be between 1 and 200.", err=True)
        raise typer.Exit(2)
    if max_papers < 1 or max_papers > 100:
        typer.echo("Error: --evidence-max-papers must be between 1 and 100.", err=True)
        raise typer.Exit(2)
    if max_chains < 0 or max_chains > 100:
        typer.echo("Error: --evidence-max-chains must be between 0 and 100.", err=True)
        raise typer.Exit(2)


def _mark_run_failed_if_needed(
    run: Any,
    runtime: Any,
    *,
    json_stream: bool,
    error: str,
) -> None:
    state = _read_json_object_path(run.state_path)
    if state.get("status") == "failed":
        return
    phase = state.get("phase") if isinstance(state.get("phase"), str) else "failed"
    runtime.update_run_state(
        run,
        {"status": "failed", "phase": phase, "error": error},
    )
    runtime.emit_run_event(
        run,
        event_type="run.failed",
        phase=phase,
        json_stream=json_stream,
        payload={"error": error},
    )


def _exit_after_orchestrator_error(
    exc: ResearchOrchestratorError,
    *,
    run: Any,
    runtime: Any,
    json_stream: bool,
) -> NoReturn:
    if exc.exit_code != 0:
        _mark_run_failed_if_needed(
            run,
            runtime,
            json_stream=json_stream,
            error=str(exc),
        )
    if exc.exit_code != 0 and str(exc):
        typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(exc.exit_code) from exc


def _run_config_overrides_from_legacy_flags(
    *,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    analysis_provider: str,
    model: str | None,
    focus_model: str | None,
    assess_model: str | None,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    focus_count: int,
    evidence_selection_mode: str,
    evidence_max_items: int | None,
    evidence_max_papers: int | None,
    evidence_max_chains: int | None,
) -> dict[str, Any]:
    return _compact_mapping(
        {
            "search": _legacy_search_overrides(
                search_index=search_index,
                search_limit=search_limit,
                reasoning_only=reasoning_only,
            ),
            "focus": {"count": focus_count} if focus_count != 1 else {},
            "evidence": _legacy_evidence_overrides(
                evidence_selection_mode=evidence_selection_mode,
                evidence_max_items=evidence_max_items,
                evidence_max_papers=evidence_max_papers,
                evidence_max_chains=evidence_max_chains,
            ),
            "report": {"section_concurrency": report_section_concurrency}
            if report_section_concurrency != 4
            else {},
            "llm": _legacy_llm_overrides(
                analysis_provider=analysis_provider,
                model=model,
                focus_model=focus_model,
                assess_model=assess_model,
                llm_temperature=llm_temperature,
                llm_timeout=llm_timeout,
                llm_max_retries=llm_max_retries,
                llm_max_tokens=llm_max_tokens,
            ),
        }
    )


def _compact_mapping(values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value}


def _legacy_search_overrides(
    *,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if search_index != DEFAULT_LKM_INDEX_ID:
        overrides["index"] = search_index
    if search_limit != 20:
        overrides["limit"] = search_limit
    if reasoning_only is not True:
        overrides["reasoning_only"] = reasoning_only
    return overrides


def _legacy_evidence_overrides(
    *,
    evidence_selection_mode: str,
    evidence_max_items: int | None,
    evidence_max_papers: int | None,
    evidence_max_chains: int | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if evidence_selection_mode != "fast":
        overrides["selection_mode"] = evidence_selection_mode
    if evidence_max_items is not None:
        overrides["max_items"] = evidence_max_items
    if evidence_max_papers is not None:
        overrides["max_papers"] = evidence_max_papers
    if evidence_max_chains is not None:
        overrides["max_chains"] = evidence_max_chains
    return overrides


def _legacy_llm_overrides(
    *,
    analysis_provider: str,
    model: str | None,
    focus_model: str | None,
    assess_model: str | None,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if analysis_provider != "checkpoint":
        overrides["provider"] = analysis_provider
    if model is not None:
        overrides["model"] = model
    if focus_model is not None:
        overrides["focus_model"] = focus_model
    if assess_model is not None:
        overrides["assess_model"] = assess_model
    if llm_temperature != 0.0:
        overrides["temperature"] = llm_temperature
    if llm_timeout != 120.0:
        overrides["timeout"] = llm_timeout
    if llm_max_retries != 2:
        overrides["max_retries"] = llm_max_retries
    if llm_max_tokens is not None:
        overrides["max_tokens"] = llm_max_tokens
    return overrides


def _resolve_run_config_or_exit(
    *,
    profile: str,
    config: str | None,
    overrides: dict[str, Any],
) -> ResearchRunConfig:
    try:
        return resolve_research_run_config(
            profile=profile,
            config_file=Path(config) if config is not None else None,
            overrides=overrides,
        )
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc


def _read_search_json(ref: str) -> tuple[dict[str, object], str]:
    if ref == "-":
        raw = sys.stdin.read()
        label = "<stdin>"
    else:
        path = Path(ref)
        label = str(path)
        if not path.exists():
            typer.echo(f"Error: --search-json file not found: {ref}", err=True)
            raise typer.Exit(2)
        raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: --search-json is not valid JSON: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(payload, dict):
        typer.echo("Error: --search-json must be a JSON object.", err=True)
        raise typer.Exit(2)
    results = payload.get("results")
    if not isinstance(results, list):
        typer.echo("Error: --search-json must contain a results array.", err=True)
        raise typer.Exit(2)
    return payload, label


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


def _read_json_object_ref(ref: str, *, label: str) -> dict[str, object]:
    if ref == "-":
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        path = Path(ref)
        source = str(path)
        if not path.exists():
            typer.echo(f"Error: {label} file not found: {ref}", err=True)
            raise typer.Exit(2)
        raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: {label} is not valid JSON: {source}: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(payload, dict):
        typer.echo(f"Error: {label} must contain a JSON object: {source}", err=True)
        raise typer.Exit(2)
    return payload


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
) -> list[ScanBatch]:
    batches: list[ScanBatch] = []
    for index, ref in enumerate(refs):
        payload, path_label = _read_search_json(ref)
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


def _record_trace_step(
    research_pkg: ResearchPackage,
    trace_dir: str | None,
    *,
    start: float,
    name: str,
    mode: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, object] | None = None,
) -> None:
    trace_path = append_research_trace_step(
        research_pkg,
        trace_dir,
        name=name,
        kind="cli",
        mode=mode,
        wall_seconds=perf_counter() - start,
        inputs=inputs,
        outputs=outputs,
        metrics=metrics,
    )
    typer.echo(f"trace: {trace_path}")


def _split_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _print_sync_summary(payload: dict[str, object]) -> None:
    typer.echo(f"writes_source: {str(payload.get('writes_source')).lower()}")
    typer.echo(f"writes_inquiry: {str(payload.get('writes_inquiry')).lower()}")
    for key in (
        "source_packages_written",
        "source_packages_added",
        "lkm_packages_materialized",
        "lkm_chains_materialized",
        "questions_written",
        "notes_written",
        "candidate_relations_written",
        "materializations_written",
        "obligations_added",
        "hypotheses_added",
    ):
        value = payload.get(key)
        if isinstance(value, list) and value:
            typer.echo(f"{key}: {len(value)}")
    focus_set = payload.get("focus_set")
    if isinstance(focus_set, str) and focus_set:
        typer.echo(f"focus_set: {focus_set}")


@research_app.command("contract")
def contract_command(
    kind: Annotated[
        str,
        typer.Argument(help="Contract to print: field_map, focus, assess, or propose."),
    ],
    language: Annotated[
        str,
        typer.Option("--language", help="Preferred analysis language for examples/guidance."),
    ] = "zh",
) -> None:
    """Print an agent-facing JSON contract for research analysis."""
    try:
        contract = research_contract(kind, language=language)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(contract, indent=2, ensure_ascii=False))


@research_app.command("status")
def status_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
) -> None:
    """Show package-native research status and initialize the audit manifest."""
    research_pkg = _load_or_exit(pkg)
    manifest = ensure_research_manifest(research_pkg)
    append_research_event(research_pkg, "status.checked", {"writes_source": False})

    inquiry = manifest["inquiry"]
    typer.echo("Research status")
    typer.echo(f"package: {research_pkg.project_name}")
    typer.echo(f"manifest: {research_pkg.path / '.gaia' / 'research' / 'manifest.json'}")
    typer.echo(f"focus: {inquiry.get('focus') or 'none'}")
    typer.echo(f"mode: {inquiry.get('mode')}")
    typer.echo(f"open_obligations: {inquiry.get('open_obligations')}")
    _print_inquiry_suggestions(research_pkg)


@trace_app.command("record")
def trace_record_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    step: Annotated[
        str,
        typer.Option("--step", help="Trace step name, e.g. llm.focus_analysis."),
    ],
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Trace directory containing trace.jsonl and derived benchmark.json.",
        ),
    ] = None,
    kind: Annotated[
        str,
        typer.Option("--kind", help="Step kind: cli, llm, search, or external."),
    ] = "external",
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Run mode label for this trace step.",
        ),
    ] = "external",
    model: Annotated[
        str | None,
        typer.Option("--model", help="LLM/provider model name for token-bearing steps."),
    ] = None,
    input_tokens: Annotated[
        int | None,
        typer.Option("--input-tokens", help="Input token count for this step."),
    ] = None,
    output_tokens: Annotated[
        int | None,
        typer.Option("--output-tokens", help="Output token count for this step."),
    ] = None,
    wall_seconds: Annotated[
        float,
        typer.Option("--wall-seconds", help="Measured wall time for this external step."),
    ] = 0.0,
    input_file: Annotated[
        list[str] | None,
        typer.Option("--input-file", help="Input file path to record; repeatable."),
    ] = None,
    output_file: Annotated[
        list[str] | None,
        typer.Option("--output-file", help="Output file path to record; repeatable."),
    ] = None,
) -> None:
    """Record an external, LLM, search, or manual step in a research run trace."""
    if wall_seconds < 0:
        typer.echo("Error: --wall-seconds must be non-negative.", err=True)
        raise typer.Exit(2)
    if input_tokens is not None and input_tokens < 0:
        typer.echo("Error: --input-tokens must be non-negative.", err=True)
        raise typer.Exit(2)
    if output_tokens is not None and output_tokens < 0:
        typer.echo("Error: --output-tokens must be non-negative.", err=True)
        raise typer.Exit(2)

    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    token_usage = None
    if input_tokens is not None or output_tokens is not None:
        token_input = input_tokens or 0
        token_output = output_tokens or 0
        token_usage = {
            "input_tokens": token_input,
            "output_tokens": token_output,
            "total_tokens": token_input + token_output,
        }
    trace_path = append_research_trace_step(
        research_pkg,
        trace_dir,
        name=step,
        kind=kind,
        mode=mode,
        wall_seconds=wall_seconds,
        inputs=list(input_file or []),
        outputs=list(output_file or []),
        model=model,
        token_usage=token_usage,
    )
    append_research_event(
        research_pkg,
        "trace.step.recorded",
        {
            "trace": str(trace_path),
            "step": step,
            "kind": kind,
            "mode": mode,
            "model": model,
            "token_usage": token_usage,
        },
    )
    typer.echo(f"Trace: {trace_path}")


@trace_app.command("summarize")
def trace_summarize_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Trace directory containing trace.jsonl and derived benchmark.json.",
        ),
    ] = None,
) -> None:
    """Rebuild the derived benchmark summary from trace.jsonl."""
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    benchmark_path = write_research_benchmark_summary(research_pkg, trace_dir)
    append_research_event(
        research_pkg,
        "trace.summary.rebuilt",
        {
            "benchmark_summary": str(benchmark_path),
        },
    )
    typer.echo(f"benchmark_summary: {benchmark_path}")


research_app.add_typer(trace_app, name="trace")


@research_app.command("run")
def run_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    topic: Annotated[
        str,
        typer.Option("--topic", help="Research topic or seed question for the run."),
    ],
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Run mode: fast-package-native.",
        ),
    ] = "fast-package-native",
    language: Annotated[
        str,
        typer.Option("--language", help="Preferred language for generated analysis."),
    ] = "zh",
    profile: Annotated[
        str,
        typer.Option("--profile", help="Research profile used by the fixed pipeline."),
    ] = "evidence-assessment",
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="Optional deterministic run id for tests or UI callers."),
    ] = None,
    config: Annotated[
        str | None,
        typer.Option("--config", help="Optional JSON/TOML workflow config file."),
    ] = None,
    env_file: Annotated[
        list[str] | None,
        typer.Option(
            "--env-file",
            help=(
                "Load dotenv-style KEY=VALUE file before live search/provider calls. "
                "Repeatable; shell environment wins on conflicts."
            ),
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option(
            "--query",
            help="Run live broad LKM search for this query and persist normalized JSON.",
        ),
    ] = None,
    search_json: Annotated[
        list[str] | None,
        typer.Option("--search-json", help="Broad normalized `gaia search lkm` JSON file."),
    ] = None,
    search_index: Annotated[
        str,
        typer.Option("--search-index", "--lkm-index", help="Configured LKM index id."),
    ] = DEFAULT_LKM_INDEX_ID,
    search_limit: Annotated[
        int,
        typer.Option("--search-limit", help="Per-query live LKM result limit."),
    ] = 20,
    reasoning_only: Annotated[
        bool,
        typer.Option(
            "--reasoning-only/--all-lkm-results",
            help="Restrict live LKM search to reasoning-backed claims.",
        ),
    ] = True,
    analysis_provider: Annotated[
        str,
        typer.Option(
            "--analysis-provider",
            help="Analysis input source: checkpoint, command, or litellm.",
        ),
    ] = "checkpoint",
    model: Annotated[
        str | None,
        typer.Option("--model", help="LiteLLM model for all analysis phases."),
    ] = None,
    focus_model: Annotated[
        str | None,
        typer.Option("--focus-model", help="LiteLLM model override for focus analysis."),
    ] = None,
    assess_model: Annotated[
        str | None,
        typer.Option("--assess-model", help="LiteLLM model override for assessment analysis."),
    ] = None,
    llm_temperature: Annotated[
        float,
        typer.Option("--llm-temperature", help="LiteLLM temperature."),
    ] = 0.0,
    llm_timeout: Annotated[
        float,
        typer.Option("--llm-timeout", help="LiteLLM timeout in seconds."),
    ] = 120.0,
    llm_max_retries: Annotated[
        int,
        typer.Option("--llm-max-retries", help="LiteLLM max retries."),
    ] = 2,
    llm_max_tokens: Annotated[
        int | None,
        typer.Option("--llm-max-tokens", help="Optional LiteLLM max output tokens."),
    ] = None,
    report_section_concurrency: Annotated[
        int,
        typer.Option(
            "--report-section-concurrency",
            help="Maximum concurrent LiteLLM calls for independent report sections.",
        ),
    ] = 4,
    focus_analysis_command: Annotated[
        str | None,
        typer.Option(
            "--focus-analysis-command",
            help="Command provider for focus analysis; receives GAIA_RESEARCH_* env vars.",
        ),
    ] = None,
    focus_analysis_json: Annotated[
        str | None,
        typer.Option(
            "--focus-analysis-json",
            help="JSON matching `gaia research contract focus` for file-provider runs.",
        ),
    ] = None,
    targeted_search_json: Annotated[
        list[str] | None,
        typer.Option(
            "--targeted-search-json",
            help="Targeted normalized `gaia search lkm` JSON file.",
        ),
    ] = None,
    targeted_query: Annotated[
        list[str] | None,
        typer.Option(
            "--targeted-query",
            help=("Targeted query text; runs live search when --targeted-search-json is omitted."),
        ),
    ] = None,
    focus: Annotated[
        str | None,
        typer.Option("--focus", help="Focus id/QID to assess after focus synthesis."),
    ] = None,
    focus_count: Annotated[
        int,
        typer.Option(
            "--focus-count",
            help="Number of synthesized focuses to assess when --focus is omitted.",
        ),
    ] = 1,
    evidence_selection_mode: Annotated[
        str,
        typer.Option(
            "--evidence-selection-mode",
            help="Evidence selection policy: fast or review.",
        ),
    ] = "fast",
    evidence_max_items: Annotated[
        int | None,
        typer.Option(
            "--evidence-max-items",
            help="Maximum selected evidence items per assessed focus.",
        ),
    ] = None,
    evidence_max_papers: Annotated[
        int | None,
        typer.Option(
            "--evidence-max-papers",
            help="Maximum selected paper leads/materialized papers per assessed focus.",
        ),
    ] = None,
    evidence_max_chains: Annotated[
        int | None,
        typer.Option(
            "--evidence-max-chains",
            help="Maximum selected chain claim ids per assessed focus.",
        ),
    ] = None,
    assess_analysis_json: Annotated[
        str | None,
        typer.Option(
            "--assess-analysis-json",
            help="JSON matching `gaia research contract assess` for file-provider runs.",
        ),
    ] = None,
    assess_analysis_command: Annotated[
        str | None,
        typer.Option(
            "--assess-analysis-command",
            help="Command provider for assessment analysis; receives GAIA_RESEARCH_* env vars.",
        ),
    ] = None,
    json_stream: Annotated[
        bool,
        typer.Option("--json-stream", help="Emit UI events as NDJSON on stdout."),
    ] = False,
) -> None:
    """Start a UI-observable research run."""
    run_config = _resolve_run_config_or_exit(
        profile=profile,
        config=config,
        overrides=_run_config_overrides_from_legacy_flags(
            search_index=search_index,
            search_limit=search_limit,
            reasoning_only=reasoning_only,
            analysis_provider=analysis_provider,
            model=model,
            focus_model=focus_model,
            assess_model=assess_model,
            llm_temperature=llm_temperature,
            llm_timeout=llm_timeout,
            llm_max_retries=llm_max_retries,
            llm_max_tokens=llm_max_tokens,
            report_section_concurrency=report_section_concurrency,
            focus_count=focus_count,
            evidence_selection_mode=evidence_selection_mode,
            evidence_max_items=evidence_max_items,
            evidence_max_papers=evidence_max_papers,
            evidence_max_chains=evidence_max_chains,
        ),
    )

    _validate_run_options(
        mode=mode,
        analysis_provider=run_config.llm.provider,
        search_limit=run_config.search.limit,
        focus_count=run_config.focus.count,
        evidence_selection_mode=run_config.evidence.selection_mode,
    )
    _validate_evidence_selection_limits(
        max_items=run_config.evidence.max_items,
        max_papers=run_config.evidence.max_papers,
        max_chains=run_config.evidence.max_chains,
    )
    research_pkg = _load_or_exit(pkg)
    _load_research_env_files_or_exit(env_file)
    effective_search_index = run_config.search.index or DEFAULT_LKM_INDEX_ID
    broad_search_refs = list(search_json or [])
    broad_queries = list(query or [])
    targeted_search_refs = list(targeted_search_json or [])
    targeted_queries = list(targeted_query or [])
    can_auto_query_plan = run_config.llm.provider == "litellm"
    try:
        run = start_research_run(
            research_pkg,
            topic=topic,
            mode=mode,
            language=language,
            profile=run_config.profile,
            run_id=run_id,
            wait_for_query_plan=not (broad_search_refs or broad_queries or can_auto_query_plan),
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    for event in run.events:
        if json_stream:
            typer.echo(json.dumps(event, ensure_ascii=False))

    runtime = DEFAULT_RUNTIME
    try:
        broad_queries = auto_plan_broad_queries_if_needed(
            research_pkg,
            run,
            topic=topic,
            language=language,
            profile=run_config.profile,
            analysis_provider=run_config.llm.provider,
            model=run_config.llm.model,
            existing_search_refs=broad_search_refs,
            existing_queries=broad_queries,
            llm_temperature=run_config.llm.temperature,
            llm_timeout=run_config.llm.timeout,
            llm_max_retries=run_config.llm.max_retries,
            llm_max_tokens=run_config.llm.max_tokens,
            json_stream=json_stream,
            runtime=runtime,
        )

        if broad_queries:
            broad_search_refs.extend(
                execute_live_searches(
                    research_pkg,
                    run,
                    queries=broad_queries,
                    prefix="broad",
                    search_index=effective_search_index,
                    search_limit=run_config.search.limit,
                    reasoning_only=run_config.search.reasoning_only,
                    json_stream=json_stream,
                    runtime=runtime,
                )
            )
        if not targeted_search_refs and targeted_queries:
            targeted_search_refs.extend(
                execute_live_searches(
                    research_pkg,
                    run,
                    queries=targeted_queries,
                    prefix="targeted",
                    search_index=effective_search_index,
                    search_limit=run_config.search.limit,
                    reasoning_only=run_config.search.reasoning_only,
                    json_stream=json_stream,
                    runtime=runtime,
                )
            )

        if broad_search_refs:
            execute_file_provider_run(
                research_pkg,
                run,
                topic=topic,
                mode=mode,
                language=language,
                search_json=broad_search_refs,
                focus_analysis_json=focus_analysis_json,
                targeted_search_json=targeted_search_refs,
                targeted_query=targeted_queries,
                focus=focus,
                focus_count=run_config.focus.count,
                assess_analysis_json=assess_analysis_json,
                analysis_provider=run_config.llm.provider,
                model=run_config.llm.model,
                focus_model=run_config.llm.focus_model,
                assess_model=run_config.llm.assess_model,
                llm_temperature=run_config.llm.temperature,
                llm_timeout=run_config.llm.timeout,
                llm_max_retries=run_config.llm.max_retries,
                llm_max_tokens=run_config.llm.max_tokens,
                report_section_concurrency=run_config.report.section_concurrency,
                search_index=effective_search_index,
                search_limit=run_config.search.limit,
                reasoning_only=run_config.search.reasoning_only,
                evidence_selection_mode=run_config.evidence.selection_mode,
                evidence_max_items=run_config.evidence.max_items,
                evidence_max_papers=run_config.evidence.max_papers,
                evidence_max_chains=run_config.evidence.max_chains,
                focus_analysis_command=focus_analysis_command,
                assess_analysis_command=assess_analysis_command,
                json_stream=json_stream,
                runtime=runtime,
            )
    except ResearchOrchestratorError as exc:
        _exit_after_orchestrator_error(
            exc,
            run=run,
            runtime=runtime,
            json_stream=json_stream,
        )

    if broad_search_refs:
        if not json_stream:
            typer.echo(f"Research run: {run.run_id}")
            typer.echo(f"Run directory: {run.run_dir}")
            typer.echo(f"State: {run.state_path}")
            state = _read_json_object_path(run.state_path)
            typer.echo(f"status: {state.get('status')}")
            typer.echo(f"phase: {state.get('phase')}")
        return

    if json_stream:
        return

    typer.echo(f"Research run: {run.run_id}")
    typer.echo(f"Run directory: {run.run_dir}")
    typer.echo(f"State: {run.state_path}")
    typer.echo(f"Events: {run.events_path}")
    typer.echo(f"Pending checkpoint: {run.checkpoint_path}")
    typer.echo("status: waiting_for_input")
    typer.echo("phase: query_plan")


@research_app.command("explore")
def explore_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    mode: Annotated[
        str,
        typer.Option("--mode", help="Explore mode: 'scan' or 'expand'."),
    ] = "scan",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan the scan without pulling papers or writing state."),
    ] = False,
    search_json: Annotated[
        list[str] | None,
        typer.Option(
            "--search-json",
            help="Normalized `gaia search lkm` JSON file; use '-' to read stdin.",
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option("--query", help="Override query text for the matching --search-json."),
    ] = None,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", help="Source QID for the matching --search-json."),
    ] = None,
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the landscape artifact."),
    ] = None,
    focus: Annotated[
        str | None,
        typer.Option("--focus", help="Focus target for --mode expand."),
    ] = None,
    obligation: Annotated[
        str | None,
        typer.Option("--obligation", help="Inquiry obligation target for --mode expand."),
    ] = None,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Run a breadth-first Explore scan or targeted expansion."""
    benchmark_start = perf_counter()
    if mode not in {"scan", "expand"}:
        typer.echo("Error: supported explore modes are `scan` and `expand`.", err=True)
        raise typer.Exit(2)
    search_refs = list(search_json or [])
    if mode == "scan" and not search_refs and not dry_run:
        typer.echo("Error: M1 explore requires `--dry-run`.", err=True)
        raise typer.Exit(2)

    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    if mode == "expand":
        if bool(focus) == bool(obligation):
            typer.echo("Error: --mode expand requires --focus or --obligation.", err=True)
            raise typer.Exit(2)
        if not search_refs:
            typer.echo("Error: --mode expand requires at least one --search-json.", err=True)
            raise typer.Exit(2)
        target = (
            {"kind": "focus", "id": focus} if focus else {"kind": "obligation", "id": obligation}
        )
        landscape = build_research_landscape(
            _scan_batches(search_refs, queries=list(query or []), sources=list(source or [])),
            pull_budget=0,
        )
        landscape["action"] = "explore.expand"
        landscape["target"] = target
        landscape["notes"] = [
            "This is a targeted expansion landscape, not an assessment.",
            "The target links this artifact back to inquiry state or an accepted focus.",
        ]
        output_path = write_research_artifact(
            research_pkg,
            "landscapes",
            "expand",
            landscape,
            out=out,
        )
        source_payload = _materialize_landscape_sources_or_exit(
            research_pkg,
            landscape,
            landscape_artifact=output_path,
            dry_run=dry_run,
        )
        sync = sync_landscape_artifact(
            research_pkg,
            landscape,
            dry_run=dry_run,
        )
        sync_payload = {**sync.to_payload(), **source_payload}
        append_research_event(
            research_pkg,
            "explore.expand.completed",
            {
                "mode": "expand",
                "target": target,
                "artifact": str(output_path),
                "stats": landscape["stats"],
                "pull_budget": 0,
                **sync_payload,
            },
        )
        stats = landscape["stats"]
        _record_trace_step(
            research_pkg,
            trace_dir,
            start=benchmark_start,
            name="explore.expand",
            mode=_research_mode(),
            inputs=search_refs,
            outputs=[str(output_path)],
            metrics={
                "query_batches": stats["query_batches"],
                "raw_results": stats["raw_results"],
                "paper_leads": stats["paper_leads"],
                "items": len(landscape.get("items", [])),
                "pull_budget": 0,
                "source_packages_added": _count_payload_items(
                    sync_payload, "source_packages_added"
                ),
                "hypotheses_added": _count_payload_items(sync_payload, "hypotheses_added"),
                "obligations_added": _count_payload_items(sync_payload, "obligations_added"),
            },
        )
        typer.echo(
            "Landscape: "
            f"{stats['query_batches']} query batch(es), "
            f"{stats['raw_results']} raw result(s), "
            f"{stats['paper_leads']} paper lead(s)."
        )
        typer.echo(f"Target: {target['kind']} {target['id']}")
        typer.echo(f"Output: {output_path}")
        typer.echo("pull_budget: 0")
        _print_sync_summary(sync_payload)
        _print_inquiry_suggestions(research_pkg)
        return

    if search_refs:
        batches = _scan_batches(search_refs, queries=list(query or []), sources=list(source or []))
        landscape = build_research_landscape(batches, pull_budget=0)
        output_path = write_research_artifact(
            research_pkg,
            "landscapes",
            "scan",
            landscape,
            out=out,
        )
        source_payload = _materialize_landscape_sources_or_exit(
            research_pkg,
            landscape,
            landscape_artifact=output_path,
            dry_run=dry_run,
        )
        sync = sync_landscape_artifact(
            research_pkg,
            landscape,
            dry_run=dry_run,
        )
        sync_payload = {**sync.to_payload(), **source_payload}
        append_research_event(
            research_pkg,
            "explore.scan.completed",
            {
                "mode": "scan",
                "artifact": str(output_path),
                "stats": landscape["stats"],
                "pull_budget": 0,
                **sync_payload,
            },
        )
        stats = landscape["stats"]
        _record_trace_step(
            research_pkg,
            trace_dir,
            start=benchmark_start,
            name="explore.scan",
            mode=_research_mode(),
            inputs=search_refs,
            outputs=[str(output_path)],
            metrics={
                "query_batches": stats["query_batches"],
                "raw_results": stats["raw_results"],
                "paper_leads": stats["paper_leads"],
                "items": len(landscape.get("items", [])),
                "pull_budget": 0,
                "source_packages_added": _count_payload_items(
                    sync_payload, "source_packages_added"
                ),
                "hypotheses_added": _count_payload_items(sync_payload, "hypotheses_added"),
                "obligations_added": _count_payload_items(sync_payload, "obligations_added"),
            },
        )
        typer.echo(
            "Landscape: "
            f"{stats['query_batches']} query batch(es), "
            f"{stats['raw_results']} raw result(s), "
            f"{stats['paper_leads']} paper lead(s)."
        )
        typer.echo(f"Output: {output_path}")
        typer.echo("pull_budget: 0")
        _print_sync_summary(sync_payload)
        _print_inquiry_suggestions(research_pkg)
        return

    append_research_event(
        research_pkg,
        "explore.scan.planned",
        {
            "mode": "scan",
            "dry_run": True,
            "pull_budget": 0,
            "writes_source": False,
            "writes_inquiry": False,
            "materialize_sources_enabled": True,
            "source_package_materialization": False,
            "source_packages_written": [],
            "source_packages_added": [],
        },
    )

    typer.echo("Research explore")
    typer.echo("mode: scan")
    typer.echo("dry_run: true")
    typer.echo("pull_budget: 0")
    typer.echo("writes_source: false")
    typer.echo("writes_inquiry: false")
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="explore.scan.plan",
        mode="dry_run",
        metrics={"pull_budget": 0, "dry_run": True},
    )
    _print_inquiry_suggestions(research_pkg)


@research_app.command("expand")
def expand_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    focus: Annotated[
        str | None,
        typer.Option("--focus", help="Focus target to expand."),
    ] = None,
    obligation: Annotated[
        str | None,
        typer.Option("--obligation", help="Inquiry obligation target to expand."),
    ] = None,
    search_json: Annotated[
        list[str] | None,
        typer.Option(
            "--search-json",
            help="Normalized `gaia search lkm` JSON file; use '-' to read stdin.",
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option("--query", help="Override query text for the matching --search-json."),
    ] = None,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", help="Source QID for the matching --search-json."),
    ] = None,
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the landscape artifact."),
    ] = None,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Run targeted Explore expansion around one focus or obligation."""
    explore_command(
        pkg,
        mode="expand",
        dry_run=False,
        search_json=search_json,
        query=query,
        source=source,
        out=out,
        focus=focus,
        obligation=obligation,
        trace_dir=trace_dir,
    )


@research_app.command("focus")
def focus_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    landscape: Annotated[
        list[str] | None,
        typer.Option(
            "--landscape",
            help="Focus synthesis input landscape artifact; defaults to latest landscape.",
        ),
    ] = None,
    analysis_json: Annotated[
        str | None,
        typer.Option(
            "--analysis-json",
            help="Agent/LLM JSON matching `gaia research contract focus`; use '-' for stdin.",
        ),
    ] = None,
    language: Annotated[
        str,
        typer.Option("--language", help="Preferred output language for synthesized focuses."),
    ] = "zh",
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the focus synthesis artifact."),
    ] = None,
    max_questions: Annotated[
        int,
        typer.Option("--max-questions", help="Maximum accepted focuses to write as questions."),
    ] = 3,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan package/inquiry writes without applying them."),
    ] = False,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Synthesize assessment-ready research focuses from landscape artifacts."""
    benchmark_start = perf_counter()
    if max_questions < 1:
        typer.echo("Error: --max-questions must be at least 1.", err=True)
        raise typer.Exit(2)
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    landscape_paths = [Path(item) for item in landscape or []] or _latest_landscape_paths(
        research_pkg
    )
    if not landscape_paths:
        typer.echo("Error: research focus requires at least one landscape artifact.", err=True)
        raise typer.Exit(2)
    landscapes = [_read_json_object_path(path) for path in landscape_paths]
    analysis = (
        _read_json_object_ref(analysis_json, label="--analysis-json")
        if analysis_json is not None
        else None
    )
    artifact = build_focus_synthesis_artifact(
        landscapes=landscapes,
        analysis=analysis,
        language=language,
    )
    output_path = write_research_artifact(
        research_pkg,
        "focuses",
        "focuses",
        artifact,
        out=out,
    )
    sync = sync_focus_artifact(
        research_pkg,
        artifact,
        max_questions=max_questions,
        dry_run=dry_run,
    )
    sync_payload = sync.to_payload()
    append_research_event(
        research_pkg,
        "focus.synthesis.completed",
        {
            "artifact": str(output_path),
            "landscapes": [str(path) for path in landscape_paths],
            "focuses": len(artifact["focuses"]),
            "coverage_gaps": len(artifact["coverage_gaps"]),
            "analysis_json": analysis_json is not None,
            "language": language,
            "max_questions": max_questions,
            **sync_payload,
        },
    )
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="focus.synthesis",
        mode=_research_mode(),
        inputs=[
            *[str(path) for path in landscape_paths],
            *([analysis_json] if analysis_json else []),
        ],
        outputs=[str(output_path)],
        metrics={
            "focuses": len(artifact["focuses"]),
            "coverage_gaps": len(artifact["coverage_gaps"]),
            "analysis_json": analysis_json is not None,
            "questions_written": _count_payload_items(sync_payload, "questions_written"),
            "obligations_added": _count_payload_items(sync_payload, "obligations_added"),
            "hypotheses_added": _count_payload_items(sync_payload, "hypotheses_added"),
            "dry_run": dry_run,
        },
    )
    typer.echo(f"Focus synthesis: {output_path}")
    typer.echo(f"focuses: {len(artifact['focuses'])}")
    typer.echo(f"coverage_gaps: {len(artifact['coverage_gaps'])}")
    _print_sync_summary(sync_payload)
    _print_inquiry_suggestions(research_pkg)


@research_app.command("assess")
def assess_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    focus: Annotated[str, typer.Option("--focus", help="Focus, QID, or obligation target.")],
    landscape: Annotated[
        list[str] | None,
        typer.Option(
            "--landscape",
            help="Assessment input landscape artifact; defaults to latest landscape.",
        ),
    ] = None,
    analysis_json: Annotated[
        str | None,
        typer.Option(
            "--analysis-json",
            help="Agent/LLM JSON matching `gaia research contract assess`; use '-' for stdin.",
        ),
    ] = None,
    strict_grounding: Annotated[
        bool,
        typer.Option(
            "--strict-grounding/--no-strict-grounding",
            help="Require relation source refs to resolve inside the evidence packet.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan package/inquiry writes without applying them."),
    ] = False,
    materialize_paper: Annotated[
        list[str] | None,
        typer.Option(
            "--materialize-paper",
            help="Materialize this LKM paper id as a deep evidence package before assessment.",
        ),
    ] = None,
    materialize_paper_from_claim: Annotated[
        list[str] | None,
        typer.Option(
            "--materialize-paper-from-claim",
            help=(
                "Resolve this LKM claim id to its backing paper and materialize that "
                "paper as a deep evidence package before assessment."
            ),
        ),
    ] = None,
    materialize_chain: Annotated[
        list[str] | None,
        typer.Option(
            "--materialize-chain",
            help=(
                "Materialize this LKM claim's reasoning chains as a focused "
                "deep evidence package before assessment."
            ),
        ),
    ] = None,
    lkm_index: Annotated[
        str,
        typer.Option(
            "--lkm-index",
            "--lkm-server",
            help=(
                "Configured LKM index id for --materialize-paper, "
                "--materialize-paper-from-claim, and --materialize-chain."
            ),
        ),
    ] = DEFAULT_LKM_INDEX_ID,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Assess one focus and sync review scaffolds into package/inquiry state."""
    benchmark_start = perf_counter()
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    has_deep_materialization = bool(
        materialize_paper or materialize_paper_from_claim or materialize_chain
    )
    lkm_materialize_payload = _materialize_lkm_papers_or_exit(
        research_pkg,
        paper_ids=list(materialize_paper or []),
        claim_ids=list(materialize_paper_from_claim or []),
        chain_claim_ids=list(materialize_chain or []),
        lkm_index=lkm_index,
        dry_run=dry_run,
    )
    landscape_paths = [Path(item) for item in landscape or []] or _latest_landscape_paths(
        research_pkg
    )
    if landscape_paths:
        landscapes = [_read_json_object_path(path) for path in landscape_paths]
        analysis = (
            _read_json_object_ref(analysis_json, label="--analysis-json")
            if analysis_json is not None
            else None
        )
        if analysis is None:
            try:
                assessment = build_assessment_from_landscapes(
                    focus={"kind": "focus", "id": focus},
                    landscapes=landscapes,
                )
            except AssessmentSchemaError as exc:
                typer.echo(f"Error: invalid assessment artifact: {exc}", err=True)
                raise typer.Exit(2) from exc
        else:
            try:
                assessment = build_assessment_from_analysis(
                    focus={"kind": "focus", "id": focus},
                    landscapes=landscapes,
                    analysis=analysis,
                    strict_grounding=strict_grounding,
                )
            except AssessmentSchemaError as exc:
                typer.echo(f"Error: invalid assessment artifact: {exc}", err=True)
                raise typer.Exit(2) from exc
        output_path = write_research_artifact(
            research_pkg,
            "assessments",
            "assessment",
            assessment,
        )
        sync = sync_assessment_artifact(
            research_pkg,
            assessment,
            dry_run=dry_run,
        )
        sync_payload = {**sync.to_payload(), **lkm_materialize_payload}
        items = assessment["evidence_packet"]["items"]
        relation_counts = _relation_type_counts(assessment["relations"])
        append_research_event(
            research_pkg,
            "assess.completed",
            {
                "focus": focus,
                "artifact": str(output_path),
                "landscapes": [str(path) for path in landscape_paths],
                "items": len(items),
                "relations": len(assessment["relations"]),
                "relation_type_counts": relation_counts,
                "candidate_obligations": len(assessment["candidate_obligations"]),
                "analysis_json": analysis_json is not None,
                "review": "review" in assessment,
                "strict_grounding": strict_grounding,
                **sync_payload,
            },
        )
        _record_trace_step(
            research_pkg,
            trace_dir,
            start=benchmark_start,
            name="assess",
            mode=_research_mode(
                deep_materialization=has_deep_materialization,
            ),
            inputs=[
                *[str(path) for path in landscape_paths],
                *([analysis_json] if analysis_json else []),
            ],
            outputs=[str(output_path)],
            metrics={
                "items": len(items),
                "relations": len(assessment["relations"]),
                "candidate_obligations": len(assessment["candidate_obligations"]),
                "analysis_json": analysis_json is not None,
                "review": "review" in assessment,
                "notes_written": _count_payload_items(sync_payload, "notes_written"),
                "candidate_relations_written": _count_payload_items(
                    sync_payload, "candidate_relations_written"
                ),
                "candidate_relations_skipped": _count_payload_items(
                    sync_payload, "candidate_relations_skipped"
                ),
                "obligations_added": _count_payload_items(sync_payload, "obligations_added"),
                "hypotheses_added": _count_payload_items(sync_payload, "hypotheses_added"),
                "lkm_packages_materialized": _count_payload_items(
                    sync_payload, "lkm_packages_materialized"
                ),
                "lkm_chains_materialized": _count_payload_items(
                    sync_payload, "lkm_chains_materialized"
                ),
            },
        )
        typer.echo(f"Assessment: {output_path}")
        typer.echo(f"focus: {focus}")
        typer.echo(f"items: {len(items)}")
        typer.echo(f"relations: {len(assessment['relations'])}")
        if relation_counts:
            typer.echo(f"relation_type_counts: {json.dumps(relation_counts, ensure_ascii=False)}")
        typer.echo(f"review: {'true' if 'review' in assessment else 'false'}")
        _print_sync_summary(sync_payload)
        _print_inquiry_suggestions(research_pkg)
        return

    if analysis_json is not None:
        typer.echo("Error: --analysis-json requires at least one landscape artifact.", err=True)
        raise typer.Exit(2)

    append_research_event(
        research_pkg,
        "assess.planned",
        {
            "focus": focus,
            "writes_source": False,
            "writes_inquiry": False,
            "relations": [],
            "promotion_hints": [],
            **lkm_materialize_payload,
        },
    )

    typer.echo("Research assess")
    typer.echo(f"focus: {focus}")
    typer.echo("writes_source: false")
    typer.echo("writes_inquiry: false")
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="assess.plan",
        mode=_research_mode(
            deep_materialization=has_deep_materialization,
        ),
        metrics={
            "relations": 0,
            "lkm_packages_materialized": _count_payload_items(
                lkm_materialize_payload, "lkm_packages_materialized"
            ),
            "lkm_chains_materialized": _count_payload_items(
                lkm_materialize_payload, "lkm_chains_materialized"
            ),
        },
    )
    _print_inquiry_suggestions(research_pkg)


@research_app.command("propose")
def propose_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    from_assessment: Annotated[
        str,
        typer.Option(
            "--from-assessment",
            help="Assessment artifact to transform into open-ended research proposals.",
        ),
    ],
    analysis_json: Annotated[
        str | None,
        typer.Option(
            "--analysis-json",
            help="Agent/LLM JSON matching `gaia research contract propose`; use '-' for stdin.",
        ),
    ] = None,
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Write accepted research_question proposals into package source and inquiry.",
        ),
    ] = False,
    max_questions: Annotated[
        int,
        typer.Option("--max-questions", help="Maximum accepted proposals to write as questions."),
    ] = 3,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Plan accepted package/inquiry writes without applying them.",
        ),
    ] = False,
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the proposal artifact."),
    ] = None,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Propose open-ended next research questions from an assessment artifact."""
    benchmark_start = perf_counter()
    if max_questions < 1:
        typer.echo("Error: --max-questions must be at least 1.", err=True)
        raise typer.Exit(2)
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    assessment_path = Path(from_assessment)
    assessment = _read_json_object_path(assessment_path)
    analysis = (
        _read_json_object_ref(analysis_json, label="--analysis-json")
        if analysis_json is not None
        else None
    )
    proposal = build_proposal_from_assessment(assessment=assessment, analysis=analysis)
    try:
        validate_proposal_artifact(proposal)
    except ProposalSchemaError as exc:
        typer.echo(f"Error: invalid proposal artifact: {exc}", err=True)
        raise typer.Exit(2) from exc
    output_path = write_research_artifact(
        research_pkg,
        "proposals",
        "proposal",
        proposal,
        out=out,
    )
    sync = sync_proposal_artifact(
        research_pkg,
        proposal,
        max_questions=max_questions,
        dry_run=(dry_run or not accept),
    )
    sync_payload = sync.to_payload()
    append_research_event(
        research_pkg,
        "propose.completed",
        {
            "artifact": str(output_path),
            "source_assessment": str(assessment_path),
            "proposals": len(proposal["proposals"]),
            "hypotheses": len(proposal["hypotheses"]),
            "candidate_obligations": len(proposal["candidate_obligations"]),
            "analysis_json": analysis_json is not None,
            "accepted": accept,
            "max_questions": max_questions,
            **sync_payload,
        },
    )
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="propose",
        mode="dry_run" if (dry_run or not accept) else _research_mode(),
        inputs=[from_assessment, *([analysis_json] if analysis_json else [])],
        outputs=[str(output_path)],
        metrics={
            "proposals": len(proposal["proposals"]),
            "hypotheses": len(proposal["hypotheses"]),
            "candidate_obligations": len(proposal["candidate_obligations"]),
            "analysis_json": analysis_json is not None,
            "accepted": accept,
            "questions_written": _count_payload_items(sync_payload, "questions_written"),
            "obligations_added": _count_payload_items(sync_payload, "obligations_added"),
            "hypotheses_added": _count_payload_items(sync_payload, "hypotheses_added"),
        },
    )
    typer.echo(f"Proposal: {output_path}")
    typer.echo(f"source_assessment: {assessment_path}")
    typer.echo(f"proposals: {len(proposal['proposals'])}")
    typer.echo(f"hypotheses: {len(proposal['hypotheses'])}")
    typer.echo(f"candidate_obligations: {len(proposal['candidate_obligations'])}")
    typer.echo(f"accepted: {str(accept).lower()}")
    _print_sync_summary(sync_payload)
    _print_inquiry_suggestions(research_pkg)


@research_app.command("promote")
def promote_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    scaffold: Annotated[
        str,
        typer.Option("--scaffold", help="Scaffold binding to materialize."),
    ],
    by: Annotated[
        str,
        typer.Option("--by", help="Comma-separated formal graph records materializing it."),
    ],
    rationale: Annotated[
        str | None,
        typer.Option("--rationale", help="Optional rationale for the materialization link."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan package writes without applying them."),
    ] = False,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Record a narrow scaffold-to-formal-knowledge materialization link."""
    benchmark_start = perf_counter()
    by_refs = _split_csv_values(by)
    if not by_refs:
        typer.echo("Error: --by must name at least one materialized target.", err=True)
        raise typer.Exit(2)
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    sync = sync_materialization(
        research_pkg,
        scaffold=scaffold,
        by=by_refs,
        rationale=rationale,
        dry_run=dry_run,
    )
    sync_payload = sync.to_payload()
    append_research_event(
        research_pkg,
        "promote.completed",
        {
            "scaffold": scaffold,
            "by": by_refs,
            "rationale": rationale,
            **sync_payload,
        },
    )
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="promote",
        mode="dry_run" if dry_run else _research_mode(),
        metrics={
            "by_refs": len(by_refs),
            "materializations_written": _count_payload_items(
                sync_payload, "materializations_written"
            ),
            "dry_run": dry_run,
        },
    )
    typer.echo("Research promote")
    typer.echo(f"scaffold: {scaffold}")
    typer.echo(f"by: {', '.join(by_refs)}")
    _print_sync_summary(sync_payload)
    _print_inquiry_suggestions(research_pkg)


@research_app.command("report")
def report_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    artifact: Annotated[
        str,
        typer.Option("--artifact", help="Research artifact JSON to render as Markdown."),
    ],
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the rendered Markdown report."),
    ] = None,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Render a research artifact as readable Markdown."""
    benchmark_start = perf_counter()
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    artifact_path = Path(artifact)
    payload = _read_json_object_path(artifact_path)
    try:
        markdown = render_research_artifact_markdown(payload)
    except ResearchReportError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    if out is None:
        typer.echo(markdown.rstrip())
        append_research_event(
            research_pkg,
            "report.rendered",
            {"artifact": str(artifact_path), "out": None, "writes_source": False},
        )
        _record_trace_step(
            research_pkg,
            trace_dir,
            start=benchmark_start,
            name="report",
            mode="report",
            inputs=[str(artifact_path)],
            metrics={
                "artifact_kind": payload.get("kind"),
                "markdown_chars": len(markdown),
                "writes_file": False,
            },
        )
        return

    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    append_research_event(
        research_pkg,
        "report.rendered",
        {"artifact": str(artifact_path), "out": str(output_path), "writes_source": False},
    )
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="report",
        mode="report",
        inputs=[str(artifact_path)],
        outputs=[str(output_path)],
        metrics={
            "artifact_kind": payload.get("kind"),
            "markdown_chars": len(markdown),
            "writes_file": True,
        },
    )
    typer.echo(f"Report: {output_path}")
    typer.echo("writes_source: false")


@research_app.command("stop")
def stop_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    focus_artifact: Annotated[
        str | None,
        typer.Option("--focus-artifact", help="Optional focus synthesis artifact JSON."),
    ] = None,
    assessment: Annotated[
        str | None,
        typer.Option("--assessment", help="Optional assessment artifact JSON."),
    ] = None,
    landscape: Annotated[
        list[str] | None,
        typer.Option(
            "--landscape",
            help="Current landscape artifact; defaults to latest package landscape.",
        ),
    ] = None,
    previous_landscape: Annotated[
        list[str] | None,
        typer.Option("--previous-landscape", help="Earlier landscape for query novelty."),
    ] = None,
    max_open_obligations: Annotated[
        int,
        typer.Option(
            "--max-open-obligations",
            help="Maximum unresolved assessment obligations before expansion is weak.",
        ),
    ] = 2,
    min_new_lead_ratio: Annotated[
        float,
        typer.Option(
            "--min-new-lead-ratio",
            help="Minimum latest-vs-previous new paper lead ratio before query novelty is weak.",
        ),
    ] = 0.2,
    out: Annotated[
        str | None,
        typer.Option("--out", help="Optional output path for the stop criteria JSON."),
    ] = None,
    trace_dir: Annotated[
        str | None,
        typer.Option(
            "--trace-dir",
            help="Append timing and size metrics to this research trace directory.",
        ),
    ] = None,
) -> None:
    """Evaluate auditable stop criteria for the current research-loop state."""
    benchmark_start = perf_counter()
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    default_landscapes = _all_landscape_paths(research_pkg)
    landscape_paths = [Path(item) for item in landscape or []]
    if not landscape_paths and default_landscapes:
        landscape_paths = default_landscapes[-1:]

    previous_paths = [Path(item) for item in previous_landscape or []]
    if not previous_paths and not landscape and default_landscapes:
        previous_paths = default_landscapes[:-1]

    stop_artifact = evaluate_research_stop(
        focus_artifact=(
            _read_json_object_path(Path(focus_artifact)) if focus_artifact is not None else None
        ),
        assessment=_read_json_object_path(Path(assessment)) if assessment is not None else None,
        landscapes=[_read_json_object_path(path) for path in landscape_paths],
        previous_landscapes=[_read_json_object_path(path) for path in previous_paths],
        max_open_obligations=max_open_obligations,
        min_new_lead_ratio=min_new_lead_ratio,
    )
    output_path = write_research_artifact(
        research_pkg,
        "stops",
        "stop",
        stop_artifact,
        out=out,
    )
    append_research_event(
        research_pkg,
        "stop.evaluated",
        {
            "artifact": str(output_path),
            "focus_artifact": focus_artifact,
            "assessment": assessment,
            "landscapes": [str(path) for path in landscape_paths],
            "previous_landscapes": [str(path) for path in previous_paths],
            "recommendation": stop_artifact["recommendation"],
            "should_stop": stop_artifact["should_stop"],
            "writes_source": False,
        },
    )
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="stop",
        mode="evaluation",
        inputs=[
            *([focus_artifact] if focus_artifact else []),
            *([assessment] if assessment else []),
            *[str(path) for path in landscape_paths],
            *[str(path) for path in previous_paths],
        ],
        outputs=[str(output_path)],
        metrics={
            "recommendation": stop_artifact["recommendation"],
            "should_stop": stop_artifact["should_stop"],
            "landscapes": len(landscape_paths),
            "previous_landscapes": len(previous_paths),
        },
    )
    typer.echo(f"Stop criteria: {output_path}")
    typer.echo(f"recommendation: {stop_artifact['recommendation']}")
    typer.echo(f"should_stop: {str(stop_artifact['should_stop']).lower()}")
    dimensions = stop_artifact["dimensions"]
    if isinstance(dimensions, dict):
        for name, dimension in sorted(dimensions.items()):
            if isinstance(dimension, dict):
                typer.echo(f"{name}: {dimension.get('status')} - {dimension.get('reason')}")
    typer.echo("writes_source: false")


__all__ = ["research_app"]
