"""End-to-end integration test: load galileo package, execute, run BP, inspect."""

from pathlib import Path

from libs.lang.models import Ref
from libs.lang.runtime import GaiaRuntime

from .conftest import PassthroughExecutor

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
FIXTURE_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


async def test_galileo_full_pipeline():
    """Full pipeline: load -> execute -> infer -> inspect."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    # Package loaded correctly
    assert result.package.name == "galileo_falling_bodies"
    assert len(result.package.loaded_modules) == 5

    # Factor graph built
    assert len(result.factor_graph.variables) == 14
    assert len(result.factor_graph.factors) == 11

    # Beliefs computed for all exported claims/settings in the story graph
    assert len(result.beliefs) == 14

    # BP should actually change beliefs from priors on key theory nodes
    assert result.beliefs["heavier_falls_faster"] != 0.7, "BP should update belief from prior"
    assert result.beliefs["tied_balls_contradiction"] != 0.6, (
        "Contradiction node should be inferred"
    )
    assert result.beliefs["vacuum_prediction"] != 0.5, (
        "Final prediction should be updated from prior"
    )

    # The graph should contain deduction chains and a relation_contradiction constraint.
    edge_types = {f["edge_type"] for f in result.factor_graph.factors}
    assert {"deduction", "relation_contradiction"} <= edge_types

    # Summary
    summary = result.inspect()
    assert summary["package"] == "galileo_falling_bodies"
    assert summary["modules"] == 5
    assert summary["variables"] == 14
    assert summary["factors"] == 11


async def test_galileo_claims_have_content():
    """All derived claims should have meaningful content."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    for decl in reasoning.knowledge:
        if hasattr(decl, "content") and decl.name in [
            "tied_pair_slower_than_heavy",
            "tied_pair_faster_than_heavy",
            "tied_balls_contradiction",
            "aristotle_contradicted",
            "medium_difference_shrinks",
            "air_resistance_is_confound",
            "inclined_plane_supports_equal_fall",
            "vacuum_prediction",
        ]:
            assert decl.content != "", f"{decl.name} should have content"

    tied_contradiction = next(
        d for d in reasoning.knowledge if d.name == "tied_balls_contradiction"
    )
    air_resistance = next(d for d in reasoning.knowledge if d.name == "air_resistance_is_confound")
    vacuum_prediction = next(d for d in reasoning.knowledge if d.name == "vacuum_prediction")
    assert "自相矛盾" in tied_contradiction.content
    assert "空气阻力" in air_resistance.content
    assert "相同速率下落" in vacuum_prediction.content


async def test_galileo_branching_structure():
    """The story should branch from Aristotle's law and later merge into one prediction."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    fg = result.factor_graph

    # Aristotle's law should feed exactly the two tied-balls prediction branches.
    hff_factors = [f for f in fg.factors if "heavier_falls_faster" in f["premises"]]
    assert len(hff_factors) == 2, "heavier_falls_faster should feed into exactly 2 chains"
    assert {f["name"] for f in hff_factors} == {
        "drag_prediction_chain.step_2",
        "combined_weight_chain.step_2",
    }

    synthesis = next(f for f in fg.factors if f["name"] == "synthesis_chain.step_2")
    assert set(synthesis["premises"]) == {
        "aristotle_contradicted",
        "air_resistance_is_confound",
        "inclined_plane_supports_equal_fall",
    }
    assert synthesis["conclusions"] == ["vacuum_prediction"]


async def test_galileo_story_arc_is_complete():
    """The fixture should tell a full story: question -> contradiction -> explanation -> prediction -> follow-up."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    motivation = next(m for m in result.package.loaded_modules if m.name == "motivation")
    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    follow_up = next(m for m in result.package.loaded_modules if m.name == "follow_up")

    main_question = next(d for d in motivation.knowledge if d.name == "main_question")
    contradiction = next(d for d in reasoning.knowledge if d.name == "tied_balls_contradiction")
    prediction = next(d for d in reasoning.knowledge if d.name == "vacuum_prediction")
    follow_up_question = next(d for d in follow_up.knowledge if d.name == "follow_up_question")

    assert "是否真正取决于物体的重量" in main_question.content
    assert "自相矛盾" in contradiction.content
    assert "相同速率下落" in prediction.content
    assert "真空" in follow_up_question.content


# ── Helper: load Einstein dependency chain ──────────────────────


