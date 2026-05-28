"""Storage helpers for canonical research loop artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.research_loop.schemas import ResearchLoopEvent, ResearchLoopState, Stage


@dataclass(frozen=True)
class ResearchLoopPaths:
    """Canonical paths under ``<pkg>/.gaia/research_loop``."""

    pkg: Path
    root: Path
    state: Path
    events: Path
    explore_tasks: Path
    explore_candidates: Path
    explore_artifacts: Path
    assess_tasks: Path
    assess_candidates: Path
    assess_artifacts: Path


def loop_paths(pkg: str | Path) -> ResearchLoopPaths:
    """Return canonical research-loop paths for a package."""
    pkg_path = Path(pkg).resolve()
    root = pkg_path / ".gaia" / "research_loop"
    return ResearchLoopPaths(
        pkg=pkg_path,
        root=root,
        state=root / "state.json",
        events=root / "events.jsonl",
        explore_tasks=root / "explore" / "tasks",
        explore_candidates=root / "explore" / "candidates",
        explore_artifacts=root / "explore" / "artifacts",
        assess_tasks=root / "assess" / "tasks",
        assess_candidates=root / "assess" / "candidates",
        assess_artifacts=root / "assess" / "artifacts",
    )


def ensure_loop_dirs(pkg: str | Path) -> ResearchLoopPaths:
    """Create the canonical research-loop directory layout."""
    paths = loop_paths(pkg)
    for directory in [
        paths.explore_tasks,
        paths.explore_candidates,
        paths.explore_artifacts,
        paths.assess_tasks,
        paths.assess_candidates,
        paths.assess_artifacts,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def append_event(
    paths: ResearchLoopPaths,
    *,
    event_type: str,
    stage: Stage | None,
    data: dict[str, Any],
) -> ResearchLoopEvent:
    """Append one JSONL audit event."""
    event = ResearchLoopEvent(event_type=event_type, stage=stage, data=data)
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    with paths.events.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json(by_alias=True) + "\n")
    return event


def load_events(paths: ResearchLoopPaths) -> list[ResearchLoopEvent]:
    """Load audit events from JSONL."""
    if not paths.events.exists():
        return []
    return [
        ResearchLoopEvent.model_validate_json(line)
        for line in paths.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latest_json_path(directory: Path) -> str | None:
    matches = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime)
    return str(matches[-1]) if matches else None


def rebuild_state(paths: ResearchLoopPaths) -> ResearchLoopState:
    """Rebuild navigation state from task and artifact files."""
    state = ResearchLoopState(
        latest_task_by_stage={
            stage: path
            for stage, path in {
                "explore": _latest_json_path(paths.explore_tasks),
                "assess": _latest_json_path(paths.assess_tasks),
            }.items()
            if path is not None
        },
        latest_artifact_by_stage={
            stage: path
            for stage, path in {
                "explore": _latest_json_path(paths.explore_artifacts),
                "assess": _latest_json_path(paths.assess_artifacts),
            }.items()
            if path is not None
        },
    )
    write_json(paths.state, state.model_dump(mode="json", by_alias=True))
    return state
