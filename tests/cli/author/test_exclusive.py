"""CLI E2E tests for ``gaia author exclusive``."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_exclusive_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "exclusive_partition",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert (
        "exclusive_partition = exclusive(hypothesis, observation, label='exclusive_partition')"
        in written
    )


def test_exclusive_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "ghost",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_exclusive_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_exclusive_postwrite_check(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "checked_exclusive",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output


def test_exclusive_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "exclusive",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--label",
            "human_excl",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author exclusive" in result.output
