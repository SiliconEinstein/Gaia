"""``gaia research`` — package-native research action skeleton."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from gaia.engine.research import (
    ResearchPackage,
    ResearchTargetError,
    ScanBatch,
    append_research_event,
    build_research_landscape,
    ensure_research_manifest,
    load_research_package,
    write_research_artifact,
)

research_app = typer.Typer(
    name="research",
    help="Package-native research actions (explore / assess / propose).",
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
        typer.Option("--mode", help="Explore mode. M1 supports only 'scan'."),
    ] = "scan",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan the scan without pulling papers or writing source."),
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
) -> None:
    """Plan an artifact-only Explore action."""
    if mode != "scan":
        typer.echo("Error: M1 supports only `--mode scan`.", err=True)
        raise typer.Exit(2)
    search_refs = list(search_json or [])
    if not search_refs and not dry_run:
        typer.echo("Error: M1 explore requires `--dry-run`.", err=True)
        raise typer.Exit(2)

    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    if search_refs:
        queries = list(query or [])
        sources = list(source or [])
        batches: list[ScanBatch] = []
        for index, ref in enumerate(search_refs):
            payload, path_label = _read_search_json(ref)
            batches.append(
                ScanBatch(
                    search_results=payload,
                    query=queries[index] if index < len(queries) else None,
                    source_qid=sources[index] if index < len(sources) else None,
                    path=path_label,
                )
            )
        landscape = build_research_landscape(batches, pull_budget=0)
        output_path = write_research_artifact(
            research_pkg,
            "landscapes",
            "scan",
            landscape,
            out=out,
        )
        append_research_event(
            research_pkg,
            "explore.scan.completed",
            {
                "mode": "scan",
                "artifact": str(output_path),
                "stats": landscape["stats"],
                "pull_budget": 0,
                "writes_source": False,
                "writes_focus_registry": False,
                "writes_obligation_ledger": False,
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
        typer.echo("candidate_focuses: artifact-local only")
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
            "writes_focus_registry": False,
            "writes_obligation_ledger": False,
        },
    )

    typer.echo("Research explore")
    typer.echo("mode: scan")
    typer.echo("dry_run: true")
    typer.echo("pull_budget: 0")
    typer.echo("writes_source: false")
    typer.echo("candidate_focuses: artifact-local only")
    _print_inquiry_suggestions(research_pkg)


@research_app.command("assess")
def assess_command(
    pkg: Annotated[str, typer.Argument(help="Path to an existing Gaia package.")],
    focus: Annotated[str, typer.Option("--focus", help="Focus, QID, or obligation target.")],
    artifact_only: Annotated[
        bool,
        typer.Option(
            "--artifact-only/--write-source",
            help="M1 supports only artifact-only assessment planning.",
        ),
    ] = True,
) -> None:
    """Plan an artifact-only Assess action."""
    if not artifact_only:
        typer.echo("Error: M1 assess supports only `--artifact-only`.", err=True)
        raise typer.Exit(2)

    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
    append_research_event(
        research_pkg,
        "assess.planned",
        {
            "focus": focus,
            "artifact_only": True,
            "writes_source": False,
            "relations": [],
            "promotion_hints": [],
        },
    )

    typer.echo("Research assess")
    typer.echo(f"focus: {focus}")
    typer.echo("artifact_only: true")
    typer.echo("writes_source: false")
    _print_inquiry_suggestions(research_pkg)


__all__ = ["research_app"]
