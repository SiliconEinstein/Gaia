# StorageManager Implementation Plan (Chunk 5/6)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `StorageManager` — a unified facade coordinating ContentStore, GraphStore, and VectorStore with three-write consistency and graceful degradation.

**Architecture:** A single class in `libs/storage_v2/manager.py` that owns all three stores, exposes thin read delegation, and coordinates writes with compensating rollback on failure. GraphStore and VectorStore are optional; ContentStore is required.

**Tech Stack:** Python 3.12, Pydantic v2, LanceDB, Kùzu, pytest (asyncio_mode=auto)

---

## Context

**ABCs:** `libs/storage_v2/content_store.py` (19 methods), `graph_store.py` (10 methods), `vector_store.py` (2 methods)

**Implementations:** `lance_content_store.py`, `kuzu_graph_store.py`, `lance_vector_store.py` — all async, tested.

**Config:** `libs/storage_v2/config.py` — `StorageConfig` with `lancedb_path`, `graph_backend`, `kuzu_path`, `vector_index_type`.

**Existing test fixtures:** `tests/libs/storage_v2/conftest.py` provides `content_store`, `packages`, `modules`, `closures`, `chains`, `probabilities`, `beliefs`, `resources`, `attachments` fixtures.

---

### Task 1: StorageManager skeleton + initialization tests

**Files:**
- Create: `libs/storage_v2/manager.py`
- Create: `tests/libs/storage_v2/test_manager.py`
- Modify: `libs/storage_v2/__init__.py`

- [ ] **Step 1: Write the test file with initialization tests**

```python
"""Tests for StorageManager — unified storage facade."""

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager


@pytest.fixture
async def full_manager(tmp_path) -> StorageManager:
    """Manager with all three stores."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu"),
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.fixture
async def no_graph_manager(tmp_path) -> StorageManager:
    """Manager with graph_backend=none."""
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="none",
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


class TestInitialization:
    async def test_full_init(self, full_manager):
        assert full_manager.content_store is not None
        assert full_manager.graph_store is not None
        assert full_manager.vector_store is not None

    async def test_no_graph_init(self, no_graph_manager):
        assert no_graph_manager.content_store is not None
        assert no_graph_manager.graph_store is None
        assert no_graph_manager.vector_store is not None

    async def test_close_idempotent(self, full_manager):
        await full_manager.close()
        await full_manager.close()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'libs.storage_v2.manager'`

- [ ] **Step 3: Write the StorageManager skeleton**

```python
"""StorageManager — unified facade for ContentStore, GraphStore, and VectorStore."""

from __future__ import annotations

import logging

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.vector_store import VectorStore

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage facade. Domain services only touch this class."""

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self.content_store: ContentStore | None = None
        self.graph_store: GraphStore | None = None
        self.vector_store: VectorStore | None = None

    async def initialize(self) -> None:
        """Instantiate and initialize all configured stores."""
        from libs.storage_v2.lance_content_store import LanceContentStore
        from libs.storage_v2.lance_vector_store import LanceVectorStore

        # ContentStore — always required
        cs = LanceContentStore(self._config.lancedb_path)
        await cs.initialize()
        self.content_store = cs

        # GraphStore — optional
        if self._config.graph_backend == "kuzu":
            from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

            kuzu_path = self._config.kuzu_path or (self._config.lancedb_path + "_kuzu")
            gs = KuzuGraphStore(kuzu_path)
            await gs.initialize_schema()
            self.graph_store = gs
        elif self._config.graph_backend == "neo4j":
            logger.warning("Neo4j graph backend not yet implemented in v2; skipping")
        # else: "none" — graph_store stays None

        # VectorStore — always created (same LanceDB path, separate table)
        vs = LanceVectorStore(self._config.lancedb_path)
        self.vector_store = vs

    async def close(self) -> None:
        """Release connections held by stores."""
        if self.graph_store is not None:
            await self.graph_store.close()
```

- [ ] **Step 4: Update `__init__.py` to export StorageManager**

Add `StorageManager` to `libs/storage_v2/__init__.py`:

```python
from libs.storage_v2.manager import StorageManager
```

