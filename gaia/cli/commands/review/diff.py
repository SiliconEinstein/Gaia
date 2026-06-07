"""gaia review diff — compare current package state with an inquiry snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.diff import run_diff_review


def diff_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    since: str | None = typer.Option(
        "last",
        "--since",
        help="Baseline inquiry review id, 'last', or 'none'",
    ),
    no_infer: bool = typer.Option(True, "--no-infer/--infer", help="Skip BP inference"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Run semantic diff against a previous inquiry review snapshot."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_diff_review(project_dir, since=since, no_infer=no_infer)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    render_review_report(report, format=format)
    if report.status == "error":
        raise typer.Exit(1)
