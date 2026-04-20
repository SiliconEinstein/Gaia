"""CLI rendering coverage for v6 likelihood method details."""

from __future__ import annotations

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n'
        'description = "v6 likelihood rendering test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_ab_test_package(pkg_dir) -> None:
    name = "v6_render_ab"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text(
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
        '__all__ = ["target", "score_correct"]\n'
    )


def test_check_show_renders_likelihood_method_details(tmp_path):
    pkg_dir = tmp_path / "v6_render_ab"
    _write_ab_test_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    target_result = runner.invoke(app, ["check", "--show", "target", str(pkg_dir)])
    assert target_result.exit_code == 0, target_result.output
    assert "method: gaia.std.likelihood.two_binomial_ab_test@v1" in target_result.output
    assert "score: log_lr=1.25689" in target_result.output
    assert "query: theta_B > theta_A" in target_result.output

    compute_result = runner.invoke(app, ["check", "--show", "score_correct", str(pkg_dir)])
    assert compute_result.exit_code == 0, compute_result.output
    assert "function: gaia.std.likelihood.two_binomial_ab_test_score" in compute_result.output
    assert "output: log_lr=1.25689" in compute_result.output
    assert "query: theta_B > theta_A" in compute_result.output


def test_render_docs_include_v6_method_details(tmp_path):
    pkg_dir = tmp_path / "v6_render_ab"
    _write_ab_test_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, infer_result.output

    render_result = runner.invoke(app, ["render", "--target", "docs", str(pkg_dir)])
    assert render_result.exit_code == 0, render_result.output

    content = (pkg_dir / "docs" / "detailed-reasoning.md").read_text()
    assert "<details><summary>Method</summary>" in content
    assert "- method: gaia.std.likelihood.two_binomial_ab_test@v1" in content
    assert "- score: log_lr=1.25689" in content
    assert "- function: gaia.std.likelihood.two_binomial_ab_test_score" in content
