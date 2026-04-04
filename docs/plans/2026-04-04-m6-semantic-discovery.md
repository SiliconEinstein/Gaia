# M6 — Semantic Discovery Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the semantic discovery pipeline — compute embeddings for global variable nodes via an external API, store them in ByteHouse, and cluster semantically similar variables using FAISS Union-Find.

**Architecture:** Three layers: (1) `ByteHouseEmbeddingStore` handles CRUD for embedding vectors in ByteHouse/ClickHouse, (2) `_embedding.py` orchestrates async embedding computation via an external HTTP API with concurrency control, (3) `_clustering.py` loads embeddings into FAISS IndexFlatIP and clusters via Union-Find with constraint filtering. The entry point `discovery.py` wires them together.

**Tech Stack:** Python 3.12, httpx (async embedding API calls), clickhouse-connect (ByteHouse), faiss-cpu (ANN search + clustering), numpy, pydantic v2

**Spec:** `docs/specs/2026-04-04-m6-semantic-discovery.md`

---

## File Structure

```
gaia/lkm/models/
    discovery.py              # NEW — SemanticCluster, ClusteringResult, ClusteringStats, DiscoveryConfig

gaia/lkm/storage/
    bytehouse_store.py        # NEW — ByteHouseEmbeddingStore: DDL, upsert, bulk load, pending query
    config.py                 # MODIFY — add ByteHouse + embedding config fields to StorageConfig

gaia/lkm/core/
    _embedding.py             # NEW — EmbeddingComputer: async API calls + ByteHouse write
    _clustering.py            # NEW — FAISS IndexFlatIP + Union-Find clustering
    discovery.py              # NEW — run_semantic_discovery() entry point

gaia/lkm/storage/
    lance_store.py            # MODIFY — add list_all_global_variable_ids() for full scan

tests/gaia/lkm/models/
    test_discovery_models.py  # NEW — model unit tests

tests/gaia/lkm/storage/
    test_bytehouse_store.py   # NEW — ByteHouse store unit tests (mocked connection)

tests/gaia/lkm/core/
    test_embedding.py         # NEW — embedding computer unit tests
    test_clustering.py        # NEW — FAISS clustering unit tests
    test_discovery.py         # NEW — integration test for full pipeline

pyproject.toml               # MODIFY — add faiss-cpu dependency
```

---

## Chunk 1: Data Models + Configuration

### Task 1: Discovery Data Models

**Files:**
- Create: `gaia/lkm/models/discovery.py`
- Modify: `gaia/lkm/models/__init__.py`
- Test: `tests/gaia/lkm/models/test_discovery_models.py`

- [ ] **Step 1: Write failing tests for discovery models**

```python
# tests/gaia/lkm/models/test_discovery_models.py
"""Tests for M6 discovery data models."""

from datetime import datetime, timezone

from gaia.lkm.models.discovery import (
    ClusteringResult,
    ClusteringStats,
    DiscoveryConfig,
    SemanticCluster,
)


def test_semantic_cluster_fields():
    c = SemanticCluster(
        cluster_id="cl_001",
        node_type="claim",
        gcn_ids=["gcn_aaa", "gcn_bbb"],
        centroid_gcn_id="gcn_aaa",
        avg_similarity=0.92,
        min_similarity=0.88,
    )
    assert c.cluster_id == "cl_001"
    assert len(c.gcn_ids) == 2
    assert c.centroid_gcn_id == "gcn_aaa"


def test_clustering_stats_defaults():
    s = ClusteringStats(
        total_variables_scanned=1000,
        total_embeddings_computed=50,
        total_clusters=10,
        cluster_size_distribution={2: 5, 3: 3, 5: 2},
        elapsed_seconds=12.5,
    )
    assert s.total_clusters == 10


def test_clustering_result_roundtrip():
    now = datetime.now(tz=timezone.utc)
    r = ClusteringResult(
        clusters=[],
        stats=ClusteringStats(
            total_variables_scanned=0,
            total_embeddings_computed=0,
            total_clusters=0,
            cluster_size_distribution={},
            elapsed_seconds=0.0,
        ),
        timestamp=now,
    )
    assert r.timestamp == now
    assert r.clusters == []


def test_discovery_config_defaults():
    c = DiscoveryConfig()
    assert c.embedding_dim == 512
    assert c.similarity_threshold == 0.85
    assert c.faiss_k == 100
    assert c.max_cluster_size == 20
    assert c.exclude_same_factor is True
    assert c.embedding_concurrency == 24
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lkm/models/test_discovery_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gaia.lkm.models.discovery'`

- [ ] **Step 3: Implement discovery models**

```python
# gaia/lkm/models/discovery.py
"""Semantic discovery models — M6 output types and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SemanticCluster:
    """A group of semantically similar global variable nodes."""

    cluster_id: str
    node_type: str  # "claim" | "question" | "setting" | "action"
    gcn_ids: list[str]
    centroid_gcn_id: str  # gcn_id closest to centroid
    avg_similarity: float
    min_similarity: float


@dataclass
class ClusteringStats:
    """Statistics from a clustering run."""

    total_variables_scanned: int
    total_embeddings_computed: int
    total_clusters: int
    cluster_size_distribution: dict[int, int]  # size → count
    elapsed_seconds: float


@dataclass
class ClusteringResult:
    """Complete output of semantic discovery."""

    clusters: list[SemanticCluster]
    stats: ClusteringStats
    timestamp: datetime


@dataclass
class DiscoveryConfig:
    """Configuration for semantic discovery pipeline."""

    # Embedding API
    embedding_api_url: str = "https://openapi.dp.tech/openapi/v1/test/vectorize"
    embedding_provider: str = "dashscope"
    embedding_dim: int = 512
    embedding_concurrency: int = 24
    embedding_max_retries: int = 3
    embedding_http_timeout: int = 30

    # Clustering
    similarity_threshold: float = 0.85
    faiss_k: int = 100
    max_cluster_size: int = 20
    exclude_same_factor: bool = True
    faiss_index_type: str = "flat"
```

