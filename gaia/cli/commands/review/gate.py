"""gaia review gate — run composed review gates."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.gate import GateName, run_gate_review

_GATE_ARGUMENT = typer.Argument(
    ...,
    help="Gate to run: candidate, calibration, completeness, or audit",
)


def gate_command(
    gate: GateName = _GATE_ARGUMENT,
    path: str = typer.Argument(".", help="Path to Gaia package"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Run a composed review gate and return pass/warning/error status."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_gate_review(project_dir, gate)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    render_review_report(report, format=format)
    if report.status == "error":
        raise typer.Exit(1)
