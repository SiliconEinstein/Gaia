"""Research run trace helpers and derived benchmark summaries."""

from __future__ import annotations

import json
import tempfile
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from gaia.engine.research.artifacts import ResearchPackage

BENCHMARK_SCHEMA_VERSION = 1
TRACE_LOCK_TIMEOUT_SECONDS = 30.0


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _isoformat_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _package_payload(pkg: ResearchPackage) -> dict[str, Any]:
    return {
        "path": str(pkg.path),
        "project_name": pkg.project_name,
        "import_name": pkg.import_name,
        "namespace": pkg.namespace,
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


@contextmanager
def _trace_write_lock(trace_dir: Path) -> Iterator[None]:
    """Serialize trace writes and derived summary refreshes for one trace dir."""
    trace_dir.mkdir(parents=True, exist_ok=True)
    lock_dir = trace_dir / ".trace.lock"
    deadline = time.monotonic() + TRACE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                msg = f"timed out waiting for research trace lock: {lock_dir}"
                raise TimeoutError(msg) from None
            time.sleep(0.01)
    try:
        yield
    finally:
        lock_dir.rmdir()


def resolve_trace_dir(pkg: ResearchPackage, path: str | Path | None) -> Path:
    """Resolve the trace directory for ``pkg``."""
    if path is None:
        return pkg.path / ".gaia" / "research" / "runs" / "current" / "trace"
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = pkg.path / resolved
    return resolved


def _append_trace_record(trace_dir: Path, step: dict[str, Any]) -> Path:
    trace_path = trace_dir / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    ts_end = datetime.now(tz=UTC)
    wall = step.get("wall_seconds")
    wall_seconds = float(wall) if isinstance(wall, int | float) else 0.0
    ts_start = ts_end - timedelta(seconds=max(0.0, wall_seconds))
    kind = str(step.get("kind") or "external")
    actor = "gaia_cli" if kind == "cli" else kind
    record = {
        "schema_version": 1,
        "ts_start": _isoformat_utc(ts_start),
        "ts_end": _isoformat_utc(ts_end),
        "actor": actor,
        "step": step.get("name"),
        "kind": kind,
        "mode": step.get("mode"),
        "status": "ok",
        "wall_seconds": wall_seconds,
        "inputs": list(step.get("inputs") or []),
        "outputs": list(step.get("outputs") or []),
        "metrics": dict(step.get("metrics") or {}),
    }
    if "model" in step:
        record["model"] = step["model"]
    if "token_usage" in step:
        record["token_usage"] = step["token_usage"]
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return trace_path


def _read_trace_records(trace_dir: Path) -> list[dict[str, Any]]:
    trace_path = trace_dir / "trace.jsonl"
    if not trace_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _benchmark_step_from_trace(record: dict[str, Any]) -> dict[str, Any]:
    step = {
        "name": record.get("step"),
        "kind": record.get("kind"),
        "mode": record.get("mode"),
        "timestamp": record.get("ts_end"),
        "wall_seconds": record.get("wall_seconds"),
        "inputs": list(record.get("inputs") or []),
        "outputs": list(record.get("outputs") or []),
        "metrics": dict(record.get("metrics") or {}),
    }
    if "model" in record:
        step["model"] = record["model"]
    if "token_usage" in record:
        step["token_usage"] = record["token_usage"]
    return step


def _benchmark_payload_from_trace(trace_dir: Path, pkg: ResearchPackage) -> dict[str, Any]:
    now = _utcnow()
    benchmark_path = trace_dir / "benchmark.json"
    created_at = now
    if benchmark_path.exists():
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_run = payload.get("run")
            if isinstance(raw_run, dict) and isinstance(raw_run.get("created_at"), str):
                created_at = raw_run["created_at"]
    steps = [_benchmark_step_from_trace(record) for record in _read_trace_records(trace_dir)]
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run": {
            "created_at": created_at,
            "updated_at": now,
            "package": _package_payload(pkg),
        },
        "steps": steps,
        "summary": _summary(steps),
    }


def _summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    total_wall = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    kind_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()

    for step in steps:
        wall = step.get("wall_seconds")
        if isinstance(wall, int | float):
            total_wall += float(wall)
        kind = step.get("kind")
        if isinstance(kind, str) and kind:
            kind_counts[kind] += 1
        mode = step.get("mode")
        if isinstance(mode, str) and mode:
            mode_counts[mode] += 1
        token_usage = step.get("token_usage")
        if isinstance(token_usage, dict):
            input_tokens = token_usage.get("input_tokens")
            output_tokens = token_usage.get("output_tokens")
            if isinstance(input_tokens, int):
                total_input_tokens += input_tokens
            if isinstance(output_tokens, int):
                total_output_tokens += output_tokens

    return {
        "steps": len(steps),
        "total_wall_seconds": round(total_wall, 6),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "kind_counts": dict(kind_counts),
        "mode_counts": dict(mode_counts),
    }


def append_research_trace_step(
    pkg: ResearchPackage,
    trace_dir_path: str | Path | None,
    *,
    name: str,
    kind: str,
    mode: str,
    wall_seconds: float,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    model: str | None = None,
    token_usage: dict[str, int] | None = None,
) -> Path:
    """Append one measured step to source-of-truth ``trace.jsonl``."""
    trace_dir = resolve_trace_dir(pkg, trace_dir_path)
    step: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "mode": mode,
        "timestamp": _utcnow(),
        "wall_seconds": round(max(0.0, wall_seconds), 6),
        "inputs": list(inputs or []),
        "outputs": list(outputs or []),
        "metrics": dict(metrics or {}),
    }
    if model:
        step["model"] = model
    if token_usage:
        step["token_usage"] = dict(token_usage)

    with _trace_write_lock(trace_dir):
        return _append_trace_record(trace_dir, step)


def write_research_benchmark_summary(
    pkg: ResearchPackage,
    trace_dir_path: str | Path | None,
) -> Path:
    """Rebuild derived ``benchmark.json`` from source-of-truth ``trace.jsonl``."""
    trace_dir = resolve_trace_dir(pkg, trace_dir_path)
    with _trace_write_lock(trace_dir):
        benchmark_path = trace_dir / "benchmark.json"
        _write_json_atomic(benchmark_path, _benchmark_payload_from_trace(trace_dir, pkg))
    return benchmark_path


__all__ = [
    "BENCHMARK_SCHEMA_VERSION",
    "append_research_trace_step",
    "resolve_trace_dir",
    "write_research_benchmark_summary",
]
