"""Tests for proof state analysis."""

from pathlib import Path

from libs.lang.proof_state import analyze_proof_state
from libs.lang.typst_loader import load_typst_package_v4

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "ir"
GALILEO_V4 = _FIXTURES / "galileo_falling_bodies_v4"
NEWTON_V4 = _FIXTURES / "newton_principia_v4"
DARK_ENERGY_V4 = _FIXTURES / "dark_energy_v4"


def test_constraint_between_members_are_used_as_premise():
    """Claims used only as between members of a constraint should be detected as holes."""
    graph = {
        "nodes": [
            {"name": "A", "type": "claim"},
            {"name": "B", "type": "claim"},
            {"name": "rel", "type": "contradiction"},
        ],
        "factors": [],
        "constraints": [
            {"name": "rel", "type": "contradiction", "between": ["A", "B"]},
        ],
    }
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "A" in hole_names
    assert "B" in hole_names
    # The relation itself should be established, not a hole
    established_names = {d["name"] for d in state["established"]}
    assert "rel" in established_names


def test_standalone_claims_reported():
    """Claims not proven and not referenced should appear in standalone."""
    graph = {
        "nodes": [
            {"name": "orphan", "type": "claim"},
        ],
        "factors": [],
        "constraints": [],
    }
    state = analyze_proof_state(graph)
    standalone_names = {d["name"] for d in state["standalone"]}
    assert "orphan" in standalone_names
    assert len(state["holes"]) == 0


# ── v4 proof state (uses "premises" key) ────────────────────────────────────


def test_v4_established_claims():
    """v4 loader uses 'premises' key; proof_state should still detect established claims."""
    graph = load_typst_package_v4(GALILEO_V4)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "galileo.composite_is_slower" in established
    assert "galileo.composite_is_faster" in established
    assert "galileo.vacuum_prediction" in established


def test_v4_holes_detected():
    """Claims used as premises without proofs should be holes in v4."""
    graph = load_typst_package_v4(GALILEO_V4)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    # aristotle.everyday_observation is now a premise of heavier_falls_faster,
    # but has no reasoning factor concluding it — it's a hole (observation claim)
    assert "aristotle.everyday_observation" in hole_names


def test_v4_settings_are_assumptions():
    graph = load_typst_package_v4(GALILEO_V4)
    state = analyze_proof_state(graph)
    assumption_names = {d["name"] for d in state["assumptions"]}
    assert "setting.thought_experiment_env" in assumption_names


def test_v4_questions_detected():
    graph = load_typst_package_v4(GALILEO_V4)
    state = analyze_proof_state(graph)
    question_names = {d["name"] for d in state["questions"]}
    assert "motivation.main_question" in question_names


def test_v4_relation_nodes_are_established():
    graph = load_typst_package_v4(DARK_ENERGY_V4)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    standalone = {d["name"] for d in state["standalone"]}
    assert "vacuum_catastrophe" in established
    assert "vacuum_catastrophe" not in standalone


def test_v4_external_refs_are_imports_not_holes():
    graph = load_typst_package_v4(NEWTON_V4)
    state = analyze_proof_state(graph)
    imports = {d["name"] for d in state["imported"]}
    holes = {d["name"] for d in state["holes"]}
    assert "vacuum_prediction" in imports
    assert "vacuum_prediction" not in holes
