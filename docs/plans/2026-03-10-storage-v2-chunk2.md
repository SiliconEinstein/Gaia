# ContentStore LanceDB Implementation Plan (Chunk 2/6)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `LanceContentStore` — a LanceDB-backed `ContentStore` with 8 tables, full CRUD, BM25 search, and BP bulk load.

**Architecture:** Each of the 8 domain models maps to one LanceDB table with a PyArrow schema. Complex fields (lists, dicts) are JSON-serialized to strings. FTS index is lazily rebuilt on the `closures` table for BM25 search. All public methods are `async def`; LanceDB calls are synchronous under the hood (following v1 pattern).

**Tech Stack:** Python 3.12, LanceDB >=0.6, PyArrow >=15.0, Pydantic v2

---

## Context

**ABC to implement:** `libs/storage_v2/content_store.py` — 17 abstract methods across write, read, search, and BP bulk load categories.

**Models:** `libs/storage_v2/models.py` — `Package`, `Module`, `Closure`, `Chain` (with `ChainStep`/`ClosureRef`), `ProbabilityRecord`, `BeliefSnapshot`, `Resource`, `ResourceAttachment`, `ScoredClosure`.

**Fixtures:** `tests/fixtures/storage_v2/*.json` — 8 JSON files with Galileo falling-bodies example data.

**v1 reference:** `libs/storage/lance_store.py` — patterns for LanceDB connection, table creation, FTS search, serialization.

**Key design decisions:**
- Closure identity is `(closure_id, version)` — both fields needed for dedup
- Chain stores `steps` as JSON string (list of ChainStep dicts)
- Module stores `imports`, `chain_ids`, `export_ids` as JSON strings
- Package stores `modules`, `exports` as JSON strings
- ProbabilityRecord and BeliefSnapshot are append-only (no upsert)
- BM25 search indexes `content` field on closures table
- `write_closures` skips duplicates by `(closure_id, version)` — check before add

---

### Task 1: Conftest — shared fixtures and store factory

**Files:**
- Create: `tests/libs/storage_v2/conftest.py`

**Step 1: Write the conftest**

```python
"""Shared fixtures for storage_v2 tests."""

import json
from pathlib import Path

import pytest

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
)


def load_fixture(name: str) -> list[dict]:
    path = Path(__file__).parents[2] / "fixtures" / "storage_v2" / f"{name}.json"
    return json.loads(path.read_text())


@pytest.fixture
def packages() -> list[Package]:
    return [Package.model_validate(d) for d in load_fixture("packages")]


@pytest.fixture
def modules() -> list[Module]:
    return [Module.model_validate(d) for d in load_fixture("modules")]


@pytest.fixture
def closures() -> list[Closure]:
    return [Closure.model_validate(d) for d in load_fixture("closures")]


@pytest.fixture
def chains() -> list[Chain]:
    return [Chain.model_validate(d) for d in load_fixture("chains")]


@pytest.fixture
def probabilities() -> list[ProbabilityRecord]:
    return [ProbabilityRecord.model_validate(d) for d in load_fixture("probabilities")]


@pytest.fixture
def beliefs() -> list[BeliefSnapshot]:
    return [BeliefSnapshot.model_validate(d) for d in load_fixture("beliefs")]


@pytest.fixture
def resources() -> list[Resource]:
    return [Resource.model_validate(d) for d in load_fixture("resources")]


@pytest.fixture
def attachments() -> list[ResourceAttachment]:
    return [ResourceAttachment.model_validate(d) for d in load_fixture("attachments")]
```

The `content_store` fixture will be added in Task 2 after the class exists.

**Step 2: Verify conftest loads**

