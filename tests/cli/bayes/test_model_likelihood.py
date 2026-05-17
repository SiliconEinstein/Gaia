"""CLI E2E tests for ``gaia bayes model`` + ``gaia bayes likelihood`` (R7 G2)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import BayesPackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def _seed_distribution(bayes_package: BayesPackage) -> None:
    """Append a Binomial distribution binding to the fixture."""
    existing = bayes_package.source_init.read_text()
    bayes_package.source_init.write_text(existing + "\nshared_dist = bayes.Binomial(n=10, p=0.5)\n")


def test_model_happy_path(bayes_package: BayesPackage) -> None:
    """`bayes model` renders a bayes.model() call."""
    _seed_distribution(bayes_package)
    result = runner.invoke(
        app,
        [
            "bayes",
            "model",
            "--hypothesis",
            "hypothesis_a",
            "--observable",
            "observable_x",
            "--distribution",
            "shared_dist",
            "--label",
            "model_a",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = bayes_package.source_init.read_text()
    assert "model_a = bayes.model(hypothesis_a" in text
    assert "observable=observable_x" in text
    assert "distribution=shared_dist" in text


def test_model_rejects_unresolved_observable(bayes_package: BayesPackage) -> None:
    """A missing observable identifier is a reference-resolution error."""
    _seed_distribution(bayes_package)
    result = runner.invoke(
        app,
        [
            "bayes",
            "model",
            "--hypothesis",
            "hypothesis_a",
            "--observable",
            "no_such_var",
            "--distribution",
            "shared_dist",
            "--label",
            "bad_model",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.reference_unresolved"


def test_likelihood_happy_path(bayes_package: BayesPackage) -> None:
    """`bayes likelihood` references two models + data observation."""
    _seed_distribution(bayes_package)
    # Seed two models + a data claim so the references resolve.
    runner.invoke(
        app,
        [
            "bayes",
            "model",
            "--hypothesis",
            "hypothesis_a",
            "--observable",
            "observable_x",
            "--distribution",
            "shared_dist",
            "--label",
            "model_a",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    runner.invoke(
        app,
        [
            "bayes",
            "model",
            "--hypothesis",
            "hypothesis_b",
            "--observable",
            "observable_x",
            "--distribution",
            "shared_dist",
            "--label",
            "model_b",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    runner.invoke(
        app,
        [
            "author",
            "claim",
            "Observed count.",
            "--label",
            "data_obs",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    result = runner.invoke(
        app,
        [
            "bayes",
            "likelihood",
            "--data",
            "data_obs",
            "--model",
            "model_a",
            "--against",
            "model_b",
            "--exclusivity",
            "none",
            "--label",
            "comparison",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = bayes_package.source_init.read_text()
    assert "comparison = bayes.likelihood(data_obs" in text
    assert "model=model_a" in text
    assert "against=[model_b]" in text
    assert "exclusivity='none'" in text


def test_likelihood_invalid_exclusivity(bayes_package: BayesPackage) -> None:
    """Bad --exclusivity value is rejected."""
    result = runner.invoke(
        app,
        [
            "bayes",
            "likelihood",
            "--data",
            "hypothesis_a",
            "--model",
            "hypothesis_b",
            "--exclusivity",
            "garbage",
            "--label",
            "x",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
