"""Embedding computer for M6 Semantic Discovery.

Pipelined streaming: overlaps content prefetch with embedding computation.
Each chunk flows through: fetch content → embed → write ByteHouse.
While chunk N is being embedded, chunk N+1's content is being prefetched.

Constant memory: ~2 chunks worth of data at peak (one embedding, one prefetching).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time

import httpx

from gaia.lkm.models.discovery import DiscoveryConfig

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 5000  # variables per pipeline chunk
_BH_BATCH_SIZE = 200  # ByteHouse insert batch size


class _TokenBucket:
    """Async token bucket rate limiter.

    Guarantees no more than `rate` requests per second, with burst up to `rate`.
    Much better than Semaphore for API rate limiting — Semaphore limits concurrency
    but not RPS, so retries can cause thundering herd.
    """

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._max = rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self._max, self._tokens + elapsed * self._rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            # Wait a bit before retrying — stagger to avoid thundering herd
            await asyncio.sleep(1.0 / self._rate + random.uniform(0, 0.01))


class Embedder:
    """Low-level async embedding API caller with token-bucket rate limiting."""

    def __init__(self, config: DiscoveryConfig, access_key: str) -> None:
        self._config = config
        # Token bucket at configured RPS (not semaphore — avoids retry storms)
        self._bucket = _TokenBucket(rate=config.embedding_concurrency)
        self._client = httpx.AsyncClient(timeout=config.embedding_http_timeout)
        self._headers = {"accessKey": access_key, "Content-Type": "application/json"}

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string with retry + jitter backoff."""
        last_exc: Exception | None = None
        for attempt in range(self._config.embedding_max_retries):
            try:
                await self._bucket.acquire()
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
                    # Jitter backoff: base * 2^attempt + random
                    delay = (0.5 * (2**attempt)) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
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
    items: list[tuple[str, str, str]] = []
    for meta in chunk:
        try:
            rep_lcn = json.loads(meta["representative_lcn"])
            local_id = rep_lcn["local_id"]
            items.append((meta["id"], local_id, meta.get("type", "")))
        except (KeyError, json.JSONDecodeError):
            pass

    if not items:
        return []

    unique_local_ids = list({lid for _, lid, _ in items})
    local_vars = await storage.get_local_variables_by_ids(unique_local_ids)

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
    """Embed a chunk and stream results to ByteHouse as they complete.

    Writes to ByteHouse in batches of _BH_BATCH_SIZE as embeddings arrive,
    instead of waiting for all embeddings to finish first.

    Returns (computed, failed) counts.
    """
    loop = asyncio.get_running_loop()
    computed = 0
    failed = 0
    buffer: list[dict] = []

    async def _flush():
        if buffer:
            batch = list(buffer)
            buffer.clear()
            await loop.run_in_executor(None, bytehouse.upsert_embeddings, batch)

    async def _embed_one(gcn_id: str, content: str, node_type: str) -> None:
        nonlocal computed, failed
        try:
            vector = await embedder.embed(content)
            buffer.append(
                {
                    "gcn_id": gcn_id,
                    "content": content,
                    "node_type": node_type,
                    "embedding": vector,
                    "source_id": config.embedding_provider,
                }
            )
            computed += 1
            if len(buffer) >= _BH_BATCH_SIZE:
                await _flush()
        except Exception as exc:
            logger.warning("Embedding failed for %s: %s", gcn_id, exc)
            failed += 1

    await asyncio.gather(*[_embed_one(g, c, t) for g, c, t in work_items])
    await _flush()  # write remaining

    return computed, failed


async def compute_embeddings(
    storage,
    bytehouse,
    config: DiscoveryConfig,
    access_key: str,
) -> dict:
    """Pipelined streaming embedding computation.

    Optimizations over naive approach:
    1. Pipelined prefetch: while chunk N embeds, chunk N+1 content is fetched
    2. Streaming writes: ByteHouse inserts happen as embeddings complete
    3. Constant memory: only ~2 chunks in memory at peak
    4. Resumable: existing ByteHouse embeddings skipped via COUNT (not full ID set)
    5. ETA logging: per-chunk timing with estimated completion

    Returns stats dict: {total, computed, skipped, failed}.
    """
    loop = asyncio.get_running_loop()

    # 1. Get pending list
    globals_list: list[dict] = await storage.list_all_public_global_ids()
    total = len(globals_list)

    if total == 0:
        return {"total": 0, "computed": 0, "skipped": 0, "failed": 0}

    # Fetch existing IDs to compute pending set
    existing_ids: set[str] = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)
    pending = [g for g in globals_list if g["id"] not in existing_ids]
    skipped = total - len(pending)
    del globals_list, existing_ids

    if not pending:
        logger.info("No pending embeddings to compute")
        return {"total": total, "computed": 0, "skipped": skipped, "failed": 0}

    n_chunks = (len(pending) + _CHUNK_SIZE - 1) // _CHUNK_SIZE
    logger.info(
        "Pending: %d/%d variables, %d chunks of %d",
        len(pending),
        total,
        n_chunks,
        _CHUNK_SIZE,
    )

    # 2. Pipelined streaming: prefetch chunk N+1 while embedding chunk N
    embedder = Embedder(config, access_key)
    total_computed = 0
    total_failed = 0
    pipeline_start = time.monotonic()
    chunk_times: list[float] = []

    # Kick off prefetch for first chunk
    chunks = [pending[i * _CHUNK_SIZE : (i + 1) * _CHUNK_SIZE] for i in range(n_chunks)]
    next_prefetch: asyncio.Task | None = asyncio.create_task(
        _fetch_content_for_chunk(storage, chunks[0])
    )

    for chunk_idx in range(n_chunks):
        chunk_start = time.monotonic()

        # Await current chunk's content (prefetched in previous iteration)
        work_items = await next_prefetch

        # Start prefetching next chunk immediately
        if chunk_idx + 1 < n_chunks:
            next_prefetch = asyncio.create_task(
                _fetch_content_for_chunk(storage, chunks[chunk_idx + 1])
            )
        else:
            next_prefetch = None  # type: ignore[assignment]

        content_skipped = len(chunks[chunk_idx]) - len(work_items)

        # Embed and stream-write
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
            computed, failed = 0, 0
            total_failed += content_skipped

        chunk_elapsed = time.monotonic() - chunk_start
        chunk_times.append(chunk_elapsed)

        # ETA calculation
        avg_chunk_time = sum(chunk_times) / len(chunk_times)
        remaining_chunks = n_chunks - chunk_idx - 1
        eta_seconds = avg_chunk_time * remaining_chunks
        eta_min = eta_seconds / 60

        rps = computed / chunk_elapsed if chunk_elapsed > 0 else 0

        logger.info(
            "Chunk %d/%d: %d→%d ok, %d fail | %.0fs (%.0f RPS) | cumulative %d/%d | ETA %.0fmin",
            chunk_idx + 1,
            n_chunks,
            len(work_items),
            computed,
            failed + content_skipped,
            chunk_elapsed,
            rps,
            total_computed,
            len(pending),
            eta_min,
        )

    await embedder.close()

    total_elapsed = time.monotonic() - pipeline_start
    logger.info(
        "Embedding complete: %d computed, %d skipped, %d failed in %.0fs (%.1f RPS avg)",
        total_computed,
        skipped,
        total_failed,
        total_elapsed,
        total_computed / total_elapsed if total_elapsed > 0 else 0,
    )
    return {
        "total": total,
        "computed": total_computed,
        "skipped": skipped,
        "failed": total_failed,
    }