async def _load_deps(runtime: GaiaRuntime) -> dict:
    """Load Galileo → Newton dependency chain, return deps for Einstein."""
    galileo = await runtime.run(FIXTURE_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    return {
        "galileo": galileo,
        "newton": newton,
        "einstein_deps": {
            "newton_principia": newton.package,
            "galileo_falling_bodies": galileo.package,
        },
    }


# ── Newton integration tests ───────────────────────────────────


async def test_newton_full_pipeline():
    """Newton depends on Galileo: load -> resolve cross-pkg -> execute -> infer."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(FIXTURE_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )

    assert newton.package.name == "newton_principia"
    assert len(newton.package.loaded_modules) == 4

    # Factor graph: 12 BP variables, 4 chain step factors
    assert len(newton.factor_graph.variables) == 12
    assert len(newton.factor_graph.factors) == 4

    # Beliefs computed
    assert len(newton.beliefs) == 12

    # Key claims updated from priors (chain conclusions with prior=0.5)
    assert newton.beliefs["acceleration_independent_of_mass"] != 0.5
    assert newton.beliefs["force_equation_result"] != 0.5

    # All edge types are deduction (no relation constraints fire)
    edge_types = {f["edge_type"] for f in newton.factor_graph.factors}
    assert edge_types == {"deduction"}

    summary = newton.inspect()
    assert summary["package"] == "newton_principia"
    assert summary["variables"] == 12
    assert summary["factors"] == 4


async def test_newton_cross_package_refs_resolved():
    """Cross-package refs to Galileo should resolve to actual Knowledge objects."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(FIXTURE_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )

    implications = next(m for m in newton.package.loaded_modules if m.name == "implications")

    # galileo_vacuum_prediction ref → Galileo's vacuum_prediction
    ref = next(
        d
        for d in implications.knowledge
        if isinstance(d, Ref) and d.name == "galileo_vacuum_prediction"
    )
    assert ref._resolved is not None
    assert ref._resolved.name == "vacuum_prediction"

    # aristotle_law ref → Galileo's heavier_falls_faster
    ref2 = next(
        d for d in implications.knowledge if isinstance(d, Ref) and d.name == "aristotle_law"
    )
    assert ref2._resolved is not None
    assert ref2._resolved.name == "heavier_falls_faster"


# ── Einstein integration tests ─────────────────────────────────


async def test_einstein_full_pipeline():
    """Einstein depends on Newton + Galileo: full transitive dependency chain."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    loaded = await _load_deps(runtime)
    einstein = await runtime.run(EINSTEIN_DIR, deps=loaded["einstein_deps"])

    assert einstein.package.name == "einstein_gravity"
    assert len(einstein.package.loaded_modules) == 4

    # Factor graph: 15 BP variables, 10 factors (9 chain + 1 relation constraint)
    assert len(einstein.factor_graph.variables) == 15
    assert len(einstein.factor_graph.factors) == 10

    # Beliefs computed
    assert len(einstein.beliefs) == 15

    # Subsumption excluded from BP
    assert "newton_subsumed_by_gr" not in einstein.beliefs

    # Key claims updated from priors
    assert einstein.beliefs["equivalence_principle"] != 0.5
    assert einstein.beliefs["three_path_convergence"] != 0.5

    # Both deduction and relation_contradiction edge types
    edge_types = {f["edge_type"] for f in einstein.factor_graph.factors}
    assert "deduction" in edge_types
    assert "relation_contradiction" in edge_types

    summary = einstein.inspect()
    assert summary["package"] == "einstein_gravity"
    assert summary["variables"] == 15
    assert summary["factors"] == 10


async def test_einstein_deflection_contradiction_constraint():
    """The deflection_contradiction should create a binary constraint."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    loaded = await _load_deps(runtime)
    einstein = await runtime.run(EINSTEIN_DIR, deps=loaded["einstein_deps"])

    constraint = next(
        f for f in einstein.factor_graph.factors if f["edge_type"] == "relation_contradiction"
    )
    assert set(constraint["premises"]) == {"gr_light_deflection", "soldner_deflection"}
    assert constraint["conclusions"] == []
    assert constraint["gate_var"] == "deflection_contradiction"


async def test_einstein_subsumption_is_metadata_only():
    """Subsumption should exist as Knowledge but not participate in BP."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    loaded = await _load_deps(runtime)
    einstein = await runtime.run(EINSTEIN_DIR, deps=loaded["einstein_deps"])

    # Subsumption exists as a knowledge declaration
    gr_module = next(m for m in einstein.package.loaded_modules if m.name == "general_relativity")
    subsumption = next(d for d in gr_module.knowledge if d.name == "newton_subsumed_by_gr")
    assert subsumption.type == "subsumption"

    # But NOT in factor graph variables or beliefs
    assert "newton_subsumed_by_gr" not in einstein.factor_graph.variables
    assert "newton_subsumed_by_gr" not in einstein.beliefs
