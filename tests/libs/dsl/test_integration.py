"""End-to-end integration test: load galileo package, execute, run BP, inspect."""

from pathlib import Path

from libs.dsl.runtime import DSLRuntime

from .conftest import PassthroughExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


async def test_galileo_full_pipeline():
    """Full pipeline: load -> execute -> infer -> inspect."""
    runtime = DSLRuntime(executor=PassthroughExecutor())
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
    assert result.beliefs["tied_balls_contradiction"] != 0.6, "Contradiction node should be inferred"
    assert result.beliefs["vacuum_prediction"] != 0.5, "Final prediction should be updated from prior"

    # The graph should explicitly contain contradiction and retraction semantics.
    edge_types = {f["edge_type"] for f in result.factor_graph.factors}
    assert {"deduction", "contradiction", "retraction"} <= edge_types

    # Summary
    summary = result.inspect()
    assert summary["package"] == "galileo_falling_bodies"
    assert summary["modules"] == 5
    assert summary["variables"] == 14
    assert summary["factors"] == 11


async def test_galileo_empty_claims_filled():
    """Execute phase should fill in empty claims."""
    runtime = DSLRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    for decl in reasoning.declarations:
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
            assert decl.content != "", f"{decl.name} should have content after execution"

    tied_contradiction = next(d for d in reasoning.declarations if d.name == "tied_balls_contradiction")
    air_resistance = next(d for d in reasoning.declarations if d.name == "air_resistance_is_confound")
    vacuum_prediction = next(d for d in reasoning.declarations if d.name == "vacuum_prediction")
    assert "不能同时为真" in tied_contradiction.content
    assert "介质阻力" in air_resistance.content
    assert "相同速率下落" in vacuum_prediction.content


async def test_galileo_branching_structure():
    """The story should branch from Aristotle's law and later merge into one prediction."""
    runtime = DSLRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    fg = result.factor_graph

    # Aristotle's law should feed exactly the two tied-balls prediction branches.
    hff_factors = [f for f in fg.factors if "heavier_falls_faster" in f["tail"]]
    assert len(hff_factors) == 2, "heavier_falls_faster should feed into exactly 2 chains"
    assert {f["name"] for f in hff_factors} == {
        "drag_prediction_chain.step_2",
        "combined_weight_chain.step_2",
    }

    synthesis = next(f for f in fg.factors if f["name"] == "synthesis_chain.step_2")
    assert set(synthesis["tail"]) == {
        "aristotle_contradicted",
        "air_resistance_is_confound",
        "inclined_plane_supports_equal_fall",
    }
    assert synthesis["head"] == ["vacuum_prediction"]


async def test_galileo_story_arc_is_complete():
    """The fixture should tell a full story: question -> contradiction -> explanation -> prediction -> follow-up."""
    runtime = DSLRuntime(executor=PassthroughExecutor())
    result = await runtime.run(FIXTURE_DIR)

    motivation = next(m for m in result.package.loaded_modules if m.name == "motivation")
    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    follow_up = next(m for m in result.package.loaded_modules if m.name == "follow_up")

    main_question = next(d for d in motivation.declarations if d.name == "main_question")
    contradiction = next(d for d in reasoning.declarations if d.name == "tied_balls_contradiction")
    prediction = next(d for d in reasoning.declarations if d.name == "vacuum_prediction")
    follow_up_question = next(d for d in follow_up.declarations if d.name == "follow_up_question")

    assert "是否真正取决于物体的重量" in main_question.content
    assert "不能同时为真" in contradiction.content
    assert "相同速率下落" in prediction.content
    assert "真空" in follow_up_question.content
