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


def test_assess_contract_forbids_workflow_terms_in_review_prose() -> None:
    contract = assess_contract(language="zh")
    payload = json.dumps(contract, ensure_ascii=False)

    assert "standalone scholarly mini-review" in payload
    assert "forbidden_review_terms" in contract
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
        assert term in contract["forbidden_review_terms"]


def test_assess_contract_requires_publication_style_review_fields() -> None:
    contract = assess_contract(language="zh")
    review_fields = contract["review_fields"]

    for field in [
        "title",
        "abstract",
        "key_points",
        "evidence_table",
        "limitations",
        "next_queries",
    ]:
        assert field in review_fields

    payload = json.dumps(contract, ensure_ascii=False)
    assert "Nature Reviews" in payload
    assert "numbered references" in payload