Run: `pytest tests/libs/storage_v2/test_models.py -v`
Expected: All 31 existing tests still PASS (conftest doesn't break anything).

**Step 3: Commit**

```bash
git add tests/libs/storage_v2/conftest.py
git commit -m "test: add shared conftest fixtures for storage_v2"
```

---

### Task 2: LanceContentStore skeleton + initialize

**Files:**
- Create: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/conftest.py` (add `content_store` fixture)
- Create: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write the failing test**

In `tests/libs/storage_v2/test_lance_content.py`:

```python
"""Tests for LanceContentStore — LanceDB-backed ContentStore implementation."""

import pytest


class TestInitialize:
    async def test_initialize_creates_tables(self, content_store):
        """After initialize(), all 8 tables should exist."""
        db = content_store._db
        tables = db.table_names()
        expected = {
            "packages", "modules", "closures", "chains",
            "probabilities", "belief_history", "resources", "resource_attachments",
        }
        assert expected.issubset(set(tables))
```

Add to `conftest.py`:

```python
from libs.storage_v2.lance_content_store import LanceContentStore

@pytest.fixture
async def content_store(tmp_path):
    store = LanceContentStore(str(tmp_path / "lance"))
    await store.initialize()
    return store
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestInitialize -v`
Expected: FAIL — `LanceContentStore` doesn't exist yet.

**Step 3: Write the implementation skeleton**

Create `libs/storage_v2/lance_content_store.py` with:
- `__init__(self, db_path: str)` — `lancedb.connect(db_path)`, init `_fts_dirty = True`
- `initialize()` — create all 8 tables with PyArrow schemas
- All other ABC methods as stubs raising `NotImplementedError`
- PyArrow schemas for all 8 tables

**PyArrow schemas:**

```python
import json
from datetime import datetime
from typing import Any

import lancedb
import pyarrow as pa

from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredClosure,
)

_PACKAGES_SCHEMA = pa.schema([
    pa.field("package_id", pa.string()),
    pa.field("name", pa.string()),
    pa.field("version", pa.string()),
    pa.field("description", pa.string()),
    pa.field("modules", pa.string()),       # JSON list[str]
    pa.field("exports", pa.string()),       # JSON list[str]
    pa.field("submitter", pa.string()),
    pa.field("submitted_at", pa.string()),  # ISO datetime
    pa.field("status", pa.string()),
])

_MODULES_SCHEMA = pa.schema([
    pa.field("module_id", pa.string()),
    pa.field("package_id", pa.string()),
    pa.field("name", pa.string()),
    pa.field("role", pa.string()),
    pa.field("imports", pa.string()),       # JSON list[ImportRef]
    pa.field("chain_ids", pa.string()),     # JSON list[str]
    pa.field("export_ids", pa.string()),    # JSON list[str]
])

_CLOSURES_SCHEMA = pa.schema([
    pa.field("closure_id", pa.string()),
    pa.field("version", pa.int64()),
    pa.field("type", pa.string()),
    pa.field("content", pa.string()),
    pa.field("prior", pa.float64()),
    pa.field("keywords", pa.string()),           # JSON list[str]
    pa.field("source_package_id", pa.string()),
    pa.field("source_module_id", pa.string()),
    pa.field("created_at", pa.string()),         # ISO datetime
    pa.field("embedding", pa.string()),          # JSON list[float] or ""
])

_CHAINS_SCHEMA = pa.schema([
    pa.field("chain_id", pa.string()),
    pa.field("module_id", pa.string()),
    pa.field("package_id", pa.string()),
    pa.field("type", pa.string()),
    pa.field("steps", pa.string()),              # JSON list[ChainStep]
])

_PROBABILITIES_SCHEMA = pa.schema([
    pa.field("chain_id", pa.string()),
    pa.field("step_index", pa.int64()),
    pa.field("value", pa.float64()),
    pa.field("source", pa.string()),
    pa.field("source_detail", pa.string()),
    pa.field("recorded_at", pa.string()),        # ISO datetime
])

