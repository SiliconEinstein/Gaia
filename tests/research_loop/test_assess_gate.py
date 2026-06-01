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


def test_next_auto_gates_ready_focus_and_enters_assess(tmp_path: Path) -> None:
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

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    payload = json.loads(result.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["stage"] == "assess"
    assert task["kind"] == "assessment_context"
    assert (explore / "explore_gate.json").exists()


def test_task_assessment_context_primitive_uses_selected_focus(tmp_path: Path) -> None:
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

    result = runner.invoke(app, ["task", "assessment-context", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["stage"] == "assess"
    assert task["kind"] == "assessment_context"
    assert task["inputs"]["focus"]["focus_id"] == "focus-net-benefit"


def test_task_assessment_context_includes_selected_ref_snippets(tmp_path: Path) -> None:
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
    (explore / "landscape-0000.json").write_text(
        json.dumps(
            {
                "kind": "landscape",
                "paper_leads": [{"paper_id": "P1"}],
                "evidence_snippets": [
                    {
                        "paper_id": "P1",
                        "lkm_node_id": "lkm:claim-1",
                        "kind": "claim",
                        "content": "Aspirin increased major bleeding without clear net benefit.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["task", "assessment-context", str(tmp_path), "--json"])

    assert result.exit_code == 0
    task = json.loads(Path(json.loads(result.stdout)["task_path"]).read_text(encoding="utf-8"))
    assert task["inputs"]["evidence_context"][0]["content"].startswith("Aspirin increased")


def test_task_evidence_diagnosis_primitive_uses_assessment_context(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["task", "evidence-diagnosis", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    task = json.loads(Path(payload["task_path"]).read_text(encoding="utf-8"))
    assert task["stage"] == "assess"
    assert task["kind"] == "evidence_diagnosis"
    assert task["allowed_refs"] == [{"kind": "paper", "id": "P1", "role": None}]


def test_task_evidence_diagnosis_includes_assessment_ref_snippets(tmp_path: Path) -> None:
    runner = CliRunner()
    explore = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    explore.mkdir(parents=True)
    assess.mkdir(parents=True)
    (explore / "landscape-0000.json").write_text(
        json.dumps(
            {
                "kind": "landscape",
                "evidence_snippets": [
                    {
                        "paper_id": "P1",
                        "lkm_node_id": "lkm:claim-1",
                        "kind": "claim",
                        "content": "Aspirin reduced events but increased bleeding.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["task", "evidence-diagnosis", str(tmp_path), "--json"])

    assert result.exit_code == 0
    task = json.loads(Path(json.loads(result.stdout)["task_path"]).read_text(encoding="utf-8"))
    assert task["inputs"]["evidence_context"][0]["content"].startswith("Aspirin reduced")


def test_assess_gate_passes_grounded_evidence_diagnosis(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )
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


def test_next_auto_gates_complete_assess_and_returns_done(tmp_path: Path) -> None:
    runner = CliRunner()
    explore = tmp_path / ".gaia" / "research_loop" / "explore" / "artifacts"
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    explore.mkdir(parents=True)
    assess.mkdir(parents=True)
    (explore / "explore_gate.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )
    (assess / "evidence_diagnosis.json").write_text(
        json.dumps(
            {
                "focus_id": "focus-net-benefit",
                "evidence_items": [{"id": "e1", "refs": [{"kind": "paper", "id": "P1"}]}],
                "limitations": ["Sparse example."],
                "gap_map": [{"gap_id": "g1", "description": "Need subgroup evidence."}],
                "next_tests": [{"gap_id": "g1", "test": "Search subgroup RCTs."}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["next", str(tmp_path), "--json"])

    payload = json.loads(result.stdout)
    assert payload["recommended_action"] == "done"
    assert payload["rationale"] == "Explore and Assess gates passed."
    assert (assess / "assess_gate.json").exists()


def test_assess_gate_revises_when_focus_id_is_not_preserved(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )
    (assess / "evidence_diagnosis.json").write_text(
        json.dumps(
            {
                "focus_id": "different-focus",
                "evidence_items": [{"id": "e1", "refs": [{"kind": "paper", "id": "P1"}]}],
                "limitations": ["Sparse example."],
                "gap_map": [{"gap_id": "g1", "description": "Need subgroup evidence."}],
                "next_tests": [{"gap_id": "g1", "test": "Search subgroup RCTs."}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["gate", str(tmp_path), "--stage", "assess", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "revise"


def test_assess_gate_revises_when_tension_lacks_two_links(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )
    (assess / "evidence_diagnosis.json").write_text(
        json.dumps(
            {
                "focus_id": "focus-net-benefit",
                "evidence_items": [{"id": "e1", "refs": [{"kind": "paper", "id": "P1"}]}],
                "contradictions_or_tensions": [
                    {
                        "id": "t1",
                        "summary": "Only one linked evidence item.",
                        "evidence_item_ids": ["e1"],
                    }
                ],
                "limitations": ["Sparse example."],
                "gap_map": [{"gap_id": "g1", "description": "Need subgroup evidence."}],
                "next_tests": [{"gap_id": "g1", "test": "Search subgroup RCTs."}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["gate", str(tmp_path), "--stage", "assess", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "revise"


def test_evidence_diagnosis_rejects_ungrounded_refs(tmp_path: Path) -> None:
    runner = CliRunner()
    assess = tmp_path / ".gaia" / "research_loop" / "assess" / "artifacts"
    assess.mkdir(parents=True)
    (assess / "assessment_context.json").write_text(
        json.dumps(
            {"focus_id": "focus-net-benefit", "evidence_refs": [{"kind": "paper", "id": "P1"}]}
        ),
        encoding="utf-8",
    )
    next_result = runner.invoke(app, ["task", "evidence-diagnosis", str(tmp_path), "--json"])
    task = json.loads(Path(json.loads(next_result.stdout)["task_path"]).read_text(encoding="utf-8"))
    candidate = tmp_path / "diagnosis-ungrounded.json"
    candidate.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "stage": "assess",
                "kind": "evidence_diagnosis",
                "selected_action": "submit_evidence_diagnosis",
                "payload": {
                    "focus_id": "focus-net-benefit",
                    "evidence_items": [{"id": "e1", "refs": [{"kind": "paper", "id": "P2"}]}],
                    "limitations": ["Sparse example."],
                    "gap_map": [{"gap_id": "g1", "description": "Need subgroup evidence."}],
                    "next_tests": [{"gap_id": "g1", "test": "Search subgroup RCTs."}],
                },
            }
        ),
        encoding="utf-8",
    )

    submit = runner.invoke(app, ["submit", str(tmp_path), str(candidate), "--json"])

    assert submit.exit_code == 1
    assert "not allowed by task" in submit.stdout
