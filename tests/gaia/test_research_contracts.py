"""Unit tests for research action LLM contracts."""

from __future__ import annotations

import json

from gaia.engine.research.contracts import assess_contract, field_map_contract


def test_field_map_contract_describes_autonomous_review_taxonomy() -> None:
    contract = field_map_contract(language="zh")
    payload = json.dumps(contract, ensure_ascii=False)

    assert contract["contract"] == "gaia.research.field_map"
    assert "buckets" in contract["output_required_fields"]
    assert "recommended_expansions" in contract["output_required_fields"]
    assert "Do not rely on review articles being present" in payload
    assert "field taxonomy" in payload


def test_assess_contract_forbids_workflow_terms_in_structured_prose() -> None:
    contract = assess_contract(language="zh")
    payload = json.dumps(contract, ensure_ascii=False)

    assert "final review prose" in payload
    assert "forbidden_prose_terms" in contract
    for term in [
        "Gaia",
        "LKM",
        "item",
        "artifact",
        "evidence packet",
        "agent",
        "CLI",
        "trace",
        "run",
        "round",
        "workflow",
        "targeted expand",
        "source promotion",
        "assessment JSON",
    ]:
        assert term in contract["forbidden_prose_terms"]


def test_assess_contract_keeps_assessment_structured_not_article_shaped() -> None:
    contract = assess_contract(language="zh")

    required = contract["output_required_fields"]
    optional = contract["output_optional_fields"]
    assert set(required) == {"relations", "candidate_obligations"}
    assert "limitations" in optional
    assert "next_queries" in optional

    payload = json.dumps(contract, ensure_ascii=False)
    assert "Do not write the final report" in payload
    assert "mini-review" in payload
