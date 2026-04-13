"""Tests for gaia render command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n'
        'description = "Test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_minimal_source(pkg_dir, name: str) -> None:
    (pkg_dir / name / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A.")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis,"
        " reason='test', prior=0.9)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )


def _write_priors(pkg_dir, name: str) -> None:
    (pkg_dir / name / "priors.py").write_text(
        "from . import evidence_a, evidence_b, hypothesis\n\n"
        "PRIORS = {\n"
        '    evidence_a: (0.9, "Direct observation."),\n'
        '    evidence_b: (0.8, "Supporting observation."),\n'
        '    hypothesis: (0.4, "Base rate."),\n'
        "}\n"
    )


def _prepare_inferred_package(tmp_path, name: str = "render_demo"):
    """Create a package with priors.py, compile and infer it. Returns pkg_dir."""
    pkg_dir = tmp_path / name
    _write_base_package(pkg_dir, name=name)
    _write_minimal_source(pkg_dir, name)
    _write_priors(pkg_dir, name)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, infer_result.output
    return pkg_dir


def test_render_target_all_writes_docs_and_github(tmp_path):
    """Happy path: render --target all (default) writes both docs and github outputs."""
    pkg_dir = _prepare_inferred_package(tmp_path)

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    docs_path = pkg_dir / "docs" / "detailed-reasoning.md"
    assert docs_path.exists(), "render should write docs/detailed-reasoning.md"
    content = docs_path.read_text()
    assert "# render_demo-gaia" in content or "# render_demo" in content

    github_dir = pkg_dir / ".github-output"
    assert (github_dir / "wiki" / "Home.md").exists()
    assert (github_dir / "manifest.json").exists()
    assert (github_dir / "docs" / "public" / "data" / "graph.json").exists()
    assert (github_dir / "README.md").exists()


def test_render_uses_metadata_priors_from_priors_py(tmp_path):
    pkg_dir = _prepare_inferred_package(tmp_path, name="metadata_prior_render")

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output

    content = (pkg_dir / "docs" / "detailed-reasoning.md").read_text()
    assert "Prior: 0.90" in content
    assert "| [evidence_b](#evidence_b) | claim | 0.80 |" in content


def test_render_fails_when_ir_artifacts_missing(tmp_path):
    """render before compile → error about missing compiled artifacts."""
    pkg_dir = tmp_path / "no_compile"
    _write_base_package(pkg_dir, name="no_compile")
    _write_minimal_source(pkg_dir, "no_compile")

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing compiled artifacts" in result.output


def test_render_fails_when_ir_stale(tmp_path):
    """render when source changed after compile → stale-artifact error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="stale_ir")

    # Mutate source so re-compile yields a different ir_hash
    (pkg_dir / "stale_ir" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A (edited).")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis,"
        " reason='test', prior=0.9)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_render_target_github_fails_when_no_beliefs(tmp_path):
    """--target github hard-errors when infer has not been run."""
    pkg_dir = tmp_path / "no_infer_gh"
    _write_base_package(pkg_dir, name="no_infer_gh")
    _write_minimal_source(pkg_dir, "no_infer_gh")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code != 0
    assert "inference" in result.output.lower() or "gaia infer" in result.output


def test_render_target_docs_succeeds_without_beliefs(tmp_path):
    """--target docs renders from compiled IR alone when infer hasn't been run."""
    pkg_dir = tmp_path / "no_infer_docs"
    _write_base_package(pkg_dir, name="no_infer_docs")
    _write_minimal_source(pkg_dir, "no_infer_docs")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "warning" in result.output.lower()


def test_render_target_all_degrades_to_docs_without_beliefs(tmp_path):
    """--target all falls back to docs-only with a warning when infer hasn't been run."""
    pkg_dir = tmp_path / "no_infer_all"
    _write_base_package(pkg_dir, name="no_infer_all")
    _write_minimal_source(pkg_dir, "no_infer_all")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "skipping" in result.output.lower()


def test_render_fails_when_beliefs_stale(tmp_path):
    """render when beliefs.json has a wrong ir_hash → stale beliefs error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="stale_beliefs")
    beliefs_path = pkg_dir / ".gaia" / "beliefs.json"
    beliefs = json.loads(beliefs_path.read_text())
    beliefs["ir_hash"] = "not-the-real-hash"
    beliefs_path.write_text(json.dumps(beliefs))

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()
    assert "beliefs" in result.output.lower()


def test_render_target_docs_only(tmp_path):
    """--target docs creates docs/detailed-reasoning.md but not .github-output/."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="docs_only")

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output

    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "Docs:" in result.output
    assert "GitHub:" not in result.output


def test_render_target_github_only(tmp_path):
    """--target github creates .github-output/ but not docs/detailed-reasoning.md."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="github_only")

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code == 0, result.output

    assert (pkg_dir / ".github-output" / "manifest.json").exists()
    assert not (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "GitHub:" in result.output
    assert "Docs:" not in result.output


def test_render_target_all_is_default(tmp_path):
    """Omitting --target is the same as --target all."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="all_default")

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert (pkg_dir / ".github-output" / "manifest.json").exists()


def test_render_target_obsidian_writes_vault(tmp_path):
    """Obsidian target creates gaia-wiki/ with _index.md and module pages."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="obsidian_demo")
    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "obsidian"])
    assert result.exit_code == 0, result.output
    wiki_dir = pkg_dir / "gaia-wiki"
    assert wiki_dir.is_dir()
    assert (wiki_dir / "_index.md").exists()
    assert (wiki_dir / "overview.md").exists()
    assert (wiki_dir / ".obsidian" / "graph.json").exists()
    assert "Obsidian:" in result.output


def test_render_target_all_does_not_include_obsidian(tmp_path):
    """Obsidian is opt-in — --target all should NOT create gaia-wiki/."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="all_no_obsidian")
    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert not (pkg_dir / "gaia-wiki").exists()
