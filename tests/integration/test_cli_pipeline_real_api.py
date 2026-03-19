"""Real-API integration test for the Typst pipeline.

Run with:
  pytest tests/integration/test_cli_pipeline_real_api.py -v -m integration_api

Requires:
  - OPENAI_API_KEY in the environment

Note: This test exercises the Typst pipeline end-to-end.
The old YAML pipeline has been removed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "gaia_language_packages"
TYPST_PACKAGES = ["galileo_falling_bodies_v3", "newton_principia_v3", "einstein_gravity_v3"]

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


def _assert_ok(result: subprocess.CompletedProcess, step: str) -> None:
    if result.returncode == 0:
        return
    raise AssertionError(
        f"{step} failed with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


@skip_no_openai
def test_real_llm_build_for_typst_packages():
    """Build all v3 Typst packages and verify Graph IR output.

    Uses real fixture paths (no copy) since Typst #import paths are relative.
    Cleans up .gaia dirs afterwards.
    """
    for package_name in TYPST_PACKAGES:
        pkg_dir = FIXTURES_DIR / package_name
        gaia_dir = pkg_dir / ".gaia"

        try:
            build = _run_gaia("build", str(pkg_dir))
            _assert_ok(build, f"{package_name}: build")
            assert (pkg_dir / ".gaia" / "graph" / "raw_graph.json").exists()
            assert (pkg_dir / ".gaia" / "graph" / "local_canonical_graph.json").exists()
            assert (pkg_dir / ".gaia" / "graph" / "canonicalization_log.json").exists()
        finally:
            if gaia_dir.exists():
                shutil.rmtree(gaia_dir)
