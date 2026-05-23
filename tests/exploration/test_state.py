"""Unit tests for gaia.engine.exploration.state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.engine.exploration.state import (
    DOCTRINE_PRESETS,
    EXPLORATION_SCHEMA_VERSION,
    POLICY_WEIGHT_KEYS,
    TURN_PHASE_AWAITING_CHECKPOINT,
    TURN_PHASE_AWAITING_SURVEY,
    TURN_PHASE_IDLE,
    Contact,
    ExplorationMap,
    Policy,
    SurveyRecord,
    append_round,
    doctrine_policy,
    exploration_dir,
    load_map,
    mint_contact_id,
    read_rounds,
    save_map,
)


def test_empty_map_roundtrip(tmp_path: Path):
    m = load_map(tmp_path)
    assert m.version == EXPLORATION_SCHEMA_VERSION
    assert m.round == 0
    assert m.surveyed == {}
    assert m.frontier == []
    save_map(tmp_path, m)
    again = load_map(tmp_path)
    # updated_at is refreshed on save, so compare everything else.
    a, b = again.to_dict(), m.to_dict()
    a.pop("updated_at")
    b.pop("updated_at")
    assert a == b


def test_map_persists_surveyed_frontier_and_policy(tmp_path: Path):
    cid = mint_contact_id()
    assert cid.startswith("ct_") and len(cid) == 11
    m = ExplorationMap(
        round=2,
        seeds=[{"kind": "claim", "text": "seed", "qid": "lkm:pkg::Seed1"}],
        policy=Policy(doctrine="Inquisitor", budget_k=3),
    )
    m.surveyed["lkm:pkg::Claim1"] = SurveyRecord(
        qid="lkm:pkg::Claim1",
        survey_round=2,
        lkm_origin={"query": "q", "lkm_node_id": "n1", "retrieved_at": "2026-01-01T00:00:00Z"},
    )
    m.frontier.append(
        Contact(
            id=cid,
            ref={"kind": "qid", "value": "lkm:pkg::Foo"},
            sources=[{"qid": "lkm:pkg::Claim1", "edge": "depends_on"}],
            discovered_round=2,
        )
    )
    save_map(tmp_path, m)

    raw = json.loads((exploration_dir(tmp_path) / "map.json").read_text("utf-8"))
    assert raw["version"] == EXPLORATION_SCHEMA_VERSION
    assert raw["round"] == 2
    assert raw["policy"]["doctrine"] == "Inquisitor"
    assert raw["surveyed"]["lkm:pkg::Claim1"]["survey_round"] == 2
    assert raw["frontier"][0]["ref"]["value"] == "lkm:pkg::Foo"

    reloaded = load_map(tmp_path)
    assert reloaded.round == 2
    assert reloaded.policy.weights == DOCTRINE_PRESETS["Inquisitor"]
    assert reloaded.surveyed["lkm:pkg::Claim1"].lkm_origin["lkm_node_id"] == "n1"
    assert len(reloaded.frontier) == 1
    assert reloaded.frontier[0].id == cid


def test_future_version_rejected(tmp_path: Path):
    exploration_dir(tmp_path).joinpath("map.json").write_text(
        json.dumps({"version": EXPLORATION_SCHEMA_VERSION + 5}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_map(tmp_path)


def test_save_is_atomic_no_tmp_left_behind(tmp_path: Path):
    m = ExplorationMap(round=1)
    save_map(tmp_path, m)
    d = exploration_dir(tmp_path)
    assert (d / "map.json").exists()
    # The tmp scratch file must not survive a successful atomic replace.
    assert not (d / "map.json.tmp").exists()
    assert list(d.glob("*.tmp")) == []


def test_rounds_append_only_and_read(tmp_path: Path):
    p = Policy(doctrine="Surveyor", budget_k=4)
    append_round(
        tmp_path,
        round_index=1,
        policy=p,
        surveyed=["lkm:pkg::Claim7"],
        discoveries=[{"kind": "keystone", "ids": ["lkm:pkg::Claim7"], "note": "high in-degree"}],
        frontier_summary={"open_after": 12, "top_score": 0.71},
        lkm_pulls=3,
    )
    append_round(
        tmp_path,
        round_index=2,
        policy=Policy(doctrine="Inquisitor"),
        surveyed=["lkm:pkg::Claim8"],
    )
    rounds = read_rounds(tmp_path)
    assert [r["round"] for r in rounds] == [1, 2]
    assert rounds[0]["policy"]["doctrine"] == "Surveyor"
    assert rounds[0]["discoveries"][0]["kind"] == "keystone"
    assert rounds[0]["frontier_summary"]["open_after"] == 12
    assert rounds[0]["lkm_pulls"] == 3
    assert rounds[1]["surveyed"] == ["lkm:pkg::Claim8"]


def test_read_rounds_empty(tmp_path: Path):
    assert read_rounds(tmp_path) == []


@pytest.mark.parametrize("doctrine", sorted(DOCTRINE_PRESETS))
def test_doctrine_presets_resolve(doctrine: str):
    pol = doctrine_policy(doctrine, budget_k=7)
    assert pol.doctrine == doctrine
    assert pol.budget_k == 7
    assert set(pol.weights) == set(POLICY_WEIGHT_KEYS)
    assert pol.weights == DOCTRINE_PRESETS[doctrine]
    # The preset is copied, not aliased — mutating the policy must not bleed back.
    pol.weights["w_tension"] = 999.0
    assert DOCTRINE_PRESETS[doctrine]["w_tension"] != 999.0


def test_named_doctrine_autofills_weights():
    pol = Policy(doctrine="Cartographer")
    assert pol.weights == DOCTRINE_PRESETS["Cartographer"]


def test_custom_doctrine_carries_explicit_weights():
    weights = dict.fromkeys(POLICY_WEIGHT_KEYS, 0.5)
    pol = Policy(doctrine="custom", weights=weights)
    assert pol.doctrine == "custom"
    assert pol.weights == weights


def test_custom_doctrine_missing_weights_rejected():
    with pytest.raises(ValueError):
        Policy(doctrine="custom", weights={"w_tension": 1.0})


def test_unknown_doctrine_rejected():
    with pytest.raises(ValueError):
        Policy(doctrine="Bogus")
    with pytest.raises(ValueError):
        doctrine_policy("custom")


def test_invalid_contact_ref_kind_rejected():
    with pytest.raises(ValueError):
        Contact(id="ct_x", ref={"kind": "bogus", "value": "v"})


def test_invalid_contact_status_rejected():
    with pytest.raises(ValueError):
        Contact(id="ct_x", ref={"kind": "qid", "value": "v"}, status="bogus")


def test_invalid_contact_source_edge_rejected():
    with pytest.raises(ValueError):
        Contact(
            id="ct_x",
            ref={"kind": "qid", "value": "v"},
            sources=[{"qid": "q", "edge": "bogus"}],
        )


def test_contact_promotion_bookkeeping(tmp_path: Path):
    cid = mint_contact_id()
    m = ExplorationMap(round=3)
    m.frontier.append(
        Contact(
            id=cid,
            ref={"kind": "qid", "value": "lkm:pkg::Claim7"},
            sources=[{"qid": "lkm:pkg::Claim1", "edge": "depends_on"}],
            discovered_round=3,
            status="open",
        )
    )
    record = m.promote_contact(cid, survey_round=4, lkm_origin={"query": "q"})

    # Contact flips to surveyed (kept, not deleted) ...
    assert m.find_contact(cid).status == "surveyed"
    assert len(m.frontier) == 1
    # ... and a SurveyRecord with promoted_from_contact is added.
    assert record.promoted_from_contact == cid
    assert record.survey_round == 4
    assert m.surveyed["lkm:pkg::Claim7"].promoted_from_contact == cid
    assert m.surveyed["lkm:pkg::Claim7"].lkm_origin == {"query": "q"}

    # Promotion bookkeeping survives a persistence round-trip.
    save_map(tmp_path, m)
    reloaded = load_map(tmp_path)
    assert reloaded.find_contact(cid).status == "surveyed"
    assert reloaded.surveyed["lkm:pkg::Claim7"].promoted_from_contact == cid


def test_promote_unknown_contact_raises():
    m = ExplorationMap()
    with pytest.raises(KeyError):
        m.promote_contact("ct_missing", survey_round=1)


def test_promote_lkm_ref_contact_rejected():
    cid = mint_contact_id()
    m = ExplorationMap()
    m.frontier.append(Contact(id=cid, ref={"kind": "lkm", "value": "lkm_node_42"}))
    with pytest.raises(ValueError):
        m.promote_contact(cid, survey_round=1)


# --------------------------------------------------------------------------- #
# turn_phase (CLIENT.md "Turn state machine")                                 #
# --------------------------------------------------------------------------- #


def test_turn_phase_defaults_to_idle():
    assert ExplorationMap().turn_phase == TURN_PHASE_IDLE


def test_turn_phase_roundtrips(tmp_path: Path):
    m = ExplorationMap(round=1, turn_phase=TURN_PHASE_AWAITING_SURVEY)
    save_map(tmp_path, m)
    raw = json.loads((exploration_dir(tmp_path) / "map.json").read_text("utf-8"))
    assert raw["turn_phase"] == TURN_PHASE_AWAITING_SURVEY
    reloaded = load_map(tmp_path)
    assert reloaded.turn_phase == TURN_PHASE_AWAITING_SURVEY


@pytest.mark.parametrize(
    "phase",
    [TURN_PHASE_IDLE, TURN_PHASE_AWAITING_SURVEY, TURN_PHASE_AWAITING_CHECKPOINT],
)
def test_all_turn_phases_persist(tmp_path: Path, phase: str):
    save_map(tmp_path, ExplorationMap(turn_phase=phase))
    assert load_map(tmp_path).turn_phase == phase


def test_invalid_turn_phase_rejected():
    with pytest.raises(ValueError):
        ExplorationMap(turn_phase="RUNNING")


def test_old_map_without_turn_phase_loads_as_idle(tmp_path: Path):
    # A map.json written before turn_phase existed has no such key — it must
    # load unchanged and default to IDLE (additive, back-compatible schema).
    legacy = {
        "version": EXPLORATION_SCHEMA_VERSION,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "round": 4,
        "seeds": [{"kind": "claim", "text": "s", "qid": "lkm:pkg::Seed1"}],
        "policy": {
            "doctrine": "Surveyor",
            "weights": dict(DOCTRINE_PRESETS["Surveyor"]),
            "budget_k": 5,
        },
        "surveyed": {},
        "frontier": [],
        "stats": {},
        # NB: no "turn_phase" key.
    }
    exploration_dir(tmp_path).joinpath("map.json").write_text(json.dumps(legacy), encoding="utf-8")
    m = load_map(tmp_path)
    assert m.turn_phase == TURN_PHASE_IDLE
    assert m.round == 4
    assert m.policy.doctrine == "Surveyor"
