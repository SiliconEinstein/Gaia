"""Tests for the gaia-lkm-explore orchestrator turn state machine (CLIENT.md).

Two layers:

* fast unit tests of the phase transitions that need no compile (a synthetic map
  + a stubbed graph resolver), and
* an integration test that runs a full IDLE → survey → checkpoint cycle against
  the hand-authored ``examples/galileo-v0-5-gaia`` fixture, compiling + inferring
  through the SDK exactly as a real turn would (no LKM needed).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gaia.engine.exploration import handoff
from gaia.engine.exploration.handoff import SurveyResult, SurveyTask
from gaia.engine.exploration.state import (
    TURN_PHASE_AWAITING_SURVEY,
    TURN_PHASE_IDLE,
    Contact,
    ExplorationMap,
    Policy,
    doctrine_policy,
    exploration_dir,
    load_map,
    save_map,
)
from gaia.explore_client import orchestrator
from gaia.explore_client.orchestrator import OrchestratorError, run_turn

pytestmark = pytest.mark.pr_gate


# --------------------------------------------------------------------------- #
# fast unit tests — no compile                                                #
# --------------------------------------------------------------------------- #


def _init_map(pkg: Path, *, doctrine: str = "Surveyor", seed_qid: str | None = None) -> None:
    seeds = []
    if seed_qid is not None:
        seeds = [{"kind": "claim", "text": seed_qid, "qid": seed_qid}]
    save_map(pkg, ExplorationMap(seeds=seeds, policy=doctrine_policy(doctrine)))


def test_turn_without_map_raises(tmp_path: Path):
    with pytest.raises(OrchestratorError):
        run_turn(tmp_path)


def test_idle_round0_no_ir_emits_seed_survey_task(tmp_path: Path, monkeypatch):
    """IDLE on a fresh init with no compiled IR → a round-0 seed-survey task."""
    _init_map(tmp_path, seed_qid="example:pkg::seed")
    # No compiled IR yet — force the graph resolver to report "uncompiled".
    monkeypatch.setattr(orchestrator, "_resolve_graph", lambda _pkg: None)

    outcome = run_turn(tmp_path)

    assert outcome.action == "emitted_task"
    assert outcome.phase_before == TURN_PHASE_IDLE
    assert outcome.phase_after == TURN_PHASE_AWAITING_SURVEY
    assert outcome.seed_survey is True
    assert outcome.round == 0

    # The map advanced to AWAITING_SURVEY and persisted it.
    assert load_map(tmp_path).turn_phase == TURN_PHASE_AWAITING_SURVEY

    # A well-formed, self-contained task file landed.
    tpath = handoff.task_path(exploration_dir(tmp_path), 0)
    assert Path(tpath).exists()
    task = SurveyTask.read(tpath)
    assert task.round == 0
    assert task.doctrine == "Surveyor"
    assert task.seed_survey is True
    assert task.contacts  # the seed itself
    assert task.result_path.endswith("turn-0.result.json")
    # The instructions are baked in (no skill) — they carry the survey procedure
    # and the re-invocation handshake.
    assert "Integrity contract" in task.instructions
    assert "gaia-lkm-explore observe" in task.instructions
    assert "gaia-lkm-explore turn" in task.instructions


def test_idle_with_frontier_emits_ranked_task(tmp_path: Path, monkeypatch):
    """IDLE with a non-empty frontier → a frontier task of the top-k contacts."""
    m = ExplorationMap(round=2, policy=Policy(doctrine="Surveyor", budget_k=2))
    m.frontier = [
        Contact(
            id="ct_a",
            ref={"kind": "qid", "value": "example:pkg::Foo"},
            sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
            score=0.9,
            status="open",
        ),
        Contact(
            id="ct_b",
            ref={"kind": "qid", "value": "example:pkg::Bar"},
            sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
            score=0.1,
            status="open",
        ),
    ]
    save_map(tmp_path, m)

    # Stub the SDK seams so no compile/IR is needed: a graph object that exists,
    # an empty joint view (no new contacts, no edges), and empty beliefs. The
    # existing open contacts on the map are what get ranked into the task.
    from gaia.engine.exploration.frontier import JointView

    monkeypatch.setattr(orchestrator, "_resolve_graph", lambda _pkg: object())
    monkeypatch.setattr(orchestrator, "_joint_view", lambda _pkg, _g: JointView())
    monkeypatch.setattr(orchestrator, "_load_beliefs", lambda _pkg: {})

    outcome = run_turn(tmp_path)

    assert outcome.action == "emitted_task"
    assert outcome.seed_survey is False
    # budget_k=2 and the higher score sorts first.
    assert outcome.contacts == ["ct_a", "ct_b"]
    task = SurveyTask.read(handoff.task_path(exploration_dir(tmp_path), 2))
    assert [c.id for c in task.contacts] == ["ct_a", "ct_b"]
    assert task.contacts[0].survey_brief  # a per-contact brief was composed


def test_emitted_task_hides_belief_but_ranks_by_it(tmp_path: Path, monkeypatch):
    """Build 11 steer 4: the agent-facing task drops belief; ranking keeps it.

    The engine ranks the frontier by a belief-weighted ``score`` (high
    ``belief_entropy`` first), but every emitted ``TaskContact`` must have NO
    ``belief_entropy`` in ``score_features`` and NO raw ``score`` — while the
    contact ORDER still reflects the internal belief ranking.
    """
    m = ExplorationMap(round=1, policy=Policy(doctrine="Surveyor", budget_k=2))
    # ct_hi has the higher belief_entropy AND the higher score; ct_lo lower both.
    m.frontier = [
        Contact(
            id="ct_lo",
            ref={"kind": "qid", "value": "example:pkg::Lo"},
            sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
            score=0.10,
            score_features={"belief_entropy": 0.10, "closeness_to_seed": 0.2},
            status="open",
        ),
        Contact(
            id="ct_hi",
            ref={"kind": "qid", "value": "example:pkg::Hi"},
            sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
            score=0.90,
            score_features={"belief_entropy": 0.90, "closeness_to_seed": 0.2},
            status="open",
        ),
    ]
    save_map(tmp_path, m)

    from gaia.engine.exploration.frontier import JointView

    monkeypatch.setattr(orchestrator, "_resolve_graph", lambda _pkg: object())
    monkeypatch.setattr(orchestrator, "_joint_view", lambda _pkg, _g: JointView())
    monkeypatch.setattr(orchestrator, "_load_beliefs", lambda _pkg: {})
    # No-op the scorer so the pre-set belief-weighted scores/features survive
    # (the real scorer would recompute them; here we assert on known values).
    monkeypatch.setattr(orchestrator, "score_frontier", lambda *_a, **_k: None)

    outcome = run_turn(tmp_path)

    # Ranking still reflects belief: the higher belief-weighted score comes first.
    assert outcome.contacts == ["ct_hi", "ct_lo"]
    task = SurveyTask.read(handoff.task_path(exploration_dir(tmp_path), 1))
    assert [c.id for c in task.contacts] == ["ct_hi", "ct_lo"]
    for tc in task.contacts:
        # No belief surfaced: belief_entropy stripped, raw score hidden.
        assert "belief_entropy" not in tc.score_features
        assert tc.score is None
        # Non-belief signals survive.
        assert "closeness_to_seed" in tc.score_features


def test_idle_turn_loads_obligations_and_boosts_matching_contact(tmp_path: Path, monkeypatch):
    """Build 12 (CLIENT.md steer 3): a live turn boosts the obligation-matching contact.

    The turn loads open obligations from .gaia/inquiry/state.json, scores
    obligation_pressure, and the contact that discharges an open obligation
    outranks the one that does not — while obligation_pressure is agent-visible
    and belief stays stripped.
    """
    from gaia.engine.exploration.frontier import JointView
    from gaia.engine.inquiry.state import (
        InquiryState,
        SyntheticObligation,
        save_state,
    )

    match_qid = "example:pkg::Match"
    plain_qid = "example:pkg::Plain"
    seed_qid = "example:pkg::seed"

    # Two sibling contacts off the same source: identical save-game state, only
    # the obligation differs. The REAL scorer runs (not stubbed) so the boost is
    # genuine. No obligation -> equal scores -> id tie-break would order them.
    m = ExplorationMap(round=1, policy=doctrine_policy("Surveyor"))
    m.frontier = [
        Contact(
            id="ct_plain",
            ref={"kind": "qid", "value": plain_qid},
            sources=[{"qid": seed_qid, "edge": "depends_on"}],
            status="open",
        ),
        Contact(
            id="ct_match",
            ref={"kind": "qid", "value": match_qid},
            sources=[{"qid": seed_qid, "edge": "depends_on"}],
            status="open",
        ),
    ]
    save_map(tmp_path, m)

    # An open synthetic obligation about the Match contact, persisted via the
    # real inquiry state loader's writer (no hand-parsed JSON).
    save_state(
        tmp_path,
        InquiryState(
            synthetic_obligations=[
                SyntheticObligation(
                    qid="oblig_x", target_qid=match_qid, content="show the keystone holds"
                )
            ]
        ),
    )

    monkeypatch.setattr(orchestrator, "_resolve_graph", lambda _pkg: object())
    monkeypatch.setattr(orchestrator, "_joint_view", lambda _pkg, _g: JointView())
    monkeypatch.setattr(orchestrator, "_load_beliefs", lambda _pkg: {})

    outcome = run_turn(tmp_path)

    # The obligation-matching contact ranks FIRST despite the lexical tie-break
    # that would otherwise put ct_match after ct_plain.
    assert outcome.contacts == ["ct_match", "ct_plain"]
    task = SurveyTask.read(handoff.task_path(exploration_dir(tmp_path), 1))
    assert [c.id for c in task.contacts] == ["ct_match", "ct_plain"]
    top = task.contacts[0]
    # obligation_pressure IS in the agent-facing features (steer 3), belief is NOT
    # (steer 4).
    assert top.score_features["obligation_pressure"] == 1.0
    assert "belief_entropy" not in top.score_features
    # The non-matching sibling carries pressure 0.0.
    assert task.contacts[1].score_features["obligation_pressure"] == 0.0


def test_load_open_obligations_empty_without_state(tmp_path: Path):
    """No inquiry state -> empty obligation list (graceful)."""
    assert orchestrator._load_open_obligations(tmp_path) == []


def test_contact_brief_does_not_surface_belief_entropy():
    """Build 11 steer 4: a high-belief_entropy contact's brief hides belief.

    Belief stays internal to the engine (Jaynes' robot) — even a dominant
    ``belief_entropy`` signal must NOT produce an "undecided territory" hint, and
    with no other strong signal the brief carries no signal sentence at all.
    """
    contact = Contact(
        id="ct_a",
        ref={"kind": "qid", "value": "example:pkg::Foo"},
        sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
        score=0.8,
        score_features={
            "belief_entropy": 0.9,
            "closeness_to_seed": 0.1,
            "new_territory": 0.0,
        },
        status="open",
    )
    brief = orchestrator._contact_survey_brief(contact)
    # The belief-derived "undecided territory" hint is gone.
    assert "undecided" not in brief
    # No belief surfaced and no other strong signal → no signal sentence.
    assert "Signal:" not in brief
    # Query anchoring is still present.
    assert "example:pkg::Foo" in brief
    assert "Anchor" in brief
    # The weak non-belief signals are not dumped either.
    assert "on-topic" not in brief
    assert "fresh unexplored" not in brief


def test_contact_brief_lkm_leads_with_pull_line_and_hint():
    """An lkm contact's brief keeps the pull line and folds in a strong signal."""
    contact = Contact(
        id="ct_p",
        ref={"kind": "lkm", "value": "paper-42"},
        sources=[{"qid": "example:pkg::seed", "edge": "lkm_related"}],
        score=0.7,
        score_features={"new_territory": 0.95, "belief_entropy": 0.1},
        meta={"title": "On Falling Bodies"},
        status="open",
    )
    brief = orchestrator._contact_survey_brief(contact)
    assert "gaia pkg add --lkm-paper paper-42" in brief
    assert "fresh unexplored territory" in brief
    assert "Anchor" in brief


def test_contact_brief_no_strong_signal_omits_hint():
    """All-weak score_features → no signal sentence appended."""
    contact = Contact(
        id="ct_w",
        ref={"kind": "qid", "value": "example:pkg::Bar"},
        sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
        score=0.2,
        score_features={"belief_entropy": 0.2, "closeness_to_seed": 0.3, "new_territory": 0.1},
        status="open",
    )
    brief = orchestrator._contact_survey_brief(contact)
    assert "Signal:" not in brief


def test_awaiting_survey_without_result_is_noop(tmp_path: Path):
    """AWAITING_SURVEY with no result manifest → report the outstanding task."""
    m = ExplorationMap(round=1, turn_phase=TURN_PHASE_AWAITING_SURVEY)
    save_map(tmp_path, m)

    outcome = run_turn(tmp_path)

    assert outcome.action == "awaiting_survey"
    assert outcome.phase_after == TURN_PHASE_AWAITING_SURVEY
    # Phase unchanged on disk.
    assert load_map(tmp_path).turn_phase == TURN_PHASE_AWAITING_SURVEY


def test_checkpoint_inferred_from_result_manifest(tmp_path: Path, monkeypatch):
    """A result manifest's presence drives the checkpoint, regardless of phase.

    Compile/infer is stubbed (the integration test exercises the real SDK path);
    here we assert the state-machine bookkeeping: discoveries computed, surveyed
    recorded, round advanced, phase back to IDLE.
    """
    m = ExplorationMap(round=1, turn_phase=TURN_PHASE_AWAITING_SURVEY)
    m.frontier = [
        Contact(
            id="ct_a",
            ref={"kind": "qid", "value": "example:pkg::Foo"},
            sources=[{"qid": "example:pkg::seed", "edge": "depends_on"}],
            status="open",
        )
    ]
    save_map(tmp_path, m)

    # The agent's result manifest for this round.
    res = SurveyResult(surveyed_qids=["example:pkg::Foo"])
    res.write(handoff.result_path(exploration_dir(tmp_path), 1))

    monkeypatch.setattr(orchestrator, "_compile_and_infer", lambda _pkg: None)
    monkeypatch.setattr(orchestrator, "_resolve_graph", lambda _pkg: object())
    monkeypatch.setattr(orchestrator, "_load_beliefs", lambda _pkg: {})
    # compute_discoveries is imported inside _checkpoint; patch it at its source.
    import gaia.engine.exploration.discoveries as disc_mod

    monkeypatch.setattr(disc_mod, "compute_discoveries", lambda *_a, **_k: [])

    outcome = run_turn(tmp_path)

    assert outcome.action == "checkpointed"
    assert outcome.phase_after == TURN_PHASE_IDLE
    assert outcome.surveyed == ["example:pkg::Foo"]

    reloaded = load_map(tmp_path)
    assert reloaded.turn_phase == TURN_PHASE_IDLE
    assert reloaded.round == 2  # advanced
    # The surveyed qid promoted the matching open contact.
    assert reloaded.surveyed["example:pkg::Foo"].promoted_from_contact == "ct_a"
    assert reloaded.find_contact("ct_a").status == "surveyed"


# --------------------------------------------------------------------------- #
# integration — full cycle against the galileo fixture (real SDK compile)     #
# --------------------------------------------------------------------------- #


def _example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "galileo-v0-5-gaia"


@pytest.fixture
def galileo_pkg(tmp_path: Path) -> Path:
    src = _example_root()
    assert src.is_dir(), f"galileo fixture not found at {src}"
    pkg = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(src, pkg)
    return pkg


def _galileo_qid(label: str) -> str:
    return f"example:galileo_v0_5::{label}"


def test_full_turn_cycle_against_galileo(galileo_pkg: Path):
    """Init → IDLE turn (emit task) → survey result → checkpoint turn (real SDK)."""
    # init the map with a resolved seed QID.
    _init_map(galileo_pkg, doctrine="Surveyor", seed_qid=_galileo_qid("aristotle_model"))

    # Turn 1 (IDLE): emit a survey task. No compiled IR yet → seed survey.
    out1 = run_turn(galileo_pkg)
    assert out1.action == "emitted_task"
    assert load_map(galileo_pkg).turn_phase == TURN_PHASE_AWAITING_SURVEY
    task = SurveyTask.read(out1.task_path)
    assert task.instructions

    # Re-invoking with no result manifest is a no-op.
    out_noop = run_turn(galileo_pkg)
    assert out_noop.action == "awaiting_survey"

    # The "agent" writes a result manifest (heavy state already in the package —
    # the galileo fixture is fully authored, so no real survey is needed).
    SurveyResult(surveyed_qids=[_galileo_qid("aristotle_model")]).write(out1.result_path)

    # Turn 2 (checkpoint): real compile + infer + round via the SDK.
    out2 = run_turn(galileo_pkg)
    assert out2.action == "checkpointed"
    assert out2.phase_after == TURN_PHASE_IDLE

    # The SDK compile/infer actually wrote the engine artifacts.
    assert (galileo_pkg / ".gaia" / "ir.json").exists()
    assert (galileo_pkg / ".gaia" / "beliefs.json").exists()

    reloaded = load_map(galileo_pkg)
    assert reloaded.turn_phase == TURN_PHASE_IDLE
    assert reloaded.round == 1
    assert _galileo_qid("aristotle_model") in reloaded.surveyed

    # A round record was appended.
    from gaia.engine.exploration.state import read_rounds

    rounds = read_rounds(galileo_pkg)
    assert [r["round"] for r in rounds] == [0]
