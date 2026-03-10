# tests/libs/lang/test_compiler.py
from pathlib import Path

from libs.lang.compiler import compile_factor_graph
from libs.lang.loader import load_package
from libs.lang.models import (
    Claim,
    ChainExpr,
    Module,
    Package,
    StepRef,
    StepLambda,
)
from libs.lang.resolver import resolve_refs

FIXTURE_DIR = (
    Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies"
)


def test_compile_produces_factor_graph():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    assert len(fg.variables) == 14
    assert len(fg.factors) == 11


def test_variable_nodes_are_claims_and_settings():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # Variable nodes should cover the full narrated story:
    # prior theory, tied-balls predictions, contradiction, confound analysis,
    # inclined-plane support, and final vacuum prediction.
    assert len(fg.variables) == 14
    assert set(fg.variables.keys()) == {
        "heavier_falls_faster",
        "everyday_observation",
        "thought_experiment_env",
        "vacuum_env",
        "tied_pair_slower_than_heavy",
        "tied_pair_faster_than_heavy",
        "tied_balls_contradiction",
        "aristotle_contradicted",
        "medium_density_observation",
        "medium_difference_shrinks",
        "air_resistance_is_confound",
        "inclined_plane_observation",
        "inclined_plane_supports_equal_fall",
        "vacuum_prediction",
    }


def test_factor_nodes_from_chain_steps():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # One factor for each reasoning step that should matter in the story graph:
    # inductive support, tied-balls predictions, contradiction, retraction, verdict,
    # medium trend, confound explanation, inclined-plane support, synthesis, and follow-up.
    assert len(fg.factors) == 11


def test_direct_dependency_creates_edge():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    drag = next(f for f in fg.factors if f["name"] == "drag_prediction_chain.step_2")
    assert drag["premises"] == ["heavier_falls_faster"]
    assert drag["conclusions"] == ["tied_pair_slower_than_heavy"]
    assert drag["probability"] == 0.93
    assert drag["edge_type"] == "deduction"


def test_indirect_dependency_excluded_from_edges():
    """Indirect dependencies should NOT create BP edges."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # thought_experiment_env is used as indirect in drag_prediction_chain
    # It should NOT appear as a tail in that factor
    drag_factors = [f for f in fg.factors if f.get("name") == "drag_prediction_chain.step_2"]
    assert len(drag_factors) == 1, "Expected exactly one drag_prediction_chain.step_2 factor"
    factor = drag_factors[0]
    assert "thought_experiment_env" not in factor.get("premises", [])


def test_contradiction_relation_creates_constraint_factor():
    """The Contradiction relation on tied_balls_contradiction should produce
    a relation_contradiction constraint factor linking the two predictions."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)

    constraint = next(f for f in fg.factors if f["name"] == "tied_balls_contradiction.constraint")
    assert constraint["edge_type"] == "relation_contradiction"
    assert set(constraint["premises"]) == {
        "tied_pair_slower_than_heavy",
        "tied_pair_faster_than_heavy",
    }
    # Relation variable excluded from constraint to avoid feedback loop
    assert constraint["conclusions"] == []
    assert constraint["probability"] == 0.6  # Uses Relation's prior as strength


def test_contradiction_chain_is_now_deduction():
    """After refactoring, the contradiction_chain no longer has edge_type;
    it should default to deduction."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)

    chain_factor = next(f for f in fg.factors if f["name"] == "contradiction_chain.step_2")
    assert chain_factor["edge_type"] == "deduction"
    assert set(chain_factor["premises"]) == {
        "tied_pair_slower_than_heavy",
        "tied_pair_faster_than_heavy",
    }
    assert chain_factor["conclusions"] == ["tied_balls_contradiction"]


def test_retract_action_replaces_retraction_chain():
    """The old retraction_chain should no longer exist; retract_aristotle
    is a RetractAction declaration (not a ChainExpr), so it produces no factor."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)

    factor_names = {f["name"] for f in fg.factors}
    assert "retraction_chain.step_2" not in factor_names
    # The retract_action is a declaration, not a chain — no factor produced
    assert not any(n.startswith("retract_aristotle") for n in factor_names)


def test_question_excluded_from_factor_graph():
    """Question type does not participate in BP even if exported."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # main_question (from motivation) is exported
    # but it's a Question type — Questions don't participate in BP
    var_names = set(fg.variables.keys())
    assert "main_question" not in var_names


# ── Inline tests (no galileo fixture) ─────────────────────────


def test_compile_empty_package():
    """A package with no modules produces an empty factor graph."""
    pkg = Package(name="empty", modules=[])
    pkg.loaded_modules = []
    fg = compile_factor_graph(pkg)
    assert fg.variables == {}
    assert fg.factors == []


def test_compile_single_chain_inline():
    """Build one module with 1 chain (3 steps) and verify factor graph structure."""
    claim_a = Claim(name="a", content="Claim A", prior=0.6)
    claim_b = Claim(name="b", content="", prior=0.5)
    chain = ChainExpr(
        name="my_chain",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "some reasoning"}, prior=0.8),
            StepRef(step=3, ref="b"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, chain],
        export=["a", "b"],
    )
    pkg = Package(name="inline_test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    # Variables: a (prior=0.6) and b (prior=0.5)
    assert len(fg.variables) == 2
    assert fg.variables["a"] == 0.6
    assert fg.variables["b"] == 0.5

    # Factors: one factor from the lambda step
    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["name"] == "my_chain.step_2"
    assert factor["premises"] == ["a"]
    assert factor["conclusions"] == ["b"]
    assert factor["probability"] == 0.8


def test_edge_type_passed_to_factor():
    """ChainExpr.edge_type should propagate to factor dict."""
    claim_a = Claim(name="a", content="x", prior=0.8)
    claim_b = Claim(name="b", content="", prior=0.5)
    chain = ChainExpr(
        name="retract_chain",
        edge_type="retraction",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "retract"}, prior=0.7),
            StepRef(step=3, ref="b"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, chain],
        export=["a", "b"],
    )
    pkg = Package(name="test_edge_type", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)
    assert len(fg.factors) == 1
    assert fg.factors[0]["edge_type"] == "retraction"


def test_edge_type_defaults_to_deduction():
    """Chains without edge_type should default to 'deduction'."""
    claim_a = Claim(name="a", content="x", prior=0.8)
    claim_b = Claim(name="b", content="", prior=0.5)
    chain = ChainExpr(
        name="default_chain",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "reason"}, prior=0.9),
            StepRef(step=3, ref="b"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, chain],
        export=["a", "b"],
    )
    pkg = Package(name="test_default_edge", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)
    assert len(fg.factors) == 1
    assert fg.factors[0]["edge_type"] == "deduction"


def test_non_exported_claim_excluded():
    """Non-exported claims must NOT appear in the factor graph variables."""
    exported_claim = Claim(name="public", content="Exported claim", prior=0.9)
    private_claim = Claim(name="private", content="Not exported", prior=0.5)
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[exported_claim, private_claim],
        export=["public"],  # only 'public' is exported
    )
    pkg = Package(name="export_test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "public" in fg.variables
    assert fg.variables["public"] == 0.9
    assert "private" not in fg.variables
