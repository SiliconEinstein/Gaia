"""Tests for gaia infer command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n\n'
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def test_infer_writes_parameterization_and_beliefs(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        'from gaia.lang import claim, noisy_and\n\n'
        'evidence = claim("Observed evidence.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        'support = noisy_and(premises=[evidence], conclusion=hypothesis)\n'
        '__all__ = ["evidence", "hypothesis", "support"]\n'
    )
    (pkg_dir / "infer_demo" / "review.py").write_text(
        'from gaia.review import ReviewBundle, review_claim, review_strategy\n'
        'from . import evidence, hypothesis, support\n\n'
        'REVIEW = ReviewBundle(\n'
        '    source_id="self_review",\n'
        '    objects=[\n'
        '        review_claim(evidence, prior=0.9, judgment="strong", justification="Direct observation."),\n'
        '        review_claim(hypothesis, prior=0.4, judgment="tentative", justification="Base rate before support."),\n'
        '        review_strategy(support, conditional_probability=0.85, judgment="good", justification="The evidence usually supports the hypothesis."),\n'
        '    ],\n'
        ')\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "BP converged: True" in result.output

    gaia_dir = pkg_dir / ".gaia"
    parameterization = json.loads((gaia_dir / "parameterization.json").read_text())
    beliefs = json.loads((gaia_dir / "beliefs.json").read_text())

    assert parameterization["source"]["source_id"] == "self_review"
    assert len(parameterization["priors"]) == 2
    assert len(parameterization["strategy_params"]) == 1

    belief_by_label = {item["label"]: item["belief"] for item in beliefs["beliefs"]}
    assert belief_by_label["hypothesis"] > 0.4


def test_infer_requires_review_sidecar(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        'from gaia.lang import claim\n\n'
        'main_claim = claim("A claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing review sidecar" in result.output.lower()


def test_infer_fails_when_compiled_artifacts_are_stale(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        'from gaia.lang import claim\n\n'
        'main_claim = claim("Original claim.")\n'
        '__all__ = ["main_claim"]\n'
    )
    (pkg_dir / "infer_demo" / "review.py").write_text(
        'from gaia.review import ReviewBundle, review_claim\n'
        'from . import main_claim\n\n'
        'REVIEW = ReviewBundle(objects=[review_claim(main_claim, prior=0.7)])\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        'from gaia.lang import claim\n\n'
        'main_claim = claim("Updated claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_infer_supports_generated_interface_claim_review(tmp_path):
    pkg_dir = tmp_path / "abduction_demo"
    _write_base_package(pkg_dir, name="abduction_demo")
    (pkg_dir / "abduction_demo" / "__init__.py").write_text(
        'from gaia.lang import abduction, claim\n\n'
        'observation = claim("Observation.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        'best_explanation = abduction(observation=observation, hypothesis=hypothesis)\n'
        '__all__ = ["observation", "hypothesis", "best_explanation"]\n'
    )
    (pkg_dir / "abduction_demo" / "review.py").write_text(
        'from gaia.review import ReviewBundle, review_claim, review_generated_claim, review_strategy\n'
        'from . import best_explanation, hypothesis, observation\n\n'
        'REVIEW = ReviewBundle(\n'
        '    objects=[\n'
        '        review_claim(observation, prior=0.9, judgment="strong", justification="Observed directly."),\n'
        '        review_claim(hypothesis, prior=0.3, judgment="possible", justification="Plausible but not dominant."),\n'
        '        review_generated_claim(best_explanation, "alternative_explanation", prior=0.2, judgment="low", justification="There are some alternatives, but they are weaker."),\n'
        '        review_strategy(best_explanation, judgment="formalized", justification="The abduction structure is acceptable."),\n'
        '    ],\n'
        ')\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    parameterization = json.loads((pkg_dir / ".gaia" / "parameterization.json").read_text())
    generated_reviews = [item for item in parameterization["objects"] if item["kind"] == "generated_claim"]
    assert len(generated_reviews) == 1
    assert generated_reviews[0]["role"] == "alternative_explanation"
    assert parameterization["priors"][2]["knowledge_id"].startswith("reg:abduction_demo::__alternative_explanation_")