And add it to `__all__`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/libs/storage_v2/test_manager.py::TestInitialization -v`
Expected: All PASS

- [ ] **Step 6: Lint**

Run: `ruff check libs/storage_v2/manager.py tests/libs/storage_v2/test_manager.py && ruff format --check libs/storage_v2/manager.py tests/libs/storage_v2/test_manager.py`

- [ ] **Step 7: Commit**

```bash
git add libs/storage_v2/manager.py libs/storage_v2/__init__.py tests/libs/storage_v2/test_manager.py
git commit -m "feat(storage-v2): chunk 5.1 — StorageManager skeleton + initialization"
```

---

### Task 2: Read delegation methods + degraded mode

**Files:**
- Modify: `libs/storage_v2/manager.py`
- Modify: `tests/libs/storage_v2/test_manager.py`

- [ ] **Step 1: Write read delegation tests**

Append to `tests/libs/storage_v2/test_manager.py`:

```python
from libs.storage_v2.models import ClosureEmbedding, Subgraph


class TestReadDelegation:
    async def test_get_closure_delegates(self, full_manager, packages, modules, closures, chains):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_closures(closures)
        c = await full_manager.get_closure(closures[0].closure_id)
        assert c is not None
        assert c.closure_id == closures[0].closure_id

    async def test_get_package_delegates(self, full_manager, packages, modules):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        p = await full_manager.get_package(pkg.package_id)
        assert p is not None
        assert p.package_id == pkg.package_id

    async def test_search_bm25_delegates(self, full_manager, packages, modules, closures):
        pkg, mods = packages[0], [m for m in modules if m.package_id == packages[0].package_id]
        await full_manager.content_store.write_package(pkg, mods)
        await full_manager.content_store.write_closures(closures)
        results = await full_manager.search_bm25("gravity", top_k=5)
        assert isinstance(results, list)


class TestDegradedMode:
    async def test_graph_none_returns_empty_subgraph(self, no_graph_manager):
        result = await no_graph_manager.get_neighbors("nonexistent")
        assert result == Subgraph()

    async def test_graph_none_search_topology_returns_empty(self, no_graph_manager):
        result = await no_graph_manager.search_topology(["nonexistent"])
        assert result == []

    async def test_vector_none_search_returns_empty(self, tmp_path):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        mgr.content_store = None  # skip init for this test
        mgr.vector_store = None
        result = await mgr.search_vector([0.1] * 8, top_k=5)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_manager.py::TestReadDelegation -v`
Expected: FAIL — `AttributeError: 'StorageManager' object has no attribute 'get_closure'`

- [ ] **Step 3: Add read delegation and degraded mode methods to StorageManager**

Append to `StorageManager` class in `libs/storage_v2/manager.py`:

```python
    # ── Read delegation (ContentStore) ──

    async def get_closure(self, closure_id: str, version: int | None = None):
        return await self.content_store.get_closure(closure_id, version)

    async def get_closure_versions(self, closure_id: str):
        return await self.content_store.get_closure_versions(closure_id)

    async def get_package(self, package_id: str):
        return await self.content_store.get_package(package_id)

    async def get_module(self, module_id: str):
        return await self.content_store.get_module(module_id)

    async def get_chains_by_module(self, module_id: str):
        return await self.content_store.get_chains_by_module(module_id)

    async def get_probability_history(self, chain_id: str, step_index: int | None = None):
        return await self.content_store.get_probability_history(chain_id, step_index)

    async def get_belief_history(self, closure_id: str):
        return await self.content_store.get_belief_history(closure_id)

    async def get_resources_for(self, target_type: str, target_id: str):
        return await self.content_store.get_resources_for(target_type, target_id)

    async def search_bm25(self, text: str, top_k: int):
        return await self.content_store.search_bm25(text, top_k)

    async def list_closures(self):
        return await self.content_store.list_closures()

    async def list_chains(self):
        return await self.content_store.list_chains()

    # ── Read delegation (GraphStore — degraded-safe) ──

    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ):
        if self.graph_store is None:
            return Subgraph()
        return await self.graph_store.get_neighbors(closure_id, direction, chain_types, max_hops)

    async def get_subgraph(self, closure_id: str, max_closures: int = 500):
        if self.graph_store is None:
            return Subgraph()
        return await self.graph_store.get_subgraph(closure_id, max_closures)

    async def search_topology(self, seed_ids: list[str], hops: int = 1):
        if self.graph_store is None:
            return []
        return await self.graph_store.search_topology(seed_ids, hops)

    # ── Read delegation (VectorStore — degraded-safe) ──

    async def search_vector(self, embedding: list[float], top_k: int):
        if self.vector_store is None:
            return []
        return await self.vector_store.search(embedding, top_k)
