"""Tests for Language -> v2 storage model conversion."""

from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_galileo_converts_to_v2():
    """Galileo package converts to v2 models with correct counts."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test-run")

    assert data.package.package_id == "galileo_falling_bodies"
    assert data.package.name == "galileo_falling_bodies"
    assert len(data.modules) == 5
    assert len(data.knowledge_items) > 0
    assert len(data.chains) > 0

    # Knowledge IDs should use / separator
    for c in data.knowledge_items:
        assert "/" in c.knowledge_id
        assert c.knowledge_id.startswith("galileo_falling_bodies/")

    # Chain IDs should use . separator
    for ch in data.chains:
        assert ch.chain_id.startswith("galileo_falling_bodies.")


def test_knowledge_dedup():
    """Same knowledge referenced from multiple modules should produce one Knowledge."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test")

    ids = [c.knowledge_id for c in data.knowledge_items]
    assert len(ids) == len(set(ids)), f"Duplicate knowledge IDs: {ids}"


def test_cross_package_refs_not_duplicated():
    """Newton referencing Galileo knowledge should not re-create them."""
    from cli.lang_to_v2 import convert_to_v2

    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)
    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    data = convert_to_v2(pkg=newton, review={}, beliefs={}, bp_run_id="test")

    # Newton knowledge should only include Newton's own declarations
    for c in data.knowledge_items:
        assert c.source_package_id == "newton_principia"


def test_beliefs_become_snapshots():
    """Belief values should become BeliefSnapshot records."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    beliefs = {"vacuum_prediction": 0.82, "heavier_falls_faster": 0.35}
    data = convert_to_v2(pkg=pkg, review={}, beliefs=beliefs, bp_run_id="test-run")

    snapshots_by_name = {s.knowledge_id.split("/")[1]: s for s in data.belief_snapshots}
    assert snapshots_by_name["vacuum_prediction"].belief == 0.82
    assert snapshots_by_name["heavier_falls_faster"].belief == 0.35


def test_review_probabilities_use_full_chain_ids():
    """Review sidecars should map chain names back to full v2 chain IDs."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    review = {
        "chains": [
            {
                "chain": "drag_prediction_chain",
                "steps": [
                    {
                        "step": "drag_prediction_chain.2",
                        "conditional_prior": 0.93,
                        "explanation": "Looks sound.",
                    }
                ],
            }
        ]
    }
    data = convert_to_v2(pkg=pkg, review=review, beliefs={}, bp_run_id="test")

    assert len(data.probabilities) == 1
    record = data.probabilities[0]
    assert record.chain_id == "galileo_falling_bodies.reasoning.drag_prediction_chain"
    assert record.step_index == 0
    assert record.value == 0.93
    assert record.source_detail == "Looks sound."


def test_einstein_cross_package_aliases_keep_external_ids():
    """Nested local refs to dependency exports should not become local knowledge items."""
    from cli.main import _load_with_deps
    from cli.lang_to_v2 import convert_to_v2

    pkg = _load_with_deps(EINSTEIN_DIR)
    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test")

    knowledge_ids = {c.knowledge_id for c in data.knowledge_items}
    assert "einstein_gravity/law_of_gravity" not in knowledge_ids
    assert "einstein_gravity/acceleration_independent_of_mass" not in knowledge_ids
    assert "einstein_gravity/vacuum_prediction" not in knowledge_ids

    chains = {c.chain_id: c for c in data.chains}
    subsumption = chains["einstein_gravity.general_relativity.subsumption_chain"]
    assert [prem.knowledge_id for prem in subsumption.steps[0].premises] == [
        "einstein_gravity/einstein_field_equations",
        "newton_principia/law_of_gravity",
        "newton_principia/acceleration_independent_of_mass",
    ]

    convergence = chains["einstein_gravity.observation.convergence_chain"]
    assert [prem.knowledge_id for prem in convergence.steps[0].premises] == [
        "galileo_falling_bodies/vacuum_prediction",
        "newton_principia/acceleration_independent_of_mass",
        "einstein_gravity/apollo15_confirms_equal_fall",
    ]


def test_einstein_subsumption_export_is_materialized_for_publish():
    """Exported subsumption declarations should become local knowledge items for storage."""
    from cli.main import _load_with_deps
    from cli.lang_to_v2 import convert_to_v2

    pkg = _load_with_deps(EINSTEIN_DIR)
    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test")

    knowledge_ids = {c.knowledge_id for c in data.knowledge_items}
    assert "einstein_gravity/newton_subsumed_by_gr" in knowledge_ids
