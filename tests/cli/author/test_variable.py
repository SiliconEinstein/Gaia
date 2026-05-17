"""CLI E2E tests for ``gaia author variable`` (R7 G3)."""

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
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_variable_happy_path_with_value(gaia_package: FixturePackage) -> None:
    """`gaia author variable --domain Nat --value 395` renders a Variable(...)."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--symbol",
            "n_total",
            "--domain",
            "Nat",
            "--value",
            "395",
            "--label",
            "f2_total",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["verb"] == "variable"
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["variable_kind"] == "variable"
    written = gaia_package.source_init.read_text()
    assert "f2_total = Variable(" in written
    assert "symbol='n_total'" in written
    assert "domain=Nat" in written
    assert "value=395" in written


def test_variable_without_value(gaia_package: FixturePackage) -> None:
    """A Variable without --value omits the kwarg."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--symbol",
            "k",
            "--domain",
            "Real",
            "--label",
            "rate_const",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "rate_const = Variable(symbol='k', domain=Real)" in written


def test_variable_const_mode(gaia_package: FixturePackage) -> None:
    """`--const --domain Nat --value 395` emits a Constant(...)."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--const",
            "--domain",
            "Nat",
            "--value",
            "395",
            "--label",
            "literal_395",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["variable_kind"] == "const"
    written = gaia_package.source_init.read_text()
    assert "literal_395 = Constant(395, Nat)" in written


def test_variable_missing_symbol_for_non_const(gaia_package: FixturePackage) -> None:
    """Plain variable mode requires --symbol."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--domain",
            "Nat",
            "--value",
            "1",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_variable_const_with_symbol_rejected(gaia_package: FixturePackage) -> None:
    """`--const --symbol foo` is incoherent."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--const",
            "--symbol",
            "foo",
            "--domain",
            "Nat",
            "--value",
            "1",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2


def test_variable_const_without_value_rejected(gaia_package: FixturePackage) -> None:
    """`--const` always needs --value."""
    result = runner.invoke(
        app,
        [
            "author",
            "variable",
            "--const",
            "--domain",
            "Nat",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
