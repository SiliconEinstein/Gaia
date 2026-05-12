"""TR-1：schema 字段约束与 pydantic 校验。."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gaia.trace.schema import (
    SCHEMA_VERSION,
    ClaimRef,
    Trace,
    TraceEvent,
    TraceManifest,
)


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_schema_version_is_one_zero():
    assert SCHEMA_VERSION == "1.0"


def test_minimal_event_validates():
    ev = TraceEvent(
        event_id="e0",
        seq=0,
        prev_hash="",
        ts=_utc("2026-04-28T00:00:00"),
        kind="decision",
        actor="arm-1",
        reason="bootstrapped",
    )
    assert ev.seq == 0
    assert ev.refs == []
    assert ev.outputs is None


def test_event_seq_must_be_nonnegative():
    with pytest.raises(ValidationError):
        TraceEvent(
            event_id="e",
            seq=-1,
            prev_hash="",
            ts=_utc("2026-04-28T00:00:00"),
            kind="decision",
            actor="x",
        )


def test_event_kind_literal_enforced():
    with pytest.raises(ValidationError):
        TraceEvent(
            event_id="e",
            seq=0,
            prev_hash="",
            ts=_utc("2026-04-28T00:00:00"),
            kind="not_a_kind",  # type: ignore[arg-type]
            actor="x",
        )


def test_event_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        TraceEvent(
            event_id="e",
            seq=0,
            prev_hash="",
            ts=_utc("2026-04-28T00:00:00"),
            kind="decision",
            actor="x",
            unknown_field=1,  # type: ignore[call-arg]
        )


def test_claim_ref_relation_literal():
    ok = ClaimRef(claim_id="c1", review_id="r1", relation="asserts")
    assert ok.relation == "asserts"
    with pytest.raises(ValidationError):
        ClaimRef(claim_id="c1", review_id="r1", relation="bad")  # type: ignore[arg-type]


def test_manifest_defaults_schema_version():
    m = TraceManifest(
        arm_id="arm-A",
        session_id="s-1",
        trace_id="t-1",
        created_at=_utc("2026-04-28T00:00:00"),
    )
    assert m.schema_version == "1.0"
    assert m.events_root == ""
    assert m.manifest_hash == ""
    assert m.signature is None


def test_trace_round_trip_via_model_dump():
    m = TraceManifest(
        arm_id="arm-A",
        session_id="s-1",
        trace_id="t-1",
        created_at=_utc("2026-04-28T00:00:00"),
    )
    ev = TraceEvent(
        event_id="e0",
        seq=0,
        prev_hash="",
        ts=_utc("2026-04-28T00:00:01"),
        kind="tool_call",
        actor="arm-A",
        tool="bash",
        inputs={"cmd": "ls"},
    )
    t = Trace(manifest=m, events=[ev])
    d = t.model_dump()
    t2 = Trace.model_validate(d)
    assert t2 == t
