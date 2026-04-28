"""Trace 文件加载——支持单 JSON 与 JSONL 两种布局，schema 失败统一降级。

reviewer 主流程不允许加载阶段 crash：任何破坏（非法 json、缺字段、类型错）
都被翻译成 ``trace_schema_violation`` 诊断条目，正常进 ranking 流。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from gaia.trace.schema import Trace, TraceEvent, TraceManifest


@dataclass
class SchemaIssue:
    """加载/校验失败的统一表示——后续转成 Diagnostic。"""

    message: str
    location: str = ""  # 例如 "events[3].kind"
    raw: dict | None = field(default=None)


@dataclass
class LoadResult:
    """加载结果：要么 trace 非空，要么 issues 非空，二者也可同时存在
    （比如 manifest 校验通过但部分 event 损坏——loader 会把损坏 event 跳过、
    其余装入 trace、在 issues 报告损坏行号）。"""

    trace: Trace | None
    issues: list[SchemaIssue] = field(default_factory=list)
    raw_path: str = ""


def _format_pydantic_error(err: ValidationError, prefix: str = "") -> list[SchemaIssue]:
    out: list[SchemaIssue] = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e.get("loc", ()))
        full_loc = f"{prefix}{loc}" if prefix else loc
        msg = e.get("msg", "validation error")
        out.append(SchemaIssue(message=msg, location=full_loc))
    return out


def _load_single_json(path: Path) -> LoadResult:
    issues: list[SchemaIssue] = []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message=f"read error: {exc}", location="<file>")],
            raw_path=str(path),
        )
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message=f"json decode: {exc}", location="<file>")],
            raw_path=str(path),
        )
    if not isinstance(data, dict):
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message="root must be object", location="<root>")],
            raw_path=str(path),
        )
    try:
        trace = Trace.model_validate(data)
        return LoadResult(trace=trace, issues=[], raw_path=str(path))
    except ValidationError as exc:
        issues.extend(_format_pydantic_error(exc))
        # 退化：尝试只解析 manifest，events 逐条解析
        return _try_partial(data, issues, path)


def _load_jsonl(path: Path) -> LoadResult:
    issues: list[SchemaIssue] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message=f"read error: {exc}", location="<file>")],
            raw_path=str(path),
        )
    nonempty = [(i, ln) for i, ln in enumerate(lines) if ln.strip()]
    if not nonempty:
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message="empty file", location="<file>")],
            raw_path=str(path),
        )
    # 第一行 manifest
    idx0, line0 = nonempty[0]
    try:
        manifest_raw = json.loads(line0)
    except json.JSONDecodeError as exc:
        return LoadResult(
            trace=None,
            issues=[
                SchemaIssue(
                    message=f"manifest json decode: {exc}",
                    location=f"line:{idx0 + 1}",
                )
            ],
            raw_path=str(path),
        )
    try:
        manifest = TraceManifest.model_validate(manifest_raw)
    except ValidationError as exc:
        issues.extend(_format_pydantic_error(exc, prefix="manifest."))
        manifest = None
    # 后续行 events
    events: list[TraceEvent] = []
    for raw_idx, line in nonempty[1:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(
                SchemaIssue(
                    message=f"event json decode: {exc}",
                    location=f"line:{raw_idx + 1}",
                )
            )
            continue
        try:
            ev = TraceEvent.model_validate(obj)
            events.append(ev)
        except ValidationError as exc:
            issues.extend(_format_pydantic_error(exc, prefix=f"line:{raw_idx + 1}."))
    if manifest is None:
        return LoadResult(trace=None, issues=issues, raw_path=str(path))
    trace = Trace(manifest=manifest, events=events)
    return LoadResult(trace=trace, issues=issues, raw_path=str(path))


def _try_partial(data: dict, issues: list[SchemaIssue], path: Path) -> LoadResult:
    """单 JSON 整体校验失败时退化：尽量保住 manifest，逐条解析 events。"""
    manifest_raw = data.get("manifest")
    events_raw = data.get("events", [])
    manifest = None
    if isinstance(manifest_raw, dict):
        try:
            manifest = TraceManifest.model_validate(manifest_raw)
        except ValidationError as exc:
            issues.extend(_format_pydantic_error(exc, prefix="manifest."))
    events: list[TraceEvent] = []
    if isinstance(events_raw, list):
        for i, item in enumerate(events_raw):
            try:
                ev = TraceEvent.model_validate(item)
                events.append(ev)
            except ValidationError as exc:
                issues.extend(_format_pydantic_error(exc, prefix=f"events[{i}]."))
    if manifest is None:
        return LoadResult(trace=None, issues=issues, raw_path=str(path))
    return LoadResult(
        trace=Trace(manifest=manifest, events=events),
        issues=issues,
        raw_path=str(path),
    )


def _detect_layout(path: Path) -> str:
    """通过文件后缀 + 首字符快速判断单 JSON 还是 JSONL。"""
    suffix = path.suffix.lower()
    if suffix == ".jsonl" or suffix == ".ndjson":
        return "jsonl"
    if suffix == ".json":
        return "json"
    # 后缀不明：peek 第一字符
    try:
        with path.open("rb") as f:
            head = f.read(2048)
    except OSError:
        return "json"
    text = head.decode("utf-8", errors="replace").lstrip()
    # 单 JSON 通常 '{' 后立刻是空白/换行 + '"manifest"'，整段是一个对象
    if text.startswith("{"):
        # 多行 + 行起头都是 '{' 也可能是 jsonl，进一步判断
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2 and lines[1].lstrip().startswith("{"):
            return "jsonl"
        return "json"
    return "json"


def load_trace(path: str | Path) -> LoadResult:
    """加载 trace 文件，自动识别 JSON 与 JSONL 布局。

    永不抛异常——任何错误都进 ``LoadResult.issues``。
    """
    p = Path(path)
    if not p.exists():
        return LoadResult(
            trace=None,
            issues=[SchemaIssue(message="file not found", location="<file>")],
            raw_path=str(p),
        )
    layout = _detect_layout(p)
    if layout == "jsonl":
        return _load_jsonl(p)
    return _load_single_json(p)
