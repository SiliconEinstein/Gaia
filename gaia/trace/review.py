"""Trace review report assembly for the eight-section ARM review.

字段命名尽量与 inquiry 平行：``trace_review_id`` / ``created_at`` / ``mode`` 等
保持一致，方便用户读两种 review 输出无认知断层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia.inquiry.diagnostics import Diagnostic, NextEdit
from gaia.inquiry.snapshot import mint_review_id
from gaia.trace.diagnostics import (
    RETRY_CHAIN_LIMIT_DEFAULT,
    ReviewIdResolver,
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
)
from gaia.trace.hashing import (
    GENESIS_PREV_HASH,
    compute_events_root,
    compute_manifest_hash,
    recompute_chain,
)
from gaia.trace.loader import LoadResult, load_trace
from gaia.trace.ranking import rank_diagnostics, rank_next_edits
from gaia.trace.schema import Trace


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# ============ 八段容器 ============


@dataclass
class TraceReviewReport:
    """Represent the eight-section ARM trace review report.

    section mapping（参 PLAN 与 gaia.inquiry.ReviewReport）：
    §1 Header        — trace_review_id / created_at / path / mode
    §2 Manifest      — manifest_status / manifest_hash / counts
    §3 Hash Chain    — hash_chain (ok / broken_at_seq / recomputed_root)
    §4 Causal Health — causal_health
       (tool_pairing / decision_grounds / parent_links / actor_continuity)
    §5 Reference Validity — reference_validity (claim_ref 解析摘要)
    §6 Tampering Signals — tampering (篡改信号集中视图)
    §7 Execution Stats — execution_stats (actors / kind 分布 / retry / time_span)
    §8 Diagnostics + NextEdits — diagnostics / next_edits / next_edits_structured
    """

    trace_review_id: str
    created_at: str
    path: str
    mode: str

    # §2 Manifest 摘要
    manifest_status: str
    manifest_hash: str | None
    counts: dict[str, int] = field(default_factory=dict)

    # §3 Hash chain
    hash_chain: dict[str, Any] = field(default_factory=dict)

    # §4 Causal health
    causal_health: dict[str, Any] = field(default_factory=dict)

    # §5 Reference validity
    reference_validity: list[dict[str, Any]] = field(default_factory=list)

    # §6 Tampering signals
    tampering: list[dict[str, Any]] = field(default_factory=list)

    # §7 Execution stats
    execution_stats: dict[str, Any] = field(default_factory=dict)

    # §8 Diagnostic stream + edits
    diagnostics: list[Diagnostic] = field(default_factory=list)
    next_edits: list[str] = field(default_factory=list)
    next_edits_structured: list[NextEdit] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible report payload."""
        d: dict[str, Any] = {
            "trace_review_id": self.trace_review_id,
            "created_at": self.created_at,
            "path": self.path,
            "mode": self.mode,
            "manifest_status": self.manifest_status,
            "manifest_hash": self.manifest_hash,
            "counts": dict(self.counts),
            "hash_chain": dict(self.hash_chain),
            "causal_health": dict(self.causal_health),
            "reference_validity": [dict(x) for x in self.reference_validity],
            "tampering": [dict(x) for x in self.tampering],
            "execution_stats": dict(self.execution_stats),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "next_edits": list(self.next_edits),
            "next_edits_structured": [e.to_dict() for e in self.next_edits_structured],
        }
        return d


# ============ Helpers：把 Diagnostic 流升成 NextEdit ============


def _to_next_edit(d: Diagnostic) -> NextEdit:
    return NextEdit(
        text=d.suggested_edit or d.message,
        kind=d.kind,
        severity=d.severity,
        target=d.target,
        label=d.label,
        source_anchor=d.source_anchor,
    )


def _diagnostic_kind(diagnostic: Diagnostic) -> str:
    """Return the runtime diagnostic kind, including trace-specific extensions."""
    return str(diagnostic.kind)


# ============ §2/§3/§4/§5/§6/§7 各段汇总 ============


