"""``gaia research`` — package-native research action skeleton."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter, sleep
from typing import Annotated, Any, cast

import typer

from gaia.cli.commands.add import (
    LKMDependencyAddError,
    add_lkm_chain_dependency,
    add_lkm_claim_dependency,
    add_lkm_paper_dependency,
    add_local_package_dependency,
    make_lkm_claim_ref,
    make_lkm_paper_ref,
)
from gaia.cli.commands.search.lkm._indexes import DEFAULT_LKM_INDEX_ID
from gaia.engine.packaging import GaiaPackagingError
from gaia.engine.research import (
    AssessmentSchemaError,
    ProposalSchemaError,
    ResearchPackage,
    ResearchReportError,
    ResearchTargetError,
    ScanBatch,
    append_research_event,
    attach_source_package_refs,
    build_assessment_from_analysis,
    build_assessment_from_landscapes,
    build_field_map_artifact,
    build_focus_synthesis_artifact,
    build_proposal_from_assessment,
    build_research_landscape,
    build_selected_evidence_artifact,
    ensure_research_manifest,
    evaluate_research_stop,
    load_research_package,
    materialize_landscape_source_package,
    render_final_research_report_markdown,
    render_markdown_with_research_citations,
    render_research_artifact_markdown,
    research_contract,
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
from gaia.engine.research.run import (
    RUN_MODES,
    ResearchRunStart,
    append_run_event,
    start_research_run,
    write_run_state,
)

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


def _read_json_object_path(path: Path) -> dict[str, object]:
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(2)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: file is not valid JSON: {path}: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(payload, dict):
        typer.echo(f"Error: file must contain a JSON object: {path}", err=True)
        raise typer.Exit(2)
    return payload


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
    artifact_only: bool,
    materialize_sources: bool = False,
    deep_materialization: bool = False,
) -> str:
    _ = materialize_sources
    if artifact_only:
        return "artifact_only"
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


def _materialize_landscape_sources_or_exit(
    research_pkg: ResearchPackage,
    landscape: dict[str, Any],
    *,
    landscape_artifact: Path,
    enabled: bool,
    artifact_only: bool,
    dry_run: bool,
) -> dict[str, object]:
    if not enabled or artifact_only or dry_run:
        return {
            "materialize_sources_enabled": bool(enabled),
            "source_package_materialization": False,
            "source_packages_written": [],
            "source_packages_added": [],
        }

    materialized = materialize_landscape_source_package(
        research_pkg,
        landscape,
        landscape_artifact=landscape_artifact,
    )
    if materialized is None:
        return {
            "materialize_sources_enabled": True,
            "source_package_materialization": False,
            "source_packages_written": [],
            "source_packages_added": [],
        }

    payload = materialized.to_payload()
    try:
        local_root = add_local_package_dependency(materialized.root, package_root=research_pkg.path)
    except GaiaPackagingError as exc:
        typer.echo(f"Error: failed to add generated source package: {exc}", err=True)
        typer.echo(f"Generated source package: {materialized.root}", err=True)
        raise typer.Exit(1) from exc

    added_payload = dict(payload)
    added_payload["path"] = str(local_root)
    attach_source_package_refs(landscape, [materialized])
    landscape_artifact.write_text(
        json.dumps(landscape, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "materialize_sources_enabled": True,
        "source_package_materialization": True,
        "source_packages_written": [payload],
        "source_packages_added": [added_payload],
    }


def _lkm_materialized_payload(
    materialized: Any,
    *,
    requested_ref: str | None = None,
) -> dict[str, object]:
    payload = {
        "requested_source_ref": requested_ref or str(materialized.source_ref),
        "source_ref": str(materialized.source_ref),
        "path": str(materialized.root),
        "package": str(materialized.dist_name),
        "import_name": str(materialized.import_name),
        "claim_count": int(materialized.claim_count),
        "question_count": int(materialized.question_count),
        "dependency_count": int(materialized.dependency_count),
    }
    chain_count = getattr(materialized, "chain_count", None)
    if isinstance(chain_count, int):
        payload["chain_count"] = chain_count
    total_chains = getattr(materialized, "total_chains", None)
    if isinstance(total_chains, int):
        payload["total_chains"] = total_chains
    return payload


def _materialize_lkm_papers_or_exit(
    research_pkg: ResearchPackage,
    *,
    paper_ids: list[str],
    claim_ids: list[str],
    chain_claim_ids: list[str],
    lkm_index: str,
    artifact_only: bool,
    dry_run: bool,
) -> dict[str, object]:
    requests = [*paper_ids, *claim_ids, *chain_claim_ids]
    if not requests or artifact_only or dry_run:
        return {
            "lkm_materialize_requests": requests,
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }

    materialized_packages = [
        *_materialize_lkm_paper_refs(
            research_pkg,
            paper_ids=paper_ids,
            lkm_index=lkm_index,
        ),
        *_materialize_lkm_claim_refs(
            research_pkg,
            claim_ids=claim_ids,
            lkm_index=lkm_index,
        ),
    ]
    materialized_chains = _materialize_lkm_chain_refs(
        research_pkg,
        claim_ids=chain_claim_ids,
        lkm_index=lkm_index,
    )
    return {
        "lkm_materialize_requests": requests,
        "lkm_packages_materialized": materialized_packages,
        "lkm_chains_materialized": materialized_chains,
    }


def _materialize_lkm_paper_refs(
    research_pkg: ResearchPackage,
    *,
    paper_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_packages: list[dict[str, object]] = []
    for paper_id in paper_ids:
        try:
            ref = make_lkm_paper_ref(lkm_index, paper_id)
            materialized = add_lkm_paper_dependency(ref, package_root=research_pkg.path)
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM paper package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM paper {paper_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_packages.append(_lkm_materialized_payload(materialized, requested_ref=ref.ref))
    return materialized_packages


def _materialize_lkm_claim_refs(
    research_pkg: ResearchPackage,
    *,
    claim_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_packages: list[dict[str, object]] = []
    for claim_id in claim_ids:
        try:
            ref = make_lkm_claim_ref(lkm_index, claim_id)
            materialized = add_lkm_claim_dependency(ref, package_root=research_pkg.path)
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM claim backing package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM claim {claim_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_packages.append(_lkm_materialized_payload(materialized, requested_ref=ref.ref))
    return materialized_packages


def _materialize_lkm_chain_refs(
    research_pkg: ResearchPackage,
    *,
    claim_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_chains: list[dict[str, object]] = []
    for claim_id in claim_ids:
        try:
            ref = make_lkm_claim_ref(lkm_index, claim_id)
            chain_materialized = add_lkm_chain_dependency(ref, package_root=research_pkg.path)
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM reasoning chain package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM chain {claim_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_chains.append(
            _lkm_materialized_payload(chain_materialized, requested_ref=ref.ref)
        )
    return materialized_chains


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
    append_research_event(research_pkg, "status.checked", {"artifact_only": True})

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
            help="Run mode: artifact_only, fast_package_native, deep, or external.",
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
            help="Run mode: artifact-only or fast-package-native.",
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
    research_pkg = _load_or_exit(pkg)
    _load_research_env_files_or_exit(env_file)
    broad_search_refs = list(search_json or [])
    broad_queries = list(query or [])
    targeted_search_refs = list(targeted_search_json or [])
    targeted_queries = list(targeted_query or [])
    can_auto_query_plan = analysis_provider == "litellm"
    try:
        run = start_research_run(
            research_pkg,
            topic=topic,
            mode=mode,
            language=language,
            profile=profile,
            run_id=run_id,
            wait_for_query_plan=not (broad_search_refs or broad_queries or can_auto_query_plan),
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    for event in run.events:
        if json_stream:
            typer.echo(json.dumps(event, ensure_ascii=False))

    broad_queries = _auto_plan_broad_queries_if_needed(
        research_pkg,
        run,
        topic=topic,
        language=language,
        profile=profile,
        analysis_provider=analysis_provider,
        model=model,
        existing_search_refs=broad_search_refs,
        existing_queries=broad_queries,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )

    if broad_queries:
        broad_search_refs.extend(
            _execute_live_searches(
                research_pkg,
                run,
                queries=broad_queries,
                prefix="broad",
                search_index=search_index,
                search_limit=search_limit,
                reasoning_only=reasoning_only,
                json_stream=json_stream,
            )
        )
    if not targeted_search_refs and targeted_queries:
        targeted_search_refs.extend(
            _execute_live_searches(
                research_pkg,
                run,
                queries=targeted_queries,
                prefix="targeted",
                search_index=search_index,
                search_limit=search_limit,
                reasoning_only=reasoning_only,
                json_stream=json_stream,
            )
        )

    if broad_search_refs:
        _execute_file_provider_run(
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
            assess_analysis_json=assess_analysis_json,
            analysis_provider=analysis_provider,
            model=model,
            focus_model=focus_model,
            assess_model=assess_model,
            llm_temperature=llm_temperature,
            llm_timeout=llm_timeout,
            llm_max_retries=llm_max_retries,
            llm_max_tokens=llm_max_tokens,
            report_section_concurrency=report_section_concurrency,
            search_index=search_index,
            search_limit=search_limit,
            reasoning_only=reasoning_only,
            focus_analysis_command=focus_analysis_command,
            assess_analysis_command=assess_analysis_command,
            json_stream=json_stream,
        )
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


def _run_state(run: ResearchRunStart) -> dict[str, Any]:
    return _read_json_object_path(run.state_path)


def _auto_plan_broad_queries_if_needed(
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
) -> list[str]:
    if existing_search_refs or existing_queries or analysis_provider != "litellm":
        return existing_queries
    resolved_model = _resolve_litellm_model(model)
    query_plan_json = _run_analysis_provider_litellm(
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
    return _queries_from_query_plan(_read_json_object_ref(query_plan_json, label="query-plan JSON"))


def _update_run_state(run: ResearchRunStart, updates: dict[str, Any]) -> dict[str, Any]:
    state = _run_state(run)
    state.update(updates)
    write_run_state(run.state_path, state)
    return state


def _emit_run_event(
    run: ResearchRunStart,
    *,
    event_type: str,
    phase: str,
    json_stream: bool,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = append_run_event(
        run.events_path,
        run_id=run.run_id,
        event_type=event_type,
        phase=phase,
        payload=payload,
    )
    if json_stream:
        typer.echo(json.dumps(event, ensure_ascii=False))
    return event


def _load_research_env_files_or_exit(env_file: list[str] | None) -> None:
    refs = _research_env_file_refs(env_file)
    for ref in refs:
        path = Path(ref).expanduser()
        if not path.exists():
            typer.echo(f"Error: --env-file not found: {ref}", err=True)
            raise typer.Exit(2)
        if not path.is_file():
            typer.echo(f"Error: --env-file is not a file: {ref}", err=True)
            raise typer.Exit(2)
        try:
            assignments = _parse_research_env_file(path)
        except ValueError as exc:
            typer.echo(f"Error: invalid --env-file {ref}: {exc}", err=True)
            raise typer.Exit(2) from exc
        for key, value in assignments.items():
            os.environ.setdefault(key, value)


def _research_env_file_refs(env_file: list[str] | None) -> list[str]:
    refs = [ref for ref in (env_file or []) if ref.strip()]
    if refs:
        return refs
    configured = os.environ.get("GAIA_RESEARCH_ENV_FILE")
    if configured:
        return [ref for ref in configured.split(os.pathsep) if ref.strip()]
    return []


def _parse_research_env_file(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"line {line_number} must be KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"line {line_number} has invalid key {key!r}")
        assignments[key] = _parse_env_value(value.strip())
    return assignments


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    comment_index = value.find(" #")
    if comment_index != -1:
        value = value[:comment_index].rstrip()
    return value


def _write_run_checkpoint(
    run: ResearchRunStart,
    *,
    phase: str,
    checkpoint_type: str,
    prompt: str,
    json_stream: bool,
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
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _update_run_state(
        run,
        {
            "status": "waiting_for_input",
            "phase": phase,
            "pending_checkpoint": str(checkpoint_path),
        },
    )
    _emit_run_event(
        run,
        event_type="checkpoint.created",
        phase=phase,
        json_stream=json_stream,
        payload={"path": str(checkpoint_path), "checkpoint_type": checkpoint_type},
    )
    _emit_run_event(
        run,
        event_type="run.waiting_for_input",
        phase=phase,
        json_stream=json_stream,
        payload={"pending_checkpoint": str(checkpoint_path)},
    )


def _record_run_cli_trace(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    start: float,
    name: str,
    mode: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, object] | None = None,
    model: str | None = None,
    token_usage: dict[str, int] | None = None,
    status: str = "ok",
) -> None:
    append_research_trace_step(
        research_pkg,
        run.run_dir / "trace",
        name=name,
        kind="cli",
        mode=mode,
        wall_seconds=perf_counter() - start,
        inputs=inputs,
        outputs=outputs,
        metrics=metrics,
        model=model,
        token_usage=token_usage,
        status=status,
    )


def _record_run_trace(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    start: float,
    name: str,
    kind: str,
    mode: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, object] | None = None,
    model: str | None = None,
    token_usage: dict[str, int] | None = None,
    status: str = "ok",
) -> None:
    append_research_trace_step(
        research_pkg,
        run.run_dir / "trace",
        name=name,
        kind=kind,
        mode=mode,
        wall_seconds=perf_counter() - start,
        inputs=inputs,
        outputs=outputs,
        metrics=metrics,
        model=model,
        token_usage=token_usage,
        status=status,
    )


def _execute_live_searches(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    queries: list[str],
    prefix: str,
    search_index: str,
    search_limit: int,
    reasoning_only: bool,
    json_stream: bool,
) -> list[str]:
    refs: list[str] = []
    searches_dir = run.run_dir / "searches"
    searches_dir.mkdir(parents=True, exist_ok=True)
    for index, query_text in enumerate(queries, start=1):
        output_path = searches_dir / f"{prefix}-{index:02d}.json"
        _emit_run_event(
            run,
            event_type="search.started",
            phase="live_search",
            json_stream=json_stream,
            payload={"query": query_text, "output": str(output_path), "prefix": prefix},
        )
        start = perf_counter()
        try:
            payload = _run_lkm_knowledge_search(
                query_text,
                index=search_index,
                limit=search_limit,
                reasoning_only=reasoning_only,
            )
        except typer.Exit:
            raise
        except Exception as exc:
            _update_run_state(
                run,
                {
                    "status": "failed",
                    "phase": "live_search",
                    "error": str(exc),
                },
            )
            _emit_run_event(
                run,
                event_type="run.failed",
                phase="live_search",
                json_stream=json_stream,
                payload={"query": query_text, "error": str(exc)},
            )
            typer.echo(f"Error: live LKM search failed for {query_text!r}: {exc}", err=True)
            raise typer.Exit(2) from exc
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        refs.append(str(output_path))
        results = payload.get("results")
        _record_run_trace(
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
        _emit_run_event(
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


def _run_lkm_knowledge_search(
    query: str,
    *,
    index: str,
    limit: int,
    reasoning_only: bool,
) -> dict[str, object]:
    from gaia.cli.commands.search._results import normalize_lkm_knowledge
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
    return normalize_lkm_knowledge(payload, query=query, kind="knowledge", index_id=index)


def _run_analysis_provider_command(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    phase: str,
    command: str,
    input_payload: dict[str, object],
    output_name: str,
    json_stream: bool,
) -> str:
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    input_path.write_text(
        json.dumps(input_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    args = shlex.split(command)
    if not args:
        typer.echo(f"Error: empty provider command for {phase}.", err=True)
        raise typer.Exit(2)
    env = {
        **os.environ,
        "GAIA_RESEARCH_PHASE": phase,
        "GAIA_RESEARCH_INPUT": str(input_path),
        "GAIA_RESEARCH_OUTPUT": str(output_path),
        "GAIA_RESEARCH_RUN_DIR": str(run.run_dir),
    }
    start = perf_counter()
    completed = subprocess.run(
        args,
        cwd=research_pkg.path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "").strip()
        _update_run_state(
            run,
            {
                "status": "failed",
                "phase": phase,
                "error": error or f"provider command exited {completed.returncode}",
            },
        )
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "command", "returncode": completed.returncode, "error": error},
        )
        typer.echo(
            f"Error: provider command failed for {phase} with exit code "
            f"{completed.returncode}: {error}",
            err=True,
        )
        raise typer.Exit(2)
    if not output_path.exists():
        typer.echo(
            f"Error: provider command for {phase} did not write {output_path}.",
            err=True,
        )
        raise typer.Exit(2)
    _read_json_object_path(output_path)
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.command.{phase}",
        kind="llm",
        mode="command",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "command",
            "phase": phase,
            "returncode": completed.returncode,
            "stdout_chars": len(completed.stdout or ""),
            "stderr_chars": len(completed.stderr or ""),
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={"provider": "command", "input": str(input_path), "output": str(output_path)},
    )
    return str(output_path)


def _run_analysis_provider_litellm(
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
    rate_limit_retry_count = 2
    rate_limit_retry_delay_seconds = 75.0
    analysis_dir = run.run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    input_path = analysis_dir / f"{output_name}.input.json"
    output_path = analysis_dir / f"{output_name}.output.json"
    raw_path = analysis_dir / f"{output_name}.raw.txt"
    hydrated_payload = _hydrate_analysis_provider_input(input_payload)
    input_path.write_text(
        json.dumps(hydrated_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _emit_run_event(
        run,
        event_type="provider.started",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    start = perf_counter()
    response: object | None = None
    retry_count = 0
    retry_wait_seconds = 0.0
    try:
        while True:
            try:
                response = asyncio.run(
                    _litellm_completion(
                        model=model,
                        phase=phase,
                        input_payload=hydrated_payload,
                        temperature=temperature,
                        timeout=timeout,
                        max_retries=max_retries,
                        max_tokens=max_tokens,
                    )
                )
                break
            except Exception as exc:
                if not _is_litellm_rate_limit_error(exc) or retry_count >= rate_limit_retry_count:
                    raise
                retry_count += 1
                retry_wait_seconds += rate_limit_retry_delay_seconds
                _emit_run_event(
                    run,
                    event_type="provider.retrying",
                    phase=phase,
                    json_stream=json_stream,
                    payload={
                        "provider": "litellm",
                        "model": model,
                        "reason": "rate_limit",
                        "attempt": retry_count,
                        "max_attempts": rate_limit_retry_count + 1,
                        "wait_seconds": rate_limit_retry_delay_seconds,
                        "error": str(exc),
                    },
                )
                sleep(rate_limit_retry_delay_seconds)
        content = _litellm_response_content(response)
        raw_path.write_text(content, encoding="utf-8")
        output_payload = _json_object_from_llm_content(content)
    except Exception as exc:
        usage = _litellm_usage_dict(response)
        prompt_tokens = _int_metric(usage.get("prompt_tokens"))
        completion_tokens = _int_metric(usage.get("completion_tokens"))
        _record_run_trace(
            research_pkg,
            run,
            start=start,
            name=f"provider.litellm.{phase}",
            kind="llm",
            mode="litellm",
            inputs=[str(input_path)],
            outputs=[str(raw_path)] if raw_path.exists() else [],
            metrics={
                "provider": "litellm",
                "phase": phase,
                "model": model,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_path": str(raw_path) if raw_path.exists() else None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": _int_metric(usage.get("total_tokens")),
                "request_id": _litellm_request_id(response),
                "retry_count": retry_count,
                "retry_wait_seconds": retry_wait_seconds,
            },
            model=model,
            token_usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
            status="failed",
        )
        _update_run_state(run, {"status": "failed", "phase": phase, "error": str(exc)})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase=phase,
            json_stream=json_stream,
            payload={"provider": "litellm", "model": model, "error": str(exc)},
        )
        typer.echo(f"Error: LiteLLM provider failed for {phase}: {exc}", err=True)
        raise typer.Exit(2) from exc
    output_path.write_text(
        json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    usage = _litellm_usage_dict(response)
    prompt_tokens = _int_metric(usage.get("prompt_tokens"))
    completion_tokens = _int_metric(usage.get("completion_tokens"))
    _record_run_trace(
        research_pkg,
        run,
        start=start,
        name=f"provider.litellm.{phase}",
        kind="llm",
        mode="litellm",
        inputs=[str(input_path)],
        outputs=[str(output_path)],
        metrics={
            "provider": "litellm",
            "phase": phase,
            "model": model,
            "raw_path": str(raw_path),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": _int_metric(usage.get("total_tokens")),
            "request_id": _litellm_request_id(response),
            "retry_count": retry_count,
            "retry_wait_seconds": retry_wait_seconds,
        },
        model=model,
        token_usage={
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    )
    _emit_run_event(
        run,
        event_type="provider.completed",
        phase=phase,
        json_stream=json_stream,
        payload={
            "provider": "litellm",
            "model": model,
            "input": str(input_path),
            "output": str(output_path),
        },
    )
    return str(output_path)


def _is_litellm_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "ratelimit" in text or "rate limit" in text or "tpm" in text


async def _litellm_completion(
    *,
    model: str,
    phase: str,
    input_payload: dict[str, object],
    temperature: float,
    timeout: float,
    max_retries: int,
    max_tokens: int | None,
) -> object:
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    litellm.suppress_debug_info = True
    litellm.disable_cost_calc = True
    kwargs: dict[str, object] = {
        "model": model,
        "messages": _litellm_messages(phase=phase, input_payload=input_payload),
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
        "response_format": {"type": "json_object"},
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return await litellm.acompletion(**kwargs)


def _litellm_messages(
    *,
    phase: str,
    input_payload: dict[str, object],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Gaia's deterministic JSON compiler for research artifacts. "
                "Return exactly one valid JSON object. The first non-whitespace "
                "character must be `{` and the last must be `}`. Do not include "
                "markdown, prose, XML, citations outside JSON, or code fences. Use "
                "only source refs and ids present in the input artifact payloads."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": phase,
                    "instruction": _litellm_phase_instruction(phase),
                    "output_shape": _litellm_output_shape(phase),
                    "validation_rules": [
                        "Return a single JSON object, not an array or string.",
                        "Do not add explanatory text before or after the JSON.",
                        "Do not add decorative or prose-only keys outside the requested shape.",
                        "Every source_refs entry must use ids present in artifact_payloads.",
                        "If evidence is weak, encode uncertainty inside JSON fields.",
                        "Prefer fewer high-quality grounded items over broad ungrounded output.",
                        (
                            "Keep strings compact; avoid LaTeX commands when Unicode "
                            "text is available."
                        ),
                    ],
                    "input": input_payload,
                },
                indent=2,
                ensure_ascii=False,
            ),
        },
    ]


def _litellm_phase_instruction(phase: str) -> str:
    if phase == "query_plan":
        return (
            "Generate 3-5 broad live-search queries for the topic. Cover distinct "
            "evidence families likely to support an autonomous review map: "
            "foundational theory, canonical models, methods/diagnostics, experiments "
            "where relevant, and recent controversies. Do not assess evidence yet."
        )
    if phase == "field_map_analysis":
        return (
            "Induce a review-oriented field map from the broad landscape before "
            "selecting narrow focuses. Build a taxonomy from primary retrieved "
            "evidence: model families, methods, observables, theory constraints, "
            "experimental systems, controversy axes, and coverage gaps. Recommend "
            "only the highest-value live-search expansions needed for review coverage."
        )
    if phase == "focus_analysis":
        return (
            "Select 1-4 assessable research focuses from the landscapes and field map. "
            "Each focus must be grounded in retrieved item ids, should fit into a "
            "field-map bucket or controversy axis, and should be narrow enough for "
            "immediate assessment."
        )
    if phase == "assess_analysis":
        return (
            "Assess only the selected focus against the selected evidence packet. "
            "Produce at most 5 grounded candidate relations, limitations, and next "
            "queries. Do not write the final review prose; later report phases will "
            "write the article from this judgment. Emit at most 2 deferred "
            "candidate obligations that directly follow from missing or conflicting "
            "evidence. Set obligation.actionable=true only for a near-term blocking "
            "task that should become an open inquiry obligation."
        )
    if phase == "report_plan":
        return (
            "Plan a scholarly evidence-review article from the field map, focus, "
            "selected evidence, and assessment judgment. Produce a concise section "
            "outline. Each section must have a stable id, title, purpose, and grounded "
            "evidence refs. Do not reassess evidence; preserve the assessment judgment."
        )
    if phase == "report_section":
        return (
            "Write exactly one article section from the section plan, selected evidence, "
            "section_evidence context, and assessment judgment. Use only refs and evidence "
            "records present in section_evidence. If section_evidence.missing_refs is not "
            "empty, explicitly describe that coverage gap instead of inventing details. Do "
            "not change the assessment conclusion. Return section markdown, not a full article."
        )
    if phase == "report_stitch":
        return (
            "Stitch section drafts into one academic evidence-review report. Add title, "
            "abstract, transitions, and conclusion. Remove repetition, keep citations as "
            "inline source refs, and do not add workflow or benchmark commentary."
        )
    return "Produce the contract-shaped JSON for this research phase."


def _litellm_output_shape(phase: str) -> dict[str, object]:
    if phase == "query_plan":
        return {
            "required_top_level_keys": ["queries"],
            "queries_item_shape": {"query": "search query text", "rationale": "why it helps"},
        }
    if phase == "field_map_analysis":
        return {
            "required_top_level_keys": [
                "domain_thesis",
                "buckets",
                "controversy_axes",
                "coverage_gaps",
                "recommended_expansions",
                "synthesis_notes",
            ],
            "buckets_item_keys": [
                "id",
                "title",
                "role",
                "required_for_review",
                "coverage_status",
                "evidence_refs",
                "recommended_queries",
            ],
            "coverage_gaps_item_keys": ["kind", "description", "recommended_queries"],
        }
    if phase == "focus_analysis":
        return {
            "required_top_level_keys": ["focuses", "coverage_gaps", "notes"],
            "focuses_item_keys": [
                "id",
                "kind",
                "status",
                "question",
                "rationale",
                "priority",
                "readiness",
                "scope",
                "coverage",
                "evidence_refs",
                "suggested_queries",
            ],
        }
    if phase == "assess_analysis":
        return {
            "required_top_level_keys": ["relations", "candidate_obligations"],
            "relations_item_keys": [
                "type",
                "claim",
                "rationale",
                "epistemic_status",
                "promotion_hint",
                "source_refs",
            ],
            "optional_judgment_keys": ["limitations", "next_queries"],
            "candidate_obligations_item_keys": [
                "kind",
                "content",
                "source_refs",
                "actionable",
            ],
        }
    if phase == "report_plan":
        return {
            "required_top_level_keys": [
                "title",
                "abstract",
                "thesis",
                "sections",
                "conclusion_prompt",
            ],
            "sections_item_keys": ["id", "title", "purpose", "evidence_refs"],
        }
    if phase == "report_section":
        return {
            "required_top_level_keys": ["section_id", "title", "markdown", "used_refs"],
            "markdown": "Markdown for exactly one report section. Start with a level-2 heading.",
        }
    if phase == "report_stitch":
        return {
            "required_top_level_keys": ["markdown"],
            "markdown": (
                "Complete final report Markdown with title, abstract, body, and conclusion."
            ),
        }
    return {"required_top_level_keys": []}


def _hydrate_analysis_provider_input(payload: dict[str, object]) -> dict[str, object]:
    hydrated = dict(payload)
    artifact_payloads: list[dict[str, object]] = []
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, str):
                continue
            path = Path(artifact)
            if path.exists():
                artifact_payloads.append(
                    {
                        "path": artifact,
                        "json": _read_json_object_path(path),
                    }
                )
    hydrated["artifact_payloads"] = artifact_payloads
    return hydrated


def _json_object_from_llm_content(content: str) -> dict[str, object]:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired_text = _escape_invalid_json_backslashes(text)
        try:
            payload = json.loads(repaired_text)
        except json.JSONDecodeError:
            raise ValueError(f"LiteLLM response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LiteLLM response must be a JSON object.")
    return payload


def _escape_invalid_json_backslashes(text: str) -> str:
    """Preserve LaTeX-style backslashes inside otherwise valid JSON strings."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)


