"""CLI E2E tests for ``gaia author associate``."""

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


def test_associate_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "associate",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--p-a-given-b",
            "0.9",
            "--p-b-given-a",
            "0.6",
            "--label",
            "h_obs_assoc",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "h_obs_assoc = associate(hypothesis, observation" in written
    assert "p_a_given_b=0.9" in written
    assert "p_b_given_a=0.6" in written


def test_associate_with_pattern(gaia_package: FixturePackage) -> None:
    """--pattern=equal renders the kwarg correctly."""
    result = runner.invoke(
        app,
        [
            "author",
            "associate",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--p-a-given-b",
            "0.8",
            "--p-b-given-a",
            "0.8",
            "--pattern",
            "equal",
            "--label",
            "patterned",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "pattern='equal'" in written


def test_associate_bad_pattern_exits_2(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "associate",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--p-a-given-b",
            "0.5",
            "--p-b-given-a",
            "0.5",
            "--pattern",
            "xor",
            "--label",
            "bad_pattern",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_associate_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "associate",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--p-a-given-b",
            "0.5",
            "--p-b-given-a",
            "0.5",
            "--label",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_associate_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "associate",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--p-a-given-b",
            "0.5",
            "--p-b-given-a",
            "0.5",
            "--label",
            "human_assoc",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author associate" in result.output
