import warnings

from libs.lang.compiler import compile_factor_graph
from libs.lang.models import (
    Claim,
    ChainExpr,
    Contradiction,
    Equivalence,
    Module,
    Package,
    Ref,
    StepLambda,
    StepRef,
)


def test_contradiction_compiles_to_variable_node():
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
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "a" in fg.variables
    assert "b" in fg.variables
    assert "a_contradicts_b" in fg.variables
    assert fg.variables["a_contradicts_b"] == 0.95


def test_equivalence_compiles_to_variable_node():
    claim_x = Claim(name="x", content="X", prior=0.6)
    claim_y = Claim(name="y", content="Y", prior=0.9)
    equiv = Equivalence(
        name="x_equiv_y",
        between=["x", "y"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_x, claim_y, equiv],
        export=["x", "y", "x_equiv_y"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "x_equiv_y" in fg.variables
    assert fg.variables["x_equiv_y"] == 0.85


def test_contradiction_generates_constraint_factor():
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
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["edge_type"] == "relation_contradiction"
    assert set(factor["premises"]) == {"a", "b"}
    assert factor["conclusions"] == []  # Relation excluded to avoid feedback loop
    assert factor["probability"] == 0.95  # Uses Relation's prior as strength
    assert factor["gate_var"] == "a_contradicts_b"
    assert factor["name"] == "a_contradicts_b.constraint"


def test_equivalence_generates_constraint_factor():
    claim_x = Claim(name="x", content="X", prior=0.6)
    claim_y = Claim(name="y", content="Y", prior=0.9)
    equiv = Equivalence(
        name="x_equiv_y",
        between=["x", "y"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_x, claim_y, equiv],
        export=["x", "y", "x_equiv_y"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["edge_type"] == "relation_equivalence"
    assert set(factor["premises"]) == {"x", "y"}
    assert factor["conclusions"] == []  # Relation excluded to avoid feedback loop
    assert factor["gate_var"] == "x_equiv_y"


def test_relation_with_chain_produces_both_factors():
    """A chain leading to a Relation + the Relation's constraint = 2 factors."""
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="contra",
        between=["a", "b"],
        prior=0.6,
    )
    chain = ChainExpr(
        name="reasoning",
        steps=[
            StepRef(step=1, ref="a"),
            StepLambda(step=2, **{"lambda": "shows contradiction"}, prior=0.9),
            StepRef(step=3, ref="contra"),
        ],
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra, chain],
        export=["a", "b", "contra"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    # 3 variables: a, b, contra
    assert len(fg.variables) == 3
    # 2 factors: chain step + relation constraint
    assert len(fg.factors) == 2
    chain_factor = next(f for f in fg.factors if f["name"] == "reasoning.step_2")
    constraint_factor = next(f for f in fg.factors if f["name"] == "contra.constraint")
    assert chain_factor["edge_type"] == "deduction"
    assert constraint_factor["edge_type"] == "relation_contradiction"


def test_non_exported_relation_excluded():
    """Non-exported Relation should not appear as variable node."""
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="hidden_contra",
        between=["a", "b"],
        prior=0.95,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra],
        export=["a", "b"],  # contra NOT exported
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    assert "hidden_contra" not in fg.variables
    # No constraint factor either (relation var not in fg.variables)
    assert len(fg.factors) == 0


def test_edge_type_emits_deprecation_warning():
    """Using edge_type on ChainExpr should emit a deprecation warning."""
    claim_a = Claim(name="a", content="x", prior=0.8)
    claim_b = Claim(name="b", content="", prior=0.5)
    chain = ChainExpr(
        name="old_chain",
        edge_type="contradiction",
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
    pkg = Package(name="test_deprecated", modules=["m"])
    pkg.loaded_modules = [mod]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_factor_graph(pkg)
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "deprecated" in str(deprecation_warnings[0].message).lower()
        assert "old_chain" in str(deprecation_warnings[0].message)


def test_ref_alias_relation_gets_constraint():
    """A Relation re-exported via Ref alias should still produce a constraint factor."""
    claim_a = Claim(name="a", content="A", prior=0.8)
    claim_b = Claim(name="b", content="B", prior=0.7)
    contra = Contradiction(
        name="c0",
        between=["a", "b"],
        prior=0.95,
    )
    ref_alias = Ref(name="c", ref="c0")
    ref_alias._resolved = contra

    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, contra, ref_alias],
        export=["a", "b", "c"],  # Only alias exported, not c0
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    # Variable should be under alias name
    assert "c" in fg.variables
    assert "c0" not in fg.variables
    # Constraint factor should exist (was previously missing)
    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor["edge_type"] == "relation_contradiction"
    assert set(factor["premises"]) == {"a", "b"}
    assert factor["name"] == "c.constraint"
    assert factor["gate_var"] == "c"


def test_equivalence_nary_decomposes_to_pairwise():
    """Equivalence over 3+ members should decompose into pairwise constraints."""
    claim_a = Claim(name="a", content="A", prior=0.9)
    claim_b = Claim(name="b", content="B", prior=0.1)
    claim_c = Claim(name="c", content="C", prior=0.9)
    equiv = Equivalence(
        name="abc_equiv",
        between=["a", "b", "c"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_a, claim_b, claim_c, equiv],
        export=["a", "b", "c", "abc_equiv"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    # Should produce C(3,2) = 3 pairwise constraint factors
    constraint_factors = [f for f in fg.factors if "abc_equiv" in f["name"]]
    assert len(constraint_factors) == 3
    # Each should be binary (2 premises)
    for f in constraint_factors:
        assert len(f["premises"]) == 2
        assert f["edge_type"] == "relation_equivalence"
        assert f["conclusions"] == []
        assert f["gate_var"] == "abc_equiv"
    # All pairs covered
    pairs = {tuple(sorted(f["premises"])) for f in constraint_factors}
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}


def test_equivalence_binary_no_decomposition():
    """Equivalence over exactly 2 members should produce a single constraint."""
    claim_x = Claim(name="x", content="X", prior=0.6)
    claim_y = Claim(name="y", content="Y", prior=0.9)
    equiv = Equivalence(
        name="xy_equiv",
        between=["x", "y"],
        prior=0.85,
    )
    mod = Module(
        type="reasoning_module",
        name="m",
        declarations=[claim_x, claim_y, equiv],
        export=["x", "y", "xy_equiv"],
    )
    pkg = Package(name="test", modules=["m"])
    pkg.loaded_modules = [mod]

    fg = compile_factor_graph(pkg)

    constraint_factors = [f for f in fg.factors if "xy_equiv" in f["name"]]
    assert len(constraint_factors) == 1
    assert constraint_factors[0]["name"] == "xy_equiv.constraint"
    assert constraint_factors[0]["gate_var"] == "xy_equiv"
