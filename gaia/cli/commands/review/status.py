"""gaia review status — read-only status overview across review layers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.status import run_status_review


def status_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Show a quick read-only status overview for a Gaia package."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_status_review(project_dir)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    render_review_report(report, format=format)
    if report.status == "error":
        raise typer.Exit(1)
