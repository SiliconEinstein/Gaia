"""Unit tests for research focus synthesis artifacts."""

from __future__ import annotations

import pytest

from gaia.engine.research.focus import (
    FocusSynthesisSchemaError,
    build_focus_synthesis_artifact,
    validate_focus_synthesis_artifact,
)


def _landscape() -> dict[str, object]:
    return {
        "kind": "research_landscape",
        "action": "explore.scan",
        "stats": {"query_batches": 1, "raw_results": 1, "paper_leads": 1},
        "candidate_focuses": [
            {
                "id": "candidate_focus_query_0",
                "question": "What are the main evidence tensions around aspirin?",
                "evidence_refs": [{"kind": "item", "id": "item_0"}],
            }
        ],
    }


def _focus(**overrides: object) -> dict[str, object]:
    focus: dict[str, object] = {
        "id": "elderly_net_benefit",
        "kind": "research_focus",
        "status": "candidate",
        "question": "70岁及以上人群中，阿司匹林一级预防的净获益是否为正？",
        "rationale": "ASPREE 相关证据同时涉及无心血管获益和大出血增加。",
        "priority": "high",
        "readiness": "ready_for_assess",
        "scope": {"population": "older adults", "endpoint": "net benefit"},
        "coverage": {"items": 3, "missing": []},
        "evidence_refs": [{"kind": "item", "id": "item_0"}],
        "suggested_queries": [],
    }
    focus.update(overrides)
    return focus


def test_focus_synthesis_accepts_llm_analysis_payload() -> None:
    artifact = build_focus_synthesis_artifact(
        landscapes=[_landscape()],
        analysis={
            "focuses": [_focus()],
            "coverage_gaps": [
                {
                    "kind": "missing_endpoint",
                    "description": "缺少颅内出血终点的分层证据。",
                    "evidence_refs": [{"kind": "item", "id": "item_0"}],
                }
            ],
            "notes": ["由 agent/LLM 从 landscape 中聚类生成。"],
        },
        language="zh",
    )

    assert artifact["kind"] == "focus_synthesis"
    assert artifact["focuses"][0]["priority"] == "high"
    assert artifact["coverage_gaps"][0]["kind"] == "missing_endpoint"
    assert validate_focus_synthesis_artifact(artifact) is artifact


def test_focus_synthesis_fallback_uses_landscape_candidates() -> None:
    artifact = build_focus_synthesis_artifact(landscapes=[_landscape()])

    assert artifact["focuses"][0]["id"] == "candidate_focus_query_0"
    assert artifact["focuses"][0]["readiness"] == "needs_expand"
    assert "deterministic fallback" in artifact["notes"][0]


def test_focus_synthesis_requires_grounding_refs() -> None:
    with pytest.raises(FocusSynthesisSchemaError, match="evidence_refs"):
        build_focus_synthesis_artifact(
            landscapes=[_landscape()],
            analysis={"focuses": [_focus(evidence_refs=[])], "coverage_gaps": [], "notes": []},
        )


def test_focus_synthesis_rejects_invalid_readiness() -> None:
    with pytest.raises(FocusSynthesisSchemaError, match="readiness"):
        build_focus_synthesis_artifact(
            landscapes=[_landscape()],
            analysis={
                "focuses": [_focus(readiness="ready")],
                "coverage_gaps": [],
                "notes": [],
            },
        )
