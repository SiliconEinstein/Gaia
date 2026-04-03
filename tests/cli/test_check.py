"""Tests for gaia check command."""

from __future__ import annotations

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(pkg_dir, *, content: str = "A test claim.") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "check-demo-gaia"\nversion = "1.2.0"\n\n'
        '[tool.gaia]\nnamespace = "reg"\ntype = "knowledge-package"\n'
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
