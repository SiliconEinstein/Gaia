"""Integration test for the CLI build → review → infer → publish pipeline.

Exercises the full `gaia build/review/infer/publish` flow using a fixture
package and mock review (no LLM API key required).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "gaia_language_packages"
PACKAGES = ["galileo_falling_bodies", "einstein_gravity", "newton_principia"]


def _run_gaia(*args: str, env_override: dict | None = None) -> subprocess.CompletedProcess:
    """Run a gaia CLI command and return the result."""
    import os

    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(params=PACKAGES)
def package_path(request):
    return FIXTURES_DIR / request.param


@pytest.fixture
def clean_package(package_path):
    """Ensure .gaia/ is removed before and after the test."""
    _run_gaia("clean", str(package_path))
    yield package_path
    _run_gaia("clean", str(package_path))


class TestCliPipeline:
    """Full pipeline: build → review (mock) → infer → publish → search."""

    def test_build(self, clean_package):
        result = _run_gaia("build", str(clean_package))
        assert result.returncode == 0, f"build failed: {result.stderr}"
        assert (clean_package / ".gaia" / "build" / "manifest.json").exists()
        assert (clean_package / ".gaia" / "build" / "package.md").exists()

    def test_review_mock(self, clean_package):
        _run_gaia("build", str(clean_package))
        result = _run_gaia("review", str(clean_package), "--mock")
        assert result.returncode == 0, f"review failed: {result.stderr}"
        reviews_dir = clean_package / ".gaia" / "reviews"
        review_files = list(reviews_dir.glob("review_*.yaml"))
        assert len(review_files) >= 1
        # Mock review should produce chains
        import yaml

        review = yaml.safe_load(review_files[0].read_text())
        assert len(review.get("chains", [])) > 0, "mock review produced 0 chains"

    def test_infer(self, clean_package):
        _run_gaia("build", str(clean_package))
        _run_gaia("review", str(clean_package), "--mock")
        result = _run_gaia("infer", str(clean_package))
        assert result.returncode == 0, f"infer failed: {result.stderr}"
        infer_path = clean_package / ".gaia" / "infer" / "infer_result.json"
        assert infer_path.exists()
        infer_data = json.loads(infer_path.read_text())
        assert len(infer_data["variables"]) > 0

    def test_publish_and_search(self, clean_package, tmp_path):
        """Full pipeline through publish + verify search reads back data."""
        _run_gaia("build", str(clean_package))
        _run_gaia("review", str(clean_package), "--mock")
        _run_gaia("infer", str(clean_package))

        db_path = str(tmp_path / "test_db")
        result = _run_gaia("publish", str(clean_package), "--local", "--db-path", db_path)
        assert result.returncode == 0, f"publish failed: {result.stderr}"

        # Verify receipt
        receipt_path = clean_package / ".gaia" / "publish" / "receipt.json"
        assert receipt_path.exists()
        receipt = json.loads(receipt_path.read_text())
        assert receipt["stats"]["knowledge_items"] > 0
        assert receipt["stats"]["chains"] > 0

        # Verify LanceDB has data
        import lancedb

        db = lancedb.connect(db_path)
        tables = db.list_tables().tables
        assert "knowledge" in tables
        assert "chains" in tables

        knowledge_table = db.open_table("knowledge")
        assert knowledge_table.count_rows() > 0

        chains_table = db.open_table("chains")
        assert chains_table.count_rows() > 0
