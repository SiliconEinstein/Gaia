"""Real-API integration test for the CLI build -> review -> infer -> publish pipeline.

Run with:
  pytest tests/integration/test_cli_pipeline_real_api.py -v -m integration_api

Requires:
  - OPENAI_API_KEY in the environment
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "gaia_language_packages"
PACKAGES = ["galileo_falling_bodies", "newton_principia", "einstein_gravity"]

pytestmark = pytest.mark.integration_api

skip_no_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


def _run_gaia(
    *args: str, env_override: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _copy_all_fixtures(tmp_path: Path) -> Path:
    parent = tmp_path / "packages"
    parent.mkdir(parents=True, exist_ok=True)
    for pkg_dir in FIXTURES_DIR.iterdir():
        if pkg_dir.is_dir():
            shutil.copytree(pkg_dir, parent / pkg_dir.name)
    return parent


def _assert_ok(result: subprocess.CompletedProcess, step: str) -> None:
    if result.returncode == 0:
        return
    raise AssertionError(
        f"{step} failed with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


@skip_no_openai
def test_real_llm_pipeline_for_all_three_packages(tmp_path):
    parent = _copy_all_fixtures(tmp_path)
    db_path = str(tmp_path / "db")

    for package_name in PACKAGES:
        pkg_dir = parent / package_name

        build = _run_gaia("build", str(pkg_dir))
        _assert_ok(build, f"{package_name}: build")
        assert (pkg_dir / ".gaia" / "graph" / "raw_graph.json").exists()
        assert (pkg_dir / ".gaia" / "graph" / "local_canonical_graph.json").exists()
        assert (pkg_dir / ".gaia" / "graph" / "canonicalization_log.json").exists()

        review = _run_gaia("review", str(pkg_dir), "--model", "gpt-5-mini")
        _assert_ok(review, f"{package_name}: review")
        review_files = sorted((pkg_dir / ".gaia" / "reviews").glob("review_*.yaml"))
        assert review_files, f"{package_name}: missing review sidecar"

        infer = _run_gaia("infer", str(pkg_dir))
        _assert_ok(infer, f"{package_name}: infer")
        assert (pkg_dir / ".gaia" / "inference" / "local_parameterization.json").exists()
        infer_result = pkg_dir / ".gaia" / "infer" / "infer_result.json"
        assert infer_result.exists(), f"{package_name}: missing infer_result.json"
        infer_data = json.loads(infer_result.read_text())
        assert infer_data["variables"], f"{package_name}: infer_result has no variables"

        publish = _run_gaia("publish", str(pkg_dir), "--local", "--db-path", db_path)
        _assert_ok(publish, f"{package_name}: publish --local")
        receipt_path = pkg_dir / ".gaia" / "publish" / "receipt.json"
        assert receipt_path.exists(), f"{package_name}: missing publish receipt"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["package_id"] == package_name
        assert receipt["stats"]["knowledge_items"] > 0
        assert receipt["stats"]["chains"] > 0
        assert receipt["db_path"] == db_path
