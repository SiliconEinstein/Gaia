"""TR-2：11 个 detector 各自最小阳性 + 阴性 + ranking trace mode。."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gaia.engine.trace.diagnostics import (
    detect_actor,
    detect_claim_refs,
    detect_decision_grounds,
    detect_hash_chain,
    detect_manifest_hash,
    detect_parent_links,
    detect_retry,
    detect_seq,
    detect_timestamps,
    detect_tool_pairing,
    from_schema_issues,
    run_all_detectors,
)
from gaia.engine.trace.hashing import (
    GENESIS_PREV_HASH,
    compute_events_root,
    compute_manifest_hash,
    hash_event,
)
from gaia.engine.trace.loader import LoadResult, SchemaIssue
from gaia.engine.trace.ranking import _MODE_RANK, rank_diagnostics, supported_modes
from gaia.engine.trace.schema import ClaimRef, Trace, TraceEvent, TraceManifest


def _ts(seq: int) -> datetime:
    return datetime(2026, 4, 28, tzinfo=UTC) + timedelta(seconds=seq)


def _ev(seq: int, prev_hash: str, **kw) -> TraceEvent:
    base = {
        "event_id": f"e{seq}",
        "seq": seq,
        "prev_hash": prev_hash,
        "ts": _ts(seq),
        "kind": "decision",
        "actor": "arm",
        "reason": "grounded by inputs",
        "inputs": {"step": "inputs"},
    }
    base.update(kw)
    return TraceEvent(**base)


def _build_clean(n: int = 3) -> Trace:
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(n):
        ev = _ev(i, prev_hash=prev)
        events.append(ev)
        prev = hash_event(ev)
    manifest = TraceManifest(
        arm_id="arm",
        session_id="s",
        trace_id="t",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    manifest = manifest.model_copy(update={"manifest_hash": compute_manifest_hash(manifest)})
    return Trace(manifest=manifest, events=events)


# ============ Detector 1：schema_violation ============


def test_from_schema_issues_translates_each_issue():
    issues = [
        SchemaIssue(message="missing field", location="events[0].seq"),
        SchemaIssue(message="bad type", location="manifest.arm_id"),
    ]
    diags = from_schema_issues(issues)
    assert len(diags) == 2
    assert all(d.kind == "trace_schema_violation" for d in diags)
    assert all(d.severity == "error" for d in diags)


# ============ Detector 2：hash_chain ============


def test_clean_trace_has_no_hash_chain_diagnostic():
    t = _build_clean()
    assert detect_hash_chain(t) == []


def test_hash_chain_break_detected_at_correct_seq():
    t = _build_clean(5)
    # 改 events[2] 内容 ⇒ 链在 events[3] 断开
    t.events[2] = t.events[2].model_copy(update={"reason": "tampered text"})
    diags = detect_hash_chain(t)
    assert any(d.data["broken_at_seq"] == 3 for d in diags)


def test_genesis_prev_hash_must_be_empty():
    t = _build_clean(3)
    t.events[0] = t.events[0].model_copy(update={"prev_hash": "abcd"})
    diags = detect_hash_chain(t)
    assert any(d.data["broken_at_seq"] == 0 for d in diags)


# ============ Detector 3：manifest_hash ============


def test_manifest_hash_clean_no_diag():
    t = _build_clean()
    assert detect_manifest_hash(t) == []


def test_events_root_mismatch_detected():
    t = _build_clean(3)
    bad = t.manifest.model_copy(update={"events_root": "0" * 64})
    t = Trace(manifest=bad, events=t.events)
    diags = detect_manifest_hash(t)
    assert any(d.target == "manifest.events_root" for d in diags)


def test_manifest_hash_mismatch_detected():
    t = _build_clean(3)
    bad = t.manifest.model_copy(update={"manifest_hash": "f" * 64})
    t = Trace(manifest=bad, events=t.events)
    diags = detect_manifest_hash(t)
    assert any(d.target == "manifest.manifest_hash" for d in diags)


# ============ Detector 4：timestamps ============


def test_timestamp_disorder_detected():
    t = _build_clean(3)
    bad_ts = t.events[1].ts - timedelta(seconds=10)
    t.events[1] = t.events[1].model_copy(update={"ts": bad_ts})
    diags = detect_timestamps(t)
    assert any(d.kind == "trace_timestamp_disorder" for d in diags)


def test_clean_timestamps_no_diag():
    t = _build_clean(5)
    assert detect_timestamps(t) == []


# ============ Detector 5：seq ============


def test_seq_jump_detected():
    t = _build_clean(3)
    t.events[2] = t.events[2].model_copy(update={"seq": 99})
    diags = detect_seq(t)
    assert any("seq jump" in d.message for d in diags)


def test_first_seq_must_be_zero():
    t = _build_clean(2)
    t.events[0] = t.events[0].model_copy(update={"seq": 7})
    t.events[1] = t.events[1].model_copy(update={"seq": 8})
    diags = detect_seq(t)
    assert diags  # 至少首事件 seq != 0


# ============ Detector 6：decision_grounds ============


def test_decision_without_reason_flagged():
    ev = _ev(0, prev_hash="", kind="decision", reason=None)
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_decision_grounds(Trace(manifest=m, events=[ev]))
    assert any("no `reason`" in d.message for d in diags)


def test_decision_reason_unrelated_to_inputs_flagged():
    ev = _ev(
        0,
        prev_hash="",
        kind="decision",
        reason="totally orthogonal text",
        inputs={"k": "alpha beta gamma"},
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_decision_grounds(Trace(manifest=m, events=[ev]))
    assert any("shares no token" in d.message for d in diags)


def test_decision_with_overlap_passes():
    ev = _ev(0, prev_hash="", reason="alpha was chosen", inputs={"k": "alpha"})
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_decision_grounds(Trace(manifest=m, events=[ev])) == []


# ============ Detector 7：tool_pairing ============


def test_tool_call_without_result_flagged():
    call = TraceEvent(
        event_id="c0",
        seq=0,
        prev_hash="",
        ts=_ts(0),
        kind="tool_call",
        actor="arm",
        tool="bash",
        inputs={"cmd": "ls"},
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_tool_pairing(Trace(manifest=m, events=[call]))
    assert any(d.kind == "tool_call_without_result" for d in diags)


def test_tool_call_paired_with_result_via_parent():
    call = TraceEvent(
        event_id="c0",
        seq=0,
        prev_hash="",
        ts=_ts(0),
        kind="tool_call",
        actor="arm",
        tool="bash",
    )
    result = TraceEvent(
        event_id="r0",
        seq=1,
        prev_hash="x",
        ts=_ts(1),
        kind="tool_result",
        actor="arm",
        parent_event_id="c0",
        outputs={"stdout": "ok"},
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_tool_pairing(Trace(manifest=m, events=[call, result])) == []


# ============ Detector 8：claim_ref ============


def test_claim_ref_unresolved_when_resolver_returns_false():
    ev = _ev(
        0,
        prev_hash="",
        refs=[ClaimRef(claim_id="c1", review_id="rev-1", relation="asserts")],
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_claim_refs(Trace(manifest=m, events=[ev]), resolver=lambda _r: False)
    assert any(d.kind == "unresolved_claim_ref" for d in diags)


def test_claim_ref_resolved_when_resolver_returns_true():
    ev = _ev(
        0,
        prev_hash="",
        refs=[ClaimRef(claim_id="c1", review_id="rev-1", relation="asserts")],
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_claim_refs(Trace(manifest=m, events=[ev]), resolver=lambda _r: True) == []


def test_claim_ref_resolver_exception_treated_as_unresolved():
    ev = _ev(
        0,
        prev_hash="",
        refs=[ClaimRef(claim_id="c1", review_id="r", relation="uses")],
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))

    def boom(_):
        raise RuntimeError("nope")

    diags = detect_claim_refs(Trace(manifest=m, events=[ev]), resolver=boom)
    assert any("resolver raised" in d.message for d in diags)


# ============ Detector 9：orphan_event ============


def test_orphan_parent_event_id_flagged():
    e0 = _ev(0, prev_hash="")
    e1 = _ev(1, prev_hash="x", parent_event_id="ghost")
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_parent_links(Trace(manifest=m, events=[e0, e1]))
    assert any(d.kind == "orphan_event" for d in diags)


def test_valid_parent_event_id_no_diag():
    e0 = _ev(0, prev_hash="")
    e1 = _ev(1, prev_hash="x", parent_event_id="e0")
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_parent_links(Trace(manifest=m, events=[e0, e1])) == []


# ============ Detector 10：retry ============


def test_retry_chain_within_limit_no_diag():
    events: list[TraceEvent] = [_ev(0, prev_hash="")]
    for i in range(1, 4):
        events.append(
            TraceEvent(
                event_id=f"r{i}",
                seq=i,
                prev_hash="x",
                ts=_ts(i),
                kind="retry",
                actor="arm",
                error="transient",
                parent_event_id=events[-1].event_id,
            )
        )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_retry(Trace(manifest=m, events=events), max_chain=5) == []


def test_retry_chain_exceeds_limit_flagged():
    events: list[TraceEvent] = [_ev(0, prev_hash="")]
    for i in range(1, 8):
        events.append(
            TraceEvent(
                event_id=f"r{i}",
                seq=i,
                prev_hash="x",
                ts=_ts(i),
                kind="retry",
                actor="arm",
                error="loop",
                parent_event_id=events[-1].event_id,
            )
        )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_retry(Trace(manifest=m, events=events), max_chain=3)
    assert any(d.kind == "retry_diverged" for d in diags)


# ============ Detector 11：actor_switch ============


def test_actor_switch_without_decision_flagged():
    e0 = TraceEvent(
        event_id="e0",
        seq=0,
        prev_hash="",
        ts=_ts(0),
        kind="intermediate_state",
        actor="A",
    )
    e1 = TraceEvent(
        event_id="e1",
        seq=1,
        prev_hash="x",
        ts=_ts(1),
        kind="intermediate_state",
        actor="B",
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    diags = detect_actor(Trace(manifest=m, events=[e0, e1]))
    assert any(d.kind == "actor_switch_unexplained" for d in diags)


def test_actor_switch_with_decision_in_between_no_diag():
    e0 = TraceEvent(
        event_id="e0",
        seq=0,
        prev_hash="",
        ts=_ts(0),
        kind="intermediate_state",
        actor="A",
    )
    e1 = TraceEvent(
        event_id="e1",
        seq=1,
        prev_hash="x",
        ts=_ts(1),
        kind="decision",
        actor="A",
        reason="grounded by step",
        inputs={"step": "x"},
    )
    e2 = TraceEvent(
        event_id="e2",
        seq=2,
        prev_hash="x",
        ts=_ts(2),
        kind="intermediate_state",
        actor="B",
    )
    m = TraceManifest(arm_id="a", session_id="s", trace_id="t", created_at=_ts(0))
    assert detect_actor(Trace(manifest=m, events=[e0, e1, e2])) == []


# ============ run_all_detectors + ranking ============


def test_run_all_detectors_clean_trace_yields_nothing():
    t = _build_clean(3)
    res = LoadResult(trace=t, issues=[])
    assert run_all_detectors(res) == []


def test_run_all_detectors_returns_schema_issues_when_trace_none():
    issues = [SchemaIssue(message="bad", location="manifest")]
    res = LoadResult(trace=None, issues=issues)
    diags = run_all_detectors(res)
    assert len(diags) == 1
    assert diags[0].kind == "trace_schema_violation"


def test_ranking_trace_mode_supported():
    assert "trace" in supported_modes()
    table = _MODE_RANK["trace"]
    # 关键 trace kind 都在表里且 schema_violation 排第一
    assert table["trace_schema_violation"] == 0
    assert table["trace_hash_chain_broken"] == 1


def test_ranking_trace_mode_orders_kinds_correctly():
    diags = run_all_detectors(
        LoadResult(
            trace=None,
            issues=[
                SchemaIssue(message="x", location="loc"),
            ],
        )
    )
    # 加一条 hash_chain_broken
    t = _build_clean(3)
    t.events[1] = t.events[1].model_copy(update={"reason": "x"})
    chain_diags = detect_hash_chain(t)
    diags.extend(chain_diags)
    ranked = rank_diagnostics(diags, mode="trace")
    # schema_violation 必须排在 hash_chain_broken 之前
    kinds = [d.kind for d in ranked]
    assert kinds.index("trace_schema_violation") < kinds.index("trace_hash_chain_broken")