def _build_manifest_section(trace: Trace | None) -> tuple[str, str | None, dict[str, int]]:
    if trace is None:
        return "schema_failed", None, {"events": 0, "decisions": 0, "tool_calls": 0, "retries": 0}
    counts = {
        "events": len(trace.events),
        "decisions": sum(1 for e in trace.events if e.kind == "decision"),
        "tool_calls": sum(1 for e in trace.events if e.kind == "tool_call"),
        "tool_results": sum(1 for e in trace.events if e.kind == "tool_result"),
        "retries": sum(1 for e in trace.events if e.kind == "retry"),
        "intermediate_states": sum(1 for e in trace.events if e.kind == "intermediate_state"),
        "claim_refs": sum(len(e.refs) for e in trace.events),
    }
    return "ok", trace.manifest.manifest_hash or None, counts


def _build_hash_chain_section(trace: Trace | None) -> dict[str, Any]:
    if trace is None or not trace.events:
        return {"ok": True, "broken_at_seq": None, "recomputed_root": ""}
    chain = recompute_chain(trace.events)
    broken_at: int | None = None
    if trace.events[0].prev_hash != GENESIS_PREV_HASH:
        broken_at = trace.events[0].seq
    else:
        for i in range(1, len(trace.events)):
            if trace.events[i].prev_hash != chain[i - 1]:
                broken_at = trace.events[i].seq
                break
    expected_root = compute_events_root(trace.events)
    expected_manifest_hash = compute_manifest_hash(trace.manifest)
    return {
        "ok": broken_at is None
        and trace.manifest.events_root == expected_root
        and (
            not trace.manifest.manifest_hash
            or trace.manifest.manifest_hash == expected_manifest_hash
        ),
        "broken_at_seq": broken_at,
        "recomputed_root": expected_root,
        "declared_root": trace.manifest.events_root,
        "recomputed_manifest_hash": expected_manifest_hash,
        "declared_manifest_hash": trace.manifest.manifest_hash,
    }


def _build_causal_health_section(diags: list[Diagnostic], trace: Trace | None) -> dict[str, Any]:
    if trace is None:
        return {
            "tool_pairing": {"calls": 0, "unresolved": 0},
            "decision_grounds": {"decisions": 0, "ungrounded": 0},
            "parent_links": {"orphans": 0},
            "actor_continuity": {"unexplained_switches": 0},
        }
    decisions = sum(1 for e in trace.events if e.kind == "decision")
    calls = sum(1 for e in trace.events if e.kind == "tool_call")
    return {
        "tool_pairing": {
            "calls": calls,
            "unresolved": sum(
                1 for d in diags if _diagnostic_kind(d) == "tool_call_without_result"
            ),
        },
        "decision_grounds": {
            "decisions": decisions,
            "ungrounded": sum(
                1 for d in diags if _diagnostic_kind(d) == "decision_without_grounds"
            ),
        },
        "parent_links": {
            "orphans": sum(1 for d in diags if _diagnostic_kind(d) == "orphan_event"),
        },
        "actor_continuity": {
            "unexplained_switches": sum(
                1 for d in diags if _diagnostic_kind(d) == "actor_switch_unexplained"
            ),
        },
        "retry": {
            "diverged_chains": sum(1 for d in diags if _diagnostic_kind(d) == "retry_diverged"),
        },
    }


def _build_reference_section(
    trace: Trace | None, *, resolver: ReviewIdResolver | None, package_path: str | Path | None
) -> list[dict[str, Any]]:
    if trace is None:
        return []
    # 用 detector 的 resolver 逻辑，但这里要全集（resolved 也列出）
    from gaia.trace.diagnostics import _default_resolver_factory

    res = resolver or _default_resolver_factory(package_path)
    out: list[dict[str, Any]] = []
    for ev in trace.events:
        for j, ref in enumerate(ev.refs):
            try:
                ok = bool(res(ref.review_id))
            except Exception:
                ok = False
            out.append(
                {
                    "event_id": ev.event_id,
                    "seq": ev.seq,
                    "ref_index": j,
                    "claim_id": ref.claim_id,
                    "review_id": ref.review_id,
                    "relation": ref.relation,
                    "resolved": ok,
                }
            )
    return out


