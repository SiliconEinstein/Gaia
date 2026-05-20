"""CLI E2E tests for ``gaia author compute``."""

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


def _seed_compute_targets(gaia_package: FixturePackage) -> None:
    """Seed a Claim subclass + a fn so compute can reference them."""
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\nfrom gaia.engine.lang.runtime.knowledge import Claim\n"
        + "class Probability(Claim):\n    pass\n"
        + "def compute_prob():\n    return Probability('result')\n"
    )


def test_compute_happy_path(gaia_package: FixturePackage) -> None:
    """compute() with conclusion-type + fn + given resolves and writes."""
    _seed_compute_targets(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "compute",
            "--dsl-binding-name",
            "result",
            "--conclusion-type",
            "Probability",
            "--fn",
            "compute_prob",
            "--given",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "result = compute(Probability, fn=compute_prob" in written


def test_compute_without_fn(gaia_package: FixturePackage) -> None:
    """compute() can omit --fn (lazy / inline)."""
    _seed_compute_targets(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "compute",
            "--dsl-binding-name",
            "result2",
            "--conclusion-type",
            "Probability",
            "--given",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "result2 = compute(Probability" in written
    assert "fn=" not in written.split("result2 = compute")[1].split("\n")[0]


def test_compute_unresolved_type_exits_3(gaia_package: FixturePackage) -> None:
    """Unknown --conclusion-type fails the reference invariant."""
    result = runner.invoke(
        app,
        [
            "author",
            "compute",
            "--dsl-binding-name",
            "r",
            "--conclusion-type",
            "Ghostly",
            "--given",
            "hypothesis",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3


def test_compute_human_mode(gaia_package: FixturePackage) -> None:
    _seed_compute_targets(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "compute",
            "--dsl-binding-name",
            "human_compute",
            "--conclusion-type",
            "Probability",
            "--target",
            str(gaia_package.root),
            "--no-check",
            "--human",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gaia author compute" in result.output