- [ ] **Step 4: Update `gaia/lkm/models/__init__.py`** — add exports for `SemanticCluster`, `ClusteringResult`, `ClusteringStats`, `DiscoveryConfig`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/models/test_discovery_models.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add gaia/lkm/models/discovery.py gaia/lkm/models/__init__.py tests/gaia/lkm/models/test_discovery_models.py
git commit -m "feat(m6): add discovery data models and config"
```

---

### Task 2: Storage Config — ByteHouse + Embedding fields

**Files:**
- Modify: `gaia/lkm/storage/config.py`
- Test: `tests/gaia/lkm/storage/test_config.py` (create if not exists)

- [ ] **Step 1: Write failing test for new config fields**

```python
# tests/gaia/lkm/storage/test_config.py (append or create)
"""Tests for storage config ByteHouse fields."""

import os

from gaia.lkm.storage.config import StorageConfig


def test_bytehouse_defaults():
    c = StorageConfig()
    assert c.bytehouse_host == ""
    assert c.bytehouse_database == "paper_data"


def test_bytehouse_from_env(monkeypatch):
    monkeypatch.setenv("BYTEHOUSE_HOST", "gw.bytehouse.volces.com")
    monkeypatch.setenv("BYTEHOUSE_USER", "u")
    monkeypatch.setenv("BYTEHOUSE_PASSWORD", "p")
    monkeypatch.setenv("BYTEHOUSE_DATABASE", "mydb")
    monkeypatch.setenv("ACCESS_KEY", "ak_test")
    c = StorageConfig()
    assert c.bytehouse_host == "gw.bytehouse.volces.com"
    assert c.bytehouse_database == "mydb"
    assert c.embedding_access_key == "ak_test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia/lkm/storage/test_config.py -v -k bytehouse`
Expected: FAIL — `AttributeError: bytehouse_host`

- [ ] **Step 3: Add ByteHouse + embedding fields to StorageConfig**

Add to `gaia/lkm/storage/config.py` `StorageConfig` class:

```python
    # ByteHouse (ClickHouse-compatible)
    bytehouse_host: str = ""
    bytehouse_user: str = ""
    bytehouse_password: str = ""
    bytehouse_database: str = "paper_data"

    # Embedding API
    embedding_access_key: str = ""
```

And in `model_post_init`, add fallbacks:

```python
        # ByteHouse fallbacks from BYTEHOUSE_* env vars
        if not self.bytehouse_host:
            self.bytehouse_host = os.environ.get("BYTEHOUSE_HOST", "")
        if not self.bytehouse_user:
            self.bytehouse_user = os.environ.get("BYTEHOUSE_USER", "")
        if not self.bytehouse_password:
            self.bytehouse_password = os.environ.get("BYTEHOUSE_PASSWORD", "")
        bh_db = os.environ.get("BYTEHOUSE_DATABASE", "")
        if bh_db:
            self.bytehouse_database = bh_db
        # Embedding API key fallback
        if not self.embedding_access_key:
            self.embedding_access_key = os.environ.get("ACCESS_KEY", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gaia/lkm/storage/test_config.py -v -k bytehouse`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add gaia/lkm/storage/config.py tests/gaia/lkm/storage/test_config.py
git commit -m "feat(m6): add ByteHouse and embedding config fields"
```

---

## Chunk 2: ByteHouse Embedding Store

### Task 3: ByteHouseEmbeddingStore

**Files:**
- Create: `gaia/lkm/storage/bytehouse_store.py`
- Modify: `gaia/lkm/storage/__init__.py`
- Test: `tests/gaia/lkm/storage/test_bytehouse_store.py`

**Key design decisions:**
- Uses `clickhouse-connect` (already in deps) — ByteHouse is ClickHouse-compatible
- All methods are sync (ClickHouse driver is sync); callers wrap with `run_in_executor`
- Table: `paper_data.node_embeddings` with `HaUniqueMergeTree` on `gcn_id`
- Embedding stored as `Array(Float32)` — ClickHouse native array type

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/storage/test_bytehouse_store.py
"""Tests for ByteHouseEmbeddingStore.

Uses unittest.mock to mock clickhouse_connect.get_client.
"""

from unittest.mock import MagicMock, call, patch

import numpy as np

from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore


def _make_store() -> tuple[ByteHouseEmbeddingStore, MagicMock]:
    with patch("gaia.lkm.storage.bytehouse_store.clickhouse_connect") as mock_cc:
        mock_client = MagicMock()
        mock_cc.get_client.return_value = mock_client
        store = ByteHouseEmbeddingStore(
            host="localhost", user="u", password="p", database="test_db"
        )
        return store, mock_client


def test_constructor_connects():
    store, mock_client = _make_store()
    assert store._client is mock_client


def test_ensure_table_executes_ddl():
    store, mock_client = _make_store()
    store.ensure_table()
    assert mock_client.command.called
    ddl = mock_client.command.call_args[0][0]
    assert "node_embeddings" in ddl
    assert "HaUniqueMergeTree" in ddl


def test_get_existing_gcn_ids():
    store, mock_client = _make_store()
    mock_client.query.return_value.result_rows = [("gcn_aaa",), ("gcn_bbb",)]
    result = store.get_existing_gcn_ids()
    assert result == {"gcn_aaa", "gcn_bbb"}


def test_upsert_embeddings():
    store, mock_client = _make_store()
    records = [
        {
            "gcn_id": "gcn_aaa",
            "content": "YBCO superconducts at 90K",
            "node_type": "claim",
            "embedding": [0.1] * 512,
            "source_id": "dashscope-v1",
        }
    ]
    store.upsert_embeddings(records)
    assert mock_client.insert.called


def test_load_embeddings_by_type():
    store, mock_client = _make_store()
    # Simulate query result: columns gcn_id, embedding
    mock_client.query.return_value.result_rows = [
        ("gcn_aaa", [0.1] * 512),
        ("gcn_bbb", [0.2] * 512),
    ]
    ids, matrix = store.load_embeddings_by_type("claim")
    assert ids == ["gcn_aaa", "gcn_bbb"]
    assert matrix.shape == (2, 512)


def test_load_embeddings_empty():
    store, mock_client = _make_store()
    mock_client.query.return_value.result_rows = []
    ids, matrix = store.load_embeddings_by_type("claim")
    assert ids == []
    assert matrix.shape == (0,)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lkm/storage/test_bytehouse_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ByteHouseEmbeddingStore**

```python
# gaia/lkm/storage/bytehouse_store.py
"""ByteHouse (ClickHouse-compatible) store for node embeddings."""