def _build_tampering_section(diags: list[Diagnostic]) -> list[dict[str, Any]]:
    """Collect error-level diagnostics that strongly indicate tampering."""
    keep = {
        "trace_schema_violation",
        "trace_hash_chain_broken",
        "trace_manifest_hash_mismatch",
        "trace_timestamp_disorder",
        "trace_seq_disorder",
    }
    out: list[dict[str, Any]] = []
    for d in diags:
        if d.kind not in keep:
            continue
        out.append(
            {
                "kind": d.kind,
                "severity": d.severity,
                "target": d.target,
                "label": d.label,
                "message": d.message,
                "data": dict(d.data),
            }
        )
    return out


def _build_execution_stats(trace: Trace | None) -> dict[str, Any]:
    if trace is None or not trace.events:
        return {
            "actors": [],
            "kind_distribution": {},
            "retry_count": 0,
            "time_span_seconds": 0.0,
        }
    actors = sorted({e.actor for e in trace.events})
    dist: dict[str, int] = {}
    for e in trace.events:
        dist[e.kind] = dist.get(e.kind, 0) + 1
    retry_count = dist.get("retry", 0)
    span = (trace.events[-1].ts - trace.events[0].ts).total_seconds()
    return {
        "actors": actors,
        "kind_distribution": dist,
        "retry_count": retry_count,
        "time_span_seconds": max(span, 0.0),
        "first_ts": trace.events[0].ts.isoformat(),
        "last_ts": trace.events[-1].ts.isoformat(),
    }


# ============ 主入口 ============


def run_trace_review(
    path: str | Path,
    *,
    mode: str = "trace",
    resolver: ReviewIdResolver | None = None,
    package_path: str | Path | None = None,
    retry_chain_limit: int = RETRY_CHAIN_LIMIT_DEFAULT,
    snapshot_dir: str | Path | None = None,
) -> TraceReviewReport:
    """Load a trace, run detectors, build sections, and save a snapshot.

    ``mode`` 与 ranking 的 mode 表对齐；默认 ``"trace"``。
    ``mode == "publish"`` 时 ranking 套 publish 表，warning 也会被前置。
    ``snapshot_dir=None`` 走默认 ``<cwd>/.gaia/trace/reviews/``。
    """
    load_result: LoadResult = load_trace(path)
    trace = load_result.trace

    diags: list[Diagnostic] = []
    diags.extend(from_schema_issues(load_result.issues))
    if trace is not None:
        diags.extend(detect_hash_chain(trace))
        diags.extend(detect_manifest_hash(trace))
        diags.extend(detect_timestamps(trace))
        diags.extend(detect_seq(trace))
        diags.extend(detect_decision_grounds(trace))
        diags.extend(detect_tool_pairing(trace))
        diags.extend(detect_claim_refs(trace, resolver=resolver, package_path=package_path))
        diags.extend(detect_parent_links(trace))
        diags.extend(detect_retry(trace, max_chain=retry_chain_limit))
        diags.extend(detect_actor(trace))

    diags = rank_diagnostics(diags, mode)

    next_edits_structured = [_to_next_edit(d) for d in diags]
    next_edits_structured = rank_next_edits(next_edits_structured, mode)
    next_edits = [edit.text for edit in next_edits_structured if edit.text]

    manifest_status, manifest_hash, counts = _build_manifest_section(trace)
    hash_chain = _build_hash_chain_section(trace)
    causal_health = _build_causal_health_section(diags, trace)
    reference_validity = _build_reference_section(
        trace, resolver=resolver, package_path=package_path
    )
    tampering = _build_tampering_section(diags)
    execution_stats = _build_execution_stats(trace)

    ir_hash = manifest_hash or hash_chain.get("recomputed_root", "") or "nohash"
    review_id = mint_review_id(ir_hash, mode)

    report = TraceReviewReport(
        trace_review_id=review_id,
        created_at=_utcnow_iso(),
        path=str(path),
        mode=mode,
        manifest_status=manifest_status,
        manifest_hash=manifest_hash,
        counts=counts,
        hash_chain=hash_chain,
        causal_health=causal_health,
        reference_validity=reference_validity,
        tampering=tampering,
        execution_stats=execution_stats,
        diagnostics=diags,
        next_edits=next_edits,
        next_edits_structured=next_edits_structured,
    )

    # 写 snapshot——失败不应让 review 失败
    try:
        from gaia.trace.snapshot import save_trace_review_snapshot

        save_trace_review_snapshot(report, snapshot_dir=snapshot_dir)
    except Exception:
        pass

    return report
