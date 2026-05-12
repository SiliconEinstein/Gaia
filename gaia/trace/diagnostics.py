"""Trace-domain deterministic diagnostic detectors.

设计纪律：
- 每个 detector 是纯函数 ``(Trace, ...) -> list[Diagnostic]``，不抛异常
- 字段缺失/类型错 ⇒ 跳过该事件并把上下文塞进 ``data["corrupt"]``，
  让 reviewer 仍能渲染（吸取 dz-fusion 教训：autouse monkeypatch 整个
  module 会 hide 真类，这里反过来——不允许任何"信任 trace 自报"的捷径）
- 复用 ``gaia.inquiry.diagnostics.Diagnostic`` dataclass；``kind`` 字段 Literal
  在 Python 运行时不被强制，新 trace kind 会被 ranking 正确处理（unknown
  kind 不被丢弃，只是排序档放在末尾——除非显式在 _MODE_RANK 加 "trace" mode）
- 事件锚点写在 ``data["trace_anchor"] = {"event_id", "seq", "ts"}``；
  ``source_anchor`` 留 None（trace 不指 file:line）
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Literal

from gaia.inquiry.diagnostics import Diagnostic
from gaia.trace.hashing import (
    GENESIS_PREV_HASH,
    compute_events_root,
    compute_manifest_hash,
    recompute_chain,
)
from gaia.trace.loader import LoadResult, SchemaIssue
from gaia.trace.schema import Trace, TraceEvent

TraceDiagnosticKind = Literal[
    "trace_schema_violation",
    "trace_hash_chain_broken",
    "trace_manifest_hash_mismatch",
    "trace_timestamp_disorder",
    "trace_seq_disorder",
    "decision_without_grounds",
    "tool_call_without_result",
    "unresolved_claim_ref",
    "orphan_event",
    "retry_diverged",
    "actor_switch_unexplained",
]

# v1 默认阈值——detector 调用方可覆盖
RETRY_CHAIN_LIMIT_DEFAULT: int = 5


def _anchor(event: TraceEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "seq": event.seq,
        "ts": event.ts.isoformat(),
    }


def _diag(
    *,
    severity: str,
    kind: str,
    target: str,
    label: str,
    message: str,
    suggested_edit: str = "",
    data: dict[str, Any] | None = None,
) -> Diagnostic:
    """Construct a diagnostic while preserving trace-specific kind strings."""
    return Diagnostic(
        severity=severity,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
        target=target,
        label=label,
        message=message,
        suggested_edit=suggested_edit,
        data=data or {},
        source_anchor=None,
    )


# ============ Detector 1：schema 违例（loader 阶段） ============


def from_schema_issues(issues: list[SchemaIssue]) -> list[Diagnostic]:
    """Convert loader schema issues into trace diagnostics."""
    out: list[Diagnostic] = []
    for issue in issues:
        out.append(
            _diag(
                severity="error",
                kind="trace_schema_violation",
                target=issue.location or "<root>",
                label=issue.location or "schema",
                message=issue.message,
                suggested_edit="Fix the offending field per ARM trace v1 schema.",
                data={"location": issue.location},
            )
        )
    return out


# ============ Detector 2：hash chain ============


def detect_hash_chain(trace: Trace) -> list[Diagnostic]:
    """Detect broken event hash-chain links.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for genesis or previous-hash mismatches.
    """
    events = trace.events
    if not events:
        return []
    out: list[Diagnostic] = []
    if events[0].prev_hash != GENESIS_PREV_HASH:
        out.append(
            _diag(
                severity="error",
                kind="trace_hash_chain_broken",
                target=events[0].event_id,
                label=f"event[seq={events[0].seq}]",
                message=(
                    f"first event's prev_hash must be empty (genesis); got {events[0].prev_hash!r}"
                ),
                suggested_edit="Set events[0].prev_hash = '' (genesis marker).",
                data={"trace_anchor": _anchor(events[0]), "broken_at_seq": events[0].seq},
            )
        )
    chain = recompute_chain(events)
    for i in range(1, len(events)):
        expected = chain[i - 1]
        if events[i].prev_hash != expected:
            out.append(
                _diag(
                    severity="error",
                    kind="trace_hash_chain_broken",
                    target=events[i].event_id,
                    label=f"event[seq={events[i].seq}]",
                    message=(
                        f"prev_hash mismatch at seq={events[i].seq}: "
                        f"expected {expected[:12]}..., got "
                        f"{events[i].prev_hash[:12]}..."
                    ),
                    suggested_edit=(
                        f"Recompute prev_hash from event[seq={events[i].seq - 1}] "
                        f"or restore the original event payload."
                    ),
                    data={
                        "trace_anchor": _anchor(events[i]),
                        "broken_at_seq": events[i].seq,
                        "expected_prev_hash": expected,
                        "actual_prev_hash": events[i].prev_hash,
                    },
                )
            )
    return out


# ============ Detector 3：manifest hash ============


def detect_manifest_hash(trace: Trace) -> list[Diagnostic]:
    """Detect manifest hashes that no longer match trace contents.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for `events_root` or `manifest_hash` mismatches.
    """
    out: list[Diagnostic] = []
    expected_root = compute_events_root(trace.events)
    if trace.manifest.events_root and trace.manifest.events_root != expected_root:
        out.append(
            _diag(
                severity="error",
                kind="trace_manifest_hash_mismatch",
                target="manifest.events_root",
                label="manifest",
                message=(
                    "manifest.events_root != recomputed root: "
                    f"declared {trace.manifest.events_root[:12]}..., "
                    f"recomputed {expected_root[:12]}..."
                ),
                suggested_edit="Recompute events_root = sha256(canonical_json(events_payloads)).",
                data={
                    "declared": trace.manifest.events_root,
                    "recomputed": expected_root,
                },
            )
        )
    expected_manifest_hash = compute_manifest_hash(trace.manifest)
    if trace.manifest.manifest_hash and trace.manifest.manifest_hash != expected_manifest_hash:
        out.append(
            _diag(
                severity="error",
                kind="trace_manifest_hash_mismatch",
                target="manifest.manifest_hash",
                label="manifest",
                message=(
                    "manifest.manifest_hash != recomputed: "
                    f"declared {trace.manifest.manifest_hash[:12]}..., "
                    f"recomputed {expected_manifest_hash[:12]}..."
                ),
                suggested_edit="Recompute manifest_hash = sha256(canonical_json(manifest \\ {manifest_hash})).",
                data={
                    "declared": trace.manifest.manifest_hash,
                    "recomputed": expected_manifest_hash,
                },
            )
        )
    return out


# ============ Detector 4：时间戳单调 ============


def detect_timestamps(trace: Trace) -> list[Diagnostic]:
    """Detect event timestamps that move backward.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for timestamp ordering violations.
    """
    out: list[Diagnostic] = []
    for i in range(1, len(trace.events)):
        prev_ts = trace.events[i - 1].ts
        curr_ts = trace.events[i].ts
        if curr_ts < prev_ts:
            out.append(
                _diag(
                    severity="error",
                    kind="trace_timestamp_disorder",
                    target=trace.events[i].event_id,
                    label=f"event[seq={trace.events[i].seq}]",
                    message=(
                        f"timestamp goes backward: seq={trace.events[i].seq} "
                        f"({curr_ts.isoformat()}) before "
                        f"seq={trace.events[i - 1].seq} ({prev_ts.isoformat()})"
                    ),
                    suggested_edit="Reorder events by ts or fix clock drift in the writer.",
                    data={
                        "trace_anchor": _anchor(trace.events[i]),
                        "prev_seq": trace.events[i - 1].seq,
                        "prev_ts": prev_ts.isoformat(),
                    },
                )
            )
    return out


# ============ Detector 5：seq 连续 ============


def detect_seq(trace: Trace) -> list[Diagnostic]:
    """Detect non-contiguous event sequence numbers.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for missing or reordered sequence numbers.
    """
    out: list[Diagnostic] = []
    if not trace.events:
        return out
    if trace.events[0].seq != 0:
        out.append(
            _diag(
                severity="error",
                kind="trace_seq_disorder",
                target=trace.events[0].event_id,
                label=f"event[seq={trace.events[0].seq}]",
                message=f"first seq must be 0, got {trace.events[0].seq}",
                suggested_edit="Renumber events starting from 0.",
                data={"trace_anchor": _anchor(trace.events[0])},
            )
        )
    for i in range(1, len(trace.events)):
        expected = trace.events[i - 1].seq + 1
        if trace.events[i].seq != expected:
            out.append(
                _diag(
                    severity="error",
                    kind="trace_seq_disorder",
                    target=trace.events[i].event_id,
                    label=f"event[seq={trace.events[i].seq}]",
                    message=(f"seq jump: expected {expected}, got {trace.events[i].seq}"),
                    suggested_edit="Renumber consecutive events.",
                    data={
                        "trace_anchor": _anchor(trace.events[i]),
                        "expected_seq": expected,
                    },
                )
            )
    return out


# ============ Detector 6：decision 必须有 grounds ============


def _tokenize(text: str) -> set[str]:
    return {tok.strip().lower() for tok in text.split() if tok.strip()}


def detect_decision_grounds(trace: Trace) -> list[Diagnostic]:
    """Detect decision events whose reasons do not reference their inputs.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for missing or weakly grounded decision reasons.
    """
    out: list[Diagnostic] = []
    for ev in trace.events:
        if ev.kind != "decision":
            continue
        reason = (ev.reason or "").strip()
        if not reason:
            out.append(
                _diag(
                    severity="warning",
                    kind="decision_without_grounds",
                    target=ev.event_id,
                    label=f"event[seq={ev.seq}]",
                    message="decision event has no `reason` field",
                    suggested_edit="Fill `reason` describing the basis for this decision.",
                    data={"trace_anchor": _anchor(ev), "missing": "reason"},
                )
            )
            continue
        if not ev.inputs:
            # 无 inputs 不强制要求 reason 与 inputs 重合（可能是初始决策）
            continue
        # 把 inputs 里所有字符串值 join 起来检 token 重合
        inputs_blob: list[str] = []
        for v in ev.inputs.values():
            if isinstance(v, str):
                inputs_blob.append(v)
            elif isinstance(v, (int, float, bool)):
                inputs_blob.append(str(v))
            elif isinstance(v, (list, tuple)):
                inputs_blob.extend(str(x) for x in v)
        reason_tokens = _tokenize(reason)
        input_tokens = _tokenize(" ".join(inputs_blob))
        # 至少 1 个非 stopword token 重合视为 grounded（v1 浅检测）
        overlap = reason_tokens & input_tokens
        if not overlap:
            out.append(
                _diag(
                    severity="warning",
                    kind="decision_without_grounds",
                    target=ev.event_id,
                    label=f"event[seq={ev.seq}]",
                    message=("decision `reason` shares no token with `inputs`; may be ungrounded"),
                    suggested_edit=("Reference at least one input field in `reason`."),
                    data={"trace_anchor": _anchor(ev), "reason_token_count": len(reason_tokens)},
                )
            )
    return out


# ============ Detector 7：tool_call 必须闭合 ============


def detect_tool_pairing(trace: Trace) -> list[Diagnostic]:
    """Require each tool call to be closed by a result, retry, or actor error."""
    out: list[Diagnostic] = []
    events = trace.events
    for i, ev in enumerate(events):
        if ev.kind != "tool_call":
            continue
        closed = False
        for follow in events[i + 1 :]:
            # tool_result 走 parent_event_id 链或 inputs.tool_call_id 都接受
            if follow.kind == "tool_result" and (
                follow.parent_event_id == ev.event_id
                or follow.inputs.get("tool_call_id") == ev.event_id
            ):
                closed = True
                break
            if follow.kind == "retry" and follow.parent_event_id == ev.event_id:
                closed = True
                break
            # 带 error 的同 actor 事件也算闭合（tool 报错被捕获）
            if (
                follow.kind in ("intermediate_state", "decision")
                and follow.actor == ev.actor
                and follow.error
            ):
                closed = True
                break
        if not closed:
            out.append(
                _diag(
                    severity="warning",
                    kind="tool_call_without_result",
                    target=ev.event_id,
                    label=f"event[seq={ev.seq}]",
                    message=(
                        f"tool_call (tool={ev.tool!r}) has no matching "
                        f"tool_result/retry/error within the trace"
                    ),
                    suggested_edit=(
                        "Emit a tool_result with parent_event_id linking back, "
                        "or emit a retry event."
                    ),
                    data={"trace_anchor": _anchor(ev), "tool": ev.tool},
                )
            )
    return out


# ============ Detector 8：claim_ref 引用合法 ============

ReviewIdResolver = Callable[[str], bool]


def _default_resolver_factory(package_path: str | Path | None) -> ReviewIdResolver:
    """Resolve review IDs through package-local inquiry review snapshots.

    package_path 为 None ⇒ 永远 False（detector 会把所有 ref 标 unresolved）。
    """
    if package_path is None:

        def _none_resolver(_review_id: str) -> bool:
            return False

        return _none_resolver
    base = Path(package_path) / ".gaia" / "inquiry" / "reviews"

    def _fs_resolver(review_id: str) -> bool:
        if not review_id:
            return False
        return (base / f"{review_id}.json").is_file()

    return _fs_resolver


def detect_claim_refs(
    trace: Trace,
    *,
    resolver: ReviewIdResolver | None = None,
    package_path: str | Path | None = None,
) -> list[Diagnostic]:
    """Detect claim references whose review IDs cannot be resolved."""
    res = resolver or _default_resolver_factory(package_path)
    out: list[Diagnostic] = []
    for ev in trace.events:
        for j, ref in enumerate(ev.refs):
            try:
                ok = bool(res(ref.review_id))
            except Exception as exc:  # noqa: BLE001 — resolver 不允许 crash detector
                ok = False
                msg_extra = f" (resolver raised: {exc!r})"
            else:
                msg_extra = ""
            if not ok:
                out.append(
                    _diag(
                        severity="warning",
                        kind="unresolved_claim_ref",
                        target=ref.claim_id,
                        label=f"event[seq={ev.seq}].refs[{j}]",
                        message=(
                            f"claim_ref.review_id={ref.review_id!r} "
                            f"cannot be resolved against gaia.inquiry snapshots"
                            f"{msg_extra}"
                        ),
                        suggested_edit=(
                            "Run `gaia inquiry review` on the referenced "
                            "package to mint a valid review_id."
                        ),
                        data={
                            "trace_anchor": _anchor(ev),
                            "claim_id": ref.claim_id,
                            "review_id": ref.review_id,
                            "relation": ref.relation,
                        },
                    )
                )
    return out


# ============ Detector 9：parent_event_id 合法 ============


def detect_parent_links(trace: Trace) -> list[Diagnostic]:
    """Detect parent links that point outside the current trace.

    Args:
        trace: Loaded trace to inspect.

    Returns:
        Diagnostics for dangling `parent_event_id` values.
    """
    ids = {ev.event_id for ev in trace.events}
    out: list[Diagnostic] = []
    for ev in trace.events:
        if ev.parent_event_id and ev.parent_event_id not in ids:
            out.append(
                _diag(
                    severity="info",
                    kind="orphan_event",
                    target=ev.event_id,
                    label=f"event[seq={ev.seq}]",
                    message=(f"parent_event_id={ev.parent_event_id!r} not present in this trace"),
                    suggested_edit=(
                        "Verify the writer emits the parent before the child, "
                        "or remove the dangling parent_event_id."
                    ),
                    data={
                        "trace_anchor": _anchor(ev),
                        "parent_event_id": ev.parent_event_id,
                    },
                )
            )
    return out


# ============ Detector 10：retry 链不发散 ============


def detect_retry(trace: Trace, *, max_chain: int = RETRY_CHAIN_LIMIT_DEFAULT) -> list[Diagnostic]:
    """Detect retry chains whose length exceeds the configured limit."""
    out: list[Diagnostic] = []
    by_id = {ev.event_id: ev for ev in trace.events}
    for ev in trace.events:
        if ev.kind != "retry":
            continue
        chain_len = 1
        cursor: TraceEvent | None = ev
        seen: set[str] = set()
        while cursor and cursor.parent_event_id:
            if cursor.parent_event_id in seen:
                break  # 防 cycle
            seen.add(cursor.parent_event_id)
            parent = by_id.get(cursor.parent_event_id)
            if parent is None:
                break
            if parent.kind == "retry":
                chain_len += 1
            cursor = parent
        if chain_len > max_chain:
            out.append(
                _diag(
                    severity="warning",
                    kind="retry_diverged",
                    target=ev.event_id,
                    label=f"event[seq={ev.seq}]",
                    message=(f"retry chain length {chain_len} exceeds limit {max_chain}"),
                    suggested_edit=(
                        "Cap retries with a back-off policy or surface the "
                        "underlying error instead of looping."
                    ),
                    data={
                        "trace_anchor": _anchor(ev),
                        "retry_chain_length": chain_len,
                        "max_chain": max_chain,
                    },
                )
            )
    return out


# ============ Detector 11：actor 切换需 decision ============


def detect_actor(trace: Trace) -> list[Diagnostic]:
    """Detect unexplained actor switches within each parent-event group.

    分组依据：``parent_event_id``（None ⇒ 顶层组）；同一 group 内事件以 seq 升序
    扫描，前后 actor 不同且中间没有 decision 事件 ⇒ 标 actor_switch_unexplained。
    """
    by_parent: dict[str | None, list[TraceEvent]] = defaultdict(list)
    for ev in trace.events:
        by_parent[ev.parent_event_id].append(ev)
    out: list[Diagnostic] = []
    for _, group in by_parent.items():
        group.sort(key=lambda e: e.seq)
        last_actor: str | None = None
        decision_since_switch = False
        for ev in group:
            if last_actor is None:
                last_actor = ev.actor
                decision_since_switch = ev.kind == "decision"
                continue
            if ev.actor != last_actor:
                if not decision_since_switch:
                    out.append(
                        _diag(
                            severity="info",
                            kind="actor_switch_unexplained",
                            target=ev.event_id,
                            label=f"event[seq={ev.seq}]",
                            message=(
                                f"actor switched from {last_actor!r} to "
                                f"{ev.actor!r} without an intervening "
                                "decision event"
                            ),
                            suggested_edit=("Emit a decision event explaining the handoff."),
                            data={
                                "trace_anchor": _anchor(ev),
                                "from_actor": last_actor,
                                "to_actor": ev.actor,
                            },
                        )
                    )
                last_actor = ev.actor
                decision_since_switch = ev.kind == "decision"
            else:
                if ev.kind == "decision":
                    decision_since_switch = True
    return out


# ============ 汇总入口 ============


def run_all_detectors(
    load_result: LoadResult,
    *,
    resolver: ReviewIdResolver | None = None,
    package_path: str | Path | None = None,
    retry_chain_limit: int = RETRY_CHAIN_LIMIT_DEFAULT,
) -> list[Diagnostic]:
    """Run all trace detectors in their stable review order."""
    diags: list[Diagnostic] = []
    diags.extend(from_schema_issues(load_result.issues))
    if load_result.trace is None:
        return diags
    trace = load_result.trace
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
    return diags
