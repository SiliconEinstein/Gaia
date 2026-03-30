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
    def test_thirteen_types(self):
        assert len(StrategyType) == 13
        assert "infer" in set(StrategyType)
        assert "noisy_and" in set(StrategyType)
        assert "deduction" in set(StrategyType)
        assert "abduction" in set(StrategyType)
        assert "induction" in set(StrategyType)
        assert "toolcall" in set(StrategyType)

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

    def test_leaf_rejects_named_strategy_type(self):
        with pytest.raises(ValueError, match="Strategy form only allows types"):
            Strategy(scope="global", type="deduction", premises=["gcn_a"], conclusion="gcn_b")


class TestCompositeStrategy:
    def test_creation(self):
        sub1 = Strategy(scope="global", type="noisy_and", premises=["gcn_h"], conclusion="gcn_o")
        sub2 = Strategy(scope="global", type="noisy_and", premises=["gcn_a"], conclusion="gcn_b")
        cs = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            sub_strategies=[sub1, sub2],
        )
        assert len(cs.sub_strategies) == 2
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

    def test_composite_rejects_leaf_type(self):
        with pytest.raises(ValueError, match="CompositeStrategy form only allows types"):
            CompositeStrategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
                sub_strategies=[
                    Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")
                ],
            )

    def test_nested_composite(self):
        """CompositeStrategy can contain CompositeStrategy (recursive)."""
        inner = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["a"],
            conclusion="b",
            sub_strategies=[
                Strategy(scope="global", type="noisy_and", premises=["a"], conclusion="b")
            ],
        )
        outer = CompositeStrategy(
            scope="global",
            type="induction",
            premises=["a"],
            conclusion="c",
            sub_strategies=[inner],
        )
        assert isinstance(outer.sub_strategies[0], CompositeStrategy)

    def test_mixed_sub_strategies(self):
        """CompositeStrategy can mix Strategy and FormalStrategy."""
        leaf = Strategy(scope="global", type="noisy_and", premises=["gcn_h"], conclusion="gcn_o")
        formal = FormalStrategy(
            scope="global",
            type="deduction",
            premises=["gcn_a"],
            conclusion="gcn_b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication", variables=["gcn_a", "gcn_b"], conclusion="gcn_b"
                    ),
                ]
            ),
        )
        cs = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            sub_strategies=[leaf, formal],
        )
        assert isinstance(cs.sub_strategies[0], Strategy)
        assert isinstance(cs.sub_strategies[1], FormalStrategy)


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
                        variables=["lcn_a", "lcn_b", "lcn_m"],
                        conclusion="lcn_m",
                    ),
                    Operator(
                        operator="implication", variables=["lcn_m", "lcn_c"], conclusion="lcn_c"
                    ),
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
                    Operator(
                        operator="implication", variables=["lcn_p", "lcn_q"], conclusion="lcn_q"
                    ),
                    Operator(operator="contradiction", variables=["lcn_q", "lcn_r"]),
                    Operator(operator="complement", variables=["lcn_p", "lcn_not_p"]),
                ]
            ),
        )
        assert fs.type == StrategyType.REDUCTIO
        assert len(fs.formal_expr.operators) == 3

    def test_empty_formal_expr_rejected(self):
        with pytest.raises(ValueError, match="at least one operator"):
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(operators=[]),
            )

    def test_formal_rejects_composite_type(self):
        with pytest.raises(ValueError, match="FormalStrategy form only allows types"):
            FormalStrategy(
                scope="local",
                type="induction",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(operator="implication", variables=["a", "b"], conclusion="b"),
                    ]
                ),
            )


class TestStrategyNoLifecycleStages:
    """Verify no FactorStage concept exists — form is state per §3.8."""

    def test_no_stage_field(self):
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert not hasattr(s, "stage")

    def test_no_factor_category(self):
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert not hasattr(s, "category")
