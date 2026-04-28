"""TR-3：run_trace_review + TraceReviewReport + render 三件套 + snapshot 端到端。

策略：
- 构造 clean / tampered / schema_broken 三段 fixture，跑 run_trace_review
- 每段断言关键 diagnostic 集与八段字段都符合
- 决定性：同一 fixture 两次 render_json byte-equal（除 created_at）
- snapshot：默认走 cwd/.gaia/trace/reviews/<id>.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gaia.trace.hashing import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_events_root,
    compute_manifest_hash,
    hash_event,
)
from gaia.trace.render import render_json, render_markdown, render_text
from gaia.trace.review import TraceReviewReport, run_trace_review
from gaia.trace.schema import ClaimRef, Trace, TraceEvent, TraceManifest


# ============ Fixture 工厂 ============


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


def _build_clean_trace(n: int = 3) -> Trace:
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    for i in range(n):
        ev = _ev(i, prev_hash=prev)
        events.append(ev)
        prev = hash_event(ev)
    manifest = TraceManifest(
        arm_id="arm-x",
        session_id="sess-1",
        trace_id="trace-1",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    manifest = manifest.model_copy(
        update={"manifest_hash": compute_manifest_hash(manifest)}
    )
    return Trace(manifest=manifest, events=events)


def _write_clean_fixture(tmp: Path, n: int = 3) -> Path:
    t = _build_clean_trace(n)
    p = tmp / "trace_clean.json"
    p.write_text(t.model_dump_json(indent=2), encoding="utf-8")
    return p


def _write_tampered_fixture(tmp: Path) -> Path:
    """中段事件被改动，prev_hash 不变 ⇒ 链断"""
    t = _build_clean_trace(5)
    # 直接改 events[2].reason，使 events[3].prev_hash 不再匹配
    # 写到 JSON 后再修改 reason 字段；schema 仍合法但链断
    raw = json.loads(t.model_dump_json())
    raw["events"][2]["reason"] = "tampered text — was different"
    p = tmp / "trace_tampered.json"
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return p


def _write_schema_broken_fixture(tmp: Path) -> Path:
    """events[1] 缺 event_id，loader 应给 schema_violation。"""
    t = _build_clean_trace(3)
    raw = json.loads(t.model_dump_json())
    del raw["events"][1]["event_id"]
    p = tmp / "trace_schema_broken.json"
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return p


# ============ 主流程 ============


def test_run_trace_review_clean_yields_no_diagnostics(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    assert isinstance(report, TraceReviewReport)
    assert report.mode == "trace"
    assert report.manifest_status == "ok"
    assert report.hash_chain["ok"] is True
    assert report.hash_chain["broken_at_seq"] is None
    assert report.diagnostics == []
    assert report.next_edits == []
    assert report.tampering == []


def test_run_trace_review_clean_counts_match(tmp_path: Path):
    p = _write_clean_fixture(tmp_path, n=4)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    assert report.counts["events"] == 4
    assert report.counts["decisions"] == 4
    assert report.execution_stats["actors"] == ["arm"]


def test_run_trace_review_tampered_breaks_hash_chain(tmp_path: Path):
    p = _write_tampered_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    assert report.hash_chain["ok"] is False
    assert report.hash_chain["broken_at_seq"] is not None
    kinds = {d.kind for d in report.diagnostics}
    assert "trace_hash_chain_broken" in kinds
    # tampering 段应捕获该 hash chain 断裂
    tamper_kinds = {t["kind"] for t in report.tampering}
    assert "trace_hash_chain_broken" in tamper_kinds


def test_run_trace_review_schema_violation_does_not_crash(tmp_path: Path):
    p = _write_schema_broken_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    kinds = {d.kind for d in report.diagnostics}
    assert "trace_schema_violation" in kinds
    # ranking：schema_violation 必须排在最前
    assert report.diagnostics[0].kind == "trace_schema_violation"


def test_run_trace_review_writes_snapshot(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    snap_dir = tmp_path / "snap"
    report = run_trace_review(p, snapshot_dir=snap_dir)
    target = snap_dir / f"{report.trace_review_id}.json"
    assert target.exists()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["trace_review_id"] == report.trace_review_id
    assert saved["mode"] == "trace"


def test_run_trace_review_snapshot_failure_does_not_crash(tmp_path: Path, monkeypatch):
    """snapshot 写盘失败时 review 仍然返回。"""
    p = _write_clean_fixture(tmp_path)
    import gaia.trace.snapshot as snap_mod

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(snap_mod, "save_trace_review_snapshot", boom)
    # 不 raise
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    assert isinstance(report, TraceReviewReport)


# ============ Render 三件套 ============


def test_render_text_contains_section_headers(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    txt = render_text(report)
    for header in ["§2 Manifest", "§3 Hash Chain", "§4 Causal Health",
                   "§5 Reference Validity", "§6 Tampering", "§7 Execution Stats",
                   "§8 Diagnostics"]:
        assert header in txt, f"missing {header}"


def test_render_markdown_contains_sections(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    md = render_markdown(report)
    assert "## §2 Manifest" in md
    assert "## §3 Hash Chain" in md
    assert "## §8 Diagnostics" in md


def test_render_json_byte_equal_modulo_created_at(tmp_path: Path):
    """同一 fixture 两次跑 → render_json 除 created_at 外 byte-equal."""
    p = _write_clean_fixture(tmp_path)
    r1 = run_trace_review(p, snapshot_dir=tmp_path / "snap1")
    r2 = run_trace_review(p, snapshot_dir=tmp_path / "snap2")

    j1 = render_json(r1)
    j2 = render_json(r2)
    # mask created_at + trace_review_id（依 created_at 生成 ⇒ 也会变）
    pat = re.compile(r'"(created_at|trace_review_id)": "[^"]*"')
    assert pat.sub('"X": "X"', j1) == pat.sub('"X": "X"', j2)


def test_render_json_is_sorted(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    j = render_json(report)
    # sort_keys=True ⇒ 顶层 key 字典序
    keys = list(json.loads(j).keys())
    assert keys == sorted(keys)


def test_render_tampered_shows_tampering_signal(tmp_path: Path):
    p = _write_tampered_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    txt = render_text(report)
    assert "trace_hash_chain_broken" in txt


# ============ Reference validity ============


def test_reference_validity_lists_all_claim_refs(tmp_path: Path):
    """trace 含 ClaimRef，§5 reference_validity 应每条都列。"""
    events: list[TraceEvent] = []
    prev = GENESIS_PREV_HASH
    e0 = _ev(
        0,
        prev_hash=prev,
        refs=[
            ClaimRef(claim_id="c1", review_id="rev-1", relation="asserts"),
            ClaimRef(claim_id="c2", review_id="rev-2", relation="uses"),
        ],
    )
    events.append(e0)
    prev = hash_event(e0)
    e1 = _ev(1, prev_hash=prev)
    events.append(e1)
    manifest = TraceManifest(
        arm_id="a",
        session_id="s",
        trace_id="t",
        created_at=_ts(0),
        events_root=compute_events_root(events),
    )
    manifest = manifest.model_copy(
        update={"manifest_hash": compute_manifest_hash(manifest)}
    )
    t = Trace(manifest=manifest, events=events)
    p = tmp_path / "with_refs.json"
    p.write_text(t.model_dump_json(indent=2), encoding="utf-8")

    # resolver 全 false ⇒ 仍要列出，但 resolved=False
    report = run_trace_review(
        p, resolver=lambda r: False, snapshot_dir=tmp_path / "snap"
    )
    assert len(report.reference_validity) == 2
    assert all(not r["resolved"] for r in report.reference_validity)
    # 同时产生 unresolved_claim_ref diagnostic
    kinds = {d.kind for d in report.diagnostics}
    assert "unresolved_claim_ref" in kinds


def test_to_json_dict_round_trips(tmp_path: Path):
    p = _write_clean_fixture(tmp_path)
    report = run_trace_review(p, snapshot_dir=tmp_path / "snap")
    d = report.to_json_dict()
    # JSON 可序列化
    s = json.dumps(d, sort_keys=True)
    assert isinstance(s, str)
    assert d["trace_review_id"] == report.trace_review_id
    assert d["counts"]["events"] >= 1
