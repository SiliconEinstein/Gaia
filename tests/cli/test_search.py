"""Tests for gaia search command — searches LanceDB."""

import shutil
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/gaia_language_packages/galileo_falling_bodies"


def _publish_galileo(tmp_path: Path) -> tuple[Path, str]:
    """Build + review + publish --local, return (pkg_dir, db_path)."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    db_path = str(tmp_path / "testdb")
    runner.invoke(app, ["build", str(pkg_dir)])
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    return pkg_dir, db_path


def test_search_finds_published_nodes(tmp_path):
    """After publish --local, search should find nodes in LanceDB."""
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "重的物体", "--db-path", db_path])
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


def test_search_no_results(tmp_path):
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "quantum_entanglement_xyz", "--db-path", db_path])
    assert result.exit_code == 0
    assert "no results" in result.output.lower()


def test_search_shows_belief(tmp_path):
    """Search results should include belief values."""
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "重的物体", "--db-path", db_path])
    assert result.exit_code == 0
    assert "prior" in result.output.lower() or "belief" in result.output.lower()
