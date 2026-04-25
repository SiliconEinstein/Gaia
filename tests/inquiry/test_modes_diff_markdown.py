"""Step 6/7/8 — mode ranking, extended diff (16 categories), markdown renderer."""

from __future__ import annotations

from pathlib import Path

from gaia.inquiry.diagnostics import Diagnostic, NextEdit
from gaia.inquiry.diff import (
    SemanticDiff,
    compute_semantic_diff,
)
from gaia.inquiry.ranking import (
    rank_diagnostics,
    rank_next_edits,
    supported_modes,
)
from gaia.inquiry.review import render_markdown, run_review


# --------------------------------------------------------------------------- #
# §14.2 — extended diff categories                                            #
# --------------------------------------------------------------------------- #


def _baseline_snapshot(ir: dict, review_id: str = "base-id") -> dict:
    return {"review_id": review_id, "ir": ir, "beliefs": []}


def _claim(cid: str, label: str, content: str = "", prior=None, exported: bool = False) -> dict:
    md: dict = {}
    if prior is not None:
        md["prior"] = prior
    return {
        "id": cid,
        "label": label,
        "type": "claim",
        "content": content,
        "metadata": md,
        "exported": exported,
    }


def _question(qid: str, label: str) -> dict:
    return {"id": qid, "label": label, "type": "question", "content": "", "metadata": {}}


def _setting(sid: str, label: str) -> dict:
    return {"id": sid, "label": label, "type": "setting", "content": "", "metadata": {}}


def _strategy(sid: str, conclusion: str, premises: list[str]) -> dict:
    return {
        "id": sid,
        "conclusion": conclusion,
        "premises": list(premises),
        "background": [],
    }


def _operator(oid: str, conclusion: str, variables: list[str]) -> dict:
    return {"id": oid, "conclusion": conclusion, "variables": list(variables)}


def test_diff_added_removed_questions():
    base_ir = {"knowledges": [_question("q::a", "qa")], "strategies": [], "operators": []}
    cur_ir = {"knowledges": [_question("q::b", "qb")], "strategies": [], "operators": []}
    d = compute_semantic_diff(cur_ir, _baseline_snapshot(base_ir))
    assert d.added_questions == ["qb"]
    assert d.removed_questions == ["qa"]


def test_diff_added_removed_settings():
    base_ir = {"knowledges": [_setting("s::a", "sa")], "strategies": [], "operators": []}
    cur_ir = {
        "knowledges": [_setting("s::b", "sb"), _setting("s::a", "sa")],
        "strategies": [],
        "operators": [],
    }
    d = compute_semantic_diff(cur_ir, _baseline_snapshot(base_ir))
    assert d.added_settings == ["sb"]
    assert d.removed_settings == []


def test_diff_added_removed_changed_operators():
    base_ir = {
        "knowledges": [],
        "strategies": [],
        "operators": [_operator("op::keep", "y=Ax", ["x"]), _operator("op::gone", "z=0", [])],
    }
    cur_ir = {
        "knowledges": [],
        "strategies": [],
        "operators": [
            _operator("op::keep", "y=Bx", ["x", "b"]),
            _operator("op::new", "u=v", ["v"]),
        ],
    }
    d = compute_semantic_diff(cur_ir, _baseline_snapshot(base_ir))
    assert d.added_operators == ["new"]
    assert d.removed_operators == ["gone"]
    fields = sorted(c.field for c in d.changed_operators)
    assert fields == ["conclusion", "variables"]


def test_diff_changed_exports():
    base_ir = {
        "knowledges": [_claim("c::a", "ca", exported=False)],
        "strategies": [],
        "operators": [],
    }
    cur_ir = {
        "knowledges": [_claim("c::a", "ca", exported=True)],
        "strategies": [],
        "operators": [],
    }
    d = compute_semantic_diff(cur_ir, _baseline_snapshot(base_ir))
    assert len(d.changed_exports) == 1
    assert d.changed_exports[0].label == "ca"
    assert d.changed_exports[0].before == "False"
    assert d.changed_exports[0].after == "True"


def test_diff_to_dict_has_all_16_keys():
    d = SemanticDiff()
    keys = set(d.to_dict().keys()) - {"baseline_review_id"}
    assert keys == {
        "added_claims",
        "removed_claims",
        "changed_claims",
        "added_questions",
        "removed_questions",
        "added_settings",
        "removed_settings",
        "added_strategies",
        "removed_strategies",
        "changed_strategies",
        "added_operators",
        "removed_operators",
        "changed_operators",
        "changed_priors",
        "changed_exports",
    }


