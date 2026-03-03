"""Tests for LiteLLMJoinClient."""

from unittest.mock import AsyncMock

import pytest

from services.review_pipeline.operators.join import LiteLLMJoinClient


SAMPLE_LLM_RESPONSE = """\
<analysis anchor="0">
  <candidate id="10" relation="equivalence">
    <reason>Same claim about band gap energy.</reason>
  </candidate>
  <candidate id="20" relation="subsumption" direction="candidate_more_specific">
    <reason>Candidate specifies monolayer MoS2.</reason>
  </candidate>
  <candidate id="30" relation="subsumption" direction="anchor_more_specific">
    <reason>Anchor specifies temperature dependence.</reason>
  </candidate>
  <candidate id="40" relation="contradiction">
    <reason>Conflicting values: 1.8 eV vs 2.1 eV.</reason>
  </candidate>
  <candidate id="50" relation="unrelated">
    <reason>Different topic.</reason>
  </candidate>
</analysis>
"""


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.complete.return_value = SAMPLE_LLM_RESPONSE
    return client


@pytest.fixture
def join_client(mock_llm_client):
    return LiteLLMJoinClient(mock_llm_client)


async def test_find_joins_returns_correct_relations(join_client):
    candidates = [
        (10, "Band gap of MoS2 is 1.8 eV"),
        (20, "Band gap of monolayer MoS2 is 1.8 eV"),
        (30, "Band gap of TMDs"),
        (40, "Band gap of MoS2 is 2.1 eV"),
        (50, "Thermal conductivity of graphene"),
    ]
    trees = await join_client.find_joins("Band gap of MoS2", candidates)

    assert len(trees) == 4  # unrelated excluded
    by_target = {t.target_node_id: t for t in trees}

    assert by_target[10].relation == "equivalent"
    assert by_target[20].relation == "subsumed_by"
    assert by_target[30].relation == "subsumes"
    assert by_target[40].relation == "contradiction"

    for t in trees:
        assert t.source_node_index == 0
        assert t.verified is False


async def test_find_joins_empty_candidates(join_client):
    trees = await join_client.find_joins("some content", [])
    assert trees == []


async def test_find_joins_sends_correct_prompt(join_client, mock_llm_client):
    candidates = [(5, "test content")]
    await join_client.find_joins("anchor text", candidates)

    call_args = mock_llm_client.complete.call_args
    system_prompt = call_args.args[0]
    user_prompt = call_args.args[1]

    assert "logician" in system_prompt.lower()
    assert "anchor text" in user_prompt
    assert "test content" in user_prompt
    assert "Proposition 5" in user_prompt
