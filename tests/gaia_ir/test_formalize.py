"""Tests for IR-side named strategy formalization."""

from collections import Counter

import pytest

from gaia.gaia_ir import (
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
            premises=["reg:test::a", "reg:test::b"],
            conclusion="reg:test::c",
            background=["reg:test::ctx"],
            steps=[Step(reasoning="combine the two premises")],
            metadata={"source": "unit-test"},
        )

        result = leaf.formalize(namespace="reg", package_name="test")

        assert isinstance(result.strategy, FormalStrategy)
        assert result.strategy.background == ["reg:test::ctx"]
        assert len(result.strategy.steps or []) == 1
        assert result.strategy.steps[0].reasoning == "combine the two premises"
        assert result.strategy.metadata["source"] == "unit-test"
        assert result.strategy.metadata["generated_formal_expr"] is True
        assert result.strategy.metadata["formalization_template"] == "deduction"

        assert _operator_names(result.strategy) == ["conjunction", "implication"]
        assert len(result.knowledges) == 1

        conjunction = result.knowledges[0]
        assert conjunction.id.startswith("reg:test::__")
        assert conjunction.label is not None
        assert conjunction.label.startswith("__")
        assert conjunction.type == KnowledgeType.CLAIM
        assert conjunction.metadata["generated_kind"] == "helper_claim"
        assert conjunction.metadata["intermediate_role"] == "conjunction_result"
        assert conjunction.metadata["helper_kind"] == "conjunction_result"
        assert conjunction.metadata["owning_strategy_id"] == result.strategy.strategy_id
        assert result.strategy.formal_expr.operators[0].conclusion == conjunction.id

    def test_formalize_rejects_strategy_without_conclusion(self):
        leaf = Strategy(scope="local", type="deduction", premises=["reg:test::a", "reg:test::b"])

        with pytest.raises(ValueError, match="requires the strategy to set a conclusion"):
            leaf.formalize(namespace="reg", package_name="test")

    def test_formalize_rejects_composite_strategy(self):
        composite = CompositeStrategy(
            scope="local",
            type="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
            sub_strategies=["lcs_child"],
        )

        with pytest.raises(TypeError, match="CompositeStrategy cannot be directly formalized"):
            composite.formalize(namespace="reg", package_name="test")

    def test_formalize_rejects_already_formal_strategy(self):
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

        with pytest.raises(TypeError, match="already formalized"):
            formal.formalize(namespace="reg", package_name="test")


