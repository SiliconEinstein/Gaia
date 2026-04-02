"""Tests for Strategy data model (Strategy, CompositeStrategy, FormalStrategy)."""

import pytest
from gaia.gaia_ir import (
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    StrategyType,
    Step,
    Operator,
)


class TestStrategyType:
    def test_ten_types(self):
        assert len(StrategyType) == 10
        expected = {
            "infer",
            "noisy_and",
            "deduction",
            "reductio",
            "elimination",
            "mathematical_induction",
            "case_analysis",
            "abduction",
            "analogy",
            "extrapolation",
        }
        assert set(StrategyType) == expected

    def test_no_toolcall(self):
        """toolcall is deferred per spec."""
        with pytest.raises(ValueError):
            StrategyType("toolcall")

    def test_no_proof(self):
        """proof is deferred per spec."""
        with pytest.raises(ValueError):
            StrategyType("proof")

    def test_no_soft_implication(self):
        """soft_implication merged into noisy_and per spec."""
        with pytest.raises(ValueError):
            StrategyType("soft_implication")

    def test_binding_deferred(self):
        """binding is deferred outside Gaia IR core."""
        with pytest.raises(ValueError):
            StrategyType("binding")

    def test_independent_evidence_deferred(self):
        """independent_evidence is deferred outside Gaia IR core."""
        with pytest.raises(ValueError):
            StrategyType("independent_evidence")

    def test_induction_deferred(self):
        """induction is deferred in Gaia IR core and may return as authoring sugar later."""
        with pytest.raises(ValueError):
            StrategyType("induction")


class TestStrategyCreation:
    def test_basic_strategy(self):
        s = Strategy(
            scope="local", type="noisy_and", premises=["reg:test::a"], conclusion="reg:test::b"
        )
        assert s.strategy_id.startswith("lcs_")
        assert s.type == StrategyType.NOISY_AND

    def test_global_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be 'local'"):
            Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")

    def test_auto_id_deterministic(self):
        s1 = Strategy(scope="local", type="infer", premises=["a", "b"], conclusion="c")
        s2 = Strategy(scope="local", type="infer", premises=["b", "a"], conclusion="c")
        assert s1.strategy_id == s2.strategy_id  # sorted premises

    def test_different_type_different_id(self):
        s1 = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        s2 = Strategy(scope="local", type="noisy_and", premises=["a"], conclusion="b")
        assert s1.strategy_id != s2.strategy_id

    def test_with_background(self):
        s = Strategy(
            scope="local",
            type="noisy_and",
            premises=["reg:test::a"],
            conclusion="reg:test::b",
            background=["reg:test::setting"],
        )
        assert s.background == ["reg:test::setting"]

    def test_with_steps(self):
        s = Strategy(
            scope="local",
            type="infer",
            premises=["reg:test::a"],
            conclusion="reg:test::b",
            steps=[Step(reasoning="observed correlation")],
        )
        assert len(s.steps) == 1

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be 'local'"):
            Strategy(scope="detached", type="infer", premises=["a"], conclusion="b")

    def test_leaf_allows_named_strategy_type(self):
        """Per §3.5.1, named strategies can exist as leaf before formalization."""
        s = Strategy(
            scope="local", type="deduction", premises=["reg:test::a"], conclusion="reg:test::b"
        )
        assert s.type == StrategyType.DEDUCTION
        assert s.strategy_id.startswith("lcs_")

    def test_leaf_structure_hash_empty(self):
        """Leaf strategies have empty structure hash."""
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert s._structure_hash() == ""


class TestCompositeStrategy:
    def test_creation_with_string_refs(self):
        cs = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
            sub_strategies=["lcs_abc123", "lcs_def456"],
        )
        assert len(cs.sub_strategies) == 2
        assert cs.sub_strategies[0] == "lcs_abc123"
        assert isinstance(cs, Strategy)

    def test_empty_sub_strategies_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeStrategy(
                scope="local",
                type="abduction",
                premises=["reg:test::a"],
                conclusion="reg:test::b",
                sub_strategies=[],
            )

    def test_any_type_allowed(self):
        """CompositeStrategy is a generic container -- any type is valid."""
        for type_ in StrategyType:
            cs = CompositeStrategy(
                scope="local",
                type=type_,
                premises=["reg:test::a"],
                conclusion="reg:test::b",
                sub_strategies=["lcs_abc123"],
            )
            assert cs.type == type_

    def test_structure_hash_from_sorted_sub_strategies(self):
        """structure_hash is based on sorted sub_strategy IDs."""
        cs1 = CompositeStrategy(
            scope="local",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["lcs_x", "lcs_y"],
        )
        cs2 = CompositeStrategy(
            scope="local",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["lcs_y", "lcs_x"],
        )
        # Same sorted sub_strategies => same ID
        assert cs1.strategy_id == cs2.strategy_id

    def test_different_sub_strategies_different_id(self):
        """Different sub_strategies produce different strategy IDs."""
        cs1 = CompositeStrategy(
            scope="local",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["lcs_x"],
        )
        cs2 = CompositeStrategy(
            scope="local",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["lcs_z"],
        )
        assert cs1.strategy_id != cs2.strategy_id

    def test_structure_hash_affects_id(self):
        """CompositeStrategy ID differs from leaf Strategy ID with same scope/type/premises/conclusion."""
        leaf = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        comp = CompositeStrategy(
            scope="local",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["lcs_sub1"],
        )
        assert leaf.strategy_id != comp.strategy_id


