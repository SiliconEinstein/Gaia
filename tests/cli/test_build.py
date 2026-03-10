"""Tests for gaia build command."""

import shutil

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def test_build_creates_gaia_dir(tmp_path):
    """gaia build should create .gaia/build/ directory."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert (pkg_dir / ".gaia" / "build").exists()


def test_build_creates_module_markdown_files(tmp_path):
    """gaia build should write per-module .md files for modules with chains."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    build_dir = pkg_dir / ".gaia" / "build"
    assert (build_dir / "reasoning.md").exists()
    assert (build_dir / "aristotle.md").exists()
    assert (build_dir / "follow_up.md").exists()
    # Modules without chains should NOT have .md files
    assert not (build_dir / "motivation.md").exists()
    assert not (build_dir / "setting.md").exists()


def test_build_markdown_contains_chain_sections(tmp_path):
    """Module .md files should contain ## sections for each chain."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    reasoning_md = (pkg_dir / ".gaia" / "build" / "reasoning.md").read_text()
    assert "## drag_prediction_chain" in reasoning_md
    assert "## contradiction_chain (deduction)" in reasoning_md


def test_build_markdown_has_premise_and_conclusion(tmp_path):
    """Module .md files should contain premise and conclusion markers."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    reasoning_md = (pkg_dir / ".gaia" / "build" / "reasoning.md").read_text()
    assert "**Premise:**" in reasoning_md
    assert "**Conclusion:**" in reasoning_md


def test_build_output_contains_module_count(tmp_path):
    """gaia build should print summary."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert "galileo_falling_bodies" in result.output
    assert "5 modules" in result.output


def test_build_invalid_path():
    result = runner.invoke(app, ["build", "/nonexistent/path"])
    assert result.exit_code != 0
