"""CLI smoke tests for v6 likelihood packages."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _belief_by_label(pkg_dir) -> dict[str, float]:
    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    return {item["label"]: item["belief"] for item in beliefs["beliefs"]}


def test_cli_compile_check_infer_v6_ab_test_likelihood(tmp_path):
    pkg_dir = tmp_path / "v6_ab_cli"
    _write_base_package(pkg_dir, name="v6_ab_cli")
    (pkg_dir / "v6_ab_cli" / "__init__.py").write_text(
        "from gaia.lang import claim, compute, context, likelihood_from\n"
        "from gaia.std.likelihood import two_binomial_ab_test_score\n\n"
        'source = context("A: 500/10000 conversions; B: 550/10000 conversions.")\n'
        'counts = claim("AB counts are 500/10000 for A and 550/10000 for B.", prior=0.999)\n'
        'randomization = claim("Users were randomly assigned.", prior=0.999)\n'
        'score_correct = claim("The AB log-likelihood score was computed correctly.", prior=0.999)\n'
        'target = claim("Treatment B has a higher true conversion rate than control A.", prior=0.5)\n'
        "score = two_binomial_ab_test_score(\n"
        "    target=target,\n"
        "    control_successes=500,\n"
        "    control_trials=10000,\n"
        "    treatment_successes=550,\n"
        "    treatment_trials=10000,\n"
        '    query="theta_B > theta_A",\n'
        ")\n"
        "score_result = compute(\n"
        '    "gaia.std.likelihood.two_binomial_ab_test_score",\n'
        '    inputs={"counts": counts, "target": target},\n'
        "    assumptions=[randomization],\n"
        "    output=score,\n"
        "    correctness=score_correct,\n"
        ")\n"
        "likelihood_from(\n"
        "    target=target,\n"
        "    data=[counts],\n"
        "    assumptions=[randomization],\n"
        "    score=score_result,\n"
        ")\n"
        '__all__ = ["target"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    check_result = runner.invoke(app, ["check", str(pkg_dir)])
    assert check_result.exit_code == 0, check_result.output

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert len(ir["likelihood_scores"]) == 1
    assert ir["likelihood_scores"][0]["value"] > 1.25
    assert {strategy["type"] for strategy in ir["strategies"]} >= {"compute", "likelihood"}

    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, infer_result.output
    assert _belief_by_label(pkg_dir)["target"] > 0.75


def test_cli_compile_infer_v6_mendel_likelihood(tmp_path):
    pkg_dir = tmp_path / "v6_mendel_cli"
    _write_base_package(pkg_dir, name="v6_mendel_cli")
    (pkg_dir / "v6_mendel_cli" / "__init__.py").write_text(
        "from gaia.lang import claim, compute, context, likelihood_from\n"
        "from gaia.std.likelihood import binomial_model_score\n\n"
        'source = context("Mendel-style count: 295 dominant, 100 recessive.")\n'
        'counts = claim("The experiment observed 295 dominant plants out of 395.", prior=0.999)\n'
        'model_valid = claim("A binomial model is appropriate for this count.", prior=0.999)\n'
        'score_correct = claim("The binomial log-likelihood score was computed correctly.", prior=0.999)\n'
        'target = claim("The 3:1 binomial model is not strongly disconfirmed.", prior=0.5)\n'
        "score = binomial_model_score(\n"
        "    target=target,\n"
        "    successes=295,\n"
        "    trials=395,\n"
        "    probability=0.75,\n"
        '    query="p = 0.75",\n'
        ")\n"
        "score_result = compute(\n"
        '    "gaia.std.likelihood.binomial_model_score",\n'
        '    inputs={"counts": counts, "target": target},\n'
        "    assumptions=[model_valid],\n"
        "    output=score,\n"
        "    correctness=score_correct,\n"
        ")\n"
        "likelihood_from(\n"
        "    target=target,\n"
        "    data=[counts],\n"
        "    assumptions=[model_valid],\n"
        "    score=score_result,\n"
        ")\n"
        '__all__ = ["target"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, infer_result.output

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    assert round(ir["likelihood_scores"][0]["value"], 6) == -0.010519
    assert 0.49 < _belief_by_label(pkg_dir)["target"] < 0.51
