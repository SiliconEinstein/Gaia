"""gaia review query — structured reviewer queries."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.query import QueryKind, run_query_review

_QUERY_ARGUMENT = typer.Argument(
    ...,
    help="Query to run: weakest-claims, missing-priors, large-deltas, or unreviewed",
)


def query_command(
    query: QueryKind = _QUERY_ARGUMENT,
    path: str = typer.Argument(".", help="Path to Gaia package"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Maximum findings to return"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Run a structured query over review artifacts."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_query_review(project_dir, query, top_k=top_k)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    render_review_report(report, format=format)
    if report.status == "error":
        raise typer.Exit(1)
