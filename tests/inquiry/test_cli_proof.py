"""Tests for the ProofState-extended gaia inquiry CLI (Round A1)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _simple_pkg(pkg_dir, name: str = "proof_pkg") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim\n"
        'main_claim = claim("main hypothesis", metadata={"prior": 0.5})\n'
        '__all__ = ["main_claim"]\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# focus push / pop / stack
# ---------------------------------------------------------------------------


def test_focus_push_then_stack_then_pop(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    runner.invoke(app, ["inquiry", "focus", "a", "--path", str(pkg)])
    r = runner.invoke(app, ["inquiry", "focus", "b", "--push", "--path", str(pkg)])
    assert r.exit_code == 0
    assert "focus pushed: b" in r.output

    r2 = runner.invoke(app, ["inquiry", "focus", "--stack", "--path", str(pkg)])
    assert r2.exit_code == 0
    assert "current: b" in r2.output
    assert "a" in r2.output

    r3 = runner.invoke(app, ["inquiry", "focus", "--pop", "--path", str(pkg)])
    assert r3.exit_code == 0
    assert "popped" in r3.output
    assert "a" in r3.output


def test_focus_push_without_target_rejected(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "focus", "--push", "--path", str(pkg)])
    assert r.exit_code == 2


def test_focus_multiple_flags_rejected(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "focus", "--push", "--pop", "--path", str(pkg)])
    assert r.exit_code == 2


# ---------------------------------------------------------------------------
# obligation add / list / close
# ---------------------------------------------------------------------------


def test_obligation_add_and_list(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(
        app,
        [
            "inquiry",
            "obligation",
            "add",
            "github:proof_pkg::main_claim",
            "-c",
            "需要独立 prior",
            "--kind",
            "prior_hole",
            "--path",
            str(pkg),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "obligation added" in r.output

    r2 = runner.invoke(app, ["inquiry", "obligation", "list", "--json", "--path", str(pkg)])
    assert r2.exit_code == 0
    rows = json.loads(r2.output)
    assert len(rows) == 1
    assert rows[0]["diagnostic_kind"] == "prior_hole"
    assert rows[0]["target_qid"] == "github:proof_pkg::main_claim"


def test_obligation_close(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(
        app,
        [
            "inquiry",
            "obligation",
            "add",
            "X",
            "-c",
            "a",
            "--kind",
            "prior_hole",
            "--path",
            str(pkg),
        ],
    )
    assert r.exit_code == 0
    qid = r.output.strip().split()[2]

    r2 = runner.invoke(app, ["inquiry", "obligation", "close", qid, "--path", str(pkg)])
    assert r2.exit_code == 0
    assert "closed" in r2.output

    r3 = runner.invoke(app, ["inquiry", "obligation", "list", "--path", str(pkg)])
    assert "(no open obligations)" in r3.output


def test_obligation_close_nonexistent_fails(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "obligation", "close", "no_such", "--path", str(pkg)])
    assert r.exit_code == 1


def test_obligation_bad_kind_rejected(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(
        app,
        ["inquiry", "obligation", "add", "X", "-c", "a", "--kind", "bogus", "--path", str(pkg)],
    )
    assert r.exit_code == 2


# ---------------------------------------------------------------------------
# hypothesis
# ---------------------------------------------------------------------------


def test_hypothesis_add_list_remove(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(
        app,
        [
            "inquiry",
            "hypothesis",
            "add",
            "训练数据 i.i.d.",
            "--scope",
            "github:proof_pkg::main_claim",
            "--path",
            str(pkg),
        ],
    )
    assert r.exit_code == 0
    qid = r.output.strip().split()[2]

    r2 = runner.invoke(app, ["inquiry", "hypothesis", "list", "--json", "--path", str(pkg)])
    rows = json.loads(r2.output)
    assert len(rows) == 1
    assert rows[0]["content"] == "训练数据 i.i.d."
    assert rows[0]["scope_qid"] == "github:proof_pkg::main_claim"

    r3 = runner.invoke(app, ["inquiry", "hypothesis", "remove", qid, "--path", str(pkg)])
    assert r3.exit_code == 0


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


def test_reject_strategy(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "reject", "lcs_bad_s3", "-c", "loop", "--path", str(pkg)])
    assert r.exit_code == 0
    assert "rejected" in r.output


# ---------------------------------------------------------------------------
# tactics log
# ---------------------------------------------------------------------------


def test_tactics_log_captures_events(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    runner.invoke(app, ["inquiry", "focus", "a", "--path", str(pkg)])
    runner.invoke(
        app,
        ["inquiry", "obligation", "add", "X", "-c", "a", "--kind", "other", "--path", str(pkg)],
    )
    r = runner.invoke(app, ["inquiry", "tactics", "log", "--json", "--path", str(pkg)])
    assert r.exit_code == 0
    rows = json.loads(r.output)
    events = {row["event"] for row in rows}
    assert "focus_set" in events
    assert "obligation_add" in events


def test_tactics_log_empty(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "tactics", "log", "--path", str(pkg)])
    assert r.exit_code == 0
    assert "(no tactic log entries)" in r.output


# ---------------------------------------------------------------------------
# review includes proof state
# ---------------------------------------------------------------------------


def test_review_renders_proof_state_section(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    runner.invoke(
        app,
        [
            "inquiry",
            "obligation",
            "add",
            "github:proof_pkg::main_claim",
            "-c",
            "need prior",
            "--kind",
            "prior_hole",
            "--path",
            str(pkg),
        ],
    )
    r = runner.invoke(app, ["inquiry", "review", str(pkg)])
    assert r.exit_code == 0, r.output
    assert "## Proof state" in r.output
    assert "obligations (1)" in r.output


def test_review_json_includes_proof_context(tmp_path):
    pkg = tmp_path / "p"
    _simple_pkg(pkg)
    runner.invoke(
        app,
        ["inquiry", "hypothesis", "add", "iid", "--path", str(pkg)],
    )
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--json"])
    assert r.exit_code == 0
    parsed = json.loads(r.output)
    assert "proof_context" in parsed
    assert len(parsed["proof_context"]["hypotheses"]) == 1
