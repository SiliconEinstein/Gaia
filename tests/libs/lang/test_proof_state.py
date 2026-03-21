"""Tests for proof state analysis."""

from pathlib import Path

from libs.lang.proof_state import analyze_proof_state
from libs.lang.typst_loader import load_typst_package, load_typst_package_v4

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "gaia_language_packages"
GALILEO_V3 = _FIXTURES / "galileo_falling_bodies_v3"
NEWTON_V3 = _FIXTURES / "newton_principia_v3"
EINSTEIN_V3 = _FIXTURES / "einstein_gravity_v3"
GALILEO_V4 = _FIXTURES / "galileo_falling_bodies_v4"
NEWTON_V4 = _FIXTURES / "newton_principia_v4"
DARK_ENERGY_V4 = _FIXTURES / "dark_energy_v4"


def test_established_claims():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "composite_is_slower" in established
    assert "composite_is_faster" in established
    assert "air_resistance_is_confound" in established
    assert "vacuum_prediction" in established


def test_claim_relation_is_established():
    """claim_relation nodes (e.g. contradiction) should be established, not holes."""
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "tied_balls_contradiction" in established


def test_claim_relation_not_hole():
    """claim_relation nodes should never appear as holes."""
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "tied_balls_contradiction" not in hole_names


def test_heavier_falls_faster_is_hole():
    """A claim used as premise without a factor concluding it should be a hole."""
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "heavier_falls_faster" in hole_names


def test_settings_are_assumptions():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    assumption_names = {d["name"] for d in state["assumptions"]}
    assert "thought_experiment_env" in assumption_names
    assert "vacuum_env" in assumption_names


def test_observations_are_holes():
    """Observations used as premises without proof should be holes, not assumptions."""
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "medium_density_observation" in hole_names
    assert "inclined_plane_observation" in hole_names


def test_unreferenced_observation_is_standalone():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    standalone_names = {d["name"] for d in state["standalone"]}
    assert "everyday_observation" in standalone_names


def test_questions_detected():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    question_names = {d["name"] for d in state["questions"]}
    assert "main_question" in question_names
    assert "follow_up_question" in question_names


def test_settings_not_holes():
    """Settings are assumptions, never holes."""
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "thought_experiment_env" not in hole_names


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


def test_proof_state_format_string():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    report = state["report"]
    assert "established" in report.lower() or "\u2713" in report
    assert "assumption" in report.lower() or "\u25cb" in report
    assert "medium_density_observation  (observation, used as premise, no proof)" in report


def test_proof_state_does_not_return_axioms_key():
    graph = load_typst_package(GALILEO_V3)
    state = analyze_proof_state(graph)
    assert "axioms" not in state


# ── Newton v3 ────────────────────────────────────────────────────────────────


def test_newton_v3_loads():
    graph = load_typst_package(NEWTON_V3)
    assert len(graph["nodes"]) == 15
    assert len(graph["factors"]) == 5
    assert len(graph["constraints"]) == 2


def test_newton_v3_derivation_chain():
    """Historical derivation: Kepler → inverse square → gravity → mass equiv → a=g."""
    graph = load_typst_package(NEWTON_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "inverse_square_force" in established
    assert "law_of_gravity" in established
    assert "mass_equivalence" in established
    assert "freefall_acceleration_equals_g" in established
    assert "apollo15_confirms_equal_fall" in established
    # corroborations are constraints, not reasoning factors
    constraint_names = {c["name"] for c in graph["constraints"]}
    assert "galileo_newton_convergence" in constraint_names
    assert "apollo_galileo_convergence" in constraint_names


def test_newton_v3_corroborations_are_established():
    graph = load_typst_package(NEWTON_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    standalone = {d["name"] for d in state["standalone"]}
    assert "galileo_newton_convergence" in established
    assert "apollo_galileo_convergence" in established
    assert "galileo_newton_convergence" not in standalone
    assert "apollo_galileo_convergence" not in standalone


def test_newton_v3_observations_and_unproved_claims_are_holes():
    """Observations used as premises should be holes (need experimental proof)."""
    graph = load_typst_package(NEWTON_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "kepler_third_law" in hole_names
    assert "pendulum_experiment" in hole_names
    assert "apollo15_feather_drop" in hole_names
    assert "second_law" in hole_names
    assert "third_law" in hole_names


def test_newton_v3_inverse_square_premises():
    graph = load_typst_package(NEWTON_V3)
    f = [f for f in graph["factors"] if f["conclusion"] == "inverse_square_force"]
    assert len(f) == 1
    assert set(f[0]["premise"]) == {"kepler_third_law", "second_law"}


def test_newton_v3_mass_equivalence_premises():
    graph = load_typst_package(NEWTON_V3)
    f = [f for f in graph["factors"] if f["conclusion"] == "mass_equivalence"]
    assert len(f) == 1
    assert set(f[0]["premise"]) == {"pendulum_experiment", "second_law", "law_of_gravity"}


# ── Einstein v3 ──────────────────────────────────────────────────────────────


def test_einstein_v3_loads():
    graph = load_typst_package(EINSTEIN_V3)
    assert len(graph["nodes"]) == 16
    assert len(graph["factors"]) == 5
    assert len(graph["constraints"]) == 2


def test_einstein_v3_reasoning_chain():
    """EP → light bends → GR deflection; EFE + mercury → precession."""
    graph = load_typst_package(EINSTEIN_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    assert "equivalence_principle" in established
    assert "light_bends_in_gravity" in established
    assert "gr_light_deflection" in established
    assert "gr_mercury_precession" in established
    assert "eddington_confirms_gr" in established


def test_einstein_v3_constraints():
    graph = load_typst_package(EINSTEIN_V3)
    constraint_map = {c["name"]: c for c in graph["constraints"]}
    # Contradiction
    assert constraint_map["deflection_contradiction"]["type"] == "contradiction"
    assert set(constraint_map["deflection_contradiction"]["between"]) == {
        "gr_light_deflection",
        "soldner_deflection",
    }
    # Corroborations
    assert constraint_map["gr_dual_confirmation"]["type"] == "corroboration"
    assert set(constraint_map["gr_dual_confirmation"]["between"]) == {
        "eddington_confirms_gr",
        "gr_mercury_precession",
    }


def test_einstein_v3_corroboration_is_established():
    graph = load_typst_package(EINSTEIN_V3)
    state = analyze_proof_state(graph)
    established = {d["name"] for d in state["established"]}
    standalone = {d["name"] for d in state["standalone"]}
    assert "gr_dual_confirmation" in established
    assert "gr_dual_confirmation" not in standalone


def test_einstein_v3_holes():
    """Postulates and observations without proof should be holes."""
    graph = load_typst_package(EINSTEIN_V3)
    state = analyze_proof_state(graph)
    hole_names = {d["name"] for d in state["holes"]}
    assert "maxwell_electromagnetism" in hole_names
    assert "soldner_deflection" in hole_names
    assert "einstein_field_equations" in hole_names
    assert "eotvos_experiment" in hole_names
    assert "eddington_sobral" in hole_names
    assert "eddington_principe" in hole_names
    assert "mercury_perihelion" in hole_names


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
