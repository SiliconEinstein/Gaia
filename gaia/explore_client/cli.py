"""``gaia-explore`` — the exploration orchestrator CLI (CLIENT.md).

A **sibling console_scripts entrypoint** to ``gaia``: it drives the exploration
turn loop as code, not as a skill. The single user-facing command is the
phase-aware step ``gaia-explore turn <pkg>``; ``init`` / ``frontier`` /
``observe`` / ``round`` / ``status`` stay in the ``gaia`` engine CLI (they are
engine ops) and the orchestrator consumes them through the SDK.

Wired in ``pyproject.toml`` as::

    [project.scripts]
    gaia = "gaia.cli.main:app"
    gaia-explore = "gaia.explore_client.cli:app"

Mirrors the ``gaia`` Typer style (module-level ``typer.Option`` singletons,
``typer.echo`` envelope, ``typer.Exit`` on error).
"""

from __future__ import annotations

import json

import typer

from gaia.explore_client.orchestrator import (
    OrchestratorError,
    TurnOutcome,
    outcome_as_dict,
    run_turn,
)

app = typer.Typer(
    name="gaia-explore",
    help=(
        "Gaia Explore orchestrator — the exploration turn state machine. "
        "Sequences the deterministic `gaia explore` engine via the SDK and hands "
        "the fuzzy survey to an agent through a self-contained task envelope."
    ),
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Gaia Explore orchestrator (run ``gaia-explore turn <pkg>``).

    A no-op callback that keeps ``turn`` an explicit subcommand even though it is
    currently the only one — without it, Typer collapses a single-command app to
    the root and ``gaia-explore turn <pkg>`` would parse ``turn`` as the package
    path. Future verbs (e.g. an autonomous ``loop``) slot in as siblings.
    """


# Module-level option singletons (ruff B008: bind once, not in the signature).
_PKG_ARG = typer.Argument(..., help="Knowledge-package path (holds .gaia/exploration/map.json).")
_JSON_OPT = typer.Option(False, "--json", help="Emit the turn outcome as JSON.")


def _render_outcome(outcome: TurnOutcome) -> None:
    """Print a human-readable summary of a turn outcome."""
    for msg in outcome.messages:
        typer.echo(f"  {msg}")

    if outcome.action == "emitted_task":
        kind = "seed-survey" if outcome.seed_survey else "frontier"
        typer.echo(
            f"Turn {outcome.round}: emitted a {kind} task "
            f"({len(outcome.contacts)} contact(s)) → AWAITING_SURVEY."
        )
        typer.echo(f"  task:   {outcome.task_path}")
        typer.echo(f"  result: {outcome.result_path}")
        typer.echo(
            "Survey per the task's baked-in instructions, write the result "
            "manifest, then re-invoke `gaia-explore turn`."
        )
    elif outcome.action == "checkpointed":
        kinds = ", ".join(sorted({d["kind"] for d in outcome.discoveries})) or "none"
        typer.echo(
            f"Turn {outcome.round}: checkpointed → IDLE. "
            f"{len(outcome.surveyed)} surveyed, "
            f"{len(outcome.discoveries)} discovery(ies) [{kinds}]."
        )
        for disc in outcome.discoveries:
            ids = ", ".join(disc.get("ids", []))
            typer.echo(f"  - {disc.get('kind')}: {ids}  {disc.get('note', '')}".rstrip())
        typer.echo("Re-dial the doctrine if desired, then `gaia-explore turn` for the next turn.")
    elif outcome.action == "awaiting_survey":
        typer.echo(f"Turn {outcome.round}: AWAITING_SURVEY — a task is outstanding.")
        typer.echo(f"  task:   {outcome.task_path}")
        typer.echo(f"  result: {outcome.result_path}")


@app.command("turn")
def turn_command(
    pkg: str = _PKG_ARG,
    json_out: bool = _JSON_OPT,
) -> None:
    r"""Run one phase-aware exploration turn (CLIENT.md "Turn state machine").

    Reads the save-game's ``turn_phase`` and infers ``AWAITING_CHECKPOINT`` from a
    result manifest's presence:

    * **IDLE** → rank the frontier (via the SDK), write a self-contained survey
      task (``turn-<n>.task.json``), set ``AWAITING_SURVEY``, print the task path,
      and exit. Round 0 emits a seed-survey task.
    * **AWAITING_CHECKPOINT** (result manifest present) → compile + infer (SDK) +
      run the round, emit the discovery report, set ``IDLE``, and exit.
    * **AWAITING_SURVEY** with no result yet → report the outstanding task.

    Initialise the map first with ``gaia explore init <pkg> --seed … --doctrine …``.

    Example:

    .. code-block:: bash

        gaia explore init ./pkg --seed example:pkg::seed --doctrine Surveyor
        gaia-explore turn ./pkg          # IDLE → emits the survey task
        # ... agent surveys, writes the result manifest ...
        gaia-explore turn ./pkg          # checkpoint → discovery report
    """
    try:
        outcome = run_turn(pkg)
    except OrchestratorError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if json_out:
        typer.echo(json.dumps(outcome_as_dict(outcome), ensure_ascii=False, indent=2))
        return
    _render_outcome(outcome)


__all__ = ["app"]
