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
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
            background=["lcn_ctx"],
            steps=[Step(reasoning="combine the two premises")],
            metadata={"source": "unit-test"},
        )

        result = leaf.formalize()

        assert isinstance(result.strategy, FormalStrategy)
        assert result.strategy.background == ["lcn_ctx"]
        assert len(result.strategy.steps or []) == 1
        assert result.strategy.steps[0].reasoning == "combine the two premises"
        assert result.strategy.metadata["source"] == "unit-test"
        assert result.strategy.metadata["generated_formal_expr"] is True
        assert result.strategy.metadata["formalization_template"] == "deduction"

        assert _operator_names(result.strategy) == ["conjunction", "implication"]
        assert len(result.knowledges) == 1

        conjunction = result.knowledges[0]
        assert conjunction.id.startswith("lcn_")
        assert conjunction.type == KnowledgeType.CLAIM
        assert conjunction.metadata["generated_kind"] == "helper_claim"
        assert conjunction.metadata["intermediate_role"] == "conjunction_result"
        assert conjunction.metadata["helper_kind"] == "conjunction_result"
        assert conjunction.metadata["owning_strategy_id"] == result.strategy.strategy_id
        assert result.strategy.formal_expr.operators[0].conclusion == conjunction.id

    def test_formalize_rejects_strategy_without_conclusion(self):
        leaf = Strategy(scope="global", type="deduction", premises=["gcn_a", "gcn_b"])

        with pytest.raises(ValueError, match="requires the strategy to set a conclusion"):
            leaf.formalize()

    def test_formalize_rejects_composite_strategy(self):
        composite = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            sub_strategies=["gcs_child"],
        )

        with pytest.raises(TypeError, match="CompositeStrategy cannot be directly formalized"):
            composite.formalize()

    def test_formalize_rejects_already_formal_strategy(self):
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
                    Operator(operator="implication", variables=["lcn_m"], conclusion="lcn_c"),
                ]
            ),
        )

        with pytest.raises(TypeError, match="already formalized"):
            formal.formalize()


class TestFormalizeNamedStrategy:
    def test_deterministic_output(self):
        result_a = formalize_named_strategy(
            scope="global",
            type_="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
        )
        result_b = formalize_named_strategy(
            scope="global",
            type_="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
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
            ("deduction", ["gcn_a", "gcn_b"]),
            ("mathematical_induction", ["gcn_base", "gcn_step"]),
            ("analogy", ["gcn_source_law", "gcn_bridge"]),
            ("extrapolation", ["gcn_known_law", "gcn_continuity"]),
        ],
    )
    def test_conjunction_templates(self, type_: str, premises: list[str]):
        result = formalize_named_strategy(
            scope="global",
            type_=type_,
            premises=premises,
            conclusion="gcn_out",
        )

        assert _operator_names(result.strategy) == ["conjunction", "implication"]
        assert _role_counts(result.knowledges) == Counter({"conjunction_result": 1})

        conjunction = result.knowledges[0]
        assert conjunction.metadata["generated_kind"] == "helper_claim"
        assert result.strategy.formal_expr.operators[0].conclusion == conjunction.id
        assert result.strategy.formal_expr.operators[1].variables == [conjunction.id]

    def test_abduction_template(self):
        result = formalize_named_strategy(
            scope="global",
            type_="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
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
            "observation": ["gcn_obs"],
        }
        assert result.strategy.premises[0] == "gcn_obs"

        alternative_explanation = _knowledge_for_role(result.knowledges, "alternative_explanation")
        disjunction = _knowledge_for_role(result.knowledges, "disjunction_result")
        equivalence = _knowledge_for_role(result.knowledges, "equivalence_result")

        assert alternative_explanation.metadata["generated_kind"] == "interface_claim"
        assert alternative_explanation.metadata["visibility"] == "strategy_interface"
        assert equivalence.metadata["generated_kind"] == "helper_claim"
        assert equivalence.metadata["helper_kind"] == "equivalence_result"
        assert result.strategy.premises == ["gcn_obs", alternative_explanation.id]
        assert result.strategy.formal_expr.operators[0].variables == [
            "gcn_h",
            alternative_explanation.id,
        ]
        assert result.strategy.formal_expr.operators[0].conclusion == disjunction.id
        assert result.strategy.formal_expr.operators[1].variables == [disjunction.id, "gcn_obs"]
        assert result.strategy.formal_expr.operators[1].conclusion == equivalence.id

    def test_abduction_reuses_explicit_alternative_explanation(self):
        result = formalize_named_strategy(
            scope="global",
            type_="abduction",
            premises=["gcn_obs", "gcn_alt"],
            conclusion="gcn_h",
        )

        assert _operator_names(result.strategy) == ["disjunction", "equivalence"]
        assert _role_counts(result.knowledges) == Counter(
            {
                "disjunction_result": 1,
                "equivalence_result": 1,
            }
        )
        assert result.strategy.premises == ["gcn_obs", "gcn_alt"]
        assert result.strategy.metadata["interface_roles"] == {
            "alternative_explanation": ["gcn_alt"],
            "observation": ["gcn_obs"],
        }

    def test_induction_deferred(self):
        with pytest.raises(ValueError, match="deferred in Gaia IR core"):
            formalize_named_strategy(
                scope="global",
                type_="induction",
                premises=["gcn_obs_1", "gcn_obs_2"],
                conclusion="gcn_law",
            )

    def test_reductio_deferred(self):
        with pytest.raises(ValueError, match="reductio is deferred in Gaia IR core"):
            formalize_named_strategy(
                scope="global",
                type_="reductio",
                premises=["gcn_r"],
                conclusion="gcn_not_p",
            )

    def test_elimination_template(self):
        result = formalize_named_strategy(
            scope="global",
            type_="elimination",
            premises=[
                "gcn_exhaustive",
                "gcn_h1",
                "gcn_e1",
                "gcn_h2",
                "gcn_e2",
            ],
            conclusion="gcn_h3",
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
            "eliminated_candidate": ["gcn_h1", "gcn_h2"],
            "elimination_evidence": ["gcn_e1", "gcn_e2"],
            "exhaustiveness": ["gcn_exhaustive"],
        }

    def test_case_analysis_template(self):
        result = formalize_named_strategy(
            scope="global",
            type_="case_analysis",
            premises=["gcn_exhaustive", "gcn_a1", "gcn_p1", "gcn_a2", "gcn_p2"],
            conclusion="gcn_c",
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
            "case": ["gcn_a1", "gcn_a2"],
            "case_support": ["gcn_p1", "gcn_p2"],
            "exhaustiveness": ["gcn_exhaustive"],
        }

    def test_case_analysis_open_world_variant_deferred(self):
        with pytest.raises(ValueError, match="open-world case_analysis is deferred"):
            formalize_named_strategy(
                scope="global",
                type_="case_analysis",
                premises=["gcn_exhaustive", "gcn_a1", "gcn_p1", "gcn_a2", "gcn_p2"],
                conclusion="gcn_c",
                metadata={"include_other_relevant_case": True},
            )

    def test_rejects_non_named_strategy_type(self):
        with pytest.raises(ValueError, match="only supports named FormalStrategy types"):
            formalize_named_strategy(
                scope="global",
                type_="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
            )
