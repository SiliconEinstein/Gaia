# M2: LKM Storage Layer — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the LanceDB storage layer for LKM — 8 core tables with write protocol, content_hash dedup, and StorageManager facade.

**Architecture:** LanceContentStore wraps synchronous LanceDB calls via `run_in_executor`. All complex fields (lists, dicts, nested Pydantic models) are serialized as JSON strings in `pa.string()` columns. StorageManager is the facade providing `ingest_local_graph()` → `integrate_global_graph()` → `commit_package()` flow. GraphStore/VectorStore/BM25/belief_snapshots/node_embeddings are deferred to later milestones.

**Tech Stack:** Python 3.12+, LanceDB, PyArrow, Pydantic v2

**Spec:** `docs/specs/2026-03-31-m2-storage.md`

**Depends on:** M1 models in `gaia/lkm/models/`

---

## File Structure

All paths relative to repo root. Work happens in worktree `.worktrees/lkm-m2-storage/`.

```
gaia/lkm/storage/
├── __init__.py              # Public exports
├── config.py                # StorageConfig (pydantic-settings, env_prefix LKM_)
├── _schemas.py              # PyArrow schemas for 8 tables + _TABLE_SCHEMAS dict
├── _serialization.py        # model_to_row / row_to_model for each M1 model
├── lance_store.py           # LanceContentStore — table init, CRUD, indexes, async wrapping
└── manager.py               # StorageManager facade — ingest/integrate/commit/read protocol

tests/gaia/lkm/storage/
├── __init__.py
├── test_lance_store.py      # Integration tests (real LanceDB, tmp_path)
└── test_e2e_ingest.py       # E2E: ingest 3 packages (galileo/einstein/newton), verify dedup
```

**Why this split:**
- `_schemas.py` is pure data (PyArrow schema dicts) — changes when table columns change
- `_serialization.py` is pure functions (model↔row) — changes when M1 models change
- `lance_store.py` is the LanceDB I/O layer — changes when LanceDB API changes
- `manager.py` is the orchestration layer — changes when write protocol changes

---

## Chunk 1: Config + Schemas + Serialization

### Task 1: StorageConfig

**Files:**
- Create: `gaia/lkm/storage/__init__.py`
- Create: `gaia/lkm/storage/config.py`

- [ ] **Step 1: Create `gaia/lkm/storage/config.py`**

```python
"""LKM storage configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """LKM storage layer configuration.

    All fields overrideable via LKM_ prefixed environment variables.
    """

    # LanceDB
    lancedb_path: str = "/data/lancedb/lkm"
    lancedb_uri: str | None = None  # s3:// or tos:// remote URI

    # Graph backend (deferred — placeholder for M6/M8)
    graph_backend: str = "none"  # "neo4j" | "kuzu" | "none"

    model_config = {"env_prefix": "LKM_"}

    @property
    def effective_lancedb_uri(self) -> str:
        return self.lancedb_uri or self.lancedb_path
```

- [ ] **Step 2: Create `gaia/lkm/storage/__init__.py`**

```python
"""LKM storage layer."""

from gaia.lkm.storage.config import StorageConfig

__all__ = ["StorageConfig"]
```

- [ ] **Step 3: Smoke test**

Run: `python -c "from gaia.lkm.storage import StorageConfig; c = StorageConfig(); print(c.effective_lancedb_uri)"`

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/storage/
git commit -m "feat(lkm): add M2 StorageConfig with LKM_ env prefix"
```

---

### Task 2: PyArrow schemas

**Files:**
- Create: `gaia/lkm/storage/_schemas.py`

- [ ] **Step 1: Create `gaia/lkm/storage/_schemas.py`**

8 table schemas, matching M2 spec §二 exactly. All complex fields as `pa.string()` (JSON serialized).

```python
"""PyArrow schemas for LKM LanceDB tables."""

from __future__ import annotations

import pyarrow as pa

# ── Local layer ──

LOCAL_VARIABLE_NODES = pa.schema([
    pa.field("id", pa.string()),              # QID
    pa.field("type", pa.string()),            # claim | setting | question
    pa.field("visibility", pa.string()),      # public | private
    pa.field("content", pa.string()),
    pa.field("content_hash", pa.string()),
    pa.field("parameters", pa.string()),      # JSON list[Parameter]
    pa.field("source_package", pa.string()),
    pa.field("metadata", pa.string()),        # JSON dict | ""
    pa.field("ingest_status", pa.string()),   # "preparing" | "merged"
])

LOCAL_FACTOR_NODES = pa.schema([
    pa.field("id", pa.string()),
    pa.field("factor_type", pa.string()),     # strategy | operator
    pa.field("subtype", pa.string()),
    pa.field("premises", pa.string()),        # JSON list[str]
    pa.field("conclusion", pa.string()),
    pa.field("background", pa.string()),      # JSON list[str] | ""
    pa.field("steps", pa.string()),           # JSON list[Step] | ""
    pa.field("source_package", pa.string()),
    pa.field("metadata", pa.string()),
    pa.field("ingest_status", pa.string()),
])

# ── Global layer ──

GLOBAL_VARIABLE_NODES = pa.schema([
    pa.field("id", pa.string()),              # gcn_id
    pa.field("type", pa.string()),
    pa.field("visibility", pa.string()),
    pa.field("content_hash", pa.string()),    # MUST have scalar index
    pa.field("parameters", pa.string()),      # JSON list[Parameter]
    pa.field("representative_lcn", pa.string()),  # JSON LocalCanonicalRef
    pa.field("local_members", pa.string()),   # JSON list[LocalCanonicalRef]
    pa.field("metadata", pa.string()),
])

