from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.research_loop.cli import app


def test_focus_synthesis_candidate_writes_focuses(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "scope.json").write_text(
        json.dumps({"seed_question": "aspirin"}), encoding="utf-8"
    )
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

    next_result = runner.invoke(app, ["task", "focus-synthesis", str(tmp_path), "--json"])
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


def test_focus_synthesis_rejects_ungrounded_refs(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "landscape-0000.json").write_text(
        json.dumps({"kind": "landscape", "paper_leads": [{"paper_id": "P1"}]}),
        encoding="utf-8",
    )
    next_result = runner.invoke(app, ["task", "focus-synthesis", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    candidate = tmp_path / "focuses-ungrounded.json"
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
                            "evidence_refs": [{"kind": "paper", "id": "P2"}],
                            "ready_for_assess": True,
                        }
                    ],
                    "selection": {"selected_focus_ids": ["focus-net-benefit"]},
                },
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])

    assert submit.exit_code == 1
    assert "not allowed by task" in submit.stdout


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


def test_needs_more_landscape_routes_to_next_query_round(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "scope.json").write_text(
        json.dumps({"seed_question": "aspirin", "search_budget": 2}), encoding="utf-8"
    )
    (artifacts / "query_plan.json").write_text(
        json.dumps(
            {
                "queries": [{"query": "aspirin primary prevention", "purpose": "broad"}],
                "rationale": "Round 0.",
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "query_plan-0000.json").write_text(
        (artifacts / "query_plan.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (artifacts / "landscape-0000.json").write_text(
        json.dumps({"kind": "landscape", "paper_leads": [{"paper_id": "P1"}]}),
        encoding="utf-8",
    )
    next_result = runner.invoke(app, ["next", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    candidate = tmp_path / "focus-needs-more.json"
    candidate.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "explore",
                "kind": "focus_synthesis",
                "selected_action": "needs_more_landscape",
                "override_rationale": "Need subgroup coverage before assessment.",
                "payload": {
                    "focuses": [
                        {
                            "focus_id": "focus-diabetes",
                            "research_question": "Does aspirin help diabetes patients?",
                            "evidence_refs": [{"kind": "paper", "id": "P1"}],
                            "coverage_status": "needs_more_landscape",
                            "ready_for_assess": False,
                        }
                    ],
                    "next_queries": [
                        {
                            "query": "aspirin primary prevention diabetes bleeding",
                            "purpose": "diabetes subgroup",
                        }
                    ],
                    "continue_rationale": "Diabetes subgroup is under-covered.",
                },
            }
        ),
        encoding="utf-8",
    )
    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])
    assert submit.exit_code == 0

    second_next = runner.invoke(app, ["next", str(tmp_path), "--json"])

    payload = json.loads(second_next.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert payload["recommended_action"] == "submit_query_plan"
    assert task["task_id"] == "task-query-plan-0002"
    assert task["inputs"]["round"] == 1
    assert task["inputs"]["prior_focus_synthesis"]["next_queries"][0]["query"].startswith(
        "aspirin primary prevention diabetes"
    )


def test_second_round_search_writes_numbered_landscape(tmp_path: Path) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "query_plan-0001.json").write_text(
        json.dumps(
            {
                "queries": [{"query": "free fall", "purpose": "fixture"}],
                "rationale": "Round 1.",
            }
        ),
        encoding="utf-8",
    )
    next_result = runner.invoke(app, ["task", "search-execution", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    raw_path = Path("tests/lkm_explorer/fixtures/lkm_search_free_fall.json").resolve()
    candidate = tmp_path / "search-results-round-1.json"
    candidate.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "explore",
                "kind": "search_execution",
                "selected_action": "submit_search_results",
                "payload": {"results": [{"query": "free fall", "path": str(raw_path)}]},
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])

    assert submit.exit_code == 0
    assert (artifacts / "landscape-0001.json").exists()
    assert (artifacts / "raw_search_manifest-0001.json").exists()


def test_second_round_focus_synthesis_can_use_cumulative_landscape_refs(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "landscape-0000.json").write_text(
        json.dumps({"kind": "landscape", "paper_leads": [{"paper_id": "P0"}]}),
        encoding="utf-8",
    )
    (artifacts / "landscape-0001.json").write_text(
        json.dumps({"kind": "landscape", "paper_leads": [{"paper_id": "P1"}]}),
        encoding="utf-8",
    )

    next_result = runner.invoke(app, ["task", "focus-synthesis", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    candidate = tmp_path / "focuses-round-1.json"
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
                            "focus_id": "focus-cross-round",
                            "research_question": "What focus needs both rounds?",
                            "evidence_refs": [
                                {"kind": "paper", "id": "P0"},
                                {"kind": "paper", "id": "P1"},
                            ],
                            "ready_for_assess": True,
                        }
                    ],
                    "selection": {"selected_focus_ids": ["focus-cross-round"]},
                },
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])

    assert submit.exit_code == 0
    allowed_refs = {(ref["kind"], ref["id"]) for ref in task["allowed_refs"]}
    assert allowed_refs == {("paper", "P0"), ("paper", "P1")}


def test_first_round_query_plan_writes_numbered_artifact_and_alias(tmp_path: Path) -> None:
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
                "payload": {"seed_question": "free fall", "search_budget": 1},
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
                    "queries": [{"query": "free fall", "purpose": "fixture"}],
                    "rationale": "Round 0.",
                },
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(query_candidate), "--json"])

    artifacts = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    assert submit.exit_code == 0
    assert (artifacts / "query_plan-0000.json").exists()
    assert (artifacts / "query_plan.json").exists()
