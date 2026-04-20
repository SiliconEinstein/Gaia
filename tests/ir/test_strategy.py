"""Tests for Strategy data model (Strategy, CompositeStrategy, FormalStrategy)."""

import pytest
from gaia.ir import (
    Strategy,
    CompositeStrategy,
    ComputeMethod,
    FormalStrategy,
    FormalExpr,
    LikelihoodModuleSpec,
    LikelihoodScoreRecord,
    ModuleUseMethod,
    OpaqueConditionalMethod,
    StrategyType,
    Step,
    Operator,
)


class TestStrategyType:
    def test_v6_compatible_types(self):
        assert len(StrategyType) == 16
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
            "induction",
            "support",
            "compare",
            "likelihood",
            "compute",
            "opaque_conditional",
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

    def test_induction_exists(self):
        """induction is a valid CompositeStrategy type."""
        assert StrategyType("induction") == StrategyType.INDUCTION


class TestStrategyCreation:
    def test_basic_strategy(self):
        s = Strategy(
            scope="local",
            type="noisy_and",
            premises=["github:test::a"],
            conclusion="github:test::b",
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
            premises=["github:test::a"],
            conclusion="github:test::b",
            background=["github:test::setting"],
        )
        assert s.background == ["github:test::setting"]

    def test_with_steps(self):
        s = Strategy(
            scope="local",
            type="infer",
            premises=["github:test::a"],
            conclusion="github:test::b",
            steps=[Step(reasoning="observed correlation")],
        )
        assert len(s.steps) == 1

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be 'local'"):
            Strategy(scope="detached", type="infer", premises=["a"], conclusion="b")

    def test_leaf_allows_named_strategy_type(self):
        """Per §3.5.1, named strategies can exist as leaf before formalization."""
        s = Strategy(
            scope="local",
            type="deduction",
            premises=["github:test::a"],
            conclusion="github:test::b",
        )
        assert s.type == StrategyType.DEDUCTION
        assert s.strategy_id.startswith("lcs_")

    def test_leaf_structure_hash_empty(self):
        """Leaf strategies have empty structure hash."""
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert s._structure_hash() == ""

    def test_likelihood_method_affects_strategy_id(self):
        s1 = Strategy(
            scope="local",
            type="likelihood",
            premises=["github:test::counts", "github:test::score_correct"],
            conclusion="github:test::target",
            method=ModuleUseMethod(
                module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
                input_bindings={
                    "counts": "github:test::counts",
                    "target": "github:test::target",
                },
                output_bindings={"score": "score:ab"},
                premise_bindings={
                    "data_observed": "github:test::counts",
                    "score_correct": "github:test::score_correct",
                },
            ),
            reason="Apply AB-test likelihood.",
        )
        s2 = Strategy(
            scope="local",
            type="likelihood",
            premises=["github:test::counts", "github:test::score_correct"],
            conclusion="github:test::target",
            method=ModuleUseMethod(
                module_ref="gaia.std.likelihood.binomial_test@v1",
                input_bindings={
                    "counts": "github:test::counts",
                    "target": "github:test::target",
                },
                output_bindings={"score": "score:ab"},
                premise_bindings={
                    "data_observed": "github:test::counts",
                    "score_correct": "github:test::score_correct",
                },
            ),
            reason="Apply binomial likelihood.",
        )
        assert s1.strategy_id != s2.strategy_id

    def test_assertions_affect_strategy_id(self):
        s1 = Strategy(
            scope="local",
            type="deduction",
            premises=["github:test::a"],
            conclusion="github:test::b",
            assertions=["github:test::assertion_1"],
        )
        s2 = Strategy(
            scope="local",
            type="deduction",
            premises=["github:test::a"],
            conclusion="github:test::b",
            assertions=["github:test::assertion_2"],
        )
        assert s1.strategy_id != s2.strategy_id

    def test_compute_and_opaque_methods_round_trip(self):
        compute = ComputeMethod(
            function_ref="two_binomial_log_lr",
            input_bindings={"counts": "github:test::counts"},
            output="score:ab",
            output_binding={"value": "return_value"},
            code_hash="sha256:abc",
        )
        strategy = Strategy(
            scope="local",
            type="compute",
            premises=["github:test::counts"],
            conclusion="github:test::score_correct",
            method=compute,
        )
        dumped = strategy.model_dump(mode="json")
        loaded = Strategy.model_validate(dumped)
        assert isinstance(loaded.method, ComputeMethod)
        assert loaded.method.output == "score:ab"

        opaque = Strategy(
            scope="local",
            type="opaque_conditional",
            premises=["github:test::a"],
            conclusion="github:test::b",
            method=OpaqueConditionalMethod(parameter_ref="cond_001"),
        )
        assert isinstance(Strategy.model_validate(opaque.model_dump()).method, OpaqueConditionalMethod)

    def test_likelihood_module_and_score_records(self):
        spec = LikelihoodModuleSpec(
            module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
            input_schema={"counts": "ABCounts", "target": "Claim"},
            output_schema={"score": "LikelihoodScoreRecord"},
            premise_schema={"score_correct": "Claim"},
            target_role="target",
            score_role="score",
            score_type="log_lr",
            effect="add_log_odds",
        )
        score = LikelihoodScoreRecord(
            score_id="score:ab",
            module_ref=spec.module_ref,
            target="github:test::target",
            score_type="log_lr",
            value=1.73,
            query="theta_B > theta_A",
        )
        assert score.module_ref == spec.module_ref
        assert score.value == 1.73