GLOBAL_FACTOR_NODES = pa.schema([
    pa.field("id", pa.string()),              # gfac_id
    pa.field("factor_type", pa.string()),
    pa.field("subtype", pa.string()),
    pa.field("premises", pa.string()),        # JSON list[str] (gcn_ids)
    pa.field("conclusion", pa.string()),      # gcn_id
    pa.field("representative_lfn", pa.string()),
    pa.field("source_package", pa.string()),
    pa.field("metadata", pa.string()),
])

# ── Binding ──

CANONICAL_BINDINGS = pa.schema([
    pa.field("local_id", pa.string()),        # MUST have index
    pa.field("global_id", pa.string()),       # MUST have index
    pa.field("binding_type", pa.string()),    # MUST have index
    pa.field("package_id", pa.string()),
    pa.field("version", pa.string()),
    pa.field("decision", pa.string()),
    pa.field("reason", pa.string()),
    pa.field("created_at", pa.string()),      # ISO 8601
])

# ── Parameterization ──

PRIOR_RECORDS = pa.schema([
    pa.field("variable_id", pa.string()),     # MUST have index
    pa.field("value", pa.float64()),
    pa.field("source_id", pa.string()),
    pa.field("created_at", pa.string()),
])

FACTOR_PARAM_RECORDS = pa.schema([
    pa.field("factor_id", pa.string()),       # MUST have index
    pa.field("conditional_probabilities", pa.string()),  # JSON list[float]
    pa.field("source_id", pa.string()),
    pa.field("created_at", pa.string()),
])

PARAM_SOURCES = pa.schema([
    pa.field("source_id", pa.string()),
    pa.field("source_class", pa.string()),    # official | heuristic | provisional
    pa.field("model", pa.string()),
    pa.field("policy", pa.string()),          # | ""
    pa.field("config", pa.string()),          # JSON dict | ""
    pa.field("created_at", pa.string()),
])

# ── Registry ──

TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "local_variable_nodes": LOCAL_VARIABLE_NODES,
    "local_factor_nodes": LOCAL_FACTOR_NODES,
    "global_variable_nodes": GLOBAL_VARIABLE_NODES,
    "global_factor_nodes": GLOBAL_FACTOR_NODES,
    "canonical_bindings": CANONICAL_BINDINGS,
    "prior_records": PRIOR_RECORDS,
    "factor_param_records": FACTOR_PARAM_RECORDS,
    "param_sources": PARAM_SOURCES,
}
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/storage/_schemas.py
git commit -m "feat(lkm): add M2 PyArrow schemas for 8 LanceDB tables"
```

---

### Task 3: Serialization helpers

**Files:**
- Create: `gaia/lkm/storage/_serialization.py`

Model ↔ row conversion. Each model gets a `_to_row()` and `_from_row()` pair.
Convention: JSON string for complex fields, ISO 8601 for datetimes, `""` for None optionals.

- [ ] **Step 1: Create `gaia/lkm/storage/_serialization.py`**

```python
"""Model ↔ LanceDB row serialization.

Convention:
- Complex fields (list, dict, nested model) → JSON string
- datetime → ISO 8601 string
- Optional string/dict → "" when None
"""

from __future__ import annotations

import json
from datetime import datetime

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    ParameterizationSource,
    PriorRecord,
    Step,
)


def _q(s: str) -> str:
    """Escape single quotes for LanceDB SQL filter expressions."""
    return s.replace("'", "''")


# ── LocalVariableNode ──


def local_variable_to_row(node: LocalVariableNode, ingest_status: str = "preparing") -> dict:
    return {
        "id": node.id,
        "type": node.type,
        "visibility": node.visibility,
        "content": node.content,
        "content_hash": node.content_hash,
        "parameters": json.dumps([p.model_dump() for p in node.parameters]),
        "source_package": node.source_package,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
        "ingest_status": ingest_status,
    }


