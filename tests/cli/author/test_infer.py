"""CLI E2E tests for ``gaia author infer``."""

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


def test_infer_happy_path(gaia_package: FixturePackage) -> None:
    """infer() with evidence + hypothesis + likelihoods writes the call."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "hypothesis",
            "--hypothesis",
            "observation",
            "--p-e-given-h",
            "0.7",
            "--p-e-given-not-h",
            "0.2",
            "--dsl-binding-name",
            "evidence_for_h",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "evidence_for_h = infer(hypothesis" in written
    assert "hypothesis=observation" in written
    assert "p_e_given_h=0.7" in written
    assert "p_e_given_not_h=0.2" in written


def test_infer_default_p_e_given_not_h(gaia_package: FixturePackage) -> None:
    """Omitting --p-e-given-not-h omits the kwarg (DSL defaults to 0.5)."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "hypothesis",
            "--hypothesis",
            "observation",
            "--p-e-given-h",
            "0.7",
            "--dsl-binding-name",
            "defaulted_infer",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "p_e_given_not_h" not in written.split("defaulted_infer = infer")[1].split("\n")[0]


def test_infer_unresolved_hypothesis_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "hypothesis",
            "--hypothesis",
            "ghost_h",
            "--p-e-given-h",
            "0.5",
            "--dsl-binding-name",
            "bad_infer",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_infer_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==evidence is a self-loop."""
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "hypothesis",
            "--hypothesis",
            "observation",
            "--p-e-given-h",
            "0.5",
            "--dsl-binding-name",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_infer_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "infer",
            "--evidence",
            "hypothesis",
            "--hypothesis",
            "observation",
            "--p-e-given-h",
            "0.5",
            "--dsl-binding-name",
            "human_infer",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author infer" in result.output
