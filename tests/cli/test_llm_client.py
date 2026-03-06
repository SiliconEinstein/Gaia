"""Tests for review LLM client."""

from unittest.mock import AsyncMock, patch

import pytest

from cli.llm_client import review_claim


@pytest.mark.asyncio
async def test_review_claim_returns_parsed_result():
    mock_response = """score: 0.92
justification: "test"
confirmed_premises: [1, 2]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []"""

    with patch("cli.llm_client._call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await review_claim(
            claim={
                "id": 3,
                "content": "C",
                "type": "deduction",
                "why": "because",
                "premise": [1, 2],
            },
            all_claims={1: {"id": 1, "content": "A"}, 2: {"id": 2, "content": "B"}},
            model="test-model",
        )
    assert result["score"] == pytest.approx(0.92)
    assert result["confirmed_premises"] == [1, 2]
