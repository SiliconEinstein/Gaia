"""Unit tests for gaia.inquiry.state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.inquiry.state import (
    STATE_SCHEMA_VERSION,
    InquiryState,
    SyntheticHypothesis,
    SyntheticObligation,
    SyntheticRejection,
    append_tactic_event,
    inquiry_dir,
    load_state,
    mint_qid,
    pop_focus_frame,
    push_focus_frame,
    read_tactic_log,
    save_state,
)


def test_empty_state_roundtrip(tmp_path: Path):
    state = load_state(tmp_path)
    assert state.version == STATE_SCHEMA_VERSION
    assert state.focus is None
    assert state.synthetic_obligations == []
    save_state(tmp_path, state)
    again = load_state(tmp_path)
    assert again.to_dict() == state.to_dict()


def test_state_persists_focus_and_obligations(tmp_path: Path):
    s = InquiryState()
    s.focus = "main_claim"
    s.focus_kind = "claim"
    s.synthetic_obligations.append(
        SyntheticObligation(
            qid=mint_qid("oblig"),
            target_qid="github:p::main_claim",
            content="needs prior",
            diagnostic_kind="prior_hole",
        )
    )
    save_state(tmp_path, s)

    raw = json.loads((inquiry_dir(tmp_path) / "state.json").read_text("utf-8"))
    assert raw["version"] == STATE_SCHEMA_VERSION
    assert raw["focus"] == "main_claim"
    assert raw["synthetic_obligations"][0]["diagnostic_kind"] == "prior_hole"

    reloaded = load_state(tmp_path)
    assert reloaded.focus == "main_claim"
    assert len(reloaded.synthetic_obligations) == 1


def test_future_version_rejected(tmp_path: Path):
    inquiry_dir(tmp_path).joinpath("state.json").write_text(
        json.dumps({"version": STATE_SCHEMA_VERSION + 5, "focus": None}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_state(tmp_path)


def test_invalid_mode_rejected(tmp_path: Path):
    inquiry_dir(tmp_path).joinpath("state.json").write_text(
        json.dumps({"version": STATE_SCHEMA_VERSION, "mode": "bogus"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_state(tmp_path)


def test_invalid_obligation_kind_rejected():
    with pytest.raises(ValueError):
        SyntheticObligation(qid="x", target_qid="t", content="c", diagnostic_kind="bogus")


def test_focus_push_and_pop_roundtrip(tmp_path: Path):
    s = InquiryState()
    s.focus = "a"
    push_focus_frame(s)
    s.focus = "b"
    assert s.focus_stack and s.focus_stack[-1]["focus"] == "a"

    old = pop_focus_frame(s)
    assert old == {"focus": "b", "focus_kind": None, "focus_resolved_id": None}
    assert s.focus == "a"
    assert s.focus_stack == []


def test_pop_empty_stack_returns_none():
    s = InquiryState()
    assert pop_focus_frame(s) is None


def test_tactic_log_append_and_read(tmp_path: Path):
    append_tactic_event(tmp_path, "focus_set", {"target": "a"})
    append_tactic_event(tmp_path, "obligation_add", {"qid": "x"})
    log = read_tactic_log(tmp_path)
    assert [r["event"] for r in log] == ["focus_set", "obligation_add"]
    assert log[0]["payload"]["target"] == "a"


def test_synthetic_hypothesis_and_rejection_dataclasses():
    h = SyntheticHypothesis(qid="h1", content="iid", scope_qid="c1")
    r = SyntheticRejection(qid="r1", target_strategy="s", content="loop")
    assert h.created_at and r.created_at
