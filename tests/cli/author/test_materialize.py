"""CLI E2E tests for ``gaia author materialize``."""

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


def _seed_scaffold_and_record(gaia_package: FixturePackage) -> None:
    """Add a depends_on scaffold + an equal record to feed materialize."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nscaffold_action = depends_on(observation, given=hypothesis, label='scaffold_action')\n"
        + "formal_record = equal(hypothesis, observation, label='formal_record')\n"
    )


def test_materialize_happy_path(gaia_package: FixturePackage) -> None:
    """Materialize binds scaffold to formal records via --by."""
    _seed_scaffold_and_record(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "materialize",
            "--scaffold",
            "scaffold_action",
            "--by",
            "formal_record",
            "--dsl-binding-name",
            "scaffold_materialized",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "scaffold_materialized = materialize(scaffold_action, by=[formal_record])" in written


def test_materialize_unresolved_scaffold_exits_3(gaia_package: FixturePackage) -> None:
    _seed_scaffold_and_record(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "materialize",
            "--scaffold",
            "ghost_scaffold",
            "--by",
            "formal_record",
            "--dsl-binding-name",
            "ghost_mat",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_materialize_empty_by_exits_2(gaia_package: FixturePackage) -> None:
    _seed_scaffold_and_record(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "materialize",
            "--scaffold",
            "scaffold_action",
            "--by",
            "",
            "--dsl-binding-name",
            "empty_by",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_materialize_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==scaffold is a self-loop."""
    _seed_scaffold_and_record(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "materialize",
            "--scaffold",
            "scaffold_action",
            "--by",
            "formal_record",
            "--dsl-binding-name",
            "scaffold_action",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_materialize_human_mode(gaia_package: FixturePackage) -> None:
    _seed_scaffold_and_record(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "materialize",
            "--scaffold",
            "scaffold_action",
            "--by",
            "formal_record",
            "--dsl-binding-name",
            "human_mat",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author materialize" in result.output
