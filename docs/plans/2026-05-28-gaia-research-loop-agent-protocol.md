# Gaia Research Loop Agent Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the MVP `gaia-research-loop` CLI and protocol so a generic agent can run an Explore -> Assess loop through self-contained task envelopes, validated candidate JSON, durable artifacts, and repairable state.

**Architecture:** Add a new `gaia.research_loop` package that owns protocol schemas, storage, event logging, state rebuild, task generation, candidate validation, and the `gaia-research-loop` Typer app. Reuse `gaia.lkm_explorer` landscape/focus helpers where possible, but keep the new loop storage under `.gaia/research_loop/` and keep `gaia-lkm-explore` backward-compatible.

**Tech Stack:** Python 3.12, Typer, Pydantic v2, pytest, ruff, mypy strict, existing `uv` workflow.

---

## Implementation Strategy

This plan intentionally builds the protocol in thin, testable layers:

1. Shared schema and storage.
2. `status` and state rebuild.
3. Pure task-builder primitives and a `task` CLI group.
4. `next` task emission on top of the primitives.
5. `submit` validation and repair context.
6. Query planning and mechanical search execution.
7. LKM landscape adaptation under the new storage layout.
8. Focus synthesis and Explore gate.
9. Assessment context, evidence diagnosis, and Assess gate.
10. Thin in-repo skill template and final verification.

Every intelligent step is represented as a task envelope. Gaia validates shape,
grounding, and state transitions; the external agent supplies semantic judgment.

## File Structure

Create:

- `gaia/research_loop/__init__.py`  
  Public package marker and CLI-facing exports.
- `gaia/research_loop/schemas.py`  
  Pydantic models and constants for task, candidate, artifact, gate, state, refs,
  events, query plans, focuses, and assessment outputs.
- `gaia/research_loop/storage.py`  
  Canonical path helpers, directory initialization, JSON read/write, state rebuild,
  and event log append/read helpers.
- `gaia/research_loop/tasks.py`  
  Task envelope builders for scope, query planning, search execution, focus
  synthesis, assessment context, and evidence diagnosis.
- `gaia/research_loop/engine.py`  
  State machine orchestration for `status`, `next`, `submit`, and `gate`.
- `gaia/research_loop/lkm_adapter.py`  
  LKM-specific parsing and reuse of `gaia.lkm_explorer` landscape/focus helpers.
- `gaia/research_loop/cli.py`  
  Typer app for `gaia-research-loop`, including orchestration commands and a
  `task` sub-app for independently callable primitives.
- `tests/research_loop/__init__.py`
- `tests/research_loop/test_schemas.py`
- `tests/research_loop/test_storage.py`
- `tests/research_loop/test_cli_status.py`
- `tests/research_loop/test_next_submit.py`
- `tests/research_loop/test_lkm_adapter.py`
- `tests/research_loop/test_explore_gate.py`
- `tests/research_loop/test_assess_gate.py`
- `gaia/_skills/gaia-research-loop/SKILL.md`

Modify:

- `pyproject.toml`  
  Add the `gaia-research-loop` console script.
- `tests/baseline/__snapshots__/test_help_snapshots/` if the existing help
  snapshot suite discovers console scripts automatically. If it does not,
  leave snapshots untouched.

Do not modify:

- `gaia/lkm_explorer/client/verbs.py` unless a small exported helper is needed.
  It is already large; new loop orchestration belongs in `gaia/research_loop/`.
- Existing `.gaia/exploration/` artifact paths. The new canonical path is
  `.gaia/research_loop/`.

---

## Task 1: Schema Models

**Files:**

- Create: `gaia/research_loop/__init__.py`
- Create: `gaia/research_loop/schemas.py`
- Create: `tests/research_loop/__init__.py`
- Test: `tests/research_loop/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/research_loop/test_schemas.py` with tests that establish the
contract before implementation:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaia.research_loop.schemas import (
    CandidateEnvelope,
    EvidenceRef,
    ResearchLoopTask,
    TaskKind,
)


def test_task_embeds_contract_and_minimal_example() -> None:
    task = ResearchLoopTask(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        objective="Plan the next LKM searches.",
        inputs={"scope": {"seed": "aspirin primary prevention"}},
        instructions=["Return two focused queries."],
        allowed_actions=["submit_query_plan", "stop"],
        recommended_action="submit_query_plan",
        output_contract={"type": "object", "required": ["queries"]},
        allowed_refs=[EvidenceRef(kind="scope", id="scope-1")],
        minimal_example={"queries": [{"query": "example query", "purpose": "shape only"}]},
        submit_command="gaia-research-loop submit /tmp/pkg candidate.json",
    )

    assert task.schema == "gaia.research_loop.task.v1"
    assert task.stage == "explore"
    assert task.kind == TaskKind.QUERY_PLAN
    assert task.repair_context is None


def test_candidate_selected_action_must_be_allowed_or_recommended() -> None:
    candidate = CandidateEnvelope(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        selected_action="stop",
        override_rationale="Budget exhausted.",
        payload={"reason": "No more searches."},
    )

    candidate.validate_against_actions(
        recommended_action="submit_query_plan",
        allowed_actions=["submit_query_plan", "stop"],
    )


