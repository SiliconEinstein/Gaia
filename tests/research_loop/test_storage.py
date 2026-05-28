from __future__ import annotations

from pathlib import Path

from gaia.research_loop.storage import (
    append_event,
    ensure_loop_dirs,
    load_events,
    rebuild_state,
    write_json,
)


def test_ensure_loop_dirs_creates_canonical_layout(tmp_path: Path) -> None:
    paths = ensure_loop_dirs(tmp_path)

    assert paths.root == tmp_path / ".gaia" / "research_loop"
    for stage in ["explore", "assess"]:
        for leaf in ["tasks", "candidates", "artifacts"]:
            assert (paths.root / stage / leaf).is_dir()


def test_append_event_writes_jsonl(tmp_path: Path) -> None:
    paths = ensure_loop_dirs(tmp_path)
    append_event(paths, event_type="task_emitted", stage="explore", data={"task_id": "t1"})

    events = load_events(paths)
    assert len(events) == 1
    assert events[0].event_type == "task_emitted"
    assert events[0].stage == "explore"
    assert events[0].data == {"task_id": "t1"}


def test_rebuild_state_indexes_latest_task_and_artifact(tmp_path: Path) -> None:
    paths = ensure_loop_dirs(tmp_path)
    write_json(paths.explore_tasks / "task-1.json", {"task_id": "task-1", "kind": "scope"})
    write_json(paths.explore_artifacts / "scope.json", {"kind": "scope", "id": "scope-1"})

    state = rebuild_state(paths)

    assert state.schema_id == "gaia.research_loop.state.v1"
    assert state.latest_task_by_stage["explore"].endswith("task-1.json")
    assert state.latest_artifact_by_stage["explore"].endswith("scope.json")
