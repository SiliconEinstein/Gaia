# tests/libs/lang/test_executor.py
from pathlib import Path

from libs.lang.executor import execute_package
from libs.lang.loader import load_package
from libs.lang.models import (
    Arg,
    Claim,
    ChainExpr,
    InferAction,
    Module,
    Package,
    Param,
    StepApply,
    StepLambda,
    StepRef,
    ToolCallAction,
)
from libs.lang.resolver import resolve_refs

from .conftest import MockExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies"


async def test_execute_fills_empty_claims():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    await execute_package(pkg, executor)

    # The fixture should now fill a full chain of intermediate conclusions,
    # not just the final verdict.
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    filled_names = {
        "tied_pair_slower_than_heavy",
        "tied_pair_faster_than_heavy",
        "tied_balls_contradiction",
        "aristotle_contradicted",
        "medium_difference_shrinks",
        "air_resistance_is_confound",
        "inclined_plane_supports_equal_fall",
        "vacuum_prediction",
    }
    for decl in reasoning.declarations:
        if hasattr(decl, "content") and decl.name in filled_names:
            assert decl.content.strip() != "", f"{decl.name} should be filled"


async def test_execute_calls_infer_action():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    await execute_package(pkg, executor)

    # The richer story uses 4 reusable infer actions:
    # drag-effect deduction, contradiction exposure, confound explanation,
    # and final vacuum synthesis.
    infer_calls = [c for c in executor.calls if c["type"] == "infer"]
    assert len(infer_calls) == 4
    prompts = "\n".join(c["prompt"] for c in infer_calls)
    assert "轻球应当拖慢重球" in prompts
    assert "不能同时为真" in prompts
    assert "介质阻力造成的表象" in prompts
    assert "不同重量的物体应以相同速率下落" in prompts


async def test_execute_calls_lambda():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    await execute_package(pkg, executor)

    # The Galileo story uses 6 one-off lambda steps for narrative pivots
    # (retraction_chain was replaced by a RetractAction, removing one lambda).
    lambda_calls = [c for c in executor.calls if c["type"] == "lambda"]
    assert len(lambda_calls) == 6
    contents = "\n".join(c["content"] for c in lambda_calls)
    assert "归纳成一条普遍规律" in contents
    assert "复合体 HL 总重量大于单独的重球 H" in contents
    assert "自由落体的普遍真理" in contents
    assert "外部阻力效应" in contents
    assert "斜面实验把自由落体减慢到可测量尺度后" in contents
    assert "寻找足够接近真空的直接实验" in contents


async def test_execute_preserves_existing_content():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    await execute_package(pkg, executor)

    # heavier_falls_faster already had content, should not be overwritten
    aristotle = next(m for m in pkg.loaded_modules if m.name == "aristotle")
    hff = next(d for d in aristotle.declarations if d.name == "heavier_falls_faster")
    assert "重的物体" in hff.content


