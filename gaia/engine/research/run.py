"""UI-observable research run envelopes."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia.engine.research.artifacts import ResearchPackage, ensure_research_manifest

RUN_SCHEMA_VERSION = 1
RUN_MODES = {"fast-package-native"}


@dataclass(frozen=True)
class ResearchRunStart:
    """Result of creating a UI-observable research run envelope."""

    run_id: str
    run_dir: Path
    state_path: Path
    events_path: Path
    checkpoint_path: Path
    events: list[dict[str, Any]]


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utcstamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized[:40] or "research"


def _validate_run_id(value: str) -> str:
    if value != _slug(value):
        msg = (
            "run_id must contain only lowercase ASCII letters, digits, and hyphens, "
            "and must not start or end with a hyphen"
        )
        raise ValueError(msg)
    return value


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


def _package_payload(pkg: ResearchPackage) -> dict[str, str]:
    return {
        "path": str(pkg.path),
        "project_name": pkg.project_name,
        "import_name": pkg.import_name,
        "namespace": pkg.namespace,
    }


def append_run_event(
    events_path: Path,
    *,
    run_id: str,
    event_type: str,
    phase: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one UI-facing run event and return the event payload."""
    event: dict[str, Any] = {
        "schema_version": RUN_SCHEMA_VERSION,
        "type": event_type,
        "run_id": run_id,
        "phase": phase,
        "ts": _utcnow(),
    }
    if payload:
        event.update(payload)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def write_run_state(state_path: Path, state: dict[str, Any]) -> None:
    """Atomically write the current UI-facing run state."""
    _write_json_atomic(state_path, state)


def start_research_run(
    pkg: ResearchPackage,
    *,
    topic: str,
    mode: str,
    language: str,
    profile: str,
    run_id: str | None = None,
    wait_for_query_plan: bool = True,
) -> ResearchRunStart:
    """Create the initial run state and query-plan checkpoint."""
    if mode not in RUN_MODES:
        msg = f"unsupported research run mode: {mode!r}"
        raise ValueError(msg)
    ensure_research_manifest(pkg)
    resolved_run_id = (
        _validate_run_id(run_id) if run_id is not None else f"{_slug(topic)}-{_utcstamp()}"
    )
    run_dir = pkg.path / ".gaia" / "research" / "runs" / resolved_run_id
    searches_dir = run_dir / "searches"
    analysis_dir = run_dir / "analysis"
    trace_dir = run_dir / "trace"
    checkpoint_dir = run_dir / "checkpoints"
    for path in (searches_dir, analysis_dir, trace_dir, checkpoint_dir):
        path.mkdir(parents=True, exist_ok=True)

    events_path = run_dir / "events.ndjson"
    checkpoint_path = checkpoint_dir / "query_plan.request.json"
    state_path = run_dir / "state.json"

    state = {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "status": "waiting_for_input" if wait_for_query_plan else "running",
        "phase": "query_plan" if wait_for_query_plan else "setup",
        "mode": mode,
        "profile": profile,
        "language": language,
        "topic": topic,
        "package": _package_payload(pkg),
        "run_dir": str(run_dir),
        "trace_dir": str(trace_dir),
        "pending_checkpoint": str(checkpoint_path) if wait_for_query_plan else None,
        "artifacts": {},
        "metrics": {},
    }
    _write_json_atomic(state_path, state)

    events: list[dict[str, Any]] = []
    events.append(
        append_run_event(
            events_path,
            run_id=resolved_run_id,
            event_type="run.created",
            phase="setup",
            payload={
                "run_dir": str(run_dir),
                "mode": mode,
                "profile": profile,
                "language": language,
                "topic": topic,
            },
        )
    )
    if wait_for_query_plan:
        checkpoint = {
            "schema_version": RUN_SCHEMA_VERSION,
            "type": "checkpoint.query_plan",
            "checkpoint_id": "query_plan_001",
            "phase": "query_plan",
            "prompt": "Review or edit broad query families before live search.",
            "choices": [
                {
                    "id": "continue",
                    "label": "Continue with defaults",
                    "recommended": True,
                }
            ],
            "default_action": {
                "action": "continue",
                "queries": [],
            },
        }
        _write_json_atomic(checkpoint_path, checkpoint)
        events.append(
            append_run_event(
                events_path,
                run_id=resolved_run_id,
                event_type="checkpoint.created",
                phase="query_plan",
                payload={
                    "path": str(checkpoint_path),
                    "checkpoint_type": "checkpoint.query_plan",
                },
            )
        )
        events.append(
            append_run_event(
                events_path,
                run_id=resolved_run_id,
                event_type="run.waiting_for_input",
                phase="query_plan",
                payload={"pending_checkpoint": str(checkpoint_path)},
            )
        )

    return ResearchRunStart(
        run_id=resolved_run_id,
        run_dir=run_dir,
        state_path=state_path,
        events_path=events_path,
        checkpoint_path=checkpoint_path,
        events=events,
    )


__all__ = [
    "RUN_MODES",
    "RUN_SCHEMA_VERSION",
    "ResearchRunStart",
    "append_run_event",
    "start_research_run",
    "write_run_state",
]
