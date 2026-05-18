"""CLI E2E tests for ``gaia author candidate-relation``."""

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


def test_candidate_relation_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--pattern",
            "equal",
            "--label",
            "maybe_equal",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "maybe_equal = candidate_relation(" in written
    assert "claims=[hypothesis, observation]" in written
    assert "pattern='equal'" in written


def test_candidate_relation_without_pattern(gaia_package: FixturePackage) -> None:
    """Pattern is optional."""
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--label",
            "patternless",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "pattern=" not in written.split("patternless = candidate_relation")[1].split("\n")[0]


def test_candidate_relation_requires_two_claims(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis",
            "--label",
            "too_few",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_contradict_requires_two(gaia_package: FixturePackage) -> None:
    """pattern=contradict requires exactly 2 claims."""
    # Seed a third claim to test the rejection.
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(existing + "\nthird = claim('Third.')\n")
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation,third",
            "--pattern",
            "contradict",
            "--label",
            "three_way_contra",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_bad_pattern_exits_2(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--pattern",
            "xor",
            "--label",
            "bad_pat",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_candidate_relation_unresolved_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,ghost",
            "--label",
            "unresolved",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_candidate_relation_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "candidate-relation",
            "--claims",
            "hypothesis,observation",
            "--label",
            "human_cr",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author candidate_relation" in result.output