def test_candidate_override_requires_rationale() -> None:
    candidate = CandidateEnvelope(
        task_id="task-query-plan-1",
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        selected_action="stop",
        payload={"reason": "No more searches."},
    )

    with pytest.raises(ValueError, match="override_rationale"):
        candidate.validate_against_actions(
            recommended_action="submit_query_plan",
            allowed_actions=["submit_query_plan", "stop"],
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ResearchLoopTask(
            task_id="task-query-plan-1",
            stage="explore",
            kind=TaskKind.QUERY_PLAN,
            objective="Plan.",
            inputs={},
            instructions=[],
            allowed_actions=["submit_query_plan"],
            recommended_action="submit_query_plan",
            output_contract={},
            allowed_refs=[],
            minimal_example={},
            submit_command="gaia-research-loop submit /tmp/pkg candidate.json",
            unexpected=True,
        )
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_schemas.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'gaia.research_loop'`.

- [ ] **Step 3: Implement schema models**

Create `gaia/research_loop/__init__.py`:

```python
"""Agent-facing Gaia research loop protocol."""
```

Create `gaia/research_loop/schemas.py` with:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TASK_SCHEMA = "gaia.research_loop.task.v1"
CANDIDATE_SCHEMA = "gaia.research_loop.candidate.v1"
ARTIFACT_SCHEMA = "gaia.research_loop.artifact.v1"
GATE_SCHEMA = "gaia.research_loop.gate.v1"

Stage = Literal["explore", "assess"]


class TaskKind(StrEnum):
    SCOPE = "scope"
    QUERY_PLAN = "query_plan"
    SEARCH_EXECUTION = "search_execution"
    FOCUS_SYNTHESIS = "focus_synthesis"
    EXPLORE_GATE = "explore_gate"
    ASSESSMENT_CONTEXT = "assessment_context"
    EVIDENCE_DIAGNOSIS = "evidence_diagnosis"
    ASSESS_GATE = "assess_gate"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str
    role: str | None = None


class RepairContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failed_candidate_path: str
    errors: list[dict[str, Any]]
    instruction: str
    preserved_fields: dict[str, Any] = Field(default_factory=dict)


class ResearchLoopTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: Literal["gaia.research_loop.task.v1"] = TASK_SCHEMA
    task_id: str
    stage: Stage
    kind: TaskKind
    objective: str
    inputs: dict[str, Any]
    instructions: list[str]
    allowed_actions: list[str]
    recommended_action: str
    output_contract: dict[str, Any]
    allowed_refs: list[EvidenceRef] = Field(default_factory=list)
    minimal_example: dict[str, Any]
    submit_command: str
    validation: dict[str, Any] = Field(default_factory=dict)
    repair_context: RepairContext | None = None


class CandidateEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: Literal["gaia.research_loop.candidate.v1"] = CANDIDATE_SCHEMA
    task_id: str
    stage: Stage
    kind: TaskKind
    selected_action: str
    override_rationale: str | None = None
    payload: dict[str, Any]

    def validate_against_actions(
        self,
        *,
        recommended_action: str,
        allowed_actions: list[str],
    ) -> None:
        if self.selected_action not in allowed_actions:
            raise ValueError(f"selected_action {self.selected_action!r} is not allowed")
        if (
            self.selected_action != recommended_action
            and not self.override_rationale
        ):
            raise ValueError("override_rationale is required when overriding recommendation")
```

- [ ] **Step 4: Verify schema tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_schemas.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Type and lint the new module**

Run:

```bash
uv run mypy gaia/research_loop tests/research_loop
uv run ruff check gaia/research_loop tests/research_loop
uv run ruff format --check gaia/research_loop tests/research_loop
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gaia/research_loop/__init__.py gaia/research_loop/schemas.py tests/research_loop/__init__.py tests/research_loop/test_schemas.py
git commit -m "feat(research-loop): add protocol schemas"
```

---

## Task 2: Storage, Event Log, and State Rebuild

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Create: `gaia/research_loop/storage.py`
- Test: `tests/research_loop/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create tests for canonical layout, event append, and rebuild:

```python
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

    assert state.schema == "gaia.research_loop.state.v1"
    assert state.latest_task_by_stage["explore"].endswith("task-1.json")
    assert state.latest_artifact_by_stage["explore"].endswith("scope.json")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_storage.py -q
```

Expected: fail because `storage.py` and `ResearchLoopEvent` do not exist.

- [ ] **Step 3: Add state and event schemas**

Extend `gaia/research_loop/schemas.py` with:

```python
from datetime import UTC, datetime

STATE_SCHEMA = "gaia.research_loop.state.v1"


def utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class ResearchLoopEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: Literal["gaia.research_loop.event.v1"] = "gaia.research_loop.event.v1"
    created_at: str = Field(default_factory=utcnow)
    event_type: str
    stage: Stage | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ResearchLoopState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: Literal["gaia.research_loop.state.v1"] = STATE_SCHEMA
    phase: str = "idle"
    latest_task_by_stage: dict[str, str] = Field(default_factory=dict)
    latest_artifact_by_stage: dict[str, str] = Field(default_factory=dict)
    last_validation_error: dict[str, Any] | None = None
```

- [ ] **Step 4: Implement storage helpers**

Create `gaia/research_loop/storage.py` with path helpers:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.research_loop.schemas import ResearchLoopEvent, ResearchLoopState, Stage


@dataclass(frozen=True)
class ResearchLoopPaths:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_event(
    paths: ResearchLoopPaths,
    *,
    event_type: str,
    stage: Stage | None,
    data: dict[str, Any],
) -> ResearchLoopEvent:
    event = ResearchLoopEvent(event_type=event_type, stage=stage, data=data)
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    with paths.events.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    return event


def load_events(paths: ResearchLoopPaths) -> list[ResearchLoopEvent]:
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
    write_json(paths.state, state.model_dump(mode="json"))
    return state
```

- [ ] **Step 5: Verify storage tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_storage.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Run schema and storage tests together**

Run:

```bash
uv run pytest tests/research_loop/test_schemas.py tests/research_loop/test_storage.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop/schemas.py gaia/research_loop/storage.py tests/research_loop/test_storage.py
git commit -m "feat(research-loop): add storage and event log"
```

---

## Task 3: `gaia-research-loop status`

**Files:**

- Create: `gaia/research_loop/engine.py`
- Create: `gaia/research_loop/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/research_loop/test_cli_status.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/research_loop/test_cli_status.py`:

```python
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_status_initializes_empty_loop(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["status", str(tmp_path), "--json"])

    assert result.exit_code == 0
    assert '"phase": "idle"' in result.stdout
    assert (tmp_path / ".gaia" / "research_loop" / "state.json").exists()


def test_status_human_output_names_next_command(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["status", str(tmp_path)])

    assert result.exit_code == 0
    assert "Research loop: idle" in result.stdout
    assert "Next: gaia-research-loop next" in result.stdout
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_cli_status.py -q
```

Expected: fail because `gaia.research_loop.cli` does not exist.

- [ ] **Step 3: Implement engine status**

Create `gaia/research_loop/engine.py` with:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia.research_loop.storage import ensure_loop_dirs, load_events, rebuild_state


def status_payload(pkg: str | Path) -> dict[str, Any]:
    paths = ensure_loop_dirs(pkg)
    state = rebuild_state(paths)
    events = load_events(paths)
    return {
        "schema": state.schema,
        "phase": state.phase,
        "root": str(paths.root),
        "latest_task_by_stage": state.latest_task_by_stage,
        "latest_artifact_by_stage": state.latest_artifact_by_stage,
        "event_count": len(events),
        "recommended_next": "gaia-research-loop next",
    }
```

- [ ] **Step 4: Implement CLI and console script**

Create `gaia/research_loop/cli.py`:

```python
from __future__ import annotations

import json

import typer

from gaia.research_loop.engine import status_payload

app = typer.Typer(
    name="gaia-research-loop",
    help="Gaia Research Loop — agent-facing Explore -> Assess protocol.",
    no_args_is_help=True,
)

_PKG_ARG = typer.Argument(..., help="Knowledge-package path.")
_JSON_OPT = typer.Option(False, "--json", help="Emit JSON.")


@app.command("status")
def status_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Show or rebuild research loop state."""
    payload = status_payload(pkg)
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Research loop: {payload['phase']}")
    typer.echo(f"Root: {payload['root']}")
    typer.echo(f"Events: {payload['event_count']}")
    typer.echo(f"Next: {payload['recommended_next']} {pkg}")
```

Modify `pyproject.toml`:

```toml
[project.scripts]
gaia = "gaia.cli.main:app"
gaia-lkm-explore = "gaia.lkm_explorer.client.cli:app"
gaia-research-loop = "gaia.research_loop.cli:app"
```

- [ ] **Step 5: Verify CLI tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_cli_status.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Verify installed script help**

Run:

```bash
uv run gaia-research-loop --help
uv run gaia-research-loop status /tmp/gaia-research-loop-smoke --json
```

Expected: help lists `status`; JSON output contains `"phase": "idle"`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml gaia/research_loop/engine.py gaia/research_loop/cli.py tests/research_loop/test_cli_status.py
git commit -m "feat(research-loop): add status cli"
```

---

## Task 4: `next` for Scope and Query Planning

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Create: `gaia/research_loop/tasks.py`
- Modify: `gaia/research_loop/engine.py`
- Modify: `gaia/research_loop/cli.py`
- Test: `tests/research_loop/test_next_submit.py`

- [ ] **Step 1: Write failing `next` tests**

Add to `tests/research_loop/test_next_submit.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_next_emits_scope_task_for_empty_loop(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["recommended_action"] == "submit_scope"
    task_path = Path(payload["task_path"])
    assert task_path.exists()
    task = json.loads(task_path.read_text(encoding="utf-8"))
    assert task["kind"] == "scope"
    assert task["output_contract"]["title"] == "ScopeCandidatePayload"
    assert task["submit_command"].startswith("gaia-research-loop submit")


def test_next_emits_query_plan_after_scope_artifact(tmp_path: Path) -> None:
    runner = CliRunner()
    scope_dir = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    scope_dir.mkdir(parents=True)
    (scope_dir / "scope.json").write_text(
        json.dumps({"kind": "scope", "seed_question": "aspirin primary prevention"}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["recommended_action"] == "submit_query_plan"
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["kind"] == "query_plan"
    assert "Plan the next LKM searches" in task["objective"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py -q
```

Expected: fail because `next` command and task builders do not exist.

- [ ] **Step 3: Add payload schemas**

Extend `schemas.py` with `ScopeCandidatePayload` and `QueryPlanCandidatePayload`:

```python
class ScopeCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_question: str
    domain_profile: str | None = None
    scope_dimensions: dict[str, list[str]] = Field(default_factory=dict)
    search_budget: int = 5


class PlannedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    purpose: str
    expected_evidence_family: str | None = None
    source_ref: EvidenceRef | None = None


class QueryPlanCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[PlannedQuery]
    rationale: str
```

- [ ] **Step 4: Implement task builders**

Create `gaia/research_loop/tasks.py` with:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia.research_loop.schemas import (
    EvidenceRef,
    QueryPlanCandidatePayload,
    ResearchLoopTask,
    ScopeCandidatePayload,
    TaskKind,
)
from gaia.research_loop.storage import ResearchLoopPaths, write_json


def _task_path(paths: ResearchLoopPaths, task_id: str) -> Path:
    return paths.explore_tasks / f"{task_id}.json"


def build_scope_task(paths: ResearchLoopPaths) -> tuple[ResearchLoopTask, Path]:
    task_id = "task-scope-0001"
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.SCOPE,
        objective="Turn the seed research question into a structured exploration scope.",
        inputs={"pkg": str(paths.pkg)},
        instructions=[
            "Identify the seed question and any obvious scope dimensions.",
            "Keep this lightweight; do not assess evidence yet.",
        ],
        allowed_actions=["submit_scope", "stop"],
        recommended_action="submit_scope",
        output_contract=ScopeCandidatePayload.model_json_schema(),
        allowed_refs=[],
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "scope",
            "selected_action": "submit_scope",
            "payload": {"seed_question": "example topic", "search_budget": 3},
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def build_query_plan_task(paths: ResearchLoopPaths, scope: dict[str, Any]) -> tuple[ResearchLoopTask, Path]:
    task_id = "task-query-plan-0001"
    task = ResearchLoopTask(
        task_id=task_id,
        stage="explore",
        kind=TaskKind.QUERY_PLAN,
        objective="Plan the next LKM searches from the current scope and coverage.",
        inputs={"scope": scope},
        instructions=[
            "Propose a small set of LKM search queries.",
            "Prefer breadth-first coverage over deep paper analysis.",
        ],
        allowed_actions=["submit_query_plan", "stop"],
        recommended_action="submit_query_plan",
        output_contract=QueryPlanCandidatePayload.model_json_schema(),
        allowed_refs=[EvidenceRef(kind="scope", id="scope")],
        minimal_example={
            "task_id": task_id,
            "stage": "explore",
            "kind": "query_plan",
            "selected_action": "submit_query_plan",
            "payload": {
                "queries": [{"query": "example query", "purpose": "cover one evidence family"}],
                "rationale": "Tiny shape example only.",
            },
        },
        submit_command=f"gaia-research-loop submit {paths.pkg} <candidate.json>",
    )
    return task, _task_path(paths, task_id)


def write_task(task: ResearchLoopTask, path: Path) -> None:
    write_json(path, task.model_dump(mode="json"))
```

- [ ] **Step 5: Implement `next` engine and CLI**

Add `next_payload` to `engine.py`:

```python
from gaia.research_loop.storage import read_json, write_json
from gaia.research_loop.tasks import build_query_plan_task, build_scope_task, write_task


def next_payload(pkg: str | Path) -> dict[str, Any]:
    paths = ensure_loop_dirs(pkg)
    scope_path = paths.explore_artifacts / "scope.json"
    if scope_path.exists():
        task, task_path = build_query_plan_task(paths, read_json(scope_path))
    else:
        task, task_path = build_scope_task(paths)
    write_task(task, task_path)
    append_event(
        paths,
        event_type="task_emitted",
        stage=task.stage,
        data={"task_id": task.task_id, "kind": task.kind.value, "task_path": str(task_path)},
    )
    rebuild_state(paths)
    return {
        "recommended_action": task.recommended_action,
        "allowed_actions": task.allowed_actions,
        "task_path": str(task_path),
        "submit_command": task.submit_command,
        "rationale": task.objective,
    }
```

Add CLI command:

```python
from gaia.research_loop.engine import next_payload, status_payload


@app.command("next")
def next_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit the next task envelope."""
    payload = next_payload(pkg)
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Recommended: {payload['recommended_action']}")
    typer.echo(f"Task: {payload['task_path']}")
    typer.echo(f"Submit: {payload['submit_command']}")
```

- [ ] **Step 6: Verify `next` tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop/schemas.py gaia/research_loop/tasks.py gaia/research_loop/engine.py gaia/research_loop/cli.py tests/research_loop/test_next_submit.py
git commit -m "feat(research-loop): emit scope and query tasks"
```

---

## Task 4A: Independently Callable Task Primitives

**Files:**

- Modify: `gaia/research_loop/cli.py`
- Modify: `gaia/research_loop/tasks.py`
- Test: `tests/research_loop/test_next_submit.py`

- [ ] **Step 1: Add failing primitive CLI tests**

Append to `tests/research_loop/test_next_submit.py`:

```python
def test_task_scope_primitive_writes_scope_task(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["task", "scope", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["recommended_action"] == "submit_scope"
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["kind"] == "scope"
    assert task["submit_command"].startswith("gaia-research-loop submit")


def test_task_query_plan_primitive_uses_existing_scope(tmp_path: Path) -> None:
    runner = CliRunner()
    scope_dir = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    scope_dir.mkdir(parents=True)
    (scope_dir / "scope.json").write_text(
        json.dumps({"seed_question": "aspirin primary prevention"}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["task", "query-plan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["kind"] == "query_plan"
    assert task["inputs"]["scope"]["seed_question"] == "aspirin primary prevention"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py::test_task_scope_primitive_writes_scope_task tests/research_loop/test_next_submit.py::test_task_query_plan_primitive_uses_existing_scope -q
```

Expected: fail because the `task` CLI group does not exist.

- [ ] **Step 3: Add primitive engine helper**

Add a helper in `engine.py`:

```python
def emit_task(pkg: str | Path, *, kind: TaskKind) -> dict[str, Any]:
    paths = ensure_loop_dirs(pkg)
    if kind == TaskKind.SCOPE:
        task, task_path = build_scope_task(paths)
    elif kind == TaskKind.QUERY_PLAN:
        scope_path = paths.explore_artifacts / "scope.json"
        if not scope_path.exists():
            raise FileNotFoundError("scope.json is required for query-plan task")
        task, task_path = build_query_plan_task(paths, read_json(scope_path))
    else:
        raise ValueError(f"Primitive task {kind.value} is not implemented yet")
    write_task(task, task_path)
    append_event(
        paths,
        event_type="task_emitted",
        stage=task.stage,
        data={"task_id": task.task_id, "kind": task.kind.value, "task_path": str(task_path)},
    )
    rebuild_state(paths)
    return {
        "recommended_action": task.recommended_action,
        "allowed_actions": task.allowed_actions,
        "task_path": str(task_path),
        "submit_command": task.submit_command,
        "rationale": task.objective,
    }
```

Change `next_payload` to call `emit_task` instead of duplicating task emission
logic.

- [ ] **Step 4: Add `task` sub-app**

In `cli.py`:

```python
from gaia.research_loop.schemas import TaskKind

task_app = typer.Typer(help="Emit one task envelope without running the full loop.")
app.add_typer(task_app, name="task")


def _echo_task_payload(payload: dict[str, Any], json_out: bool) -> None:
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Recommended: {payload['recommended_action']}")
    typer.echo(f"Task: {payload['task_path']}")
    typer.echo(f"Submit: {payload['submit_command']}")


@task_app.command("scope")
def task_scope_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a scope task envelope without consulting loop state."""
    _echo_task_payload(emit_task(pkg, kind=TaskKind.SCOPE), json_out)


@task_app.command("query-plan")
def task_query_plan_command(pkg: str = _PKG_ARG, json_out: bool = _JSON_OPT) -> None:
    """Emit a query planning task envelope from the current scope artifact."""
    _echo_task_payload(emit_task(pkg, kind=TaskKind.QUERY_PLAN), json_out)
```

- [ ] **Step 5: Verify primitive tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py::test_task_scope_primitive_writes_scope_task tests/research_loop/test_next_submit.py::test_task_query_plan_primitive_uses_existing_scope -q
```

Expected: both pass.

- [ ] **Step 6: Verify orchestration still works**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py::test_next_emits_scope_task_for_empty_loop tests/research_loop/test_next_submit.py::test_next_emits_query_plan_after_scope_artifact -q
```

Expected: both pass; `next` and primitive commands share the same task builders.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop/cli.py gaia/research_loop/engine.py tests/research_loop/test_next_submit.py
git commit -m "feat(research-loop): expose task primitives"
```

---

## Task 5: `submit` Validation and Repair Context

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Modify: `gaia/research_loop/storage.py`
- Modify: `gaia/research_loop/engine.py`
- Modify: `gaia/research_loop/cli.py`
- Test: `tests/research_loop/test_next_submit.py`

- [ ] **Step 1: Add failing submit tests**

Append:

```python
def test_submit_scope_writes_scope_artifact(tmp_path: Path) -> None:
    runner = CliRunner()
    next_result = runner.invoke(app, ["next", str(tmp_path), "--json"])
    task_path = Path(json.loads(next_result.stdout)["task_path"])
    task = json.loads(task_path.read_text(encoding="utf-8"))
    candidate_path = tmp_path / "scope-candidate.json"
    candidate_path.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "explore",
                "kind": "scope",
                "selected_action": "submit_scope",
                "payload": {
                    "seed_question": "aspirin primary prevention",
                    "domain_profile": "clinical",
                    "scope_dimensions": {"outcome": ["MI", "major bleeding"]},
                    "search_budget": 4,
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["submit", str(tmp_path), str(candidate_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "accepted"
    scope_artifact = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts" / "scope.json"
    assert json.loads(scope_artifact.read_text(encoding="utf-8"))["seed_question"] == (
        "aspirin primary prevention"
    )


def test_submit_invalid_candidate_records_repair_context(tmp_path: Path) -> None:
    runner = CliRunner()
    next_result = runner.invoke(app, ["next", str(tmp_path), "--json"])
    task_path = Path(json.loads(next_result.stdout)["task_path"])
    task = json.loads(task_path.read_text(encoding="utf-8"))
    bad_candidate = tmp_path / "bad.json"
    bad_candidate.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "explore",
                "kind": "scope",
                "selected_action": "submit_scope",
                "payload": {"search_budget": 4},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["submit", str(tmp_path), str(bad_candidate), "--json"])
    assert result.exit_code == 1

    repair_result = runner.invoke(app, ["next", str(tmp_path), "--json"])
    repair_task = json.loads(Path(json.loads(repair_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    assert repair_task["repair_context"]["failed_candidate_path"].endswith("bad.json")
    assert "seed_question" in json.dumps(repair_task["repair_context"]["errors"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py -q
```

Expected: fail because `submit` does not exist.

- [ ] **Step 3: Implement task lookup and candidate persistence**

Add helpers in `storage.py`:

```python
def find_task(paths: ResearchLoopPaths, task_id: str) -> Path:
    for directory in [paths.explore_tasks, paths.assess_tasks]:
        candidate = directory / f"{task_id}.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No task envelope found for {task_id}")


def candidate_destination(paths: ResearchLoopPaths, stage: str, candidate_path: Path) -> Path:
    directory = paths.explore_candidates if stage == "explore" else paths.assess_candidates
    return directory / candidate_path.name
```

- [ ] **Step 4: Implement validation and artifact writing**

Add `submit_candidate` to `engine.py`:

```python
from pydantic import ValidationError

from gaia.research_loop.schemas import (
    CandidateEnvelope,
    QueryPlanCandidatePayload,
    ResearchLoopTask,
    ScopeCandidatePayload,
    TaskKind,
)
from gaia.research_loop.storage import candidate_destination, find_task


def _payload_model_for(kind: TaskKind) -> type[ScopeCandidatePayload] | type[QueryPlanCandidatePayload]:
    if kind == TaskKind.SCOPE:
        return ScopeCandidatePayload
    if kind == TaskKind.QUERY_PLAN:
        return QueryPlanCandidatePayload
    raise ValueError(f"No payload validator for {kind.value}")


def submit_candidate(pkg: str | Path, candidate_path: str | Path) -> dict[str, Any]:
    paths = ensure_loop_dirs(pkg)
    source_path = Path(candidate_path).resolve()
    try:
        candidate = CandidateEnvelope.model_validate_json(source_path.read_text(encoding="utf-8"))
        task_path = find_task(paths, candidate.task_id)
        task = ResearchLoopTask.model_validate_json(task_path.read_text(encoding="utf-8"))
        if candidate.stage != task.stage or candidate.kind != task.kind:
            raise ValueError("candidate stage/kind does not match task")
        candidate.validate_against_actions(
            recommended_action=task.recommended_action,
            allowed_actions=task.allowed_actions,
        )
        payload_model = _payload_model_for(task.kind)
        payload = payload_model.model_validate(candidate.payload)
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        errors = exc.errors() if isinstance(exc, ValidationError) else [{"msg": str(exc)}]
        _record_validation_failure(paths, source_path, errors)
        raise

    copied_candidate = candidate_destination(paths, candidate.stage, source_path)
    write_json(copied_candidate, candidate.model_dump(mode="json"))
    if task.kind == TaskKind.SCOPE:
        artifact_path = paths.explore_artifacts / "scope.json"
        write_json(artifact_path, payload.model_dump(mode="json"))
    elif task.kind == TaskKind.QUERY_PLAN:
        artifact_path = paths.explore_artifacts / "query_plan.json"
        write_json(artifact_path, payload.model_dump(mode="json"))
    append_event(
        paths,
        event_type="candidate_submitted",
        stage=candidate.stage,
        data={"task_id": candidate.task_id, "candidate_path": str(copied_candidate)},
    )
    rebuild_state(paths)
    return {"status": "accepted", "artifact_path": str(artifact_path)}
```

Add `_record_validation_failure`:

```python
def _record_validation_failure(
    paths: ResearchLoopPaths,
    failed_candidate_path: Path,
    errors: list[dict[str, Any]],
) -> None:
    state = rebuild_state(paths)
    state.last_validation_error = {
        "failed_candidate_path": str(failed_candidate_path),
        "errors": errors,
        "instruction": "Repair the candidate JSON so it satisfies the same task contract.",
    }
    write_json(paths.state, state.model_dump(mode="json"))
    append_event(
        paths,
        event_type="validation_failed",
        stage=None,
        data=state.last_validation_error,
    )
```

Modify `next_payload` so when `state.last_validation_error` exists, it re-emits
the same task with `repair_context` populated instead of advancing.

- [ ] **Step 5: Add CLI command**

In `cli.py`:

```python
from gaia.research_loop.engine import next_payload, status_payload, submit_candidate


@app.command("submit")
def submit_command(
    pkg: str = _PKG_ARG,
    candidate: str = typer.Argument(..., help="Candidate JSON path."),
    json_out: bool = _JSON_OPT,
) -> None:
    """Validate and submit a candidate JSON file."""
    try:
        payload = submit_candidate(pkg, candidate)
    except Exception as exc:
        if json_out:
            typer.echo(json.dumps({"status": "rejected", "error": str(exc)}, indent=2))
        else:
            typer.echo(f"Rejected: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(f"Accepted: {payload['artifact_path']}")
```

- [ ] **Step 6: Verify submit and repair tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop tests/research_loop/test_next_submit.py
git commit -m "feat(research-loop): validate candidate submission"
```

---

## Task 6: Query Plan to Mechanical Search Execution Task

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Modify: `gaia/research_loop/tasks.py`
- Modify: `gaia/research_loop/engine.py`
- Test: `tests/research_loop/test_next_submit.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_next_after_query_plan_emits_search_execution(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["next", str(tmp_path), "--json"])
    scope_candidate = tmp_path / "scope.json"
    scope_candidate.write_text(
        json.dumps(
            {
                "task_id": "task-scope-0001",
                "stage": "explore",
                "kind": "scope",
                "selected_action": "submit_scope",
                "payload": {"seed_question": "aspirin primary prevention", "search_budget": 2},
            }
        ),
        encoding="utf-8",
    )
    runner.invoke(app, ["submit", str(tmp_path), str(scope_candidate), "--json"])
    runner.invoke(app, ["next", str(tmp_path), "--json"])
    query_candidate = tmp_path / "query-plan.json"
    query_candidate.write_text(
        json.dumps(
            {
                "task_id": "task-query-plan-0001",
                "stage": "explore",
                "kind": "query_plan",
                "selected_action": "submit_query_plan",
                "payload": {
                    "queries": [{"query": "aspirin primary prevention bleeding", "purpose": "harms"}],
                    "rationale": "Need harm evidence.",
                },
            }
        ),
        encoding="utf-8",
    )
    runner.invoke(app, ["submit", str(tmp_path), str(query_candidate), "--json"])

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    payload = json.loads(result.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["kind"] == "search_execution"
    assert "gaia search lkm knowledge" in task["inputs"]["commands"][0]["command"]
    assert task["inputs"]["commands"][0]["output_path"].endswith(".json")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py::test_next_after_query_plan_emits_search_execution -q
```

Expected: fail because `next` does not advance past query plan.

- [ ] **Step 3: Add search execution payload schema**

In `schemas.py`:

```python
class SearchResultPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    path: str


class SearchExecutionCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[SearchResultPath]
```

- [ ] **Step 4: Add task builder**

In `tasks.py`, add `build_search_execution_task(paths, query_plan)` that creates
commands such as:

```python
command = f"gaia search lkm knowledge {query_text!r} --json > {output_path}"
```

The task input item should include:

```json
{
  "query": "aspirin primary prevention bleeding",
  "command": "gaia search lkm knowledge 'aspirin primary prevention bleeding' --json > ...",
  "output_path": ".gaia/research_loop/explore/artifacts/raw-search-0001-0.json"
}
```

- [ ] **Step 5: Update `next` routing**

Routing order:

```text
if last_validation_error: repair same task
elif no scope artifact: scope
elif no query_plan artifact: query_plan
elif landscape artifact exists and no focuses artifact: focus_synthesis
elif no raw_search_manifest artifact: search_execution
else: landscape
```

- [ ] **Step 6: Verify targeted test passes**

Run:

```bash
uv run pytest tests/research_loop/test_next_submit.py::test_next_after_query_plan_emits_search_execution -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop tests/research_loop/test_next_submit.py
git commit -m "feat(research-loop): emit search execution tasks"
```

---

## Task 7: LKM Landscape Artifact Under Research Loop

**Files:**

- Create: `gaia/research_loop/lkm_adapter.py`
- Modify: `gaia/research_loop/engine.py`
- Test: `tests/research_loop/test_lkm_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create fixture-based tests using `tests/lkm_explorer/fixtures/lkm_search_free_fall.json`:

```python
from __future__ import annotations

from pathlib import Path

from gaia.research_loop.lkm_adapter import build_landscape_from_raw_results


def test_build_landscape_from_raw_results_extracts_paper_leads(tmp_path: Path) -> None:
    fixture = Path("tests/lkm_explorer/fixtures/lkm_search_free_fall.json")

    artifact = build_landscape_from_raw_results(
        pkg=tmp_path,
        raw_results=[("free fall", fixture)],
        round_number=0,
    )

    assert artifact["schema"] == "gaia.research_loop.artifact.v1"
    assert artifact["kind"] == "landscape"
    assert artifact["round"] == 0
    assert artifact["raw_results"][0]["query"] == "free fall"
    assert isinstance(artifact["paper_leads"], list)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
uv run pytest tests/research_loop/test_lkm_adapter.py -q
```

Expected: fail because adapter does not exist.

- [ ] **Step 3: Implement adapter**

Create `lkm_adapter.py` with a small adapter around existing landscape parser.
If `gaia.lkm_explorer.engine.landscape.build_landscape` accepts the raw fixture
shape directly, use it. If not, implement only the minimal extraction needed for
saved LKM search envelopes and keep the function pure.

Required output shape:

```python
{
    "schema": "gaia.research_loop.artifact.v1",
    "kind": "landscape",
    "round": round_number,
    "raw_results": [{"query": query, "path": str(path)}],
    "paper_leads": [...],
    "coverage": {"paper_count": len(paper_leads)},
}
```

- [ ] **Step 4: Add submit path for search execution**

When a valid `SearchExecutionCandidatePayload` is submitted:

1. Validate every `path` exists.
2. Write `raw_search_manifest.json`.
3. Build and write `landscape-0000.json`.
4. Append `artifact_written`.

- [ ] **Step 5: Verify adapter and CLI path**

Run:

```bash
uv run pytest tests/research_loop/test_lkm_adapter.py tests/research_loop/test_next_submit.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gaia/research_loop/lkm_adapter.py gaia/research_loop/engine.py tests/research_loop/test_lkm_adapter.py tests/research_loop/test_next_submit.py
git commit -m "feat(research-loop): build lkm landscape artifacts"
```

---

## Task 8: Focus Synthesis Task and Explore Gate

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Modify: `gaia/research_loop/tasks.py`
- Modify: `gaia/research_loop/engine.py`
- Test: `tests/research_loop/test_explore_gate.py`

- [ ] **Step 1: Write failing focus and gate tests**

Create `tests/research_loop/test_explore_gate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_focus_synthesis_candidate_writes_focuses(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "scope.json").write_text(json.dumps({"seed_question": "aspirin"}), encoding="utf-8")
    (artifacts / "query_plan.json").write_text(json.dumps({"queries": []}), encoding="utf-8")
    (artifacts / "landscape-0000.json").write_text(
        json.dumps(
            {
                "kind": "landscape",
                "paper_leads": [{"paper_id": "P1", "title": "Aspirin trial"}],
            }
        ),
        encoding="utf-8",
    )

    next_result = runner.invoke(app, ["next", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    assert task["kind"] == "focus_synthesis"
    candidate = tmp_path / "focuses.json"
    candidate.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "explore",
                "kind": "focus_synthesis",
                "selected_action": "submit_focuses",
                "payload": {
                    "focuses": [
                        {
                            "focus_id": "focus-net-benefit",
                            "research_question": "Does benefit outweigh bleeding risk?",
                            "why_it_matters": "It determines clinical recommendation.",
                            "evidence_refs": [{"kind": "paper", "id": "P1"}],
                            "coverage_status": "ready_for_assess",
                            "ready_for_assess": True,
                            "recommended_assess_mode": "evidence_table",
                        }
                    ],
                    "selection": {
                        "selected_focus_ids": ["focus-net-benefit"],
                        "selection_rationale": "Ready and grounded.",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])
    assert submit.exit_code == 0
    focuses = json.loads((artifacts / "focuses.json").read_text(encoding="utf-8"))
    assert focuses["focuses"][0]["focus_id"] == "focus-net-benefit"


def test_gate_passes_when_selected_focus_ready(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "focuses.json").write_text(
        json.dumps(
            {
                "focuses": [
                    {
                        "focus_id": "focus-net-benefit",
                        "ready_for_assess": True,
                        "evidence_refs": [{"kind": "paper", "id": "P1"}],
                    }
                ],
                "selection": {"selected_focus_ids": ["focus-net-benefit"]},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["gate", str(tmp_path), "--stage", "explore", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_explore_gate.py -q
```

Expected: fail because focus payloads and gate are not implemented.

- [ ] **Step 3: Implement focus schemas and task**

Add `FocusCandidatePayload`, `FocusRecord`, and `FocusSelection` models.
Build a `focus_synthesis` task whose `allowed_refs` come from `landscape`
paper leads and LKM node ids.

- [ ] **Step 4: Implement Explore gate**

Gate status:

```text
pass   = selected ready focus has at least one grounded evidence ref
revise = no selected focus, no ready focus, or ungrounded refs
```

Write gate report to:

```text
.gaia/research_loop/explore/artifacts/explore_gate.json
```

- [ ] **Step 5: Verify Explore gate tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_explore_gate.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add gaia/research_loop tests/research_loop/test_explore_gate.py
git commit -m "feat(research-loop): add focus synthesis gate"
```

---

## Task 9: Assessment Context, Evidence Diagnosis, and Assess Gate

**Files:**

- Modify: `gaia/research_loop/schemas.py`
- Modify: `gaia/research_loop/tasks.py`
- Modify: `gaia/research_loop/engine.py`
- Test: `tests/research_loop/test_assess_gate.py`

- [ ] **Step 1: Write failing assess tests**

Create `tests/research_loop/test_assess_gate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_next_after_explore_gate_emits_assessment_context(tmp_path: Path) -> None:
    runner = CliRunner()
    explore = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    explore.mkdir(parents=True)
    (explore / "focuses.json").write_text(
        json.dumps(
            {
                "focuses": [
                    {
                        "focus_id": "focus-net-benefit",
                        "research_question": "Does benefit outweigh bleeding risk?",
                        "ready_for_assess": True,
                        "evidence_refs": [{"kind": "paper", "id": "P1"}],
                    }
                ],
                "selection": {"selected_focus_ids": ["focus-net-benefit"]},
            }
        ),
        encoding="utf-8",
    )
    (explore / "explore_gate.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    task = json.loads(Path(json.loads(result.stdout)["task_path"]).read_text(encoding="utf-8"))
    assert task["stage"] == "assess"
    assert task["kind"] == "assessment_context"


def test_assess_gate_passes_grounded_evidence_diagnosis(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "evidence_diagnosis.json").write_text(
        json.dumps(
            {
                "focus_id": "focus-net-benefit",
                "evidence_items": [{"id": "e1", "refs": [{"kind": "paper", "id": "P1"}]}],
                "contradictions_or_tensions": [],
                "limitations": ["Sparse example."],
                "gap_map": [{"gap_id": "g1", "description": "Need subgroup evidence."}],
                "next_tests": [{"gap_id": "g1", "test": "Search subgroup RCTs."}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["gate", str(tmp_path), "--stage", "assess", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "pass"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/research_loop/test_assess_gate.py -q
```

Expected: fail because Assess routing and gate are not implemented.

- [ ] **Step 3: Implement assess schemas**

Add:

- `AssessmentContextPayload`
- `EvidenceItem`
- `EvidenceDiagnosisPayload`
- `GapMapEntry`
- `NextTest`

Require refs on evidence items and require `next_tests[].gap_id` to refer to an
existing gap.

- [ ] **Step 4: Implement assess task routing**

After Explore gate pass:

```text
if no assessment_context artifact: emit assessment_context task
elif no evidence_diagnosis artifact: emit evidence_diagnosis task
else: recommend assess_gate
```

- [ ] **Step 5: Implement Assess gate**

Gate status:

```text
pass   = diagnosis has evidence items, limitations, gap map, and next tests tied to gaps
revise = missing refs, missing gaps, missing limitations, or dangling next_tests
```

- [ ] **Step 6: Verify assess tests pass**

Run:

```bash
uv run pytest tests/research_loop/test_assess_gate.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add gaia/research_loop tests/research_loop/test_assess_gate.py
git commit -m "feat(research-loop): add assessment loop gate"
```

---

## Task 10: Thin Skill Template

**Files:**

- Create: `gaia/_skills/gaia-research-loop/SKILL.md`
- Test: `tests/research_loop/test_cli_status.py`

- [ ] **Step 1: Add test that skill exists and stays thin**

Append:

```python
def test_research_loop_skill_exists_and_is_thin() -> None:
    path = Path("gaia/_skills/gaia-research-loop/SKILL.md")

    text = path.read_text(encoding="utf-8")

    assert "gaia-research-loop next" in text
    assert "output_contract" in text
    assert "Do not hardcode" in text
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
uv run pytest tests/research_loop/test_cli_status.py::test_research_loop_skill_exists_and_is_thin -q
```

Expected: fail because the skill file does not exist.

- [ ] **Step 3: Create skill**

Create `gaia/_skills/gaia-research-loop/SKILL.md`:

```markdown
---
name: gaia-research-loop
description: Run Gaia's agent-facing Explore -> Assess research loop through self-contained task envelopes.
---

# Gaia Research Loop

Use this when a user asks to run or continue a Gaia research loop.

1. Run `gaia-research-loop next <pkg> --json`.
2. Open the returned task envelope.
3. Follow the task's `instructions`.
4. If the task requires reasoning, use your own model.
5. Write candidate JSON matching `output_contract`.
6. Run the task's `submit_command`.
7. If validation fails, run `gaia-research-loop next <pkg> --json` and repair
   the same task using `repair_context`.
8. Repeat until `gaia-research-loop status <pkg>` or `gaia-research-loop gate`
   reports that the loop is done.

Do not hardcode query planning, focus synthesis, or assessment schemas. The task
envelope is the contract.
```

- [ ] **Step 4: Verify skill test passes**

Run:

```bash
uv run pytest tests/research_loop/test_cli_status.py::test_research_loop_skill_exists_and_is_thin -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add gaia/_skills/gaia-research-loop/SKILL.md tests/research_loop/test_cli_status.py
git commit -m "docs(research-loop): add thin agent skill"
```

---

## Task 11: End-to-End Smoke and Final Gates

**Files:**

- Test-only changes if needed: `tests/research_loop/test_next_submit.py`
- No production files unless smoke reveals a bug.

- [ ] **Step 1: Add a tiny E2E smoke test**

Add one test that runs:

```text
status -> next(scope) -> submit(scope) -> next(query_plan) -> submit(query_plan)
-> next(search_execution)
```

Use a saved raw fixture instead of live network for the landscape transition.

- [ ] **Step 2: Run research loop test suite**

Run:

```bash
uv run pytest tests/research_loop -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lkm explorer regression slice**

Run:

```bash
uv run pytest tests/lkm_explorer -q
```

Expected: all tests pass; this verifies new code did not break the existing
Explore engine.

- [ ] **Step 4: Run typecheck and lint**

Run:

```bash
uv run mypy gaia tests
uv run ruff check gaia tests
uv run ruff format --check gaia tests
```

Expected: all pass.

- [ ] **Step 5: Run CLI smoke manually**

Run:

```bash
uv run gaia-research-loop --help
uv run gaia-research-loop status /tmp/gaia-research-loop-smoke --json
uv run gaia-research-loop next /tmp/gaia-research-loop-smoke --json
```

Expected:

- help lists `status`, `next`, `submit`, and `gate`;
- status initializes `.gaia/research_loop`;
- next emits a task envelope path and a submit command.

- [ ] **Step 6: Run PR-gate slice**

Run:

```bash
uv run pytest -n auto -v -m "pr_gate and not slow"
```

Expected: pass. If failures are unrelated to this branch, record them with
exact test names and output before deciding whether to fix or defer.

- [ ] **Step 7: Final commit**

```bash
git add gaia tests pyproject.toml
git commit -m "test(research-loop): cover agent protocol smoke"
```

---

## Verification Matrix

| Requirement | Verification |
| --- | --- |
| New `gaia-research-loop` CLI exists | `uv run gaia-research-loop --help` |
| Canonical `.gaia/research_loop/` layout | `tests/research_loop/test_storage.py` |
| `state.json` rebuilds from artifacts | `test_rebuild_state_indexes_latest_task_and_artifact` |
| `events.jsonl` records actions | `test_append_event_writes_jsonl` |
| Task envelope has output contract and example | `test_task_embeds_contract_and_minimal_example` |
| Candidate validates selected action and override rationale | `test_candidate_selected_action_must_be_allowed_or_recommended`, `test_candidate_override_requires_rationale` |
| `next` emits first task | `test_next_emits_scope_task_for_empty_loop` |
| Task primitives can be called without full loop orchestration | `test_task_scope_primitive_writes_scope_task`, `test_task_query_plan_primitive_uses_existing_scope` |
| Scope submission writes artifact | `test_submit_scope_writes_scope_artifact` |
| Validation failure returns repairable same task | `test_submit_invalid_candidate_records_repair_context` |
| Query planning is agent task | `test_next_emits_query_plan_after_scope_artifact` |
| Search execution is mechanical | `test_next_after_query_plan_emits_search_execution` |
| Raw LKM results become landscape | `test_build_landscape_from_raw_results_extracts_paper_leads` |
| Focus synthesis is agent task | `test_focus_synthesis_candidate_writes_focuses` |
| Explore gate passes selected ready focus | `test_gate_passes_when_selected_focus_ready` |
| Assess context starts from selected focus | `test_next_after_explore_gate_emits_assessment_context` |
| Assess gate checks diagnosis/gaps/tests | `test_assess_gate_passes_grounded_evidence_diagnosis` |
| Thin skill does not hardcode schemas | `test_research_loop_skill_exists_and_is_thin` |

## Self-Review Notes

- Spec coverage: This plan covers the CLI, independently callable task
  primitives, canonical storage, state/event model, task envelope, repair
  context, query planning, search execution, landscape, focus synthesis,
  Explore gate, assessment context, evidence diagnosis, Assess gate, thin skill,
  and verification.
- Scope boundary: The plan stops before `Propose`, `Discover`, `Merge`, live LKM
  networking, built-in LLM providers, and claim merge.
- Risk: The exact LKM raw search fixture shape may require a small adapter
  adjustment in Task 7. The test requires only the stable output contract, not a
  specific internal parser.
