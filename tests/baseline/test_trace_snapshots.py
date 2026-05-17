"""Snapshot tests for `gaia trace verify|show` against deterministic traces.

The fixtures in `conftest.py` build a Trace whose timestamps + hashes are
fully reproducible, so we can byte-capture the verify-clean output, the
tamper-detection output, and the show-stream output.

`gaia trace review` is intentionally not covered byte-for-byte here:
its text renderer mixes deterministic findings with optional snapshot-dir
side effects and pulls in a non-trivial diagnostic-rendering layer that
A3 (Layer 3 —副作用 artifact fixture) is the better home for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.baseline.conftest import cli_snapshot

pytestmark = pytest.mark.pr_gate


def test_trace_verify_clean_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace verify on a clean trace → exit 0 with hash details."""
    result = run_gaia("trace", "verify", str(clean_trace_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_trace_verify_quiet_clean_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace verify --quiet on a clean trace → silent, exit 0."""
    result = run_gaia("trace", "verify", str(clean_trace_path), "--quiet")
    assert result.exit_code == 0
    assert result.stdout.strip() == ""
    assert cli_snapshot(result) == snapshot


def test_trace_verify_tampered_snapshot(tampered_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace verify on a tampered trace → exit 1 with error messages."""
    result = run_gaia("trace", "verify", str(tampered_trace_path))
    assert result.exit_code == 1
    assert cli_snapshot(result) == snapshot


def test_trace_show_text_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace show <clean trace> → text event stream, exit 0."""
    result = run_gaia("trace", "show", str(clean_trace_path))
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_trace_show_json_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace show --json <clean trace> → JSONL events, exit 0."""
    result = run_gaia("trace", "show", str(clean_trace_path), "--json")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_trace_show_kind_filter_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace show --kind tool_call against an all-decision trace → empty body."""
    result = run_gaia("trace", "show", str(clean_trace_path), "--kind", "tool_call")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot


def test_trace_show_limit_snapshot(clean_trace_path: Path, run_gaia, snapshot) -> None:
    """Gaia trace show --limit 1 → only the first event."""
    result = run_gaia("trace", "show", str(clean_trace_path), "--limit", "1")
    assert result.exit_code == 0
    assert cli_snapshot(result) == snapshot