class TestFormalizeNamedStrategy:
    def test_deterministic_output(self):
        result_a = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
            namespace="reg",
            package_name="test",
        )
        result_b = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
            namespace="reg",
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
            ("deduction", ["reg:test::a", "reg:test::b"]),
            ("mathematical_induction", ["reg:test::base", "reg:test::step"]),
            ("analogy", ["reg:test::source_law", "reg:test::bridge"]),
            ("extrapolation", ["reg:test::known_law", "reg:test::continuity"]),
        ],
    )
    def test_conjunction_templates(self, type_: str, premises: list[str]):
        result = formalize_named_strategy(
            scope="local",
            type_=type_,
            premises=premises,
            conclusion="reg:test::out",
            namespace="reg",
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
            premises=["reg:test::obs"],
            conclusion="reg:test::h",
            namespace="reg",
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
            "observation": ["reg:test::obs"],
        }
        assert result.strategy.premises[0] == "reg:test::obs"

        alternative_explanation = _knowledge_for_role(result.knowledges, "alternative_explanation")
        disjunction = _knowledge_for_role(result.knowledges, "disjunction_result")
        equivalence = _knowledge_for_role(result.knowledges, "equivalence_result")

        assert alternative_explanation.metadata["generated_kind"] == "interface_claim"
        assert alternative_explanation.metadata["visibility"] == "strategy_interface"
        assert equivalence.metadata["generated_kind"] == "helper_claim"
        assert equivalence.metadata["helper_kind"] == "equivalence_result"
        assert result.strategy.premises == ["reg:test::obs", alternative_explanation.id]
        assert result.strategy.formal_expr.operators[0].variables == [
            "reg:test::h",
            alternative_explanation.id,
        ]
        assert result.strategy.formal_expr.operators[0].conclusion == disjunction.id
        assert result.strategy.formal_expr.operators[1].variables == [
            disjunction.id,
            "reg:test::obs",
        ]
        assert result.strategy.formal_expr.operators[1].conclusion == equivalence.id

    def test_abduction_reuses_explicit_alternative_explanation(self):
        result = formalize_named_strategy(
            scope="local",
            type_="abduction",
            premises=["reg:test::obs", "reg:test::alt"],
            conclusion="reg:test::h",
            namespace="reg",
            package_name="test",
        )

        assert _operator_names(result.strategy) == ["disjunction", "equivalence"]
        assert _role_counts(result.knowledges) == Counter(
            {
                "disjunction_result": 1,
                "equivalence_result": 1,
            }
        )
        assert result.strategy.premises == ["reg:test::obs", "reg:test::alt"]
        assert result.strategy.metadata["interface_roles"] == {
            "alternative_explanation": ["reg:test::alt"],
            "observation": ["reg:test::obs"],
        }

    def test_induction_deferred(self):
        with pytest.raises(ValueError, match="deferred in Gaia IR core"):
            formalize_named_strategy(
                scope="local",
                type_="induction",
                premises=["reg:test::obs_1", "reg:test::obs_2"],
                conclusion="reg:test::law",
                namespace="reg",
                package_name="test",
            )

    def test_reductio_deferred(self):
        with pytest.raises(ValueError, match="reductio is deferred in Gaia IR core"):
            formalize_named_strategy(
                scope="local",
                type_="reductio",
                premises=["reg:test::r"],
                conclusion="reg:test::not_p",
                namespace="reg",
                package_name="test",
            )

    def test_elimination_template(self):
        result = formalize_named_strategy(
            scope="local",
            type_="elimination",
            premises=[
                "reg:test::exhaustive",
                "reg:test::h1",
                "reg:test::e1",
                "reg:test::h2",
                "reg:test::e2",
            ],
            conclusion="reg:test::h3",
            namespace="reg",
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
            "eliminated_candidate": ["reg:test::h1", "reg:test::h2"],
            "elimination_evidence": ["reg:test::e1", "reg:test::e2"],
            "exhaustiveness": ["reg:test::exhaustive"],
        }

    def test_case_analysis_template(self):
        result = formalize_named_strategy(
            scope="local",
            type_="case_analysis",
            premises=[
                "reg:test::exhaustive",
                "reg:test::a1",
                "reg:test::p1",
                "reg:test::a2",
                "reg:test::p2",
            ],
            conclusion="reg:test::c",
            namespace="reg",
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
            "case": ["reg:test::a1", "reg:test::a2"],
            "case_support": ["reg:test::p1", "reg:test::p2"],
            "exhaustiveness": ["reg:test::exhaustive"],
        }

    def test_case_analysis_open_world_variant_deferred(self):
        with pytest.raises(ValueError, match="open-world case_analysis is deferred"):
            formalize_named_strategy(
                scope="local",
                type_="case_analysis",
                premises=[
                    "reg:test::exhaustive",
                    "reg:test::a1",
                    "reg:test::p1",
                    "reg:test::a2",
                    "reg:test::p2",
                ],
                conclusion="reg:test::c",
                namespace="reg",
                package_name="test",
                metadata={"include_other_relevant_case": True},
            )

    def test_rejects_non_named_strategy_type(self):
        with pytest.raises(ValueError, match="only supports named FormalStrategy types"):
            formalize_named_strategy(
                scope="local",
                type_="infer",
                premises=["reg:test::a"],
                conclusion="reg:test::b",
                namespace="reg",
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
