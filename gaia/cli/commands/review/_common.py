"""Common utilities for gaia review CLI commands — report rendering and helpers."""

from __future__ import annotations

import json
from typing import Literal

import typer

from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity


def render_review_report(
    report: ReviewReport,
    format: Literal["text", "json"] = "text",
) -> None:
    """Render ReviewReport to stdout in text or JSON format.

    Args:
        report: ReviewReport to render
        format: Output format (text or json)
    """
    if format == "json":
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return

    # Text format
    _render_text_header(report)
    _render_text_findings(report)
    _render_text_recommendations(report)
    _render_text_footer(report)


def _render_text_header(report: ReviewReport) -> None:
    """Render report header in text format."""
    status_icon = {
        "pass": "✓",
        "warning": "⚠",
        "error": "✗",
    }
    icon = status_icon.get(report.status, "·")

    typer.echo("=" * 70)
    typer.echo(f"GAIA REVIEW REPORT — {icon} {report.status.upper()}")
    typer.echo("=" * 70)
    typer.echo(f"Type: {report.review_type}")
    typer.echo(f"Path: {report.path}")
    typer.echo(f"Review ID: {report.review_id}")
    typer.echo(f"Created: {report.created_at}")
    typer.echo("")
    typer.echo(f"Summary: {report.summary}")
    typer.echo("")


def _render_text_findings(report: ReviewReport) -> None:
    """Render findings in text format."""
    if not report.findings:
        typer.echo("No findings.")
        typer.echo("")
        return

    # Group by severity
    errors = [f for f in report.findings if f.severity == ReviewSeverity.ERROR]
    warnings = [f for f in report.findings if f.severity == ReviewSeverity.WARNING]
    infos = [f for f in report.findings if f.severity == ReviewSeverity.INFO]

    if errors:
        typer.echo(f"Errors ({len(errors)}):")
        for i, finding in enumerate(errors, 1):
            _render_finding(i, finding)
        typer.echo("")

    if warnings:
        typer.echo(f"Warnings ({len(warnings)}):")
        for i, finding in enumerate(warnings, 1):
            _render_finding(i, finding)
        typer.echo("")

    if infos:
        typer.echo(f"Info ({len(infos)}):")
        for i, finding in enumerate(infos, 1):
            _render_finding(i, finding)
        typer.echo("")


def _render_finding(index: int, finding: ReviewFinding) -> None:
    """Render single finding."""
    severity_icon = {
        ReviewSeverity.ERROR: "✗",
        ReviewSeverity.WARNING: "⚠",
        ReviewSeverity.INFO: "i",
        ReviewSeverity.PASS: "✓",
    }
    icon = severity_icon.get(finding.severity, "·")

    typer.echo(f"  {index}. {icon} [{finding.category}] {finding.location}")
    typer.echo(f"     {finding.message}")
    if finding.detector:
        typer.echo(f"     Detector: {finding.detector}")


def _render_text_recommendations(report: ReviewReport) -> None:
    """Render recommendations in text format."""
    if not report.recommendations:
        return

    typer.echo(f"Recommendations ({len(report.recommendations)}):")
    for i, rec in enumerate(report.recommendations, 1):
        priority_icon = {"high": "!", "medium": "·", "low": "-"}
        icon = priority_icon.get(rec.priority, "·")

        typer.echo(f"  {i}. {icon} [{rec.priority}] {rec.action}")
        typer.echo(f"     Target: {rec.target}")
        typer.echo(f"     {rec.rationale}")
        if rec.example:
            typer.echo(f"     Example: {rec.example}")
    typer.echo("")


def _render_text_footer(report: ReviewReport) -> None:
    """Render report footer in text format."""
    typer.echo("=" * 70)
    if report.metadata:
        typer.echo("Metadata:")
        for key, value in report.metadata.items():
            typer.echo(f"  {key}: {value}")
        typer.echo("=" * 70)
