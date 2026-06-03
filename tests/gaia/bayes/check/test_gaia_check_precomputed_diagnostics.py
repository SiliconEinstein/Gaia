"""gaia check rule: ``bayes:precomputed-solver-diagnostics-missing``.

The v0.6 unified-bayes spec (``docs/specs/2026-05-17-bayes-unified-design.md``
§4.1, §6) requires :class:`PrecomputedLikelihoods` Claims to carry at
least one audit-relevant diagnostic field (a seed, a solver version,
or a convergence statistic). Empty ``diagnostics`` payloads — or
payloads with only solver-private keys that gaia audit cannot interpret
— surface as a soft warning so reviewers notice before the run reaches
BP.

These tests pin three shapes:

1. Empty ``diagnostics`` ⇒ warning fires.
2. Diagnostics with at least one recognised field (e.g. ``seed``) ⇒ no warning.
3. Diagnostics with only unrecognised keys ⇒ warning fires with a hint
   listing what was found.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(pkg_dir: Path, source: str) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "bayes-precomputed-check-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    src = pkg_dir / "bayes_precomputed_check"
    src.mkdir()
    (src / "__init__.py").write_text(source)


_PACKAGE_TEMPLATE = """
import gaia.engine.bayes as bayes
from gaia.engine.bayes.runtime.precomputed import PrecomputedLikelihoods
from gaia.engine.lang import (
    Binomial, Nat, Probability, Variable, observe, parameter,
)

theta = Variable(symbol="theta", domain=Probability)
k_var = Variable(symbol="k", domain=Nat, value=3)

h_a = parameter(theta, 0.5, label="h_a", prior=0.5)
h_b = parameter(theta, 0.7, label="h_b", prior=0.5)

data = observe(k_var, value=3, label="data", rationale="Observed k = 3.")

pred_a = bayes.model(
    h_a, observable=k_var, distribution=Binomial("k under a", n=5, p=theta),
    label="pred_a",
)
pred_b = bayes.model(
    h_b, observable=k_var, distribution=Binomial("k under b", n=5, p=theta),
    label="pred_b",
)

solver_run = PrecomputedLikelihoods(
    "Solver-provided log marginal likelihoods.",
    log_likelihoods={h_a: -1.5, h_b: -2.8},
    diagnostics=DIAGNOSTICS_PAYLOAD,
    solver="custom-stub",
    label="solver_run",
)

cmp = bayes.compare(
    data, models=[pred_a, pred_b],
    exclusivity="exhaustive_pairwise_complement",
    precomputed=solver_run, label="cmp",
)

__all__ = [
    "h_a", "h_b", "data", "pred_a", "pred_b", "solver_run", "cmp",
]
"""


def _format_pkg(diagnostics_repr: str) -> str:
    return _PACKAGE_TEMPLATE.replace("DIAGNOSTICS_PAYLOAD", diagnostics_repr)


def test_empty_diagnostics_triggers_warning(tmp_path: Path):
    pkg_dir = tmp_path / "bayes_precomputed_check"
    _write_package(pkg_dir, _format_pkg("{}"))

    result = runner.invoke(app, ["build", "check", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "bayes:precomputed-solver-diagnostics-missing" in result.output
    assert "solver_run" in result.output
    assert "empty diagnostics payload" in result.output


def test_diagnostics_with_seed_does_not_trigger_warning(tmp_path: Path):
    pkg_dir = tmp_path / "bayes_precomputed_check"
    _write_package(pkg_dir, _format_pkg("{'seed': 42}"))

    result = runner.invoke(app, ["build", "check", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "bayes:precomputed-solver-diagnostics-missing" not in result.output


def test_diagnostics_with_unrecognised_keys_triggers_warning(tmp_path: Path):
    """Only opaque solver-private keys ⇒ warn so audit rules notice."""
    pkg_dir = tmp_path / "bayes_precomputed_check"
    _write_package(pkg_dir, _format_pkg("{'private_field_x': 1.0, 'another_private': 'hello'}"))

    result = runner.invoke(app, ["build", "check", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "bayes:precomputed-solver-diagnostics-missing" in result.output
    # The warning message lists what was actually found so the author can fix it.
    assert "another_private" in result.output
    assert "private_field_x" in result.output


def test_diagnostics_with_r_hat_max_does_not_trigger_warning(tmp_path: Path):
    """An MCMC-style convergence statistic alone is enough to count as audited."""
    pkg_dir = tmp_path / "bayes_precomputed_check"
    _write_package(pkg_dir, _format_pkg("{'r_hat_max': 1.001}"))

    result = runner.invoke(app, ["build", "check", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "bayes:precomputed-solver-diagnostics-missing" not in result.output


def test_diagnostics_with_abs_error_estimate_does_not_trigger_warning(tmp_path: Path):
    """Quadrature-style error estimate is also enough."""
    pkg_dir = tmp_path / "bayes_precomputed_check"
    _write_package(pkg_dir, _format_pkg("{'abs_error_estimate': 1e-12}"))

    result = runner.invoke(app, ["build", "check", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "bayes:precomputed-solver-diagnostics-missing" not in result.output
