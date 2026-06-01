"""``gaia research`` — package-native research action skeleton."""

from __future__ import annotations

from typing import Annotated

import typer

from gaia.engine.research import (
    ResearchPackage,
    ResearchTargetError,
    append_research_event,
    ensure_research_manifest,
    load_research_package,
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
) -> None:
    """Plan an artifact-only Explore action."""
    if mode != "scan":
        typer.echo("Error: M1 supports only `--mode scan`.", err=True)
        raise typer.Exit(2)
    if not dry_run:
        typer.echo("Error: M1 explore requires `--dry-run`.", err=True)
        raise typer.Exit(2)

    research_pkg = _load_or_exit(pkg)
    ensure_research_manifest(research_pkg)
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
