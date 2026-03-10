"""Runtime integration tests for Relation types."""

from libs.lang.models import (
    Arg,
    ChainExpr,
    Claim,
    Contradiction,
    Equivalence,
    Module,
    Package,
    StepApply,
    StepLambda,
    StepRef,
)
from libs.lang.runtime import GaiaRuntime, RuntimeResult


def _build_equivalence_package(
    *,
    member_names: tuple[str, ...],
    priors: tuple[float, ...],
    include_equivalence: bool,
    relation_name: str,
) -> tuple[Package, Equivalence | None]:
    claims = [
        Claim(name=name, content=name.upper(), prior=prior)
        for name, prior in zip(member_names, priors, strict=True)
    ]
    relation = None
    declarations = list(claims)
    export = list(member_names)
    if include_equivalence:
        relation = Equivalence(name=relation_name, between=list(member_names), prior=0.85)
        declarations.append(relation)
        export.append(relation_name)

    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=declarations,
        export=export,
    )
    pkg = Package(name=f"{relation_name}_pkg", modules=["m"])
    pkg.loaded_modules = [mod]
    return pkg, relation


def _build_shared_premise_package(
    include_contradiction: bool,
) -> tuple[Package, Contradiction | None]:
    premise = Claim(name="premise", content="Shared premise", prior=0.8)
    claim_a = Claim(name="a", content="Prediction A", prior=0.5)
    claim_b = Claim(name="b", content="Prediction B", prior=0.5)

    chain_a = ChainExpr(
        name="chain_a",
        steps=[
            StepRef(step=1, ref="premise"),
            StepLambda(step=2, **{"lambda": "derive A"}, prior=0.9),
            StepRef(step=3, ref="a"),
        ],
    )
    chain_b = ChainExpr(
        name="chain_b",
        steps=[
            StepRef(step=1, ref="premise"),
            StepLambda(step=2, **{"lambda": "derive B"}, prior=0.9),
            StepRef(step=3, ref="b"),
        ],
    )

    declarations = [premise, claim_a, claim_b, chain_a, chain_b]
    export = ["premise", "a", "b"]
    contra = None
    if include_contradiction:
        contra = Contradiction(
            name="a_vs_b",
            between=["a", "b"],
            prior=0.95,
        )
        declarations.append(contra)
        export.append("a_vs_b")

    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=declarations,
        export=export,
    )
    pkg = Package(name="test_integration", modules=["m"])
    pkg.loaded_modules = [mod]
    return pkg, contra


def _build_relation_gate_package(include_support_chain: bool) -> tuple[Package, Contradiction]:
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="a_vs_b",
        between=["a", "b"],
        prior=0.1,
    )

    declarations = [claim_a, claim_b, contra]
    if include_support_chain:
        declarations.append(
            ChainExpr(
                name="establish_contradiction",
                steps=[
                    StepRef(step=1, ref="a"),
                    StepApply(
                        step=2,
                        apply="support_contradiction",
                        args=[
                            Arg(ref="a", dependency="direct"),
                            Arg(ref="b", dependency="direct"),
                        ],
                        prior=0.95,
                    ),
                    StepRef(step=3, ref="a_vs_b"),
                ],
            )
        )

    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=declarations,
        export=["a", "b", "a_vs_b"],
    )
    pkg = Package(name="relation_gate_pkg", modules=["m"])
    pkg.loaded_modules = [mod]
    return pkg, contra


async def test_contradiction_gets_belief_after_inference():
    """Relation declarations should have .belief set after BP."""
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="a_contradicts_b",
        between=["a", "b"],
        prior=0.95,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra],
        export=["a", "b", "a_contradicts_b"],
    )
    pkg = Package(name="test_relation_bp", modules=["m"])
    pkg.loaded_modules = [mod]

    runtime = GaiaRuntime()
    result = RuntimeResult(package=pkg)
    result = await runtime.infer(result)

    # Relation should have belief computed
    assert "a_contradicts_b" in result.beliefs
    assert contra.belief is not None
    assert contra.belief == result.beliefs["a_contradicts_b"]


