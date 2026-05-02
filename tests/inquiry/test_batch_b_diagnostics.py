"""Tests for Batch B Inquiry diagnostics:
stale_artifact / focus_low_posterior / prior_without_justification /
unreviewed_warrant / rejected_warrant + publish_blockers strict gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from gaia.cli.commands.check_core import HoleEntry, KnowledgeBreakdown
from gaia.inquiry.diagnostics import (
    Diagnostic,
    detect_focus_low_posterior,
    detect_prior_without_justification,
    detect_stale_artifact,
    detect_warrant_status,
)
from gaia.inquiry.ranking import rank_diagnostics, supported_modes
from gaia.inquiry.review import publish_blockers, run_review


# --------------------------------------------------------------------------- #
# stale_artifact
# --------------------------------------------------------------------------- #


def test_stale_artifact_emits_when_hash_differs(tmp_path: Path) -> None:
    (tmp_path / ".gaia").mkdir()
    (tmp_path / ".gaia" / "ir_hash").write_text("abc123old")
    diags = detect_stale_artifact(tmp_path, current_ir_hash="def456new")
    assert len(diags) == 1
    assert diags[0].kind == "stale_artifact"
    assert diags[0].severity == "warning"
    assert "abc123" in diags[0].message
    assert "def456" in diags[0].message


def test_stale_artifact_silent_when_hash_matches(tmp_path: Path) -> None:
    (tmp_path / ".gaia").mkdir()
    (tmp_path / ".gaia" / "ir_hash").write_text("samehash")
    assert detect_stale_artifact(tmp_path, current_ir_hash="samehash") == []


def test_stale_artifact_silent_when_no_recorded_file(tmp_path: Path) -> None:
    assert detect_stale_artifact(tmp_path, current_ir_hash="anyhash") == []


def test_stale_artifact_silent_when_no_current_hash(tmp_path: Path) -> None:
    (tmp_path / ".gaia").mkdir()
    (tmp_path / ".gaia" / "ir_hash").write_text("recorded")
    assert detect_stale_artifact(tmp_path, current_ir_hash=None) == []


# --------------------------------------------------------------------------- #
# focus_low_posterior
# --------------------------------------------------------------------------- #


def test_focus_low_posterior_emits_below_threshold() -> None:
    belief_report = {"focus": {"knowledge_id": "k::x", "label": "x", "after": 0.1, "before": 0.5}}
    diags = detect_focus_low_posterior(belief_report, threshold=0.3)
    assert len(diags) == 1
    assert diags[0].kind == "focus_low_posterior"
    assert diags[0].label == "x"
    assert diags[0].data["posterior"] == 0.1


def test_focus_low_posterior_silent_above_threshold() -> None:
    belief_report = {"focus": {"knowledge_id": "k::y", "label": "y", "after": 0.9}}
    assert detect_focus_low_posterior(belief_report, threshold=0.3) == []


def test_focus_low_posterior_silent_when_no_focus() -> None:
    assert detect_focus_low_posterior({"focus": None}) == []
    assert detect_focus_low_posterior({}) == []


# --------------------------------------------------------------------------- #
# prior_without_justification
# --------------------------------------------------------------------------- #


def test_prior_without_justification_emits_for_empty_justification() -> None:
    kb = KnowledgeBreakdown()
    kb.independent.append(
        HoleEntry(cid="c::a", label="a", content="ca", prior=0.7, prior_justification="")
    )
    kb.independent.append(
        HoleEntry(cid="c::b", label="b", content="cb", prior=0.3, prior_justification="ok")
    )
    kb.independent.append(
        HoleEntry(cid="c::c", label="c", content="cc", prior=None, prior_justification="")
    )
    diags = detect_prior_without_justification(kb)
    labels = {d.label for d in diags}
    assert labels == {"a"}
    assert diags[0].kind == "prior_without_justification"
    assert diags[0].severity == "info"


# --------------------------------------------------------------------------- #
# warrant_status
# --------------------------------------------------------------------------- #


@dataclass
class _S:
    id: str
    metadata: dict = field(default_factory=dict)


@dataclass
class _G:
    strategies: list = field(default_factory=list)


def test_warrant_status_unreviewed_for_no_judgment() -> None:
    g = _G(strategies=[_S(id="s::s1"), _S(id="s::s2", metadata={"judgment": "accepted"})])
    diags = detect_warrant_status(g, rejected_strategy_targets=set())
    kinds = [(d.kind, d.label) for d in diags]
    assert ("unreviewed_warrant", "s1") in kinds
    assert all(d.label != "s2" for d in diags)


def test_warrant_status_rejected_takes_priority() -> None:
    g = _G(strategies=[_S(id="s::s1")])
    diags = detect_warrant_status(g, rejected_strategy_targets={"s1"})
    assert len(diags) == 1
    assert diags[0].kind == "rejected_warrant"
    assert diags[0].label == "s1"


def test_warrant_status_handles_missing_graph() -> None:
    assert detect_warrant_status(None, set()) == []


# --------------------------------------------------------------------------- #
# Ranking — new kinds appear in every mode (no kind silently rank=99).
# --------------------------------------------------------------------------- #


def test_ranking_includes_all_new_kinds_for_every_mode() -> None:
    new_kinds = [
        "stale_artifact",
        "focus_low_posterior",
        "prior_without_justification",
        "unreviewed_warrant",
        "rejected_warrant",
    ]
    for mode in supported_modes():
        diags = [
            Diagnostic(severity="warning", kind=k, target=k, label=k, message=k) for k in new_kinds
        ]
        ranked = rank_diagnostics(diags, mode)
        # All present (no drop), and kind-rank lookup must be < 99.
        from gaia.inquiry.ranking import _MODE_RANK, _UNKNOWN_KIND_RANK

        table = _MODE_RANK[mode]
        for d in ranked:
            assert table.get(d.kind, _UNKNOWN_KIND_RANK) < _UNKNOWN_KIND_RANK, (
                f"{d.kind} not ranked for mode={mode}"
            )


# --------------------------------------------------------------------------- #
# publish_blockers
# --------------------------------------------------------------------------- #


def _empty_report():
    from gaia.inquiry.focus import FocusBinding
    from gaia.inquiry.review import ReviewReport

    return ReviewReport(
        review_id="r",
        created_at="t",
        path="p",
        focus=FocusBinding(raw=None, kind="none", resolved_id=None),
        mode="publish",
        compile_status="ok",
        ir_hash="h",
        counts={"knowledge": 0, "strategies": 0, "operators": 0},
    )


def test_publish_blockers_empty_for_clean_report() -> None:
    report = _empty_report()
    assert publish_blockers(report) == []


def test_publish_blockers_flags_prior_hole_diagnostic() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="warning", kind="prior_hole", target="c::a", label="a", message="missing prior"
        )
    ]
    blockers = publish_blockers(report)
    assert len(blockers) == 1
    assert "prior_hole" in blockers[0]
    assert "a" in blockers[0]


def test_publish_blockers_flags_graph_warnings_and_errors() -> None:
    report = _empty_report()
    report.graph_health = {"errors": ["bad node"], "warnings": ["weird ref"]}
    blockers = publish_blockers(report)
    assert any("graph error" in b for b in blockers)
    assert any("graph warning" in b for b in blockers)


def test_publish_blockers_ignores_non_blocking_kinds() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="info", kind="rejected_warrant", target="s::s1", label="s1", message="rejected"
        ),
        Diagnostic(
            severity="info", kind="background_only", target="c::b", label="b", message="bg only"
        ),
    ]
    assert publish_blockers(report) == []


# --------------------------------------------------------------------------- #
# End-to-end via run_review on simple_pkg fixture (no rejections, no judgments).
# --------------------------------------------------------------------------- #


def test_run_review_in_publish_mode_runs_clean(simple_pkg):
    report = run_review(str(simple_pkg), mode="publish")
    # simple_pkg compiles, and the new diagnostic emitters must integrate
    # cleanly into the run pipeline.
    assert report.compile_status == "ok"
    kinds = {d.kind for d in report.diagnostics}
    assert "orphaned_claim" in kinds
    publish_blockers(report)  # must not raise
