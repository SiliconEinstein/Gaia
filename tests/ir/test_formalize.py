"""Tests for IR-side named strategy formalization."""

from collections import Counter

import pytest

from gaia.ir import (
    CompositeStrategy,
    FormalExpr,
    FormalStrategy,
    KnowledgeType,
    Operator,
    Step,
    Strategy,
    formalize_named_strategy,
)


def _operator_names(strategy: FormalStrategy) -> list[str]:
    return [op.operator.value for op in strategy.formal_expr.operators]


def _generated_role(knowledge) -> str:
    metadata = knowledge.metadata or {}
    return metadata.get("interface_role") or metadata.get("intermediate_role")


def _role_counts(knowledges) -> Counter[str]:
    return Counter(_generated_role(knowledge) for knowledge in knowledges)


def _knowledge_for_role(knowledges, role: str):
    return next(knowledge for knowledge in knowledges if _generated_role(knowledge) == role)


class TestStrategyFormalize:
    def test_leaf_strategy_formalize_preserves_user_fields(self):
        leaf = Strategy(
            scope="local",
            type="deduction",
            premises=["github:test::a", "github:test::b"],
            conclusion="github:test::c",
            background=["github:test::ctx"],
            steps=[Step(reasoning="combine the two premises")],
            metadata={"source": "unit-test"},
        )

        result = leaf.formalize(namespace="github", package_name="test")

        assert isinstance(result.strategy, FormalStrategy)
        assert result.strategy.background == ["github:test::ctx"]
        assert len(result.strategy.steps or []) == 1
        assert result.strategy.steps[0].reasoning == "combine the two premises"
        assert result.strategy.metadata["source"] == "unit-test"
        assert result.strategy.metadata["generated_formal_expr"] is True
        assert result.strategy.metadata["formalization_template"] == "deduction"

        assert _operator_names(result.strategy) == ["conjunction", "implication"]
        assert len(result.knowledges) == 1

        conjunction = result.knowledges[0]
        assert conjunction.id.startswith("github:test::__")
        assert conjunction.label is not None
        assert conjunction.label.startswith("__")
        assert conjunction.type == KnowledgeType.CLAIM
        assert conjunction.metadata["generated_kind"] == "helper_claim"
        assert conjunction.metadata["intermediate_role"] == "conjunction_result"
        assert conjunction.metadata["helper_kind"] == "conjunction_result"
        assert conjunction.metadata["owning_strategy_id"] == result.strategy.strategy_id
        assert result.strategy.formal_expr.operators[0].conclusion == conjunction.id

    def test_formalize_rejects_strategy_without_conclusion(self):
        leaf = Strategy(
            scope="local", type="deduction", premises=["github:test::a", "github:test::b"]
        )

        with pytest.raises(ValueError, match="requires the strategy to set a conclusion"):
            leaf.formalize(namespace="github", package_name="test")

    def test_formalize_rejects_composite_strategy(self):
        composite = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
            sub_strategies=["lcs_child"],
        )

        with pytest.raises(TypeError, match="CompositeStrategy cannot be directly formalized"):
            composite.formalize(namespace="github", package_name="test")

    def test_formalize_rejects_already_formal_strategy(self):
        formal = FormalStrategy(
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
                        variables=["github:test::m"],
                        conclusion="github:test::c",
                    ),
                ]
            ),
        )

        with pytest.raises(TypeError, match="already formalized"):
            formal.formalize(namespace="github", package_name="test")


