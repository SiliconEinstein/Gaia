"""TR-1：loader 在 JSON / JSONL 双布局下的健壮性。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from gaia.trace.hashing import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_events_root,
    compute_manifest_hash,
    hash_event,
)
from gaia.trace.loader import load_trace
from gaia.trace.schema import TraceEvent, TraceManifest


def _build_clean_trace() -> tuple[TraceManifest, list[TraceEvent]]:
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(3):
        ev = TraceEvent(
            event_id=f"e{i}",
            seq=i,
            prev_hash=prev,
            ts=datetime(2026, 4, 28, 0, 0, i, tzinfo=timezone.utc),
            kind="decision",
            actor="arm",
            reason="grounded",
            inputs={"step": i},
        )
        events.append(ev)
        prev = hash_event(ev)
    manifest = TraceManifest(
        arm_id="arm",
        session_id="s1",
        trace_id="t1",
        created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        events_root=compute_events_root(events),
    )
    manifest = manifest.model_copy(update={"manifest_hash": compute_manifest_hash(manifest)})
    return manifest, events


def _write_single_json(path: Path, manifest: TraceManifest, events: list[TraceEvent]) -> None:
    data = {"manifest": manifest.model_dump(mode="json"), "events": [e.model_dump(mode="json") for e in events]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, manifest: TraceManifest, events: list[TraceEvent]) -> None:
    lines = [json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False)]
    for e in events:
        lines.append(json.dumps(e.model_dump(mode="json"), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_single_json_clean(tmp_path: Path):
    manifest, events = _build_clean_trace()
    path = tmp_path / "trace.json"
    _write_single_json(path, manifest, events)
    res = load_trace(path)
    assert res.trace is not None
    assert res.issues == []
    assert len(res.trace.events) == 3
    assert res.trace.manifest.arm_id == "arm"


def test_load_jsonl_clean(tmp_path: Path):
    manifest, events = _build_clean_trace()
    path = tmp_path / "trace.jsonl"
    _write_jsonl(path, manifest, events)
    res = load_trace(path)
    assert res.trace is not None
    assert res.issues == []
    assert len(res.trace.events) == 3


def test_load_missing_file_returns_issue(tmp_path: Path):
    res = load_trace(tmp_path / "nope.jsonl")
    assert res.trace is None
    assert any("not found" in i.message for i in res.issues)


def test_load_invalid_json_returns_issue(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    res = load_trace(path)
    assert res.trace is None
    assert any("json decode" in i.message for i in res.issues)


def test_load_jsonl_with_one_corrupt_event_keeps_rest(tmp_path: Path):
    manifest, events = _build_clean_trace()
    lines = [json.dumps(manifest.model_dump(mode="json"))]
    lines.append(json.dumps(events[0].model_dump(mode="json")))
    lines.append('{"event_id":"bad","seq":-1}')  # 缺字段 + seq 负
    lines.append(json.dumps(events[2].model_dump(mode="json")))
    path = tmp_path / "trace.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    res = load_trace(path)
    assert res.trace is not None
    # 损坏行被跳过，其余事件保留（顺序仍是写入顺序，reviewer 后续校验 seq 单调）
    assert len(res.trace.events) == 2
    assert res.issues  # 至少 1 条 issue


def test_load_partial_single_json_keeps_manifest_when_one_event_invalid(tmp_path: Path):
    manifest, events = _build_clean_trace()
    bad_data = {
        "manifest": manifest.model_dump(mode="json"),
        "events": [
            events[0].model_dump(mode="json"),
            {"event_id": "x", "seq": 1},  # 缺很多字段
            events[2].model_dump(mode="json"),
        ],
    }
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(bad_data, ensure_ascii=False), encoding="utf-8")
    res = load_trace(path)
    assert res.trace is not None
    assert res.trace.manifest.arm_id == "arm"
    assert len(res.trace.events) == 2
    assert any("events[1]" in i.location for i in res.issues)


def test_canonical_bytes_match_loader_output(tmp_path: Path):
    """加载后再 canonical_json，与原 model_dump canonical 应 byte-equal。"""
    manifest, events = _build_clean_trace()
    path = tmp_path / "trace.jsonl"
    _write_jsonl(path, manifest, events)
    res = load_trace(path)
    assert res.trace is not None
    assert canonical_json(events[1].model_dump()) == canonical_json(
        res.trace.events[1].model_dump()
    )
