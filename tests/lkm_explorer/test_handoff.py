"""Unit tests for gaia.lkm_explorer.engine.handoff (CLIENT.md "Envelopes")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gaia.lkm_explorer.engine.handoff import (
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
        "kind",
        "contacts",
        "bridge_worklist",
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
    res = SurveyResult(surveyed_qids=["lkm:pkg::Claim7", "lkm:pkg::Claim8"])
    p = res.write(result_path(tmp_path, 2))
    assert p.exists()
    loaded = SurveyResult.read(p)
    assert loaded == res
    assert loaded.surveyed_qids == ["lkm:pkg::Claim7", "lkm:pkg::Claim8"]


def test_result_defaults_are_minimal():
    res = SurveyResult()
    assert res.surveyed_qids == []


def test_result_tolerates_legacy_fields(tmp_path: Path):
    """A legacy 3-field result (build <=8) still reads — extras are ignored."""
    p = result_path(tmp_path, 3)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"surveyed_qids": ["lkm:pkg::Claim9"], "observed": true, "notes": "y"}',
        encoding="utf-8",
    )
    loaded = SurveyResult.read(p)
    assert loaded.surveyed_qids == ["lkm:pkg::Claim9"]
    # The retired keys are tolerated and dropped (pydantic default extra="ignore").
    assert not hasattr(loaded, "observed")
    assert not hasattr(loaded, "notes")


def test_task_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        SurveyTask.model_validate({"round": 1})


# --------------------------------------------------------------------------- #
# Phase 2 (EXPANSION.md §3.D / §3.E): kind discriminator + bridge worklist      #
# --------------------------------------------------------------------------- #


def test_task_kind_defaults_to_expand():
    task = SurveyTask(pkg="p", round=1, doctrine="Surveyor", budget_k=5)
    assert task.kind == "expand"
    assert task.bridge_worklist == []


def test_consolidate_task_roundtrips_with_islands(tmp_path: Path):
    from gaia.lkm_explorer.engine.handoff import IslandBrief

    task = SurveyTask(
        pkg="p",
        round=2,
        doctrine="Diplomat",
        budget_k=5,
        kind="consolidate",
        bridge_worklist=[
            IslandBrief(
                member_qids=["lkm:pkg::b", "lkm:pkg::c"],
                brief="b: ...; c: ...",
                reopened=True,
                bridge_hint="lkm:pkg::b",
            )
        ],
        instructions="bridge or ratify",
    )
    p = task.write(task_path(tmp_path, 2))
    back = SurveyTask.read(p)
    assert back.kind == "consolidate"
    assert len(back.bridge_worklist) == 1
    assert back.bridge_worklist[0].member_qids == ["lkm:pkg::b", "lkm:pkg::c"]
    assert back.bridge_worklist[0].reopened is True
    assert back.bridge_worklist[0].bridge_hint == "lkm:pkg::b"


def test_old_task_without_kind_reads_as_expand(tmp_path: Path):
    legacy = {
        "pkg": "p",
        "round": 0,
        "doctrine": "Surveyor",
        "budget_k": 5,
        "contacts": [],
        "instructions": "x",
        "result_path": "r",
        # NB: no kind / bridge_worklist.
    }
    p = task_path(tmp_path, 0)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(legacy), encoding="utf-8")
    task = SurveyTask.read(p)
    assert task.kind == "expand"
    assert task.bridge_worklist == []


def test_result_carries_ratified_and_back_compat(tmp_path: Path):
    from gaia.lkm_explorer.engine.handoff import RatifiedSeparationResult

    res = SurveyResult(
        surveyed_qids=["lkm:pkg::x"],
        ratified=[
            RatifiedSeparationResult(member_qids=["lkm:pkg::b"], rationale="separate domain")
        ],
    )
    p = res.write(result_path(tmp_path, 1))
    back = SurveyResult.read(p)
    assert back.surveyed_qids == ["lkm:pkg::x"]
    assert len(back.ratified) == 1
    assert back.ratified[0].member_qids == ["lkm:pkg::b"]


def test_old_result_without_ratified_reads_empty(tmp_path: Path):
    legacy = {"surveyed_qids": ["lkm:pkg::x"], "notes": "ignored", "observed": ["ignored"]}
    p = result_path(tmp_path, 0)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(legacy), encoding="utf-8")
    res = SurveyResult.read(p)
    assert res.surveyed_qids == ["lkm:pkg::x"]
    assert res.ratified == []
