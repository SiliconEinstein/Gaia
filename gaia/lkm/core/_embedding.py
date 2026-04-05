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
_CONTENT_BATCH_SIZE = 500  # batch size for LanceDB content lookups


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
                    return response.json()["data"]["vector"]
            except (httpx.HTTPError, KeyError) as exc:
                last_exc = exc
                if attempt < self._config.embedding_max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        await self._client.aclose()


async def _batch_fetch_content(
    storage,
    pending: list[dict],
) -> dict[str, str]:
    """Batch-fetch content for pending globals via local variable lookup.

    Uses storage.get_local_variables_by_ids() for efficient batch queries
    (one LanceDB query per 500 IDs instead of one per ID).

    Returns {gcn_id: content_text} for items where content was found.
    """
    gcn_to_content: dict[str, str] = {}

    # Parse representative_lcn to get local_ids
    items: list[tuple[str, str]] = []  # (gcn_id, local_id)
    for meta in pending:
        try:
            rep_lcn = json.loads(meta["representative_lcn"])
            local_id = rep_lcn["local_id"]
            items.append((meta["id"], local_id))
        except (KeyError, json.JSONDecodeError):
            logger.warning("Cannot parse representative_lcn for %s", meta["id"])

    # Deduplicate local_ids
    unique_local_ids = list({local_id for _, local_id in items})

    logger.info("Batch-fetching content for %d unique local variables...", len(unique_local_ids))
    local_vars = await storage.get_local_variables_by_ids(unique_local_ids)

    # Map back to gcn_ids
    for gcn_id, local_id in items:
        lv = local_vars.get(local_id)
        if lv and lv.content:
            gcn_to_content[gcn_id] = lv.content

    logger.info(
        "Content fetch: %d requested, %d unique local, %d found",
        len(pending), len(unique_local_ids), len(gcn_to_content),
    )
    return gcn_to_content


async def compute_embeddings(
    storage,
    bytehouse,
    config: DiscoveryConfig,
    access_key: str,
) -> dict:
    """Orchestrate embedding computation for all un-embedded public globals.

    Flow:
    1. Get all public global variable metadata
    2. Find pending (not in ByteHouse)
    3. Batch-fetch content from LanceDB
    4. Compute embeddings with bounded concurrency
    5. Batch-write to ByteHouse

    Returns stats dict: {total, computed, skipped, failed}.
    """
    loop = asyncio.get_running_loop()

    # 1. Retrieve all public global variable metadata
    globals_list: list[dict] = await storage.list_all_public_global_ids()
    total = len(globals_list)

    if total == 0:
        return {"total": 0, "computed": 0, "skipped": 0, "failed": 0}

    # 2. Find pending
    existing_ids: set[str] = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)
    pending = [g for g in globals_list if g["id"] not in existing_ids]
    skipped = total - len(pending)

    if not pending:
        logger.info("No pending embeddings to compute")
        return {"total": total, "computed": 0, "skipped": skipped, "failed": 0}

    logger.info("Computing embeddings for %d/%d variables", len(pending), total)

    # 3. Batch-fetch content
    gcn_to_content = await _batch_fetch_content(storage, pending)

    # Build work items: (gcn_id, content, node_type)
    work_items = []
    content_failed = 0
    for meta in pending:
        gcn_id = meta["id"]
        if gcn_id not in gcn_to_content:
            content_failed += 1
            continue
        work_items.append((gcn_id, gcn_to_content[gcn_id], meta.get("type", "")))

    logger.info(
        "%d items with content, %d without content", len(work_items), content_failed
    )

    # 4. Compute embeddings with bounded concurrency
    embedder = Embedder(config, access_key)
    results: list[dict] = []
    embed_failed = 0

    sem = asyncio.Semaphore(config.embedding_concurrency)

    async def _embed_one(gcn_id: str, content: str, node_type: str) -> dict | None:
        nonlocal embed_failed
        try:
            async with sem:
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
            embed_failed += 1
            return None

    # Run with bounded concurrency
    tasks = [_embed_one(gid, content, ntype) for gid, content, ntype in work_items]
    raw_results = await asyncio.gather(*tasks)
    results = [r for r in raw_results if r is not None]

    await embedder.close()

    # 5. Batch-write to ByteHouse
    for i in range(0, len(results), _BATCH_SIZE):
        chunk = results[i : i + _BATCH_SIZE]
        await loop.run_in_executor(None, bytehouse.upsert_embeddings, chunk)
        logger.info("Wrote batch %d/%d to ByteHouse", i // _BATCH_SIZE + 1,
                     (len(results) + _BATCH_SIZE - 1) // _BATCH_SIZE)

    computed = len(results)
    failed = content_failed + embed_failed

    logger.info(
        "Embedding complete: %d computed, %d skipped, %d failed",
        computed, skipped, failed,
    )
    return {"total": total, "computed": computed, "skipped": skipped, "failed": failed}
