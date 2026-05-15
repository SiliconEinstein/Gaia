"""Pydantic schema for ARM Trace v1.

字段语义参考 ARM 协议 v1 §7（Trace modality）：
- 一段 trace 由 manifest（元信息 + hash 锚）和 events（事件流）构成
- 每条 event 携 prev_hash 形成单向链，破坏链 ⇒ reviewer 必检出
- manifest.events_root 是全部 events canonical-json 的 sha256，独立校验

文件布局：
- 单 JSON：``{"manifest": {...}, "events": [...]}``
- JSONL：第一行 manifest，其余每行一个 event

设计纪律：
- 所有字段语义由 schema 自身定义，**不**与任何外部系统耦合
- 字段缺失/类型错 ⇒ pydantic 抛 ValidationError；loader 捕获后转为
  ``trace_schema_violation`` diagnostic，不让 reviewer crash
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ARM trace 当前 schema 版本——升 schema 时同步改 v1 → v2
SCHEMA_VERSION: str = "1.0"

# 事件 kind 枚举，扩展时同步 detector 与 ranking 表
TraceEventKind = Literal[
    "decision",
    "tool_call",
    "tool_result",
    "intermediate_state",
    "retry",
    "claim_ref",
]

# 引用关系——把 trace 的事件挂回 gaia knowledge graph 的 claim
ClaimRefRelation = Literal["asserts", "uses", "contradicts"]


class ClaimRef(BaseModel):
    """Reference one Gaia knowledge claim from a trace event."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., min_length=1)
    review_id: str = Field(..., min_length=1)
    relation: ClaimRefRelation


class TraceEvent(BaseModel):
    """Represent the smallest accounting unit in an ARM trace.

    - prev_hash：前一事件的 canonical-json sha256（首事件 ``""``）
    - seq：单调递增整数，从 0 起，reviewer 校验连续
    - ts：utc datetime；reviewer 校验单调非降
    - parent_event_id：retry / sub-call 父子关系（None ⇒ root 事件）
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1)
    seq: int = Field(..., ge=0)
    prev_hash: str = ""
    ts: datetime
    kind: TraceEventKind
    actor: str = Field(..., min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    reason: str | None = None
    refs: list[ClaimRef] = Field(default_factory=list)
    parent_event_id: str | None = None
    tool: str | None = None
    error: str | None = None


class TraceManifest(BaseModel):
    """Describe trace metadata and hash anchors.

    ``events_root`` / ``manifest_hash`` 在写入端计算后冻结，
    reviewer 端独立重算比对——任何字段被改 ⇒ 哈希不一致。

    ``signature`` 字段是 v2 hook，v1 不验签也不强求填。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION)
    arm_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    created_at: datetime
    events_root: str = ""
    manifest_hash: str = ""
    signature: str | None = None  # v2 ed25519 hook，v1 留空


class Trace(BaseModel):
    """Represent a complete trace as a manifest plus ordered events."""

    model_config = ConfigDict(extra="forbid")

    manifest: TraceManifest
    events: list[TraceEvent] = Field(default_factory=list)