class TestFormalStrategy:
    def test_deduction(self):
        """Deduction: conjunction + implication."""
        fs = FormalStrategy(
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
        assert fs.type == StrategyType.DEDUCTION
        assert len(fs.formal_expr.operators) == 2
        assert isinstance(fs, Strategy)

    def test_reductio_formal_strategy_deferred(self):
        with pytest.raises(ValueError, match="FormalStrategy form only allows types"):
            FormalStrategy(
                scope="local",
                type="reductio",
                premises=["reg:test::r"],
                conclusion="reg:test::not_p",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["reg:test::p"],
                            conclusion="reg:test::q",
                        ),
                        Operator(
                            operator="contradiction",
                            variables=["reg:test::q", "reg:test::r"],
                            conclusion="reg:test::contra",
                        ),
                        Operator(
                            operator="complement",
                            variables=["reg:test::p", "reg:test::not_p"],
                            conclusion="reg:test::comp",
                        ),
                    ]
                ),
            )

    def test_abduction_is_formal(self):
        """Named leaf strategies can be formalized into canonical FormalStrategy skeletons."""
        leaf = Strategy(
            scope="local",
            type="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
        )
        result = leaf.formalize(namespace="reg", package_name="test")
        assert result.strategy.type == StrategyType.ABDUCTION
        assert len(result.strategy.formal_expr.operators) == 2
        assert len(result.strategy.premises) == 2
        assert result.strategy.metadata["interface_roles"]["observation"] == ["reg:test::obs"]
        assert result.strategy.metadata["interface_roles"]["alternative_explanation"] == [
            result.strategy.premises[1]
        ]

    def test_reductio_formalization_deferred(self):
        leaf = Strategy(
            scope="local",
            type="reductio",
            premises=["reg:test::r"],
            conclusion="reg:test::not_p",
        )
        with pytest.raises(ValueError, match="reductio is deferred in Gaia IR core"):
            leaf.formalize(namespace="reg", package_name="test")

    def test_case_analysis_open_world_deferred(self):
        leaf = Strategy(
            scope="local",
            type="case_analysis",
            premises=[
                "reg:test::exhaustive",
                "reg:test::a1",
                "reg:test::p1",
                "reg:test::a2",
                "reg:test::p2",
            ],
            conclusion="reg:test::c",
            metadata={"include_other_relevant_case": True},
        )
        with pytest.raises(ValueError, match="open-world case_analysis is deferred"):
            leaf.formalize(namespace="reg", package_name="test")

    def test_analogy_is_formal(self):
        leaf = Strategy(
            scope="local",
            type="analogy",
            premises=["reg:test::source_law", "reg:test::bridge"],
            conclusion="reg:test::target",
        )
        result = leaf.formalize(namespace="reg", package_name="test")
        assert result.strategy.type == StrategyType.ANALOGY
        assert len(result.strategy.formal_expr.operators) == 2

    def test_extrapolation_is_formal(self):
        leaf = Strategy(
            scope="local",
            type="extrapolation",
            premises=["reg:test::known_law", "reg:test::continuity"],
            conclusion="reg:test::extended",
        )
        result = leaf.formalize(namespace="reg", package_name="test")
        assert result.strategy.type == StrategyType.EXTRAPOLATION
        assert len(result.strategy.formal_expr.operators) == 2

    def test_empty_formal_expr_rejected(self):
        with pytest.raises(ValueError, match="at least one operator"):
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(operators=[]),
            )

    def test_formal_rejects_leaf_type(self):
        with pytest.raises(ValueError, match="FormalStrategy form only allows types"):
            FormalStrategy(
                scope="local",
                type="infer",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(operator="implication", variables=["a"], conclusion="b"),
                    ]
                ),
            )

    def test_structure_hash_from_formal_expr(self):
        """FormalStrategy structure_hash is derived from canonical formal expression."""
        fs = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a"],
            conclusion="b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["a"], conclusion="b"),
                ]
            ),
        )
        assert fs._structure_hash() != ""

    def test_different_formal_expr_different_id(self):
        """Different formal expressions produce different strategy IDs."""
        fs1 = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a"],
            conclusion="b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["a"], conclusion="b"),
                ]
            ),
        )
        fs2 = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a"],
            conclusion="b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["a"], conclusion="b"),
                    Operator(operator="implication", variables=["b"], conclusion="c"),
                ]
            ),
        )
        assert fs1.strategy_id != fs2.strategy_id

    def test_structure_hash_affects_id_vs_leaf(self):
        """FormalStrategy ID differs from hypothetical leaf with same scope/type/premises/conclusion."""
        fs = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a"],
            conclusion="b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["a"], conclusion="b"),
                ]
            ),
        )
        # A leaf with same inputs but empty structure_hash would get a different ID
        from gaia.gaia_ir.strategy import _compute_strategy_id

        leaf_id = _compute_strategy_id("local", "deduction", ["a"], "b", structure_hash="")
        assert fs.strategy_id != leaf_id


class TestStrategyNoLifecycleStages:
    """Verify no FactorStage concept exists — form is state per §3.8."""

    def test_no_stage_field(self):
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert not hasattr(s, "stage")

    def test_no_factor_category(self):
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert not hasattr(s, "category")
