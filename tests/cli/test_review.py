"""Tests for gaia review command."""

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def _setup_build(tmp_path: Path) -> Path:
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    return pkg_dir


def test_review_creates_sidecar(tmp_path):
    """gaia review should create a review file in .gaia/reviews/."""
    pkg_dir = _setup_build(tmp_path)
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code == 0
    reviews_dir = pkg_dir / ".gaia" / "reviews"
    assert reviews_dir.exists()
    yamls = list(reviews_dir.glob("review_*.yaml"))
    assert len(yamls) == 1


def test_review_sidecar_has_correct_structure(tmp_path):
    """Review sidecar should have package name, chains, and steps."""
    pkg_dir = _setup_build(tmp_path)
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    reviews_dir = pkg_dir / ".gaia" / "reviews"
    review_file = list(reviews_dir.glob("review_*.yaml"))[0]
    data = yaml.safe_load(review_file.read_text())
    assert data["package"] == "galileo_falling_bodies"
    assert "chains" in data
    assert len(data["chains"]) >= 1
    chain = data["chains"][0]
    assert "chain" in chain
    assert "steps" in chain


def test_review_errors_without_build(tmp_path):
    """gaia review should error if build hasn't been run."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code != 0
    assert "build" in result.output.lower()


def test_review_then_infer_pipeline(tmp_path):
    """Full pipeline: build -> review -> infer should work end-to-end."""
    pkg_dir = _setup_build(tmp_path)
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    assert "heavier_falls_faster" in result.output
