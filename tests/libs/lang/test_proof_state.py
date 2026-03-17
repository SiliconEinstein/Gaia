"""Tests for proof state analysis."""

from pathlib import Path

from libs.lang.proof_state import analyze_proof_state
from libs.lang.typst_loader import load_typst_package

GALILEO_V2 = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_v2")


def test_established_claims():
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "tied_balls_contradiction" in established
    assert "air_resistance_is_confound" in established
    assert "vacuum_prediction" in established


def test_axioms_include_settings():
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    axiom_names = {d["name"] for d in state["axioms"]}
    assert "thought_experiment_env" in axiom_names
    assert "vacuum_env" in axiom_names


def test_axioms_include_observations():
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    axiom_names = {d["name"] for d in state["axioms"]}
    assert "medium_density_observation" in axiom_names
    assert "inclined_plane_observation" in axiom_names


def test_questions_detected():
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    question_names = {d["name"] for d in state["questions"]}
    assert "main_question" in question_names
    assert "follow_up_question" in question_names


def test_holes_detected():
    """heavier_falls_faster is a claim without proof, used as premise."""
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "heavier_falls_faster" in hole_names


def test_no_false_holes():
    """Settings and observations should never be holes."""
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "thought_experiment_env" not in hole_names
    assert "medium_density_observation" not in hole_names


def test_proof_state_format_string():
    graph = load_typst_package(GALILEO_V2)
    state = analyze_proof_state(graph)
    report = state["report"]
    assert "established" in report.lower() or "\u2713" in report
    assert "hole" in report.lower() or "?" in report
