"""Step 5 — source anchor + structured NextEdit (Round A2)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.inquiry.anchor import SourceAnchor, find_anchors
from gaia.inquiry.diagnostics import (
    Diagnostic,
    NextEdit,
    format_diagnostics_as_next_edits,
    format_diagnostics_as_structured_edits,
)
from gaia.inquiry.review import run_review

runner = CliRunner()


def _write_pkg(pkg_dir: Path, name: str = "anchor_pkg") -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir(exist_ok=True)
    body = (
        "from gaia.lang import claim, support\n"
        "\n"
        "# a prior hole (no prior set) — should be anchored\n"
        'hypothesis = claim("unverified hypothesis")\n'
        'evidence = claim("evidence", metadata={"prior": 0.7})\n'
        "\n"
        "conclusion = claim(\n"
        '    "conclusion from above"\n'
        ")\n"
        "sup = support(premises=[hypothesis, evidence], conclusion=conclusion)\n"
        '__all__ = ["hypothesis", "evidence", "conclusion", "sup"]\n'
    )
    (src / "__init__.py").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# anchor.find_anchors — pure AST scan                                         #
# --------------------------------------------------------------------------- #


def test_find_anchors_locates_claims(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    anchors = find_anchors(pkg)
    assert "hypothesis" in anchors
    assert "evidence" in anchors
    assert "conclusion" in anchors
    assert "sup" in anchors
    ha = anchors["hypothesis"]
    assert isinstance(ha, SourceAnchor)
    assert ha.file.endswith("__init__.py")
    # hypothesis 赋值在第 4 行 (from; 空行; 注释; hypothesis=...)
    assert ha.line == 4


def test_find_anchors_multiline_call(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    anchors = find_anchors(pkg)
    # conclusion = claim("conclusion from above") 跨两行, ast 取起始行
    assert anchors["conclusion"].line == 7


def test_find_anchors_handles_syntax_error(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    (pkg / "anchor_pkg" / "broken.py").write_text("def oops(\n", encoding="utf-8")
    anchors = find_anchors(pkg)
    # 坏文件被跳过, 正常文件仍被解析
    assert "hypothesis" in anchors


def test_find_anchors_ignores_hidden_dirs(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    hidden = pkg / ".gaia" / "cache"
    hidden.mkdir(parents=True)
    (hidden / "leak.py").write_text(
        'from gaia.lang import claim\nleak = claim("x")\n', encoding="utf-8"
    )
    anchors = find_anchors(pkg)
    assert "leak" not in anchors


def test_find_anchors_returns_empty_for_nonexistent(tmp_path):
    assert find_anchors(tmp_path / "does_not_exist") == {}


# --------------------------------------------------------------------------- #
# Diagnostic now carries source_anchor                                        #
# --------------------------------------------------------------------------- #


def test_review_diagnostics_carry_anchor(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    hole_diags = [d for d in report.diagnostics if d.kind == "prior_hole"]
    assert hole_diags, "expected at least one prior_hole diagnostic"
    for d in hole_diags:
        assert d.source_anchor is not None
        assert d.source_anchor.file.endswith("__init__.py")
        assert d.source_anchor.line >= 1


def test_diagnostic_to_dict_omits_anchor_when_missing():
    d = Diagnostic(
        severity="warning",
        kind="validation_warning",
        target="graph",
        label="graph",
        message="m",
    )
    payload = d.to_dict()
    assert "source_anchor" not in payload


def test_diagnostic_to_dict_includes_anchor():
    d = Diagnostic(
        severity="warning",
        kind="prior_hole",
        target="t",
        label="lbl",
        message="m",
        suggested_edit="fix it",
        source_anchor=SourceAnchor(file="mod.py", line=3, column=0),
    )
    payload = d.to_dict()
    assert payload["source_anchor"] == {"file": "mod.py", "line": 3, "column": 0}


# --------------------------------------------------------------------------- #
# NextEdit structured                                                         #
# --------------------------------------------------------------------------- #


def test_text_next_edit_contains_file_line(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    assert any("__init__.py:" in edit for edit in report.next_edits), report.next_edits


def test_structured_next_edits_have_anchor(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    assert report.next_edits_structured
    assert len(report.next_edits_structured) == len(report.next_edits)
    for e in report.next_edits_structured:
        assert isinstance(e, NextEdit)
        assert e.text
        assert e.kind
        assert e.severity in ("error", "warning", "info")
    assert any(e.source_anchor is not None for e in report.next_edits_structured)


def test_structured_next_edits_dedup_matches_text():
    diags = [
        Diagnostic(
            severity="warning",
            kind="prior_hole",
            target="a",
            label="a",
            message="m1",
            suggested_edit="same edit",
        ),
        Diagnostic(
            severity="warning",
            kind="orphaned_claim",
            target="b",
            label="b",
            message="m2",
            suggested_edit="same edit",
        ),
        Diagnostic(
            severity="error",
            kind="validation_error",
            target="graph",
            label="graph",
            message="m3",
            suggested_edit="fix error",
        ),
    ]
    text = format_diagnostics_as_next_edits(diags)
    struct = format_diagnostics_as_structured_edits(diags)
    assert len(text) == len(struct) == 2
    # error 排在 warning 前
    assert struct[0].severity == "error"
    assert struct[0].text == "fix error"
    assert struct[1].text == "same edit"


# --------------------------------------------------------------------------- #
# CLI JSON 输出 schema                                                        #
# --------------------------------------------------------------------------- #


def test_cli_json_contains_next_edits_structured(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert "next_edits_structured" in data
    assert data["next_edits_structured"]
    first = data["next_edits_structured"][0]
    assert {"text", "kind", "severity", "target", "label"} <= set(first)
