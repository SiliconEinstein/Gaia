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
    def test_eleven_types(self):
        assert len(StrategyType) == 11
        expected = {
            "infer",
            "noisy_and",
            "deduction",
            "reductio",
            "elimination",
            "mathematical_induction",
            "case_analysis",
            "abduction",
            "induction",
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

    def test_no_independent_evidence(self):
        """independent_evidence uses Operator(equivalence) per spec."""
        with pytest.raises(ValueError):
            StrategyType("independent_evidence")


class TestStrategyCreation:
    def test_basic_strategy(self):
        s = Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
        assert s.strategy_id.startswith("lcs_")
        assert s.type == StrategyType.NOISY_AND

    def test_global_strategy(self):
        s = Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")
        assert s.strategy_id.startswith("gcs_")

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
            premises=["lcn_a"],
            conclusion="lcn_b",
            background=["lcn_setting"],
        )
        assert s.background == ["lcn_setting"]

    def test_with_steps(self):
        s = Strategy(
            scope="local",
            type="infer",
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="observed correlation")],
        )
        assert len(s.steps) == 1

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be one of"):
            Strategy(scope="detached", type="infer", premises=["a"], conclusion="b")

    def test_global_steps_rejected(self):
        with pytest.raises(ValueError, match="must not carry steps"):
            Strategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
                steps=[Step(reasoning="should stay local")],
            )

    def test_leaf_allows_named_strategy_type(self):
        """Per §3.5.1, named strategies can exist as leaf before formalization."""
        s = Strategy(scope="global", type="deduction", premises=["gcn_a"], conclusion="gcn_b")
        assert s.type == StrategyType.DEDUCTION
        assert s.strategy_id.startswith("gcs_")

    def test_leaf_structure_hash_empty(self):
        """Leaf strategies have empty structure hash."""
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert s._structure_hash() == ""


class TestCompositeStrategy:
    def test_creation_with_string_refs(self):
        cs = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            sub_strategies=["gcs_abc123", "gcs_def456"],
        )
        assert len(cs.sub_strategies) == 2
        assert cs.sub_strategies[0] == "gcs_abc123"
        assert isinstance(cs, Strategy)

    def test_empty_sub_strategies_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeStrategy(
                scope="global",
                type="induction",
                premises=["gcn_a"],
                conclusion="gcn_b",
                sub_strategies=[],
            )

    def test_any_type_allowed(self):
        """CompositeStrategy is a generic container -- any type is valid."""
        for type_ in StrategyType:
            cs = CompositeStrategy(
                scope="global",
                type=type_,
                premises=["gcn_a"],
                conclusion="gcn_b",
                sub_strategies=["gcs_abc123"],
            )
            assert cs.type == type_

    def test_structure_hash_from_sorted_sub_strategies(self):
        """structure_hash is based on sorted sub_strategy IDs."""
        cs1 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["gcs_x", "gcs_y"],
        )
        cs2 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["gcs_y", "gcs_x"],
        )
        # Same sorted sub_strategies => same ID
        assert cs1.strategy_id == cs2.strategy_id

    def test_different_sub_strategies_different_id(self):
        """Different sub_strategies produce different strategy IDs."""
        cs1 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["gcs_x"],
        )
        cs2 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["a"],
            conclusion="b",
            sub_strategies=["gcs_z"],
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
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["lcn_a", "lcn_b"],
                        conclusion="lcn_m",
                    ),
                    Operator(operator="implication", variables=["lcn_m"], conclusion="lcn_c"),
                ]
            ),
        )
        assert fs.type == StrategyType.DEDUCTION
        assert len(fs.formal_expr.operators) == 2
        assert isinstance(fs, Strategy)

    def test_reductio(self):
        """Reductio: implication + contradiction + complement."""
        fs = FormalStrategy(
            scope="local",
            type="reductio",
            premises=["lcn_r"],
            conclusion="lcn_not_p",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["lcn_p"], conclusion="lcn_q"),
                    Operator(
                        operator="contradiction",
                        variables=["lcn_q", "lcn_r"],
                        conclusion="lcn_contra",
                    ),
                    Operator(
                        operator="complement",
                        variables=["lcn_p", "lcn_not_p"],
                        conclusion="lcn_comp",
                    ),
                ]
            ),
        )
        assert fs.type == StrategyType.REDUCTIO
        assert len(fs.formal_expr.operators) == 3

    def test_abduction_is_formal(self):
        """Abduction is now a FormalStrategy type."""
        fs = FormalStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["gcn_h"], conclusion="gcn_obs"),
                ]
            ),
        )
        assert fs.type == StrategyType.ABDUCTION

    def test_induction_is_formal(self):
        """Induction is now a FormalStrategy type."""
        fs = FormalStrategy(
            scope="global",
            type="induction",
            premises=["gcn_a"],
            conclusion="gcn_b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["gcn_a"], conclusion="gcn_b"),
                ]
            ),
        )
        assert fs.type == StrategyType.INDUCTION

    def test_analogy_is_formal(self):
        """Analogy is now a FormalStrategy type."""
        fs = FormalStrategy(
            scope="global",
            type="analogy",
            premises=["gcn_a"],
            conclusion="gcn_b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="equivalence", variables=["gcn_a", "gcn_b"], conclusion="gcn_eq"
                    ),
                ]
            ),
        )
        assert fs.type == StrategyType.ANALOGY

    def test_extrapolation_is_formal(self):
        """Extrapolation is now a FormalStrategy type."""
        fs = FormalStrategy(
            scope="global",
            type="extrapolation",
            premises=["gcn_a"],
            conclusion="gcn_b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["gcn_a"], conclusion="gcn_b"),
                ]
            ),
        )
        assert fs.type == StrategyType.EXTRAPOLATION

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
