"""Tests for the ``--interactive`` flow on ``gaia author <verb>``.

``--interactive`` is wired uniformly: any pre-write warning surfaces a
numbered prompt in human mode; JSON mode auto-suppresses. These tests
exercise the activation logic against a synthesised
:class:`AuthorPrewriteResult` with warnings injected.

The shape of the prompt + the abort envelope is the load-bearing
contract.
"""

from __future__ import annotations

import io

import pytest
import typer

from gaia.cli.commands.author._envelope import Diagnostic
from gaia.cli.commands.author._runner import _maybe_consume_warnings

pytestmark = pytest.mark.pr_gate


def _warning(message: str = "synthetic", kind: str = "prewrite.synthetic") -> Diagnostic:
    return Diagnostic(kind=kind, level="warning", message=message, source="prewrite")


def test_interactive_no_warnings_proceeds() -> None:
    """No warnings → always proceed regardless of flag state."""
    proceed, abort = _maybe_consume_warnings("claim", [], interactive=True, human=True)
    assert proceed
    assert abort is None


def test_interactive_off_proceeds_with_warnings() -> None:
    """Warnings present but --interactive off → proceed silently."""
    proceed, abort = _maybe_consume_warnings("claim", [_warning()], interactive=False, human=True)
    assert proceed
    assert abort is None


def test_interactive_json_mode_auto_suppresses() -> None:
    """JSON mode (human=False) always proceeds — agents can't drive stdin."""
    proceed, abort = _maybe_consume_warnings("claim", [_warning()], interactive=True, human=False)
    assert proceed
    assert abort is None


def test_interactive_human_default_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty input at the prompt defaults to N → abort with `aborted` envelope."""
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    proceed, abort = _maybe_consume_warnings(
        "claim", [_warning("first")], interactive=True, human=True
    )
    assert not proceed
    assert abort is not None
    assert abort.status == "aborted"
    assert abort.code == 0
    assert abort.warnings == ["first"]
    assert abort.diagnostics[0].kind == "user.aborted"
    # The original warning is preserved in the diagnostics list.
    assert abort.diagnostics[1].message == "first"


def test_interactive_human_y_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Typing `y` at the prompt continues to write."""
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    proceed, abort = _maybe_consume_warnings("claim", [_warning()], interactive=True, human=True)
    assert proceed
    assert abort is None


def test_interactive_human_yes_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """`yes` is also accepted."""
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    proceed, abort = _maybe_consume_warnings("claim", [_warning()], interactive=True, human=True)
    assert proceed
    assert abort is None


def test_interactive_explicit_n_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    proceed, abort = _maybe_consume_warnings("claim", [_warning()], interactive=True, human=True)
    assert not proceed
    assert abort is not None
    assert abort.status == "aborted"


def test_interactive_prompt_numbers_multiple_warnings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Multiple warnings are numbered 1)..N) in the prompt body."""
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    warnings = [_warning("first", "kind.a"), _warning("second", "kind.b")]
    proceed, _ = _maybe_consume_warnings("claim", warnings, interactive=True, human=True)
    assert proceed
    out = capsys.readouterr().out
    assert "1) kind.a: first" in out
    assert "2) kind.b: second" in out


def test_interactive_abort_envelope_carries_user_aborted_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The abort path emits the canonical `user.aborted` diagnostic kind."""
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    _, abort = _maybe_consume_warnings("claim", [_warning()], interactive=True, human=True)
    assert abort is not None
    kinds = [d.kind for d in abort.diagnostics]
    assert "user.aborted" in kinds


def test_interactive_typer_prompt_can_be_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity: the underlying typer.prompt call wires through correctly."""
    monkeypatch.setattr("sys.stdin", io.StringIO("Y\n"))
    answer = typer.prompt("test", default="N", show_default=False)
    assert answer == "Y"
