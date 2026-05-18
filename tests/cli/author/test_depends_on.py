"""CLI E2E tests for ``gaia author depends-on``."""

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


def test_depends_on_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--label",
            "obs_depends_on_h",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert (
        "obs_depends_on_h = depends_on(observation, given=[hypothesis], label='obs_depends_on_h')"
        in written
    )


def test_depends_on_multi_given(gaia_package: FixturePackage) -> None:
    """Multiple --given identifiers render as a list."""
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis,observation",
            "--label",
            "multi_dep",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "given=[hypothesis, observation]" in written


def test_depends_on_empty_given_exits_2(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_depends_on_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "ghost",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_depends_on_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==conclusion is a self-loop."""
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--label",
            "observation",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_depends_on_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "depends-on",
            "--conclusion",
            "observation",
            "--given",
            "hypothesis",
            "--label",
            "human_dep",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author depends_on" in result.output
