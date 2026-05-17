import pytest

from gaia.engine.bp.contraction import contract_to_cpt, factor_to_tensor
from gaia.engine.bp.exact import exact_inference, exact_joint_over
from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.junction_tree import JunctionTreeInference
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.ir import FormalExpr, FormalStrategy, Knowledge, LocalCanonicalGraph, Operator


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


def test_hard_implication_maxent_counts_feasible_worlds_exactly():
    fg = FactorGraph()
    for var_id in ["a", "c", "a_implies_c"]:
        fg.add_variable(var_id)
    fg.add_factor("imp", FactorType.IMPLICATION, ["a", "c"], "a_implies_c")
    fg.add_evidence("a_implies_c", 1)

    exact_beliefs, _ = exact_inference(fg)
    jt_result = JunctionTreeInference().run(fg)
    joint = exact_joint_over(fg, ["a", "c"])

    assert joint == pytest.approx([1 / 3, 0.0, 1 / 3, 1 / 3])
    assert exact_beliefs["a"] == pytest.approx(1 / 3)
    assert exact_beliefs["c"] == pytest.approx(2 / 3)
    assert jt_result.beliefs["a"] == pytest.approx(exact_beliefs["a"])
    assert jt_result.beliefs["c"] == pytest.approx(exact_beliefs["c"])


def test_factor_tensor_for_hard_conjunction_is_strict_delta():
    fg = FactorGraph()
    fg.add_variable("a")
    fg.add_variable("b")
    fg.add_variable("both")
    fg.add_factor("and", FactorType.CONJUNCTION, ["a", "b"], "both")

    tensor, _axes = factor_to_tensor(fg.factors[0])

    assert tensor[0, 0, 0] == 1.0
    assert tensor[0, 0, 1] == 0.0
    assert tensor[1, 1, 0] == 0.0
    assert tensor[1, 1, 1] == 1.0


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

    assert fg.hard_evidence["github:jaynes::same"] == 1
    assert fg.factors[0].factor_type == FactorType.EQUIVALENCE


def test_deduction_lowers_to_normalized_implication_with_asserted_helper():
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

    assert len(fg.factors) == 1
    factor = fg.factors[0]
    assert fg.hard_evidence["github:jaynes::__imp"] == 1
    assert factor.factor_type == FactorType.DEDUCTIVE_IMPLICATION
    assert factor.variables == ["github:jaynes::a"]
    assert factor.conclusion == "github:jaynes::c"


def test_deduction_open_antecedent_defaults_to_half_despite_unobserved_consequences():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b1", type="claim", content="B1"),
            Knowledge(id="github:jaynes::b2", type="claim", content="B2"),
            Knowledge(id="github:jaynes::__imp1", type="claim", content="A implies B1"),
            Knowledge(id="github:jaynes::__imp2", type="claim", content="A implies B2"),
        ],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::b1",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::b1"],
                            conclusion="github:jaynes::__imp1",
                        )
                    ]
                ),
            ),
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::b2",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::b2"],
                            conclusion="github:jaynes::__imp2",
                        )
                    ]
                ),
            ),
        ],
    )

    fg = lower_local_graph(graph)
    beliefs, _ = exact_inference(fg)

    assert beliefs["github:jaynes::a"] == pytest.approx(0.5)
    assert beliefs["github:jaynes::b1"] == pytest.approx(0.75)
    assert beliefs["github:jaynes::b2"] == pytest.approx(0.75)


def test_deduction_respects_existing_antecedent_prior_without_unobserved_penalty():
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b1", type="claim", content="B1"),
            Knowledge(id="github:jaynes::b2", type="claim", content="B2"),
            Knowledge(id="github:jaynes::__imp1", type="claim", content="A implies B1"),
            Knowledge(id="github:jaynes::__imp2", type="claim", content="A implies B2"),
        ],
        strategies=[
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::b1",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::b1"],
                            conclusion="github:jaynes::__imp1",
                        )
                    ]
                ),
            ),
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["github:jaynes::a"],
                conclusion="github:jaynes::b2",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:jaynes::a", "github:jaynes::b2"],
                            conclusion="github:jaynes::__imp2",
                        )
                    ]
                ),
            ),
        ],
    )

    fg = lower_local_graph(graph, node_priors={"github:jaynes::a": 0.7})
    beliefs, _ = exact_inference(fg)

    assert beliefs["github:jaynes::a"] == pytest.approx(0.7)
    assert beliefs["github:jaynes::b1"] == pytest.approx(0.85)
    assert beliefs["github:jaynes::b2"] == pytest.approx(0.85)


