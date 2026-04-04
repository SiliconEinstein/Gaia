"""Embedding computer for M6 Semantic Discovery.

Fetches embeddings for all public global variable nodes that are not yet
stored in ByteHouse, using bounded concurrency and batch writes.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from gaia.lkm.models.discovery import DiscoveryConfig

logger = logging.getLogger(__name__)

_BATCH_SIZE = 200


class Embedder:
    """Low-level async embedding API caller with retry logic.

    Args:
        config: Discovery pipeline configuration.
        access_key: API access key sent in the ``accessKey`` request header.
    """

    def __init__(self, config: DiscoveryConfig, access_key: str) -> None:
        self._config = config
        self._sem = asyncio.Semaphore(config.embedding_concurrency)
        self._client = httpx.AsyncClient(timeout=config.embedding_http_timeout)
        self._headers = {"accessKey": access_key, "Content-Type": "application/json"}

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Retries up to ``config.embedding_max_retries`` times with linear
        back-off (``0.5 * (attempt + 1)`` seconds).

        Args:
            text: The text to embed.

        Returns:
            A list of floats (the embedding vector).

        Raises:
            httpx.HTTPError: If all retry attempts are exhausted.
        """
        last_exc: Exception | None = None
        for attempt in range(self._config.embedding_max_retries):
            try:
                async with self._sem:
                    response = await self._client.post(
                        self._config.embedding_api_url,
                        json={"text": text, "provider": self._config.embedding_provider},
                        headers=self._headers,
                    )
                    response.raise_for_status()
                    return response.json()["data"]["vector"]
            except (httpx.HTTPError, KeyError) as exc:
                last_exc = exc
                if attempt < self._config.embedding_max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


async def compute_embeddings(
    storage,
    bytehouse,
    config: DiscoveryConfig,
    access_key: str,
) -> dict:
    """Orchestrate embedding computation for all un-embedded public globals.

    1. Fetches all public global variable metadata from ``storage``.
    2. Finds pending IDs (not yet in ByteHouse).
    3. Fetches content via ``storage.get_local_variable(local_id).content``.
    4. Calls the embedding API with bounded concurrency.
    5. Writes results to ByteHouse in batches of 200.

    ByteHouse calls are synchronous and are wrapped with
    ``loop.run_in_executor`` to avoid blocking the event loop.

    Args:
        storage: A ``StorageManager`` instance with async read methods.
        bytehouse: A ``ByteHouseEmbeddingStore`` instance (sync methods).
        config: Discovery pipeline configuration.
        access_key: API access key for the embedding endpoint.

    Returns:
        Stats dict with keys: ``total``, ``computed``, ``skipped``, ``failed``.
    """
    loop = asyncio.get_event_loop()

    # 1. Retrieve all public global variable metadata
    globals_list: list[dict] = await storage.list_all_public_global_ids()
    total = len(globals_list)

    # 2. Find which ones already have embeddings
    existing_ids: set[str] = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)

    pending = [g for g in globals_list if g["gcn_id"] not in existing_ids]
    skipped = total - len(pending)

    embedder = Embedder(config, access_key)
    computed = 0
    failed = 0
    batch: list[dict] = []

    async def _flush_batch() -> None:
        if not batch:
            return
        current = list(batch)
        batch.clear()
        await loop.run_in_executor(None, bytehouse.upsert_embeddings, current)

    async def _process_one(meta: dict) -> None:
        nonlocal computed, failed
        gcn_id = meta["gcn_id"]
        node_type = meta.get("node_type", "")
        source_id = meta.get("source_id", "")

        # Parse representative_lcn to get the local node ID
        try:
            rep_lcn = json.loads(meta["representative_lcn"])
            local_id = rep_lcn["local_id"]
        except (KeyError, json.JSONDecodeError) as exc:
            logger.warning("Cannot parse representative_lcn for %s: %s", gcn_id, exc)
            failed += 1
            return

        # Fetch local variable content
        local_var = await storage.get_local_variable(local_id)
        if local_var is None:
            logger.warning("Local variable not found: %s (gcn=%s)", local_id, gcn_id)
            failed += 1
            return

        # Compute embedding
        try:
            vector = await embedder.embed(local_var.content)
        except Exception as exc:
            logger.warning("Embedding failed for %s: %s", gcn_id, exc)
            failed += 1
            return

        batch.append(
            {
                "gcn_id": gcn_id,
                "content": local_var.content,
                "node_type": node_type,
                "embedding": vector,
                "source_id": source_id,
            }
        )
        computed += 1

        # Flush once the batch is full
        if len(batch) >= _BATCH_SIZE:
            await _flush_batch()

    # Process all pending items (concurrency is bounded inside Embedder via semaphore)
    tasks = [_process_one(meta) for meta in pending]
    await asyncio.gather(*tasks)

    # Flush any remaining records
    await _flush_batch()

    await embedder.close()

    return {
        "total": total,
        "computed": computed,
        "skipped": skipped,
        "failed": failed,
    }
