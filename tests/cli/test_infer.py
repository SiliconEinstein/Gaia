"""Tests for gaia infer command."""

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/gaia_language_packages/galileo_falling_bodies"


def _setup_build_and_review(tmp_path: Path) -> Path:
    """Copy fixture, run build, create a test review file."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)

    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0

    reviews_dir = pkg_dir / ".gaia" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review = {
        "package": "galileo_falling_bodies",
        "model": "test-passthrough",
        "timestamp": "2026-03-08T14:30:00Z",
        "chains": [],
    }
    (reviews_dir / "review_2026-03-08_14-30-00.yaml").write_text(
        yaml.dump(review, allow_unicode=True, sort_keys=False)
    )
    return pkg_dir


def test_infer_produces_beliefs(tmp_path):
    pkg_dir = _setup_build_and_review(tmp_path)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    assert "belief" in result.output.lower() or "Beliefs" in result.output


def test_infer_heavier_falls_faster_decreases(tmp_path):
    pkg_dir = _setup_build_and_review(tmp_path)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    assert "heavier_falls_faster" in result.output


def test_infer_errors_without_review(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "review" in result.output.lower()


def test_infer_errors_without_build(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0


def test_infer_with_explicit_review(tmp_path):
    pkg_dir = _setup_build_and_review(tmp_path)
    review_path = pkg_dir / ".gaia" / "reviews" / "review_2026-03-08_14-30-00.yaml"
    result = runner.invoke(app, ["infer", str(pkg_dir), "--review", str(review_path)])
    assert result.exit_code == 0
