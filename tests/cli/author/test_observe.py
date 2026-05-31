"""CLI E2E tests for ``gaia author observe``."""

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


def test_observe_discrete_claim(gaia_package: FixturePackage) -> None:
    """observe(my_claim) discrete form (no --value)."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--dsl-binding-name",
            "obs_h",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "obs_h = observe(hypothesis)" in written


def test_observe_continuous_with_value(gaia_package: FixturePackage) -> None:
    """--value forwards verbatim as a numeric literal for the continuous form."""
    # The DSL would normally need a Distribution here, but pre-write parses
    # the snippet for syntax only and we set --no-check to skip the engine
    # roundtrip.
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--value",
            "203",
            "--error",
            "5",
            "--dsl-binding-name",
            "obs_continuous",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "value=203" in written
    assert "error=5" in written


def test_observe_with_given_conditional(gaia_package: FixturePackage) -> None:
    """--given builds a conditional discrete observation."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--given",
            "observation",
            "--dsl-binding-name",
            "cond_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "given=[observation]" in written


def test_observe_source_refs_still_renders_for_transition(
    gaia_package: FixturePackage,
) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--source-refs",
            "Drozdov2015",
            "--dsl-binding-name",
            "obs_with_legacy_source",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "source_refs=['Drozdov2015']" in written


def test_observe_value_and_given_mutually_exclusive(gaia_package: FixturePackage) -> None:
    """Setting --value + --given is rejected as a syntax error."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--value",
            "1.0",
            "--given",
            "observation",
            "--dsl-binding-name",
            "bad_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_error_requires_value(gaia_package: FixturePackage) -> None:
    """--error without --value is rejected."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--error",
            "0.1",
            "--dsl-binding-name",
            "lonely_error",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_observe_self_loop_exits_1(gaia_package: FixturePackage) -> None:
    """label==conclusion is a self-loop."""
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--dsl-binding-name",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 1


def test_observe_human_mode(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--dsl-binding-name",
            "human_obs",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author observe" in result.output
