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
    assert (
        json.loads(scope_artifact.read_text(encoding="utf-8"))["seed_question"]
        == "aspirin primary prevention"
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
    repair_task = json.loads(
        Path(json.loads(repair_result.stdout)["task_path"]).read_text(encoding="utf-8")
    )
    assert repair_task["repair_context"]["failed_candidate_path"].endswith("bad.json")
    assert "seed_question" in json.dumps(repair_task["repair_context"]["errors"])


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
                    "queries": [
                        {"query": "aspirin primary prevention bleeding", "purpose": "harms"}
                    ],
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
