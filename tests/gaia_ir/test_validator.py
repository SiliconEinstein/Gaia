"""Tests for Gaia IR validator."""

from gaia.gaia_ir import (
    Knowledge,
    KnowledgeType,
    Operator,
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
)
from gaia.gaia_ir.validator import (
    validate_local_graph,
    validate_global_graph,
    validate_parameterization,
    validate_bindings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim(id: str, content: str = "test") -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.CLAIM, content=content)


def _setting(id: str) -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.SETTING)


def _local_graph(**kwargs) -> LocalCanonicalGraph:
    defaults = {"knowledges": [], "operators": [], "strategies": []}
    defaults.update(kwargs)
    return LocalCanonicalGraph(**defaults)


def _global_graph(**kwargs) -> GlobalCanonicalGraph:
    defaults = {"knowledges": [], "operators": [], "strategies": []}
    defaults.update(kwargs)
    return GlobalCanonicalGraph(**defaults)


# ---------------------------------------------------------------------------
# 1. Knowledge validation
# ---------------------------------------------------------------------------


class TestKnowledgeValidation:
    def test_valid_local(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        r = validate_local_graph(g)
        assert r.valid

    def test_wrong_prefix_local(self):
        g = _local_graph(knowledges=[_claim("gcn_wrong")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("prefix" in e for e in r.errors)

    def test_wrong_prefix_global(self):
        g = _global_graph(knowledges=[_claim("lcn_wrong")])
        r = validate_global_graph(g)
        assert not r.valid

    def test_duplicate_id(self):
        g = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_a", "other")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("duplicate" in e for e in r.errors)

    def test_claim_without_content_or_repr(self):
        k = Knowledge(id="gcn_bad", type=KnowledgeType.CLAIM)
        g = _global_graph(knowledges=[k])
        r = validate_global_graph(g)
        assert not r.valid
        assert any("content or representative_lcn" in e for e in r.errors)

    def test_claim_with_representative_lcn_ok(self):
        from gaia.gaia_ir import LocalCanonicalRef

        k = Knowledge(
            id="gcn_ok",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_x", package_id="pkg", version="1"
            ),
        )
        g = _global_graph(knowledges=[k])
        r = validate_global_graph(g)
        assert r.valid

    def test_local_knowledge_must_have_content(self):
        k = Knowledge(id="lcn_a", type=KnowledgeType.CLAIM)
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("content" in e for e in r.errors)

    def test_local_knowledge_must_not_have_representative_lcn(self):
        from gaia.gaia_ir import LocalCanonicalRef

        k = Knowledge(
            id="lcn_a",
            type=KnowledgeType.CLAIM,
            content="test",
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_x", package_id="pkg", version="1"
            ),
        )
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("representative_lcn" in e for e in r.errors)

    def test_local_knowledge_must_not_have_local_members(self):
        from gaia.gaia_ir import LocalCanonicalRef

        k = Knowledge(
            id="lcn_a",
            type=KnowledgeType.CLAIM,
            content="test",
            local_members=[
                LocalCanonicalRef(local_canonical_id="lcn_x", package_id="pkg", version="1")
            ],
        )
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("local_members" in e for e in r.errors)


# ---------------------------------------------------------------------------
# 2. Operator validation
# ---------------------------------------------------------------------------


class TestOperatorValidation:
    def test_valid_operator_equivalence(self):
        """Equivalence: 2 variables + conclusion (helper claim)."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["lcn_a", "lcn_b"],
                    conclusion="lcn_h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_valid_operator_implication(self):
        """Implication: 1 variable + conclusion."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="lcn_b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_valid_operator_conjunction(self):
        """Conjunction: >=2 variables + conclusion."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_m")],
            operators=[
                Operator(
                    operator_id="lco_and",
                    scope="local",
                    operator="conjunction",
                    variables=["lcn_a", "lcn_b"],
                    conclusion="lcn_m",
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_variable_reference(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["lcn_a", "lcn_missing"],
                    conclusion="lcn_h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("not found" in e for e in r.errors)

    def test_dangling_conclusion_reference(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="lcn_missing",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "not found" in e for e in r.errors)

    def test_operator_variable_on_non_claim(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _setting("lcn_s"), _claim("lcn_h")],
            operators=[
                Operator(
                    operator_id="lco_eq",
                    scope="local",
                    operator="equivalence",
                    variables=["lcn_a", "lcn_s"],
                    conclusion="lcn_h",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("must be claim" in e for e in r.errors)

    def test_operator_conclusion_on_non_claim(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _setting("lcn_s")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="lcn_s",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "must be claim" in e for e in r.errors)

    def test_local_graph_rejects_global_scoped_operator(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[
                Operator(
                    operator_id="gco_bad",
                    scope="global",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="lcn_b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)

    def test_global_graph_rejects_local_scoped_operator(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            operators=[
                Operator(
                    operator_id="lco_bad",
                    scope="local",
                    operator="implication",
                    variables=["gcn_a"],
                    conclusion="gcn_b",
                )
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)

    def test_operator_conclusion_scope_prefix_check(self):
        """Operator conclusion should have correct scope prefix."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="gcn_wrong",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong prefix" in e or "not found" in e for e in r.errors)

    def test_top_level_operator_requires_scope_and_id(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[Operator(operator="implication", variables=["lcn_a"], conclusion="lcn_b")],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("Top-level Operator must set both operator_id and scope" in e for e in r.errors)


# ---------------------------------------------------------------------------
# 3. Strategy validation
# ---------------------------------------------------------------------------


class TestStrategyValidation:
    def test_valid_strategy(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_premise(self):
        g = _local_graph(
            knowledges=[_claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_missing"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "not found" in e for e in r.errors)

    def test_dangling_conclusion(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_missing")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "not found" in e for e in r.errors)

    def test_premise_must_be_claim(self):
        g = _local_graph(
            knowledges=[_setting("lcn_s"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_s"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "must be claim" in e for e in r.errors)

    def test_conclusion_must_be_claim(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _setting("lcn_s")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_s")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "must be claim" in e for e in r.errors)

    def test_self_loop_rejected(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_a")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("self-loop" in e for e in r.errors)

    def test_background_warning_if_missing(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(
                    scope="local",
                    type="noisy_and",
                    premises=["lcn_a"],
                    conclusion="lcn_b",
                    background=["lcn_nonexistent"],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid  # warning, not error
        assert any("background" in w for w in r.warnings)

    def test_global_strategy_rejects_steps(self):
        """Pydantic model validation rejects steps on global Strategy at construction time."""
        import pytest
        from gaia.gaia_ir import Step

        with pytest.raises(Exception, match="global Strategy must not carry steps"):
            Strategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
                steps=[Step(reasoning="should not be here")],
            )

    def test_strategy_prefix_check(self):
        """Pydantic model validation rejects wrong ID prefix at construction time."""
        import pytest

        with pytest.raises(Exception, match="lcs_ prefix"):
            Strategy(
                strategy_id="gcs_wrong",
                scope="local",
                type="infer",
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_local_graph_rejects_global_scoped_strategy(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="global", type="infer", premises=["lcn_a"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)

    def test_global_graph_rejects_local_scoped_strategy(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["gcn_a"], conclusion="gcn_b")
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)


class TestCompositeStrategyValidation:
    def test_valid_composite_with_string_refs(self):
        """CompositeStrategy with sub_strategies as string references."""
        sub = Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_c")],
            strategies=[
                sub,
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    sub_strategies=[sub.strategy_id],
                ),
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_sub_strategy_ref_not_found(self):
        """CompositeStrategy referencing a non-existent sub_strategy ID."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
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
        leaf = Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")

        comp_a = CompositeStrategy(
            strategy_id="lcs_comp_a",
            scope="local",
            type="abduction",
            premises=["lcn_a"],
            conclusion="lcn_b",
            sub_strategies=["lcs_comp_b"],
        )
        comp_b = CompositeStrategy(
            strategy_id="lcs_comp_b",
            scope="local",
            type="abduction",
            premises=["lcn_a"],
            conclusion="lcn_b",
            sub_strategies=["lcs_comp_a"],
        )
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[leaf, comp_a, comp_b],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("cycle" in e.lower() for e in r.errors)

    def test_composite_no_cycle_valid(self):
        """CompositeStrategy DAG (no cycle) should pass."""
        leaf = Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
        comp = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["lcn_a"],
            conclusion="lcn_b",
            sub_strategies=[leaf.strategy_id],
        )
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[leaf, comp],
        )
        r = validate_local_graph(g)
        assert r.valid


class TestFormalStrategyValidation:
    def test_valid_formal(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_m"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a", "lcn_b"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["lcn_a", "lcn_b"],
                                conclusion="lcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["lcn_m"],
                                conclusion="lcn_c",
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
            knowledges=[_claim("lcn_a"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_missing"],
                                conclusion="lcn_c",
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
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_m"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a", "lcn_b"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["lcn_a", "lcn_b"],
                                conclusion="lcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["lcn_m"],
                                conclusion="lcn_c",
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
                _claim("lcn_a"),
                _claim("lcn_c"),
                _claim("lcn_outside"),
            ],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_outside"],
                                conclusion="lcn_c",
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
        # lcn_m is a private intermediate in the FormalStrategy
        # Another strategy should not reference it
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["lcn_a"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["lcn_a"],
                        conclusion="lcn_m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["lcn_m"],
                        conclusion="lcn_c",
                    ),
                ]
            ),
        )
        # lcn_m is private: it's an operator conclusion but NOT in any top-level
        # strategy's premises/conclusion. Another strategy references it — violation.
        other = Strategy(
            scope="local",
            type="noisy_and",
            premises=["lcn_m"],
            conclusion="lcn_c",
        )
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c"), _claim("lcn_m")],
            strategies=[formal, other],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("private internal node" in e for e in r.errors)

    def test_formal_expr_non_private_node_ok(self):
        """An operator conclusion that IS in the owning strategy's interface is not private."""
        # lcn_c is both an operator conclusion and the FormalStrategy's conclusion,
        # so it's NOT private. Another strategy can reference it freely.
        formal = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["lcn_a"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["lcn_a"],
                        conclusion="lcn_c",
                    ),
                ]
            ),
        )
        other = Strategy(
            scope="local",
            type="noisy_and",
            premises=["lcn_c"],
            conclusion="lcn_d",
        )
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c"), _claim("lcn_d")],
            strategies=[formal, other],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_formal_expr_cycle_detected(self):
        """FormalExpr operators that form a cycle: A->B and B->A."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_b"],
                                conclusion="lcn_c",
                            ),
                            Operator(
                                operator="implication",
                                variables=["lcn_c"],
                                conclusion="lcn_b",
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
            knowledges=[_claim("lcn_a"), _claim("lcn_m"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_a"],
                                conclusion="lcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["lcn_m"],
                                conclusion="lcn_c",
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
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["lcn_a", "lcn_b"],
                        conclusion="lcn_m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["lcn_m"],
                        conclusion="lcn_c",
                    ),
                ]
            ),
        )
        # Top-level operator uses private node lcn_m as a variable
        top_op = Operator(
            operator_id="lco_bad",
            scope="local",
            operator="implication",
            variables=["lcn_m"],
            conclusion="lcn_c",
        )
        g = _local_graph(
            knowledges=[
                _claim("lcn_a"),
                _claim("lcn_b"),
                _claim("lcn_c"),
                _claim("lcn_m"),
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
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["lcn_a", "lcn_b"],
                        conclusion="lcn_m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["lcn_m"],
                        conclusion="lcn_c",
                    ),
                ]
            ),
        )
        # Top-level operator outputs to private node lcn_m
        top_op = Operator(
            operator_id="lco_bad",
            scope="local",
            operator="implication",
            variables=["lcn_a"],
            conclusion="lcn_m",
        )
        g = _local_graph(
            knowledges=[
                _claim("lcn_a"),
                _claim("lcn_b"),
                _claim("lcn_c"),
                _claim("lcn_m"),
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
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["gcn_wrong"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong prefix" in e for e in r.errors)

    def test_scope_consistency_global(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                Strategy(scope="global", type="infer", premises=["lcn_wrong"], conclusion="gcn_b")
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid

    def test_operator_conclusion_scope_prefix(self):
        """Operator conclusion with wrong prefix is caught in scope consistency."""
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[
                Operator(
                    operator_id="lco_impl",
                    scope="local",
                    operator="implication",
                    variables=["lcn_a"],
                    conclusion="gcn_wrong",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        # Should have wrong prefix error for conclusion
        assert any("wrong prefix" in e or "not found" in e for e in r.errors)

    def test_formal_expr_operator_scope_prefix(self):
        """FormalExpr-embedded operators with wrong prefix are caught in scope consistency."""
        # lcn_a and lcn_c exist in local graph, but FormalExpr internally
        # references gcn_wrong which has a global prefix in a local graph.
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c"), _claim("lcn_m")],
            strategies=[
                FormalStrategy(
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_a"],
                                conclusion="lcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["gcn_wrong"],
                                conclusion="lcn_c",
                            ),
                        ]
                    ),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong prefix" in e and "FormalStrategy" in e for e in r.errors)

    def test_hash_consistency(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        r = validate_local_graph(g)
        assert r.valid  # auto-computed hash should match

    def test_hash_mismatch(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        g.ir_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        r = validate_local_graph(g)
        assert not r.valid
        assert any("ir_hash mismatch" in e for e in r.errors)

    def test_empty_graph_valid(self):
        r = validate_local_graph(_local_graph())
        assert r.valid

    def test_empty_global_valid(self):
        r = validate_global_graph(_global_graph())
        assert r.valid


# ---------------------------------------------------------------------------
# 5. Parameterization completeness
# ---------------------------------------------------------------------------


class TestParameterizationValidation:
    def _graph(self):
        return _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _setting("gcn_s")],
            strategies=[
                Strategy(scope="global", type="noisy_and", premises=["gcn_a"], conclusion="gcn_b"),
            ],
        )

    def test_complete_parameterization(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid

    def test_missing_prior(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert not r.valid
        assert any("gcn_b" in e and "missing PriorRecord" in e for e in r.errors)

    def test_missing_strategy_param_for_parameterized(self):
        from gaia.gaia_ir import PriorRecord

        g = self._graph()
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("missing StrategyParamRecord" in e for e in r.errors)

    def test_formal_strategy_without_params_passes(self):
        """FormalStrategy types do not need StrategyParamRecord."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_m")],
            strategies=[
                FormalStrategy(
                    scope="global",
                    type="deduction",
                    premises=["gcn_a"],
                    conclusion="gcn_b",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["gcn_a"],
                                conclusion="gcn_b",
                            ),
                        ]
                    ),
                ),
            ],
        )
        # gcn_m is not referenced by any FormalExpr operator, so it's a regular claim
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_m", value=0.5, source_id="s"),
            ],
            strategy_params=[],  # no params needed for deduction
        )
        assert r.valid

    def test_private_helper_claim_no_prior_needed(self):
        """Private helper claims (FormalExpr internal) don't need PriorRecord."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[
                _claim("gcn_a"),
                _claim("gcn_b"),
                _claim("gcn_m"),  # private helper: conjunction result
                _claim("gcn_c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="global",
                    type="deduction",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["gcn_a", "gcn_b"],
                                conclusion="gcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["gcn_m"],
                                conclusion="gcn_c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        # gcn_m is private (operator conclusion, not in premises/conclusion)
        # → no PriorRecord needed
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
                # no prior for gcn_m
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_private_helper_claim_prior_prohibited(self):
        """Providing PriorRecord for a private helper claim is an error."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[
                _claim("gcn_a"),
                _claim("gcn_b"),
                _claim("gcn_m"),
                _claim("gcn_c"),
            ],
            strategies=[
                FormalStrategy(
                    scope="global",
                    type="deduction",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["gcn_a", "gcn_b"],
                                conclusion="gcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["gcn_m"],
                                conclusion="gcn_c",
                            ),
                        ]
                    ),
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_m", value=0.5, source_id="s"),  # prohibited!
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("structural helper claim" in e for e in r.errors)

    def test_abduction_generated_interface_claim_requires_prior(self):
        """Auto-generated alternative explanations are public interface claims with priors."""
        from gaia.gaia_ir import PriorRecord

        formalized = Strategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
        ).formalize()
        alternative_explanation = next(
            knowledge
            for knowledge in formalized.knowledges
            if knowledge.metadata.get("interface_role") == "alternative_explanation"
        )

        g = _global_graph(
            knowledges=[_claim("gcn_obs"), _claim("gcn_h"), *formalized.knowledges],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_obs", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_h", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any(alternative_explanation.id in e and "missing PriorRecord" in e for e in r.errors)

    def test_abduction_generated_interface_claim_prior_allowed(self):
        """The generated alternative explanation can be parameterized like any public claim."""
        from gaia.gaia_ir import PriorRecord

        formalized = Strategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
        ).formalize()
        alternative_explanation = next(
            knowledge
            for knowledge in formalized.knowledges
            if knowledge.metadata.get("interface_role") == "alternative_explanation"
        )

        g = _global_graph(
            knowledges=[_claim("gcn_obs"), _claim("gcn_h"), *formalized.knowledges],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_obs", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_h", value=0.5, source_id="s"),
                PriorRecord(gcn_id=alternative_explanation.id, value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_elimination_only_requires_interface_priors(self):
        """Strict elimination should not introduce hidden prior-bearing internal claims."""
        from gaia.gaia_ir import PriorRecord

        formalized = Strategy(
            scope="global",
            type="elimination",
            premises=[
                "gcn_exhaustive",
                "gcn_h1",
                "gcn_e1",
                "gcn_h2",
                "gcn_e2",
            ],
            conclusion="gcn_h3",
        ).formalize()

        g = _global_graph(
            knowledges=[
                _claim("gcn_exhaustive"),
                _claim("gcn_h1"),
                _claim("gcn_e1"),
                _claim("gcn_h2"),
                _claim("gcn_e2"),
                _claim("gcn_h3"),
                *formalized.knowledges,
            ],
            strategies=[formalized.strategy],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_exhaustive", value=0.9, source_id="s"),
                PriorRecord(gcn_id="gcn_h1", value=0.2, source_id="s"),
                PriorRecord(gcn_id="gcn_e1", value=0.9, source_id="s"),
                PriorRecord(gcn_id="gcn_h2", value=0.2, source_id="s"),
                PriorRecord(gcn_id="gcn_e2", value=0.9, source_id="s"),
                PriorRecord(gcn_id="gcn_h3", value=0.2, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_top_level_helper_claim_no_prior_needed(self):
        """Top-level structural helper claims should also be excluded from prior coverage."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_eq")],
            operators=[
                Operator(
                    operator_id="gco_eq",
                    scope="global",
                    operator="equivalence",
                    variables=["gcn_a", "gcn_b"],
                    conclusion="gcn_eq",
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid

    def test_top_level_helper_claim_prior_prohibited(self):
        """Top-level structural helper claims must not accept independent priors."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_eq")],
            operators=[
                Operator(
                    operator_id="gco_eq",
                    scope="global",
                    operator="equivalence",
                    variables=["gcn_a", "gcn_b"],
                    conclusion="gcn_eq",
                ),
            ],
        )
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_eq", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("gcn_eq" in e and "structural helper claim" in e for e in r.errors)

    def test_param_for_non_parameterized_type_warns(self):
        """StrategyParamRecord for a FormalStrategy type should warn."""
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                FormalStrategy(
                    scope="global",
                    type="deduction",
                    premises=["gcn_a"],
                    conclusion="gcn_b",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["gcn_a"],
                                conclusion="gcn_b",
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
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
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
        """Settings don't carry probability — no PriorRecord needed."""
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid  # gcn_s (setting) doesn't need a prior

    def test_cromwell_bounds_on_priors(self):
        """PriorRecord auto-clamps, so raw values within bounds should pass."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a")],
            strategies=[],
        )
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[],
        )
        assert r.valid

    def test_dangling_prior_warning(self):
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(knowledges=[_claim("gcn_a")])
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_nonexistent", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid  # warning, not error
        assert any("non-existent" in w for w in r.warnings)

    def test_dangling_strategy_param_warning(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(knowledges=[_claim("gcn_a")])
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id="gcs_ghost", conditional_probabilities=[0.5], source_id="s"
                ),
            ],
        )
        assert r.valid
        assert any("non-existent" in w for w in r.warnings)

    def test_empty_graph_no_requirements(self):
        r = validate_parameterization(_global_graph(), [], [])
        assert r.valid

    def test_noisy_and_wrong_arity_rejected(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
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
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_c")],
            strategies=[
                Strategy(
                    scope="global",
                    type="infer",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
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
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_c")],
            strategies=[
                Strategy(
                    scope="global",
                    type="infer",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
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


# ---------------------------------------------------------------------------
# 6. CanonicalBinding validation
# ---------------------------------------------------------------------------


class TestBindingValidation:
    def test_valid_bindings(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_b")])
        global_ = _global_graph(knowledges=[_claim("gcn_x"), _claim("gcn_y")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="similarity 0.95",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_b",
                global_canonical_id="gcn_y",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="no match",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert r.valid

    def test_missing_binding(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_b")])
        global_ = _global_graph(knowledges=[_claim("gcn_x")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="match",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("lcn_b" in e and "no CanonicalBinding" in e for e in r.errors)

    def test_duplicate_binding(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[_claim("gcn_x"), _claim("gcn_y")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="first",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_y",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="second",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("2 bindings" in e for e in r.errors)

    def test_binding_dangling_local(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[_claim("gcn_x")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="ok",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_ghost",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="dangling",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("not found in local" in e for e in r.errors)

    def test_binding_dangling_global(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_ghost",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="dangling global",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("not found in global" in e for e in r.errors)

    def test_empty_bindings_for_empty_graph(self):
        r = validate_bindings([], _local_graph(), _global_graph())
        assert r.valid
