from gaia.lang import Claim, ClaimAtom, decompose, implies, land
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.action import Decompose, Structural
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.roles import roles_for_claim


def _knowledge_by_helper_kind(compiled, helper_kind):
    return [
        k for k in compiled.graph.knowledges if (k.metadata or {}).get("helper_kind") == helper_kind
    ]


def test_decompose_registers_structural_action_and_returns_whole_claim():
    with CollectedPackage("decompose_demo") as pkg:
        c = Claim("Composite claim.")
        a = Claim("Atomic A.")
        b = Claim("Atomic B.")
        d = Claim("Atomic D.")
        formula = land(ClaimAtom(a), implies(ClaimAtom(b), ClaimAtom(d)))
        result = decompose(c, parts=(a, b, d), formula=formula, label="split_c")

    assert result is c
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Decompose)
    assert isinstance(action, Structural)
    assert action.whole is c
    assert action.parts == (a, b, d)
    assert action.formula is formula
    assert [occ.role for occ in roles_for_claim(a, pkg)] == ["decomposition_part"]


def test_compile_decompose_generates_formula_helper_and_equivalence_operator():
    with CollectedPackage("decompose_demo") as pkg:
        c = Claim("Composite claim.")
        c.label = "c"
        a = Claim("Atomic A.")
        a.label = "a"
        b = Claim("Atomic B.")
        b.label = "b"
        d = Claim("Atomic D.")
        d.label = "d"
        decompose(
            c,
            parts=(a, b, d),
            formula=land(ClaimAtom(a), implies(ClaimAtom(b), ClaimAtom(d))),
            rationale="C expands to A and if B then D.",
            label="split_c",
        )

    compiled = compile_package_artifact(pkg)

    formula_helpers = _knowledge_by_helper_kind(compiled, "decomposition_formula")
    assert len(formula_helpers) == 1
    formula_helper = formula_helpers[0]
    assert formula_helper.metadata["generated"] is True
    assert formula_helper.metadata["review"] is False
    assert formula_helper.id == "github:decompose_demo::__decompose_split_c_formula"

    equivalence_helpers = _knowledge_by_helper_kind(compiled, "decomposition_equivalence")
    assert len(equivalence_helpers) == 1
    assert equivalence_helpers[0].metadata["review"] is False

    operators = compiled.graph.operators
    equivalence = next(op for op in operators if op.operator == "equivalence")
    assert equivalence.variables == ["github:decompose_demo::c", formula_helper.id]
    assert equivalence.metadata["action_label"] == "github:decompose_demo::action::split_c"
    assert equivalence.metadata["pattern"] == "decomposition"
    assert equivalence.metadata["decomposition"]["whole"] == "github:decompose_demo::c"
    assert equivalence.metadata["decomposition"]["parts"] == [
        "github:decompose_demo::a",
        "github:decompose_demo::b",
        "github:decompose_demo::d",
    ]
    assert compiled.action_label_map["github:decompose_demo::action::split_c"] == (
        equivalence.operator_id
    )
