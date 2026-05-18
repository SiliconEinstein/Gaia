"""CLI E2E tests for ``gaia author contradict``."""

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


def test_contradict_happy_path(gaia_package: FixturePackage) -> None:
    """Contradict references seeded labels and writes a `contradict(...)` call."""
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "they_contradict",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert (
        "they_contradict = contradict(hypothesis, observation)" in written
    )


def test_contradict_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "ghost",
            "--dsl-binding-name",
            "c",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.reference_unresolved"


def test_contradict_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==a or label==b is a self-loop (exit 1)."""
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.self_loop"


def test_contradict_postwrite_check(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "checked_contradict",
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output


def test_contradict_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "contradict",
            "--a",
            "hypothesis",
            "--b",
            "observation",
            "--dsl-binding-name",
            "human_contra",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author contradict" in result.output
