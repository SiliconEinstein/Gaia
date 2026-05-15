"""Snapshot tests for inquiry read-path commands on an empty package.

These cover `gaia inquiry <verb>` invocations whose output does not depend on
prior synthetic state — i.e. they read from a fresh `.gaia/inquiry/state.json`
default state. They complement the error-path tests in test_error_path_snapshots
by capturing the *happy "nothing here" path* — which is what most users see
first.

Write-path commands (`obligation add` / `hypothesis add` / `reject`) are
intentionally not captured byte-for-byte here because mint_qid() produces a
uuid4-derived suffix; the masker collapses those to <UUID8>, but the resulting
snapshot would be near-trivial. Verifying mutator side-effects is A3's job.
"""

from __future__ import annotations

from pathlib import Path

from tests.baseline.conftest import cli_snapshot


def test_inquiry_focus_default_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry focus with no target on a fresh package → '(none)'."""
    result = run_gaia("inquiry", "focus", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_focus_stack_empty_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry focus --stack on empty focus stack."""
    result = run_gaia("inquiry", "focus", "--stack", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_obligation_list_empty_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry obligation list with no synthetic obligations."""
    result = run_gaia("inquiry", "obligation", "list", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_obligation_list_empty_json_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry obligation list --json with no obligations → '[]'."""
    result = run_gaia("inquiry", "obligation", "list", "--json", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_hypothesis_list_empty_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry hypothesis list with no hypotheses."""
    result = run_gaia("inquiry", "hypothesis", "list", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_hypothesis_list_empty_json_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry hypothesis list --json with no hypotheses → '[]'."""
    result = run_gaia("inquiry", "hypothesis", "list", "--json", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_tactics_log_empty_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry tactics log with no recorded events."""
    result = run_gaia("inquiry", "tactics", "log", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_inquiry_tactics_log_empty_json_snapshot(tmp_path: Path, run_gaia, snapshot) -> None:
    """Gaia inquiry tactics log --json with no events → '[]'."""
    result = run_gaia("inquiry", "tactics", "log", "--json", "--path", str(tmp_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot
