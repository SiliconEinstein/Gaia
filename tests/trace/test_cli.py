"""TR-4：CliRunner 端到端三命令。."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.trace.hashing import (
    GENESIS_PREV_HASH,
    compute_events_root,
    compute_manifest_hash,
    hash_event,
)
from gaia.trace.schema import Trace, TraceEvent, TraceManifest


runner = CliRunner()


def _ts(seq: int) -> datetime:
    return datetime(2026, 4, 28, tzinfo=timezone.utc) + timedelta(seconds=seq)


def _ev(seq: int, prev_hash: str, **kw) -> TraceEvent:
    base = dict(
        event_id=f"e{seq}",
        seq=seq,
        prev_hash=prev_hash,
        ts=_ts(seq),
        kind="decision",
        actor="arm",
        reason="grounded by inputs",
        inputs={"step": "inputs"},
    )
    base.update(kw)
    return TraceEvent(**base)


def _build_clean(n: int = 3) -> Trace:
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(n):
        ev = _ev(i, prev_hash=prev)
        events.append(ev)
        prev = hash_event(ev)
    m = TraceManifest(
        arm_id="arm-x",
        session_id="s",
        trace_id="t",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    m = m.model_copy(update={"manifest_hash": compute_manifest_hash(m)})
    return Trace(manifest=m, events=events)


def _write(tmp: Path, t: Trace, name: str = "t.json") -> Path:
    p = tmp / name
    p.write_text(t.model_dump_json(indent=2), encoding="utf-8")
    return p


# ============ verify ============


def test_verify_clean_returns_zero(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(app, ["trace", "verify", str(p)])
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_verify_quiet_silent_on_clean(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(app, ["trace", "verify", str(p), "--quiet"])
    assert r.exit_code == 0
    assert r.stdout.strip() == ""


def test_verify_tampered_exits_one(tmp_path: Path):
    t = _build_clean(4)
    raw = json.loads(t.model_dump_json())
    raw["events"][2]["reason"] = "tampered"
    p = tmp_path / "t.json"
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    r = runner.invoke(app, ["trace", "verify", str(p)])
    assert r.exit_code == 1
    assert "FAIL" in r.stderr


def test_verify_schema_broken_exits_two(tmp_path: Path):
    t = _build_clean(2)
    raw = json.loads(t.model_dump_json())
    del raw["events"][0]["event_id"]
    p = tmp_path / "t.json"
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    r = runner.invoke(app, ["trace", "verify", str(p)])
    assert r.exit_code == 2


# ============ review ============


def test_review_clean_text_zero(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(
        app,
        ["trace", "review", str(p), "--snapshot-dir", str(tmp_path / "snap")],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "ARM Trace Review" in r.stdout
    assert "§3 Hash Chain" in r.stdout


def test_review_json_is_parseable_and_deterministic(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r1 = runner.invoke(
        app,
        ["trace", "review", str(p), "--json", "--snapshot-dir", str(tmp_path / "s1")],
    )
    r2 = runner.invoke(
        app,
        ["trace", "review", str(p), "--json", "--snapshot-dir", str(tmp_path / "s2")],
    )
    assert r1.exit_code == 0 and r2.exit_code == 0
    d1 = json.loads(r1.stdout)
    d2 = json.loads(r2.stdout)
    # 除 created_at / trace_review_id 外，两次结构一致
    for k in ("created_at", "trace_review_id"):
        d1.pop(k, None)
        d2.pop(k, None)
    assert d1 == d2


def test_review_markdown_emits_headers(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(
        app,
        ["trace", "review", str(p), "--markdown", "--snapshot-dir", str(tmp_path / "snap")],
    )
    assert r.exit_code == 0
    assert "## §3 Hash Chain" in r.stdout


def test_review_tampered_exits_one(tmp_path: Path):
    t = _build_clean(4)
    raw = json.loads(t.model_dump_json())
    raw["events"][2]["reason"] = "tampered"
    p = tmp_path / "t.json"
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    r = runner.invoke(
        app,
        ["trace", "review", str(p), "--snapshot-dir", str(tmp_path / "snap")],
    )
    assert r.exit_code == 1


def test_review_invalid_mode_exits_two(tmp_path: Path):
    p = _write(tmp_path, _build_clean(2))
    r = runner.invoke(
        app,
        ["trace", "review", str(p), "--mode", "bogus", "--snapshot-dir", str(tmp_path / "snap")],
    )
    assert r.exit_code == 2


def test_review_json_and_markdown_mutex(tmp_path: Path):
    p = _write(tmp_path, _build_clean(2))
    r = runner.invoke(
        app,
        [
            "trace",
            "review",
            str(p),
            "--json",
            "--markdown",
            "--snapshot-dir",
            str(tmp_path / "snap"),
        ],
    )
    assert r.exit_code == 2


def test_review_strict_warning_exits_one(tmp_path: Path):
    """构造 decision_without_grounds（warning）+ --strict ⇒ exit 1."""
    events: list[TraceEvent] = []
    e0 = TraceEvent(
        event_id="e0",
        seq=0,
        prev_hash=GENESIS_PREV_HASH,
        ts=_ts(0),
        kind="decision",
        actor="arm",
        # no reason ⇒ warning
        inputs={},
    )
    events.append(e0)
    m = TraceManifest(
        arm_id="a",
        session_id="s",
        trace_id="t",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    m = m.model_copy(update={"manifest_hash": compute_manifest_hash(m)})
    p = _write(tmp_path, Trace(manifest=m, events=events), name="warn.json")

    r_no = runner.invoke(
        app,
        ["trace", "review", str(p), "--snapshot-dir", str(tmp_path / "s1")],
    )
    assert r_no.exit_code == 0  # warning only

    r_strict = runner.invoke(
        app,
        ["trace", "review", str(p), "--strict", "--snapshot-dir", str(tmp_path / "s2")],
    )
    assert r_strict.exit_code == 1


# ============ show ============


def test_show_lists_events(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(app, ["trace", "show", str(p)])
    assert r.exit_code == 0
    assert "events shown" in r.stdout
    assert "seq=0" in r.stdout
    assert "seq=2" in r.stdout


def test_show_with_kind_filter(tmp_path: Path):
    """混合 kind，只列 decision."""
    e0 = _ev(0, prev_hash=GENESIS_PREV_HASH)
    h0 = hash_event(e0)
    e1 = TraceEvent(
        event_id="t1",
        seq=1,
        prev_hash=h0,
        ts=_ts(1),
        kind="tool_call",
        actor="arm",
        tool="bash",
    )
    events = [e0, e1]
    m = TraceManifest(
        arm_id="a",
        session_id="s",
        trace_id="t",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    m = m.model_copy(update={"manifest_hash": compute_manifest_hash(m)})
    p = _write(tmp_path, Trace(manifest=m, events=events), name="mix.json")

    r = runner.invoke(app, ["trace", "show", str(p), "--kind", "decision"])
    assert r.exit_code == 0
    assert "seq=0" in r.stdout
    assert "tool_call" not in r.stdout


def test_show_limit(tmp_path: Path):
    p = _write(tmp_path, _build_clean(5))
    r = runner.invoke(app, ["trace", "show", str(p), "--limit", "2"])
    assert r.exit_code == 0
    assert "seq=0" in r.stdout
    assert "seq=1" in r.stdout
    assert "seq=2" not in r.stdout


def test_show_json_emits_jsonl(tmp_path: Path):
    p = _write(tmp_path, _build_clean(3))
    r = runner.invoke(app, ["trace", "show", str(p), "--json"])
    assert r.exit_code == 0
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 3
    for ln in lines:
        d = json.loads(ln)
        assert "event_id" in d
        assert "seq" in d


def test_show_schema_broken_exits_two(tmp_path: Path):
    raw = {"manifest": {"foo": "bar"}, "events": []}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    r = runner.invoke(app, ["trace", "show", str(p)])
    assert r.exit_code == 2