# --------------------------------------------------------------------------- #
# §7 / §15.4 — mode-specific ranking                                          #
# --------------------------------------------------------------------------- #


def _diag(kind: str, severity: str = "warning", label: str = "x") -> Diagnostic:
    return Diagnostic(
        severity=severity,
        kind=kind,
        target=label,
        label=label,
        message=f"{kind} for {label}",
        suggested_edit=f"fix {label}",
    )


def test_supported_modes_match_spec():
    assert set(supported_modes()) == {"auto", "formalize", "explore", "verify", "publish"}


def test_rank_explore_promotes_focus_weakness():
    ds = [
        _diag("prior_hole", "warning", "ph"),
        _diag("focus_weakness", "warning", "fw"),
        _diag("validation_warning", "warning", "vw"),
    ]
    ranked = rank_diagnostics(ds, "explore")
    assert ranked[0].kind == "focus_weakness"
    # prior_hole drops to last since it has rank 10 in explore.
    assert ranked[-1].kind == "prior_hole"


def test_rank_formalize_promotes_prior_holes_and_structural_holes():
    ds = [
        _diag("focus_weakness", "warning", "fw"),
        _diag("prior_hole", "warning", "ph"),
        _diag("structural_hole", "warning", "sh"),
    ]
    ranked = rank_diagnostics(ds, "formalize")
    kinds = [d.kind for d in ranked]
    assert (
        kinds.index("structural_hole") < kinds.index("prior_hole") < kinds.index("focus_weakness")
    )


def test_rank_publish_keeps_compile_errors_first():
    ds = [
        _diag("background_only_claim", "info", "bg"),
        _diag("compile_error", "error", "ce"),
        _diag("prior_hole", "warning", "ph"),
    ]
    ranked = rank_diagnostics(ds, "publish")
    assert ranked[0].kind == "compile_error"


def test_rank_unknown_kind_does_not_drop():
    ds = [
        _diag("prior_hole", "warning", "ph"),
        Diagnostic(
            severity="warning",
            kind="future_unknown_kind",  # type: ignore[arg-type]
            target="z",
            label="z",
            message="future",
            suggested_edit="fix z",
        ),
    ]
    ranked = rank_diagnostics(ds, "auto")
    assert len(ranked) == 2
    assert {d.kind for d in ranked} == {"prior_hole", "future_unknown_kind"}


def test_rank_next_edits_severity_tiebreak():
    edits = [
        NextEdit(text="A", kind="prior_hole", severity="info", target="a", label="a"),
        NextEdit(text="B", kind="prior_hole", severity="error", target="b", label="b"),
        NextEdit(text="C", kind="prior_hole", severity="warning", target="c", label="c"),
    ]
    ranked = rank_next_edits(edits, "auto")
    assert [e.severity for e in ranked] == ["error", "warning", "info"]


# --------------------------------------------------------------------------- #
# §17.2 — markdown renderer                                                   #
# --------------------------------------------------------------------------- #


def test_render_markdown_has_all_eight_sections(simple_pkg: Path):
    report = run_review(simple_pkg, no_infer=True)
    md = render_markdown(report)
    for heading in (
        "# Gaia Inquiry Review",
        "## Focus",
        "## Compile",
        "## Semantic diff",
        "## Graph health",
        "## Inquiry tree",
        "## Prior holes",
        "## Belief report",
        "## Next edits",
    ):
        assert heading in md, f"missing section: {heading}\n---\n{md}"


def test_render_markdown_includes_review_id(simple_pkg: Path):
    report = run_review(simple_pkg, no_infer=True)
    md = render_markdown(report)
    assert f"`{report.review_id}`" in md


def test_render_markdown_diff_section_lists_added_categories(tmp_path: Path):
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "diffmd-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg / "diffmd"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, question\n"
        'a = claim("a")\n'
        'q = question("q")\n'
        '__all__ = ["a", "q"]\n',
        encoding="utf-8",
    )
    r1 = run_review(pkg, no_infer=True)

    (src / "__init__.py").write_text(
        "from gaia.lang import claim, question\n"
        'a = claim("a")\n'
        'b = claim("b")\n'
        'q = question("q")\n'
        'q2 = question("q2")\n'
        '__all__ = ["a", "b", "q", "q2"]\n',
        encoding="utf-8",
    )
    r2 = run_review(pkg, no_infer=True, since=r1.review_id)
    md = render_markdown(r2)
    assert "Added claims" in md
    assert "Added questions" in md
