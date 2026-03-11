"""Tests for gaia publish command (v2 storage)."""

import json
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
    """Run build + review (mock) + infer so publish has all artifacts."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    build_result = runner.invoke(app, ["build", str(pkg_dir)])
    assert build_result.exit_code == 0, f"build failed: {build_result.output}"
    review_result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert review_result.exit_code == 0, f"review failed: {review_result.output}"
    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, f"infer failed: {infer_result.output}"
    return pkg_dir


def test_publish_local_writes_receipt(tmp_path):
    """gaia publish --local should write receipt.json to .gaia/publish/."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"

    receipt_path = pkg_dir / ".gaia" / "publish" / "receipt.json"
    assert receipt_path.exists(), "receipt.json was not created"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["version"] == 1
    assert "package_id" in receipt
    assert "published_at" in receipt
    assert receipt["db_path"] == db_path
    assert receipt["stats"]["closures"] > 0
    assert receipt["stats"]["chains"] > 0
    assert len(receipt["closure_ids"]) == receipt["stats"]["closures"]
    assert len(receipt["chain_ids"]) == receipt["stats"]["chains"]


def test_publish_local_writes_v2_closures(tmp_path):
    """gaia publish --local should write closures to LanceDB v2 closures table."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"
    assert "closures" in result.output.lower()

    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("closures")
    assert table.count_rows() > 0
    rows = table.search().limit(1000).to_list()
    # Each closure_id should appear exactly once (no duplicates)
    ids = [r["closure_id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate closure IDs found: {ids}"


def test_publish_local_writes_to_kuzu(tmp_path):
    """gaia publish --local should write topology to Kuzu graph store."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"
    kuzu_dir = Path(db_path) / "kuzu"
    assert kuzu_dir.exists()


def test_publish_local_writes_chains(tmp_path):
    """gaia publish --local should write chains to LanceDB v2 chains table."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"
    assert "chains" in result.output.lower()

    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("chains")
    assert table.count_rows() > 0


def test_publish_local_idempotent(tmp_path):
    """gaia publish --local twice should succeed (idempotent via delete-before-insert)."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result1 = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result1.exit_code == 0, f"first publish failed: {result1.output}"
    result2 = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result2.exit_code == 0, f"second publish failed: {result2.output}"

    # Verify no duplicate closures
    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("closures")
    assert table.count_rows() > 0
    rows = table.search().limit(1000).to_list()
    ids = [r["closure_id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate closure IDs after re-publish: {ids}"


def test_publish_local_errors_without_build(tmp_path):
    """publish --local should error when no manifest.json exists."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code != 0


def test_publish_local_errors_without_infer(tmp_path):
    """publish --local should error when no infer_result.json exists."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    # Build and review, but skip infer
    runner.invoke(app, ["build", str(pkg_dir)])
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code != 0
    assert "infer" in result.output.lower()
