"""DashScope embedding model — real implementation of EmbeddingModel ABC."""

from __future__ import annotations

import asyncio

import httpx

from services.review_pipeline.operators.embedding import EmbeddingModel


class DashScopeEmbeddingModel(EmbeddingModel):
    """Embedding model backed by a DashScope-compatible HTTP API.

    Sends each text as a single POST request and returns the vector from
    ``response["data"]["vector"]``.
    """

    def __init__(
        self,
        api_url: str,
        access_key: str,
        provider: str = "dashscope",
        max_rps: int = 600,
        http_timeout: int = 30,
    ) -> None:
        self._api_url = api_url
        self._access_key = access_key
        self._provider = provider
        self._sem = asyncio.Semaphore(max_rps)
        self._http_timeout = http_timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._http_timeout)
        return self._client

    async def _embed_single(self, text: str) -> list[float]:
        headers = {
            "accessKey": self._access_key,
            "Content-Type": "application/json",
        }
        payload = {"text": text, "provider": self._provider}
        async with self._sem:
            r = await self._get_client().post(self._api_url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["data"]["vector"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts (sequential HTTP calls)."""
        results: list[list[float]] = []
        for text in texts:
            vec = await self._embed_single(text)
            results.append(vec)
        return results

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