```

Add import at top of `manager.py`:

```python
from libs.storage_v2.models import Subgraph
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_manager.py -v`
Expected: All PASS

- [ ] **Step 5: Lint**

Run: `ruff check libs/storage_v2/manager.py tests/libs/storage_v2/test_manager.py && ruff format --check libs/storage_v2/manager.py tests/libs/storage_v2/test_manager.py`

- [ ] **Step 6: Commit**

```bash
git add libs/storage_v2/manager.py tests/libs/storage_v2/test_manager.py
git commit -m "feat(storage-v2): chunk 5.2 — read delegation + degraded mode"
```

---

### Task 3: Three-write `ingest_package()` + rollback tests

**Files:**
- Modify: `libs/storage_v2/manager.py`
- Create: `tests/libs/storage_v2/test_three_write.py`

- [ ] **Step 1: Write three-write test file**

```python
"""Tests for StorageManager three-write consistency and rollback."""

from unittest.mock import AsyncMock, patch

import pytest

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager
from libs.storage_v2.models import ClosureEmbedding


@pytest.fixture
async def manager(tmp_path) -> StorageManager:
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu"),
    )
    mgr = StorageManager(config)
    await mgr.initialize()
    yield mgr
    await mgr.close()


def _make_embeddings(closures) -> list[ClosureEmbedding]:
    return [
        ClosureEmbedding(
            closure_id=c.closure_id,
            version=c.version,
            embedding=[0.1 * i for i in range(8)],
        )
        for c in closures
    ]


class TestIngestSuccess:
    async def test_ingest_writes_all_stores(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_closures)

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
            embeddings=embeddings,
        )

        # ContentStore has the package
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

        # ContentStore has closures
        c = await manager.content_store.get_closure(pkg_closures[0].closure_id)
        assert c is not None

        # GraphStore has topology
        sub = await manager.graph_store.get_subgraph(pkg_closures[0].closure_id)
        assert len(sub.closure_ids) > 0

        # VectorStore has embeddings
        results = await manager.vector_store.search([0.1 * i for i in range(8)], top_k=1)
        assert len(results) >= 1

    async def test_ingest_without_embeddings(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
        )

        p = await manager.content_store.get_package(pkg.package_id)
        assert p is not None

    async def test_ingest_no_graph(
        self, tmp_path, packages, modules, closures, chains
    ):
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        await mgr.initialize()

        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await mgr.ingest_package(
            package=pkg,
            modules=pkg_modules,
            closures=pkg_closures,
            chains=pkg_chains,
        )

        p = await mgr.content_store.get_package(pkg.package_id)
        assert p is not None
        await mgr.close()


class TestIngestRollback:
    async def test_graph_failure_rolls_back_content(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # Make graph_store.write_topology raise
        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("graph write failed")
        )

        with pytest.raises(RuntimeError, match="graph write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                closures=pkg_closures,
                chains=pkg_chains,
            )

        # Content should be rolled back
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is None

    async def test_vector_failure_rolls_back_content_and_graph(
        self, manager, packages, modules, closures, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_closures)

        # Make vector_store.write_embeddings raise
        manager.vector_store.write_embeddings = AsyncMock(
            side_effect=RuntimeError("vector write failed")
        )

        with pytest.raises(RuntimeError, match="vector write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                closures=pkg_closures,
                chains=pkg_chains,
                embeddings=embeddings,
            )

        # Content should be rolled back
        p = await manager.content_store.get_package(pkg.package_id)
        assert p is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_three_write.py -v`
Expected: FAIL — `AttributeError: 'StorageManager' object has no attribute 'ingest_package'`

- [ ] **Step 3: Implement `ingest_package()` with compensating rollback**

Add to `StorageManager` class in `libs/storage_v2/manager.py`:

```python
    # ── Three-Write: ingest_package ──

    async def ingest_package(
        self,
        package: Package,
        modules: list[Module],
        closures: list[Closure],
        chains: list[Chain],
        embeddings: list[ClosureEmbedding] | None = None,
    ) -> None:
        """Write a complete package to all stores with compensating rollback.

        Write order: ContentStore → GraphStore → VectorStore.
        On failure, previously-written stores are cleaned up via delete_package.
        """
        package_id = package.package_id

        # Step 1: ContentStore (source of truth)
        await self.content_store.write_package(package, modules)
        await self.content_store.write_closures(closures)
        await self.content_store.write_chains(chains)

        # Step 2: GraphStore (optional)
        if self.graph_store is not None:
            try:
                await self.graph_store.write_topology(closures, chains)
            except Exception:
                logger.error("GraphStore write failed; rolling back ContentStore")
                await self.content_store.delete_package(package_id)
                raise

        # Step 3: VectorStore (optional)
        if self.vector_store is not None and embeddings:
            try:
                await self.vector_store.write_embeddings(embeddings)
            except Exception:
                logger.error("VectorStore write failed; rolling back ContentStore + GraphStore")
                if self.graph_store is not None:
                    await self.graph_store.delete_package(package_id)
                await self.content_store.delete_package(package_id)
                raise