class TestCompositeStrategy:
    def test_creation_with_string_refs(self):
        cs = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
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
                premises=["github:test::a"],
                conclusion="github:test::b",
                sub_strategies=[],
            )

    def test_any_type_allowed(self):
        """CompositeStrategy is a generic container -- any type is valid."""
        for type_ in StrategyType:
            cs = CompositeStrategy(
                scope="local",
                type=type_,
                premises=["github:test::a"],
                conclusion="github:test::b",
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
            premises=["github:test::a", "github:test::b"],
            conclusion="github:test::c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["github:test::a", "github:test::b"],
                        conclusion="github:test::m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["github:test::m", "github:test::c"],
                        conclusion="github:test::h",
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
                premises=["github:test::r"],
                conclusion="github:test::not_p",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(
                            operator="implication",
                            variables=["github:test::p", "github:test::q"],
                            conclusion="github:test::impl_h",
                        ),
                        Operator(
                            operator="contradiction",
                            variables=["github:test::q", "github:test::r"],
                            conclusion="github:test::contra",
                        ),
                        Operator(
                            operator="complement",
                            variables=["github:test::p", "github:test::not_p"],
                            conclusion="github:test::comp",
                        ),
                    ]
                ),
            )

    def test_abduction_is_formal(self):
        """Named leaf strategies can be formalized into canonical FormalStrategy skeletons."""
        leaf = Strategy(
            scope="local",
            type="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
        )
        result = leaf.formalize(namespace="github", package_name="test")
        assert result.strategy.type == StrategyType.ABDUCTION
        assert len(result.strategy.formal_expr.operators) == 2
        assert len(result.strategy.premises) == 2
        assert result.strategy.metadata["interface_roles"]["observation"] == ["github:test::obs"]
        assert result.strategy.metadata["interface_roles"]["alternative_explanation"] == [
            result.strategy.premises[1]
        ]

    def test_implication_order_matters_for_id(self):
        """A→B and B→A must produce distinct FormalStrategy IDs."""
        fs_fwd = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["github:test::a"],
            conclusion="github:test::b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["github:test::a", "github:test::b"],
                        conclusion="github:test::h_fwd",
                    ),
                ]
            ),
        )
        fs_rev = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["github:test::a"],
            conclusion="github:test::b",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["github:test::b", "github:test::a"],
                        conclusion="github:test::h_rev",
                    ),
                ]
            ),
        )
        assert fs_fwd.strategy_id != fs_rev.strategy_id

    def test_reductio_formalization_deferred(self):
        leaf = Strategy(
            scope="local",
            type="reductio",
            premises=["github:test::r"],
            conclusion="github:test::not_p",
        )
        with pytest.raises(ValueError, match="reductio is deferred in Gaia IR core"):
            leaf.formalize(namespace="github", package_name="test")

    def test_case_analysis_open_world_deferred(self):
        leaf = Strategy(
            scope="local",
            type="case_analysis",
            premises=[
                "github:test::exhaustive",
                "github:test::a1",
                "github:test::p1",
                "github:test::a2",
                "github:test::p2",
            ],
            conclusion="github:test::c",
            metadata={"include_other_relevant_case": True},
        )
        with pytest.raises(ValueError, match="open-world case_analysis is deferred"):
            leaf.formalize(namespace="github", package_name="test")

    def test_analogy_is_formal(self):
        leaf = Strategy(
            scope="local",
            type="analogy",
            premises=["github:test::source_law", "github:test::bridge"],
            conclusion="github:test::target",
        )
        result = leaf.formalize(namespace="github", package_name="test")
        assert result.strategy.type == StrategyType.ANALOGY
        assert len(result.strategy.formal_expr.operators) == 2

    def test_extrapolation_is_formal(self):
        leaf = Strategy(
            scope="local",
            type="extrapolation",
            premises=["github:test::known_law", "github:test::continuity"],
            conclusion="github:test::extended",
        )
        result = leaf.formalize(namespace="github", package_name="test")
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
                        Operator(operator="implication", variables=["a", "b"], conclusion="h"),
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
                    Operator(operator="implication", variables=["a", "b"], conclusion="h"),
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
                    Operator(operator="implication", variables=["a", "b"], conclusion="h1"),
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
                    Operator(operator="implication", variables=["a", "b"], conclusion="h1"),
                    Operator(operator="implication", variables=["b", "c"], conclusion="h2"),
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
                    Operator(operator="implication", variables=["a", "b"], conclusion="h"),
                ]
            ),
        )
        # A leaf with same inputs but empty structure_hash would get a different ID
        from gaia.ir.strategy import _compute_strategy_id

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