_BELIEF_HISTORY_SCHEMA = pa.schema([
    pa.field("closure_id", pa.string()),
    pa.field("version", pa.int64()),
    pa.field("belief", pa.float64()),
    pa.field("bp_run_id", pa.string()),
    pa.field("computed_at", pa.string()),         # ISO datetime
])

_RESOURCES_SCHEMA = pa.schema([
    pa.field("resource_id", pa.string()),
    pa.field("type", pa.string()),
    pa.field("format", pa.string()),
    pa.field("title", pa.string()),
    pa.field("description", pa.string()),
    pa.field("storage_backend", pa.string()),
    pa.field("storage_path", pa.string()),
    pa.field("size_bytes", pa.int64()),
    pa.field("checksum", pa.string()),
    pa.field("metadata", pa.string()),           # JSON dict
    pa.field("created_at", pa.string()),         # ISO datetime
    pa.field("source_package_id", pa.string()),
])

_RESOURCE_ATTACHMENTS_SCHEMA = pa.schema([
    pa.field("resource_id", pa.string()),
    pa.field("target_type", pa.string()),
    pa.field("target_id", pa.string()),
    pa.field("role", pa.string()),
    pa.field("description", pa.string()),
])
```

**Table creation in `initialize()`:**

```python
async def initialize(self) -> None:
    schemas = {
        "packages": _PACKAGES_SCHEMA,
        "modules": _MODULES_SCHEMA,
        "closures": _CLOSURES_SCHEMA,
        "chains": _CHAINS_SCHEMA,
        "probabilities": _PROBABILITIES_SCHEMA,
        "belief_history": _BELIEF_HISTORY_SCHEMA,
        "resources": _RESOURCES_SCHEMA,
        "resource_attachments": _RESOURCE_ATTACHMENTS_SCHEMA,
    }
    existing = set(self._db.table_names())
    for name, schema in schemas.items():
        if name not in existing:
            self._db.create_table(name, schema=schema)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestInitialize -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/conftest.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: add LanceContentStore skeleton with 8-table schema initialization"
```

---

### Task 3: Write and read packages + modules

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestWritePackage:
    async def test_write_and_get_package(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        pkg = await content_store.get_package("galileo_falling_bodies")
        assert pkg is not None
        assert pkg.package_id == "galileo_falling_bodies"
        assert pkg.status == "merged"
        assert "galileo_falling_bodies.setting" in pkg.modules

    async def test_get_nonexistent_package(self, content_store):
        pkg = await content_store.get_package("nonexistent")
        assert pkg is None

    async def test_write_and_get_module(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        mod = await content_store.get_module("galileo_falling_bodies.setting")
        assert mod is not None
        assert mod.name == "setting"
        assert mod.role == "setting"

    async def test_get_nonexistent_module(self, content_store):
        mod = await content_store.get_module("nonexistent")
        assert mod is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWritePackage -v`
Expected: FAIL — methods raise NotImplementedError.

**Step 3: Implement serialization helpers and methods**

Key serialization pattern (for all tables):

```python
def _package_to_row(pkg: Package) -> dict[str, Any]:
    return {
        "package_id": pkg.package_id,
        "name": pkg.name,
        "version": pkg.version,
        "description": pkg.description or "",
        "modules": json.dumps(pkg.modules),
        "exports": json.dumps(pkg.exports),
        "submitter": pkg.submitter,
        "submitted_at": pkg.submitted_at.isoformat(),
        "status": pkg.status,
    }

def _row_to_package(row: dict[str, Any]) -> Package:
    return Package(
        package_id=row["package_id"],
        name=row["name"],
        version=row["version"],
        description=row["description"] or None,
        modules=json.loads(row["modules"]),
        exports=json.loads(row["exports"]),
        submitter=row["submitter"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        status=row["status"],
    )
```

Similar `_module_to_row` / `_row_to_module` pair.

**Methods:**

