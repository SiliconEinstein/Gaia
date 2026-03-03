"""Tests for DashScopeEmbeddingModel."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.review_pipeline.operators.embedding_dashscope import DashScopeEmbeddingModel


@pytest.fixture
def model():
    return DashScopeEmbeddingModel(
        api_url="https://embed.example.com/v1/embed",
        access_key="test-key-123",
    )


def _mock_response(vector: list[float], status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json={"data": {"vector": vector}},
        request=httpx.Request("POST", "https://embed.example.com/v1/embed"),
    )


async def test_embed_single_text(model):
    expected = [0.1, 0.2, 0.3]
    with patch.object(model, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(expected)
        mock_get.return_value = mock_client

        result = await model.embed(["hello world"])

    assert result == [expected]
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["json"]["text"] == "hello world"
    assert call_kwargs.kwargs["json"]["provider"] == "dashscope"
    assert call_kwargs.kwargs["headers"]["accessKey"] == "test-key-123"


async def test_embed_multiple_texts(model):
    vecs = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    with patch.object(model, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.post.side_effect = [_mock_response(v) for v in vecs]
        mock_get.return_value = mock_client

        result = await model.embed(["a", "b", "c"])

    assert result == vecs
    assert mock_client.post.call_count == 3


async def test_embed_http_error_raises(model):
    with patch.object(model, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.post.return_value = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://embed.example.com/v1/embed"),
        )
        mock_get.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await model.embed(["fail"])
