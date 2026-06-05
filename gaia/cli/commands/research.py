"""``gaia research`` — package-native research action skeleton."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from gaia.cli.commands.add import (
    LKMDependencyAddError,
    add_lkm_paper_dependency,
    add_local_package_dependency,
    make_lkm_paper_ref,
)
from gaia.cli.commands.search.lkm._indexes import DEFAULT_LKM_INDEX_ID
from gaia.engine.packaging import GaiaPackagingError
from gaia.engine.research import (
    ResearchPackage,
    ResearchReportError,
    ResearchTargetError,
    ScanBatch,
    append_research_event,
    attach_source_package_refs,
    build_assessment_from_analysis,
    build_assessment_from_landscapes,
    build_focus_synthesis_artifact,
    build_research_landscape,
    ensure_research_manifest,
    evaluate_research_stop,
    load_research_package,
    materialize_landscape_source_package,
    render_research_artifact_markdown,
    research_contract,
    sync_assessment_artifact,
    sync_focus_artifact,
    sync_landscape_artifact,
    sync_materialization,
    write_research_artifact,
)

research_app = typer.Typer(
    name="research",
    help="Package-native research actions (explore / assess / promote).",
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


def _split_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _print_sync_summary(payload: dict[str, object]) -> None:
    typer.echo(f"writes_source: {str(payload.get('writes_source')).lower()}")
    typer.echo(f"writes_inquiry: {str(payload.get('writes_inquiry')).lower()}")
    for key in (
        "source_packages_written",
        "source_packages_added",
        "lkm_packages_pulled",
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


def _lkm_materialized_payload(materialized: Any) -> dict[str, object]:
    return {
        "source_ref": str(materialized.source_ref),
        "path": str(materialized.root),
        "package": str(materialized.dist_name),
        "import_name": str(materialized.import_name),
        "claim_count": int(materialized.claim_count),
        "question_count": int(materialized.question_count),
        "dependency_count": int(materialized.dependency_count),
    }


def _pull_lkm_papers_or_exit(
    research_pkg: ResearchPackage,
    *,
    paper_ids: list[str],
    lkm_index: str,
    artifact_only: bool,
    dry_run: bool,
) -> dict[str, object]:
    if not paper_ids or artifact_only or dry_run:
        return {
            "lkm_pull_requests": list(paper_ids),
            "lkm_packages_pulled": [],
        }

    pulled: list[dict[str, object]] = []
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
            typer.echo(f"Error: failed to pull LKM paper {paper_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        pulled.append(_lkm_materialized_payload(materialized))
    return {
        "lkm_pull_requests": list(paper_ids),
        "lkm_packages_pulled": pulled,
    }


@research_app.command("contract")
def contract_command(
    kind: Annotated[str, typer.Argument(help="Contract to print: focus or assess.")],
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
) -> None:
    """Run a breadth-first Explore scan or targeted expansion."""
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
) -> None:
    """Synthesize assessment-ready research focuses from landscape artifacts."""
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
    pull_paper: Annotated[
        list[str] | None,
        typer.Option(
            "--pull-paper",
            help="Materialize this LKM paper id as a deep evidence package before assessment.",
        ),
    ] = None,
    lkm_index: Annotated[
        str,
        typer.Option(
            "--lkm-index",
            "--lkm-server",
            help="Configured LKM index id for --pull-paper.",
        ),
    ] = DEFAULT_LKM_INDEX_ID,
) -> None:
    """Assess one focus and sync review scaffolds into package/inquiry state."""
    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    lkm_pull_payload = _pull_lkm_papers_or_exit(
        research_pkg,
        paper_ids=list(pull_paper or []),
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
            assessment = build_assessment_from_landscapes(
                focus={"kind": "focus", "id": focus},
                landscapes=landscapes,
            )
        else:
            assessment = build_assessment_from_analysis(
                focus={"kind": "focus", "id": focus},
                landscapes=landscapes,
                analysis=analysis,
                strict_grounding=strict_grounding,
            )
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
        sync_payload = {**sync.to_payload(), **lkm_pull_payload}
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
            **lkm_pull_payload,
        },
    )

    typer.echo("Research assess")
    typer.echo(f"focus: {focus}")
    typer.echo(f"artifact_only: {str(artifact_only).lower()}")
    typer.echo("writes_source: false")
    typer.echo("writes_inquiry: false")
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
) -> None:
    """Record a narrow scaffold-to-formal-knowledge materialization link."""
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
) -> None:
    """Render a research artifact as readable Markdown."""
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
        return

    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    append_research_event(
        research_pkg,
        "report.rendered",
        {"artifact": str(artifact_path), "out": str(output_path), "writes_source": False},
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
) -> None:
    """Evaluate auditable stop criteria for the current research-loop state."""
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
