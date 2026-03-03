"""Tests for LiteLLMVerifyClient."""

from unittest.mock import AsyncMock

import pytest

from services.review_pipeline.context import JoinTree
from services.review_pipeline.operators.verify import LiteLLMVerifyClient


SAMPLE_PASS_RESPONSE = """\
<verification edge_id="1" type="join">
  <result>pass</result>
  <checks>
    <check child="42" entails_parent="true">
      <reason>Child directly implies parent.</reason>
    </check>
  </checks>
  <quality>
    <classification_correct>true</classification_correct>
    <suggested_classification>subsumption</suggested_classification>
    <union_error>false</union_error>
    <union_error_detail></union_error_detail>
    <tightness>4</tightness>
    <substantiveness>5</substantiveness>
  </quality>
</verification>
"""

SAMPLE_FAIL_RESPONSE = """\
<verification edge_id="2" type="join">
  <result>fail</result>
  <checks>
    <check child="99" entails_parent="false">
      <reason>Child discusses a different phenomenon.</reason>
    </check>
  </checks>
  <quality>
    <classification_correct>false</classification_correct>
    <suggested_classification>unrelated</suggested_classification>
    <union_error>true</union_error>
    <union_error_detail>Parent combines claims from different sources.</union_error_detail>
    <tightness>2</tightness>
    <substantiveness>1</substantiveness>
  </quality>
</verification>
"""


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def verify_client(mock_llm):
    return LiteLLMVerifyClient(mock_llm)


async def test_verify_pass(verify_client, mock_llm):
    mock_llm.complete.return_value = SAMPLE_PASS_RESPONSE
    tree = JoinTree(source_node_index=0, target_node_id=42, relation="equivalent")

    result = await verify_client.verify([tree])

    assert len(result) == 1
    assert result[0].verified is True
    assert "Tightness: 4/5" in result[0].reasoning
    assert "Substantiveness: 5/5" in result[0].reasoning


async def test_verify_fail(verify_client, mock_llm):
    mock_llm.complete.return_value = SAMPLE_FAIL_RESPONSE
    tree = JoinTree(source_node_index=0, target_node_id=99, relation="subsumes")

    result = await verify_client.verify([tree])

    assert result[0].verified is False
    assert "Union error" in result[0].reasoning
    assert "does NOT entail" in result[0].reasoning


async def test_verify_multiple_trees(verify_client, mock_llm):
    mock_llm.complete.side_effect = [SAMPLE_PASS_RESPONSE, SAMPLE_FAIL_RESPONSE]
    trees = [
        JoinTree(source_node_index=0, target_node_id=42, relation="equivalent"),
        JoinTree(source_node_index=0, target_node_id=99, relation="subsumes"),
    ]

    result = await verify_client.verify(trees)

    assert len(result) == 2
    assert result[0].verified is True
    assert result[1].verified is False
    assert mock_llm.complete.call_count == 2


async def test_verify_sends_prompt_with_content(verify_client, mock_llm):
    mock_llm.complete.return_value = SAMPLE_PASS_RESPONSE
    tree = JoinTree(
        source_node_index=1,
        target_node_id=10,
        relation="subsumed_by",
        source_content="Band gap of MoS2 is 1.8 eV",
        target_content="Monolayer MoS2 band gap is 1.8 eV",
    )

    await verify_client.verify([tree])

    system_prompt = mock_llm.complete.call_args.args[0]
    assert "logician" in system_prompt.lower()
    user_prompt = mock_llm.complete.call_args.args[1]
    assert "Band gap of MoS2 is 1.8 eV" in user_prompt
    assert "Monolayer MoS2 band gap is 1.8 eV" in user_prompt
    assert "Child 10" in user_prompt