from __future__ import annotations

import logging

import clickhouse_connect
import numpy as np

logger = logging.getLogger(__name__)


class ByteHouseEmbeddingStore:
    """CRUD for node_embeddings table in ByteHouse.

    All methods are synchronous — callers should use run_in_executor
    for async contexts.
    """

    TABLE = "node_embeddings"

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str = "paper_data",
        secure: bool = True,
    ) -> None:
        self._client = clickhouse_connect.get_client(
            host=host,
            user=user,
            password=password,
            database=database,
            secure=secure,
        )
        self._database = database

    def ensure_table(self) -> None:
        """Create node_embeddings table if not exists."""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self._database}.{self.TABLE} (
            gcn_id        String,
            content       String,
            node_type     String,
            embedding     Array(Float32),
            source_id     String,
            created_at    DateTime DEFAULT now()
        ) ENGINE = HaUniqueMergeTree()
        ORDER BY gcn_id
        UNIQUE KEY gcn_id
        SETTINGS index_granularity = 128
        """
        self._client.command(ddl)
        logger.info("Ensured table %s.%s", self._database, self.TABLE)

    def get_existing_gcn_ids(self) -> set[str]:
        """Return set of gcn_ids that already have embeddings."""
        result = self._client.query(
            f"SELECT gcn_id FROM {self._database}.{self.TABLE}"
        )
        return {row[0] for row in result.result_rows}

    def upsert_embeddings(self, records: list[dict]) -> None:
        """Batch insert embedding records.

        Each record: {gcn_id, content, node_type, embedding: list[float], source_id}
        HaUniqueMergeTree handles dedup on gcn_id.
        """
        if not records:
            return
        columns = ["gcn_id", "content", "node_type", "embedding", "source_id"]
        data = [
            [r["gcn_id"], r["content"], r["node_type"], r["embedding"], r["source_id"]]
            for r in records
        ]
        self._client.insert(
            f"{self._database}.{self.TABLE}",
            data,
            column_names=columns,
        )
        logger.info("Upserted %d embedding records", len(records))

    def load_embeddings_by_type(
        self, node_type: str
    ) -> tuple[list[str], np.ndarray]:
        """Load all embeddings for a given node_type.

        Returns:
            (gcn_ids, embedding_matrix) where matrix is (N, dim) float32.
            If empty, returns ([], np.array([])).
        """
        result = self._client.query(
            f"SELECT gcn_id, embedding FROM {self._database}.{self.TABLE} "
            f"WHERE node_type = %(node_type)s",
            parameters={"node_type": node_type},
        )
        if not result.result_rows:
            return [], np.array([])

        gcn_ids = [row[0] for row in result.result_rows]
        vectors = [np.asarray(row[1], dtype=np.float32) for row in result.result_rows]
        matrix = np.vstack(vectors)
        return gcn_ids, matrix

    def close(self) -> None:
        """Close the ClickHouse connection."""
        self._client.close()
```

- [ ] **Step 4: Update `gaia/lkm/storage/__init__.py`** — add `ByteHouseEmbeddingStore` to imports and `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/storage/test_bytehouse_store.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add gaia/lkm/storage/bytehouse_store.py gaia/lkm/storage/__init__.py tests/gaia/lkm/storage/test_bytehouse_store.py
git commit -m "feat(m6): add ByteHouseEmbeddingStore for node embeddings"
```

---

## Chunk 3: Embedding Computer

### Task 4: LanceDB — list all public global variable IDs

**Files:**
- Modify: `gaia/lkm/storage/lance_store.py`
- Modify: `gaia/lkm/storage/manager.py`
- Test: `tests/gaia/lkm/storage/test_lance_store.py` (append)

The existing `list_global_variables` has `limit=100` default which is too small for scanning all variables. We need a dedicated method that scans all public variables without content (just IDs + type + representative_lcn for content lookup).

- [ ] **Step 1: Write failing test**

```python
# In tests/gaia/lkm/storage/test_lance_store.py or a new test file
# tests/gaia/lkm/core/test_discovery.py (we'll add integration later)

# For now, add to existing lance store tests:
async def test_list_all_public_global_ids(lance_store):
    """list_all_public_global_ids returns all public gcn_ids with type and representative_lcn."""
    # Setup: write some global variables
    from gaia.lkm.models import GlobalVariableNode, LocalCanonicalRef

    gvs = [
        GlobalVariableNode(
            id=f"gcn_{i:04d}",
            type="claim" if i % 2 == 0 else "question",
            visibility="public" if i < 8 else "private",
            content_hash=f"hash_{i}",
            representative_lcn=LocalCanonicalRef(
                local_id=f"pkg::label_{i}", package_id="pkg", version="1.0"
            ),
            local_members=[
                LocalCanonicalRef(
                    local_id=f"pkg::label_{i}", package_id="pkg", version="1.0"
                )
            ],
        )
        for i in range(10)
    ]
    await lance_store.write_global_variables(gvs)
    result = await lance_store.list_all_public_global_ids()
    # Should have 8 public variables (indices 0-7)
    assert len(result) == 8
    # Each item is a dict with id, type, representative_lcn
    assert all("id" in r and "type" in r and "representative_lcn" in r for r in result)
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `list_all_public_global_ids` on LanceContentStore**

Add to `gaia/lkm/storage/lance_store.py`:

```python
    async def list_all_public_global_ids(self) -> list[dict]:
        """List all public global variable IDs with type and representative_lcn.

        Returns list of dicts: {id, type, representative_lcn (JSON string)}.
        No limit — scans the full table.
        """
        table = self._db.open_table("global_variable_nodes")
        results = await self._run(
            lambda: (
                table.search()
                .where("visibility = 'public'")
                .select(["id", "type", "representative_lcn"])
                .limit(_MAX_SCAN)
                .to_list()
            )
        )
        return [{"id": r["id"], "type": r["type"], "representative_lcn": r["representative_lcn"]} for r in results]
```

Add passthrough to `gaia/lkm/storage/manager.py`:

```python
    async def list_all_public_global_ids(self) -> list[dict]:
        """List all public global variable IDs with type and representative_lcn."""
        return await self.content.list_all_public_global_ids()
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add gaia/lkm/storage/lance_store.py gaia/lkm/storage/manager.py tests/
git commit -m "feat(m6): add list_all_public_global_ids to LanceContentStore"
```

---

### Task 5: Embedding Computer

**Files:**
- Create: `gaia/lkm/core/_embedding.py`
- Test: `tests/gaia/lkm/core/test_embedding.py`

**Design:** Async embedding computer that:
1. Gets pending gcn_ids (public globals minus already-embedded in ByteHouse)
2. Resolves content via `representative_lcn` → `local_variable_nodes.content`
3. Calls embedding API with httpx + semaphore concurrency control
4. Batches results to ByteHouse

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/core/test_embedding.py
"""Tests for M6 embedding computer."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from gaia.lkm.core._embedding import Embedder, compute_embeddings
from gaia.lkm.models.discovery import DiscoveryConfig