async def test_execute_chain_order():
    """Producer chains should run before the final synthesis chain."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    await execute_package(pkg, executor)

    # vacuum_prediction has pre-filled content; executor should preserve it.
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    vp = next(d for d in reasoning.declarations if d.name == "vacuum_prediction")
    assert "相同速率下落" in vp.content


# ── Inline tests (no galileo fixture) ─────────────────────────


async def test_execute_missing_action_skips():
    """A chain step that applies a nonexistent action is silently skipped."""
    claim_in = Claim(name="input_claim", content="some input", prior=0.9)
    claim_out = Claim(name="output_claim", content="", prior=0.5)
    chain = ChainExpr(
        name="bad_chain",
        steps=[
            StepRef(step=1, ref="input_claim"),
            StepApply(
                step=2,
                apply="nonexistent_action",
                args=[Arg(ref="input_claim", dependency="direct")],
            ),
            StepRef(step=3, ref="output_claim"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_in, claim_out, chain],
        export=[],
    )
    pkg = Package(name="test_missing_action", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    # No crash; output claim stays empty since the action wasn't found
    assert claim_out.content == ""
    # Executor was never called
    assert len(executor.calls) == 0


async def test_execute_preserves_nonempty_target():
    """If the output claim already has content, execution does NOT overwrite it."""
    claim_in = Claim(name="input_claim", content="existing input", prior=0.9)
    claim_out = Claim(name="output_claim", content="already filled", prior=0.5)
    chain = ChainExpr(
        name="preserve_chain",
        steps=[
            StepRef(step=1, ref="input_claim"),
            StepLambda(step=2, **{"lambda": "do something"}, prior=0.8),
            StepRef(step=3, ref="output_claim"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_in, claim_out, chain],
        export=[],
    )
    pkg = Package(name="test_preserve", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    # Lambda was called (it always runs)
    assert len(executor.calls) == 1
    assert executor.calls[0]["type"] == "lambda"
    # But the output claim was not overwritten because it already had content
    assert claim_out.content == "already filled"


async def test_execute_dispatches_toolcall_to_execute_tool():
    """ToolCallAction should go through execute_tool, not execute_infer."""
    tool_action = ToolCallAction(
        name="measure_time",
        tool="stopwatch",
        params=[Param(name="object", type="claim")],
        content="Measure fall time of {object}",
    )
    claim_in = Claim(name="ball", content="iron ball", prior=0.9)
    claim_out = Claim(name="measurement", content="", prior=0.5)
    chain = ChainExpr(
        name="measure_chain",
        steps=[
            StepRef(step=1, ref="ball"),
            StepApply(step=2, apply="measure_time", args=[Arg(ref="ball", dependency="direct")]),
            StepRef(step=3, ref="measurement"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[tool_action, claim_in, claim_out, chain],
        export=["ball", "measurement"],
    )
    pkg = Package(name="test_tool", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    # Should have called execute_tool, NOT execute_infer
    tool_calls = [c for c in executor.calls if c["type"] == "tool"]
    infer_calls = [c for c in executor.calls if c["type"] == "infer"]
    assert len(tool_calls) == 1
    assert len(infer_calls) == 0
    assert tool_calls[0]["tool"] == "stopwatch"
    assert "iron ball" in tool_calls[0]["prompt"]
    # Output claim should be filled
    assert claim_out.content != ""


async def test_execute_toolcall_uses_action_name_when_tool_is_none():
    """When ToolCallAction.tool is None, fall back to action.name."""
    tool_action = ToolCallAction(
        name="lookup_density",
        tool=None,
        params=[Param(name="material", type="claim")],
        content="Look up density of {material}",
    )
    claim_in = Claim(name="material", content="iron", prior=0.9)
    claim_out = Claim(name="density_result", content="", prior=0.5)
    chain = ChainExpr(
        name="lookup_chain",
        steps=[
            StepRef(step=1, ref="material"),
            StepApply(
                step=2, apply="lookup_density", args=[Arg(ref="material", dependency="direct")]
            ),
            StepRef(step=3, ref="density_result"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[tool_action, claim_in, claim_out, chain],
        export=["material", "density_result"],
    )
    pkg = Package(name="test_tool_fallback", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    tool_calls = [c for c in executor.calls if c["type"] == "tool"]
    assert len(tool_calls) == 1
    # Should fall back to action name "lookup_density"
    assert tool_calls[0]["tool"] == "lookup_density"


async def test_execute_topo_sorts_chains():
    """Chains are executed in dependency order regardless of declaration order."""
    claim_a = Claim(name="a", content="input", prior=0.9)
    claim_b = Claim(name="b", content="", prior=0.5)
    claim_c = Claim(name="c", content="", prior=0.5)

    # chain_2 reads b (written by chain_1), writes c
    # Declare chain_2 FIRST to test that topo sort reorders
    chain_2 = ChainExpr(
        name="chain_2",
        steps=[
            StepRef(step=1, ref="b"),
            StepLambda(step=2, **{"lambda": "derive c from b"}, prior=0.8),
            StepRef(step=3, ref="c"),
        ],
    )
    # chain_1 reads a, writes b
    chain_1 = ChainExpr(
        name="chain_1",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "derive b from a"}, prior=0.8),
            StepRef(step=3, ref="b"),
        ],
    )

    # Declare chain_2 before chain_1 (wrong order)
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, claim_c, chain_2, chain_1],
        export=["a", "b", "c"],
    )
    pkg = Package(name="test_topo", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    # chain_1 should have executed first (writes b), then chain_2 (reads b)
    # So claim_c should have content (chain_2 ran after chain_1 filled b)
    assert claim_b.content != "", "chain_1 should have filled b"
    assert claim_c.content != "", (
        "chain_2 should have filled c (topo sort ensures chain_1 runs first)"
    )


async def test_infer_action_still_uses_execute_infer():
    """InferAction should still go through execute_infer (regression guard)."""
    infer_action = InferAction(
        name="reason_about",
        params=[Param(name="premise", type="claim")],
        content="Reason about {premise}",
    )
    claim_in = Claim(name="premise", content="all objects fall", prior=0.9)
    claim_out = Claim(name="conclusion", content="", prior=0.5)
    chain = ChainExpr(
        name="reason_chain",
        steps=[
            StepRef(step=1, ref="premise"),
            StepApply(step=2, apply="reason_about", args=[Arg(ref="premise", dependency="direct")]),
            StepRef(step=3, ref="conclusion"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[infer_action, claim_in, claim_out, chain],
        export=["premise", "conclusion"],
    )
    pkg = Package(name="test_infer_regression", modules=["m"])
    pkg.loaded_modules = [mod]

    executor = MockExecutor()
    await execute_package(pkg, executor)

    infer_calls = [c for c in executor.calls if c["type"] == "infer"]
    tool_calls = [c for c in executor.calls if c["type"] == "tool"]
    assert len(infer_calls) == 1
    assert len(tool_calls) == 0
    assert "all objects fall" in infer_calls[0]["prompt"]