async def test_equivalence_gets_belief_after_inference():
    """Equivalence should change beliefs relative to the no-relation control graph."""
    pkg, equiv = _build_equivalence_package(
        member_names=("x", "y"),
        priors=(0.6, 0.9),
        include_equivalence=True,
        relation_name="x_equiv_y",
    )
    control_pkg, _ = _build_equivalence_package(
        member_names=("x", "y"),
        priors=(0.6, 0.9),
        include_equivalence=False,
        relation_name="x_equiv_y",
    )
    runtime = GaiaRuntime()
    result = await runtime.infer(RuntimeResult(package=pkg))
    control = await runtime.infer(RuntimeResult(package=control_pkg))

    assert equiv is not None
    assert equiv.belief is not None
    # Equivalence should narrow the gap between beliefs.
    # Note: both may rise (reward for agreeing at 1,1), so we only check gap narrowing
    # and that the lower-prior claim is pulled up.
    result_gap = abs(result.beliefs["y"] - result.beliefs["x"])
    control_gap = abs(control.beliefs["y"] - control.beliefs["x"])
    assert result_gap < control_gap
    assert result.beliefs["x"] > control.beliefs["x"]


async def test_contradiction_weakens_shared_premises():
    """Contradiction should lower the shared premise and both branches vs control."""
    pkg, contra = _build_shared_premise_package(include_contradiction=True)
    control_pkg, _ = _build_shared_premise_package(include_contradiction=False)
    runtime = GaiaRuntime()
    result = await runtime.infer(RuntimeResult(package=pkg))
    control = await runtime.infer(RuntimeResult(package=control_pkg))

    assert result.beliefs["a"] < control.beliefs["a"]
    assert result.beliefs["b"] < control.beliefs["b"]
    assert result.beliefs["premise"] < control.beliefs["premise"]
    assert contra is not None
    assert result.beliefs["a_vs_b"] > 0.8


async def test_nary_equivalence_pulls_all_members_toward_group():
    """A 3-way equivalence should affect every member, not just the first two."""
    pkg, equiv = _build_equivalence_package(
        member_names=("a", "b", "c"),
        priors=(0.9, 0.1, 0.9),
        include_equivalence=True,
        relation_name="abc_equiv",
    )
    control_pkg, _ = _build_equivalence_package(
        member_names=("a", "b", "c"),
        priors=(0.9, 0.1, 0.9),
        include_equivalence=False,
        relation_name="abc_equiv",
    )
    runtime = GaiaRuntime()
    result = await runtime.infer(RuntimeResult(package=pkg))
    control = await runtime.infer(RuntimeResult(package=control_pkg))

    assert equiv is not None
    assert equiv.belief is not None
    # The outlier (b, prior=0.1) should be pulled toward the majority (a,c at 0.9)
    assert result.beliefs["b"] > control.beliefs["b"]
    # All three members must participate — spread should narrow vs control
    result_spread = max(result.beliefs[name] for name in ("a", "b", "c")) - min(
        result.beliefs[name] for name in ("a", "b", "c")
    )
    control_spread = max(control.beliefs[name] for name in ("a", "b", "c")) - min(
        control.beliefs[name] for name in ("a", "b", "c")
    )
    assert result_spread < control_spread


async def test_relation_support_chain_strengthens_constraint_via_gate_belief():
    """Supporting evidence for a Relation should increase its constraint effect."""
    pkg, contra = _build_relation_gate_package(include_support_chain=True)
    control_pkg, _ = _build_relation_gate_package(include_support_chain=False)

    runtime = GaiaRuntime()
    result = await runtime.infer(RuntimeResult(package=pkg))
    control = await runtime.infer(RuntimeResult(package=control_pkg))

    assert contra.belief is not None
    assert result.beliefs["a_vs_b"] > control.beliefs["a_vs_b"]
    assert result.beliefs["a"] < control.beliefs["a"]
    assert result.beliefs["b"] < control.beliefs["b"]
