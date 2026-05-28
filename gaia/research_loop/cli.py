"""``gaia-research-loop`` command-line interface."""

from __future__ import annotations

import json

import typer

from gaia.research_loop.engine import status_payload

app = typer.Typer(
    name="gaia-research-loop",
    help="Gaia Research Loop — agent-facing Explore -> Assess protocol.",
    no_args_is_help=True,
)

_PKG_ARG = typer.Argument(..., help="Knowledge-package path.")
_JSON_OPT = typer.Option(False, "--json", help="Emit JSON.")


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
