"""Tests for ``gaia --version`` — 4-line metadata output."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_version_flag_exits_zero() -> None:
    """``gaia --version`` exits with status 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output


def test_version_flag_prints_four_lines() -> None:
    """Output is exactly 4 lines in the documented order with expected prefixes."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    # CliRunner adds a trailing newline; split + strip empties.
    lines = [ln for ln in result.output.splitlines() if ln != ""]
    assert len(lines) == 4, lines
    assert lines[0].startswith("gaia-lang ")
    assert lines[1].startswith("channel: ")
    assert lines[2].startswith("commit: ")
    assert lines[3].startswith("ir_schema: ")
    # ir_schema must be of the form ir-vN+<12hex>
    assert re.fullmatch(r"ir_schema: ir-v\d+\+[0-9a-f]{12}", lines[3]), lines[3]


def test_version_flag_blocks_subcommand_execution() -> None:
    """``--version`` is eager and short-circuits any subcommand.

    Passing it before a subcommand still just prints version metadata
    and exits (no subcommand runs).
    """
    result = runner.invoke(app, ["--version", "build"])
    assert result.exit_code == 0, result.output
    # No "build" group help; output starts with the gaia-lang version line.
    assert result.output.startswith("gaia-lang ")
    # And contains the ir_schema line — i.e., the eager callback ran fully.
    assert "ir_schema: ir-v" in result.output
