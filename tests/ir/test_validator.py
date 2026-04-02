"""Tests for Gaia IR validator."""

from gaia.ir import (
    Knowledge,
    KnowledgeType,
    Operator,
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    LocalCanonicalGraph,
)
from gaia.ir.validator import (
    validate_local_graph,
    validate_parameterization,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim(id: str, content: str = "test") -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.CLAIM, content=content)


def _setting(id: str) -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.SETTING)


def _local_graph(**kwargs) -> LocalCanonicalGraph:
    defaults = {
        "namespace": "reg",
        "package_name": "test",
        "knowledges": [],
        "operators": [],
        "strategies": [],
    }
    defaults.update(kwargs)
    return LocalCanonicalGraph(**defaults)


# ---------------------------------------------------------------------------
# 1. Knowledge validation
# ---------------------------------------------------------------------------


class TestKnowledgeValidation:
    def test_valid_local(self):
        g = _local_graph(knowledges=[_claim("reg:test::a")])
        r = validate_local_graph(g)
        assert r.valid

    def test_wrong_prefix_local(self):
        g = _local_graph(knowledges=[_claim("gcn_wrong")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("QID format" in e for e in r.errors)

    def test_duplicate_id(self):
        g = _local_graph(knowledges=[_claim("reg:test::a"), _claim("reg:test::a", "other")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("duplicate" in e for e in r.errors)

    def test_local_knowledge_must_have_content(self):
        k = Knowledge(id="reg:test::a", type=KnowledgeType.CLAIM)
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("content" in e for e in r.errors)

    def test_duplicate_label_rejected(self):
        g = _local_graph(
            knowledges=[
                Knowledge(id="reg:test::x", type=KnowledgeType.CLAIM, content="first", label="x"),
                Knowledge(id="reg:test2::x", type=KnowledgeType.CLAIM, content="second", label="x"),
            ]
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("duplicate" in e and "label" in e for e in r.errors)

    def test_namespace_must_be_allowed(self):
        """Namespace must be reg or paper."""
        g = LocalCanonicalGraph(
            namespace="invalid",
            package_name="test",
            knowledges=[Knowledge(id="invalid:test::a", type="claim", content="test", label="a")],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("namespace" in e for e in r.errors)

    def test_external_qid_with_different_namespace_is_allowed(self):
        """Local graphs may explicitly reference external package nodes."""
        g = LocalCanonicalGraph(
            namespace="reg",
            package_name="test",
            knowledges=[Knowledge(id="paper:other::a", type="claim", content="test", label="a")],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_external_qid_with_different_package_is_allowed(self):
        """Foreign package QIDs are valid as long as the QID itself is valid."""
        g = LocalCanonicalGraph(
            namespace="reg",
            package_name="test",
            knowledges=[Knowledge(id="reg:other_pkg::a", type="claim", content="test", label="a")],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_valid_namespace_and_package(self):
        """Valid namespace and matching package pass."""
        g = _local_graph(knowledges=[_claim("reg:test::a")])
        r = validate_local_graph(g)
        assert r.valid


# ---------------------------------------------------------------------------
# 2. Operator validation
# ---------------------------------------------------------------------------


class TestOperatorValidation:
    def test_valid_operator_equivalence(self):
        """Equivalence: 2 variables + conclusion (helper claim)."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b"), _claim("reg:test::h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_valid_operator_implication(self):
        """Implication: 1 variable + conclusion."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["reg:test::a"],
                    conclusion="reg:test::b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_valid_operator_conjunction(self):
        """Conjunction: >=2 variables + conclusion."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b"), _claim("reg:test::m")],
            operators=[
                Operator(
                    operator_id="lco_and",
                    scope="local",
                    operator="conjunction",
                    variables=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::m",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_variable_reference(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::missing"],
                    conclusion="reg:test::h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("not found" in e for e in r.errors)

    def test_dangling_conclusion_reference(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["reg:test::a"],
                    conclusion="reg:test::missing",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "not found" in e for e in r.errors)

    def test_operator_variable_on_non_claim(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _setting("reg:test::s"), _claim("reg:test::h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::s"],
                    conclusion="reg:test::h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("must be claim" in e for e in r.errors)

    def test_operator_conclusion_on_non_claim(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _setting("reg:test::s")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["reg:test::a"],
                    conclusion="reg:test::s",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "must be claim" in e for e in r.errors)

    def test_global_scoped_operator_rejected_at_construction(self):
        """Global scope is no longer allowed — Operator model rejects it."""
        import pytest

        with pytest.raises(ValueError, match="scope must be one of"):
            Operator(
                operator_id="gco_bad",
                scope="global",
                operator="implication",
                variables=["reg:test::a"],
                conclusion="reg:test::b",
            )

    def test_operator_conclusion_scope_prefix_check(self):
        """Operator conclusion should have correct scope prefix."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["reg:test::a"],
                    conclusion="gcn_wrong",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong format" in e or "not found" in e for e in r.errors)

    def test_top_level_operator_requires_scope_and_id(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            operators=[
                Operator(
                    operator="implication", variables=["reg:test::a"], conclusion="reg:test::b"
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("Top-level Operator must set both operator_id and scope" in e for e in r.errors)

    def test_operator_lco_prefix_required(self):
        """Pydantic model validation rejects wrong ID prefix at construction time."""
        import pytest

        with pytest.raises(Exception, match="lco_ prefix"):
            Operator(
                operator_id="bad_prefix",
                scope="local",
                operator="implication",
                variables=["reg:test::a"],
                conclusion="reg:test::b",
            )


# ---------------------------------------------------------------------------
# 3. Strategy validation
# ---------------------------------------------------------------------------


class TestStrategyValidation:
    def test_valid_strategy(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[
                Strategy(
                    scope="local",
                    type="noisy_and",
                    premises=["reg:test::a"],
                    conclusion="reg:test::b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_premise(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::b")],
            strategies=[
                Strategy(
                    scope="local",
                    type="infer",
                    premises=["reg:test::missing"],
                    conclusion="reg:test::b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "not found" in e for e in r.errors)

    def test_dangling_conclusion(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a")],
            strategies=[
                Strategy(
                    scope="local",
                    type="infer",
                    premises=["reg:test::a"],
                    conclusion="reg:test::missing",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "not found" in e for e in r.errors)

    def test_premise_must_be_claim(self):
        g = _local_graph(
            knowledges=[_setting("reg:test::s"), _claim("reg:test::b")],
            strategies=[
                Strategy(
                    scope="local", type="infer", premises=["reg:test::s"], conclusion="reg:test::b"
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "must be claim" in e for e in r.errors)

    def test_conclusion_must_be_claim(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _setting("reg:test::s")],
            strategies=[
                Strategy(
                    scope="local", type="infer", premises=["reg:test::a"], conclusion="reg:test::s"
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "must be claim" in e for e in r.errors)

    def test_self_loop_rejected(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a")],
            strategies=[
                Strategy(
                    scope="local", type="infer", premises=["reg:test::a"], conclusion="reg:test::a"
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("self-loop" in e for e in r.errors)

    def test_background_warning_if_missing(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[
                Strategy(
                    scope="local",
                    type="noisy_and",
                    premises=["reg:test::a"],
                    conclusion="reg:test::b",
                    background=["reg:test::nonexistent"],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid  # warning, not error
        assert any("background" in w for w in r.warnings)

    def test_global_scope_rejected_at_construction(self):
        """Global scope is no longer allowed — Strategy model rejects it."""
        import pytest

        with pytest.raises(ValueError, match="scope must be 'local'"):
            Strategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
            )

    def test_strategy_prefix_check(self):
        """Pydantic model validation rejects wrong ID prefix at construction time."""
        import pytest

        with pytest.raises(Exception, match="lcs_ prefix"):
            Strategy(
                strategy_id="gcs_wrong",
                scope="local",
                type="infer",
                premises=["reg:test::a"],
                conclusion="reg:test::b",
            )


class TestCompositeStrategyValidation:
    def test_valid_composite_with_string_refs(self):
        """CompositeStrategy with sub_strategies as string references."""
        sub = Strategy(
            scope="local", type="noisy_and", premises=["reg:test::a"], conclusion="reg:test::b"
        )
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b"), _claim("reg:test::c")],
            strategies=[
                sub,
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    sub_strategies=[sub.strategy_id],
                ),
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_sub_strategy_ref_not_found(self):
        """CompositeStrategy referencing a non-existent sub_strategy ID."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::c")],
            strategies=[
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    sub_strategies=["lcs_nonexistent"],
                ),
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("sub_strategy" in e and "not found" in e for e in r.errors)

    def test_composite_cycle_detected(self):
        """CompositeStrategy cycle: A references B, B references A."""
        # We need to manually construct IDs to create a cycle
        # Build two composites that reference each other
        # First create a leaf strategy for valid sub_strategies
        leaf = Strategy(
            scope="local", type="noisy_and", premises=["reg:test::a"], conclusion="reg:test::b"
        )

        comp_a = CompositeStrategy(
            strategy_id="lcs_comp_a",
            scope="local",
            type="abduction",
            premises=["reg:test::a"],
            conclusion="reg:test::b",
            sub_strategies=["lcs_comp_b"],
        )
        comp_b = CompositeStrategy(
            strategy_id="lcs_comp_b",
            scope="local",
            type="abduction",
            premises=["reg:test::a"],
            conclusion="reg:test::b",
            sub_strategies=["lcs_comp_a"],
        )
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[leaf, comp_a, comp_b],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("cycle" in e.lower() for e in r.errors)

    def test_composite_no_cycle_valid(self):
        """CompositeStrategy DAG (no cycle) should pass."""
        leaf = Strategy(
            scope="local", type="noisy_and", premises=["reg:test::a"], conclusion="reg:test::b"
        )
        comp = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["reg:test::a"],
            conclusion="reg:test::b",
            sub_strategies=[leaf.strategy_id],
        )
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[leaf, comp],
        )
        r = validate_local_graph(g)
        assert r.valid


class TestFormalStrategyValidation:
    def test_valid_formal(self):
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::m"),
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["reg:test::a", "reg:test::b"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::m"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_formal_expr_dangling_ref(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::missing"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid

    def test_formal_expr_reference_closure_valid(self):
        """All operator refs within premises/conclusion/other operator conclusions."""
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::m"),
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["reg:test::a", "reg:test::b"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::m"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_formal_expr_reference_closure_violation(self):
        """Operator variable not in premises/conclusion/operator conclusions."""
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::c"),
                _claim("reg:test::outside"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::outside"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("reference closure" in e for e in r.errors)

    def test_formal_expr_private_node_isolation(self):
        """Private internal node must not be referenced by another strategy."""
        # reg:test::m is a private intermediate in the FormalStrategy
        # Another strategy should not reference it
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["reg:test::a"],
            conclusion="reg:test::c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["reg:test::a"],
                        conclusion="reg:test::m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["reg:test::m"],
                        conclusion="reg:test::c",
                    ),
                ]
            ),
        )
        # reg:test::m is private: it's an operator conclusion but NOT in any top-level
        # strategy's premises/conclusion. Another strategy references it — violation.
        other = Strategy(
            scope="local",
            type="noisy_and",
            premises=["reg:test::m"],
            conclusion="reg:test::c",
        )
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::c"), _claim("reg:test::m")],
            strategies=[formal, other],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("private internal node" in e for e in r.errors)

    def test_formal_expr_non_private_node_ok(self):
        """An operator conclusion that IS in the owning strategy's interface is not private."""
        # reg:test::c is both an operator conclusion and the FormalStrategy's conclusion,
        # so it's NOT private. Another strategy can reference it freely.
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["reg:test::a"],
            conclusion="reg:test::c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["reg:test::a"],
                        conclusion="reg:test::c",
                    ),
                ]
            ),
        )
        other = Strategy(
            scope="local",
            type="noisy_and",
            premises=["reg:test::c"],
            conclusion="reg:test::d",
        )
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::c"), _claim("reg:test::d")],
            strategies=[formal, other],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_formal_expr_cycle_detected(self):
        """FormalExpr operators that form a cycle: A->B and B->A."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b"), _claim("reg:test::c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::b"],
                                conclusion="reg:test::c",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::c"],
                                conclusion="reg:test::b",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("cycle" in e.lower() for e in r.errors)

    def test_formal_expr_no_cycle_valid(self):
        """Linear chain A->M->C has no cycle."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::m"), _claim("reg:test::c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::m"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_private_node_referenced_by_top_level_operator_variable(self):
        """Top-level operator referencing a FormalExpr private node as variable is an error."""
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["reg:test::a", "reg:test::b"],
            conclusion="reg:test::c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["reg:test::a", "reg:test::b"],
                        conclusion="reg:test::m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["reg:test::m"],
                        conclusion="reg:test::c",
                    ),
                ]
            ),
        )
        # Top-level operator uses private node reg:test::m as a variable
        top_op = Operator(
            operator_id="lco_bad",
            scope="local",
            operator="implication",
            variables=["reg:test::m"],
            conclusion="reg:test::c",
        )
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::c"),
                _claim("reg:test::m"),
            ],
            operators=[top_op],
            strategies=[formal],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("private internal node" in e for e in r.errors)

    def test_private_node_referenced_by_top_level_operator_conclusion(self):
        """Top-level operator using a FormalExpr private node as conclusion is an error."""
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["reg:test::a", "reg:test::b"],
            conclusion="reg:test::c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["reg:test::a", "reg:test::b"],
                        conclusion="reg:test::m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["reg:test::m"],
                        conclusion="reg:test::c",
                    ),
                ]
            ),
        )
        # Top-level operator outputs to private node reg:test::m
        top_op = Operator(
            operator_id="lco_bad",
            scope="local",
            operator="implication",
            variables=["reg:test::a"],
            conclusion="reg:test::m",
        )
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::c"),
                _claim("reg:test::m"),
            ],
            operators=[top_op],
            strategies=[formal],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("private internal node" in e for e in r.errors)


# ---------------------------------------------------------------------------
# 4. Graph-level validation
# ---------------------------------------------------------------------------


class TestGraphLevelValidation:
    def test_scope_consistency_local(self):
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[
                Strategy(
                    scope="local", type="infer", premises=["gcn_wrong"], conclusion="reg:test::b"
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong format" in e for e in r.errors)

    def test_operator_conclusion_scope_prefix(self):
        """Operator conclusion with wrong prefix is caught in scope consistency."""
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["reg:test::a"],
                    conclusion="gcn_wrong",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        # Should have wrong format error for conclusion
        assert any("wrong format" in e or "not found" in e for e in r.errors)

    def test_formal_expr_operator_scope_prefix(self):
        """FormalExpr-embedded operators with wrong prefix are caught in scope consistency."""
        # reg:test::a and reg:test::c exist in local graph, but FormalExpr internally
        # references gcn_wrong which has a global prefix in a local graph.
        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::c"), _claim("reg:test::m")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["gcn_wrong"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong format" in e and "FormalStrategy" in e for e in r.errors)

    def test_hash_consistency(self):
        g = _local_graph(knowledges=[_claim("reg:test::a")])
        r = validate_local_graph(g)
        assert r.valid  # auto-computed hash should match

    def test_hash_mismatch(self):
        g = _local_graph(knowledges=[_claim("reg:test::a")])
        g.ir_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        r = validate_local_graph(g)
        assert not r.valid
        assert any("ir_hash mismatch" in e for e in r.errors)

    def test_empty_graph_valid(self):
        r = validate_local_graph(_local_graph())
        assert r.valid


# ---------------------------------------------------------------------------
# 5. Parameterization completeness
# ---------------------------------------------------------------------------


class TestParameterizationValidation:
    def _graph(self):
        return _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _setting("reg:test::s"),
            ],
            strategies=[
                Strategy(
                    scope="local",
                    type="noisy_and",
                    premises=["reg:test::a"],
                    conclusion="reg:test::b",
                ),
            ],
        )

    def test_complete_parameterization(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid

    def test_missing_prior(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert not r.valid
        assert any("reg:test::b" in e and "missing PriorRecord" in e for e in r.errors)

    def test_missing_strategy_param_for_parameterized(self):
        from gaia.ir import PriorRecord

        g = self._graph()
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.7, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("missing StrategyParamRecord" in e for e in r.errors)

    def test_formal_strategy_without_params_passes(self):
        """FormalStrategy types do not need StrategyParamRecord."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::m"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::b",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::b",
                            ),
                        ]
                    ),
                ),
            ],
        )
        # reg:test::m is not referenced by any FormalExpr operator, so it's a regular claim
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::m", value=0.5, source_id="s"),
            ],
            strategy_params=[],  # no params needed for deduction
        )
        assert r.valid

    def test_private_helper_claim_no_prior_needed(self):
        """Private helper claims (FormalExpr internal) don't need PriorRecord."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::m"),  # private helper: conjunction result
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["reg:test::a", "reg:test::b"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::m"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        # reg:test::m is private (operator conclusion, not in premises/conclusion)
        # -> no PriorRecord needed
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
                # no prior for reg:test::m
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_private_helper_claim_prior_prohibited(self):
        """Providing PriorRecord for a private helper claim is an error."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::m"),
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["reg:test::a", "reg:test::b"],
                                conclusion="reg:test::m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::m"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::m", value=0.5, source_id="s"),  # prohibited!
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("private or structural helper claim" in e for e in r.errors)

    def test_implication_private_node_prior_prohibited(self):
        """Any FormalExpr private node (not just structural helpers) must not have PriorRecord."""
        from gaia.ir import PriorRecord

        # reg:test::mid is an implication conclusion inside FormalExpr, NOT in the
        # strategy's interface (premises/conclusion). Even though implication is
        # not a "structural helper" operator type, reg:test::mid is still private.
        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::mid"),
                _claim("reg:test::final"),
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::mid",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::mid"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::final", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::mid", value=0.5, source_id="s"),  # prohibited!
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("reg:test::mid" in e and "private or structural helper" in e for e in r.errors)

    def test_implication_private_node_no_prior_needed(self):
        """FormalExpr private implication nodes don't need PriorRecord."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::mid"),
                _claim("reg:test::c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::mid",
                            ),
                            Operator(
                                operator="implication",
                                variables=["reg:test::mid"],
                                conclusion="reg:test::c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
                # reg:test::mid is private -- no prior needed
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_abduction_generated_interface_claim_requires_prior(self):
        """Auto-generated alternative explanations are public interface claims with priors."""
        from gaia.ir import PriorRecord

        formalized = Strategy(
            scope="local",
            type="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
        ).formalize(namespace="reg", package_name="test")
        alternative_explanation = next(
            knowledge
            for knowledge in formalized.knowledges
            if knowledge.metadata.get("interface_role") == "alternative_explanation"
        )

        g = _local_graph(
            knowledges=[
                _claim("reg:test::obs"),
                _claim("reg:test::h"),
                *formalized.knowledges,
            ],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::obs", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::h", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any(alternative_explanation.id in e and "missing PriorRecord" in e for e in r.errors)

    def test_abduction_generated_interface_claim_prior_allowed(self):
        """The generated alternative explanation can be parameterized like any public claim."""
        from gaia.ir import PriorRecord

        formalized = Strategy(
            scope="local",
            type="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
        ).formalize(namespace="reg", package_name="test")
        alternative_explanation = next(
            knowledge
            for knowledge in formalized.knowledges
            if knowledge.metadata.get("interface_role") == "alternative_explanation"
        )

        g = _local_graph(
            knowledges=[
                _claim("reg:test::obs"),
                _claim("reg:test::h"),
                *formalized.knowledges,
            ],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::obs", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::h", value=0.5, source_id="s"),
                PriorRecord(knowledge_id=alternative_explanation.id, value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_elimination_only_requires_interface_priors(self):
        """Strict elimination should not introduce hidden prior-bearing internal claims."""
        from gaia.ir import PriorRecord

        formalized = Strategy(
            scope="local",
            type="elimination",
            premises=[
                "reg:test::exhaustive",
                "reg:test::h1",
                "reg:test::e1",
                "reg:test::h2",
                "reg:test::e2",
            ],
            conclusion="reg:test::h3",
        ).formalize(namespace="reg", package_name="test")

        g = _local_graph(
            knowledges=[
                _claim("reg:test::exhaustive"),
                _claim("reg:test::h1"),
                _claim("reg:test::e1"),
                _claim("reg:test::h2"),
                _claim("reg:test::e2"),
                _claim("reg:test::h3"),
                *formalized.knowledges,
            ],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::exhaustive", value=0.9, source_id="s"),
                PriorRecord(knowledge_id="reg:test::h1", value=0.2, source_id="s"),
                PriorRecord(knowledge_id="reg:test::e1", value=0.9, source_id="s"),
                PriorRecord(knowledge_id="reg:test::h2", value=0.2, source_id="s"),
                PriorRecord(knowledge_id="reg:test::e2", value=0.9, source_id="s"),
                PriorRecord(knowledge_id="reg:test::h3", value=0.2, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_top_level_helper_claim_no_prior_needed(self):
        """Top-level structural helper claims should also be excluded from prior coverage."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::eq"),
            ],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::eq",
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_top_level_helper_claim_prior_prohibited(self):
        """Top-level structural helper claims must not accept independent priors."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::eq"),
            ],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::eq",
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::eq", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any(
            "reg:test::eq" in e and "private or structural helper claim" in e for e in r.errors
        )

    def test_param_for_non_parameterized_type_warns(self):
        """StrategyParamRecord for a FormalStrategy type should warn."""
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = _local_graph(
            knowledges=[_claim("reg:test::a"), _claim("reg:test::b")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["reg:test::a"],
                    conclusion="reg:test::b",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["reg:test::a"],
                                conclusion="reg:test::b",
                            ),
                        ]
                    ),
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.5], source_id="s"
                ),
            ],
        )
        assert r.valid  # warning, not error
        assert any("not parameterized" in w for w in r.warnings)

    def test_setting_does_not_need_prior(self):
        """Settings don't carry probability -- no PriorRecord needed."""
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid  # reg:test::s (setting) doesn't need a prior

    def test_cromwell_bounds_on_priors(self):
        """PriorRecord auto-clamps, so raw values within bounds should pass."""
        from gaia.ir import PriorRecord

        g = _local_graph(
            knowledges=[_claim("reg:test::a")],
            strategies=[],
        )
        r = validate_parameterization(
            g,
            priors=[PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s")],
            strategy_params=[],
        )
        assert r.valid

    def test_dangling_prior_warning(self):
        from gaia.ir import PriorRecord

        g = _local_graph(knowledges=[_claim("reg:test::a")])
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::nonexistent", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid  # warning, not error
        assert any("non-existent" in w for w in r.warnings)

    def test_dangling_strategy_param_warning(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = _local_graph(knowledges=[_claim("reg:test::a")])
        r = validate_parameterization(
            g,
            priors=[PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id="lcs_ghost", conditional_probabilities=[0.5], source_id="s"
                ),
            ],
        )
        assert r.valid
        assert any("non-existent" in w for w in r.warnings)

    def test_empty_graph_no_requirements(self):
        r = validate_parameterization(_local_graph(), [], [])
        assert r.valid

    def test_noisy_and_wrong_arity_rejected(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.2, 0.3, 0.4, 0.5],
                    source_id="s",
                ),
            ],
        )
        assert not r.valid
        assert any("noisy_and" in e and "requires 1" in e for e in r.errors)

    def test_infer_wrong_arity_rejected(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::c"),
            ],
            strategies=[
                Strategy(
                    scope="local",
                    type="infer",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.8, 0.9],  # needs 2^2=4
                    source_id="s",
                ),
            ],
        )
        assert not r.valid
        assert any("2^2=4" in e for e in r.errors)

    def test_infer_correct_arity_passes(self):
        from gaia.ir import PriorRecord, StrategyParamRecord

        g = _local_graph(
            knowledges=[
                _claim("reg:test::a"),
                _claim("reg:test::b"),
                _claim("reg:test::c"),
            ],
            strategies=[
                Strategy(
                    scope="local",
                    type="infer",
                    premises=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(knowledge_id="reg:test::a", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::b", value=0.5, source_id="s"),
                PriorRecord(knowledge_id="reg:test::c", value=0.5, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.8, 0.7, 0.6, 0.9],
                    source_id="s",
                ),
            ],
        )
        assert r.valid