```python
async def write_package(self, package: Package, modules: list[Module]) -> None:
    pkg_table = self._db.open_table("packages")
    pkg_table.add([_package_to_row(package)])
    if modules:
        mod_table = self._db.open_table("modules")
        mod_table.add([_module_to_row(m) for m in modules])

async def get_package(self, package_id: str) -> Package | None:
    table = self._db.open_table("packages")
    results = table.search().where(f"package_id = '{package_id}'").limit(1).to_list()
    if not results:
        return None
    return _row_to_package(results[0])

async def get_module(self, module_id: str) -> Module | None:
    table = self._db.open_table("modules")
    results = table.search().where(f"module_id = '{module_id}'").limit(1).to_list()
    if not results:
        return None
    return _row_to_module(results[0])
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWritePackage -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement write_package, get_package, get_module"
```

---

### Task 4: Write and read closures (with dedup + versioning)

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestWriteClosures:
    async def test_write_and_get_closure(self, content_store, closures):
        await content_store.write_closures(closures)
        c = await content_store.get_closure(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert c is not None
        assert c.prior == pytest.approx(0.3)

    async def test_get_latest_version(self, content_store, closures):
        """When version=None, return the latest version."""
        await content_store.write_closures(closures)
        # Write a v2 of an existing closure
        v2 = closures[0].model_copy(update={"version": 2, "content": "updated content"})
        await content_store.write_closures([v2])
        latest = await content_store.get_closure(closures[0].closure_id)
        assert latest is not None
        assert latest.version == 2
        assert latest.content == "updated content"

    async def test_get_specific_version(self, content_store, closures):
        await content_store.write_closures(closures)
        c = await content_store.get_closure(closures[0].closure_id, version=1)
        assert c is not None
        assert c.version == 1

    async def test_get_nonexistent_closure(self, content_store):
        c = await content_store.get_closure("nonexistent")
        assert c is None

    async def test_get_closure_versions(self, content_store, closures):
        await content_store.write_closures(closures)
        v2 = closures[0].model_copy(update={"version": 2})
        await content_store.write_closures([v2])
        versions = await content_store.get_closure_versions(closures[0].closure_id)
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2

    async def test_skip_duplicate_closure(self, content_store, closures):
        """Writing the same (closure_id, version) twice should not create duplicates."""
        await content_store.write_closures(closures)
        await content_store.write_closures(closures)  # write again
        versions = await content_store.get_closure_versions(closures[0].closure_id)
        assert len(versions) == 1
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWriteClosures -v`
Expected: FAIL

**Step 3: Implement**

Serialization:
```python
def _closure_to_row(c: Closure) -> dict[str, Any]:
    return {
        "closure_id": c.closure_id,
        "version": c.version,
        "type": c.type,
        "content": c.content,
        "prior": c.prior,
        "keywords": json.dumps(c.keywords),
        "source_package_id": c.source_package_id,
        "source_module_id": c.source_module_id,
        "created_at": c.created_at.isoformat(),
        "embedding": json.dumps(c.embedding) if c.embedding else "",
    }

def _row_to_closure(row: dict[str, Any]) -> Closure:
    emb_raw = row.get("embedding", "")
    return Closure(
        closure_id=row["closure_id"],
        version=row["version"],
        type=row["type"],
        content=row["content"],
        prior=row["prior"],
        keywords=json.loads(row["keywords"]),
        source_package_id=row["source_package_id"],
        source_module_id=row["source_module_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        embedding=json.loads(emb_raw) if emb_raw else None,
    )
```

Methods:
```python
async def write_closures(self, closures: list[Closure]) -> None:
    if not closures:
        return
    table = self._db.open_table("closures")
    # Filter out duplicates already in table
    new_rows = []
    for c in closures:
        existing = (
            table.search()
            .where(f"closure_id = '{c.closure_id}' AND version = {c.version}")
            .limit(1)
            .to_list()
        )
        if not existing:
            new_rows.append(_closure_to_row(c))
    if new_rows:
        table.add(new_rows)
        self._fts_dirty = True

async def get_closure(self, closure_id: str, version: int | None = None) -> Closure | None:
    table = self._db.open_table("closures")
    if version is not None:
        results = (
            table.search()
            .where(f"closure_id = '{closure_id}' AND version = {version}")
            .limit(1)
            .to_list()
        )
    else:
        # Get latest version
        results = (
            table.search()
            .where(f"closure_id = '{closure_id}'")
            .limit(1000)
            .to_list()
        )
        if not results:
            return None
        results = [max(results, key=lambda r: r["version"])]
    if not results:
        return None
    return _row_to_closure(results[0])

async def get_closure_versions(self, closure_id: str) -> list[Closure]:
    table = self._db.open_table("closures")
    results = (
        table.search()
        .where(f"closure_id = '{closure_id}'")
        .limit(1000)
        .to_list()
    )
    closures = [_row_to_closure(r) for r in results]
    return sorted(closures, key=lambda c: c.version)
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWriteClosures -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement write_closures with dedup, get_closure with versioning"
```

---

### Task 5: Write and read chains

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestWriteChains:
    async def test_write_and_get_chains_by_module(self, content_store, chains):
        await content_store.write_chains(chains)
        result = await content_store.get_chains_by_module(
            "galileo_falling_bodies.reasoning"
        )
        assert len(result) == 2
        chain_ids = {c.chain_id for c in result}
        assert "galileo_falling_bodies.reasoning.contradiction_chain" in chain_ids
        assert "galileo_falling_bodies.reasoning.verdict_chain" in chain_ids

    async def test_chain_steps_roundtrip(self, content_store, chains):
        """ChainStep data (premises, conclusion, reasoning) survives serialization."""
        await content_store.write_chains(chains)
        result = await content_store.get_chains_by_module(
            "galileo_falling_bodies.reasoning"
        )
        verdict = next(c for c in result if "verdict" in c.chain_id)
        assert len(verdict.steps) == 2
        assert verdict.steps[0].step_index == 0
        assert len(verdict.steps[0].premises) > 0
        assert verdict.steps[0].conclusion.closure_id != ""

    async def test_get_chains_empty_module(self, content_store):
        result = await content_store.get_chains_by_module("nonexistent")
        assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWriteChains -v`

**Step 3: Implement**

```python
def _chain_to_row(chain: Chain) -> dict[str, Any]:
    return {
        "chain_id": chain.chain_id,
        "module_id": chain.module_id,
        "package_id": chain.package_id,
        "type": chain.type,
        "steps": json.dumps([s.model_dump() for s in chain.steps]),
    }

def _row_to_chain(row: dict[str, Any]) -> Chain:
    return Chain(
        chain_id=row["chain_id"],
        module_id=row["module_id"],
        package_id=row["package_id"],
        type=row["type"],
        steps=json.loads(row["steps"]),
    )

async def write_chains(self, chains: list[Chain]) -> None:
    if not chains:
        return
    table = self._db.open_table("chains")
    table.add([_chain_to_row(c) for c in chains])

async def get_chains_by_module(self, module_id: str) -> list[Chain]:
    table = self._db.open_table("chains")
    results = table.search().where(f"module_id = '{module_id}'").limit(10000).to_list()
    return [_row_to_chain(r) for r in results]
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestWriteChains -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement write_chains, get_chains_by_module with step serialization"
```

---

### Task 6: Probabilities and beliefs (append-only)

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestProbabilities:
    async def test_write_and_get_probability_history(self, content_store, probabilities):
        await content_store.write_probabilities(probabilities)
        history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain"
        )
        assert len(history) == 3  # 3 records for verdict_chain

    async def test_filter_by_step_index(self, content_store, probabilities):
        await content_store.write_probabilities(probabilities)
        history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain",
            step_index=0,
        )
        assert len(history) == 2  # 2 records for step_index=0
        assert all(r.step_index == 0 for r in history)

    async def test_empty_history(self, content_store):
        history = await content_store.get_probability_history("nonexistent")
        assert history == []


