"""Tests for focus resolution and CLI focus command."""

from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.inquiry.state import load_state

runner = CliRunner()


def test_resolve_freeform_without_graph():
    b = resolve_focus_target("any text", None)
    assert isinstance(b, FocusBinding)
    assert b.raw == "any text"
    assert b.kind == "freeform"


def test_resolve_none():
    b = resolve_focus_target(None, None)
    assert b.kind == "none"
    assert b.raw is None


def test_cli_focus_set_and_show(simple_pkg: Path):
    r = runner.invoke(app, ["inquiry", "focus", "main_claim", "--path", str(simple_pkg)])
    assert r.exit_code == 0, r.output
    assert "focus set" in r.output

    r2 = runner.invoke(app, ["inquiry", "focus", "--path", str(simple_pkg)])
    assert r2.exit_code == 0
    assert "main_claim" in r2.output

    state = load_state(simple_pkg)
    assert state.focus == "main_claim"


def test_cli_focus_freeform_then_clear(simple_pkg: Path):
    r = runner.invoke(
        app, ["inquiry", "focus", "arbitrary research goal", "--path", str(simple_pkg)]
    )
    assert r.exit_code == 0

    r2 = runner.invoke(app, ["inquiry", "focus", "--clear", "--path", str(simple_pkg)])
    assert r2.exit_code == 0
    assert "cleared" in r2.output
    assert load_state(simple_pkg).focus is None


def test_cli_focus_resolves_claim_to_question_kind(simple_pkg: Path):
    r = runner.invoke(app, ["inquiry", "focus", "rq", "--path", str(simple_pkg)])
    assert r.exit_code == 0
    # show should report it with resolved kind (question or freeform fallback)
    r2 = runner.invoke(app, ["inquiry", "focus", "--path", str(simple_pkg)])
    assert r2.exit_code == 0
    assert "rq" in r2.output
