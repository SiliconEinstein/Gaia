"""Embedding computer for M6 Semantic Discovery.

Streaming pipeline: process pending variables in chunks of CHUNK_SIZE.
Each chunk: fetch content → compute embeddings → write to ByteHouse → free memory.
Constant memory usage regardless of total pending count.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from gaia.lkm.models.discovery import DiscoveryConfig

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 5000  # variables per pipeline chunk (content + embed + write)
_BH_BATCH_SIZE = 200  # ByteHouse insert batch size


class Embedder:
    """Low-level async embedding API caller with retry logic."""

    def __init__(self, config: DiscoveryConfig, access_key: str) -> None:
        self._config = config
        self._sem = asyncio.Semaphore(config.embedding_concurrency)
        self._client = httpx.AsyncClient(timeout=config.embedding_http_timeout)
        self._headers = {"accessKey": access_key, "Content-Type": "application/json"}

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string with retry."""
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
                    body = response.json()
                    if "data" not in body:
                        raise ValueError(
                            f"API returned no 'data' field: {body.get('code')}, "
                            f"{body.get('error', {}).get('msg', 'unknown')}"
                        )
                    return body["data"]["vector"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_exc = exc
                if attempt < self._config.embedding_max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        await self._client.aclose()


async def _fetch_content_for_chunk(
    storage,
    chunk: list[dict],
) -> list[tuple[str, str, str]]:
    """Fetch content for a chunk of pending globals.

    Returns list of (gcn_id, content, node_type) for items with valid content.
    """
    # Parse representative_lcn → local_id
    items: list[tuple[str, str, str]] = []  # (gcn_id, local_id, node_type)
    for meta in chunk:
        try:
            rep_lcn = json.loads(meta["representative_lcn"])
            local_id = rep_lcn["local_id"]
            items.append((meta["id"], local_id, meta.get("type", "")))
        except (KeyError, json.JSONDecodeError):
            pass

    if not items:
        return []

    # Batch fetch from LanceDB
    unique_local_ids = list({lid for _, lid, _ in items})
    local_vars = await storage.get_local_variables_by_ids(unique_local_ids)

    # Map back, skip empty content
    work_items = []
    for gcn_id, local_id, node_type in items:
        lv = local_vars.get(local_id)
        if lv and lv.content and len(lv.content.strip()) > 10:
            work_items.append((gcn_id, lv.content, node_type))

    return work_items


async def _embed_and_write_chunk(
    embedder: Embedder,
    bytehouse,
    work_items: list[tuple[str, str, str]],
    config: DiscoveryConfig,
) -> tuple[int, int]:
    """Embed a chunk and write results to ByteHouse.

    Returns (computed, failed) counts.
    """
    loop = asyncio.get_running_loop()
    computed = 0
    failed = 0

    async def _embed_one(gcn_id: str, content: str, node_type: str) -> dict | None:
        nonlocal failed
        try:
            vector = await embedder.embed(content)
            return {
                "gcn_id": gcn_id,
                "content": content,
                "node_type": node_type,
                "embedding": vector,
                "source_id": config.embedding_provider,
            }
        except Exception as exc:
            logger.warning("Embedding failed for %s: %s", gcn_id, exc)
            failed += 1
            return None

    # Compute embeddings (concurrency bounded by Embedder's semaphore)
    raw = await asyncio.gather(*[_embed_one(g, c, t) for g, c, t in work_items])
    results = [r for r in raw if r is not None]
    computed = len(results)

    # Write to ByteHouse in sub-batches
    for i in range(0, len(results), _BH_BATCH_SIZE):
        sub = results[i : i + _BH_BATCH_SIZE]
        await loop.run_in_executor(None, bytehouse.upsert_embeddings, sub)

    return computed, failed


async def compute_embeddings(
    storage,
    bytehouse,
    config: DiscoveryConfig,
    access_key: str,
) -> dict:
    """Streaming embedding pipeline.

    Processes pending variables in chunks of CHUNK_SIZE:
      fetch content → compute embeddings → write ByteHouse → free memory

    Memory usage is constant (~CHUNK_SIZE * avg_content_size) regardless
    of total pending count.

    Returns stats dict: {total, computed, skipped, failed}.
    """
    loop = asyncio.get_running_loop()

    # 1. Get all public global variable metadata (just IDs, small)
    globals_list: list[dict] = await storage.list_all_public_global_ids()
    total = len(globals_list)

    if total == 0:
        return {"total": 0, "computed": 0, "skipped": 0, "failed": 0}

    # 2. Find pending (not in ByteHouse)
    existing_ids: set[str] = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)
    pending = [g for g in globals_list if g["id"] not in existing_ids]
    skipped = total - len(pending)

    # Free globals_list — we only need pending from here
    del globals_list

    if not pending:
        logger.info("No pending embeddings to compute")
        return {"total": total, "computed": 0, "skipped": skipped, "failed": 0}

    n_chunks = (len(pending) + _CHUNK_SIZE - 1) // _CHUNK_SIZE
    logger.info(
        "Computing embeddings for %d/%d variables in %d chunks of %d",
        len(pending),
        total,
        n_chunks,
        _CHUNK_SIZE,
    )

    # 3. Streaming pipeline: chunk by chunk
    embedder = Embedder(config, access_key)
    total_computed = 0
    total_failed = 0

    for chunk_idx in range(n_chunks):
        start = chunk_idx * _CHUNK_SIZE
        chunk = pending[start : start + _CHUNK_SIZE]

        # Fetch content for this chunk
        work_items = await _fetch_content_for_chunk(storage, chunk)
        content_skipped = len(chunk) - len(work_items)

        # Embed and write
        if work_items:
            computed, failed = await _embed_and_write_chunk(
                embedder,
                bytehouse,
                work_items,
                config,
            )
            total_computed += computed
            total_failed += failed + content_skipped
        else:
            total_failed += content_skipped

        logger.info(
            "Chunk %d/%d: %d content → %d embedded, %d failed | cumulative: %d/%d",
            chunk_idx + 1,
            n_chunks,
            len(work_items),
            computed if work_items else 0,
            (failed if work_items else 0) + content_skipped,
            total_computed,
            len(pending),
        )

    await embedder.close()

    logger.info(
        "Embedding complete: %d computed, %d skipped (existing), %d failed",
        total_computed,
        skipped,
        total_failed,
    )
    return {
        "total": total,
        "computed": total_computed,
        "skipped": skipped,
        "failed": total_failed,
    }
