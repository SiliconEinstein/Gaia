from libs.lang.models import (
    Claim,
    Question,  # noqa: F401 — import-smoke-test
    Setting,  # noqa: F401 — import-smoke-test
    InferAction,
    ToolCallAction,  # noqa: F401 — import-smoke-test
    ChainExpr,
    Dependency,
    Ref,
    Module,
    Package,
    StepRef,
    StepApply,
    StepLambda,
    Param,
    Arg,
)


def test_claim_creation():
    c = Claim(name="test", content="some claim", prior=0.8)
    assert c.type == "claim"
    assert c.prior == 0.8


def test_infer_action_with_params():
    a = InferAction(
        name="reductio",
        params=[Param(name="hyp", type="claim")],
        return_type="claim",
        content="对 {hyp} 运用归谬法",
        prior=0.9,
    )
    assert a.type == "infer_action"
    assert len(a.params) == 1
    assert a.params[0].name == "hyp"
    assert a.params[0].type == "claim"
    assert a.return_type == "claim"
    assert "{hyp}" in a.content


def test_chain_expr_steps():
    chain = ChainExpr(
        name="my_chain",
        steps=[
            StepRef(step=1, ref="premise"),
            StepApply(
                step=2,
                apply="reductio",
                args=[Arg(ref="premise", dependency="direct")],
                prior=0.9,
            ),
            StepRef(step=3, ref="conclusion"),
        ],
    )
    assert chain.type == "chain_expr"
    assert len(chain.steps) == 3
    assert isinstance(chain.steps[0], StepRef)
    assert chain.steps[0].ref == "premise"
    assert isinstance(chain.steps[1], StepApply)
    assert chain.steps[1].apply == "reductio"
    assert chain.steps[1].args[0].dependency == "direct"
    assert isinstance(chain.steps[2], StepRef)


def test_ref_declaration():
    r = Ref(name="premise", target="other_module.premise")
    assert r.type == "ref"
    assert r.target == "other_module.premise"


def test_module_with_declarations():
    m = Module(
        type="reasoning_module",
        name="reasoning",
        declarations=[
            Claim(name="c1", content="test"),
        ],
        export=["c1"],
    )
    assert m.type == "reasoning_module"
    assert m.name == "reasoning"
    assert len(m.declarations) == 1
    assert m.declarations[0].name == "c1"
    assert m.export == ["c1"]


def test_package():
    p = Package(
        name="test_pkg",
        version="1.0.0",
        modules_list=["mod_a", "mod_b"],
        export=["conclusion"],
    )
    assert p.name == "test_pkg"
    assert p.version == "1.0.0"
    assert p.modules_list == ["mod_a", "mod_b"]
    assert p.export == ["conclusion"]


def test_prior_defaults_to_none():
    c = Claim(name="test", content="no prior")
    assert c.prior is None


def test_step_discriminator():
    """Steps are distinguished by which key is present: ref, apply, or lambda_."""
    s1 = StepRef(step=1, ref="x")
    s2 = StepApply(step=2, apply="f", args=[])
    s3 = StepLambda(step=3, lambda_="some reasoning")
    assert s1.ref == "x"
    assert s2.apply == "f"
    assert s3.lambda_ == "some reasoning"


def test_package_with_dependencies():
    pkg = Package(
        name="test",
        dependencies=[Dependency(package="physics_base", version=">=1.0.0")],
        modules=["m1"],
    )
    assert len(pkg.dependencies) == 1
    assert pkg.dependencies[0].package == "physics_base"
    assert pkg.dependencies[0].version == ">=1.0.0"