class TestFormalizeNamedStrategy:
    def test_deterministic_output(self):
        result_a = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
            namespace="github",
            package_name="test",
        )
        result_b = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
            namespace="github",
            package_name="test",
        )

        assert [knowledge.id for knowledge in result_a.knowledges] == [
            knowledge.id for knowledge in result_b.knowledges
        ]
        assert result_a.strategy.strategy_id == result_b.strategy.strategy_id
        assert result_a.strategy.model_dump(mode="json") == result_b.strategy.model_dump(
            mode="json"
        )

    @pytest.mark.parametrize(
        ("type_", "premises"),
        [
            ("deduction", ["github:test::a", "github:test::b"]),
            ("mathematical_induction", ["github:test::base", "github:test::step"]),
            ("analogy", ["github:test::source_law", "github:test::bridge"]),
            ("extrapolation", ["github:test::known_law", "github:test::continuity"]),
        ],
    )
    def test_conjunction_templates(self, type_: str, premises: list[str]):
        result = formalize_named_strategy(
            scope="local",
            type_=type_,
            premises=premises,
            conclusion="github:test::out",
            namespace="github",
            package_name="test",
        )

        assert _operator_names(result.strategy) == ["conjunction", "implication"]
        assert _role_counts(result.knowledges) == Counter({"conjunction_result": 1})

        conjunction = result.knowledges[0]
        assert conjunction.metadata["generated_kind"] == "helper_claim"
        assert result.strategy.formal_expr.operators[0].conclusion == conjunction.id
        assert result.strategy.formal_expr.operators[1].variables == [conjunction.id]

    def test_abduction_template(self):
        result = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["github:test::obs"],
            conclusion="github:test::h",
            namespace="github",
            package_name="test",
        )

        assert _operator_names(result.strategy) == ["disjunction", "equivalence"]
        assert _role_counts(result.knowledges) == Counter(
            {
                "alternative_explanation": 1,
                "disjunction_result": 1,
                "equivalence_result": 1,
            }
        )
        assert result.strategy.metadata["interface_roles"] == {
            "alternative_explanation": [result.strategy.premises[1]],
            "observation": ["github:test::obs"],
        }
        assert result.strategy.premises[0] == "github:test::obs"

        alternative_explanation = _knowledge_for_role(result.knowledges, "alternative_explanation")
        disjunction = _knowledge_for_role(result.knowledges, "disjunction_result")
        equivalence = _knowledge_for_role(result.knowledges, "equivalence_result")

        assert alternative_explanation.metadata["generated_kind"] == "interface_claim"
        assert alternative_explanation.metadata["visibility"] == "strategy_interface"
        assert equivalence.metadata["generated_kind"] == "helper_claim"
        assert equivalence.metadata["helper_kind"] == "equivalence_result"
        assert result.strategy.premises == ["github:test::obs", alternative_explanation.id]
        assert result.strategy.formal_expr.operators[0].variables == [
            "github:test::h",
            alternative_explanation.id,
        ]
        assert result.strategy.formal_expr.operators[0].conclusion == disjunction.id
        assert result.strategy.formal_expr.operators[1].variables == [
            disjunction.id,
            "github:test::obs",
        ]
        assert result.strategy.formal_expr.operators[1].conclusion == equivalence.id

    def test_abduction_reuses_explicit_alternative_explanation(self):
        result = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["github:test::obs", "github:test::alt"],
            conclusion="github:test::h",
            namespace="github",
            package_name="test",
        )

        assert _operator_names(result.strategy) == ["disjunction", "equivalence"]
        assert _role_counts(result.knowledges) == Counter(
            {
                "disjunction_result": 1,
                "equivalence_result": 1,
            }
        )
        assert result.strategy.premises == ["github:test::obs", "github:test::alt"]
        assert result.strategy.metadata["interface_roles"] == {
            "alternative_explanation": ["github:test::alt"],
            "observation": ["github:test::obs"],
        }

    def test_induction_not_formal_strategy(self):
        """Induction is a CompositeStrategy, not a FormalStrategy — formalize rejects it."""
        with pytest.raises(ValueError, match="only supports named FormalStrategy types"):
            formalize_named_strategy(
                scope="local",
                type_="induction",
                premises=["github:test::obs_1", "github:test::obs_2"],
                conclusion="github:test::law",
                namespace="github",
                package_name="test",
            )

    def test_reductio_deferred(self):
        with pytest.raises(ValueError, match="reductio is deferred in Gaia IR core"):
            formalize_named_strategy(
                scope="local",
                type_="reductio",
                premises=["github:test::r"],
                conclusion="github:test::not_p",
                namespace="github",
                package_name="test",
            )

    def test_elimination_template(self):
        result = formalize_named_strategy(
            scope="local",
            type_="elimination",
            premises=[
                "github:test::exhaustive",
                "github:test::h1",
                "github:test::e1",
                "github:test::h2",
                "github:test::e2",
            ],
            conclusion="github:test::h3",
            namespace="github",
            package_name="test",
        )

        assert _operator_names(result.strategy) == [
            "disjunction",
            "equivalence",
            "contradiction",
            "contradiction",
            "conjunction",
            "implication",
        ]
        assert _role_counts(result.knowledges) == Counter(
            {
                "disjunction_result": 1,
                "equivalence_result": 1,
                "contradiction_result": 2,
                "conjunction_result": 1,
            }
        )
        assert result.strategy.metadata["interface_roles"] == {
            "eliminated_candidate": ["github:test::h1", "github:test::h2"],
            "elimination_evidence": ["github:test::e1", "github:test::e2"],
            "exhaustiveness": ["github:test::exhaustive"],
        }

    def test_case_analysis_template(self):
        result = formalize_named_strategy(
            scope="local",
            type_="case_analysis",
            premises=[
                "github:test::exhaustive",
                "github:test::a1",
                "github:test::p1",
                "github:test::a2",
                "github:test::p2",
            ],
            conclusion="github:test::c",
            namespace="github",
            package_name="test",
        )

        assert _operator_names(result.strategy) == [
            "disjunction",
            "equivalence",
            "conjunction",
            "implication",
            "conjunction",
            "implication",
        ]
        assert _role_counts(result.knowledges) == Counter(
            {
                "disjunction_result": 1,
                "equivalence_result": 1,
                "conjunction_result": 2,
            }
        )
        assert result.strategy.metadata["interface_roles"] == {
            "case": ["github:test::a1", "github:test::a2"],
            "case_support": ["github:test::p1", "github:test::p2"],
            "exhaustiveness": ["github:test::exhaustive"],
        }

    def test_case_analysis_open_world_variant_deferred(self):
        with pytest.raises(ValueError, match="open-world case_analysis is deferred"):
            formalize_named_strategy(
                scope="local",
                type_="case_analysis",
                premises=[
                    "github:test::exhaustive",
                    "github:test::a1",
                    "github:test::p1",
                    "github:test::a2",
                    "github:test::p2",
                ],
                conclusion="github:test::c",
                namespace="github",
                package_name="test",
                metadata={"include_other_relevant_case": True},
            )

    def test_rejects_non_named_strategy_type(self):
        with pytest.raises(ValueError, match="only supports named FormalStrategy types"):
            formalize_named_strategy(
                scope="local",
                type_="infer",
                premises=["github:test::a"],
                conclusion="github:test::b",
                namespace="github",
                package_name="test",
            )

    def test_rejects_global_scope(self):
        with pytest.raises(ValueError, match="only supports scope='local'"):
            formalize_named_strategy(
                scope="global",
                type_="deduction",
                premises=["gcn_a", "gcn_b"],
                conclusion="gcn_c",
            )
