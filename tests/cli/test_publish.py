"""Tests for gaia publish command."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/gaia_language_packages/galileo_falling_bodies"


def test_publish_requires_mode():
    """gaia publish without --git, --local, or --server should error."""
    result = runner.invoke(app, ["publish", "."])
    assert result.exit_code != 0


def test_publish_git_runs_commands(tmp_path):
    """gaia publish --git should run git add + commit + push."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "package.yaml").write_text("name: test\nmodules: []\nexport: []")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    (tmp_path / "test.yaml").write_text("test: true")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")
        runner.invoke(app, ["publish", str(tmp_path), "--git"])
    assert mock_run.called


def _setup_full_pipeline(tmp_path: Path) -> Path:
    """Run build + review (mock) so publish has artifacts to work with."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    return pkg_dir


def test_publish_local_writes_to_lancedb(tmp_path):
    """gaia publish --local should write nodes to LanceDB."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    assert "nodes" in result.output.lower()
    assert "edges" in result.output.lower()


def test_publish_local_writes_to_kuzu(tmp_path):
    """gaia publish --local should write edges to Kuzu graph store."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    kuzu_dir = Path(db_path) / "kuzu"
    assert kuzu_dir.exists()


def test_publish_local_idempotent(tmp_path):
    """gaia publish --local twice should succeed (idempotent)."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result1 = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result1.exit_code == 0
    result2 = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result2.exit_code == 0
    # Verify no duplicate nodes — count should be same as first run
    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("nodes")
    assert table.count_rows() > 0
    # Each node id should appear exactly once
    rows = table.search().limit(1000).to_list()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate node IDs found: {ids}"


def test_publish_local_errors_without_build(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code != 0
