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
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_review(pkg_dir, package_name: str, review_name: str, body: str) -> None:
    reviews_dir = pkg_dir / package_name / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    (reviews_dir / f"{review_name}.py").write_text(body)


def test_infer_writes_parameterization_and_beliefs(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A.")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )
    _write_review(
        pkg_dir,
        "infer_demo",
        "self_review",
        "from gaia.review import ReviewBundle, review_claim, review_strategy\n"
        "from .. import evidence_a, evidence_b, hypothesis, s\n\n"
        "REVIEW = ReviewBundle(\n"
        '    source_id="self_review",\n'
        "    objects=[\n"
        '        review_claim(evidence_a, prior=0.9, judgment="strong", justification="Direct observation."),\n'
        '        review_claim(evidence_b, prior=0.8, judgment="supporting", justification="A second reinforcing observation."),\n'
        '        review_claim(hypothesis, prior=0.4, judgment="tentative", justification="Base rate before support."),\n'
        '        review_strategy(s, judgment="good", justification="The evidence usually supports the hypothesis."),\n'
        "    ],\n"
        ")\n",
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Method:" in result.output

    gaia_dir = pkg_dir / ".gaia"
    parameterization = json.loads(
        (gaia_dir / "reviews" / "self_review" / "parameterization.json").read_text()
    )
    beliefs = json.loads((gaia_dir / "reviews" / "self_review" / "beliefs.json").read_text())

    assert parameterization["source"]["source_id"] == "self_review"
    assert len(parameterization["priors"]) == 3

    belief_by_label = {item["label"]: item["belief"] for item in beliefs["beliefs"]}
    assert all(not item["knowledge_id"].startswith("_m_") for item in beliefs["beliefs"])
    assert belief_by_label["hypothesis"] > 0.4


def test_infer_requires_review_sidecar(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        'from gaia.lang import claim\n\nmain_claim = claim("A claim.")\n__all__ = ["main_claim"]\n'
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
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Original claim.")\n'
        '__all__ = ["main_claim"]\n'
    )
    _write_review(
        pkg_dir,
        "infer_demo",
        "self_review",
        "from gaia.review import ReviewBundle, review_claim\n"
        "from .. import main_claim\n\n"
        "REVIEW = ReviewBundle(objects=[review_claim(main_claim, prior=0.7)])\n",
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Updated claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_infer_supports_generated_interface_claim_review(tmp_path):
    """Deduction (named strategy) generates interface claims that can be reviewed."""
    pkg_dir = tmp_path / "deduction_demo"
    _write_base_package(pkg_dir, name="deduction_demo")
    (pkg_dir / "deduction_demo" / "__init__.py").write_text(
        "from gaia.lang import deduction, claim\n\n"
        'law = claim("forall x. P(x)")\n'
        'instance = claim("P(a)")\n'
        "proof = deduction(premises=[law], conclusion=instance, reason='instantiate')\n"
        '__all__ = ["law", "instance", "proof"]\n'
    )
    _write_review(
        pkg_dir,
        "deduction_demo",
        "self_review",
        "from gaia.review import ReviewBundle, review_claim, review_strategy\n"
        "from .. import law, instance, proof\n\n"
        "REVIEW = ReviewBundle(\n"
        "    objects=[\n"
        '        review_claim(law, prior=0.9, judgment="strong", justification="Well established."),\n'
        '        review_claim(instance, prior=0.5, judgment="possible", justification="Follows from law."),\n'
        '        review_strategy(proof, judgment="formalized", justification="The deduction is correct."),\n'
        "    ],\n"
        ")\n",
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output


def test_infer_requires_review_selection_when_multiple_reviews_exist(tmp_path):
    pkg_dir = tmp_path / "multi_review_demo"
    _write_base_package(pkg_dir, name="multi_review_demo")
    (pkg_dir / "multi_review_demo" / "__init__.py").write_text(
        'from gaia.lang import claim\n\nmain_claim = claim("A claim.")\n__all__ = ["main_claim"]\n'
    )
    _write_review(
        pkg_dir,
        "multi_review_demo",
        "optimistic",
        "from gaia.review import ReviewBundle, review_claim\n"
        "from .. import main_claim\n\n"
        'REVIEW = ReviewBundle(source_id="optimistic", objects=[review_claim(main_claim, prior=0.9)])\n',
    )
    _write_review(
        pkg_dir,
        "multi_review_demo",
        "conservative",
        "from gaia.review import ReviewBundle, review_claim\n"
        "from .. import main_claim\n\n"
        'REVIEW = ReviewBundle(source_id="conservative", objects=[review_claim(main_claim, prior=0.2)])\n',
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    ambiguous = runner.invoke(app, ["infer", str(pkg_dir)])
    assert ambiguous.exit_code != 0
    assert "--review" in ambiguous.output
    assert "optimistic" in ambiguous.output
    assert "conservative" in ambiguous.output

    optimistic = runner.invoke(app, ["infer", "--review", "optimistic", str(pkg_dir)])
    assert optimistic.exit_code == 0, optimistic.output
    conservative = runner.invoke(app, ["infer", "--review", "conservative", str(pkg_dir)])
    assert conservative.exit_code == 0, conservative.output

    optimistic_beliefs = json.loads(
        (pkg_dir / ".gaia" / "reviews" / "optimistic" / "beliefs.json").read_text()
    )
    conservative_beliefs = json.loads(
        (pkg_dir / ".gaia" / "reviews" / "conservative" / "beliefs.json").read_text()
    )
    optimistic_belief = optimistic_beliefs["beliefs"][0]["belief"]
    conservative_belief = conservative_beliefs["beliefs"][0]["belief"]
    assert optimistic_belief > conservative_belief