def row_to_local_variable(row: dict) -> LocalVariableNode:
    params_raw = row.get("parameters", "[]")
    meta_raw = row.get("metadata", "")
    return LocalVariableNode(
        id=row["id"],
        type=row["type"],
        visibility=row["visibility"],
        content=row["content"],
        content_hash=row["content_hash"],
        parameters=[Parameter(**p) for p in json.loads(params_raw)] if params_raw else [],
        source_package=row["source_package"],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── LocalFactorNode ──


def local_factor_to_row(node: LocalFactorNode, ingest_status: str = "preparing") -> dict:
    return {
        "id": node.id,
        "factor_type": node.factor_type,
        "subtype": node.subtype,
        "premises": json.dumps(node.premises),
        "conclusion": node.conclusion,
        "background": json.dumps(node.background) if node.background else "",
        "steps": json.dumps([s.model_dump() for s in node.steps]) if node.steps else "",
        "source_package": node.source_package,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
        "ingest_status": ingest_status,
    }


def row_to_local_factor(row: dict) -> LocalFactorNode:
    bg_raw = row.get("background", "")
    steps_raw = row.get("steps", "")
    meta_raw = row.get("metadata", "")
    return LocalFactorNode(
        id=row["id"],
        factor_type=row["factor_type"],
        subtype=row["subtype"],
        premises=json.loads(row["premises"]),
        conclusion=row["conclusion"],
        background=json.loads(bg_raw) if bg_raw else None,
        steps=[Step(**s) for s in json.loads(steps_raw)] if steps_raw else None,
        source_package=row["source_package"],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── GlobalVariableNode ──


def global_variable_to_row(node: GlobalVariableNode) -> dict:
    return {
        "id": node.id,
        "type": node.type,
        "visibility": node.visibility,
        "content_hash": node.content_hash,
        "parameters": json.dumps([p.model_dump() for p in node.parameters]),
        "representative_lcn": json.dumps(node.representative_lcn.model_dump()),
        "local_members": json.dumps([m.model_dump() for m in node.local_members]),
        "metadata": json.dumps(node.metadata) if node.metadata else "",
    }


def row_to_global_variable(row: dict) -> GlobalVariableNode:
    meta_raw = row.get("metadata", "")
    return GlobalVariableNode(
        id=row["id"],
        type=row["type"],
        visibility=row["visibility"],
        content_hash=row["content_hash"],
        parameters=[Parameter(**p) for p in json.loads(row["parameters"])],
        representative_lcn=LocalCanonicalRef(**json.loads(row["representative_lcn"])),
        local_members=[LocalCanonicalRef(**m) for m in json.loads(row["local_members"])],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── GlobalFactorNode ──


def global_factor_to_row(node: GlobalFactorNode) -> dict:
    return {
        "id": node.id,
        "factor_type": node.factor_type,
        "subtype": node.subtype,
        "premises": json.dumps(node.premises),
        "conclusion": node.conclusion,
        "representative_lfn": node.representative_lfn,
        "source_package": node.source_package,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
    }


def row_to_global_factor(row: dict) -> GlobalFactorNode:
    meta_raw = row.get("metadata", "")
    return GlobalFactorNode(
        id=row["id"],
        factor_type=row["factor_type"],
        subtype=row["subtype"],
        premises=json.loads(row["premises"]),
        conclusion=row["conclusion"],
        representative_lfn=row["representative_lfn"],
        source_package=row["source_package"],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── CanonicalBinding ──


def binding_to_row(b: CanonicalBinding) -> dict:
    return {
        "local_id": b.local_id,
        "global_id": b.global_id,
        "binding_type": b.binding_type,
        "package_id": b.package_id,
        "version": b.version,
        "decision": b.decision,
        "reason": b.reason,
        "created_at": datetime.now().isoformat(),
    }


def row_to_binding(row: dict) -> CanonicalBinding:
    return CanonicalBinding(
        local_id=row["local_id"],
        global_id=row["global_id"],
        binding_type=row["binding_type"],
        package_id=row["package_id"],
        version=row["version"],
        decision=row["decision"],
        reason=row["reason"],
    )


# ── PriorRecord ──


def prior_to_row(r: PriorRecord) -> dict:
    return {
        "variable_id": r.variable_id,
        "value": r.value,
        "source_id": r.source_id,
        "created_at": r.created_at.isoformat(),
    }


def row_to_prior(row: dict) -> PriorRecord:
    return PriorRecord(
        variable_id=row["variable_id"],
        value=row["value"],
        source_id=row["source_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# ── FactorParamRecord ──


def factor_param_to_row(r: FactorParamRecord) -> dict:
    return {
        "factor_id": r.factor_id,
        "conditional_probabilities": json.dumps(r.conditional_probabilities),
        "source_id": r.source_id,
        "created_at": r.created_at.isoformat(),
    }


def row_to_factor_param(row: dict) -> FactorParamRecord:
    return FactorParamRecord(
        factor_id=row["factor_id"],
        conditional_probabilities=json.loads(row["conditional_probabilities"]),
        source_id=row["source_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# ── ParameterizationSource ──


def param_source_to_row(s: ParameterizationSource) -> dict:
    return {
        "source_id": s.source_id,
        "source_class": s.source_class,
        "model": s.model,
        "policy": s.policy or "",
        "config": json.dumps(s.config) if s.config else "",
        "created_at": s.created_at.isoformat(),
    }


def row_to_param_source(row: dict) -> ParameterizationSource:
    config_raw = row.get("config", "")
    return ParameterizationSource(
        source_id=row["source_id"],
        source_class=row["source_class"],
        model=row["model"],
        policy=row["policy"] or None,
        config=json.loads(config_raw) if config_raw else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/storage/_serialization.py
git commit -m "feat(lkm): add M2 model↔row serialization helpers"
```

---

## Chunk 2: LanceContentStore

### Task 4: LanceContentStore implementation

**Files:**
- Create: `gaia/lkm/storage/lance_store.py`

This is the core storage class. Key patterns:
- `_run()` wraps all sync LanceDB calls via `run_in_executor`
- `initialize()` creates tables + scalar indexes
- All writes are batch (`table.add(rows)`)
- Reads filter by `ingest_status = 'merged'` for local nodes

- [ ] **Step 1: Create `gaia/lkm/storage/lance_store.py`**

```python
"""LanceDB storage backend for LKM."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import lancedb

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalFactorNode,
    LocalVariableNode,
    ParameterizationSource,
    PriorRecord,
)
from gaia.lkm.storage._schemas import TABLE_SCHEMAS
from gaia.lkm.storage._serialization import (
    _q,
    binding_to_row,
    factor_param_to_row,
    global_factor_to_row,
    global_variable_to_row,
    local_factor_to_row,
    local_variable_to_row,
    param_source_to_row,
    prior_to_row,
    row_to_binding,
    row_to_global_factor,
    row_to_global_variable,
    row_to_local_factor,
    row_to_local_variable,
    row_to_param_source,
    row_to_prior,
)

_MAX_SCAN = 100_000


class LanceContentStore:
    """LanceDB-backed content store for LKM.

    All LanceDB calls are synchronous — wrapped via run_in_executor.
    """

    def __init__(self, uri: str) -> None:
        self._db = lancedb.connect(uri)

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous function in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ── Initialization ──

    async def initialize(self) -> None:
        """Create all tables if they don't exist, then ensure indexes."""
        existing = set(self._db.list_tables().tables)
        for table_name, schema in TABLE_SCHEMAS.items():
            if table_name not in existing:
                await self._run(self._db.create_table, table_name, schema=schema)
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        """Create scalar indexes on key columns. Safe to call repeatedly."""
        index_specs = [
            ("local_variable_nodes", "content_hash"),
            ("global_variable_nodes", "content_hash"),
            ("canonical_bindings", "local_id"),
            ("canonical_bindings", "global_id"),
            ("canonical_bindings", "binding_type"),
            ("prior_records", "variable_id"),
            ("factor_param_records", "factor_id"),
        ]
        for table_name, column in index_specs:
            try:
                table = self._db.open_table(table_name)
                await self._run(table.create_scalar_index, column, replace=True)
            except Exception:
                # Index creation may fail on empty tables — that's OK,
                # we'll retry after first data write
                pass

    # ── Local node writes ──

    async def write_local_variables(self, nodes: list[LocalVariableNode]) -> None:
        """Batch write local variable nodes with ingest_status='preparing'."""
        if not nodes:
            return
        table = self._db.open_table("local_variable_nodes")
        rows = [local_variable_to_row(n, ingest_status="preparing") for n in nodes]
        await self._run(table.add, rows)

    async def write_local_factors(self, nodes: list[LocalFactorNode]) -> None:
        """Batch write local factor nodes with ingest_status='preparing'."""
        if not nodes:
            return
        table = self._db.open_table("local_factor_nodes")
        rows = [local_factor_to_row(n, ingest_status="preparing") for n in nodes]
        await self._run(table.add, rows)

    async def commit_ingest(self, source_package: str) -> None:
        """Flip ingest_status from 'preparing' to 'merged' for a package."""
        escaped = _q(source_package)
        for table_name in ("local_variable_nodes", "local_factor_nodes"):
            table = self._db.open_table(table_name)
            # LanceDB update: read preparing rows, delete, re-add as merged
            preparing = await self._run(
                lambda t=table, sp=escaped: t.search()
                .where(f"source_package = '{sp}' AND ingest_status = 'preparing'")
                .limit(_MAX_SCAN)
                .to_list()
            )
            if preparing:
                for row in preparing:
                    row["ingest_status"] = "merged"
                await self._run(
                    table.delete, f"source_package = '{escaped}' AND ingest_status = 'preparing'"
                )
                await self._run(table.add, preparing)

    # ── Global node writes ──

    async def write_global_variables(self, nodes: list[GlobalVariableNode]) -> None:
        """Batch write global variable nodes (append-only, idempotent)."""
        if not nodes:
            return
        table = self._db.open_table("global_variable_nodes")
        rows = [global_variable_to_row(n) for n in nodes]
        await self._run(table.add, rows)

    async def write_global_factors(self, nodes: list[GlobalFactorNode]) -> None:
        """Batch write global factor nodes (append-only)."""
        if not nodes:
            return
        table = self._db.open_table("global_factor_nodes")
        rows = [global_factor_to_row(n) for n in nodes]
        await self._run(table.add, rows)

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        """Batch write canonical bindings (append-only, immutable)."""
        if not bindings:
            return
        table = self._db.open_table("canonical_bindings")
        rows = [binding_to_row(b) for b in bindings]
        await self._run(table.add, rows)

    # ── Parameterization writes ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("prior_records")
        rows = [prior_to_row(r) for r in records]
        await self._run(table.add, rows)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("factor_param_records")
        rows = [factor_param_to_row(r) for r in records]
        await self._run(table.add, rows)

    async def write_param_source(self, source: ParameterizationSource) -> None:
        table = self._db.open_table("param_sources")
        await self._run(table.add, [param_source_to_row(source)])

    # ── Reads: local nodes ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        """Get a merged local variable by ID."""
        table = self._db.open_table("local_variable_nodes")
        escaped = _q(local_id)
        results = await self._run(
            lambda: table.search()
            .where(f"id = '{escaped}' AND ingest_status = 'merged'")
            .limit(1)
            .to_list()
        )
        return row_to_local_variable(results[0]) if results else None

    async def get_local_variables_by_package(
        self, source_package: str, merged_only: bool = True
    ) -> list[LocalVariableNode]:
        """Get all local variables for a package."""
        table = self._db.open_table("local_variable_nodes")
        escaped = _q(source_package)
        where = f"source_package = '{escaped}'"
        if merged_only:
            where += " AND ingest_status = 'merged'"
        results = await self._run(
            lambda: table.search().where(where).limit(_MAX_SCAN).to_list()
        )
        return [row_to_local_variable(r) for r in results]

    async def get_local_factor(self, factor_id: str) -> LocalFactorNode | None:
        """Get a merged local factor by ID."""
        table = self._db.open_table("local_factor_nodes")
        escaped = _q(factor_id)
        results = await self._run(
            lambda: table.search()
            .where(f"id = '{escaped}' AND ingest_status = 'merged'")
            .limit(1)
            .to_list()
        )
        return row_to_local_factor(results[0]) if results else None

    # ── Reads: global nodes ──

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(gcn_id)
        results = await self._run(
            lambda: table.search().where(f"id = '{escaped}'").limit(1).to_list()
        )
        return row_to_global_variable(results[0]) if results else None

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        """O(1) indexed lookup by content_hash. Core dedup operation."""
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(content_hash)
        results = await self._run(
            lambda: table.search()
            .where(f"content_hash = '{escaped}' AND visibility = '{visibility}'")
            .limit(1)
            .to_list()
        )
        return row_to_global_variable(results[0]) if results else None

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None:
        table = self._db.open_table("global_factor_nodes")
        escaped = _q(gfac_id)
        results = await self._run(
            lambda: table.search().where(f"id = '{escaped}'").limit(1).to_list()
        )
        return row_to_global_factor(results[0]) if results else None

    async def find_global_factor_exact(
        self,
        premises: list[str],
        conclusion: str,
        factor_type: str,
        subtype: str,
    ) -> GlobalFactorNode | None:
        """Find a global factor by exact structure match."""
        import json as _json

        table = self._db.open_table("global_factor_nodes")
        escaped_conclusion = _q(conclusion)
        escaped_type = _q(factor_type)
        escaped_subtype = _q(subtype)
        # Filter by conclusion + type + subtype first, then check premises in Python
        results = await self._run(
            lambda: table.search()
            .where(
                f"conclusion = '{escaped_conclusion}' AND "
                f"factor_type = '{escaped_type}' AND "
                f"subtype = '{escaped_subtype}'"
            )
            .limit(_MAX_SCAN)
            .to_list()
        )
        sorted_premises = sorted(premises)
        for r in results:
            if sorted((_json.loads(r["premises"]))) == sorted_premises:
                return row_to_global_factor(r)
        return None

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None:
        table = self._db.open_table("canonical_bindings")
        escaped = _q(local_id)
        results = await self._run(
            lambda: table.search().where(f"local_id = '{escaped}'").limit(1).to_list()
        )
        return row_to_binding(results[0]) if results else None

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]:
        table = self._db.open_table("canonical_bindings")
        escaped = _q(global_id)
        results = await self._run(
            lambda: table.search().where(f"global_id = '{escaped}'").limit(_MAX_SCAN).to_list()
        )
        return [row_to_binding(r) for r in results]

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        table = self._db.open_table("prior_records")
        escaped = _q(variable_id)
        results = await self._run(
            lambda: table.search().where(f"variable_id = '{escaped}'").limit(_MAX_SCAN).to_list()
        )
        return [row_to_prior(r) for r in results]

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        table = self._db.open_table("param_sources")
        escaped = _q(source_id)
        results = await self._run(
            lambda: table.search().where(f"source_id = '{escaped}'").limit(1).to_list()
        )
        return row_to_param_source(results[0]) if results else None

    # ── Update: global variable local_members ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        """Replace a global variable node (for appending to local_members)."""
        table = self._db.open_table("global_variable_nodes")
        escaped = _q(gcn_id)
        await self._run(table.delete, f"id = '{escaped}'")
        await self._run(table.add, [global_variable_to_row(updated_node)])

    # ── Table counts (for verification) ──

    async def count(self, table_name: str) -> int:
        """Return row count for a table."""
        table = self._db.open_table(table_name)
        return await self._run(lambda: table.count_rows())
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/storage/lance_store.py
git commit -m "feat(lkm): add M2 LanceContentStore — 8 tables, async wrapping, batch writes"
```

---

### Task 5: StorageManager facade

**Files:**
- Create: `gaia/lkm/storage/manager.py`
- Modify: `gaia/lkm/storage/__init__.py`

- [ ] **Step 1: Create `gaia/lkm/storage/manager.py`**

```python
"""StorageManager — unified facade for LKM storage operations."""

from __future__ import annotations

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalFactorNode,
    LocalVariableNode,
    ParameterizationSource,
    PriorRecord,
)
from gaia.lkm.storage.config import StorageConfig
from gaia.lkm.storage.lance_store import LanceContentStore


class StorageManager:
    """Unified storage facade for LKM.

    Delegates to LanceContentStore (required) and optional backends
    (GraphStore, VectorStore — added in later milestones).
    """

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._content: LanceContentStore | None = None

    @property
    def content(self) -> LanceContentStore:
        assert self._content is not None, "StorageManager not initialized — call initialize() first"
        return self._content

    async def initialize(self) -> None:
        """Initialize all storage backends."""
        self._content = LanceContentStore(self._config.effective_lancedb_uri)
        await self._content.initialize()

    async def close(self) -> None:
        """Close storage backends. LanceDB needs no explicit close."""
        pass

    # ── Ingest protocol ──

    async def ingest_local_graph(
        self,
        package_id: str,
        version: str,
        variable_nodes: list[LocalVariableNode],
        factor_nodes: list[LocalFactorNode],
    ) -> None:
        """Step 1: Write local nodes with ingest_status='preparing'."""
        await self.content.write_local_variables(variable_nodes)
        await self.content.write_local_factors(factor_nodes)

    async def commit_package(self, source_package: str) -> None:
        """Step 7: Flip ingest_status from 'preparing' to 'merged'."""
        await self.content.commit_ingest(source_package)

    async def integrate_global_graph(
        self,
        variable_nodes: list[GlobalVariableNode],
        factor_nodes: list[GlobalFactorNode],
        bindings: list[CanonicalBinding],
        prior_records: list[PriorRecord] | None = None,
        factor_param_records: list[FactorParamRecord] | None = None,
    ) -> None:
        """Steps 2-4: Write global nodes, bindings, and parameters."""
        await self.content.write_global_variables(variable_nodes)
        await self.content.write_global_factors(factor_nodes)
        await self.content.write_bindings(bindings)
        if prior_records:
            await self.content.write_prior_records(prior_records)
        if factor_param_records:
            await self.content.write_factor_param_records(factor_param_records)

    # ── Parameterization ──

    async def write_param_source(self, source: ParameterizationSource) -> None:
        await self.content.write_param_source(source)

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        await self.content.write_prior_records(records)

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        await self.content.write_factor_param_records(records)

    # ── Reads: variables ──

    async def get_local_variable(self, local_id: str) -> LocalVariableNode | None:
        return await self.content.get_local_variable(local_id)

    async def get_global_variable(self, gcn_id: str) -> GlobalVariableNode | None:
        return await self.content.get_global_variable(gcn_id)

    async def find_global_by_content_hash(
        self, content_hash: str, visibility: str = "public"
    ) -> GlobalVariableNode | None:
        return await self.content.find_global_by_content_hash(content_hash, visibility)

    # ── Reads: factors ──

    async def get_global_factor(self, gfac_id: str) -> GlobalFactorNode | None:
        return await self.content.get_global_factor(gfac_id)

    async def find_global_factor_exact(
        self, premises: list[str], conclusion: str, factor_type: str, subtype: str
    ) -> GlobalFactorNode | None:
        return await self.content.find_global_factor_exact(
            premises, conclusion, factor_type, subtype
        )

    # ── Reads: bindings ──

    async def find_canonical_binding(self, local_id: str) -> CanonicalBinding | None:
        return await self.content.find_canonical_binding(local_id)

    async def find_bindings_by_global_id(self, global_id: str) -> list[CanonicalBinding]:
        return await self.content.find_bindings_by_global_id(global_id)

    # ── Reads: parameterization ──

    async def get_prior_records(self, variable_id: str) -> list[PriorRecord]:
        return await self.content.get_prior_records(variable_id)

    async def get_param_source(self, source_id: str) -> ParameterizationSource | None:
        return await self.content.get_param_source(source_id)

    # ── Update ──

    async def update_global_variable_members(
        self, gcn_id: str, updated_node: GlobalVariableNode
    ) -> None:
        await self.content.update_global_variable_members(gcn_id, updated_node)
```

- [ ] **Step 2: Update `gaia/lkm/storage/__init__.py`**

```python
"""LKM storage layer."""

from gaia.lkm.storage.config import StorageConfig
from gaia.lkm.storage.lance_store import LanceContentStore
from gaia.lkm.storage.manager import StorageManager

__all__ = ["StorageConfig", "LanceContentStore", "StorageManager"]
```

- [ ] **Step 3: Commit**

```bash
git add gaia/lkm/storage/manager.py gaia/lkm/storage/__init__.py
git commit -m "feat(lkm): add M2 StorageManager facade with ingest/integrate/commit protocol"
```

---

## Chunk 3: Integration Tests + E2E

### Task 6: Integration tests

**Files:**
- Create: `tests/gaia/lkm/storage/__init__.py`
- Create: `tests/gaia/lkm/storage/test_lance_store.py`

Tests use real LanceDB with `tmp_path` fixture. No mocks.

- [ ] **Step 1: Create `tests/gaia/lkm/storage/test_lance_store.py`**

```python
"""Integration tests for LanceContentStore — real LanceDB, tmp_path."""

import pytest

from gaia.lkm.models import (
    CanonicalBinding,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    compute_content_hash,
    new_gcn_id,
)
from gaia.lkm.storage import StorageConfig, StorageManager


@pytest.fixture
async def storage(tmp_path):
    """Create a StorageManager with a fresh LanceDB in tmp_path."""
    config = StorageConfig(lancedb_path=str(tmp_path / "test_lkm.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


def _make_local_var(
    label: str, content: str, package: str, type_: str = "claim", visibility: str = "public"
) -> LocalVariableNode:
    """Helper to construct a LocalVariableNode with computed content_hash."""
    qid = f"reg:{package}::{label}"
    ch = compute_content_hash(type_, content, [])
    return LocalVariableNode(
        id=qid, type=type_, visibility=visibility,
        content=content, content_hash=ch,
        parameters=[], source_package=package,
    )


class TestTableCreation:
    async def test_all_8_tables_created(self, storage):
        tables = set(storage.content._db.list_tables().tables)
        expected = {
            "local_variable_nodes", "local_factor_nodes",
            "global_variable_nodes", "global_factor_nodes",
            "canonical_bindings",
            "prior_records", "factor_param_records", "param_sources",
        }
        assert expected.issubset(tables)


class TestIngestVisibility:
    async def test_preparing_nodes_invisible(self, storage):
        """Nodes with ingest_status='preparing' should not be returned by reads."""
        node = _make_local_var("claim1", "test content", "pkg_a")
        await storage.ingest_local_graph("pkg_a", "1.0.0", [node], [])

        # Before commit: node should NOT be visible
        result = await storage.get_local_variable("reg:pkg_a::claim1")
        assert result is None

    async def test_merged_nodes_visible(self, storage):
        """After commit, nodes should be visible."""
        node = _make_local_var("claim1", "test content", "pkg_a")
        await storage.ingest_local_graph("pkg_a", "1.0.0", [node], [])
        await storage.commit_package("pkg_a")

        result = await storage.get_local_variable("reg:pkg_a::claim1")
        assert result is not None
        assert result.content == "test content"
        assert result.id == "reg:pkg_a::claim1"


class TestContentHashDedup:
    async def test_find_global_by_content_hash(self, storage):
        """content_hash lookup must work for dedup."""
        content = "Objects fall at equal rates in vacuum"
        ch = compute_content_hash("claim", content, [])
        gcn_id = new_gcn_id()
        ref = LocalCanonicalRef(local_id="reg:galileo::vac", package_id="galileo", version="1.0.0")

        global_var = GlobalVariableNode(
            id=gcn_id, type="claim", visibility="public",
            content_hash=ch, parameters=[],
            representative_lcn=ref, local_members=[ref],
        )
        await storage.integrate_global_graph([global_var], [], [])

        # Lookup by content_hash should find it
        found = await storage.find_global_by_content_hash(ch)
        assert found is not None
        assert found.id == gcn_id

    async def test_content_hash_miss(self, storage):
        """Non-existent content_hash returns None."""
        found = await storage.find_global_by_content_hash("nonexistent_hash")
        assert found is None


class TestBindings:
    async def test_bidirectional_binding_lookup(self, storage):
        """Bindings should be queryable by both local_id and global_id."""
        binding = CanonicalBinding(
            local_id="reg:galileo::claim1", global_id="gcn_abc123",
            binding_type="variable", package_id="galileo",
            version="1.0.0", decision="create_new",
            reason="no matching global node",
        )
        await storage.content.write_bindings([binding])

        # Lookup by local_id
        found = await storage.find_canonical_binding("reg:galileo::claim1")
        assert found is not None
        assert found.global_id == "gcn_abc123"

        # Lookup by global_id
        found_list = await storage.find_bindings_by_global_id("gcn_abc123")
        assert len(found_list) == 1
        assert found_list[0].local_id == "reg:galileo::claim1"


class TestWriteReadRoundtrip:
    async def test_local_variable_roundtrip(self, storage):
        """Write + commit + read should preserve all fields."""
        params = [Parameter(name="x", type="int")]
        ch = compute_content_hash("claim", "test", [("x", "int")])
        node = LocalVariableNode(
            id="reg:pkg::c1", type="claim", visibility="public",
            content="test", content_hash=ch,
            parameters=params, source_package="pkg",
            metadata={"key": "value"},
        )
        await storage.ingest_local_graph("pkg", "1.0.0", [node], [])
        await storage.commit_package("pkg")

        result = await storage.get_local_variable("reg:pkg::c1")
        assert result is not None
        assert result.parameters[0].name == "x"
        assert result.metadata == {"key": "value"}
        assert result.content_hash == ch

    async def test_local_factor_roundtrip(self, storage):
        """Factor write + commit + read preserves steps and background."""
        from gaia.lkm.models import Step

        factor = LocalFactorNode(
            id="lfac_test123", factor_type="strategy", subtype="infer",
            premises=["reg:pkg::p1", "reg:pkg::p2"],
            conclusion="reg:pkg::c1",
            background=["reg:pkg::setting1"],
            steps=[Step(reasoning="Because reasons", premises=["reg:pkg::p1"])],
            source_package="pkg",
        )
        await storage.ingest_local_graph("pkg", "1.0.0", [], [factor])
        await storage.commit_package("pkg")

        result = await storage.content.get_local_factor("lfac_test123")
        assert result is not None
        assert result.premises == ["reg:pkg::p1", "reg:pkg::p2"]
        assert result.steps[0].reasoning == "Because reasons"
        assert result.background == ["reg:pkg::setting1"]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/gaia/lkm/storage/test_lance_store.py -v`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/lkm/storage/
git commit -m "test(lkm): add M2 integration tests — visibility, dedup, bindings, roundtrip"
```

---

### Task 7: E2E ingest script with galileo/einstein/newton content

**Files:**
- Create: `tests/gaia/lkm/storage/test_e2e_ingest.py`

Uses real knowledge content from the 3 Typst v4 packages. Tests the full ingest → commit → integrate → dedup flow.

The key scenario: `newton_principia` references `galileo_falling_bodies::vacuum_prediction` — this should produce a `match_existing` binding on the shared content.

- [ ] **Step 1: Create `tests/gaia/lkm/storage/test_e2e_ingest.py`**

```python
"""E2E test: ingest galileo → einstein → newton, verify dedup on shared content.

Uses real knowledge content from Typst v4 test packages.
Newton's package references Galileo's vacuum_prediction claim — after both
are ingested, content_hash dedup should merge them into one global variable.
"""

import pytest

from gaia.lkm.models import (
    CanonicalBinding,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    compute_content_hash,
    new_gcn_id,
)
from gaia.lkm.storage import StorageConfig, StorageManager


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "e2e.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


# ── Fixture data from Typst v4 packages ──

# Galileo claims (subset)
GALILEO_CLAIMS = [
    ("heavier_falls_faster", "物体下落的速度与其重量成正比——重者下落更快。"),
    ("composite_is_slower", "假设"重者下落更快"，将重球与轻球绑成复合体，则复合体的下落速度慢于重球单独下落。"),
    ("composite_is_faster", "假设"重者下落更快"，将重球与轻球绑成复合体，则复合体的下落速度快于重球单独下落。"),
    ("vacuum_prediction", "在真空中，不同重量的物体应以相同速率下落。"),
]

# Einstein claims (subset)
EINSTEIN_CLAIMS = [
    ("equivalence_principle", "在足够小的时空区域内，均匀引力场的效应与匀加速参考系的效应不可区分。"),
    ("light_bends_in_gravity", "光线在引力场中会发生弯曲。"),
    ("gr_light_deflection", "广义相对论预测：光线掠过太阳表面时偏折1.75角秒。"),
]

# Newton claims — note vacuum_prediction has SAME content as Galileo's
NEWTON_CLAIMS = [
    ("second_law", "牛顿第二定律：物体所受合外力等于其惯性质量与加速度的乘积。F = m_i a"),
    ("law_of_gravity", "万有引力定律：两个物体之间的引力与两者质量之积成正比，与距离的平方成反比。"),
    ("freefall_acceleration", "在地球表面附近，任何物体的自由落体加速度都等于g≈9.8m/s²，与物体质量无关。"),
    # This claim has identical content to galileo::vacuum_prediction
    ("vacuum_prediction", "在真空中，不同重量的物体应以相同速率下落。"),
]


def _build_local_vars(claims: list[tuple[str, str]], package: str) -> list[LocalVariableNode]:
    """Build LocalVariableNode list from (label, content) pairs."""
    nodes = []
    for label, content in claims:
        qid = f"reg:{package}::{label}"
        ch = compute_content_hash("claim", content, [])
        nodes.append(LocalVariableNode(
            id=qid, type="claim", visibility="public",
            content=content, content_hash=ch,
            parameters=[], source_package=package,
        ))
    return nodes


def _build_simple_factor(package: str, premise_label: str, conclusion_label: str) -> LocalFactorNode:
    """Build a simple infer factor between two claims in the same package."""
    return LocalFactorNode(
        id=f"lfac_{package}_{premise_label}_{conclusion_label}",
        factor_type="strategy", subtype="infer",
        premises=[f"reg:{package}::{premise_label}"],
        conclusion=f"reg:{package}::{conclusion_label}",
        source_package=package,
    )


async def _ingest_and_integrate(
    storage: StorageManager,
    package: str,
    version: str,
    local_vars: list[LocalVariableNode],
    local_factors: list[LocalFactorNode],
) -> tuple[list[GlobalVariableNode], list[CanonicalBinding]]:
    """Full ingest→commit→integrate flow. Returns new globals and bindings."""
    # Step 1: write local nodes
    await storage.ingest_local_graph(package, version, local_vars, local_factors)

    # Step 2: commit (preparing → merged)
    await storage.commit_package(package)

    # Step 3: integrate — check dedup for each local variable
    new_globals = []
    all_bindings = []

    for lv in local_vars:
        existing = await storage.find_global_by_content_hash(lv.content_hash)
        ref = LocalCanonicalRef(local_id=lv.id, package_id=package, version=version)

        if existing is not None:
            # match_existing: append to local_members
            updated_members = existing.local_members + [ref]
            updated = GlobalVariableNode(
                id=existing.id, type=existing.type, visibility=existing.visibility,
                content_hash=existing.content_hash, parameters=existing.parameters,
                representative_lcn=existing.representative_lcn,
                local_members=updated_members,
            )
            await storage.update_global_variable_members(existing.id, updated)
            all_bindings.append(CanonicalBinding(
                local_id=lv.id, global_id=existing.id,
                binding_type="variable", package_id=package, version=version,
                decision="match_existing", reason="content_hash exact match",
            ))
        else:
            # create_new
            gcn_id = new_gcn_id()
            gv = GlobalVariableNode(
                id=gcn_id, type=lv.type, visibility=lv.visibility,
                content_hash=lv.content_hash, parameters=lv.parameters,
                representative_lcn=ref, local_members=[ref],
            )
            new_globals.append(gv)
            all_bindings.append(CanonicalBinding(
                local_id=lv.id, global_id=gcn_id,
                binding_type="variable", package_id=package, version=version,
                decision="create_new", reason="no matching global node",
            ))

    await storage.integrate_global_graph(new_globals, [], all_bindings)
    return new_globals, all_bindings


class TestE2EIngest:
    async def test_three_package_ingest_with_dedup(self, storage):
        """Ingest galileo → einstein → newton.
        Newton's vacuum_prediction should dedup against Galileo's.
        """
        galileo_vars = _build_local_vars(GALILEO_CLAIMS, "galileo_falling_bodies")
        galileo_factors = [
            _build_simple_factor("galileo_falling_bodies", "heavier_falls_faster", "composite_is_slower"),
        ]
        einstein_vars = _build_local_vars(EINSTEIN_CLAIMS, "einstein_gravity")
        newton_vars = _build_local_vars(NEWTON_CLAIMS, "newton_principia")

        # ── Ingest galileo ──
        g_globals, g_bindings = await _ingest_and_integrate(
            storage, "galileo_falling_bodies", "4.0.0", galileo_vars, galileo_factors,
        )
        assert len(g_globals) == 4, "All galileo claims should be new globals"
        assert all(b.decision == "create_new" for b in g_bindings)

        # ── Ingest einstein ──
        e_globals, e_bindings = await _ingest_and_integrate(
            storage, "einstein_gravity", "4.0.0", einstein_vars, [],
        )
        assert len(e_globals) == 3, "All einstein claims should be new (no overlap)"
        assert all(b.decision == "create_new" for b in e_bindings)

        # ── Ingest newton ──
        n_globals, n_bindings = await _ingest_and_integrate(
            storage, "newton_principia", "4.0.0", newton_vars, [],
        )
        # 3 new + 1 existing (vacuum_prediction matches galileo's)
        assert len(n_globals) == 3, "3 unique newton claims create new globals"

        match_bindings = [b for b in n_bindings if b.decision == "match_existing"]
        assert len(match_bindings) == 1, "vacuum_prediction should match galileo's"
        assert "reg:newton_principia::vacuum_prediction" == match_bindings[0].local_id

        # ── Verify final state ──
        # Total globals: 4 (galileo) + 3 (einstein) + 3 (newton unique) = 10
        global_count = await storage.content.count("global_variable_nodes")
        assert global_count == 10

        # Total local vars: 4 + 3 + 4 = 11
        local_count = await storage.content.count("local_variable_nodes")
        assert local_count == 11

        # vacuum_prediction global node should have 2 local members
        vac_hash = compute_content_hash("claim", "在真空中，不同重量的物体应以相同速率下落。", [])
        vac_global = await storage.find_global_by_content_hash(vac_hash)
        assert vac_global is not None
        assert len(vac_global.local_members) == 2
        member_ids = {m.local_id for m in vac_global.local_members}
        assert "reg:galileo_falling_bodies::vacuum_prediction" in member_ids
        assert "reg:newton_principia::vacuum_prediction" in member_ids

        # ── Verify all local nodes are merged ──
        for pkg in ["galileo_falling_bodies", "einstein_gravity", "newton_principia"]:
            vars_ = await storage.content.get_local_variables_by_package(pkg, merged_only=True)
            assert len(vars_) > 0, f"{pkg} should have merged local vars"

    async def test_preparing_invisible_during_ingest(self, storage):
        """During ingest (before commit), local nodes should not appear in reads."""
        galileo_vars = _build_local_vars(GALILEO_CLAIMS[:1], "galileo_test")
        await storage.ingest_local_graph("galileo_test", "1.0.0", galileo_vars, [])

        # Before commit — invisible
        result = await storage.get_local_variable("reg:galileo_test::heavier_falls_faster")
        assert result is None

        # After commit — visible
        await storage.commit_package("galileo_test")
        result = await storage.get_local_variable("reg:galileo_test::heavier_falls_faster")
        assert result is not None
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/gaia/lkm/storage/ -v`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/lkm/storage/
git commit -m "test(lkm): add M2 E2E test — 3-package ingest with cross-package dedup"
```

---

## Post-completion

Run full verification:

```bash
# All M2 tests
pytest tests/gaia/lkm/ -v

# Lint
ruff check gaia/lkm/storage/ tests/gaia/lkm/storage/
ruff format --check gaia/lkm/storage/ tests/gaia/lkm/storage/

# Import smoke test
python -c "from gaia.lkm.storage import StorageManager, StorageConfig; print('M2 imports OK')"
```

Then create PR and proceed to M3 (Lowering).
