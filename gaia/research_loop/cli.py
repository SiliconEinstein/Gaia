"""``gaia-research-loop`` command-line interface."""

from __future__ import annotations

import json

import typer

from gaia.research_loop.engine import (
    emit_task,
    gate_payload,
    next_payload,
    status_payload,
    submit_candidate,
)
from gaia.research_loop.schemas import TaskKind

app = typer.Typer(
    name="gaia-research-loop",
    help="Gaia Research Loop — agent-facing Explore -> Assess protocol.",
    no_args_is_help=True,
)

_PKG_ARG = typer.Argument(..., help="Knowledge-package path.")
_JSON_OPT = typer.Option(False, "--json", help="Emit JSON.")
_STAGE_OPT = typer.Option("explore", "--stage", help="Loop stage to gate.")
task_app = typer.Typer(help="Emit one task envelope without running the full loop.")
app.add_typer(task_app, name="task")


@app.callback()
def main() -> None:
    """Run Gaia research loop commands."""


@app.command("status")
def status_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Show or rebuild research loop state."""
    payload = status_payload(pkg)
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Research loop: {payload['phase']}")
    typer.echo(f"Root: {payload['root']}")
    typer.echo(f"Events: {payload['event_count']}")
    typer.echo(f"Next: {payload['recommended_next']} {pkg}")


@app.command("next")
def next_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit the next task envelope."""
    payload = next_payload(pkg)
    _echo_task_payload(payload, json_out)


@app.command("submit")
def submit_command(
    pkg: str = _PKG_ARG,
    candidate: str = typer.Argument(..., help="Candidate JSON path."),
    json_out: bool = _JSON_OPT,
) -> None:
    """Validate and submit a candidate JSON file."""
    try:
        payload = submit_candidate(pkg, candidate)
    except Exception as exc:
        if json_out:
            typer.echo(json.dumps({"status": "rejected", "error": str(exc)}, indent=2))
        else:
            typer.echo(f"Rejected: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Accepted: {payload['artifact_path']}")


@app.command("gate")
def gate_command(
    pkg: str = _PKG_ARG,
    stage: str = _STAGE_OPT,
    json_out: bool = _JSON_OPT,
) -> None:
    """Run a stage gate."""
    try:
        payload = gate_payload(pkg, stage=stage)
    except Exception as exc:
        if json_out:
            typer.echo(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        else:
            typer.echo(f"Gate error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"{stage}: {payload['status']}")


def _echo_task_payload(payload: dict[str, object], json_out: bool) -> None:
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Recommended: {payload['recommended_action']}")
    if payload.get("task_path") is not None:
        typer.echo(f"Task: {payload['task_path']}")
    if payload.get("submit_command") is not None:
        typer.echo(f"Submit: {payload['submit_command']}")


@task_app.command("scope")
def task_scope_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a scope task envelope without consulting loop state."""
    payload = emit_task(pkg, kind=TaskKind.SCOPE)
    _echo_task_payload(payload, json_out)


@task_app.command("query-plan")
def task_query_plan_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a query planning task envelope from the current scope artifact."""
    payload = emit_task(pkg, kind=TaskKind.QUERY_PLAN)
    _echo_task_payload(payload, json_out)


@task_app.command("search-execution")
def task_search_execution_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a search execution task envelope from the current query plan."""
    payload = emit_task(pkg, kind=TaskKind.SEARCH_EXECUTION)
    _echo_task_payload(payload, json_out)


@task_app.command("focus-synthesis")
def task_focus_synthesis_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a focus synthesis task envelope from the current landscape."""
    payload = emit_task(pkg, kind=TaskKind.FOCUS_SYNTHESIS)
    _echo_task_payload(payload, json_out)


@task_app.command("assessment-context")
def task_assessment_context_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit an assessment context task envelope from selected focuses."""
    payload = emit_task(pkg, kind=TaskKind.ASSESSMENT_CONTEXT)
    _echo_task_payload(payload, json_out)


@task_app.command("evidence-diagnosis")
def task_evidence_diagnosis_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit an evidence diagnosis task envelope from assessment context."""
    payload = emit_task(pkg, kind=TaskKind.EVIDENCE_DIAGNOSIS)
    _echo_task_payload(payload, json_out)
