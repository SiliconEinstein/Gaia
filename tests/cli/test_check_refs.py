"""Tests for ``gaia build check --refs``."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _write_refs_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-check-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / "references.json").write_text(
        json.dumps(
            {
                "Bell1964": {"type": "article-journal", "title": "Bell theorem"},
                "Unused2020": {"type": "article-journal", "title": "Unused paper"},
            }
        )
    )
    pkg_src = pkg_dir / "refs_check"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, figure\n\n"
        'lemma = claim("A local lemma.")\n'
        "fig1 = figure(\n"
        '    source="Bell1964",\n'
        '    locator="Fig. 1",\n'
        '    path="artifacts/figures/missing.png",\n'
        '    caption="A missing package-local figure.",\n'
        ")\n"
        'main = claim("Cites [@Bell1964], uses [@lemma] and [@fig1], and has @typo.")\n'
        'legacy = claim("Legacy reference metadata.", '
        'refs=[{"type": "figure", "id": "Fig. 2"}], figure="Fig. 2")\n'
        '__all__ = ["main"]\n'
    )


def test_check_refs_reports_reference_findings(tmp_path):
    pkg_dir = tmp_path / "refs_check"
    _write_refs_package(pkg_dir)

    compile_result = runner.invoke(app, ["build", "compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["build", "check", "--refs", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "Reference checks:" in result.output
    assert "Cited refs: Bell1964" in result.output
    assert "Knowledge refs: lemma" in result.output
    assert "Artifact refs: fig1" in result.output
    assert "Unused citations: Unused2020" in result.output
    assert "Unresolved bare refs: typo" in result.output
    assert "Missing artifact files: fig1 -> artifacts/figures/missing.png" in result.output
    assert "Legacy reference metadata: legacy -> refs, figure" in result.output


def test_check_refs_counts_legacy_observe_source_refs(tmp_path):
    pkg_dir = tmp_path / "refs_check_source_refs"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-check-source-refs-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / "references.json").write_text(
        json.dumps(
            {
                "Legacy2015": {
                    "type": "article-journal",
                    "title": "Legacy observation source",
                }
            }
        )
    )
    pkg_src = pkg_dir / "refs_check_source_refs"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, observe\n\n"
        'hypothesis = claim("A measured claim.")\n'
        'observe(hypothesis, source_refs=["Legacy2015"], label="legacy_obs")\n'
        '__all__ = ["hypothesis"]\n'
    )

    result = runner.invoke(app, ["build", "check", "--refs", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "Legacy source refs: Legacy2015" in result.output
    assert "Unused citations: none" in result.output
    assert "Legacy reference metadata: hypothesis -> observe.source_refs" in result.output


def test_check_refs_counts_nonlocal_strategy_reason_citations_as_used(tmp_path, monkeypatch):
    dep_dir = tmp_path / "refs_dep_bridge_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-dep-bridge-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "refs_dep_bridge"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\nfrom gaia.engine.lang.compat import deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))
    dep_compile = runner.invoke(app, ["build", "compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

    bridge_dir = tmp_path / "refs_bridge_pkg"
    bridge_dir.mkdir()
    (bridge_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "refs-bridge-pkg-gaia"\n'
        'version = "1.0.0"\n'
        'dependencies = ["refs-dep-bridge-gaia>=0.4.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (bridge_dir / "references.json").write_text(
        json.dumps(
            {
                "Bridge2024": {
                    "type": "article-journal",
                    "title": "Bridge citation",
                }
            }
        )
    )
    bridge_src = bridge_dir / "refs_bridge_pkg"
    bridge_src.mkdir()
    (bridge_src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\nfrom gaia.engine.lang.compat import fills\n"
        "from refs_dep_bridge import missing_lemma\n\n"
        'bridge_result = claim("A new theorem that proves the missing lemma.")\n'
        "fills(\n"
        "    source=bridge_result,\n"
        "    target=missing_lemma,\n"
        '    reason="Theorem 3 establishes the lemma. See [@Bridge2024].",\n'
        ")\n"
        '__all__ = ["bridge_result"]\n'
    )

    result = runner.invoke(app, ["build", "check", "--refs", str(bridge_dir)])

    assert result.exit_code == 0, result.output
    assert "Cited refs: Bridge2024" in result.output
    assert "Unused citations: none" in result.output


def test_check_refs_reports_unresolved_bare_refs_for_scaffold_action_labels(tmp_path):
    pkg_dir = tmp_path / "refs_check_scaffold_labels"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-check-scaffold-labels-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "refs_check_scaffold_labels"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.engine.lang import candidate_relation, claim\n\n"
        'a = claim("This text mentions @open_relation, but it is not a Knowledge ref.")\n'
        'b = claim("Second claim.")\n'
        'candidate_relation(claims=[a, b], label="open_relation")\n'
        '__all__ = ["a", "b"]\n'
    )

    result = runner.invoke(app, ["build", "check", "--refs", str(pkg_dir)])

    assert result.exit_code == 0, result.output
    assert "Unresolved bare refs: open_relation" in result.output


def test_check_refs_gate_fails_on_hard_reference_findings(tmp_path):
    pkg_dir = tmp_path / "refs_check_gate"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-check-gate-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n\n'
        "[tool.gaia.quality]\nallow_holes = true\n"
    )
    (pkg_dir / "references.json").write_text(
        json.dumps({"Bell1964": {"type": "article-journal", "title": "Bell theorem"}})
    )
    pkg_src = pkg_dir / "refs_check_gate"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.engine.lang import figure, note\n\n"
        "fig1 = figure(\n"
        '    source="Bell1964",\n'
        '    locator="Fig. 1",\n'
        '    path="artifacts/figures/missing.png",\n'
        '    caption="Missing figure.",\n'
        ")\n"
        'main = note("A note with @typo and [@fig1].")\n'
        'legacy = note("Legacy reference metadata.", '
        'refs=[{"type": "figure", "id": "Fig. 2"}], figure="Fig. 2")\n'
        '__all__ = ["main"]\n'
    )

    result = runner.invoke(app, ["build", "check", "--refs", "--gate", str(pkg_dir)])

    assert result.exit_code != 0
    assert "Quality gate failed:" in result.output
    assert "Reference check: unresolved bare refs: typo" in result.output
    assert (
        "Reference check: missing artifact files: fig1 -> artifacts/figures/missing.png"
        in result.output
    )
    assert "Reference check: legacy reference metadata: legacy -> refs, figure" in result.output
