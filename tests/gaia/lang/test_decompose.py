import pytest

from gaia.engine.lang import Claim, ClaimAtom, decompose, implies, land, lor
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.action import Decompose, Reasoning, Relation
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang.runtime.roles import roles_for_claim


def _knowledge_by_helper_kind(compiled, helper_kind):
    return [
        k for k in compiled.graph.knowledges if (k.metadata or {}).get("helper_kind") == helper_kind
    ]


def test_decompose_registers_reasoning_action_and_returns_whole_claim():
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
    assert isinstance(action, Reasoning)
    assert not isinstance(action, Relation)
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

    formula_graph = next(
        graph for graph in compiled.graph.formula_graphs if graph.source_claim == formula_helper.id
    )
    nodes = {node.id: node for node in formula_graph.nodes}
    root = nodes[formula_graph.root]
    assert root.kind == "op"
    assert root.descriptor["operator"] == "conjunction"
    implication_edge = next(
        edge
        for edge in formula_graph.edges
        if edge.source == formula_graph.root
        and edge.role == "operand"
        and nodes[edge.target].descriptor.get("operator") == "implication"
    )
    implication = nodes[implication_edge.target]
    assert implication.kind == "op"
    assert {edge.role for edge in formula_graph.edges if edge.source == implication.id} == {
        "antecedent",
        "consequent",
    }


def test_decompose_rejects_multiple_decompositions_for_same_whole():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")
    b = Claim("Atomic B.")
    decompose(c, parts=(a,), formula=ClaimAtom(a), label="split_c")

    with pytest.raises(ValueError, match="already decomposed"):
        decompose(c, parts=(b,), formula=ClaimAtom(b), label="split_c_again")


def test_decompose_rejects_direct_decomposition_cycle():
    a = Claim("Claim A.")
    b = Claim("Claim B.")
    decompose(a, parts=(b,), formula=ClaimAtom(b), label="a_as_b")

    with pytest.raises(ValueError, match="cycle"):
        decompose(b, parts=(a,), formula=ClaimAtom(a), label="b_as_a")


def test_decompose_rejects_transitive_decomposition_cycle():
    a = Claim("Claim A.")
    b = Claim("Claim B.")
    c = Claim("Claim C.")
    decompose(a, parts=(b,), formula=ClaimAtom(b), label="a_as_b")
    decompose(b, parts=(c,), formula=ClaimAtom(c), label="b_as_c")

    with pytest.raises(ValueError, match="cycle"):
        decompose(c, parts=(a,), formula=ClaimAtom(a), label="c_as_a")


def test_decompose_rejects_non_claim_whole():
    a = Claim("Atomic A.")

    # Since RFC #703 lift-coverage extension, decompose(whole=...) goes through
    # _lift_to_claim — a non-Boolean-valued input like a plain str raises the
    # educational lift TypeError instead of the old "whole must be a Claim".
    with pytest.raises(TypeError, match="decompose.*whole"):
        decompose("not a claim", parts=(a,), formula=ClaimAtom(a))


def test_decompose_rejects_empty_parts():
    c = Claim("Composite claim.")

    with pytest.raises(ValueError, match="at least one part"):
        decompose(c, parts=(), formula=ClaimAtom(c))


def test_decompose_rejects_non_claim_parts():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")

    with pytest.raises(TypeError, match="parts must be Claims"):
        decompose(c, parts=(a, "not a claim"), formula=ClaimAtom(a))


def test_decompose_rejects_duplicate_parts():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")

    with pytest.raises(ValueError, match="parts must be unique"):
        decompose(c, parts=(a, a), formula=ClaimAtom(a))


def test_decompose_rejects_non_formula():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")

    with pytest.raises(TypeError, match="formula must be a Formula"):
        decompose(c, parts=(a,), formula=a)


def test_decompose_rejects_formula_that_references_whole():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")

    with pytest.raises(ValueError, match="must not reference the whole claim"):
        decompose(c, parts=(a,), formula=lor(ClaimAtom(a), ClaimAtom(c)))


def test_decompose_rejects_unused_part():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")
    b = Claim("Atomic B.")

    with pytest.raises(ValueError, match="every decompose part"):
        decompose(c, parts=(a, b), formula=ClaimAtom(a))


def test_decompose_rejects_unlisted_formula_atom():
    c = Claim("Composite claim.")
    a = Claim("Atomic A.")
    b = Claim("Atomic B.")

    with pytest.raises(ValueError, match="only reference listed parts"):
        decompose(c, parts=(a,), formula=land(ClaimAtom(a), ClaimAtom(b)))
