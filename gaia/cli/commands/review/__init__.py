"""Gaia review CLI — unified reviewer interface.

Implements `gaia review` as per design doc: docs/plans/gaia-review/00-design.md

Phase 1 MVP commands:
  package      — run complete package review (inquiry + trace + calibration)
  node         — single-node review (filter diagnostics to one claim/strategy/operator)
  calibration  — Δ_qid audit (posterior - prior ranking + honesty check)
  manifest     — review and update action audit records (CRUD)
  status       — read-only overview across review layers
  gate         — composed pass/warn/fail gate checks
  query        — structured reviewer queries
  report       — markdown/html/json report rendering

Phase 2 (future):
  red-team     — adversarial review (LLM or heuristic backend)
  diff         — compare two package states
"""

from __future__ import annotations

import typer

from gaia.cli.commands.review.calibration_cmd import calibration_command
from gaia.cli.commands.review.diff import diff_command
from gaia.cli.commands.review.gate import gate_command
from gaia.cli.commands.review.manifest import manifest_app
from gaia.cli.commands.review.node import node_command
from gaia.cli.commands.review.package import package_command
from gaia.cli.commands.review.query import query_command
from gaia.cli.commands.review.red_team import red_team_command
from gaia.cli.commands.review.report import report_command
from gaia.cli.commands.review.status import status_command

app = typer.Typer(
    name="review",
    help=(
        "Reviewer tooling — package / node / calibration / manifest / status / "
        "red-team / diff / gate / query / report."
    ),
    no_args_is_help=True,
)

# Phase 1 MVP commands
app.command("package")(package_command)
app.command("node")(node_command)
app.command("calibration")(calibration_command)
app.command("status")(status_command)
app.command("red-team")(red_team_command)
app.command("diff")(diff_command)
app.command("gate")(gate_command)
app.command("query")(query_command)
app.command("report")(report_command)

# manifest is a sub-app (has its own subcommands: list/show/accept/reject/needs-inputs)
app.add_typer(manifest_app, name="manifest")
