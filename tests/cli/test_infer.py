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


def test_infer_with_priors_py(tmp_path):
    """Package with priors.py — infer reads metadata priors from compiled IR."""
    pkg_dir = tmp_path / "priors_infer"
    _write_base_package(pkg_dir, name="priors_infer")
    (pkg_dir / "priors_infer" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence = claim("Evidence.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        "s = deduction(premises=[evidence], conclusion=hypothesis, reason='deduction', prior=0.9)\n"
        '__all__ = ["evidence", "hypothesis", "s"]\n'
    )
    (pkg_dir / "priors_infer" / "priors.py").write_text(
        "from . import evidence, hypothesis\n\n"
        "PRIORS = {\n"
        '    evidence: (0.9, "Direct observation."),\n'
        '    hypothesis: (0.4, "Base rate."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Method:" in result.output

    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    belief_by_label = {item["label"]: item["belief"] for item in beliefs["beliefs"]}
    assert belief_by_label["hypothesis"] > 0.4


def test_infer_without_priors_py(tmp_path):
    """Package without priors.py — infer uses default 0.5 priors."""
    pkg_dir = tmp_path / "no_priors_infer"
    _write_base_package(pkg_dir, name="no_priors_infer")
    (pkg_dir / "no_priors_infer" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence = claim("Evidence.")\n'
        'hypothesis = claim("Hypothesis.")\n'
        "s = deduction(premises=[evidence], conclusion=hypothesis, reason='deduction', prior=0.9)\n"
        '__all__ = ["evidence", "hypothesis", "s"]\n'
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    beliefs = json.loads((pkg_dir / ".gaia" / "beliefs.json").read_text())
    assert len(beliefs["beliefs"]) >= 2


def test_infer_fails_when_compiled_artifacts_are_stale(tmp_path):
    pkg_dir = tmp_path / "infer_demo"
    _write_base_package(pkg_dir, name="infer_demo")
    (pkg_dir / "infer_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Original claim.")\n'
        '__all__ = ["main_claim"]\n'
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


def test_infer_with_deduction_strategy(tmp_path):
    """Deduction strategy auto-formalizes and runs BP successfully."""
    pkg_dir = tmp_path / "deduction_demo"
    _write_base_package(pkg_dir, name="deduction_demo")
    (pkg_dir / "deduction_demo" / "__init__.py").write_text(
        "from gaia.lang import deduction, claim\n\n"
        'law = claim("forall x. P(x)")\n'
        'instance = claim("P(a)")\n'
        "proof = deduction(premises=[law], conclusion=instance, reason='instantiate', prior=0.9)\n"
        '__all__ = ["law", "instance", "proof"]\n'
    )
    (pkg_dir / "deduction_demo" / "priors.py").write_text(
        "from . import law, instance\n\n"
        "PRIORS = {\n"
        '    law: (0.9, "Well established."),\n'
        '    instance: (0.5, "Follows from law."),\n'
        "}\n"
    )

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0, result.output