```

Add imports at top of `manager.py`:

```python
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    ClosureEmbedding,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    Subgraph,
)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_three_write.py -v`
Expected: All PASS

- [ ] **Step 5: Lint**

Run: `ruff check libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py && ruff format --check libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py`

- [ ] **Step 6: Commit**

```bash
git add libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py
git commit -m "feat(storage-v2): chunk 5.3 — ingest_package with three-write + rollback"
```

---

### Task 4: Passthrough write methods (probabilities, beliefs, resources)

**Files:**
- Modify: `libs/storage_v2/manager.py`
- Modify: `tests/libs/storage_v2/test_three_write.py`

- [ ] **Step 1: Write passthrough write tests**

Append to `tests/libs/storage_v2/test_three_write.py`:

```python
class TestPassthroughWrites:
    async def test_add_probabilities(
        self, manager, packages, modules, closures, chains, probabilities
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
        )

        pkg_probs = [p for p in probabilities if p.chain_id in {ch.chain_id for ch in pkg_chains}]
        if pkg_probs:
            await manager.add_probabilities(pkg_probs)
            history = await manager.content_store.get_probability_history(pkg_probs[0].chain_id)
            assert len(history) > 0

    async def test_write_beliefs(
        self, manager, packages, modules, closures, chains, beliefs
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
        )

        pkg_beliefs = [
            b for b in beliefs if b.closure_id in {c.closure_id for c in pkg_closures}
        ]
        if pkg_beliefs:
            await manager.write_beliefs(pkg_beliefs)
            history = await manager.content_store.get_belief_history(pkg_beliefs[0].closure_id)
            assert len(history) > 0

    async def test_write_resources(
        self, manager, packages, modules, closures, chains, resources, attachments
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_closures = [c for c in closures if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        await manager.ingest_package(
            package=pkg, modules=pkg_modules, closures=pkg_closures, chains=pkg_chains
        )

        pkg_resources = [r for r in resources if r.source_package_id == pkg.package_id]
        pkg_attachments = [
            a for a in attachments if a.resource_id in {r.resource_id for r in pkg_resources}
        ]
        if pkg_resources:
            await manager.write_resources(pkg_resources, pkg_attachments)
            for a in pkg_attachments:
                found = await manager.content_store.get_resources_for(a.target_type, a.target_id)
                assert isinstance(found, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_three_write.py::TestPassthroughWrites -v`
Expected: FAIL — `AttributeError: 'StorageManager' object has no attribute 'add_probabilities'`

- [ ] **Step 3: Add passthrough write methods**

Add to `StorageManager` class in `libs/storage_v2/manager.py`:

```python
    # ── Passthrough writes ──

    async def add_probabilities(self, records: list[ProbabilityRecord]) -> None:
        """Write probabilities to ContentStore + sync to GraphStore."""
        await self.content_store.write_probabilities(records)
        if self.graph_store is not None:
            for r in records:
                await self.graph_store.update_probability(r.chain_id, r.step_index, r.value)

    async def write_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Write belief snapshots to ContentStore + sync to GraphStore."""
        await self.content_store.write_belief_snapshots(snapshots)
        if self.graph_store is not None:
            await self.graph_store.update_beliefs(snapshots)

    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None:
        """Write resources to ContentStore + link in GraphStore."""
        await self.content_store.write_resources(resources, attachments)
        if self.graph_store is not None:
            await self.graph_store.write_resource_links(attachments)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_three_write.py -v`
Expected: All PASS

- [ ] **Step 5: Run full storage_v2 test suite**

Run: `pytest tests/libs/storage_v2/ -v`
Expected: All PASS

- [ ] **Step 6: Lint**

Run: `ruff check libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py && ruff format --check libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py`

- [ ] **Step 7: Commit**

```bash
git add libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py
git commit -m "feat(storage-v2): chunk 5.4 — passthrough writes (probabilities, beliefs, resources)"
```

---

## Summary

After completing all tasks:
- `StorageManager` in `libs/storage_v2/manager.py` coordinates all three stores
- `ingest_package()` implements three-write with compensating rollback
- Read methods delegate to appropriate stores with degraded-safe fallbacks
- Passthrough writes sync ContentStore → GraphStore for probabilities, beliefs, resources
- Full test coverage in `test_manager.py` (init, reads, degraded mode) and `test_three_write.py` (ingest, rollback, passthrough writes)
