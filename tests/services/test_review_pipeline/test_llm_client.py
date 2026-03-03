"""Tests for the shared LLM client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.review_pipeline.config import LLMModelConfig
from services.review_pipeline.llm_client import LLMClient


@pytest.fixture
def config():
    return LLMModelConfig(provider="openai", name="gpt-5-mini")


@pytest.fixture
def client(config):
    return LLMClient(config)


async def test_complete_sends_correct_messages(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="result-text"))]

    with patch(
        "services.review_pipeline.llm_client.litellm.acompletion", new_callable=AsyncMock
    ) as mock_acomp:
        mock_acomp.return_value = mock_response
        result = await client.complete("sys prompt", "user prompt")

    assert result == "result-text"
    call_kwargs = mock_acomp.call_args
    messages = call_kwargs.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "sys prompt"}
    assert messages[1] == {"role": "user", "content": "user prompt"}
    assert call_kwargs.kwargs["model"] == "openai/gpt-5-mini"


async def test_complete_raises_on_failure(client):
    with patch(
        "services.review_pipeline.llm_client.litellm.acompletion", new_callable=AsyncMock
    ) as mock_acomp:
        mock_acomp.side_effect = Exception("connection refused")
        with pytest.raises(RuntimeError, match="LLM call failed"):
            await client.complete("sys", "usr")


async def test_model_routing_dptech():
    cfg = LLMModelConfig(provider="dptech", name="gpt-5-mini", temperature=0.5)
    client = LLMClient(cfg)
    assert client._call_config["model"] == "openai/gpt-5-mini"
    assert client._call_config["temperature"] == 0.5


async def test_invalid_provider_raises():
    cfg = LLMModelConfig(provider="nonexistent", name="foo")
    with pytest.raises(ValueError, match="Model mapping not found"):
        LLMClient(cfg)
