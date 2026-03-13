"""Tests for gaia build command."""

import shutil
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/gaia_language_packages/galileo_falling_bodies"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_creates_gaia_dir(tmp_path):
    """gaia build should create .gaia/build/ directory."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert (pkg_dir / ".gaia" / "build").exists()


def test_build_creates_single_package_md(tmp_path):
    """gaia build should write a single package.md with all modules."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    build_dir = pkg_dir / ".gaia" / "build"
    package_md = build_dir / "package.md"
    assert package_md.exists()
    content = package_md.read_text()
    assert "[module:motivation]" in content
    assert "[module:reasoning]" in content
    assert "[module:follow_up]" in content


def test_build_writes_graph_ir_artifacts(tmp_path):
    """gaia build should write raw/local graph artifacts."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    graph_dir = pkg_dir / ".gaia" / "graph"
    assert (graph_dir / "raw_graph.json").exists()
    assert (graph_dir / "local_canonical_graph.json").exists()
    assert (graph_dir / "canonicalization_log.json").exists()


def test_build_script_entrypoint_works(tmp_path):
    """`python cli/main.py build ...` should work from the repo root."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = subprocess.run(
        [sys.executable, "cli/main.py", "build", str(pkg_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (pkg_dir / ".gaia" / "graph" / "raw_graph.json").exists()


def test_build_markdown_contains_chain_sections(tmp_path):
    """package.md should contain chain anchors for each chain."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    content = (pkg_dir / ".gaia" / "build" / "package.md").read_text()
    assert "[chain:drag_prediction_chain]" in content
    assert "[chain:contradiction_chain]" in content


def test_build_markdown_has_conclusion(tmp_path):
    """package.md should contain conclusion markers."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    content = (pkg_dir / ".gaia" / "build" / "package.md").read_text()
    assert "**Conclusion:**" in content


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
