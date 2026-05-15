"""TR-1：canonical_json 决定性 + chain 篡改检出。."""

from datetime import UTC, datetime

import pytest

from gaia.engine.trace.hashing import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_events_root,
    compute_manifest_hash,
    hash_event,
    recompute_chain,
    sha256_hex,
    verify_chain,
)
from gaia.engine.trace.schema import TraceEvent, TraceManifest


def _ev(seq: int, prev_hash: str, *, kind="decision", actor="arm", **kw) -> TraceEvent:
    base = {
        "event_id": f"e{seq}",
        "seq": seq,
        "prev_hash": prev_hash,
        "ts": datetime(2026, 4, 28, tzinfo=UTC).replace(second=seq),
        "kind": kind,
        "actor": actor,
        "reason": "r" if kind == "decision" else None,
    }
    base.update(kw)
    return TraceEvent(**base)


def _build_chain(n: int) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(n):
        ev = _ev(i, prev_hash=prev)
        events.append(ev)
        prev = hash_event(ev)
    return events


# ---------- canonical_json ----------


def test_canonical_json_is_deterministic_across_dict_orderings():
    a = {"b": 1, "a": [1, 2], "c": "x"}
    b = {"a": [1, 2], "c": "x", "b": 1}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_no_whitespace():
    out = canonical_json({"a": 1, "b": [1, 2]})
    assert b" " not in out
    assert out == b'{"a":1,"b":[1,2]}'


def test_canonical_json_datetime_to_iso_z():
    dt = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
    out = canonical_json({"t": dt})
    assert out == b'{"t":"2026-04-28T12:00:00Z"}'


def test_canonical_json_naive_datetime_assumed_utc():
    dt = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    assert canonical_json({"t": dt}) == b'{"t":"2026-04-28T12:00:00Z"}'


def test_canonical_json_rejects_non_finite_float():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"x": float("inf")})


def test_canonical_json_rejects_non_str_dict_key():
    with pytest.raises(TypeError):
        canonical_json({1: "x"})


def test_canonical_json_handles_unicode_without_escape():
    out = canonical_json({"k": "中文"})
    # ensure_ascii=False ⇒ 直接 utf-8 出，不转义
    assert "中文".encode() in out


# ---------- sha256 + chain ----------


def test_sha256_hex_matches_stdlib():
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_chain_genesis_event_prev_hash_is_empty_string():
    events = _build_chain(1)
    assert events[0].prev_hash == GENESIS_PREV_HASH


def test_chain_recompute_matches_event_prev_hash():
    events = _build_chain(5)
    chain = recompute_chain(events)
    assert len(chain) == 5
    for i in range(1, len(events)):
        assert events[i].prev_hash == chain[i - 1]


def test_verify_chain_detects_tampered_prev_hash_in_middle():
    events = _build_chain(5)
    # 篡改 events[3].prev_hash
    events[3] = events[3].model_copy(update={"prev_hash": "deadbeef" * 8})
    ok, broken_at = verify_chain(events)
    assert not ok
    assert broken_at == 3


def test_verify_chain_detects_tampered_event_content():
    events = _build_chain(5)
    # 改 events[2].reason ⇒ events[2] 的 hash 变 ⇒ events[3].prev_hash 不再匹配
    events[2] = events[2].model_copy(update={"reason": "tampered"})
    ok, broken_at = verify_chain(events)
    assert not ok
    assert broken_at == 3  # 第 3 条的 prev_hash 与 recomputed[2] 不符


def test_verify_chain_detects_bad_genesis_prev_hash():
    events = _build_chain(2)
    events[0] = events[0].model_copy(update={"prev_hash": "abc"})
    ok, broken_at = verify_chain(events)
    assert not ok
    assert broken_at == 0


def test_verify_chain_empty_events_is_ok():
    ok, broken_at = verify_chain([])
    assert ok
    assert broken_at is None


def test_event_payload_excludes_prev_hash():
    """关键性质：prev_hash 不进 hash 输入，否则 hash 与 prev_hash 形成自洽循环。."""
    e1 = _ev(0, prev_hash="")
    e2 = _ev(0, prev_hash="deadbeef")
    assert hash_event(e1) == hash_event(e2)


def test_events_root_is_deterministic():
    events_a = _build_chain(3)
    events_b = _build_chain(3)
    assert compute_events_root(events_a) == compute_events_root(events_b)


def test_events_root_changes_when_event_modified():
    events = _build_chain(3)
    root_before = compute_events_root(events)
    events[1] = events[1].model_copy(update={"actor": "intruder"})
    assert compute_events_root(events) != root_before


def test_manifest_hash_excludes_self_field():
    m = TraceManifest(
        arm_id="arm",
        session_id="s",
        trace_id="t",
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    h1 = compute_manifest_hash(m)
    m2 = m.model_copy(update={"manifest_hash": h1})
    assert compute_manifest_hash(m2) == h1  # self-field 不影响


def test_manifest_hash_changes_with_substantive_field():
    m = TraceManifest(
        arm_id="arm",
        session_id="s",
        trace_id="t",
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    h1 = compute_manifest_hash(m)
    m2 = m.model_copy(update={"arm_id": "other"})
    assert compute_manifest_hash(m2) != h1
