"""CLI E2E tests for ``gaia bayes <distribution>``."""

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


def test_binomial_happy_path(bayes_package: BayesPackage) -> None:
    """`bayes binomial --n 395 --p 0.75` renders a Binomial literal."""
    result = runner.invoke(
        app,
        [
            "bayes",
            "binomial",
            "--n",
            "395",
            "--p",
            "0.75",
            "--label",
            "mendel_binomial",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = bayes_package.source_init.read_text()
    assert "mendel_binomial = Binomial('mendel_binomial', n=395, p=0.75)" in text


def test_distribution_metadata_is_rendered(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "normal",
            "--mu",
            "0",
            "--sigma",
            "1",
            "--label",
            "temperature_noise",
            "--metadata",
            '{"unit": "K"}',
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = bayes_package.source_init.read_text()
    assert (
        "temperature_noise = Normal('temperature_noise', mu=0, sigma=1, metadata={'unit': 'K'})"
    ) in text


def test_beta_binomial_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "beta-binomial",
            "--n",
            "395",
            "--alpha",
            "1.0",
            "--beta",
            "1.0",
            "--label",
            "diffuse_betabin",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    text = bayes_package.source_init.read_text()
    assert "diffuse_betabin = BetaBinomial('diffuse_betabin', n=395, alpha=1.0, beta=1.0)" in text


def test_normal_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "normal",
            "--mu",
            "0",
            "--sigma",
            "1",
            "--label",
            "standard_normal",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "standard_normal = Normal('standard_normal', mu=0, sigma=1)" in (
        bayes_package.source_init.read_text()
    )


def test_poisson_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "poisson",
            "--rate",
            "3.5",
            "--label",
            "rare_events",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "rare_events = Poisson('rare_events', rate=3.5)" in (
        bayes_package.source_init.read_text()
    )


def test_beta_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "beta",
            "--alpha",
            "2",
            "--beta",
            "5",
            "--label",
            "beta_prior",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "beta_prior = Beta('beta_prior', alpha=2, beta=5)" in (
        bayes_package.source_init.read_text()
    )


def test_lognormal_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "log-normal",
            "--mu",
            "0",
            "--sigma",
            "1",
            "--label",
            "lognorm",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "lognorm = LogNormal('lognorm', mu=0, sigma=1)" in (
        bayes_package.source_init.read_text()
    )


def test_exponential_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "exponential",
            "--rate",
            "0.5",
            "--label",
            "lifetime",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "lifetime = Exponential('lifetime', rate=0.5)" in (bayes_package.source_init.read_text())


def test_gamma_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "gamma",
            "--alpha",
            "2",
            "--rate",
            "1",
            "--label",
            "gamma_dist",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "gamma_dist = Gamma('gamma_dist', alpha=2, rate=1)" in (
        bayes_package.source_init.read_text()
    )


def test_studentt_default_mu_sigma(bayes_package: BayesPackage) -> None:
    """StudentT defaults mu=0.0, sigma=1.0 when omitted."""
    result = runner.invoke(
        app,
        [
            "bayes",
            "student-t",
            "--df",
            "5",
            "--label",
            "t_dist",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (
        "t_dist = StudentT('t_dist', df=5, mu=0.0, sigma=1.0)"
        in bayes_package.source_init.read_text()
    )


def test_cauchy_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "cauchy",
            "--mu",
            "0",
            "--gamma",
            "1",
            "--label",
            "cauchy_dist",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "cauchy_dist = Cauchy('cauchy_dist', mu=0, gamma=1)" in (
        bayes_package.source_init.read_text()
    )


def test_chisquared_happy_path(bayes_package: BayesPackage) -> None:
    result = runner.invoke(
        app,
        [
            "bayes",
            "chi-squared",
            "--df",
            "3",
            "--label",
            "chi_dist",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "chi_dist = ChiSquared('chi_dist', df=3)" in bayes_package.source_init.read_text()


def test_distribution_envelope_carries_distribution_kind(
    bayes_package: BayesPackage,
) -> None:
    """Envelope payload tags the distribution kind for agent inspection."""
    result = runner.invoke(
        app,
        [
            "bayes",
            "binomial",
            "--n",
            "10",
            "--p",
            "0.5",
            "--label",
            "fair_coin",
            "--target",
            str(bayes_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["distribution_kind"] == "Binomial"
