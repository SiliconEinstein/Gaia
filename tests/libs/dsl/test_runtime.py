"""Tests for the DSL Runtime — Load -> Execute -> Infer -> Inspect pipeline."""

from pathlib import Path

from libs.dsl.models import RetractAction
from libs.dsl.runtime import DSLRuntime, RuntimeResult

from .conftest import MockExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


async def test_runtime_full_pipeline():
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.run(FIXTURE_DIR)

    assert isinstance(result, RuntimeResult)
    assert result.package.name == "galileo_falling_bodies"
    assert len(result.beliefs) == 14
    assert result.factor_graph is not None
    edge_types = {f["edge_type"] for f in result.factor_graph.factors}
    assert {"deduction", "relation_contradiction"}.issubset(edge_types)


async def test_runtime_beliefs_computed():
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.run(FIXTURE_DIR)

    # Key theory nodes should move away from their priors after BP.
    assert "heavier_falls_faster" in result.beliefs
    assert result.beliefs["heavier_falls_faster"] != 0.7
    assert "tied_balls_contradiction" in result.beliefs
    assert result.beliefs["tied_balls_contradiction"] != 0.6
    assert "vacuum_prediction" in result.beliefs
    assert result.beliefs["vacuum_prediction"] != 0.5


async def test_runtime_load_only():
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.load(FIXTURE_DIR)

    assert result.package.name == "galileo_falling_bodies"
    assert len(result.package.loaded_modules) == 5
    # No beliefs yet (not inferred)
    assert len(result.beliefs) == 0


async def test_runtime_beliefs_written_back_to_declarations():
    """After run(), Claim.belief should reflect BP posteriors."""
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.run(FIXTURE_DIR)

    # Find heavier_falls_faster claim via the package
    aristotle = next(m for m in result.package.loaded_modules if m.name == "aristotle")
    hff = next(d for d in aristotle.declarations if d.name == "heavier_falls_faster")

    # belief field should be set and match result.beliefs
    assert hff.belief is not None
    assert hff.belief == result.beliefs["heavier_falls_faster"]
    # belief should differ from prior (BP updated it)
    assert hff.belief != hff.prior

    # Also check a Setting gets its belief written back
    setting_mod = next(m for m in result.package.loaded_modules if m.name == "setting")
    thought_env = next(d for d in setting_mod.declarations if d.name == "thought_experiment_env")
    assert thought_env.belief is not None
    assert thought_env.belief == result.beliefs["thought_experiment_env"]


async def test_runtime_preserves_retract_action_provenance_contract():
    """RetractAction should remain provenance-only while pointing to belief-bearing nodes."""
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.run(FIXTURE_DIR)

    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    retract = next(d for d in reasoning.declarations if d.name == "retract_aristotle")

    assert isinstance(retract, RetractAction)
    assert retract.target == "heavier_falls_faster"
    assert retract.reason == "tied_balls_contradiction"
    assert retract.name not in result.beliefs
    assert retract.target in result.beliefs
    assert retract.reason in result.beliefs
    assert not any(f["name"].startswith("retract_aristotle") for f in result.factor_graph.factors)


async def test_runtime_execute_only():
    """Execute fills claims but no BP."""
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.load(FIXTURE_DIR)
    result = await runtime.execute(result)

    # Claims should be filled with a coherent story, not just placeholders.
    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    ac = next(d for d in reasoning.declarations if d.name == "aristotle_contradicted")
    assert ac.content != ""
    vp = next(d for d in reasoning.declarations if d.name == "vacuum_prediction")
    assert "相同速率下落" in vp.content

    # But no factor graph or beliefs
    assert result.factor_graph is None
    assert len(result.beliefs) == 0


async def test_runtime_infer_only():
    """Infer without execute — BP runs on priors alone."""
    runtime = DSLRuntime()  # no executor
    result = await runtime.load(FIXTURE_DIR)
    result = await runtime.infer(result)

    # Factor graph should exist
    assert result.factor_graph is not None
    assert len(result.factor_graph.variables) == 14

    # Beliefs should be computed (from priors only)
    assert len(result.beliefs) == 14


async def test_runtime_inspect():
    runtime = DSLRuntime(executor=MockExecutor())
    result = await runtime.run(FIXTURE_DIR)
    summary = result.inspect()

    assert summary["package"] == "galileo_falling_bodies"
    assert summary["modules"] == 5
    assert summary["variables"] == 14
    assert summary["factors"] == 11
    assert len(summary["beliefs"]) == 14
