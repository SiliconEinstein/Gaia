"""Shared embedding model interface and implementations."""

from __future__ import annotations

import hashlib
import math
import os
import struct
from abc import ABC, abstractmethod


class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        ...


class DPEmbeddingModel(EmbeddingModel):  # pragma: no cover
    """Embedding model using internal DP embedding service.

    API: POST {api_url} with {"text": "...", "provider": "dashscope"}
    Response: {"data": {"vector": [float, ...]}}

    Env vars:
        API_URL: embedding service URL
        ACCESS_KEY: authentication key (sent as accessKey header)
    """

    def __init__(
        self,
        api_url: str | None = None,
        access_key: str | None = None,
        provider: str = "dashscope",
        max_concurrent: int = 8,
    ) -> None:
        self._api_url = api_url or os.getenv("API_URL", "")
        self._access_key = access_key or os.getenv("ACCESS_KEY", "")
        self._provider = provider
        self._max_concurrent = max_concurrent

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        import httpx

        headers = {
            "accessKey": self._access_key,
            "Content-Type": "application/json",
        }
        sem = asyncio.Semaphore(self._max_concurrent)

        async def _embed_one(client: httpx.AsyncClient, text: str) -> list[float]:
            payload = {"text": text, "provider": self._provider}
            async with sem:
                for attempt in range(3):
                    try:
                        r = await client.post(self._api_url, headers=headers, json=payload)
                        r.raise_for_status()
                        body = r.json()
                        if "data" not in body or "vector" not in body.get("data", {}):
                            raise ValueError(f"Unexpected API response: {body}")
                        return body["data"]["vector"]
                    except (httpx.ReadTimeout, httpx.ConnectTimeout, ValueError):
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2**attempt)

        async with httpx.AsyncClient(timeout=60) as client:
            tasks = [_embed_one(client, t) for t in texts]
            return await asyncio.gather(*tasks)


class StubEmbeddingModel(EmbeddingModel):
    """Deterministic stub: hashes text to produce reproducible vectors."""

    def __init__(self, dim: int = 512) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            raw = digest * ((self._dim * 4 // len(digest)) + 1)
            floats = list(struct.unpack(f"<{self._dim}f", raw[: self._dim * 4]))
            floats = [0.0 if (math.isnan(f) or math.isinf(f)) else f for f in floats]
            mag = max(abs(f) for f in floats) or 1.0
            results.append([f / mag for f in floats])
        return results