def _litellm_response_content(response: object) -> str:
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    return "" if content is None else str(content)
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        return "" if content is None else str(content)
    return ""


def _litellm_usage_dict(response: object) -> dict[str, object]:
    usage = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    try:
        return dict(usage)
    except Exception:
        return {}


def _litellm_request_id(response: object) -> str | None:
    if isinstance(response, dict):
        value = response.get("id") or response.get("request_id")
        return str(value) if value else None
    for attr in ("id", "request_id"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return None


def _int_metric(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _resolve_litellm_model(model: str | None) -> str:
    resolved = model or os.environ.get("GAIA_RESEARCH_LLM_MODEL")
    if resolved and resolved.strip():
        return resolved.strip()
    typer.echo(
        "Error: --analysis-provider litellm requires --model or GAIA_RESEARCH_LLM_MODEL.",
        err=True,
    )
    raise typer.Exit(2)


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
        typer.echo("Error: query_plan output must contain a `queries` list.", err=True)
        raise typer.Exit(2)
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
        typer.echo("Error: query_plan output did not contain any non-empty queries.", err=True)
        raise typer.Exit(2)
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
) -> tuple[list[str], list[str]]:
    if targeted_search_json:
        return targeted_search_json, targeted_query
    queries = targeted_query or _suggested_queries_for_focus(focus_artifact, selected_focus)
    if not queries:
        return [], []
    search_refs = _execute_live_searches(
        research_pkg,
        run,
        queries=queries,
        prefix="targeted",
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        json_stream=json_stream,
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
    materialize_sources: bool,
    artifact_only: bool,
    focus_analysis_json: str | None,
    scan_landscape: dict[str, Any],
    scan_path: Path,
    json_stream: bool,
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
        model=_resolve_litellm_model(focus_model or model),
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        research_mode=research_mode,
        scan_landscape=scan_landscape,
        scan_path=scan_path,
        json_stream=json_stream,
    )
    state_artifacts = {"field_map": str(field_map_path)}
    coverage_queries = _coverage_queries_from_field_map(field_map_artifact)
    if not coverage_queries:
        return landscapes, landscape_paths, field_map_path, 0, state_artifacts

    coverage_search_json = _execute_live_searches(
        research_pkg,
        run,
        queries=coverage_queries,
        prefix="coverage",
        search_index=search_index,
        search_limit=search_limit,
        reasoning_only=reasoning_only,
        json_stream=json_stream,
    )
    coverage_path, coverage_landscape = _run_coverage_landscape_phase(
        research_pkg,
        run,
        coverage_search_json=coverage_search_json,
        coverage_queries=coverage_queries,
        field_map_path=field_map_path,
        research_mode=research_mode,
        materialize_sources=materialize_sources,
        artifact_only=artifact_only,
        json_stream=json_stream,
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
) -> tuple[Path, dict[str, Any]]:
    _update_run_state(run, {"phase": "field_map_analysis"})
    field_map_json = _run_analysis_provider_litellm(
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
    _update_run_state(run, {"phase": "field_map_sync"})
    _emit_run_event(
        run,
        event_type="phase.started",
        phase="field_map_sync",
        json_stream=json_stream,
        payload={"inputs": [str(scan_path), field_map_json]},
    )
    start = perf_counter()
    field_map_analysis = _read_json_object_ref(field_map_json, label="field-map JSON")
    field_map_artifact = build_field_map_artifact(
        topic=topic,
        landscapes=[scan_landscape],
        analysis=field_map_analysis,
        language=language,
    )
    field_map_path = write_research_artifact(
        research_pkg,
        "field_maps",
        "field-map",
        field_map_artifact,
    )
    append_research_event(
        research_pkg,
        "run.field_map_sync.completed",
        {
            "artifact": str(field_map_path),
            "buckets": len(field_map_artifact["buckets"]),
            "coverage_gaps": len(field_map_artifact["coverage_gaps"]),
            "recommended_expansions": len(field_map_artifact["recommended_expansions"]),
        },
    )
    _record_run_cli_trace(
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
    _emit_run_event(
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
    materialize_sources: bool,
    artifact_only: bool,
    json_stream: bool,
) -> tuple[Path, dict[str, Any]]:
    _update_run_state(run, {"phase": "explore_coverage"})
    _emit_run_event(
        run,
        event_type="phase.started",
        phase="explore_coverage",
        json_stream=json_stream,
        payload={"inputs": coverage_search_json, "field_map": str(field_map_path)},
    )
    start = perf_counter()
    coverage_landscape = build_research_landscape(
        _scan_batches(coverage_search_json, queries=coverage_queries, sources=[]),
        pull_budget=0,
    )
    coverage_landscape["action"] = "explore.coverage"
    coverage_landscape["target"] = {"kind": "field_map", "id": str(field_map_path)}
    coverage_path = write_research_artifact(
        research_pkg,
        "landscapes",
        "coverage",
        coverage_landscape,
    )
    coverage_source_payload = _materialize_landscape_sources_or_exit(
        research_pkg,
        coverage_landscape,
        landscape_artifact=coverage_path,
        enabled=materialize_sources,
        artifact_only=artifact_only,
        dry_run=False,
    )
    coverage_sync = sync_landscape_artifact(
        research_pkg,
        coverage_landscape,
        artifact_only=artifact_only,
        dry_run=False,
    )
    coverage_sync_payload = {**coverage_sync.to_payload(), **coverage_source_payload}
    append_research_event(
        research_pkg,
        "run.explore_coverage.completed",
        {
            "artifact": str(coverage_path),
            "target": {"kind": "field_map", "id": str(field_map_path)},
            "stats": coverage_landscape["stats"],
            **coverage_sync_payload,
        },
    )
    _record_run_cli_trace(
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
    _emit_run_event(
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


def _run_evidence_select_and_deep_expand(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    focus_artifact: dict[str, Any],
    selected_focus: str,
    landscapes: list[dict[str, Any]],
    landscape_paths: list[Path],
    lkm_index: str,
    artifact_only: bool,
    research_mode: str,
    json_stream: bool,
) -> tuple[Path, dict[str, Any]]:
    focus_payload = _focus_payload_for_selection(focus_artifact, selected_focus)
    _update_run_state(run, {"phase": "evidence_select"})
    _emit_run_event(
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
    )
    selected_evidence_path = write_research_artifact(
        research_pkg,
        "evidence",
        "selected-evidence",
        selected_evidence,
    )
    plan = cast(dict[str, list[str]], selected_evidence["materialization_plan"])
    selection = cast(dict[str, Any], selected_evidence["selection"])
    append_research_event(
        research_pkg,
        "run.evidence_select.completed",
        {
            "focus": selected_focus,
            "artifact": str(selected_evidence_path),
            "selection": selection,
            "materialization_plan": plan,
        },
    )
    _record_run_cli_trace(
        research_pkg,
        run,
        start=start,
        name="evidence.select",
        mode=research_mode,
        inputs=[str(path) for path in landscape_paths],
        outputs=[str(selected_evidence_path)],
        metrics={
            **selection,
            "paper_materialize_requests": len(plan["paper_ids"]),
            "chain_materialize_requests": len(plan["chain_claim_ids"]),
        },
    )
    _emit_run_event(
        run,
        event_type="phase.completed",
        phase="evidence_select",
        json_stream=json_stream,
        payload={
            "artifact": str(selected_evidence_path),
            "selection": selection,
            "materialization_plan": plan,
        },
    )

    _update_run_state(run, {"phase": "deep_expand"})
    _emit_run_event(
        run,
        event_type="phase.started",
        phase="deep_expand",
        json_stream=json_stream,
        payload={"focus": selected_focus, "artifact": str(selected_evidence_path), "plan": plan},
    )
    start = perf_counter()
    materialized = _materialize_lkm_papers_or_exit(
        research_pkg,
        paper_ids=list(plan["paper_ids"]),
        claim_ids=list(plan["claim_ids"]),
        chain_claim_ids=list(plan["chain_claim_ids"]),
        lkm_index=lkm_index,
        artifact_only=artifact_only,
        dry_run=False,
    )
    selected_evidence["materialization_result"] = materialized
    selected_evidence_path.write_text(
        json.dumps(selected_evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    append_research_event(
        research_pkg,
        "run.deep_expand.completed",
        {
            "focus": selected_focus,
            "artifact": str(selected_evidence_path),
            **materialized,
        },
    )
    _record_run_cli_trace(
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
    _emit_run_event(
        run,
        event_type="phase.completed",
        phase="deep_expand",
        json_stream=json_stream,
        payload={"artifact": str(selected_evidence_path), **materialized},
    )
    return selected_evidence_path, selected_evidence


def _report_provider_input(
    *,
    phase: str,
    topic: str,
    language: str,
    artifact_paths: list[Path],
    focus: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "type": "gaia.research.report_request",
        "phase": phase,
        "topic": topic,
        "language": language,
        "focus": focus,
        "artifacts": [str(path) for path in artifact_paths],
    }
    if extra:
        payload.update(extra)
    return payload


def _report_ref_key(ref: object) -> tuple[str, str] | None:
    if not isinstance(ref, dict):
        return None
    kind = ref.get("kind")
    if not isinstance(kind, str) or not kind:
        return None
    ref_id = ref.get("id") or ref.get("paper_id") or ref.get("ref")
    if isinstance(ref_id, int):
        ref_id = str(ref_id)
    if not isinstance(ref_id, str) or not ref_id:
        return None
    return kind, ref_id


def _report_section_ref_keys(section: dict[str, object]) -> list[tuple[str, str]]:
    refs = section.get("evidence_refs")
    if not isinstance(refs, list):
        return []
    keys: list[tuple[str, str]] = []
    for ref in refs:
        key = _report_ref_key(ref)
        if key is not None and key not in keys:
            keys.append(key)
    return keys


def _item_report_ref_keys(item: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    kind = item.get("kind")
    item_id = item.get("id")
    if isinstance(kind, str) and isinstance(item_id, str) and item_id:
        keys.add((kind, item_id))
        if kind == "variable":
            keys.add(("item", item_id))
    stable_item_id = item.get("item_id")
    if isinstance(stable_item_id, str) and stable_item_id:
        keys.add(("item", stable_item_id))
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    package_ref_payload = item.get("package_ref")
    package_ref = package_ref_payload.get("ref") if isinstance(package_ref_payload, dict) else None
    if isinstance(package_ref, str) and package_ref:
        keys.add(("package_ref", package_ref))
    return keys


def _paper_lead_report_ref_keys(lead: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    paper_id = lead.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    variable_ids = lead.get("variable_ids")
    if isinstance(variable_ids, list):
        for variable_id in variable_ids:
            if isinstance(variable_id, str) and variable_id:
                keys.add(("variable", variable_id))
    return keys


def _citation_report_ref_keys(citation: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    paper_id = citation.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        keys.add(("paper", paper_id))
    source_kind = citation.get("source_kind")
    source_id = citation.get("source_id")
    if isinstance(source_kind, str) and isinstance(source_id, str) and source_id:
        keys.add((source_kind, source_id))
    for field, kind in (("item_ids", "item"), ("variable_ids", "variable")):
        values = citation.get(field)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value:
                    keys.add((kind, value))
    return keys


def _relation_report_ref_keys(relation: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    source_refs = relation.get("source_refs")
    if not isinstance(source_refs, list):
        return keys
    for ref in source_refs:
        key = _report_ref_key(ref)
        if key is not None:
            keys.add(key)
    return keys


def _report_citation_from_item(item: dict[str, Any], citation_id: str) -> dict[str, Any]:
    source = item.get("source")
    source_payload = source if isinstance(source, dict) else {}
    paper_id = source_payload.get("paper_id")
    source_kind = (
        "paper" if isinstance(paper_id, str) and paper_id else str(item.get("kind") or "item")
    )
    citation: dict[str, Any] = {
        "id": citation_id,
        "source_kind": source_kind,
        "title": source_payload.get("paper_title") or item.get("title"),
        "doi": source_payload.get("doi"),
        "item_ids": [],
        "variable_ids": [],
    }
    stable_item_id = item.get("item_id") or item.get("id")
    if isinstance(stable_item_id, str) and stable_item_id:
        citation["item_ids"].append(stable_item_id)
    if item.get("kind") == "variable" and isinstance(item.get("id"), str):
        citation["variable_ids"].append(str(item["id"]))
    if isinstance(paper_id, str) and paper_id:
        citation["paper_id"] = paper_id
    elif isinstance(item.get("id"), str):
        citation["source_id"] = item["id"]
    return citation


def _report_citations_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        source = item.get("source")
        source_payload = source if isinstance(source, dict) else {}
        paper_id = source_payload.get("paper_id")
        if isinstance(paper_id, str) and paper_id:
            key = ("paper", paper_id)
        else:
            item_id = item.get("id") or item.get("item_id")
            if not isinstance(item_id, str) or not item_id:
                continue
            key = (str(item.get("kind") or "item"), item_id)
        citation = by_key.get(key)
        if citation is None:
            citation = _report_citation_from_item(item, f"section_citation_{len(citations) + 1}")
            by_key[key] = citation
            citations.append(citation)
            continue
        stable_item_id = item.get("item_id") or item.get("id")
        if isinstance(stable_item_id, str) and stable_item_id not in citation["item_ids"]:
            citation["item_ids"].append(stable_item_id)
        if (
            item.get("kind") == "variable"
            and isinstance(item.get("id"), str)
            and item["id"] not in citation["variable_ids"]
        ):
            citation["variable_ids"].append(item["id"])
    return citations


def _append_unique_dict(
    values: list[dict[str, Any]],
    value: dict[str, Any],
    *,
    seen: set[str],
) -> None:
    key = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if key in seen:
        return
    seen.add(key)
    values.append(dict(value))


def _append_unique_keyed_dict(
    values: list[dict[str, Any]],
    value: dict[str, Any],
    *,
    key: str,
    seen: set[str],
) -> None:
    if key in seen:
        return
    seen.add(key)
    values.append(dict(value))


def _item_report_dedupe_key(item: dict[str, Any]) -> str:
    kind = item.get("kind") or "item"
    source_id = item.get("id") or item.get("item_id")
    if isinstance(source_id, str) and source_id:
        return f"{kind}:{source_id}"
    source = item.get("source")
    paper_id = source.get("paper_id") if isinstance(source, dict) else None
    return (
        f"paper:{paper_id}"
        if isinstance(paper_id, str) and paper_id
        else json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _paper_lead_report_dedupe_key(lead: dict[str, Any]) -> str:
    paper_id = lead.get("paper_id")
    return (
        str(paper_id)
        if isinstance(paper_id, str) and paper_id
        else json.dumps(
            lead,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _artifact_evidence_packets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    evidence_packet = payload.get("evidence_packet")
    if isinstance(evidence_packet, dict):
        packets.append(evidence_packet)
    if payload.get("kind") in {"research_landscape", "selected_evidence"}:
        packets.append(payload)
    return packets


def _collect_matching_packet_records(
    packet: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    items: list[dict[str, Any]],
    paper_leads: list[dict[str, Any]],
    seen_items: set[str],
    seen_leads: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    packet_items = packet.get("items")
    if isinstance(packet_items, list):
        for item in packet_items:
            if not isinstance(item, dict):
                continue
            item_keys = _item_report_ref_keys(item)
            if item_keys.isdisjoint(ref_keys):
                continue
            matched.update(item_keys.intersection(ref_keys))
            _append_unique_keyed_dict(
                items,
                item,
                key=_item_report_dedupe_key(item),
                seen=seen_items,
            )

    packet_leads = packet.get("paper_leads")
    if isinstance(packet_leads, list):
        for lead in packet_leads:
            if not isinstance(lead, dict):
                continue
            lead_keys = _paper_lead_report_ref_keys(lead)
            if lead_keys.isdisjoint(ref_keys):
                continue
            matched.update(lead_keys.intersection(ref_keys))
            _append_unique_keyed_dict(
                paper_leads,
                lead,
                key=_paper_lead_report_dedupe_key(lead),
                seen=seen_leads,
            )
    return matched


def _collect_matching_relations(
    payload: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    relations: list[dict[str, Any]],
    seen_relations: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    payload_relations = payload.get("relations")
    if not isinstance(payload_relations, list):
        return matched
    for relation in payload_relations:
        if not isinstance(relation, dict):
            continue
        relation_keys = _relation_report_ref_keys(relation)
        if relation_keys.isdisjoint(ref_keys):
            continue
        matched.update(relation_keys.intersection(ref_keys))
        _append_unique_dict(relations, relation, seen=seen_relations)
    return matched


def _collect_matching_citations(
    payload: dict[str, Any],
    *,
    ref_keys: set[tuple[str, str]],
    citations: list[dict[str, Any]],
    seen_citations: set[str],
) -> set[tuple[str, str]]:
    matched: set[tuple[str, str]] = set()
    payload_citations = payload.get("citations")
    if not isinstance(payload_citations, list):
        return matched
    for citation in payload_citations:
        if not isinstance(citation, dict):
            continue
        citation_keys = _citation_report_ref_keys(citation)
        if citation_keys.isdisjoint(ref_keys):
            continue
        matched.update(citation_keys.intersection(ref_keys))
        _append_unique_dict(citations, citation, seen=seen_citations)
    return matched


def _collect_report_section_evidence(
    section: dict[str, object],
    *,
    artifact_paths: list[Path],
) -> dict[str, object]:
    ref_keys = set(_report_section_ref_keys(section))
    context: dict[str, object] = {
        "refs": [
            {"kind": kind, "id": ref_id} for kind, ref_id in _report_section_ref_keys(section)
        ],
        "items": [],
        "paper_leads": [],
        "relations": [],
        "citations": [],
        "missing_refs": [],
    }
    if not ref_keys:
        return context

    items = cast(list[dict[str, Any]], context["items"])
    paper_leads = cast(list[dict[str, Any]], context["paper_leads"])
    relations = cast(list[dict[str, Any]], context["relations"])
    citations = cast(list[dict[str, Any]], context["citations"])
    seen_items: set[str] = set()
    seen_leads: set[str] = set()
    seen_relations: set[str] = set()
    seen_citations: set[str] = set()
    matched_keys: set[tuple[str, str]] = set()

    for path in artifact_paths:
        if not path.exists():
            continue
        payload = _read_json_object_path(path)
        for packet in _artifact_evidence_packets(payload):
            matched_keys.update(
                _collect_matching_packet_records(
                    packet,
                    ref_keys=ref_keys,
                    items=items,
                    paper_leads=paper_leads,
                    seen_items=seen_items,
                    seen_leads=seen_leads,
                )
            )
        matched_keys.update(
            _collect_matching_relations(
                payload,
                ref_keys=ref_keys,
                relations=relations,
                seen_relations=seen_relations,
            )
        )
        matched_keys.update(
            _collect_matching_citations(
                payload,
                ref_keys=ref_keys,
                citations=citations,
                seen_citations=seen_citations,
            )
        )

    for citation in _report_citations_from_items(items):
        _append_unique_dict(citations, citation, seen=seen_citations)

    context["missing_refs"] = [
        {"kind": kind, "id": ref_id}
        for kind, ref_id in _report_section_ref_keys(section)
        if (kind, ref_id) not in matched_keys
    ]
    return context


def _sectioned_report_citations(section_contexts: list[dict[str, object]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for context in section_contexts:
        context_citations = context.get("citations", [])
        if not isinstance(context_citations, list):
            continue
        for citation in context_citations:
            if isinstance(citation, dict):
                _append_unique_dict(citations, citation, seen=seen)
    for index, citation in enumerate(citations, start=1):
        citation["id"] = f"report_citation_{index}"
    return citations


def _section_id(section: object, *, fallback: str) -> str:
    if isinstance(section, dict):
        raw = section.get("id")
        if isinstance(raw, str) and raw:
            return raw
    return fallback


def _safe_output_suffix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return safe[:80] or "section"


def _sections_from_report_plan(plan: dict[str, object]) -> list[dict[str, object]]:
    sections = plan.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _run_sectioned_report_writing(
    research_pkg: ResearchPackage,
    run: ResearchRunStart,
    *,
    topic: str,
    language: str,
    model: str,
    focus: str,
    field_map_path: Path | None,
    focus_path: Path,
    landscape_paths: list[Path],
    selected_evidence_path: Path | None,
    assessment_path: Path,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    json_stream: bool,
) -> tuple[str | None, list[str]]:
    artifact_paths = [
        *([field_map_path] if field_map_path is not None else []),
        focus_path,
        *([selected_evidence_path] if selected_evidence_path is not None else []),
        assessment_path,
    ]
    if selected_evidence_path is None:
        return None, []

    _update_run_state(run, {"phase": "report_plan"})
    report_plan_json = _run_analysis_provider_litellm(
        research_pkg,
        run,
        phase="report_plan",
        model=model,
        input_payload=_report_provider_input(
            phase="report_plan",
            topic=topic,
            language=language,
            artifact_paths=artifact_paths,
            focus=focus,
        ),
        output_name="report_plan",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    report_plan = _read_json_object_ref(report_plan_json, label="report-plan JSON")
    sections = _sections_from_report_plan(report_plan)
    section_contexts = [
        _collect_report_section_evidence(
            section,
            artifact_paths=[
                *landscape_paths,
                *artifact_paths,
                Path(report_plan_json),
            ],
        )
        for section in sections
    ]

    def write_section(index: int, section: dict[str, object], context: dict[str, object]) -> str:
        section_id = _section_id(section, fallback=f"section_{index}")
        output_name = f"report_section_{_safe_output_suffix(section_id)}"
        return _run_analysis_provider_litellm(
            research_pkg,
            run,
            phase="report_section",
            model=model,
            input_payload=_report_provider_input(
                phase="report_section",
                topic=topic,
                language=language,
                artifact_paths=[assessment_path, Path(report_plan_json)],
                focus=focus,
                extra={
                    "section_id": section_id,
                    "section": section,
                    "section_evidence": context,
                },
            ),
            output_name=output_name,
            temperature=llm_temperature,
            timeout=llm_timeout,
            max_retries=llm_max_retries,
            max_tokens=llm_max_tokens,
            json_stream=json_stream,
        )

    concurrency = max(1, report_section_concurrency)
    section_refs_by_index: dict[int, str] = {}
    if concurrency == 1 or len(sections) <= 1:
        for index, section in enumerate(sections, start=1):
            section_refs_by_index[index] = write_section(
                index,
                section,
                section_contexts[index - 1],
            )
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(sections))) as executor:
            futures = {
                executor.submit(write_section, index, section, section_contexts[index - 1]): index
                for index, section in enumerate(sections, start=1)
            }
            for future in as_completed(futures):
                section_refs_by_index[futures[future]] = future.result()

    section_refs = [section_refs_by_index[index] for index in range(1, len(sections) + 1)]
    section_paths = [Path(section_ref) for section_ref in section_refs]

    stitch_json = _run_analysis_provider_litellm(
        research_pkg,
        run,
        phase="report_stitch",
        model=model,
        input_payload=_report_provider_input(
            phase="report_stitch",
            topic=topic,
            language=language,
            artifact_paths=[assessment_path, Path(report_plan_json), *section_paths],
            focus=focus,
        ),
        output_name="report_stitch",
        temperature=llm_temperature,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
        max_tokens=llm_max_tokens,
        json_stream=json_stream,
    )
    stitch_payload = _read_json_object_ref(stitch_json, label="report-stitch JSON")
    markdown = stitch_payload.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None, [report_plan_json, *section_refs, stitch_json]
    rendered = render_markdown_with_research_citations(
        markdown.strip(),
        citations=_sectioned_report_citations(section_contexts),
        language=language,
    )
    return rendered, [report_plan_json, *section_refs, stitch_json]


def _maybe_run_sectioned_report_writing(
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
    selected_evidence_path: Path | None,
    assessment_path: Path,
    llm_temperature: float,
    llm_timeout: float,
    llm_max_retries: int,
    llm_max_tokens: int | None,
    report_section_concurrency: int,
    json_stream: bool,
) -> tuple[str | None, list[str]]:
    if analysis_provider != "litellm" or research_mode != "fast_package_native":
        return None, []
    return _run_sectioned_report_writing(
        research_pkg,
        run,
        topic=topic,
        language=language,
        model=_resolve_litellm_model(assess_model or model),
        focus=focus,
        field_map_path=field_map_path,
        focus_path=focus_path,
        landscape_paths=landscape_paths,
        selected_evidence_path=selected_evidence_path,
        assessment_path=assessment_path,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        report_section_concurrency=report_section_concurrency,
        json_stream=json_stream,
    )


def _execute_file_provider_run(
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
    focus_analysis_command: str | None,
    assess_analysis_command: str | None,
    json_stream: bool,
) -> None:
    artifact_only = mode == "artifact-only"
    materialize_sources = not artifact_only
    research_mode = _research_mode(
        artifact_only=artifact_only,
        materialize_sources=materialize_sources,
    )
    state_artifacts: dict[str, str] = {}
    state_metrics: dict[str, object] = {"searches": len(search_json) + len(targeted_search_json)}

    _update_run_state(run, {"status": "running", "phase": "explore_scan"})
    _emit_run_event(
        run,
        event_type="phase.started",
        phase="explore_scan",
        json_stream=json_stream,
        payload={"inputs": search_json},
    )
    start = perf_counter()
    scan_landscape = build_research_landscape(
        _scan_batches(search_json, queries=[], sources=[]),
        pull_budget=0,
    )
    scan_path = write_research_artifact(research_pkg, "landscapes", "scan", scan_landscape)
    source_payload = _materialize_landscape_sources_or_exit(
        research_pkg,
        scan_landscape,
        landscape_artifact=scan_path,
        enabled=materialize_sources,
        artifact_only=artifact_only,
        dry_run=False,
    )
    sync = sync_landscape_artifact(
        research_pkg,
        scan_landscape,
        artifact_only=artifact_only,
        dry_run=False,
    )
    sync_payload = {**sync.to_payload(), **source_payload}
    append_research_event(
        research_pkg,
        "run.explore_scan.completed",
        {"artifact": str(scan_path), "stats": scan_landscape["stats"], **sync_payload},
    )
    _record_run_cli_trace(
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
    _emit_run_event(
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
        materialize_sources=materialize_sources,
        artifact_only=artifact_only,
        focus_analysis_json=focus_analysis_json,
        scan_landscape=scan_landscape,
        scan_path=scan_path,
        json_stream=json_stream,
    )
    state_artifacts.update(field_map_artifacts)

    if focus_analysis_json is None:
        if analysis_provider == "command":
            if focus_analysis_command is None:
                typer.echo(
                    "Error: --analysis-provider command requires --focus-analysis-command "
                    "when --focus-analysis-json is omitted.",
                    err=True,
                )
                raise typer.Exit(2)
            focus_analysis_json = _run_analysis_provider_command(
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
            resolved_model = _resolve_litellm_model(focus_model or model)
            focus_analysis_json = _run_analysis_provider_litellm(
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
            )
            return

    _update_run_state(run, {"phase": "focus_sync"})
    _emit_run_event(
        run,
        event_type="phase.started",
        phase="focus_sync",
        json_stream=json_stream,
        payload={"inputs": [str(scan_path), focus_analysis_json]},
    )
    start = perf_counter()
    focus_analysis = _read_json_object_ref(focus_analysis_json, label="--focus-analysis-json")
    focus_artifact = build_focus_synthesis_artifact(
        landscapes=landscapes,
        analysis=focus_analysis,
        language=language,
    )
    focus_path = write_research_artifact(research_pkg, "focuses", "focuses", focus_artifact)
    focus_sync = sync_focus_artifact(
        research_pkg,
        focus_artifact,
        max_questions=3,
        artifact_only=artifact_only,
        dry_run=False,
    )
    focus_sync_payload = focus_sync.to_payload()
    append_research_event(
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
    _record_run_cli_trace(
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
    _emit_run_event(
        run,
        event_type="phase.completed",
        phase="focus_sync",
        json_stream=json_stream,
        payload={"artifact": str(focus_path), "focuses": len(focus_artifact["focuses"])},
    )
    selected_focus = (
        focus
        or (focus_sync_payload.get("focus_set") if isinstance(focus_sync_payload, dict) else None)
        or str(focus_artifact["focuses"][0]["id"])
    )

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
    )
    state_metrics["searches"] = len(search_json) + coverage_searches + len(targeted_search_json)

    if targeted_search_json:
        _update_run_state(run, {"phase": "explore_expand"})
        _emit_run_event(
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
            ),
            pull_budget=0,
        )
        expand_landscape["action"] = "explore.expand"
        expand_landscape["target"] = {"kind": "focus", "id": selected_focus}
        expand_path = write_research_artifact(
            research_pkg,
            "landscapes",
            "expand",
            expand_landscape,
        )
        expand_source_payload = _materialize_landscape_sources_or_exit(
            research_pkg,
            expand_landscape,
            landscape_artifact=expand_path,
            enabled=materialize_sources,
            artifact_only=artifact_only,
            dry_run=False,
        )
        expand_sync = sync_landscape_artifact(
            research_pkg,
            expand_landscape,
            artifact_only=artifact_only,
            dry_run=False,
        )
        expand_sync_payload = {**expand_sync.to_payload(), **expand_source_payload}
        append_research_event(
            research_pkg,
            "run.explore_expand.completed",
            {
                "artifact": str(expand_path),
                "target": {"kind": "focus", "id": selected_focus},
                "stats": expand_landscape["stats"],
                **expand_sync_payload,
            },
        )
        _record_run_cli_trace(
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
        state_artifacts["expand_landscape"] = str(expand_path)
        _emit_run_event(
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
            selected_focus=str(selected_focus),
            landscapes=landscapes,
            landscape_paths=landscape_paths,
            lkm_index=search_index,
            artifact_only=artifact_only,
            research_mode=research_mode,
            json_stream=json_stream,
        )
        state_artifacts["selected_evidence"] = str(selected_evidence_path)

    assessment_input_paths: list[Path] = (
        [selected_evidence_path] if selected_evidence_path is not None else landscape_paths
    )

    if assess_analysis_json is None:
        if analysis_provider == "command":
            if assess_analysis_command is None:
                typer.echo(
                    "Error: --analysis-provider command requires --assess-analysis-command "
                    "when --assess-analysis-json is omitted.",
                    err=True,
                )
                raise typer.Exit(2)
            assess_analysis_json = _run_analysis_provider_command(
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
                output_name="assess_analysis",
                json_stream=json_stream,
            )
        elif analysis_provider == "litellm":
            resolved_model = _resolve_litellm_model(assess_model or model)
            assess_analysis_json = _run_analysis_provider_litellm(
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
                output_name="assess_analysis",
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
            )
            return

    _update_run_state(run, {"phase": "assess_sync"})
    _emit_run_event(
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
    assess_analysis = _read_json_object_ref(assess_analysis_json, label="--assess-analysis-json")
    selected_evidence_packet = (
        selected_evidence_artifact.get("evidence_packet")
        if selected_evidence_artifact is not None
        else None
    )
    try:
        assessment = build_assessment_from_analysis(
            focus={"kind": "focus", "id": selected_focus},
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
        _update_run_state(run, {"status": "failed", "phase": "assess_sync", "error": str(exc)})
        _emit_run_event(
            run,
            event_type="run.failed",
            phase="assess_sync",
            json_stream=json_stream,
            payload={"error": str(exc)},
        )
        typer.echo(f"Error: invalid assessment artifact: {exc}", err=True)
        raise typer.Exit(2) from exc
    assessment_path = write_research_artifact(
        research_pkg,
        "assessments",
        "assessment",
        assessment,
    )
    assess_sync = sync_assessment_artifact(
        research_pkg,
        assessment,
        artifact_only=artifact_only,
        dry_run=False,
    )
    assess_sync_payload = assess_sync.to_payload()
    relation_counts = _relation_type_counts(assessment["relations"])
    append_research_event(
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
    _record_run_cli_trace(
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
    state_artifacts["assessment"] = str(assessment_path)
    _emit_run_event(
        run,
        event_type="phase.completed",
        phase="assess_sync",
        json_stream=json_stream,
        payload={"artifact": str(assessment_path), "relations": len(assessment["relations"])},
    )

    _update_run_state(run, {"phase": "reports_stop"})
    start = perf_counter()
    stop_payload = evaluate_research_stop(
        focus_artifact=focus_artifact,
        assessment=assessment,
        landscapes=[landscapes[-1]],
        previous_landscapes=landscapes[:-1],
    )
    stop_path = run.run_dir / "trace" / "stop.json"
    stop_path.write_text(
        json.dumps(stop_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _record_run_cli_trace(
        research_pkg,
        run,
        start=start,
        name="stop",
        mode="artifact_only",
        inputs=[str(focus_path), str(assessment_path), *[str(path) for path in landscape_paths]],
        outputs=[str(stop_path)],
        metrics={
            "recommendation": stop_payload.get("recommendation"),
            "should_stop": stop_payload.get("should_stop"),
            **dict(stop_payload.get("metrics") or {}),
        },
    )

    sectioned_markdown, sectioned_report_inputs = _maybe_run_sectioned_report_writing(
        research_pkg,
        run,
        topic=topic,
        language=language,
        analysis_provider=analysis_provider,
        research_mode=research_mode,
        model=model,
        assess_model=assess_model,
        focus=str(selected_focus),
        field_map_path=field_map_path,
        focus_path=focus_path,
        landscape_paths=landscape_paths,
        selected_evidence_path=selected_evidence_path,
        assessment_path=assessment_path,
        llm_temperature=llm_temperature,
        llm_timeout=llm_timeout,
        llm_max_retries=llm_max_retries,
        llm_max_tokens=llm_max_tokens,
        report_section_concurrency=report_section_concurrency,
        json_stream=json_stream,
    )

    _update_run_state(run, {"phase": "reports_stop"})
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
    final_report_path.write_text(final_markdown, encoding="utf-8")
    _record_run_cli_trace(
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
    _emit_run_event(
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

    benchmark_path = write_research_benchmark_summary(research_pkg, run.run_dir / "trace")
    append_research_event(
        research_pkg,
        "run.trace.summary.rebuilt",
        {"benchmark_summary": str(benchmark_path)},
    )
    state_artifacts["benchmark"] = str(benchmark_path)
    state_metrics.update(
        {
            "landscapes": len(landscapes),
            "relations": len(assessment["relations"]),
            "candidate_obligations": len(assessment["candidate_obligations"]),
        }
    )
    _update_run_state(
        run,
        {
            "status": "completed",
            "phase": "complete",
            "pending_checkpoint": None,
            "artifacts": state_artifacts,
            "metrics": state_metrics,
        },
    )
    _emit_run_event(
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
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only",
            help="Write only .gaia/research artifacts; skip inquiry/package sync.",
        ),
    ] = False,
    materialize_sources: Annotated[
        bool,
        typer.Option(
            "--materialize-sources/--no-materialize-sources",
            help=(
                "Materialize shallow search items as a local Gaia source package "
                "and add it with `gaia pkg add --local` semantics."
            ),
        ),
    ] = True,
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
            enabled=materialize_sources,
            artifact_only=artifact_only,
            dry_run=dry_run,
        )
        sync = sync_landscape_artifact(
            research_pkg,
            landscape,
            artifact_only=artifact_only,
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
            mode=_research_mode(
                artifact_only=artifact_only,
                materialize_sources=materialize_sources,
            ),
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
            enabled=materialize_sources,
            artifact_only=artifact_only,
            dry_run=dry_run,
        )
        sync = sync_landscape_artifact(
            research_pkg,
            landscape,
            artifact_only=artifact_only,
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
            mode=_research_mode(
                artifact_only=artifact_only,
                materialize_sources=materialize_sources,
            ),
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
            "artifact_only": artifact_only,
            "materialize_sources_enabled": materialize_sources,
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
        mode="artifact_only",
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
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only",
            help="Write only .gaia/research artifacts; skip inquiry/package sync.",
        ),
    ] = False,
    materialize_sources: Annotated[
        bool,
        typer.Option(
            "--materialize-sources/--no-materialize-sources",
            help=(
                "Materialize shallow search items as a local Gaia source package "
                "and add it with `gaia pkg add --local` semantics."
            ),
        ),
    ] = True,
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
        artifact_only=artifact_only,
        materialize_sources=materialize_sources,
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
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only",
            help="Write only .gaia/research artifacts; skip inquiry/package sync.",
        ),
    ] = False,
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
        artifact_only=artifact_only,
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
        mode=_research_mode(artifact_only=artifact_only),
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
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only/--write-source",
            help="Write only .gaia/research artifacts, or also sync review scaffolds.",
        ),
    ] = False,
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
        artifact_only=artifact_only,
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
            artifact_only=artifact_only,
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
                artifact_only=artifact_only,
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
        typer.echo(f"artifact_only: {str(artifact_only).lower()}")
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
            "artifact_only": artifact_only,
            "writes_source": False,
            "writes_inquiry": False,
            "relations": [],
            "promotion_hints": [],
            **lkm_materialize_payload,
        },
    )

    typer.echo("Research assess")
    typer.echo(f"focus: {focus}")
    typer.echo(f"artifact_only: {str(artifact_only).lower()}")
    typer.echo("writes_source: false")
    typer.echo("writes_inquiry: false")
    _record_trace_step(
        research_pkg,
        trace_dir,
        start=benchmark_start,
        name="assess.plan",
        mode=_research_mode(
            artifact_only=artifact_only,
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
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only",
            help="Write only .gaia/research artifacts; skip inquiry/package sync.",
        ),
    ] = False,
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
        artifact_only=(artifact_only or not accept),
        dry_run=dry_run,
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
        mode=_research_mode(artifact_only=(artifact_only or not accept)),
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
        mode=_research_mode(artifact_only=dry_run),
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
            mode="artifact_only",
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
        mode="artifact_only",
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
        mode="artifact_only",
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
