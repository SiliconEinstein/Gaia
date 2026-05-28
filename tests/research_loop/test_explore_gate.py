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
