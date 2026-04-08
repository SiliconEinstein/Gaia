"""Tests for gaia check command."""

from __future__ import annotations

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(pkg_dir, *, content: str = "A test claim.") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-demo-gaia"\nversion = "1.2.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        f'main_claim = claim("{content}")\n'
        '__all__ = ["main_claim"]\n'
    )


def test_check_passes_with_fresh_artifacts(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir)

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Check passed" in result.output


def test_check_fails_when_compiled_artifacts_are_stale(tmp_path):
    pkg_dir = tmp_path / "check_demo"
    _write_package(pkg_dir, content="Original claim.")

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output

    (pkg_dir / "check_demo" / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'main_claim = claim("Updated claim.")\n'
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_check_fails_on_invalid_fills_target(tmp_path, monkeypatch):
    dep_dir = tmp_path / "dep_check_missing_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "dep-check-missing-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "dep_check_missing"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    pkg_dir = tmp_path / "check_demo"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "check-demo-gaia"\n'
        'version = "1.2.0"\n'
        'dependencies = ["dep-check-missing-gaia>=0.4.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "check_demo"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, fills\n"
        "from dep_check_missing import missing_lemma\n\n"
        'main_claim = claim("A test claim.")\n'
        "fills(source=main_claim, target=missing_lemma)\n"
        '__all__ = ["main_claim"]\n'
    )

    result = runner.invoke(app, ["check", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing .gaia/manifests/premises.json" in result.output
