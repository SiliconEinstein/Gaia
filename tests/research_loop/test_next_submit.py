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