class TestBeliefs:
    async def test_write_and_get_belief_history(self, content_store, beliefs):
        await content_store.write_belief_snapshots(beliefs)
        history = await content_store.get_belief_history(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert len(history) >= 1
        # Should be ordered by computed_at
        if len(history) > 1:
            assert history[0].computed_at <= history[1].computed_at

    async def test_empty_belief_history(self, content_store):
        history = await content_store.get_belief_history("nonexistent")
        assert history == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestProbabilities tests/libs/storage_v2/test_lance_content.py::TestBeliefs -v`

**Step 3: Implement**

```python
def _probability_to_row(rec: ProbabilityRecord) -> dict[str, Any]:
    return {
        "chain_id": rec.chain_id,
        "step_index": rec.step_index,
        "value": rec.value,
        "source": rec.source,
        "source_detail": rec.source_detail or "",
        "recorded_at": rec.recorded_at.isoformat(),
    }

def _row_to_probability(row: dict[str, Any]) -> ProbabilityRecord:
    return ProbabilityRecord(
        chain_id=row["chain_id"],
        step_index=row["step_index"],
        value=row["value"],
        source=row["source"],
        source_detail=row["source_detail"] or None,
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
    )

def _belief_to_row(snap: BeliefSnapshot) -> dict[str, Any]:
    return {
        "closure_id": snap.closure_id,
        "version": snap.version,
        "belief": snap.belief,
        "bp_run_id": snap.bp_run_id,
        "computed_at": snap.computed_at.isoformat(),
    }

def _row_to_belief(row: dict[str, Any]) -> BeliefSnapshot:
    return BeliefSnapshot(
        closure_id=row["closure_id"],
        version=row["version"],
        belief=row["belief"],
        bp_run_id=row["bp_run_id"],
        computed_at=datetime.fromisoformat(row["computed_at"]),
    )

async def write_probabilities(self, records: list[ProbabilityRecord]) -> None:
    if not records:
        return
    table = self._db.open_table("probabilities")
    table.add([_probability_to_row(r) for r in records])

async def get_probability_history(
    self, chain_id: str, step_index: int | None = None
) -> list[ProbabilityRecord]:
    table = self._db.open_table("probabilities")
    where = f"chain_id = '{chain_id}'"
    if step_index is not None:
        where += f" AND step_index = {step_index}"
    results = table.search().where(where).limit(10000).to_list()
    records = [_row_to_probability(r) for r in results]
    return sorted(records, key=lambda r: r.recorded_at)

async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None:
    if not snapshots:
        return
    table = self._db.open_table("belief_history")
    table.add([_belief_to_row(s) for s in snapshots])

async def get_belief_history(self, closure_id: str) -> list[BeliefSnapshot]:
    table = self._db.open_table("belief_history")
    results = (
        table.search()
        .where(f"closure_id = '{closure_id}'")
        .limit(10000)
        .to_list()
    )
    snapshots = [_row_to_belief(r) for r in results]
    return sorted(snapshots, key=lambda s: s.computed_at)
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestProbabilities tests/libs/storage_v2/test_lance_content.py::TestBeliefs -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement probabilities and belief snapshots (append-only)"
```

---

### Task 7: Resources and attachments

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestResources:
    async def test_write_and_get_resources(
        self, content_store, resources, attachments
    ):
        await content_store.write_resources(resources, attachments)
        result = await content_store.get_resources_for(
            "closure",
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
        )
        assert len(result) == 1
        assert result[0].type == "image"

    async def test_get_resources_for_chain_step(
        self, content_store, resources, attachments
    ):
        await content_store.write_resources(resources, attachments)
        result = await content_store.get_resources_for(
            "chain_step",
            "galileo_falling_bodies.reasoning.contradiction_chain:0",
        )
        assert len(result) == 1

    async def test_get_resources_empty(self, content_store):
        result = await content_store.get_resources_for("closure", "nonexistent")
        assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestResources -v`

**Step 3: Implement**

```python
def _resource_to_row(r: Resource) -> dict[str, Any]:
    return {
        "resource_id": r.resource_id,
        "type": r.type,
        "format": r.format,
        "title": r.title or "",
        "description": r.description or "",
        "storage_backend": r.storage_backend,
        "storage_path": r.storage_path,
        "size_bytes": r.size_bytes or 0,
        "checksum": r.checksum or "",
        "metadata": json.dumps(r.metadata),
        "created_at": r.created_at.isoformat(),
        "source_package_id": r.source_package_id,
    }

def _row_to_resource(row: dict[str, Any]) -> Resource:
    return Resource(
        resource_id=row["resource_id"],
        type=row["type"],
        format=row["format"],
        title=row["title"] or None,
        description=row["description"] or None,
        storage_backend=row["storage_backend"],
        storage_path=row["storage_path"],
        size_bytes=row["size_bytes"] or None,
        checksum=row["checksum"] or None,
        metadata=json.loads(row["metadata"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        source_package_id=row["source_package_id"],
    )

def _attachment_to_row(a: ResourceAttachment) -> dict[str, Any]:
    return {
        "resource_id": a.resource_id,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "role": a.role,
        "description": a.description or "",
    }

async def write_resources(
    self, resources: list[Resource], attachments: list[ResourceAttachment]
) -> None:
    if resources:
        table = self._db.open_table("resources")
        table.add([_resource_to_row(r) for r in resources])
    if attachments:
        table = self._db.open_table("resource_attachments")
        table.add([_attachment_to_row(a) for a in attachments])

async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]:
    att_table = self._db.open_table("resource_attachments")
    att_results = (
        att_table.search()
        .where(f"target_type = '{target_type}' AND target_id = '{target_id}'")
        .limit(10000)
        .to_list()
    )
    if not att_results:
        return []
    resource_ids = [r["resource_id"] for r in att_results]
    res_table = self._db.open_table("resources")
    resources = []
    for rid in resource_ids:
        rows = res_table.search().where(f"resource_id = '{rid}'").limit(1).to_list()
        if rows:
            resources.append(_row_to_resource(rows[0]))
    return resources
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestResources -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement resources and attachments with join lookup"
```

---

### Task 8: BM25 search

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestBM25Search:
    async def test_search_finds_relevant_closure(self, content_store, closures):
        await content_store.write_closures(closures)
        results = await content_store.search_bm25("heavier objects fall faster", top_k=5)
        assert len(results) >= 1
        ids = [r.closure.closure_id for r in results]
        assert any("heavier" in cid for cid in ids)

    async def test_search_respects_top_k(self, content_store, closures):
        await content_store.write_closures(closures)
        results = await content_store.search_bm25("falls", top_k=2)
        assert len(results) <= 2

    async def test_search_returns_scores(self, content_store, closures):
        await content_store.write_closures(closures)
        results = await content_store.search_bm25("experiment", top_k=5)
        if results:
            assert all(r.score > 0 for r in results)

    async def test_search_empty_table(self, content_store):
        results = await content_store.search_bm25("anything", top_k=5)
        assert results == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestBM25Search -v`

**Step 3: Implement**

```python
async def search_bm25(self, text: str, top_k: int) -> list[ScoredClosure]:
    table = self._db.open_table("closures")
    if table.count_rows() == 0:
        return []
    if self._fts_dirty:
        table.create_fts_index("content", replace=True)
        self._fts_dirty = False
    results = table.search(text, query_type="fts").limit(top_k).to_list()
    scored = []
    for row in results:
        closure = _row_to_closure(row)
        scored.append(ScoredClosure(closure=closure, score=row["_score"]))
    return scored
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestBM25Search -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement BM25 search with lazy FTS index"
```

---

### Task 9: BP bulk load (list_closures, list_chains)

**Files:**
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write failing tests**

```python
class TestBPBulkLoad:
    async def test_list_closures(self, content_store, closures):
        await content_store.write_closures(closures)
        result = await content_store.list_closures()
        assert len(result) == 6

    async def test_list_chains(self, content_store, chains):
        await content_store.write_chains(chains)
        result = await content_store.list_chains()
        assert len(result) == 2

    async def test_list_closures_empty(self, content_store):
        result = await content_store.list_closures()
        assert result == []

    async def test_list_chains_empty(self, content_store):
        result = await content_store.list_chains()
        assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestBPBulkLoad -v`

**Step 3: Implement**

```python
async def list_closures(self) -> list[Closure]:
    table = self._db.open_table("closures")
    if table.count_rows() == 0:
        return []
    results = table.search().limit(table.count_rows()).to_list()
    return [_row_to_closure(r) for r in results]

async def list_chains(self) -> list[Chain]:
    table = self._db.open_table("chains")
    if table.count_rows() == 0:
        return []
    results = table.search().limit(table.count_rows()).to_list()
    return [_row_to_chain(r) for r in results]
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestBPBulkLoad -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/lance_content_store.py tests/libs/storage_v2/test_lance_content.py
git commit -m "feat: implement list_closures, list_chains for BP bulk load"
```

---

### Task 10: Full fixture integration test

**Files:**
- Modify: `tests/libs/storage_v2/test_lance_content.py`

**Step 1: Write integration test**

```python
class TestFullFixtureRoundtrip:
    """Write all fixture data and verify everything reads back correctly."""

    async def test_full_roundtrip(
        self,
        content_store,
        packages,
        modules,
        closures,
        chains,
        probabilities,
        beliefs,
        resources,
        attachments,
    ):
        # Write all fixture data
        await content_store.write_package(packages[0], modules)
        await content_store.write_closures(closures)
        await content_store.write_chains(chains)
        await content_store.write_probabilities(probabilities)
        await content_store.write_belief_snapshots(beliefs)
        await content_store.write_resources(resources, attachments)

        # Verify counts
        all_closures = await content_store.list_closures()
        assert len(all_closures) == 6

        all_chains = await content_store.list_chains()
        assert len(all_chains) == 2

        # Verify cross-references work
        pkg = await content_store.get_package("galileo_falling_bodies")
        assert pkg is not None

        mod = await content_store.get_module("galileo_falling_bodies.reasoning")
        assert mod is not None

        chains_for_mod = await content_store.get_chains_by_module(mod.module_id)
        assert len(chains_for_mod) == 2

        # Verify probability history
        prob_history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain"
        )
        assert len(prob_history) == 3

        # Verify belief history
        belief_history = await content_store.get_belief_history(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert len(belief_history) >= 1

        # Verify BM25 search
        search_results = await content_store.search_bm25("experiment", top_k=10)
        assert len(search_results) >= 1

        # Verify resources
        res = await content_store.get_resources_for(
            "closure",
            "galileo_falling_bodies.reasoning.heavier_falls_faster",
        )
        assert len(res) == 1
```

**Step 2: Run test**

Run: `pytest tests/libs/storage_v2/test_lance_content.py::TestFullFixtureRoundtrip -v`
Expected: PASS

**Step 3: Run ALL storage_v2 tests + lint**

Run: `pytest tests/libs/storage_v2/ -v && ruff check libs/storage_v2/ tests/libs/storage_v2/ && ruff format --check libs/storage_v2/ tests/libs/storage_v2/`
Expected: All tests pass, lint clean.

**Step 4: Commit**

```bash
git add tests/libs/storage_v2/test_lance_content.py
git commit -m "test: add full fixture roundtrip integration test"
```
