"""gaia review red-team — adversarial heuristic review."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.redteam import run_redteam_review


def red_team_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    node: str | None = typer.Option(None, "--node", help="Optional node ID or label to attack"),
    backend: str = typer.Option(
        "heuristic", "--backend", help="Backend to use. Currently only: heuristic"
    ),
    solution: str | None = typer.Option(
        None, "--solution", help="Optional solution artifact to scan"
    ),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Run adversarial review over a package, node, or solution artifact."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_redteam_review(
            project_dir,
            target=node,
            backend=backend,
            solution=solution,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    render_review_report(report, format=format)
    if report.status == "error":
        raise typer.Exit(1)
