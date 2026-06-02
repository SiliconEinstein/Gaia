"""Unit tests for research assessment artifact schema validation."""

from __future__ import annotations

import pytest

from gaia.engine.research.assessment import (
    AssessmentSchemaError,
    build_assessment_artifact,
    build_assessment_from_analysis,
    validate_assessment_artifact,
    validate_assessment_grounding,
)


def _relation(**overrides: object) -> dict[str, object]:
    relation: dict[str, object] = {
        "type": "supports",
        "claim": "Aspirin reduces first cardiovascular events in selected groups.",
        "rationale": "The evidence packet contains a directly relevant trial summary.",
        "epistemic_status": "candidate",
        "promotion_hint": "derive",
        "source_refs": [{"kind": "item", "id": "item_1"}],
    }
    relation.update(overrides)
    return relation


def test_assessment_artifact_validates_relation_mapping() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "aspirin-primary-prevention"},
        evidence_packet={
            "items": [
                {
                    "item_id": "item_1",
                    "kind": "variable",
                    "id": "variable_1",
                    "variable_type": "claim",
                    "content": "Trial summary.",
                }
            ]
        },
        relations=[_relation()],
        candidate_obligations=[],
    )

    assert artifact["kind"] == "assessment"
    assert validate_assessment_artifact(artifact) is artifact


def test_assessment_rejects_candidate_relation_promotion_hint() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"items": []},
        relations=[_relation(promotion_hint="candidate_relation")],
    )

    with pytest.raises(AssessmentSchemaError, match="promotion_hint"):
        validate_assessment_artifact(artifact)


def test_assessment_relation_requires_epistemic_status() -> None:
    relation = _relation()
    relation.pop("epistemic_status")
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"items": []},
        relations=[relation],
    )

    with pytest.raises(AssessmentSchemaError, match="epistemic_status"):
        validate_assessment_artifact(artifact)


def test_assessment_relation_requires_grounded_source_refs() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"items": []},
        relations=[_relation(source_refs=[])],
    )

    with pytest.raises(AssessmentSchemaError, match="source_refs"):
        validate_assessment_artifact(artifact)


def test_assessment_rejects_invalid_relation_hint_pair() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"items": []},
        relations=[_relation(type="background_for", promotion_hint="derive")],
    )

    with pytest.raises(AssessmentSchemaError, match="background_for"):
        validate_assessment_artifact(artifact)


def _landscape() -> dict[str, object]:
    return {
        "kind": "research_landscape",
        "action": "explore.scan",
        "items": [
            {
                "item_id": "original_item",
                "kind": "variable",
                "id": "aspree_variable",
                "variable_type": "claim",
                "content": (
                    "ASPREE reported no cardiovascular benefit and increased major hemorrhage."
                ),
                "source": {"paper_id": "P_ASPREE", "paper_title": "ASPREE trial"},
            }
        ],
        "paper_leads": [
            {
                "paper_id": "P_ASPREE",
                "title": "ASPREE trial",
                "variable_ids": ["aspree_variable"],
            }
        ],
    }


def test_assessment_from_analysis_preserves_typed_relations_and_review() -> None:
    artifact = build_assessment_from_analysis(
        focus={"kind": "focus", "id": "elderly_net_benefit"},
        landscapes=[_landscape()],
        analysis={
            "relations": [
                _relation(
                    type="opposes",
                    claim="ASPREE opposes routine aspirin use in healthy older adults.",
                    rationale="The item reports no cardiovascular benefit and more hemorrhage.",
                    promotion_hint="none",
                    source_refs=[{"kind": "item", "id": "item_0"}],
                )
            ],
            "review": {
                "language": "zh",
                "depth": "review",
                "summary": "老年人中常规一级预防净获益不足。",
                "sections": [{"title": "ASPREE", "body": "心血管获益不足且大出血增加。"}],
                "limitations": ["需要核对原始终点定义。"],
                "next_queries": ["aspirin primary prevention elderly bleeding"],
            },
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "补充老年亚组的绝对风险差。",
                    "source_refs": [{"kind": "item", "id": "item_0"}],
                }
            ],
        },
    )

    assert artifact["relations"][0]["type"] == "opposes"
    assert artifact["review"]["summary"] == "老年人中常规一级预防净获益不足。"
    assert validate_assessment_artifact(artifact) is artifact
    assert validate_assessment_grounding(artifact) is artifact


def test_assessment_grounding_rejects_unknown_item_ref() -> None:
    with pytest.raises(AssessmentSchemaError, match="not grounded"):
        build_assessment_from_analysis(
            focus={"kind": "focus", "id": "elderly_net_benefit"},
            landscapes=[_landscape()],
            analysis={
                "relations": [_relation(source_refs=[{"kind": "item", "id": "missing_item"}])],
                "candidate_obligations": [],
            },
        )


def test_assessment_review_requires_summary() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"items": []},
        relations=[_relation()],
        review={"language": "zh", "depth": "review", "sections": []},
    )

    with pytest.raises(AssessmentSchemaError, match="summary"):
        validate_assessment_artifact(artifact)
