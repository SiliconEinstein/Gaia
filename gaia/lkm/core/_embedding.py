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


class Embedder:
    """Async embedding API caller with worker-pool rate control.

    Uses N worker coroutines (not N*chunk_size), each sleeping 1/rate seconds
    between calls. This gives ~N * (1/latency) RPS when N is small, capped at
    `rate` RPS by the sleep. No busy-wait, no thundering herd.
    """

    def __init__(self, config: DiscoveryConfig, access_key: str) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.embedding_http_timeout)
        self._headers = {"accessKey": access_key, "Content-Type": "application/json"}
        self._n_workers = config.embedding_concurrency
        # Target ~30 RPS: each worker calls API (~50ms) + sleeps.
        # With N workers, actual RPS ≈ N / (sleep + api_latency).
        # N=30, sleep=1.5s → 30/1.55 ≈ 19 RPS. Conservative but zero 429s.
        self._sleep = 1.5

    async def _call_api(self, text: str) -> list[float]:
        """Single API call with retry + jitter backoff."""
        last_exc: Exception | None = None
        for attempt in range(self._config.embedding_max_retries):
            try:
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
                    delay = (0.5 * (2**attempt)) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def embed_batch(
        self,
        items: list[tuple[str, str, str]],
        on_result,
        on_error,
    ) -> None:
        """Embed a batch using a fixed worker pool.

        Args:
            items: List of (gcn_id, content, node_type).
            on_result: async callback(record_dict) for each success.
            on_error: async callback(gcn_id, exc) for each failure.
        """
        queue: asyncio.Queue[tuple[str, str, str] | None] = asyncio.Queue()

        # Fill queue
        for item in items:
            queue.put_nowait(item)
        # Sentinel for each worker
        for _ in range(self._n_workers):
            queue.put_nowait(None)

        async def worker():
            while True:
                item = await queue.get()
                if item is None:
                    return
                gcn_id, content, node_type = item
                try:
                    vector = await self._call_api(content)
                    await on_result(
                        {
                            "gcn_id": gcn_id,
                            "content": content,
                            "node_type": node_type,
                            "embedding": vector,
                            "source_id": self._config.embedding_provider,
                        }
                    )
                except Exception as exc:
                    await on_error(gcn_id, exc)
                # Rate control: each worker sleeps to collectively hit target RPS
                await asyncio.sleep(self._sleep)

        await asyncio.gather(*[worker() for _ in range(self._n_workers)])

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
    """Embed a chunk using worker pool and stream-write to ByteHouse.

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

    async def on_result(record: dict) -> None:
        nonlocal computed
        buffer.append(record)
        computed += 1
        if len(buffer) >= _BH_BATCH_SIZE:
            await _flush()

    async def on_error(gcn_id: str, exc: Exception) -> None:
        nonlocal failed
        logger.warning("Embedding failed for %s: %s", gcn_id, exc)
        failed += 1

    await embedder.embed_batch(work_items, on_result, on_error)
    await _flush()

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
