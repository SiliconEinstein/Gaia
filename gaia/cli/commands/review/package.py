"""gaia review package — run complete package review (inquiry + trace + calibration)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from gaia.cli.commands.review._common import render_review_report
from gaia.engine.review.orchestrator import run_package_review


def package_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
    no_infer: bool = typer.Option(
        False, "--no-infer", help="Skip BP inference (also skips calibration, which runs BP)"
    ),
    no_calibration: bool = typer.Option(False, "--no-calibration", help="Skip calibration delta"),
    no_trace: bool = typer.Option(False, "--no-trace", help="Skip trace review"),
) -> None:
    """Run comprehensive package review (inquiry + trace + calibration).

    Orchestrates:
      1. inquiry.review.run_review() — 8-section semantic review
      2. trace.review.run_trace_review() — ARM trace if exists
      3. engine.review.calibration — Δ_qid computation

    Merges findings into unified ReviewReport format.

    Exit codes:
      0  pass / warning
      1  error (blocking findings)
      2  system error (compilation failed)

    Example:
        gaia review package
        gaia review package ./my-pkg --format json
        gaia review package ./my-pkg --no-infer --no-calibration
    """
    project_dir = Path(path).resolve()

    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_package_review(
            project_dir,
            skip_inference=no_infer,
            skip_calibration=no_calibration,
            skip_trace=no_trace,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2) from e

    render_review_report(report, format=format)

    if report.status == "error":
        raise typer.Exit(1)
