"""Unit tests for the corpus runner's pure helpers.

End-to-end ``gaia build/run`` exercise is nightly's job (spec §8 step 2);
these tests cover only the runner's own decisions: exit-code mapping
and the spec §5 GitHub-render publication-bundle assertions, run
against synthetic ``.github-output/`` trees in a tmpdir.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_package_corpus.py"


def _load_runner() -> ModuleType:
    """Import ``scripts/run_package_corpus.py`` as a module for testing."""
    spec = importlib.util.spec_from_file_location("run_package_corpus", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


# ---------------------------------------------------------------------------
# compute_exit_code
# ---------------------------------------------------------------------------


def test_compute_exit_code_all_green_returns_zero() -> None:
    assert runner.compute_exit_code(None) == 0


def test_compute_exit_code_first_package_failure_returns_one() -> None:
    assert runner.compute_exit_code(0) == 1


def test_compute_exit_code_second_package_failure_returns_two() -> None:
    assert runner.compute_exit_code(1) == 2


# ---------------------------------------------------------------------------
# assert_github_render_outputs — spec §5 invariants
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_valid_pkg(tmp_path: Path) -> Path:
    """Build a synthetic ``<pkg>/.github-output/`` tree that satisfies §5."""
    pkg = tmp_path / "fake-pkg"
    out = pkg / ".github-output"
    _write(out / "README.md")
    _write(out / "wiki/Home.md")
    _write(out / "docs/public/data/graph.json", json.dumps({"nodes": []}))
    _write(out / "docs/public/data/meta.json", json.dumps({"version": "x"}))
    _write(out / "docs/public/data/beliefs.json", json.dumps({"beliefs": []}))
    return pkg


def test_assert_github_render_outputs_passes_on_valid_tree(tmp_path: Path) -> None:
    pkg = _make_valid_pkg(tmp_path)
    assert runner.assert_github_render_outputs(pkg) is None


def test_assert_github_render_outputs_flags_missing_github_output_dir(tmp_path: Path) -> None:
    pkg = tmp_path / "no-output"
    pkg.mkdir()
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert ".github-output" in reason


@pytest.mark.parametrize("missing", runner.REQUIRED_GITHUB_OUTPUTS)
def test_assert_github_render_outputs_flags_each_missing_required(
    tmp_path: Path, missing: str
) -> None:
    pkg = _make_valid_pkg(tmp_path)
    (pkg / ".github-output" / missing).unlink()
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert missing in reason
    assert "missing required output" in reason


def test_assert_github_render_outputs_flags_empty_required(tmp_path: Path) -> None:
    pkg = _make_valid_pkg(tmp_path)
    (pkg / ".github-output" / "README.md").write_text("", encoding="utf-8")
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert "empty" in reason
    assert "README.md" in reason


def test_assert_github_render_outputs_flags_invalid_json(tmp_path: Path) -> None:
    pkg = _make_valid_pkg(tmp_path)
    (pkg / ".github-output" / "docs/public/data/graph.json").write_text(
        "{not json", encoding="utf-8"
    )
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert "not valid JSON" in reason
    assert "graph.json" in reason


def test_assert_github_render_outputs_flags_forbidden_package_json(tmp_path: Path) -> None:
    pkg = _make_valid_pkg(tmp_path)
    _write(pkg / ".github-output" / "docs/package.json", "{}")
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert "docs/package.json" in reason
    assert "forbidden" in reason


def test_assert_github_render_outputs_flags_forbidden_docs_src(tmp_path: Path) -> None:
    pkg = _make_valid_pkg(tmp_path)
    (pkg / ".github-output" / "docs/src").mkdir(parents=True)
    reason = runner.assert_github_render_outputs(pkg)
    assert reason is not None
    assert "docs/src" in reason
    assert "forbidden" in reason


# ---------------------------------------------------------------------------
# Corpus list is locked to the alpha dispatch.
# ---------------------------------------------------------------------------


def test_corpus_locked_to_galileo_then_mendel() -> None:
    names = [name for name, _ in runner.CORPUS_PACKAGES]
    assert names == ["galileo", "mendel"]
