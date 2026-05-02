"""Tests for the remaining 5 §15.2 diagnostic kinds:

blocked_warrant_path / focus_unsupported / large_belief_drop /
overstrong_strategy_without_provenance /
claim_with_evidence_but_no_focus_connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from gaia.cli.commands.check_core import HoleEntry, KnowledgeBreakdown
from gaia.inquiry.diagnostics import (
    Diagnostic,
    detect_blocked_warrant_path,
    detect_claim_with_evidence_but_no_focus_connection,
    detect_focus_unsupported,
    detect_large_belief_drop,
    detect_overstrong_strategy_without_provenance,
)
from gaia.inquiry.focus import FocusBinding
from gaia.inquiry.ranking import _MODE_RANK, _UNKNOWN_KIND_RANK, supported_modes
from gaia.inquiry.review import publish_blockers, run_review


# --------------------------------------------------------------------------- #
# Lightweight graph stubs                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class _K:
    id: str
    label: str = ""


@dataclass
class _S:
    id: str
    conclusion: str | None = None
    premises: list = field(default_factory=list)
    background: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class _O:
    id: str
    conclusion: str | None = None
    variables: list = field(default_factory=list)


@dataclass
class _G:
    knowledges: list = field(default_factory=list)
    strategies: list = field(default_factory=list)
    operators: list = field(default_factory=list)


def _focus(target_id: str | None) -> FocusBinding:
    return FocusBinding(raw=target_id, kind="claim", resolved_id=target_id)


# --------------------------------------------------------------------------- #
# blocked_warrant_path                                                        #
# --------------------------------------------------------------------------- #


def test_blocked_warrant_path_emits_when_premise_is_hole() -> None:
    kb = KnowledgeBreakdown()
    kb.independent.append(HoleEntry(cid="c::a", label="a", content="ca", prior=None))
    g = _G(
        strategies=[
            _S(id="s::s1", conclusion="c::z", premises=["c::a", "c::b"]),
            _S(id="s::s2", conclusion="c::y", premises=["c::b"]),
        ]
    )
    diags = detect_blocked_warrant_path(g, kb)
    assert len(diags) == 1
    d = diags[0]
    assert d.kind == "blocked_warrant_path"
    assert d.label == "s1"
    assert d.severity == "warning"
    assert d.data["blocking_premises"] == ["c::a"]


def test_blocked_warrant_path_silent_when_no_holes() -> None:
    kb = KnowledgeBreakdown()
    g = _G(strategies=[_S(id="s::s1", conclusion="c::z", premises=["c::a"])])
    assert detect_blocked_warrant_path(g, kb) == []


def test_blocked_warrant_path_silent_when_graph_missing() -> None:
    kb = KnowledgeBreakdown()
    kb.holes.append(HoleEntry(cid="c::a", label="a", content="", prior=None))
    assert detect_blocked_warrant_path(None, kb) == []


# --------------------------------------------------------------------------- #
# focus_unsupported                                                           #
# --------------------------------------------------------------------------- #


def test_focus_unsupported_emits_when_no_reference() -> None:
    g = _G(
        knowledges=[_K(id="c::main", label="main")],
        strategies=[_S(id="s::s1", conclusion="c::other", premises=["c::p"])],
    )
    diags = detect_focus_unsupported(g, _focus("c::main"))
    assert len(diags) == 1
    assert diags[0].kind == "focus_unsupported"
    assert diags[0].label == "main"
    assert diags[0].severity == "warning"


def test_focus_unsupported_silent_when_strategy_concludes_focus() -> None:
    g = _G(strategies=[_S(id="s::s1", conclusion="c::main")])
    assert detect_focus_unsupported(g, _focus("c::main")) == []


def test_focus_unsupported_silent_when_used_as_premise() -> None:
    g = _G(strategies=[_S(id="s::s1", conclusion="c::z", premises=["c::main"])])
    assert detect_focus_unsupported(g, _focus("c::main")) == []


def test_focus_unsupported_silent_when_referenced_by_operator() -> None:
    g = _G(operators=[_O(id="o::o1", variables=["c::main"])])
    assert detect_focus_unsupported(g, _focus("c::main")) == []


def test_focus_unsupported_silent_when_no_focus() -> None:
    g = _G(strategies=[_S(id="s::s1")])
    assert detect_focus_unsupported(g, None) == []
    assert detect_focus_unsupported(g, _focus(None)) == []


# --------------------------------------------------------------------------- #
# large_belief_drop                                                           #
# --------------------------------------------------------------------------- #


def test_large_belief_drop_emits_at_or_below_threshold() -> None:
    report = {
        "largest_decreases": [
            {"label": "x", "before": 0.8, "after": 0.4, "delta": -0.4},
            {"label": "y", "before": 0.6, "after": 0.5, "delta": -0.1},
        ]
    }
    diags = detect_large_belief_drop(report, threshold=0.3)
    assert len(diags) == 1
    assert diags[0].label == "x"
    assert diags[0].kind == "large_belief_drop"
    assert diags[0].severity == "warning"
    assert diags[0].data["delta"] == pytest.approx(-0.4)


def test_large_belief_drop_silent_when_below_threshold() -> None:
    report = {"largest_decreases": [{"label": "y", "before": 0.6, "after": 0.5, "delta": -0.1}]}
    assert detect_large_belief_drop(report, threshold=0.3) == []


def test_large_belief_drop_silent_with_no_baseline() -> None:
    assert detect_large_belief_drop({"largest_decreases": []}) == []
    assert detect_large_belief_drop({}) == []


def test_large_belief_drop_handles_malformed_delta() -> None:
    report = {"largest_decreases": [{"label": "z", "delta": None}]}
    assert detect_large_belief_drop(report) == []


# --------------------------------------------------------------------------- #
# overstrong_strategy_without_provenance                                      #
# --------------------------------------------------------------------------- #


def test_overstrong_warning_when_high_strength_no_provenance() -> None:
    g = _G(strategies=[_S(id="s::s1", metadata={"strength": 0.9})])
    diags = detect_overstrong_strategy_without_provenance(g, strength_threshold=0.8)
    assert len(diags) == 1
    assert diags[0].severity == "warning"
    assert diags[0].kind == "overstrong_strategy_without_provenance"
    assert diags[0].data["strength"] == pytest.approx(0.9)


def test_overstrong_silent_when_provenance_present() -> None:
    g = _G(
        strategies=[
            _S(id="s::s1", metadata={"strength": 0.9, "provenance": "lemma 3.4"}),
        ]
    )
    assert detect_overstrong_strategy_without_provenance(g) == []


def test_overstrong_silent_when_justification_present() -> None:
    g = _G(strategies=[_S(id="s::s1", metadata={"justification": "matches paper §2"})])
    assert detect_overstrong_strategy_without_provenance(g) == []


def test_overstrong_info_when_no_strength_field() -> None:
    g = _G(strategies=[_S(id="s::s1", metadata={})])
    diags = detect_overstrong_strategy_without_provenance(g)
    assert len(diags) == 1
    assert diags[0].severity == "info"


def test_overstrong_uses_confidence_as_fallback() -> None:
    g = _G(strategies=[_S(id="s::s1", metadata={"confidence": 0.95})])
    diags = detect_overstrong_strategy_without_provenance(g, strength_threshold=0.8)
    assert len(diags) == 1
    assert diags[0].severity == "warning"


# --------------------------------------------------------------------------- #
# claim_with_evidence_but_no_focus_connection                                 #
# --------------------------------------------------------------------------- #


def test_claim_evidence_disconnected_emits() -> None:
    g = _G(
        knowledges=[
            _K(id="c::main", label="main"),
            _K(id="c::p", label="p"),
            _K(id="c::orphan_bg", label="orphan_bg"),
            _K(id="c::q", label="q"),
        ],
        strategies=[
            _S(id="s::s1", conclusion="c::main", premises=["c::p"]),
            _S(
                id="s::s2",
                conclusion="c::q",
                premises=[],
                background=["c::orphan_bg"],
            ),
        ],
    )
    diags = detect_claim_with_evidence_but_no_focus_connection(g, _focus("c::main"))
    labels = {d.label for d in diags}
    assert labels == {"orphan_bg"}
    assert diags[0].kind == "claim_with_evidence_but_no_focus_connection"
    assert diags[0].severity == "info"


def test_claim_evidence_silent_when_connected() -> None:
    g = _G(
        knowledges=[
            _K(id="c::main", label="main"),
            _K(id="c::ev", label="ev"),
        ],
        strategies=[
            _S(id="s::s1", conclusion="c::main", premises=[], background=["c::ev"]),
        ],
    )
    # ev 在 s::s1.background, c::main 是同一 strategy 的 conclusion → 同连通分量, 不报。
    assert detect_claim_with_evidence_but_no_focus_connection(g, _focus("c::main")) == []


def test_claim_evidence_silent_with_no_focus() -> None:
    g = _G()
    assert detect_claim_with_evidence_but_no_focus_connection(g, None) == []


def test_claim_evidence_silent_when_claim_in_premises() -> None:
    g = _G(
        knowledges=[
            _K(id="c::main", label="main"),
            _K(id="c::ev", label="ev"),
            _K(id="c::other", label="other"),
        ],
        strategies=[
            _S(id="s::s1", conclusion="c::main", premises=[]),
            _S(
                id="s::s2",
                conclusion="c::other",
                premises=["c::ev"],
                background=["c::ev"],
            ),
        ],
    )
    # ev 在 in_bg ∩ in_core → 不属于 bg_only, 不报。
    assert detect_claim_with_evidence_but_no_focus_connection(g, _focus("c::main")) == []


# --------------------------------------------------------------------------- #
# Ranking — every new kind is ranked in every mode (no rank=99 fallback).     #
# --------------------------------------------------------------------------- #


def test_ranking_includes_all_remaining_kinds_for_every_mode() -> None:
    new_kinds = [
        "blocked_warrant_path",
        "focus_unsupported",
        "large_belief_drop",
        "overstrong_strategy_without_provenance",
        "claim_with_evidence_but_no_focus_connection",
    ]
    for mode in supported_modes():
        table = _MODE_RANK[mode]
        for k in new_kinds:
            assert table.get(k, _UNKNOWN_KIND_RANK) < _UNKNOWN_KIND_RANK, (
                f"{k} not ranked for mode={mode}"
            )


# --------------------------------------------------------------------------- #
# publish_blockers — new blocking kinds                                       #
# --------------------------------------------------------------------------- #


def _empty_report():
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


def test_publish_blockers_flags_blocked_warrant_path() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="warning",
            kind="blocked_warrant_path",
            target="s::s1",
            label="s1",
            message="blocked",
        )
    ]
    blockers = publish_blockers(report)
    assert any("blocked_warrant_path" in b for b in blockers)


def test_publish_blockers_flags_focus_unsupported() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="warning",
            kind="focus_unsupported",
            target="c::m",
            label="m",
            message="no ref",
        )
    ]
    assert any("focus_unsupported" in b for b in publish_blockers(report))


def test_publish_blockers_flags_overstrong_without_provenance() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="info",
            kind="overstrong_strategy_without_provenance",
            target="s::s1",
            label="s1",
            message="no provenance",
        )
    ]
    assert any("overstrong" in b for b in publish_blockers(report))


def test_publish_blockers_ignores_large_belief_drop_and_no_focus_connection() -> None:
    report = _empty_report()
    report.diagnostics = [
        Diagnostic(
            severity="warning",
            kind="large_belief_drop",
            target="x",
            label="x",
            message="dropped",
        ),
        Diagnostic(
            severity="info",
            kind="claim_with_evidence_but_no_focus_connection",
            target="c::y",
            label="y",
            message="dangling",
        ),
    ]
    assert publish_blockers(report) == []


# --------------------------------------------------------------------------- #
# Integration: run_review on simple_pkg fixture; the new emitters compose.   #
# --------------------------------------------------------------------------- #


def test_run_review_integrates_new_diagnostics(simple_pkg) -> None:
    report = run_review(str(simple_pkg), mode="publish")
    assert report.compile_status == "ok"
    legal_kinds = set(_MODE_RANK["publish"].keys())
    for d in report.diagnostics:
        assert d.kind in legal_kinds, f"unknown diag kind leaked: {d.kind}"
