"""State-machine helpers for the Gaia research loop CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia.research_loop.storage import ensure_loop_dirs, load_events, rebuild_state


def status_payload(pkg: str | Path) -> dict[str, Any]:
    """Return a JSON-compatible research-loop status payload."""
    paths = ensure_loop_dirs(pkg)
    state = rebuild_state(paths)
    events = load_events(paths)
    return {
        "schema": state.schema_id,
        "phase": state.phase,
        "root": str(paths.root),
        "latest_task_by_stage": state.latest_task_by_stage,
        "latest_artifact_by_stage": state.latest_artifact_by_stage,
        "event_count": len(events),
        "recommended_next": "gaia-research-loop next",
    }
