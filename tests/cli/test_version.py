"""Tests for ``gaia --version`` — 4-line metadata output."""

from __future__ import annotations

import re
import sys

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

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


@pytest.mark.parametrize("argv", [["--version"], []], ids=["version", "no-args"])
def test_no_update_check_on_version_or_bare(
    argv: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``gaia --version`` and bare ``gaia`` never trigger the update check.

    The eager ``--version`` exits first, and the no-subcommand case short-circuits
    before the check (``no_args_is_help`` shows help and exits) — so the
    network-touching ``maybe_notify_update`` must not be called for either. Patch
    it to record invocations and assert none occur.
    """
    import gaia.cli._update_check as uc

    calls = {"n": 0}

    def spy(**_kwargs: object) -> None:
        calls["n"] += 1

    monkeypatch.setattr(uc, "maybe_notify_update", spy)
    runner.invoke(app, argv)
    assert calls["n"] == 0, f"update check fired for argv={argv!r}"


@pytest.mark.parametrize(
    "argv",
    [
        ["build", "--help"],
        ["sdk", "--help"],
        ["inquiry", "--help"],
        ["inquiry", "focus", "--help"],
    ],
    ids=["group-help", "command-help", "subapp-help", "nested-help"],
)
def test_no_update_check_on_subcommand_help(
    argv: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subcommand / group / nested help screens stay quiet.

    Unlike bare ``gaia`` and ``gaia --help`` (caught by the no-args guard),
    ``gaia <sub> --help`` routes through the root callback with a non-None
    ``invoked_subcommand`` *before* Typer renders the help — so the check would
    fire unless the callback skips it. The not-yet-parsed ``--help`` lives only
    in ``sys.argv`` at that point, so simulate a realistic argv (CliRunner does
    not touch ``sys.argv``) and assert the network-touching check never runs.
    """
    import gaia.cli._update_check as uc

    calls = {"n": 0}

    def spy(**_kwargs: object) -> None:
        calls["n"] += 1

    monkeypatch.setattr(uc, "maybe_notify_update", spy)
    monkeypatch.setattr(sys, "argv", ["gaia", *argv])
    runner.invoke(app, argv)
    assert calls["n"] == 0, f"update check fired for help path argv={argv!r}"
