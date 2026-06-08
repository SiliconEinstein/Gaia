"""gaia review calibration — Δ_qid audit (posterior - prior ranking + honesty check)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer

from gaia.engine.review.calibration import run_calibration_review


def calibration_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
    top_k: int = typer.Option(20, "--top-k", "-k", help="Number of top deltas to show"),
    honesty: bool = typer.Option(False, "--honesty", help="Check git diff for prior changes"),
) -> None:
    """Run calibration audit — compute Δ = posterior - prior, rank by |Δ|.

    Steps:
      1. Run BP to get posteriors
      2. Extract priors from package
      3. Compute Δ = posterior - prior for each claim
      4. Sort by |Δ| descending
      5. Optional: git diff to check if priors changed after seeing posteriors

    Large |Δ| values (>0.15) indicate:
      - Evidence significantly updates belief
      - Prior may have been poorly calibrated
      - Potential for circular reasoning if prior was set after seeing evidence

    Exit codes:
      0  success
      1  user error
      2  system error

    Example:
        gaia review calibration
        gaia review calibration --top-k 10 --honesty
        gaia review calibration --format json > calibration.json
    """
    project_dir = Path(path).resolve()

    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_calibration_review(
            project_dir,
            top_k=top_k,
            check_git_honesty=honesty,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2) from e

    # Render
    if format == "json":
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return

    # Text format
    convergence_icon = "✓" if report.converged else "⚠"

    typer.echo("=" * 70)
    typer.echo(f"GAIA CALIBRATION REVIEW — {convergence_icon}")
    typer.echo("=" * 70)
    typer.echo(f"Path: {report.path}")
    typer.echo(f"Review ID: {report.review_id}")
    typer.echo(f"Created: {report.created_at}")
    typer.echo(f"Method: {report.method_used} ({'exact' if report.is_exact else 'approximate'})")
    typer.echo(f"Converged: {report.converged}")
    typer.echo(f"Iterations: {report.iterations}")
    typer.echo("")

    if not report.top_deltas:
        typer.echo("No deltas to report (no claims carry an explicit authored prior).")
    else:
        typer.echo(f"Top {len(report.top_deltas)} Belief Shifts (by |Δ|):")
        typer.echo("")

        for i, delta in enumerate(report.top_deltas, 1):
            # Flag large deltas
            flag = "⚠" if delta.abs_delta > 0.15 else " "

            typer.echo(f"  {i:2d}. {flag} {delta.claim_label[:40]:40} Δ={delta.delta:+.3f}")
            typer.echo(
                f"      Prior: {delta.prior:.3f}  →  Posterior: {delta.posterior:.3f}  "
                f"(|Δ|={delta.abs_delta:.3f})"
            )
            typer.echo("")

    # Honesty check
    if report.honesty_check:
        typer.echo("Honesty Check (git diff scan):")
        status = report.honesty_check.get("status", "unknown")
        message = report.honesty_check.get("message", "")

        if status == "suspicious":
            typer.echo(f"  ⚠ {message}")
            changes = report.honesty_check.get("changes", [])
            for change in changes[:5]:
                typer.echo(f"    {change}")
        else:
            typer.echo(f"  ✓ {message}")

        typer.echo("")

    typer.echo("=" * 70)
    typer.echo("Interpretation:")
    typer.echo("  |Δ| < 0.05  — Belief barely changed (prior well-calibrated or weak evidence)")
    typer.echo("  |Δ| 0.05-0.15 — Moderate update (expected for informative evidence)")
    typer.echo("  |Δ| > 0.15  — Large shift (check: was prior set after seeing evidence?)")
    typer.echo("=" * 70)
