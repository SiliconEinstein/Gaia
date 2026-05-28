"""``gaia-research-loop`` command-line interface."""

from __future__ import annotations

import json

import typer

from gaia.research_loop.engine import emit_task, next_payload, status_payload
from gaia.research_loop.schemas import TaskKind

app = typer.Typer(
    name="gaia-research-loop",
    help="Gaia Research Loop — agent-facing Explore -> Assess protocol.",
    no_args_is_help=True,
)

_PKG_ARG = typer.Argument(..., help="Knowledge-package path.")
_JSON_OPT = typer.Option(False, "--json", help="Emit JSON.")
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


def _echo_task_payload(payload: dict[str, object], json_out: bool) -> None:
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Recommended: {payload['recommended_action']}")
    typer.echo(f"Task: {payload['task_path']}")
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
