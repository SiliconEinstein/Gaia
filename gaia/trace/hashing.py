"""Canonical JSON and SHA-256 helpers for trace tamper checks.

设计纪律（吸取 dz-fusion P0-1 教训：reviewer 不允许走"trace 自己说我没坏"
的捷径，必须独立重算）：

- ``canonical_json``：固定 ``sort_keys=True`` + ``separators=(",", ":")`` +
  ``ensure_ascii=False``，``datetime`` 序列化为 ISO8601 utc string，
  ``float`` 严格走标准 repr——跨平台 byte-equal
- ``recompute_chain``：从 events[0] 开始独立逐条算 prev_hash，**不读** event 自带的
  prev_hash 字段做判断；返回 ``[hash_of_event_0, hash_of_event_1, ...]``
- ``compute_events_root``：把 events 序列整体 canonical-json 后 sha256，作为
  manifest.events_root 的真值，独立于 chain hash 提供第二条校验路径
- ``compute_manifest_hash``：先把 manifest 中的 ``manifest_hash`` 字段去掉再 hash，
  避免 self-reference

reviewer 端比对：
1. recompute_chain[i] == events[i+1].prev_hash？
2. compute_events_root(events) == manifest.events_root？
3. compute_manifest_hash(manifest) == manifest.manifest_hash？
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from gaia.trace.schema import TraceEvent, TraceManifest

# 首事件 prev_hash 的约定值（空串），便于 writer 与 reviewer 共识
GENESIS_PREV_HASH: str = ""


def _to_jsonable(value: Any) -> Any:
    """Convert values into deterministic JSON-compatible structures.

    - datetime：先归一化到 UTC，再 isoformat（with 'Z'），byte-equal 不依赖 tz suffix
    - dict：按 key 递归（key 必须是 str；非 str key 抛 TypeError）
    - list/tuple：递归
    - bool/int/str/float/None：原样
    - 其他对象：fallback 走 ``str(value)``，并在 reviewer 侧记 corrupt
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("non-finite float in canonical_json input")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            v = value.replace(tzinfo=timezone.utc)
        else:
            v = value.astimezone(timezone.utc)
        s = v.isoformat()
        if s.endswith("+00:00"):
            s = s[:-6] + "Z"
        return s
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"canonical_json requires str dict keys, got {type(k)}")
            out[k] = _to_jsonable(v)
        return out
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    raise TypeError(f"canonical_json cannot serialize {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    """Encode JSON byte-identically across platforms and processes.

    用于 hash chain 与 events_root；任何调整都会让既有 trace 失效，需慎重升 schema。
    """
    norm = _to_jsonable(value)
    return json.dumps(
        norm,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def event_payload(event: TraceEvent) -> dict[str, Any]:
    """Project an event into the payload used for chain hashing.

    把 prev_hash 从 hash 输入里剔除是关键：否则改 prev_hash 会让 hash 也变，
    chain 本身就形成自洽循环——reviewer 将检不出篡改。
    """
    d = event.model_dump()
    d.pop("prev_hash", None)
    return d


def hash_event(event: TraceEvent) -> str:
    """Hash one trace event after removing its `prev_hash` link."""
    return sha256_hex(canonical_json(event_payload(event)))


def recompute_chain(events: list[TraceEvent]) -> list[str]:
    """Recompute each event hash independently.

    - 不读 event.prev_hash；reviewer 用返回值与 events[i+1].prev_hash 比对
    - 空 events → 空列表
    """
    return [hash_event(ev) for ev in events]


def compute_events_root(events: list[TraceEvent]) -> str:
    """Compute the root hash for the full event sequence."""
    payload = [event_payload(ev) for ev in events]
    return sha256_hex(canonical_json(payload))


def compute_manifest_hash(manifest: TraceManifest) -> str:
    """Compute the manifest hash with `manifest_hash` excluded."""
    d = manifest.model_dump()
    d.pop("manifest_hash", None)
    return sha256_hex(canonical_json(d))


def verify_chain(events: list[TraceEvent]) -> tuple[bool, int | None]:
    """Check hash-chain integrity and return `(ok, broken_at_seq)`.

    - events[0].prev_hash 必须等于 ``GENESIS_PREV_HASH``
    - 第 i 条（i >= 1）的 prev_hash 必须等于 hash_event(events[i-1])
    - 任一条不满足 ⇒ (False, events[i].seq)；都满足 ⇒ (True, None)
    """
    if not events:
        return True, None
    if events[0].prev_hash != GENESIS_PREV_HASH:
        return False, events[0].seq
    chain = recompute_chain(events)
    for i in range(1, len(events)):
        expected = chain[i - 1]
        if events[i].prev_hash != expected:
            return False, events[i].seq
    return True, None