def test_deduction_conclusion_prior_can_confirm_premise():
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

    # A prior on C is external information that C is true-like; under normalized
    # deduction it can confirm A without unobserved C penalizing A beforehand.
    assert beliefs["github:jaynes::a"] > 0.5
    assert beliefs["github:jaynes::a"] == pytest.approx(9 / 14, abs=1e-6)


def test_deduction_ignores_helper_prior_for_normalized_implication():
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
    assert fg.hard_evidence["github:jaynes::__imp"] == 1
    assert "github:jaynes::__imp" not in fg.unary_factors
    assert fg.factors[0].factor_type == FactorType.DEDUCTIVE_IMPLICATION


# ---------------------------------------------------------------------------
# V9 (Jaynes D2): structural deduplication of top-level operators
# ---------------------------------------------------------------------------


def test_d2_symmetric_equivalence_reorder_dedup():
    """EQUIVALENCE(A,B) and EQUIVALENCE(B,A) into the same helper → one factor."""
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b", type="claim", content="B"),
            Knowledge(id="github:jaynes::same", type="claim", content="A iff B"),
        ],
        operators=[
            Operator(
                operator="equivalence",
                variables=["github:jaynes::a", "github:jaynes::b"],
                conclusion="github:jaynes::same",
            ),
            Operator(
                operator="equivalence",
                variables=["github:jaynes::b", "github:jaynes::a"],
                conclusion="github:jaynes::same",
            ),
        ],
    )

    fg = lower_local_graph(graph)

    assert len(fg.factors) == 1
    assert len(fg.dedup_audit) == 1
    assert fg.dedup_audit[0]["op"].endswith("equivalence")
    assert fg.dedup_audit[0]["conclusion"] == "github:jaynes::same"


def test_d2_symmetric_conflicting_conclusions_raises():
    """CONJUNCTION(A,B,C) and CONJUNCTION(C,B,A) into different helpers → raise."""
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b", type="claim", content="B"),
            Knowledge(id="github:jaynes::c", type="claim", content="C"),
            Knowledge(id="github:jaynes::h1", type="claim", content="all"),
            Knowledge(id="github:jaynes::h2", type="claim", content="all (alt)"),
        ],
        operators=[
            Operator(
                operator="conjunction",
                variables=["github:jaynes::a", "github:jaynes::b", "github:jaynes::c"],
                conclusion="github:jaynes::h1",
            ),
            Operator(
                operator="conjunction",
                variables=["github:jaynes::c", "github:jaynes::b", "github:jaynes::a"],
                conclusion="github:jaynes::h2",
            ),
        ],
    )

    with pytest.raises(ValueError, match="D2 violation"):
        lower_local_graph(graph)


def test_d2_asymmetric_implication_reverse_is_independent():
    """IMPLICATION(A,B) and IMPLICATION(B,A) are different relations; both kept."""
    graph = LocalCanonicalGraph(
        namespace="github",
        package_name="jaynes",
        knowledges=[
            Knowledge(id="github:jaynes::a", type="claim", content="A"),
            Knowledge(id="github:jaynes::b", type="claim", content="B"),
            Knowledge(id="github:jaynes::ab", type="claim", content="A→B"),
            Knowledge(id="github:jaynes::ba", type="claim", content="B→A"),
        ],
        operators=[
            Operator(
                operator="implication",
                variables=["github:jaynes::a", "github:jaynes::b"],
                conclusion="github:jaynes::ab",
            ),
            Operator(
                operator="implication",
                variables=["github:jaynes::b", "github:jaynes::a"],
                conclusion="github:jaynes::ba",
            ),
        ],
    )

    fg = lower_local_graph(graph)

    assert len(fg.factors) == 2
    assert fg.dedup_audit == []
