"""Unit tests for gaia.engine.exploration.handoff (CLIENT.md "Envelopes")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gaia.engine.exploration.handoff import (
    RESULT_FILENAME_TEMPLATE,
    TASK_FILENAME_TEMPLATE,
    SurveyResult,
    SurveyTask,
    TaskContact,
    result_path,
    task_path,
)


def test_task_path_and_result_path(tmp_path: Path):
    assert task_path(tmp_path, 3) == tmp_path / TASK_FILENAME_TEMPLATE.format(round=3)
    assert result_path(tmp_path, 3) == tmp_path / RESULT_FILENAME_TEMPLATE.format(round=3)
    assert task_path(tmp_path, 3).name == "turn-3.task.json"
    assert result_path(tmp_path, 3).name == "turn-3.result.json"


def test_task_roundtrips_full_shape(tmp_path: Path):
    task = SurveyTask(
        pkg="./pkg",
        round=1,
        doctrine="Surveyor",
        budget_k=5,
        contacts=[
            TaskContact(
                id="ct_ab12",
                ref={"kind": "qid", "value": "lkm:pkg::Foo"},
                score=0.71,
                score_features={"belief_entropy": 0.4, "closeness_to_seed": 0.5},
                sources=[{"qid": "lkm:pkg::Claim1", "edge": "depends_on"}],
                survey_brief="survey lkm:pkg::Foo (reached via depends_on)",
            )
        ],
        instructions="Full survey procedure here.",
        result_path=".gaia/exploration/turn-1.result.json",
    )
    p = task.write(task_path(tmp_path, 1))
    assert p.exists()
    # No tmp scratch file survives the atomic replace.
    assert list(Path(p).parent.glob("*.tmp")) == []

    loaded = SurveyTask.read(p)
    assert loaded == task
    assert loaded.contacts[0].ref["value"] == "lkm:pkg::Foo"
    assert loaded.contacts[0].score == 0.71
    assert loaded.result_path.endswith("turn-1.result.json")

    # On-disk JSON matches the documented envelope keys.
    raw = json.loads(p.read_text("utf-8"))
    assert set(raw) == {
        "pkg",
        "round",
        "doctrine",
        "budget_k",
        "contacts",
        "seed_survey",
        "instructions",
        "result_path",
    }
    assert set(raw["contacts"][0]) == {
        "id",
        "ref",
        "score",
        "score_features",
        "sources",
        "survey_brief",
    }


def test_round_zero_seed_survey_task(tmp_path: Path):
    task = SurveyTask(
        pkg="./pkg",
        round=0,
        doctrine="Surveyor",
        budget_k=5,
        seed_survey=True,
        contacts=[],
        instructions="Survey the seed itself.",
        result_path=str(result_path(tmp_path, 0)),
    )
    p = task.write(task_path(tmp_path, 0))
    loaded = SurveyTask.read(p)
    assert loaded.seed_survey is True
    assert loaded.contacts == []


def test_result_roundtrips_minimal(tmp_path: Path):
    res = SurveyResult(
        surveyed_qids=["lkm:pkg::Claim7", "lkm:pkg::Claim8"],
        observed=True,
        notes="surfaced two related papers",
    )
    p = res.write(result_path(tmp_path, 2))
    assert p.exists()
    loaded = SurveyResult.read(p)
    assert loaded == res
    assert loaded.surveyed_qids == ["lkm:pkg::Claim7", "lkm:pkg::Claim8"]
    assert loaded.observed is True


def test_result_defaults_are_minimal():
    res = SurveyResult()
    assert res.surveyed_qids == []
    assert res.observed is False
    assert res.notes == ""


def test_task_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        SurveyTask.model_validate({"round": 1})