class TestEmbedder:
    """Test the low-level Embedder API caller."""

    @pytest.mark.asyncio
    async def test_embed_returns_vector(self):
        """Embedder.embed() calls the API and returns a float list."""
        config = DiscoveryConfig()
        embedder = Embedder(config, access_key="test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"vector": [0.1] * 512}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            vec = await embedder.embed("test text")
            assert len(vec) == 512
            assert vec[0] == pytest.approx(0.1)

        await embedder.close()

    @pytest.mark.asyncio
    async def test_embed_sends_correct_payload(self):
        """Verify the API request payload and headers."""
        config = DiscoveryConfig()
        embedder = Embedder(config, access_key="my_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"vector": [0.0] * 512}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await embedder.embed("hello world")

            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["json"]["text"] == "hello world"
            assert call_kwargs[1]["json"]["provider"] == "dashscope"
            assert "accessKey" in call_kwargs[1]["headers"]

        await embedder.close()


class TestComputeEmbeddings:
    """Test the orchestrator that finds pending nodes and computes embeddings."""

    @pytest.mark.asyncio
    async def test_skips_already_embedded(self):
        """Nodes already in ByteHouse are not re-embedded."""
        mock_storage = AsyncMock()
        mock_storage.list_all_public_global_ids.return_value = [
            {"id": "gcn_aaa", "type": "claim", "representative_lcn": '{"local_id":"pkg::a","package_id":"pkg","version":"1.0"}'},
            {"id": "gcn_bbb", "type": "claim", "representative_lcn": '{"local_id":"pkg::b","package_id":"pkg","version":"1.0"}'},
        ]

        mock_bh = MagicMock()
        mock_bh.get_existing_gcn_ids.return_value = {"gcn_aaa"}  # already done

        mock_storage.get_local_variable = AsyncMock(return_value=MagicMock(content="some text"))

        config = DiscoveryConfig()
        embedder_mock = AsyncMock()
        embedder_mock.embed = AsyncMock(return_value=[0.5] * 512)
        embedder_mock.close = AsyncMock()

        with patch("gaia.lkm.core._embedding.Embedder", return_value=embedder_mock):
            stats = await compute_embeddings(mock_storage, mock_bh, config, access_key="k")

        # Only gcn_bbb should be computed (gcn_aaa skipped)
        assert stats["computed"] == 1
        assert stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_private_variables_excluded(self):
        """Private variables are not returned by list_all_public_global_ids."""
        mock_storage = AsyncMock()
        # list_all_public_global_ids only returns public — tested in lance_store
        mock_storage.list_all_public_global_ids.return_value = []
        mock_bh = MagicMock()
        mock_bh.get_existing_gcn_ids.return_value = set()

        config = DiscoveryConfig()
        stats = await compute_embeddings(mock_storage, mock_bh, config, access_key="k")
        assert stats["computed"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lkm/core/test_embedding.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `_embedding.py`**

```python
# gaia/lkm/core/_embedding.py
"""Embedding computation for M6 semantic discovery.

Calls external embedding API, writes results to ByteHouse.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from gaia.lkm.models.discovery import DiscoveryConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Async embedding API caller with concurrency control."""

    def __init__(self, config: DiscoveryConfig, access_key: str) -> None:
        self._config = config
        self._sem = asyncio.Semaphore(config.embedding_concurrency)
        self._client = httpx.AsyncClient(timeout=config.embedding_http_timeout)
        self._headers = {
            "accessKey": access_key,
            "Content-Type": "application/json",
        }

    async def embed(self, text: str) -> list[float]:
        """Compute embedding for a single text. Retries on failure."""
        payload = {"text": text, "provider": self._config.embedding_provider}
        for attempt in range(self._config.embedding_max_retries):
            async with self._sem:
                try:
                    r = await self._client.post(
                        self._config.embedding_api_url,
                        headers=self._headers,
                        json=payload,
                    )
                    r.raise_for_status()
                    return r.json()["data"]["vector"]
                except Exception:
                    if attempt == self._config.embedding_max_retries - 1:
                        raise
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError("unreachable")

    async def close(self) -> None:
        await self._client.aclose()


async def compute_embeddings(
    storage,  # StorageManager
    bytehouse,  # ByteHouseEmbeddingStore
    config: DiscoveryConfig,
    access_key: str,
) -> dict:
    """Compute embeddings for all pending public global variables.

    Returns stats dict: {total, computed, skipped, failed}.
    """
    # 1. Get all public global variable metadata
    all_globals = await storage.list_all_public_global_ids()
    if not all_globals:
        return {"total": 0, "computed": 0, "skipped": 0, "failed": 0}

    # 2. Find pending (not yet in ByteHouse)
    loop = asyncio.get_running_loop()
    existing = await loop.run_in_executor(None, bytehouse.get_existing_gcn_ids)
    pending = [g for g in all_globals if g["id"] not in existing]

    stats = {
        "total": len(all_globals),
        "computed": 0,
        "skipped": len(all_globals) - len(pending),
        "failed": 0,
    }

    if not pending:
        logger.info("No pending embeddings to compute")
        return stats

    logger.info("Computing embeddings for %d/%d variables", len(pending), len(all_globals))

    # 3. Resolve content and compute embeddings
    embedder = Embedder(config, access_key)
    batch: list[dict] = []
    batch_size = 200

    async def process_one(meta: dict) -> dict | None:
        gcn_id = meta["id"]
        lcn = json.loads(meta["representative_lcn"])
        local_var = await storage.get_local_variable(lcn["local_id"])
        if not local_var or not local_var.content:
            return None
        try:
            vec = await embedder.embed(local_var.content)
            return {
                "gcn_id": gcn_id,
                "content": local_var.content,
                "node_type": meta["type"],
                "embedding": vec,
                "source_id": f"{config.embedding_provider}",
            }
        except Exception:
            logger.warning("Failed to embed %s", gcn_id, exc_info=True)
            return None

    # Process with bounded concurrency
    sem = asyncio.Semaphore(config.embedding_concurrency)

    async def bounded(meta: dict) -> dict | None:
        async with sem:
            return await process_one(meta)

    results = await asyncio.gather(*(bounded(m) for m in pending))

    records = [r for r in results if r is not None]
    stats["computed"] = len(records)
    stats["failed"] = len(pending) - len(records)

    # 4. Batch write to ByteHouse
    for i in range(0, len(records), batch_size):
        chunk = records[i : i + batch_size]
        await loop.run_in_executor(None, bytehouse.upsert_embeddings, chunk)

    await embedder.close()
    logger.info(
        "Embedding complete: %d computed, %d skipped, %d failed",
        stats["computed"],
        stats["skipped"],
        stats["failed"],
    )
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/core/test_embedding.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add gaia/lkm/core/_embedding.py tests/gaia/lkm/core/test_embedding.py
git commit -m "feat(m6): add embedding computer with async API + ByteHouse write"
```

---

## Chunk 4: FAISS Clustering

### Task 6: Add `faiss-cpu` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `faiss-cpu` to dependencies**

Add `"faiss-cpu>=1.7"` to the `dependencies` list in `pyproject.toml`.

- [ ] **Step 2: Run `uv sync`**

Run: `uv sync`
Expected: faiss-cpu installed

- [ ] **Step 3: Verify import**

Run: `python -c "import faiss; print(faiss.__version__)"`
Expected: prints version

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add faiss-cpu dependency for M6 clustering"
```

---

### Task 7: FAISS Clustering + Union-Find

**Files:**
- Create: `gaia/lkm/core/_clustering.py`
- Test: `tests/gaia/lkm/core/test_clustering.py`

**Design:** Reference `propositional_logic_analysis/clustering/src/faiss_clusterer.py`
- Normalize embeddings → FAISS IndexFlatIP (inner product = cosine)
- k-NN search → Union-Find merge pairs above threshold
- Filter constraints: same-type only, exclude_same_factor, max_cluster_size

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/core/test_clustering.py
"""Tests for FAISS clustering + Union-Find."""

import numpy as np
import pytest

from gaia.lkm.core._clustering import cluster_embeddings
from gaia.lkm.models.discovery import DiscoveryConfig, SemanticCluster


def _make_similar_pair(dim: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Create two very similar vectors."""
    base = np.random.randn(dim).astype(np.float32)
    noise = np.random.randn(dim).astype(np.float32) * 0.05
    return base, base + noise


def _make_dissimilar(dim: int = 512) -> np.ndarray:
    """Create a random vector unlikely to match the similar pair."""
    return np.random.randn(dim).astype(np.float32)


class TestClusterEmbeddings:
    def test_similar_pairs_clustered(self):
        """Two similar vectors should end up in the same cluster."""
        np.random.seed(42)
        v1, v2 = _make_similar_pair()
        gcn_ids = ["gcn_001", "gcn_002"]
        matrix = np.vstack([v1, v2])

        config = DiscoveryConfig(similarity_threshold=0.85, faiss_k=10)
        clusters = cluster_embeddings(gcn_ids, matrix, config)

        assert len(clusters) == 1
        assert set(clusters[0].gcn_ids) == {"gcn_001", "gcn_002"}

    def test_dissimilar_not_clustered(self):
        """Dissimilar vectors should not be clustered together."""
        np.random.seed(42)
        v1 = np.random.randn(512).astype(np.float32)
        v2 = -v1  # opposite direction — cosine ≈ -1
        gcn_ids = ["gcn_001", "gcn_002"]
        matrix = np.vstack([v1, v2])

        config = DiscoveryConfig(similarity_threshold=0.85)
        clusters = cluster_embeddings(gcn_ids, matrix, config)
        assert len(clusters) == 0  # no clusters with size ≥ 2

    def test_max_cluster_size_enforced(self):
        """Clusters exceeding max_cluster_size are split."""
        np.random.seed(42)
        # Create 30 nearly identical vectors
        base = np.random.randn(512).astype(np.float32)
        matrix = np.vstack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(30)])
        gcn_ids = [f"gcn_{i:03d}" for i in range(30)]

        config = DiscoveryConfig(similarity_threshold=0.85, max_cluster_size=10)
        clusters = cluster_embeddings(gcn_ids, matrix, config)

        for c in clusters:
            assert len(c.gcn_ids) <= 10

    def test_exclude_same_factor(self):
        """Nodes sharing a factor should not be clustered together."""
        np.random.seed(42)
        v1, v2 = _make_similar_pair()
        gcn_ids = ["gcn_001", "gcn_002"]
        matrix = np.vstack([v1, v2])
        # gcn_001 and gcn_002 share factor gfac_x
        factor_index = {"gcn_001": {"gfac_x"}, "gcn_002": {"gfac_x"}}

        config = DiscoveryConfig(similarity_threshold=0.85, exclude_same_factor=True)
        clusters = cluster_embeddings(gcn_ids, matrix, config, factor_index=factor_index)
        assert len(clusters) == 0  # excluded because same factor

    def test_cluster_stats(self):
        """Clusters have correct centroid and similarity stats."""
        np.random.seed(42)
        v1, v2 = _make_similar_pair()
        gcn_ids = ["gcn_001", "gcn_002"]
        matrix = np.vstack([v1, v2])

        config = DiscoveryConfig(similarity_threshold=0.80)
        clusters = cluster_embeddings(gcn_ids, matrix, config)

        assert len(clusters) == 1
        c = clusters[0]
        assert c.centroid_gcn_id in gcn_ids
        assert 0.0 < c.min_similarity <= c.avg_similarity <= 1.0

    def test_single_node_no_cluster(self):
        """A single node cannot form a cluster."""
        v = np.random.randn(512).astype(np.float32)
        clusters = cluster_embeddings(["gcn_001"], v.reshape(1, -1), DiscoveryConfig())
        assert len(clusters) == 0

    def test_empty_input(self):
        """Empty input returns empty clusters."""
        clusters = cluster_embeddings([], np.array([]), DiscoveryConfig())
        assert clusters == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lkm/core/test_clustering.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `_clustering.py`**

```python
# gaia/lkm/core/_clustering.py
"""FAISS-based semantic clustering with Union-Find.

Reference: propositional_logic_analysis/clustering/src/faiss_clusterer.py
"""

from __future__ import annotations

import logging
import uuid

import faiss
import numpy as np

from gaia.lkm.models.discovery import DiscoveryConfig, SemanticCluster

logger = logging.getLogger(__name__)


class _UnionFind:
    """Simple Union-Find with path compression and union by rank."""

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def cluster_embeddings(
    gcn_ids: list[str],
    matrix: np.ndarray,
    config: DiscoveryConfig,
    factor_index: dict[str, set[str]] | None = None,
) -> list[SemanticCluster]:
    """Cluster embedding vectors using FAISS k-NN + Union-Find.

    Args:
        gcn_ids: Global variable IDs corresponding to rows of matrix.
        matrix: (N, dim) float32 embedding matrix.
        config: Clustering configuration.
        factor_index: Optional {gcn_id: set of factor_ids} for same-factor exclusion.

    Returns:
        List of SemanticCluster (only clusters with size >= 2).
    """
    n = len(gcn_ids)
    if n < 2:
        return []
    if matrix.ndim == 1:
        return []

    # Normalize for cosine similarity via inner product
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = (matrix / norms).astype(np.float32)

    # Build FAISS index
    dim = normalized.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(normalized)

    # k-NN search
    k = min(config.faiss_k, n)
    distances, indices = index.search(normalized, k)

    # Union-Find merge
    uf = _UnionFind(n)
    id_to_idx = {gid: i for i, gid in enumerate(gcn_ids)}

    for i in range(n):
        for j_pos in range(k):
            j = int(indices[i][j_pos])
            if j < 0 or j == i:
                continue
            sim = float(distances[i][j_pos])
            if sim < config.similarity_threshold:
                continue

            # Exclude same-factor pairs
            if config.exclude_same_factor and factor_index:
                factors_i = factor_index.get(gcn_ids[i], set())
                factors_j = factor_index.get(gcn_ids[j], set())
                if factors_i & factors_j:
                    continue

            uf.union(i, j)

    # Extract connected components
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups.setdefault(root, []).append(i)

    # Build clusters (size >= 2 only), enforce max_cluster_size
    clusters: list[SemanticCluster] = []
    for members in groups.values():
        if len(members) < 2:
            continue

        # Split if exceeding max_cluster_size
        sub_groups = [
            members[i : i + config.max_cluster_size]
            for i in range(0, len(members), config.max_cluster_size)
        ]

        for sub in sub_groups:
            if len(sub) < 2:
                continue

            member_ids = [gcn_ids[i] for i in sub]
            member_vecs = normalized[sub]

            # Compute centroid and find closest member
            centroid = member_vecs.mean(axis=0)
            centroid /= np.linalg.norm(centroid) + 1e-9
            sims_to_centroid = member_vecs @ centroid
            centroid_idx = int(np.argmax(sims_to_centroid))

            # Pairwise similarity stats
            pairwise = member_vecs @ member_vecs.T
            # Extract upper triangle (excluding diagonal)
            triu_idx = np.triu_indices(len(sub), k=1)
            pairwise_values = pairwise[triu_idx]

            clusters.append(
                SemanticCluster(
                    cluster_id=f"cl_{uuid.uuid4().hex[:12]}",
                    node_type="",  # filled by caller who groups by type
                    gcn_ids=member_ids,
                    centroid_gcn_id=member_ids[centroid_idx],
                    avg_similarity=float(np.mean(pairwise_values)) if len(pairwise_values) > 0 else 0.0,
                    min_similarity=float(np.min(pairwise_values)) if len(pairwise_values) > 0 else 0.0,
                )
            )

    logger.info("Clustering: %d nodes → %d clusters", n, len(clusters))
    return clusters
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/core/test_clustering.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add gaia/lkm/core/_clustering.py tests/gaia/lkm/core/test_clustering.py
git commit -m "feat(m6): add FAISS clustering with Union-Find"
```

---

## Chunk 5: Discovery Orchestrator + Integration

### Task 8: Discovery Orchestrator

**Files:**
- Create: `gaia/lkm/core/discovery.py`
- Test: `tests/gaia/lkm/core/test_discovery.py`

**Design:** Entry point that wires together:
1. `compute_embeddings()` → generate pending embeddings
2. For each `node_type`, load from ByteHouse → `cluster_embeddings()`
3. Build factor_index from Neo4j (if available) for same-factor exclusion
4. Assemble `ClusteringResult`

**Note:** `_build_factor_index` calls `storage.graph.get_variable_factor_index()` which doesn't exist yet on Neo4jGraphStore. The implementation handles this gracefully — returns empty dict if graph unavailable or method missing, disabling same-factor exclusion. The Neo4j method can be added in a follow-up task.

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lkm/core/test_discovery.py
"""Tests for M6 discovery orchestrator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from gaia.lkm.core.discovery import run_semantic_discovery
from gaia.lkm.models.discovery import DiscoveryConfig


@pytest.mark.asyncio
async def test_run_semantic_discovery_empty():
    """Empty graph produces empty result."""
    mock_storage = AsyncMock()
    mock_storage.list_all_public_global_ids.return_value = []
    mock_storage.graph = None

    mock_bh = MagicMock()
    mock_bh.get_existing_gcn_ids.return_value = set()
    mock_bh.load_embeddings_by_type.return_value = ([], np.array([]))

    config = DiscoveryConfig()

    with patch("gaia.lkm.core.discovery.compute_embeddings", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = {"total": 0, "computed": 0, "skipped": 0, "failed": 0}
        result = await run_semantic_discovery(mock_storage, mock_bh, config, access_key="k")

    assert result.clusters == []
    assert result.stats.total_variables_scanned == 0


@pytest.mark.asyncio
async def test_run_semantic_discovery_clusters_by_type():
    """Variables are clustered per node_type independently."""
    mock_storage = AsyncMock()
    mock_storage.list_all_public_global_ids.return_value = [
        {"id": f"gcn_{i}", "type": "claim", "representative_lcn": "{}"}
        for i in range(5)
    ]
    mock_storage.graph = None

    mock_bh = MagicMock()
    mock_bh.get_existing_gcn_ids.return_value = set()

    # Return embeddings only for "claim"
    base = np.random.randn(512).astype(np.float32)
    claim_matrix = np.vstack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(5)])
    mock_bh.load_embeddings_by_type.side_effect = lambda t: (
        ([f"gcn_{i}" for i in range(5)], claim_matrix) if t == "claim"
        else ([], np.array([]))
    )

    config = DiscoveryConfig(similarity_threshold=0.80)

    with patch("gaia.lkm.core.discovery.compute_embeddings", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = {"total": 5, "computed": 5, "skipped": 0, "failed": 0}
        result = await run_semantic_discovery(mock_storage, mock_bh, config, access_key="k")

    # Should have at least one cluster, all with node_type="claim"
    assert len(result.clusters) >= 1
    for c in result.clusters:
        assert c.node_type == "claim"


@pytest.mark.asyncio
async def test_idempotent_result():
    """Running discovery twice with same data gives same cluster count."""
    mock_storage = AsyncMock()
    mock_storage.list_all_public_global_ids.return_value = [
        {"id": f"gcn_{i}", "type": "claim", "representative_lcn": "{}"}
        for i in range(3)
    ]
    mock_storage.graph = None

    np.random.seed(123)
    base = np.random.randn(512).astype(np.float32)
    matrix = np.vstack([base + np.random.randn(512).astype(np.float32) * 0.01 for _ in range(3)])

    mock_bh = MagicMock()
    mock_bh.get_existing_gcn_ids.return_value = set()
    mock_bh.load_embeddings_by_type.side_effect = lambda t: (
        ([f"gcn_{i}" for i in range(3)], matrix.copy()) if t == "claim"
        else ([], np.array([]))
    )

    config = DiscoveryConfig(similarity_threshold=0.80)

    with patch("gaia.lkm.core.discovery.compute_embeddings", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = {"total": 3, "computed": 0, "skipped": 3, "failed": 0}
        r1 = await run_semantic_discovery(mock_storage, mock_bh, config, access_key="k")
        r2 = await run_semantic_discovery(mock_storage, mock_bh, config, access_key="k")

    assert r1.stats.total_clusters == r2.stats.total_clusters
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lkm/core/test_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `discovery.py`**

```python
# gaia/lkm/core/discovery.py
"""M6 Semantic Discovery — entry point.

Orchestrates embedding computation and FAISS clustering to find
semantically similar global variable nodes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timezone

from gaia.lkm.core._clustering import cluster_embeddings
from gaia.lkm.core._embedding import compute_embeddings
from gaia.lkm.models.discovery import (
    ClusteringResult,
    ClusteringStats,
    DiscoveryConfig,
)

logger = logging.getLogger(__name__)

# Node types that participate in clustering
_NODE_TYPES = ("claim", "question", "setting", "action")


async def _build_factor_index(storage) -> dict[str, set[str]]:
    """Build {gcn_id: set(gfac_ids)} from Neo4j if available.

    Returns empty dict if graph store is not configured.
    """
    if storage.graph is None:
        return {}
    try:
        return await storage.graph.get_variable_factor_index()
    except Exception:
        logger.warning("Failed to build factor index from graph store", exc_info=True)
        return {}


async def run_semantic_discovery(
    storage,  # StorageManager
    bytehouse,  # ByteHouseEmbeddingStore
    config: DiscoveryConfig,
    access_key: str,
) -> ClusteringResult:
    """Run the full semantic discovery pipeline.

    1. Compute embeddings for pending variables
    2. For each node_type, load embeddings and cluster
    3. Return ClusteringResult
    """
    t0 = time.monotonic()
    loop = asyncio.get_running_loop()

    # Step 1: Compute pending embeddings
    emb_stats = await compute_embeddings(storage, bytehouse, config, access_key)

    # Step 2: Build factor index for same-factor exclusion
    factor_index = await _build_factor_index(storage)

    # Step 3: Cluster per node_type
    all_clusters = []
    total_scanned = 0

    for node_type in _NODE_TYPES:
        gcn_ids, matrix = await loop.run_in_executor(
            None, bytehouse.load_embeddings_by_type, node_type
        )
        total_scanned += len(gcn_ids)

        if len(gcn_ids) < 2:
            continue

        clusters = cluster_embeddings(gcn_ids, matrix, config, factor_index)
        for c in clusters:
            c.node_type = node_type
        all_clusters.extend(clusters)

    # Step 4: Build stats
    size_dist = Counter(len(c.gcn_ids) for c in all_clusters)
    elapsed = time.monotonic() - t0

    stats = ClusteringStats(
        total_variables_scanned=total_scanned,
        total_embeddings_computed=emb_stats.get("computed", 0),
        total_clusters=len(all_clusters),
        cluster_size_distribution=dict(size_dist),
        elapsed_seconds=round(elapsed, 2),
    )

    result = ClusteringResult(
        clusters=all_clusters,
        stats=stats,
        timestamp=datetime.now(tz=timezone.utc),
    )

    logger.info(
        "Semantic discovery complete: %d clusters from %d variables in %.1fs",
        stats.total_clusters,
        stats.total_variables_scanned,
        stats.elapsed_seconds,
    )
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/core/test_discovery.py -v`
Expected: 3 passed

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/gaia/lkm/ -v`
Expected: All existing tests + new tests pass

- [ ] **Step 6: Lint and format**

Run: `ruff check gaia/lkm/core/ gaia/lkm/models/discovery.py gaia/lkm/storage/bytehouse_store.py gaia/lkm/storage/config.py tests/gaia/lkm/ && ruff format --check .`
Fix any issues.

- [ ] **Step 7: Commit**

```bash
git add gaia/lkm/core/discovery.py tests/gaia/lkm/core/test_discovery.py
git commit -m "feat(m6): add semantic discovery orchestrator"
```

---

## Chunk 6: Wiring + Final Integration

### Task 9: Wire ByteHouse into StorageManager

**Files:**
- Modify: `gaia/lkm/storage/manager.py`

The `ByteHouseEmbeddingStore` is not managed by `StorageManager` lifecycle directly — it's passed to `run_semantic_discovery` as a separate argument. However, `StorageManager` should provide a factory method to create one from config.

- [ ] **Step 1: Add `create_bytehouse_store` to StorageManager**

```python
# In gaia/lkm/storage/manager.py, add method:
    def create_bytehouse_store(self):
        """Create a ByteHouseEmbeddingStore from config. Returns None if not configured."""
        from gaia.lkm.storage.bytehouse_store import ByteHouseEmbeddingStore

        if not self._config.bytehouse_host:
            return None
        return ByteHouseEmbeddingStore(
            host=self._config.bytehouse_host,
            user=self._config.bytehouse_user,
            password=self._config.bytehouse_password,
            database=self._config.bytehouse_database,
        )
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/storage/manager.py
git commit -m "feat(m6): add create_bytehouse_store to StorageManager"
```

---

### Task 10: Discovery CLI script (optional manual trigger)

**Files:**
- Create: `gaia/lkm/scripts/discovery.py`

- [ ] **Step 1: Implement CLI script**

```python
# gaia/lkm/scripts/discovery.py
"""CLI script to run M6 semantic discovery.

Usage: python -m gaia.lkm.scripts.discovery [--threshold 0.85] [--dry-run]
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from gaia.lkm.models.discovery import DiscoveryConfig
from gaia.lkm.storage import StorageConfig, StorageManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(threshold: float = 0.85, dry_run: bool = False) -> None:
    config = StorageConfig()
    storage = StorageManager(config)
    await storage.initialize()

    bytehouse = storage.create_bytehouse_store()
    if bytehouse is None:
        logger.error("ByteHouse not configured — set BYTEHOUSE_HOST env var")
        sys.exit(1)
    bytehouse.ensure_table()

    discovery_config = DiscoveryConfig(similarity_threshold=threshold)

    if dry_run:
        ids = await storage.list_all_public_global_ids()
        existing = await asyncio.get_running_loop().run_in_executor(
            None, bytehouse.get_existing_gcn_ids
        )
        logger.info("Public globals: %d, already embedded: %d, pending: %d",
                     len(ids), len(existing), len(ids) - len(existing))
        return

    from gaia.lkm.core.discovery import run_semantic_discovery

    result = await run_semantic_discovery(
        storage, bytehouse, discovery_config, access_key=config.embedding_access_key,
    )

    # Print summary
    print(json.dumps({
        "total_clusters": result.stats.total_clusters,
        "total_scanned": result.stats.total_variables_scanned,
        "embeddings_computed": result.stats.total_embeddings_computed,
        "elapsed_seconds": result.stats.elapsed_seconds,
        "cluster_sizes": result.stats.cluster_size_distribution,
    }, indent=2))

    # Print first 5 clusters as sample
    for c in result.clusters[:5]:
        print(f"\nCluster {c.cluster_id} ({c.node_type}): {len(c.gcn_ids)} nodes, "
              f"avg_sim={c.avg_similarity:.3f}")
        for gid in c.gcn_ids[:3]:
            print(f"  - {gid}")

    await storage.close()
    bytehouse.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run M6 semantic discovery")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(threshold=args.threshold, dry_run=args.dry_run))
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/scripts/discovery.py
git commit -m "feat(m6): add discovery CLI script"
```

---

### Task 11: Final verification

- [ ] **Step 1: Run full LKM test suite**

Run: `pytest tests/gaia/lkm/ -v`
Expected: All pass

- [ ] **Step 2: Run full project test suite**

Run: `pytest`
Expected: All pass (existing tests unaffected)

- [ ] **Step 3: Lint**

Run: `ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 4: Final commit if any fixes needed**

- [ ] **Step 5: PR creation**

Use @finishing-a-development-branch skill.
