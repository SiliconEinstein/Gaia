"""``gaia-lkm-explore`` — the unified exploration client CLI (CLIENT.md).

A **sibling console_scripts entrypoint** to ``gaia`` and, as of build 7
(CLIENT.md "Unified surface"), the *single* user-facing surface for exploration.
It carries both halves of the turn loop:

* the deterministic **engine verbs** (``init`` / ``observe`` / ``frontier`` /
  ``round`` / ``status`` / ``render``), migrated here from the now-removed
  ``gaia explore`` sub-app — thin wrappers over :mod:`gaia.engine.exploration`
  (the library / SDK, which stays in gaia); and
* the **orchestrator** phase-aware step ``turn`` — the turn state machine that
  sequences the engine via the SDK and hands the fuzzy survey to a thin agent
  through a self-contained task envelope.

Wired in ``pyproject.toml`` as::

    [project.scripts]
    gaia = "gaia.cli.main:app"
    gaia-lkm-explore = "gaia.explore_client.cli:app"

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
from gaia.explore_client.verbs import (
    frontier_command,
    init_command,
    observe_command,
    render_command,
    round_command,
    status_command,
)

app = typer.Typer(
    name="gaia-lkm-explore",
    help=(
        "Gaia LKM Explore — fog-of-war exploration of a knowledge package. "
        "Deterministic engine verbs (init / observe / frontier / round / status / "
        "render) plus the orchestrator turn state machine (turn), which hands the "
        "fuzzy survey to an agent through a self-contained task envelope."
    ),
    no_args_is_help=True,
)

# Engine verbs (migrated from the removed `gaia explore` sub-app, build 7). They
# wrap `gaia.engine.exploration` (the library / SDK) and are pure + deterministic
# — no LKM call, no `gaia author` orchestration; those are the agent's survey.
app.command(name="init")(init_command)
app.command(name="observe")(observe_command)
app.command(name="frontier")(frontier_command)
app.command(name="round")(round_command)
app.command(name="status")(status_command)
app.command(name="render")(render_command)


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
            "manifest, then re-invoke `gaia-lkm-explore turn`."
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
        typer.echo(
            "Re-dial the doctrine if desired, then `gaia-lkm-explore turn` for the next turn."
        )
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

    Initialise the map first with
    ``gaia-lkm-explore init <pkg> --seed … --doctrine …``.

    Example:

    .. code-block:: bash

        gaia-lkm-explore init ./pkg --seed example:pkg::seed --doctrine Surveyor
        gaia-lkm-explore turn ./pkg      # IDLE → emits the survey task
        # ... agent surveys, writes the result manifest ...
        gaia-lkm-explore turn ./pkg      # checkpoint → discovery report
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
