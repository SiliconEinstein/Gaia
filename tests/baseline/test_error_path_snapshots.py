"""Snapshot tests for `gaia` error paths.

Each leaf verb has at least one user-facing error path that is fully
deterministic — missing pyproject.toml, invalid --mode value, conflicting
flags, missing required argument, etc. Capturing these gives the engine
↔ CLI refactor a strong byte-baseline for diagnostic messages without
any fixture-state coupling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.baseline.conftest import cli_snapshot

pytestmark = pytest.mark.pr_gate

# --------------------------------------------------------------------------- #
# Top-level leaves                                                            #
# --------------------------------------------------------------------------- #


def test_compile_missing_pyproject_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia build compile on an empty dir → non-zero with a diagnostic message."""
    result = run_gaia("build", "compile", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_compile_wrong_gaia_type_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia build compile when [tool.gaia].type is not knowledge-package."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "foo"\nversion = "1.0.0"\n\n[tool.gaia]\ntype = "something-else"\n',
        encoding="utf-8",
    )
    result = run_gaia("build", "compile", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_check_missing_pyproject_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia build check on an empty dir → non-zero with a diagnostic message."""
    result = run_gaia("build", "check", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_infer_missing_pyproject_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia run infer on an empty dir → non-zero with a diagnostic message."""
    result = run_gaia("run", "infer", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_init_warns_for_name_without_suffix_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia build init <name without -gaia suffix> warns but succeeds."""
    result = run_gaia("build", "init", "my-package", cwd=tmp_path)
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_render_missing_pyproject_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia run render on an empty dir → non-zero."""
    result = run_gaia("run", "render", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_starmap_missing_pyproject_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inspect starmap on an empty dir → non-zero."""
    result = run_gaia("inspect", "starmap", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_starmap_replay_missing_logs_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inspect starmap-replay on an empty dir → non-zero."""
    result = run_gaia("inspect", "starmap-replay", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# inquiry subgroup                                                            #
# --------------------------------------------------------------------------- #


def test_inquiry_focus_mutex_flags_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry focus --clear --push are mutually exclusive."""
    result = run_gaia(
        "inquiry",
        "focus",
        "--clear",
        "--push",
        "anything",
        "--path",
        str(tmp_path),
    )
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_focus_pop_empty_stack_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry focus --pop on empty stack → non-zero."""
    result = run_gaia("inquiry", "focus", "--pop", "--path", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_obligation_close_unknown_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry obligation close with unknown qid → non-zero."""
    result = run_gaia("inquiry", "obligation", "close", "nope_00000000", "--path", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_obligation_add_invalid_kind_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry obligation add with invalid --kind → non-zero."""
    result = run_gaia(
        "inquiry",
        "obligation",
        "add",
        "target",
        "-c",
        "content",
        "--kind",
        "not-a-kind",
        "--path",
        str(tmp_path),
    )
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_hypothesis_remove_unknown_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry hypothesis remove with unknown qid → non-zero."""
    result = run_gaia("inquiry", "hypothesis", "remove", "nope_00000000", "--path", str(tmp_path))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_review_invalid_mode_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry review --mode bogus → non-zero."""
    result = run_gaia("inquiry", "review", str(tmp_path), "--mode", "bogus")
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_review_json_markdown_mutex_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry review --json --markdown are mutually exclusive."""
    result = run_gaia("inquiry", "review", str(tmp_path), "--json", "--markdown")
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


# --------------------------------------------------------------------------- #
# trace subgroup                                                              #
# --------------------------------------------------------------------------- #


def test_trace_verify_missing_path_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace verify on a non-existent trace path → non-zero."""
    missing = tmp_path / "does-not-exist.json"
    result = run_gaia("trace", "verify", str(missing))
    assert result.exit_code != 0
    assert cli_snapshot(result) == snapshot


def test_trace_review_invalid_mode_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace review --mode bogus → exit 2."""
    bogus = tmp_path / "trace.json"
    bogus.write_text("{}", encoding="utf-8")
    result = run_gaia("trace", "review", str(bogus), "--mode", "bogus")
    assert result.exit_code == 2
    assert cli_snapshot(result) == snapshot


def test_trace_review_json_markdown_mutex_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace review --json --markdown are mutually exclusive."""
    bogus = tmp_path / "trace.json"
    bogus.write_text("{}", encoding="utf-8")
    result = run_gaia("trace", "review", str(bogus), "--json", "--markdown")
    assert result.exit_code == 2
    assert cli_snapshot(result) == snapshot
