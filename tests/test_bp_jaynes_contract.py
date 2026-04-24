import pytest

from gaia.bp.contraction import contract_to_cpt, factor_to_tensor
from gaia.bp.exact import exact_inference, exact_joint_over
from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from gaia.bp.junction_tree import JunctionTreeInference
from gaia.bp.lowering import lower_local_graph
from gaia.ir import FormalExpr, FormalStrategy, Knowledge, LocalCanonicalGraph, Operator


def test_exact_inference_free_variable_has_no_implicit_half_prior():
    fg = FactorGraph()
    fg.add_variable("x")

    beliefs, z = exact_inference(fg)

    assert beliefs["x"] == pytest.approx(0.5)
    assert z == pytest.approx(2.0)


def test_exact_inference_explicit_half_prior_is_a_real_unary_factor():
    fg = FactorGraph()
    fg.add_variable("x", prior=0.5)

    beliefs, z = exact_inference(fg)

    assert beliefs["x"] == pytest.approx(0.5)
    assert z == pytest.approx(1.0)


def test_junction_tree_ignores_display_measure_without_unary_factor():
    fg = FactorGraph()
    fg.add_variable("x", prior=0.9)
    fg.unary_factors.pop("x")

    result = JunctionTreeInference().run(fg)

    assert result.beliefs["x"] == pytest.approx(0.5)


def test_contract_to_cpt_marginalizes_variable_without_unary_factor():
    fg = FactorGraph()
    fg.add_variable("a")
    fg.add_variable("m")
    fg.add_variable("c")
    fg.add_factor("a_and_m", FactorType.CONJUNCTION, ["a", "m"], "c")

    tensor = factor_to_tensor(fg.factors[0])
    cpt = contract_to_cpt([tensor], free_vars=["a", "c"], unary_priors={})

    assert cpt.shape == (2, 2)
    assert cpt[1, 1] == pytest.approx(0.5)


def test_exact_joint_over_computes_boundary_joint():
    fg = FactorGraph()
    fg.add_variable("h")
    fg.add_variable("obs", prior=0.99)
    fg.add_factor("support", FactorType.SOFT_ENTAILMENT, ["h"], "obs", p1=0.99, p2=0.5)

    beliefs, _ = exact_inference(fg)
    joint = exact_joint_over(fg, ["h"])

    assert joint.shape == (2,)
    assert joint.sum() == pytest.approx(1.0)
    assert joint[1] == pytest.approx(beliefs["h"])
    assert joint[1] > 0.5


def test_lowering_leaves_derived_conclusion_without_unary_factor():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b", type="claim", content="B"),
            Knowledge(id="github:jaynes::both", type="claim", content="A and B"),
        ],
        operators=[
            Operator(
                operator="conjunction",
                variables=["github:jaynes::a", "github:jaynes::b"],
                conclusion="github:jaynes::both",
            )
        ],
    )

    fg = lower_local_graph(graph, node_priors={"github:jaynes::a": 0.8})

    assert fg.unary_factors["github:jaynes::a"] == pytest.approx(0.8)
    assert "github:jaynes::b" not in fg.unary_factors
    assert "github:jaynes::both" not in fg.unary_factors


def test_lowering_relation_helper_is_assertion_not_default_prior():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b", type="claim", content="B"),
            Knowledge(id="github:jaynes::same", type="claim", content="A same as B"),
        ],
        operators=[
            Operator(
                operator="equivalence",
                variables=["github:jaynes::a", "github:jaynes::b"],
                conclusion="github:jaynes::same",
            )
        ],
    )

    fg = lower_local_graph(graph)

    assert fg.unary_factors["github:jaynes::same"] == pytest.approx(1.0 - CROMWELL_EPS)
    assert fg.factors[0].factor_type == FactorType.EQUIVALENCE


def test_deduction_lowers_to_hard_conditional_implication():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::c", type="claim", content="C"),
            Knowledge(id="github:jaynes::__imp", type="claim", content="A implies C"),
        ],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::c",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::c"],
                            conclusion="github:jaynes::__imp",
                        )
                    ]
                ),
            )
        ],
    )

    fg = lower_local_graph(graph)

    assert "github:jaynes::__imp" not in fg.variables
    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert factor.factor_type == FactorType.CONDITIONAL
    assert factor.variables == ["github:jaynes::a"]
    assert factor.conclusion == "github:jaynes::c"
    assert factor.cpt == pytest.approx((0.5, 1.0 - CROMWELL_EPS))


def test_deduction_conclusion_evidence_raises_premise_by_bayes():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::c", type="claim", content="C"),
            Knowledge(id="github:jaynes::__imp", type="claim", content="A implies C"),
        ],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::c",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::c"],
                            conclusion="github:jaynes::__imp",
                        )
                    ]
                ),
            )
        ],
    )

    fg = lower_local_graph(
        graph,
        node_priors={
            "github:jaynes::a": 0.5,
            "github:jaynes::c": 0.9,
        },
    )
    beliefs, _ = exact_inference(fg)

    assert beliefs["github:jaynes::a"] > 0.5
    assert beliefs["github:jaynes::a"] == pytest.approx(0.6426529445)


def test_deduction_ignores_helper_prior_for_hard_logic():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::c", type="claim", content="C"),
            Knowledge(
                id="github:jaynes::__imp",
                type="claim",
                content="A implies C",
                metadata={"prior": 0.6},
            ),
        ],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::c",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::c"],
                            conclusion="github:jaynes::__imp",
                        )
                    ]
                ),
            )
        ],
    )

    fg = lower_local_graph(graph, node_priors={"github:jaynes::__imp": 0.6})

    assert len(fg.factors) == 1
    assert fg.factors[0].factor_type == FactorType.CONDITIONAL
    assert fg.factors[0].cpt == pytest.approx((0.5, 1.0 - CROMWELL_EPS))
