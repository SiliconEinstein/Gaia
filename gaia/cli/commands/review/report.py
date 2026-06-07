"""gaia review report — human-readable review report rendering."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Literal

import typer

from gaia.engine.review._schemas import ReviewFinding, ReviewReport
from gaia.engine.review.orchestrator import run_package_review


def _finding_markdown(finding: ReviewFinding) -> str:
    return (
        f"- **{finding.severity.value}** `{finding.category}` "
        f"`{finding.location}`: {finding.message}"
    )


def _render_markdown(report: ReviewReport) -> str:
    lines = [
        f"# Gaia Review Report: {report.status.upper()}",
        "",
        f"- Type: `{report.review_type}`",
        f"- Path: `{report.path}`",
        f"- Review ID: `{report.review_id}`",
        f"- Created: `{report.created_at}`",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        "## Findings",
        "",
    ]
    if report.findings:
        lines.extend(_finding_markdown(finding) for finding in report.findings)
    else:
        lines.append("No findings.")
    lines.append("")
    if report.recommendations:
        lines.extend(["## Recommendations", ""])
        for recommendation in report.recommendations:
            lines.append(
                f"- **{recommendation.priority}** `{recommendation.action}` "
                f"for `{recommendation.target}`: {recommendation.rationale}"
            )
        lines.append("")
    return "\n".join(lines)


def _render_html(report: ReviewReport) -> str:
    markdown = _render_markdown(report)
    body = "\n".join(
        f"<p>{html.escape(line)}</p>" if line else "" for line in markdown.splitlines()
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>Gaia Review Report</title></head>'
        f"<body>{body}</body></html>\n"
    )


def _write_or_print(content: str, output: str | None) -> None:
    if output is None:
        typer.echo(content)
        return
    Path(output).write_text(content, encoding="utf-8")
    typer.echo(f"Saved review report to {output}")


def report_command(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    format: Literal["markdown", "html", "json"] = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, html, or json"
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="Optional output path"),
    no_infer: bool = typer.Option(False, "--no-infer", help="Skip BP inference"),
) -> None:
    """Render a human-readable package review report."""
    project_dir = Path(path).resolve()
    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        report = run_package_review(project_dir, skip_inference=no_infer)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    if format == "json":
        content = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    elif format == "html":
        content = _render_html(report)
    else:
        content = _render_markdown(report)
    _write_or_print(content, output)

    if report.status == "error":
        raise typer.Exit(1)
