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
