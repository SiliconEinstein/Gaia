"""Unit tests for research assessment artifact schema validation."""

from __future__ import annotations

import pytest

from gaia.engine.research.assessment import (
    AssessmentSchemaError,
    build_assessment_artifact,
    validate_assessment_artifact,
)


def _relation(**overrides: object) -> dict[str, object]:
    relation: dict[str, object] = {
        "type": "supports",
        "claim": "Aspirin reduces first cardiovascular events in selected groups.",
        "rationale": "The evidence packet contains a directly relevant trial summary.",
        "epistemic_status": "candidate",
        "promotion_hint": "derive",
        "source_refs": [{"kind": "snippet", "id": "snippet_1"}],
    }
    relation.update(overrides)
    return relation


def test_assessment_artifact_validates_relation_mapping() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "aspirin-primary-prevention"},
        evidence_packet={
            "snippets": [
                {
                    "id": "snippet_1",
                    "source_ref": {"kind": "lkm_node", "id": "lkm:node:1"},
                    "text": "Trial summary.",
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
        evidence_packet={"snippets": []},
        relations=[_relation(promotion_hint="candidate_relation")],
    )

    with pytest.raises(AssessmentSchemaError, match="promotion_hint"):
        validate_assessment_artifact(artifact)


def test_assessment_relation_requires_epistemic_status() -> None:
    relation = _relation()
    relation.pop("epistemic_status")
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"snippets": []},
        relations=[relation],
    )

    with pytest.raises(AssessmentSchemaError, match="epistemic_status"):
        validate_assessment_artifact(artifact)


def test_assessment_relation_requires_grounded_source_refs() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"snippets": []},
        relations=[_relation(source_refs=[])],
    )

    with pytest.raises(AssessmentSchemaError, match="source_refs"):
        validate_assessment_artifact(artifact)


def test_assessment_rejects_invalid_relation_hint_pair() -> None:
    artifact = build_assessment_artifact(
        focus={"kind": "focus", "id": "focus_1"},
        evidence_packet={"snippets": []},
        relations=[_relation(type="background_for", promotion_hint="derive")],
    )

    with pytest.raises(AssessmentSchemaError, match="background_for"):
        validate_assessment_artifact(artifact)
