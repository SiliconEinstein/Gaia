"""Tests for the Gaia Language elaborator — deterministic template expansion."""

from pathlib import Path

from libs.lang.elaborator import ElaboratedPackage, elaborate_package
from libs.lang.loader import _parse_module, load_package
from libs.lang.models import Package
from libs.lang.resolver import resolve_refs


FIXTURE_PATH = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies")


def test_elaborate_returns_elaborated_package():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    assert isinstance(result, ElaboratedPackage)
    assert result.package.name == "galileo_falling_bodies"


def test_elaborate_renders_chain_surface_prompts():
    """Chain-surface prompts should carry the authored reasoning text."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    key = ("drag_prediction_chain", 1)
    assert key in prompts
    rendered = prompts[key]["rendered"]
    assert "轻球天然比重球下落更慢" in rendered
    assert "复合体 HL" in rendered


def test_elaborate_records_lambda_content():
    """StepLambda content should be recorded as-is (no template substitution needed)."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    key = ("combined_weight_chain", 1)
    assert key in prompts
    assert "复合体" in prompts[key]["rendered"]


def test_elaborate_records_arg_metadata():
    """Each rendered prompt should include arg refs and dependency types."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    key = ("drag_prediction_chain", 1)
    prompt = prompts[key]
    assert len(prompt["args"]) == 2
    assert prompt["args"][0]["ref"] == "heavier_falls_faster"
    assert prompt["args"][0]["dependency"] == "direct"
    assert prompt["args"][1]["ref"] == "thought_experiment_env"
    assert prompt["args"][1]["dependency"] == "indirect"


def test_elaborate_does_not_modify_original():
    """Elaboration should not mutate the original package."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    original_content = None
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if decl.name == "medium_density_observation":
                original_content = decl.content
                break
    elaborate_package(pkg)
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if decl.name == "medium_density_observation":
                assert decl.content == original_content


def test_elaborate_covers_all_apply_and_lambda_steps():
    """Every StepApply and StepLambda in the package should produce a prompt."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    # After refactoring: retraction_chain removed (-1 lambda), so 10 prompts total
    assert len(result.prompts) >= 10


def test_chain_contexts_populated():
    """chain_contexts should have an entry for each chain in the package."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    assert "drag_prediction_chain" in result.chain_contexts
    assert "contradiction_chain" in result.chain_contexts
    assert "synthesis_chain" in result.chain_contexts


def test_chain_context_edge_type():
    """After refactoring, contradiction_chain has no edge_type (defaults to deduction).
    Contradiction semantics now come from the Relation constraint factor."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    ctx = result.chain_contexts["contradiction_chain"]
    assert ctx["edge_type"] == "deduction"
    # drag_prediction_chain should also default to 'deduction'
    ctx_drag = result.chain_contexts["drag_prediction_chain"]
    assert ctx_drag["edge_type"] == "deduction"


def test_chain_context_premise_and_conclusion():
    """drag_prediction_chain should have correct premise and conclusion refs."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    ctx = result.chain_contexts["drag_prediction_chain"]
    # Step 1 is StepRef (premise), Step 3 is StepRef (conclusion)
    assert len(ctx["premise_refs"]) == 1
    assert ctx["premise_refs"][0]["name"] == "heavier_falls_faster"
    assert ctx["premise_refs"][0]["type"] == "claim"
    assert ctx["premise_refs"][0]["prior"] == 0.7
    assert len(ctx["conclusion_refs"]) == 1
    assert ctx["conclusion_refs"][0]["name"] == "tied_pair_slower_than_heavy"


def test_args_include_decl_type_and_prior():
    """Step args should include decl_type and prior from the referenced declaration."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    prompt = prompts[("drag_prediction_chain", 2)]
    arg0 = prompt["args"][0]
    assert arg0["decl_type"] == "claim"
    assert arg0["prior"] == 0.7
    arg1 = prompt["args"][1]
    assert arg1["decl_type"] == "setting"


def test_elaborate_chain_surface_tracks_lambda_args():
    module = _parse_module(
        {
            "type": "reasoning_module",
            "name": "m",
            "premises": [
                {"type": "claim", "name": "base", "content": "Base premise", "prior": 0.7},
                {"type": "setting", "name": "regime", "content": "Relevant regime", "prior": 0.9},
            ],
            "chains": [
                {
                    "name": "demo_chain",
                    "steps": [
                        {
                            "id": "obs",
                            "type": "claim",
                            "content": "Observation",
                            "refs": [{"ref": "base", "dependency": "direct"}],
                            "prior": 0.61,
                        },
                        {
                            "id": "bridge",
                            "type": "claim",
                            "reasoning": "Combine observation with the regime.",
                            "content": "Bridge",
                            "refs": [
                                {"ref": "obs", "dependency": "direct"},
                                {"ref": "regime", "dependency": "indirect"},
                            ],
                            "prior": 0.73,
                        },
                    ],
                    "conclusion": {
                        "name": "final_claim",
                        "type": "claim",
                        "content": "Final conclusion",
                        "refs": [{"ref": "bridge", "dependency": "direct"}],
                        "prior": 0.84,
                    },
                }
            ],
            "export": ["final_claim"],
        }
    )
    pkg = Package(name="demo_pkg", modules=["m"])
    pkg.loaded_modules = [module]

    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}

    assert prompts[("demo_chain", 1)]["args"][0]["ref"] == "base"
    assert prompts[("demo_chain", 3)]["args"][0]["ref"] == "demo_chain__obs"
    assert prompts[("demo_chain", 3)]["args"][1]["dependency"] == "indirect"

    ctx = result.chain_contexts["demo_chain"]
    assert [ref["name"] for ref in ctx["premise_refs"]] == ["base"]
    assert ctx["conclusion_refs"][0]["name"] == "final_claim"
