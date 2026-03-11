# Publish State Machine + Idempotent Upsert Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken compensating-rollback in `ingest_package()` with a publish state machine (`preparing → committed`) + idempotent upsert writes + read-side visibility gate, so partial failures leave data invisible rather than dirty.

**Architecture:** Package status controls visibility. `ingest_package()` writes the package as `preparing`, writes all three stores idempotently, then flips status to `committed`. Reads filter out non-committed packages. Failed publishes stay in `preparing` and are invisible; they can be retried or cleaned up later. No cross-store rollback needed.

**Tech Stack:** LanceDB `merge_insert` for upsert, Kùzu `MERGE` (already in use), existing Pydantic models.

---

## Chunk 1: Model + Idempotent Content Writes

### Task 1: Add `preparing` status to Package model

**Files:**
- Modify: `libs/storage_v2/models.py:91`
- Test: `tests/libs/storage_v2/test_models.py`

- [ ] **Step 1: Write the failing test**

In `tests/libs/storage_v2/test_models.py`, add:

```python
def test_package_preparing_status():
    pkg = Package(
        package_id="test",
        name="test",
        version="1.0.0",
        modules=[],
        exports=[],
        submitter="tester",
        submitted_at=datetime(2026, 1, 1),
        status="preparing",
    )
    assert pkg.status == "preparing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage_v2/test_models.py::test_package_preparing_status -v`
Expected: FAIL — `"preparing"` not in Literal values

- [ ] **Step 3: Add `preparing` to Package.status Literal**

In `libs/storage_v2/models.py:91`, change:

```python
status: Literal["submitted", "merged", "rejected"]
```
to:
```python
status: Literal["preparing", "submitted", "merged", "rejected"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage_v2/test_models.py::test_package_preparing_status -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage_v2/models.py tests/libs/storage_v2/test_models.py
git commit -m "feat(storage-v2): add 'preparing' status to Package model"
```

---

### Task 2: Add `commit_package` and `get_committed_package_ids` to ContentStore ABC

**Files:**
- Modify: `libs/storage_v2/content_store.py`

These two methods are the building blocks for the state machine.

- [ ] **Step 1: Add abstract methods to ContentStore**

In `libs/storage_v2/content_store.py`, add after the `delete_package` method:

```python
@abstractmethod
async def commit_package(self, package_id: str) -> None:
    """Flip a package's status from 'preparing' to 'committed' (= 'merged')."""

@abstractmethod
async def get_committed_package_ids(self) -> set[str]:
    """Return all package_ids with status='merged'. Used by reads for visibility."""
```

- [ ] **Step 2: Commit**

```bash
git add libs/storage_v2/content_store.py
git commit -m "feat(storage-v2): add commit_package and get_committed_package_ids to ContentStore ABC"
```

---

### Task 3: Replace search→add with merge_insert in LanceContentStore writes

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py:411-447`
- Test: `tests/libs/storage_v2/test_lance_content.py`

- [ ] **Step 1: Write a test for upsert idempotency**

In `tests/libs/storage_v2/test_lance_content.py`, add to `TestWriteKnowledge`:

```python
async def test_write_knowledge_upsert_updates_content(self, content_store, knowledge_items):
    """Writing the same (knowledge_id, version) twice should update, not duplicate."""
    await content_store.write_knowledge(knowledge_items)
    updated = knowledge_items[0].model_copy(update={"content": "updated via upsert"})
    await content_store.write_knowledge([updated])
    k = await content_store.get_knowledge(knowledge_items[0].knowledge_id, version=1)
    assert k is not None
    assert k.content == "updated via upsert"
    # No duplicates
    versions = await content_store.get_knowledge_versions(knowledge_items[0].knowledge_id)
    assert len(versions) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWriteKnowledge::test_write_knowledge_upsert_updates_content -v`
Expected: FAIL — current code skips duplicates instead of updating

- [ ] **Step 3: Rewrite `write_knowledge` using merge_insert**

In `libs/storage_v2/lance_content_store.py`, replace the `write_knowledge` method (lines 430-447):

```python
async def write_knowledge(self, knowledge_items: list[Knowledge]) -> None:
    if not knowledge_items:
        return
    table = self._db.open_table("knowledge")
    rows = [_knowledge_to_row(k) for k in knowledge_items]
    (
        table.merge_insert("knowledge_id", "version")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute(rows)
    )
    self._fts_dirty = True
