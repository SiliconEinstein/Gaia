"""CLI E2E tests for ``gaia author parameter``."""

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


def _seed_variable(gaia_package: FixturePackage) -> None:
    """Seed a Variable so parameter can reference it."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nfrom gaia.engine.lang.runtime import Variable\n"
        + "from gaia.engine.lang.formula.primitives import REAL\n"
        + "theta = Variable('theta', REAL)\n"
    )


def test_parameter_happy_path(gaia_package: FixturePackage) -> None:
    _seed_variable(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "parameter",
            "--variable",
            "theta",
            "--value",
            "0.5",
            "--label",
            "theta_default",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "theta_default = parameter(theta, 0.5, label='theta_default')" in written


def test_parameter_with_prior(gaia_package: FixturePackage) -> None:
    _seed_variable(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "parameter",
            "--variable",
            "theta",
            "--value",
            "0.75",
            "--label",
            "theta_prior",
            "--prior",
            "0.6",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "prior=0.6" in written


def test_parameter_unresolved_variable_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "parameter",
            "--variable",
            "phantom_var",
            "--value",
            "1.0",
            "--label",
            "x",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_parameter_human_mode(gaia_package: FixturePackage) -> None:
    _seed_variable(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "parameter",
            "--variable",
            "theta",
            "--value",
            "0.5",
            "--label",
            "human_param",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author parameter" in result.output
