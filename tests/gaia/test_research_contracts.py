"""Unit tests for research action LLM contracts."""

from __future__ import annotations

import json

from gaia.engine.research.contracts import assess_contract


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