```

- [ ] **Step 4: Rewrite `write_package` using merge_insert**

In `libs/storage_v2/lance_content_store.py`, replace the `write_package` method (lines 411-428):

```python
async def write_package(self, package: Package, modules: list[Module]) -> None:
    pkg_table = self._db.open_table("packages")
    (
        pkg_table.merge_insert("package_id")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute([_package_to_row(package)])
    )
    if modules:
        mod_table = self._db.open_table("modules")
        rows = [_module_to_row(m) for m in modules]
        (
            mod_table.merge_insert("module_id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )
```

- [ ] **Step 5: Run all content store tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py -v`
Expected: ALL PASS — existing idempotency tests still pass, new upsert test passes

- [ ] **Step 6: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat(storage-v2): replace search-add with merge_insert in LanceContentStore"
```

---

### Task 4: Implement `commit_package` and `get_committed_package_ids` in LanceContentStore

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Test: `tests/libs/storage_v2/test_lance_content.py`

- [ ] **Step 1: Write failing tests**

Add a new test class in `tests/libs/storage_v2/test_lance_content.py`:

```python
class TestCommitPackage:
    async def test_commit_flips_status(self, content_store, packages, modules):
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, modules)
        p = await content_store.get_package(pkg.package_id)
        assert p.status == "preparing"

        await content_store.commit_package(pkg.package_id)
        p = await content_store.get_package(pkg.package_id)
        assert p.status == "merged"

    async def test_get_committed_package_ids(self, content_store, packages, modules):
        # Write one committed, one preparing
        pkg1 = packages[0]  # status="merged"
        await content_store.write_package(pkg1, modules)

        pkg2 = packages[0].model_copy(
            update={"package_id": "preparing_pkg", "status": "preparing"}
        )
        await content_store.write_package(pkg2, [])

        committed = await content_store.get_committed_package_ids()
        assert pkg1.package_id in committed
        assert "preparing_pkg" not in committed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestCommitPackage -v`
Expected: FAIL — methods not implemented

- [ ] **Step 3: Implement both methods in LanceContentStore**

Add to `LanceContentStore` after the `delete_package` method:

```python
async def commit_package(self, package_id: str) -> None:
    """Flip package status from 'preparing' to 'merged'."""
    table = self._db.open_table("packages")
    escaped = _q(package_id)
    rows = table.search().where(f"package_id = '{escaped}'").limit(1).to_list()
    if rows:
        row = dict(rows[0])
        row["status"] = "merged"
        (
            table.merge_insert("package_id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([row])
        )

async def get_committed_package_ids(self) -> set[str]:
    """Return package_ids where status = 'merged'."""
    table = self._db.open_table("packages")
    results = table.search().where("status = 'merged'").limit(_MAX_SCAN).to_list()
    return {r["package_id"] for r in results}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestCommitPackage -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage_v2/content_store.py libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat(storage-v2): implement commit_package and get_committed_package_ids"
```

---

## Chunk 2: Visibility Gate on Reads

### Task 5: Add visibility filtering to LanceContentStore reads

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Test: `tests/libs/storage_v2/test_lance_content.py`

The approach: cache committed package IDs in an instance variable, refreshed on `commit_package` and `delete_package`. Read methods that query knowledge/chains/modules by `source_package_id` / `package_id` will post-filter against committed IDs. `get_package` will add `AND status = 'merged'` to its WHERE.

**Why post-filter?** LanceDB's SQL dialect is limited — it can't do subqueries or JOINs. Since committed package IDs is a small set, post-filtering is both simple and fast. BM25 search results get the same treatment.

- [ ] **Step 1: Write failing tests for visibility**

Add a new test class in `tests/libs/storage_v2/test_lance_content.py`:

```python
class TestVisibilityGate:
    async def test_preparing_package_invisible_to_get_package(self, content_store, modules):
        from libs.storage_v2.models import Package
        pkg = Package(
            package_id="invisible_pkg",
            name="invisible",
            version="1.0.0",
            submitter="tester",
            submitted_at="2026-01-01T00:00:00Z",
            status="preparing",
        )
        await content_store.write_package(pkg, [])
        assert await content_store.get_package("invisible_pkg") is None

    async def test_preparing_knowledge_invisible_to_get(self, content_store, knowledge_items):
        from libs.storage_v2.models import Knowledge
        k = knowledge_items[0].model_copy(
            update={"source_package_id": "invisible_pkg", "knowledge_id": "invisible.k"}
        )
        await content_store.write_knowledge([k])
        assert await content_store.get_knowledge("invisible.k") is None

    async def test_preparing_knowledge_invisible_to_search(self, content_store, knowledge_items):
        from libs.storage_v2.models import Knowledge
        k = knowledge_items[0].model_copy(
            update={
                "source_package_id": "invisible_pkg",
                "knowledge_id": "invisible.k",
                "content": "unique_invisible_content_xyz",
            }
        )
        await content_store.write_knowledge([k])
        results = await content_store.search_bm25("unique_invisible_content_xyz", top_k=5)
        assert all(r.knowledge.knowledge_id != "invisible.k" for r in results)

    async def test_committed_knowledge_visible(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        k = await content_store.get_knowledge(knowledge_items[0].knowledge_id)
        assert k is not None

    async def test_list_knowledge_excludes_preparing(self, content_store, packages, modules, knowledge_items):
        # Write committed package data
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        # Write preparing knowledge
        from libs.storage_v2.models import Knowledge
        k = knowledge_items[0].model_copy(
            update={"source_package_id": "invisible_pkg", "knowledge_id": "invisible.k"}
        )
        await content_store.write_knowledge([k])
        all_k = await content_store.list_knowledge()
        assert all(ki.knowledge_id != "invisible.k" for ki in all_k)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestVisibilityGate -v`
Expected: FAIL — currently returns all data regardless of status

- [ ] **Step 3: Add committed-IDs caching to LanceContentStore**

In `LanceContentStore.__init__`, add:

```python
self._committed_ids: set[str] | None = None  # lazy-loaded cache
```

Add a private helper:

```python
async def _committed_package_ids(self) -> set[str]:
    """Return cached set of committed package IDs, refreshing if needed."""
    if self._committed_ids is None:
        self._committed_ids = await self.get_committed_package_ids()
    return self._committed_ids
```

Invalidate in `commit_package` and `delete_package` by adding `self._committed_ids = None`.

- [ ] **Step 4: Add visibility filter to get_package**

In `get_package`, change the WHERE clause:

```python
async def get_package(self, package_id: str) -> Package | None:
    table = self._db.open_table("packages")
    results = (
        table.search()
        .where(f"package_id = '{_q(package_id)}' AND status = 'merged'")
        .limit(1)
        .to_list()
    )
    if not results:
        return None
    return _row_to_package(results[0])
```

- [ ] **Step 5: Add visibility filter to knowledge reads**

For `get_knowledge`, `get_knowledge_versions`, `list_knowledge`, and `search_bm25` — post-filter by `source_package_id`:

In `get_knowledge`, after fetching results, add:

```python
committed = await self._committed_package_ids()
# filter results to only committed packages
results = [r for r in results if r["source_package_id"] in committed]
```

Apply the same pattern to `get_knowledge_versions`, `list_knowledge`.

For `search_bm25`, filter the scored results:

```python
committed = await self._committed_package_ids()
scored = []
for row in results:
    if row["source_package_id"] not in committed:
        continue
    knowledge = _row_to_knowledge(row)
    scored.append(ScoredKnowledge(knowledge=knowledge, score=row["_score"]))
```

For `get_chains_by_module` and `get_module`, filter by joining through package_id:

```python
# get_chains_by_module — filter by chain's package_id
committed = await self._committed_package_ids()
return [_row_to_chain(r) for r in results if r["package_id"] in committed]
```

```python
# get_module — filter by module's package_id
committed = await self._committed_package_ids()
results = [r for r in results if r["package_id"] in committed]
```

- [ ] **Step 6: Run visibility tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestVisibilityGate -v`
Expected: PASS

- [ ] **Step 7: Run all content store tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py -v`
Expected: ALL PASS — existing tests use fixture packages with `status="merged"`, so visibility gate is transparent

- [ ] **Step 8: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat(storage-v2): add visibility gate — reads only return committed packages"
```

---

## Chunk 3: Vector Upsert + Manager State Machine

### Task 6: Replace delete→add with merge_insert in LanceVectorStore

**Files:**
- Modify: `libs/storage_v2/lance_vector_store.py:69-113`
- Test: `tests/libs/storage_v2/test_vector_store.py`

- [ ] **Step 1: Rewrite `write_embeddings` using merge_insert**

Replace lines 84-113 in `lance_vector_store.py` (everything after validation):

```python
        # Deduplicate within the batch — last occurrence wins
        deduped: dict[tuple[str, int], KnowledgeEmbedding] = {}
        for item in items:
            deduped[(item.knowledge_id, item.version)] = item
        unique_items = list(deduped.values())

        table = self._ensure_table(dim)
        rows = [
            {
                "knowledge_id": item.knowledge_id,
                "version": item.version,
                "vector": item.embedding,
            }
            for item in unique_items
        ]
        (
            table.merge_insert("knowledge_id", "version")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )
```

- [ ] **Step 2: Run all vector store tests**

Run: `pytest tests/libs/storage_v2/test_vector_store.py -v`
Expected: ALL PASS — upsert behavior is the same, just implemented more efficiently

- [ ] **Step 3: Commit**

```bash
git add libs/storage_v2/lance_vector_store.py
git commit -m "feat(storage-v2): replace delete-add with merge_insert in LanceVectorStore"
```

---

### Task 7: Rewrite ingest_package with publish state machine

**Files:**
- Modify: `libs/storage_v2/manager.py:69-107`
- Test: `tests/libs/storage_v2/test_three_write.py`

- [ ] **Step 1: Rewrite `ingest_package` in manager.py**

Replace the entire `ingest_package` method:

```python
async def ingest_package(
    self,
    package: Package,
    modules: list[Module],
    knowledge_items: list[Knowledge],
    chains: list[Chain],
    embeddings: list[KnowledgeEmbedding] | None = None,
) -> None:
    """Write a complete package to all stores with publish state machine.

    1. Write package as 'preparing' (invisible to reads).
    2. Write content, graph, vector idempotently.
    3. Flip status to 'committed' (visible to reads).

    On failure, data stays in 'preparing' — invisible and safe to retry.
    """
    # Force status to 'preparing' during writes
    preparing_pkg = package.model_copy(update={"status": "preparing"})

    # Step 1: ContentStore (source of truth)
    await self.content_store.write_package(preparing_pkg, modules)
    await self.content_store.write_knowledge(knowledge_items)
    await self.content_store.write_chains(chains)

    # Step 2: GraphStore (optional, idempotent)
    if self.graph_store is not None:
        await self.graph_store.write_topology(knowledge_items, chains)

    # Step 3: VectorStore (optional, idempotent)
    if self.vector_store is not None and embeddings:
        await self.vector_store.write_embeddings(embeddings)

    # Step 4: Commit — flip to visible
    await self.content_store.commit_package(preparing_pkg.package_id)
```

- [ ] **Step 2: Rewrite three-write tests**

Replace `TestIngestRollback` in `tests/libs/storage_v2/test_three_write.py` with:

```python
class TestIngestPartialFailure:
    async def test_graph_failure_leaves_package_invisible(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """If GraphStore fails, package stays in 'preparing' — invisible to reads."""
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("graph write failed")
        )

        with pytest.raises(RuntimeError, match="graph write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
            )

        # Package is invisible via manager reads (visibility gate)
        p = await manager.get_package(pkg.package_id)
        assert p is None

        # But the data physically exists in preparing state
        # (direct store access bypasses visibility)

    async def test_vector_failure_leaves_package_invisible(
        self, manager, packages, modules, knowledge_items, chains
    ):
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]
        embeddings = _make_embeddings(pkg_knowledge_items)

        manager.vector_store.write_embeddings = AsyncMock(
            side_effect=RuntimeError("vector write failed")
        )

        with pytest.raises(RuntimeError, match="vector write failed"):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
                embeddings=embeddings,
            )

        # Package invisible
        p = await manager.get_package(pkg.package_id)
        assert p is None

    async def test_retry_after_failure_succeeds(
        self, manager, packages, modules, knowledge_items, chains
    ):
        """Retrying ingest after a failure should succeed (idempotent writes)."""
        pkg = packages[0]
        pkg_modules = [m for m in modules if m.package_id == pkg.package_id]
        pkg_knowledge_items = [c for c in knowledge_items if c.source_package_id == pkg.package_id]
        pkg_chains = [ch for ch in chains if ch.package_id == pkg.package_id]

        # First attempt fails at graph
        manager.graph_store.write_topology = AsyncMock(
            side_effect=RuntimeError("transient failure")
        )
        with pytest.raises(RuntimeError):
            await manager.ingest_package(
                package=pkg,
                modules=pkg_modules,
                knowledge_items=pkg_knowledge_items,
                chains=pkg_chains,
            )

        # Restore real implementation and retry
        from libs.storage_v2.kuzu_graph_store import KuzuGraphStore
        manager.graph_store.write_topology = KuzuGraphStore.write_topology.__get__(
            manager.graph_store
        )

        await manager.ingest_package(
            package=pkg,
            modules=pkg_modules,
            knowledge_items=pkg_knowledge_items,
            chains=pkg_chains,
        )

        # Now visible
        p = await manager.get_package(pkg.package_id)
        assert p is not None
        assert p.status == "merged"
```

- [ ] **Step 3: Run three-write tests**

Run: `pytest tests/libs/storage_v2/test_three_write.py -v`
Expected: ALL PASS

- [ ] **Step 4: Run full storage_v2 tests**

Run: `pytest tests/libs/storage_v2/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage_v2/manager.py tests/libs/storage_v2/test_three_write.py
git commit -m "feat(storage-v2): replace rollback with publish state machine in ingest_package"
```

---

## Chunk 4: CLI + Cleanup

### Task 8: Refactor CLI _publish_local to use StorageManager.ingest_package

**Files:**
- Modify: `cli/main.py:295-395`
- Test: `tests/cli/test_publish.py`

- [ ] **Step 1: Rewrite `_publish_local` to use StorageManager**

Replace the manual store calls (lines 344-366) with `StorageManager.ingest_package()`:

```python
    # 4. Initialize v2 stores via StorageManager
    from libs.storage_v2.config import StorageConfig
    from libs.storage_v2.manager import StorageManager

    config = StorageConfig(
        lancedb_path=db_path,
        graph_backend="kuzu",
        kuzu_path=f"{db_path}/kuzu",
    )
    mgr = StorageManager(config)
    await mgr.initialize()

    try:
        # 5. Ingest (state machine handles preparing → committed)
        await mgr.ingest_package(
            package=data.package,
            modules=data.modules,
            knowledge_items=data.knowledge_items,
            chains=data.chains,
        )

        # 6. Write supplementary data
        if data.probabilities:
            await mgr.add_probabilities(data.probabilities)
        if data.belief_snapshots:
            await mgr.write_beliefs(data.belief_snapshots)
    finally:
        await mgr.close()
```

Remove the direct `LanceContentStore` and `KuzuGraphStore` imports and the manual `delete_package` calls.

- [ ] **Step 2: Run CLI tests**

Run: `pytest tests/cli/test_publish.py tests/cli/test_pipeline_e2e.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest -m "not neo4j" -q`
Expected: ALL PASS

- [ ] **Step 4: Lint and format**

Run: `ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add cli/main.py
git commit -m "refactor(cli): use StorageManager.ingest_package instead of direct store calls"
```

---

### Task 9: Final verification and cleanup

**Files:**
- Review: all modified files

- [ ] **Step 1: Run full test suite with coverage**

Run: `pytest tests/libs/storage_v2/ --cov=libs/storage_v2 --cov-report=term-missing -q`
Expected: ≥ 95% coverage, all tests pass

- [ ] **Step 2: Run full project tests**

Run: `pytest -m "not neo4j" -q`
Expected: ALL PASS, 0 failures

- [ ] **Step 3: Verify no remaining rollback code**

Run: `grep -r "rolling back" libs/storage_v2/`
Expected: No matches

- [ ] **Step 4: Push and update PR**

```bash
git push origin feature/storage-manager
```
