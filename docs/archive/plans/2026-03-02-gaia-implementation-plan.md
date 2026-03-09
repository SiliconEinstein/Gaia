# Gaia Phase 1 Implementation Plan

> **Status:** COMPLETED (Phase 1 implemented)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the core Gaia (Large Knowledge Model) system from design docs to working code — storage layer, search engine, commit engine, inference engine, and API gateway.

**Architecture:** Monorepo Python project with `libs/` for shared libraries and `services/` for service modules. Three-layer storage (LanceDB + Neo4j + ByteHouse/LanceDB-local). FastAPI gateway. TDD throughout.

**Tech Stack:** Python 3.12+, LanceDB, Neo4j, FastAPI, Pydantic v2, pytest, pytest-asyncio, NumPy

**Naming Note:** Design docs use hyphens (`services/search-engine/`), but Python packages require underscores. All directories use underscores: `services/search_engine/`, `services/commit_engine/`, etc.

---

## Implementation Order

The system has clear dependency chains:

```
libs/models (shared data models)
    ↓
libs/storage (foundation — LanceDB, Neo4j, Vector, ID)
    ↓
services/search_engine (depends on storage)
    ↓
services/commit_engine (depends on storage + search)
    ↓
services/inference_engine (depends on storage)
    ↓
services/gateway (depends on all above)
```

**Phases:**

| Phase | Tasks | What |
|-------|-------|------|
| 1 | 1–2 | Project skeleton + shared data models |
| 2 | 3–8 | `libs/storage` — Config, IDGenerator, LanceStore, Neo4j, Vector, Manager |
| 3 | 9–12 | `services/search_engine` — 3-path recall + merger + engine |
| 4 | 13–18 | `services/commit_engine` — store, validator, dedup, reviewer, merger, engine |
| 5 | 19–21 | `services/inference_engine` — factor graph, BP, engine |
| 6 | 22–24 | `services/gateway` — FastAPI app + routes |
| 7 | 25 | Integration tests |

---

## Phase 1: Project Setup

### Task 1: Initialize Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `libs/__init__.py`
- Create: `libs/storage/__init__.py` (empty placeholder)
- Create: `libs/storage/vector_search/__init__.py` (empty placeholder)
- Create: `services/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/libs/__init__.py`
- Create: `tests/libs/storage/__init__.py`
- Create: `tests/services/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "gaia"
version = "0.1.0"
description = "Large Knowledge Model — billion-scale reasoning hypergraph"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "lancedb>=0.6",
    "neo4j>=5.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "numpy>=1.26",
    "pyarrow>=15.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.3",
]

[build-system]
requires = ["setuptools>=69.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["libs*", "services*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

**Step 2: Create directory structure**

Run:
```bash
mkdir -p libs/storage/vector_search
mkdir -p services/search_engine services/commit_engine services/inference_engine services/gateway
mkdir -p tests/libs/storage tests/services
touch libs/__init__.py libs/storage/__init__.py libs/storage/vector_search/__init__.py
touch services/__init__.py
touch tests/__init__.py tests/libs/__init__.py tests/libs/storage/__init__.py tests/services/__init__.py
```

**Step 3: Install project in dev mode**

Run: `pip install -e ".[dev]"`

**Step 4: Verify pytest runs**

Run: `pytest --co`
Expected: "no tests ran" (but no errors)

**Step 5: Commit**

```bash
git add pyproject.toml libs/ services/ tests/
git commit -m "feat: initialize project skeleton"
```

---

### Task 2: Shared Data Models (Node, HyperEdge, Operations)

**Files:**
- Create: `libs/models.py`
- Test: `tests/libs/test_models.py`

**Step 1: Write the failing test**

```python
# tests/libs/test_models.py
from libs.models import Node, HyperEdge, AddEdgeOp, ModifyEdgeOp, ModifyNodeOp, NewNode, NodeRef


def test_node_defaults():
    node = Node(id=1, type="paper-extract", content="test")
    assert node.status == "active"
    assert node.belief is None
    assert node.prior == 1.0
    assert node.keywords == []
    assert node.extra == {}
    assert node.title is None
    assert node.metadata == {}


def test_node_all_types():
    for t in ("paper-extract", "abstraction", "deduction", "conjecture"):
        node = Node(id=1, type=t, content="x")
        assert node.type == t


def test_node_title():
    node = Node(id=1, type="paper-extract", content="test", title="My Title")
    assert node.title == "My Title"


def test_hyperedge_defaults():
    edge = HyperEdge(id=1, type="paper-extract", tail=[1], head=[2])
    assert edge.verified is False
    assert edge.probability is None
    assert edge.metadata == {}


def test_hyperedge_types():
    for t in ("paper-extract", "abstraction", "induction", "contradiction", "retraction"):
        edge = HyperEdge(id=1, type=t, tail=[1], head=[2])
        assert edge.type == t


def test_add_edge_op():
    op = AddEdgeOp(
        tail=[NewNode(content="premise")],
        head=[NodeRef(node_id=42)],
        type="induction",
        reasoning=["logical deduction"],
    )
    assert op.op == "add_edge"
    assert len(op.tail) == 1
    assert len(op.head) == 1


def test_modify_edge_op():
    op = ModifyEdgeOp(edge_id=456, changes={"status": "retracted"})
    assert op.op == "modify_edge"


def test_modify_node_op():
    op = ModifyNodeOp(node_id=789, changes={"content": "updated"})
    assert op.op == "modify_node"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/test_models.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/models.py
"""Shared data models for Gaia — Node, HyperEdge, and commit operations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ── Core Graph Entities ──


class Node(BaseModel):
    id: int
    type: str  # paper-extract | abstraction | deduction | conjecture | ...
    subtype: str | None = None
    title: str | None = None
    content: str | dict | list
    keywords: list[str] = []
    prior: float = 1.0
    belief: float | None = None
    status: Literal["active", "deleted"] = "active"
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None


class HyperEdge(BaseModel):
    id: int
    type: str  # paper-extract | abstraction | induction | contradiction | retraction
    subtype: str | None = None
    tail: list[int]
    head: list[int]
    probability: float | None = None
    verified: bool = False
    reasoning: list = []
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None


# ── Commit Operations ──


class NewNode(BaseModel):
    content: str | dict | list
    keywords: list[str] = []
    extra: dict = {}


class NodeRef(BaseModel):
    node_id: int


class AddEdgeOp(BaseModel):
    op: Literal["add_edge"] = "add_edge"
    tail: list[NewNode | NodeRef]
    head: list[NewNode | NodeRef]
    type: str
    reasoning: list


class ModifyEdgeOp(BaseModel):
    op: Literal["modify_edge"] = "modify_edge"
    edge_id: int
    changes: dict


class ModifyNodeOp(BaseModel):
    op: Literal["modify_node"] = "modify_node"
    node_id: int
    changes: dict
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/test_models.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add libs/models.py tests/libs/test_models.py
git commit -m "feat: add shared data models (Node, HyperEdge, operations)"
```

---

## Phase 2: libs/storage

### Task 3: StorageConfig

**Files:**
- Create: `libs/storage/config.py`
- Test: `tests/libs/storage/test_config.py`

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_config.py
from libs.storage.config import StorageConfig


def test_default_config():
    config = StorageConfig()
    assert config.deployment_mode == "local"
    assert config.lancedb_path == "/data/lancedb/gaia"
    assert config.neo4j_uri == "bolt://localhost:7687"
    assert config.neo4j_database == "gaia"


def test_production_config():
    config = StorageConfig(
        deployment_mode="production",
        bytehouse_host="bh.example.com",
        bytehouse_api_key="key123",
    )
    assert config.deployment_mode == "production"
    assert config.bytehouse_host == "bh.example.com"


def test_local_config_override():
    config = StorageConfig(
        lancedb_path="/tmp/test/lance",
        neo4j_password="secret",
    )
    assert config.lancedb_path == "/tmp/test/lance"
    assert config.neo4j_password == "secret"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_config.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/config.py
from typing import Literal

from pydantic import BaseModel


class StorageConfig(BaseModel):
    deployment_mode: Literal["production", "local"] = "local"

    # LanceDB
    lancedb_path: str = "/data/lancedb/gaia"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "gaia"

    # ByteHouse (production only)
    bytehouse_host: str | None = None
    bytehouse_port: int = 19000
    bytehouse_database: str = "gaia"
    bytehouse_api_key: str | None = None

    # Local fallback
    local_vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage/config.py tests/libs/storage/test_config.py
git commit -m "feat: add StorageConfig"
```

---

### Task 4: IDGenerator

**Files:**
- Create: `libs/storage/id_generator.py`
- Test: `tests/libs/storage/test_id_generator.py`

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_id_generator.py
import pytest
from libs.storage.id_generator import IDGenerator


@pytest.fixture
def gen(tmp_path):
    return IDGenerator(storage_path=str(tmp_path / "ids"))


async def test_alloc_node_id(gen):
    id1 = await gen.alloc_node_id()
    id2 = await gen.alloc_node_id()
    assert id1 >= 1
    assert id2 == id1 + 1


async def test_alloc_hyperedge_id(gen):
    id1 = await gen.alloc_hyperedge_id()
    id2 = await gen.alloc_hyperedge_id()
    assert id1 >= 1
    assert id2 == id1 + 1


async def test_alloc_node_ids_bulk(gen):
    ids = await gen.alloc_node_ids_bulk(5)
    assert len(ids) == 5
    assert ids == list(range(ids[0], ids[0] + 5))


async def test_alloc_hyperedge_ids_bulk(gen):
    ids = await gen.alloc_hyperedge_ids_bulk(3)
    assert len(ids) == 3
    assert ids == list(range(ids[0], ids[0] + 3))


async def test_node_and_edge_ids_independent(gen):
    nid = await gen.alloc_node_id()
    eid = await gen.alloc_hyperedge_id()
    # Both start from 1 — independent counters
    assert nid == 1
    assert eid == 1


async def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "ids")
    gen1 = IDGenerator(storage_path=path)
    await gen1.alloc_node_ids_bulk(10)  # advances to 10

    gen2 = IDGenerator(storage_path=path)
    next_id = await gen2.alloc_node_id()
    assert next_id == 11
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_id_generator.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/id_generator.py
"""File-based ID generator. Phase 1: single-process safe via asyncio lock."""

import asyncio
import json
from pathlib import Path


class IDGenerator:

    def __init__(self, storage_path: str):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._counters: dict[str, int] = self._load()

    def _state_file(self) -> Path:
        return self._path / "counters.json"

    def _load(self) -> dict[str, int]:
        f = self._state_file()
        if f.exists():
            return json.loads(f.read_text())
        return {"node": 0, "hyperedge": 0}

    def _save(self) -> None:
        self._state_file().write_text(json.dumps(self._counters))

    async def _alloc(self, kind: str, count: int) -> list[int]:
        async with self._lock:
            start = self._counters[kind] + 1
            self._counters[kind] = start + count - 1
            self._save()
            return list(range(start, start + count))

    async def alloc_node_id(self) -> int:
        return (await self._alloc("node", 1))[0]

    async def alloc_hyperedge_id(self) -> int:
        return (await self._alloc("hyperedge", 1))[0]

    async def alloc_node_ids_bulk(self, count: int) -> list[int]:
        return await self._alloc("node", count)

    async def alloc_hyperedge_ids_bulk(self, count: int) -> list[int]:
        return await self._alloc("hyperedge", count)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_id_generator.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add libs/storage/id_generator.py tests/libs/storage/test_id_generator.py
git commit -m "feat: add IDGenerator with file-based counters"
```

---

### Task 5: LanceStore

**Files:**
- Create: `libs/storage/lance_store.py`
- Test: `tests/libs/storage/test_lance_store.py`

**Reference:** Design doc `storage-layer-design.md` §4.1 — 7 methods: `save_nodes`, `load_node`, `load_nodes_bulk`, `update_node`, `update_beliefs`, `get_beliefs_bulk`, `fts_search`.

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_lance_store.py
import pytest
from libs.models import Node
from libs.storage.lance_store import LanceStore


@pytest.fixture
async def store(tmp_path):
    s = LanceStore(db_path=str(tmp_path / "lance"))
    yield s
    await s.close()


def _make_node(id: int, content: str = "test node", type: str = "paper-extract") -> Node:
    return Node(id=id, type=type, content=content, keywords=["test"])


async def test_save_and_load_node(store):
    node = _make_node(1, "DFT predicts fcc YH10 stable")
    await store.save_nodes([node])
    loaded = await store.load_node(1)
    assert loaded is not None
    assert loaded.id == 1
    assert loaded.content == "DFT predicts fcc YH10 stable"


async def test_load_nonexistent(store):
    result = await store.load_node(999)
    assert result is None


async def test_load_nodes_bulk(store):
    nodes = [_make_node(i, f"node {i}") for i in range(1, 4)]
    await store.save_nodes(nodes)
    loaded = await store.load_nodes_bulk([1, 2, 3])
    assert len(loaded) == 3
    texts = {n.content for n in loaded}
    assert "node 1" in texts


async def test_load_nodes_bulk_partial(store):
    await store.save_nodes([_make_node(1)])
    loaded = await store.load_nodes_bulk([1, 999])
    assert len(loaded) == 1


async def test_update_node(store):
    await store.save_nodes([_make_node(1, "original")])
    await store.update_node(1, content="updated", status="deleted")
    loaded = await store.load_node(1)
    assert loaded.content == "updated"
    assert loaded.status == "deleted"


async def test_update_beliefs(store):
    await store.save_nodes([_make_node(1), _make_node(2, "second")])
    await store.update_beliefs({1: 0.8, 2: 0.6})
    beliefs = await store.get_beliefs_bulk([1, 2])
    assert beliefs[1] == pytest.approx(0.8)
    assert beliefs[2] == pytest.approx(0.6)


async def test_fts_search(store):
    await store.save_nodes([
        _make_node(1, "YH10 superconductivity at high pressure 400GPa"),
        _make_node(2, "LaH10 high pressure experiment results"),
        _make_node(3, "Copper oxide cuprate superconductor mechanism"),
    ])
    results = await store.fts_search("superconductivity", k=10)
    assert len(results) >= 1
    node_ids = [r[0] for r in results]
    assert 1 in node_ids
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_lance_store.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/lance_store.py
"""LanceDB store for node content, metadata, and belief values."""

import json

import lancedb
import pyarrow as pa

from libs.models import Node

NODES_SCHEMA = pa.schema([
    pa.field("id", pa.int64()),
    pa.field("type", pa.string()),
    pa.field("subtype", pa.string()),
    pa.field("title", pa.string()),
    pa.field("content", pa.string()),
    pa.field("keywords", pa.list_(pa.string())),
    pa.field("prior", pa.float64()),
    pa.field("belief", pa.float64()),
    pa.field("status", pa.string()),
    pa.field("metadata", pa.string()),
    pa.field("extra", pa.string()),
    pa.field("created_at", pa.string()),
])


class LanceStore:
    """LanceDB: node content + metadata + belief."""

    def __init__(self, db_path: str):
        self._db = lancedb.connect(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        if "nodes" not in self._db.table_names():
            self._db.create_table("nodes", schema=NODES_SCHEMA)
        self._table = self._db.open_table("nodes")

    async def close(self) -> None:
        pass  # LanceDB handles cleanup on GC

    def _node_to_record(self, n: Node) -> dict:
        content = n.content if isinstance(n.content, str) else json.dumps(n.content)
        return {
            "id": n.id,
            "type": n.type,
            "subtype": n.subtype,
            "title": n.title,
            "content": content,
            "keywords": n.keywords,
            "prior": n.prior,
            "belief": n.belief,
            "status": n.status,
            "metadata": json.dumps(n.metadata) if n.metadata else None,
            "extra": json.dumps(n.extra) if n.extra else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }

    def _record_to_node(self, row: dict) -> Node:
        raw_content = row["content"]
        try:
            content = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError):
            content = raw_content
        return Node(
            id=row["id"],
            type=row["type"],
            subtype=row.get("subtype"),
            title=row.get("title"),
            content=content,
            keywords=row.get("keywords") or [],
            prior=row.get("prior", 1.0),
            belief=row.get("belief"),
            status=row.get("status", "active"),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            extra=json.loads(row["extra"]) if row.get("extra") else {},
            created_at=row.get("created_at"),
        )

    async def save_nodes(self, nodes: list[Node]) -> list[int]:
        records = [self._node_to_record(n) for n in nodes]
        self._table.add(records)
        return [n.id for n in nodes]

    async def load_node(self, node_id: int) -> Node | None:
        results = (
            self._table.search()
            .where(f"id = {node_id}", prefilter=True)
            .limit(1)
            .to_list()
        )
        if not results:
            return None
        return self._record_to_node(results[0])

    async def load_nodes_bulk(self, node_ids: list[int]) -> list[Node]:
        if not node_ids:
            return []
        ids_str = ", ".join(str(i) for i in node_ids)
        results = (
            self._table.search()
            .where(f"id IN ({ids_str})", prefilter=True)
            .limit(len(node_ids))
            .to_list()
        )
        return [self._record_to_node(r) for r in results]

    async def update_node(self, node_id: int, **fields) -> None:
        node = await self.load_node(node_id)
        if node is None:
            return
        updated = node.model_copy(update=fields)
        self._table.delete(f"id = {node_id}")
        await self.save_nodes([updated])

    async def update_beliefs(self, beliefs: dict[int, float]) -> None:
        for node_id, belief in beliefs.items():
            await self.update_node(node_id, belief=belief)

    async def get_beliefs_bulk(self, node_ids: list[int]) -> dict[int, float]:
        nodes = await self.load_nodes_bulk(node_ids)
        return {n.id: n.belief for n in nodes if n.belief is not None}

    async def fts_search(self, query: str, k: int = 100) -> list[tuple[int, float]]:
        try:
            self._table.create_fts_index("content", replace=True)
        except Exception:
            pass
        results = self._table.search(query, query_type="fts").limit(k).to_list()
        return [(r["id"], r.get("_score", 0.0)) for r in results]
```

**Important:** LanceDB's API evolves fast. During implementation, consult the LanceDB docs for the installed version and adjust method signatures as needed. The patterns above (table CRUD + FTS) are correct; exact API may differ.

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_lance_store.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add libs/storage/lance_store.py tests/libs/storage/test_lance_store.py
git commit -m "feat: add LanceStore with CRUD and FTS search"
```

---

### Task 6: Neo4jGraphStore

**Files:**
- Create: `libs/storage/neo4j_store.py`
- Test: `tests/libs/storage/test_neo4j_store.py`

**Prerequisites:** Running Neo4j instance (local or Docker). Tests use a dedicated test database.

**Reference:** Design doc `storage-layer-design.md` §4.2 — 5 methods: `create_hyperedge`, `create_hyperedges_bulk`, `update_hyperedge`, `get_hyperedge`, `get_subgraph`.

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_neo4j_store.py
import os
import pytest
import neo4j
from libs.models import HyperEdge
from libs.storage.neo4j_store import Neo4jGraphStore

NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "testpassword")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "gaiatest")

pytestmark = pytest.mark.neo4j  # skip when Neo4j unavailable


@pytest.fixture
async def store():
    driver = neo4j.AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    s = Neo4jGraphStore(driver=driver, database=NEO4J_DB)
    await s.initialize_schema()
    yield s
    # Cleanup
    async with driver.session(database=NEO4J_DB) as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await driver.close()


def _edge(id: int, tail: list[int], head: list[int], type: str = "paper-extract") -> HyperEdge:
    return HyperEdge(id=id, type=type, tail=tail, head=head, reasoning=["test"])


async def test_create_and_get_hyperedge(store):
    edge = _edge(1, tail=[10, 11], head=[12])
    eid = await store.create_hyperedge(edge)
    assert eid == 1
    loaded = await store.get_hyperedge(1)
    assert loaded is not None
    assert set(loaded.tail) == {10, 11}
    assert loaded.head == [12]


async def test_create_hyperedges_bulk(store):
    edges = [_edge(1, [10], [11]), _edge(2, [11], [12])]
    ids = await store.create_hyperedges_bulk(edges)
    assert ids == [1, 2]


async def test_get_nonexistent_hyperedge(store):
    result = await store.get_hyperedge(999)
    assert result is None


async def test_update_hyperedge(store):
    await store.create_hyperedge(_edge(1, [10], [11]))
    await store.update_hyperedge(1, probability=0.9, verified=True)
    loaded = await store.get_hyperedge(1)
    assert loaded.probability == pytest.approx(0.9)
    assert loaded.verified is True


async def test_get_subgraph_basic(store):
    # Chain: 10 -[e1]-> 11 -[e2]-> 12
    await store.create_hyperedge(_edge(1, [10], [11]))
    await store.create_hyperedge(_edge(2, [11], [12]))
    node_ids, edge_ids = await store.get_subgraph([10], hops=2)
    assert 10 in node_ids
    assert 11 in node_ids
    assert 12 in node_ids
    assert 1 in edge_ids
    assert 2 in edge_ids


async def test_get_subgraph_hops_limit(store):
    await store.create_hyperedge(_edge(1, [10], [11]))
    await store.create_hyperedge(_edge(2, [11], [12]))
    # 1-hop: should reach 11 but not 12
    node_ids, edge_ids = await store.get_subgraph([10], hops=1)
    assert 11 in node_ids
    assert 12 not in node_ids


async def test_get_subgraph_edge_type_filter(store):
    await store.create_hyperedge(_edge(1, [10], [11], type="abstraction"))
    await store.create_hyperedge(_edge(2, [11], [12], type="induction"))
    node_ids, edge_ids = await store.get_subgraph([10], hops=2, edge_types=["abstraction"])
    assert 11 in node_ids
    assert 12 not in node_ids  # induction edge filtered out
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_neo4j_store.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/neo4j_store.py
"""Neo4j graph topology: nodes (Proposition) + hyperedges (Hyperedge node + :TAIL/:HEAD)."""

import json

import neo4j
from libs.models import HyperEdge


class Neo4jGraphStore:
    """Neo4j graph store. Internal labels: :Proposition, :Hyperedge."""

    def __init__(self, driver: neo4j.AsyncDriver, database: str):
        self._driver = driver
        self._db = database

    async def initialize_schema(self) -> None:
        async with self._driver.session(database=self._db) as session:
            await session.run(
                "CREATE CONSTRAINT prop_id IF NOT EXISTS "
                "FOR (p:Proposition) REQUIRE p.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT he_id IF NOT EXISTS "
                "FOR (h:Hyperedge) REQUIRE h.id IS UNIQUE"
            )

    async def close(self) -> None:
        pass  # Driver lifecycle managed by StorageManager

    async def create_hyperedge(self, edge: HyperEdge) -> int:
        async with self._driver.session(database=self._db) as session:
            await session.execute_write(self._create_edge_tx, edge)
        return edge.id

    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        async with self._driver.session(database=self._db) as session:
            for edge in edges:
                await session.execute_write(self._create_edge_tx, edge)
        return [e.id for e in edges]

    async def update_hyperedge(self, edge_id: int, **fields) -> None:
        set_clauses = ", ".join(f"e.{k} = ${k}" for k in fields)
        query = f"MATCH (e:Hyperedge {{id: $edge_id}}) SET {set_clauses}"
        async with self._driver.session(database=self._db) as session:
            await session.run(query, edge_id=edge_id, **fields)

    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        query = """
        MATCH (e:Hyperedge {id: $edge_id})
        OPTIONAL MATCH (t:Proposition)-[:TAIL]->(e)
        OPTIONAL MATCH (e)-[:HEAD]->(h:Proposition)
        RETURN e, collect(DISTINCT t.id) AS tail, collect(DISTINCT h.id) AS head
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, edge_id=edge_id)
            record = await result.single()
            if record is None or record["e"] is None:
                return None
            props = dict(record["e"])
            return HyperEdge(
                id=props["id"],
                type=props.get("type", ""),
                subtype=props.get("subtype"),
                tail=[x for x in record["tail"] if x is not None],
                head=[x for x in record["head"] if x is not None],
                probability=props.get("probability"),
                verified=props.get("verified", False),
                reasoning=json.loads(props.get("reasoning", "[]")),
                metadata=props.get("metadata") or {},
            )

    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
    ) -> tuple[set[int], set[int]]:
        """N-hop neighborhood. Knowledge 1-hop = Neo4j 2-hop (node→hyperedge→node)."""
        neo4j_hops = hops * 2
        if edge_types:
            query = """
            MATCH path = (start:Proposition)-[:TAIL|HEAD*1..""" + str(neo4j_hops) + """]-(node)
            WHERE start.id IN $node_ids
              AND (node:Proposition OR node:Hyperedge)
              AND ALL(n IN [x IN nodes(path) WHERE x:Hyperedge] WHERE n.type IN $edge_types)
            WITH collect(DISTINCT CASE WHEN node:Proposition THEN node.id END) AS props,
                 collect(DISTINCT CASE WHEN node:Hyperedge THEN node.id END) AS edges
            RETURN props + $node_ids AS all_nodes, edges
            """
            params = {"node_ids": node_ids, "edge_types": edge_types}
        else:
            query = """
            MATCH path = (start:Proposition)-[:TAIL|HEAD*1..""" + str(neo4j_hops) + """]-(node)
            WHERE start.id IN $node_ids
              AND (node:Proposition OR node:Hyperedge)
            WITH collect(DISTINCT CASE WHEN node:Proposition THEN node.id END) AS props,
                 collect(DISTINCT CASE WHEN node:Hyperedge THEN node.id END) AS edges
            RETURN props + $node_ids AS all_nodes, edges
            """
            params = {"node_ids": node_ids}

        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, **params)
            record = await result.single()
            if record is None:
                return set(node_ids), set()
            all_nodes = {n for n in record["all_nodes"] if n is not None}
            all_edges = {e for e in record["edges"] if e is not None}
            return all_nodes, all_edges

    @staticmethod
    async def _create_edge_tx(tx: neo4j.AsyncManagedTransaction, edge: HyperEdge) -> None:
        # MERGE proposition nodes
        for tid in edge.tail:
            await tx.run("MERGE (:Proposition {id: $id})", id=tid)
        for hid in edge.head:
            await tx.run("MERGE (:Proposition {id: $id})", id=hid)
        # CREATE hyperedge node
        await tx.run(
            "CREATE (e:Hyperedge {"
            "  id: $id, type: $type, subtype: $subtype,"
            "  probability: $probability, verified: $verified,"
            "  reasoning: $reasoning"
            "})",
            id=edge.id,
            type=edge.type,
            subtype=edge.subtype,
            probability=edge.probability,
            verified=edge.verified,
            reasoning=json.dumps(edge.reasoning),
        )
        # Create TAIL relationships
        for tid in edge.tail:
            await tx.run(
                "MATCH (p:Proposition {id: $pid}), (e:Hyperedge {id: $eid}) "
                "CREATE (p)-[:TAIL]->(e)",
                pid=tid, eid=edge.id,
            )
        # Create HEAD relationships
        for hid in edge.head:
            await tx.run(
                "MATCH (e:Hyperedge {id: $eid}), (p:Proposition {id: $pid}) "
                "CREATE (e)-[:HEAD]->(p)",
                eid=edge.id, pid=hid,
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_neo4j_store.py -v`
Expected: PASS (7 tests). Requires running Neo4j with test database.

**Note:** Add `conftest.py` to skip Neo4j tests when unavailable:

```python
# tests/conftest.py
import pytest

def pytest_collection_modifyitems(config, items):
    """Skip neo4j tests if NEO4J_TEST_URI not set or neo4j unreachable."""
    import os
    if not os.environ.get("NEO4J_TEST_URI") and not _neo4j_available():
        skip = pytest.mark.skip(reason="Neo4j not available")
        for item in items:
            if "neo4j" in item.keywords:
                item.add_marker(skip)

def _neo4j_available() -> bool:
    try:
        import neo4j
        driver = neo4j.GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False
```

**Step 5: Commit**

```bash
git add libs/storage/neo4j_store.py tests/libs/storage/test_neo4j_store.py tests/conftest.py
git commit -m "feat: add Neo4jGraphStore with Cypher-based hyperedge model"
```

---

### Task 7: VectorSearchClient (ABC + LanceDB local implementation)

**Files:**
- Create: `libs/storage/vector_search/base.py`
- Modify: `libs/storage/vector_search/__init__.py`
- Create: `libs/storage/vector_search/lancedb_client.py`
- Test: `tests/libs/storage/test_vector_search.py`

**Reference:** Design doc `storage-layer-design.md` §4.3 — 3 methods: `insert_batch`, `search`, `search_batch`.

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_vector_search.py
import pytest
import numpy as np
from libs.storage.vector_search import create_vector_client
from libs.storage.config import StorageConfig


@pytest.fixture
async def client(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance_vec"))
    return create_vector_client(config)


def _random_embedding(dim: int = 1024) -> list[float]:
    vec = np.random.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()


async def test_insert_and_search(client):
    embs = [_random_embedding() for _ in range(5)]
    await client.insert_batch([1, 2, 3, 4, 5], embs)
    results = await client.search(embs[0], k=3)
    assert len(results) <= 3
    # First result should be exact match (closest to itself)
    assert results[0][0] == 1


async def test_search_empty(client):
    results = await client.search(_random_embedding(), k=5)
    assert results == []


async def test_search_batch(client):
    embs = [_random_embedding() for _ in range(5)]
    await client.insert_batch([1, 2, 3, 4, 5], embs)
    results = await client.search_batch([embs[0], embs[1]], k=2)
    assert len(results) == 2
    assert results[0][0][0] == 1  # first query matches node 1
    assert results[1][0][0] == 2  # second query matches node 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_vector_search.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/vector_search/base.py
from abc import ABC, abstractmethod


class VectorSearchClient(ABC):
    """Unified vector search interface."""

    @abstractmethod
    async def insert_batch(
        self, node_ids: list[int], embeddings: list[list[float]]
    ) -> None:
        """Batch insert embeddings."""

    @abstractmethod
    async def search(
        self, query: list[float], k: int = 50
    ) -> list[tuple[int, float]]:
        """Single vector search. Returns [(node_id, distance), ...]."""

    @abstractmethod
    async def search_batch(
        self, queries: list[list[float]], k: int = 50
    ) -> list[list[tuple[int, float]]]:
        """Batch vector search."""
```

```python
# libs/storage/vector_search/lancedb_client.py
import lancedb
import pyarrow as pa
from .base import VectorSearchClient


class LanceDBVectorClient(VectorSearchClient):
    """Local vector search using LanceDB DiskANN."""

    def __init__(self, db_path: str, index_type: str = "diskann"):
        self._db = lancedb.connect(db_path)
        self._index_type = index_type
        self._table = None

    def _ensure_table(self, dim: int) -> None:
        if self._table is not None:
            return
        if "vectors" in self._db.table_names():
            self._table = self._db.open_table("vectors")
        else:
            schema = pa.schema([
                pa.field("node_id", pa.int64()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
            ])
            self._table = self._db.create_table("vectors", schema=schema)

    async def insert_batch(
        self, node_ids: list[int], embeddings: list[list[float]]
    ) -> None:
        if not node_ids:
            return
        dim = len(embeddings[0])
        self._ensure_table(dim)
        records = [
            {"node_id": nid, "vector": emb}
            for nid, emb in zip(node_ids, embeddings)
        ]
        self._table.add(records)

    async def search(
        self, query: list[float], k: int = 50
    ) -> list[tuple[int, float]]:
        if self._table is None:
            return []
        results = self._table.search(query).limit(k).to_list()
        return [(r["node_id"], r["_distance"]) for r in results]

    async def search_batch(
        self, queries: list[list[float]], k: int = 50
    ) -> list[list[tuple[int, float]]]:
        return [await self.search(q, k) for q in queries]
```

```python
# libs/storage/vector_search/__init__.py
from .base import VectorSearchClient
from ..config import StorageConfig


def create_vector_client(config: StorageConfig) -> VectorSearchClient:
    if config.deployment_mode == "production":
        from .bytehouse_client import ByteHouseVectorClient
        return ByteHouseVectorClient(
            host=config.bytehouse_host,
            port=config.bytehouse_port,
            database=config.bytehouse_database,
            api_key=config.bytehouse_api_key,
        )
    else:
        from .lancedb_client import LanceDBVectorClient
        return LanceDBVectorClient(
            db_path=config.lancedb_path,
            index_type=config.local_vector_index_type,
        )


__all__ = ["VectorSearchClient", "create_vector_client"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_vector_search.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add libs/storage/vector_search/ tests/libs/storage/test_vector_search.py
git commit -m "feat: add VectorSearchClient ABC + LanceDB local implementation"
```

---

### Task 8: StorageManager + Package Exports

**Files:**
- Create: `libs/storage/manager.py`
- Modify: `libs/storage/__init__.py`
- Test: `tests/libs/storage/test_manager.py`

**Reference:** Design doc `storage-layer-design.md` §4.4 — container with `lance`, `graph`, `vector`, `ids` attributes + `close()`.

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_manager.py
import pytest
from libs.storage import StorageManager, StorageConfig
from libs.storage.lance_store import LanceStore
from libs.storage.id_generator import IDGenerator
from libs.storage.vector_search.base import VectorSearchClient


async def test_manager_creates_stores(tmp_path):
    config = StorageConfig(
        lancedb_path=str(tmp_path / "lance"),
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="testpassword",
    )
    manager = StorageManager(config)
    assert isinstance(manager.lance, LanceStore)
    assert isinstance(manager.ids, IDGenerator)
    assert isinstance(manager.vector, VectorSearchClient)
    await manager.close()


async def test_manager_stores_work(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"))
    manager = StorageManager(config)
    # IDGenerator should work through manager
    nid = await manager.ids.alloc_node_id()
    assert nid >= 1
    await manager.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_manager.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# libs/storage/manager.py
"""StorageManager: container for all storage backends."""

import neo4j

from .config import StorageConfig
from .lance_store import LanceStore
from .neo4j_store import Neo4jGraphStore
from .vector_search import create_vector_client, VectorSearchClient
from .id_generator import IDGenerator


class StorageManager:
    """Creates all stores from a single config. No composite business logic."""

    lance: LanceStore
    graph: Neo4jGraphStore
    vector: VectorSearchClient
    ids: IDGenerator

    def __init__(self, config: StorageConfig):
        self.lance = LanceStore(config.lancedb_path)
        self._driver = neo4j.AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password),
        )
        self.graph = Neo4jGraphStore(
            driver=self._driver,
            database=config.neo4j_database,
        )
        self.vector = create_vector_client(config)
        self.ids = IDGenerator(storage_path=config.lancedb_path + "/ids")

    async def close(self) -> None:
        await self.lance.close()
        await self.graph.close()
        await self._driver.close()
```

```python
# libs/storage/__init__.py
from .config import StorageConfig
from .manager import StorageManager

__all__ = ["StorageConfig", "StorageManager"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage/test_manager.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add libs/storage/manager.py libs/storage/__init__.py tests/libs/storage/test_manager.py
git commit -m "feat: add StorageManager container and package exports"
```

---

## Phase 3: services/search_engine

**Reference:** Design doc `search-engine-design.md` — 6 public methods across 5 classes.

### Task 9: VectorRecall

**Files:**
- Create: `services/search_engine/__init__.py`
- Create: `services/search_engine/recall/__init__.py`
- Create: `services/search_engine/recall/vector.py`
- Test: `tests/services/test_search_engine/__init__.py`
- Test: `tests/services/test_search_engine/test_vector_recall.py`

**Interface:**
```python
class VectorRecall:
    def __init__(self, vector_client: VectorSearchClient): ...
    async def recall(self, embedding: list[float], k: int = 100) -> list[tuple[int, float]]:
        """Returns [(node_id, distance), ...]"""
```

**TDD Steps:** Write test → verify fail → implement (thin wrapper over `vector_client.search`) → verify pass → commit.

---

### Task 10: BM25Recall

**Files:**
- Create: `services/search_engine/recall/bm25.py`
- Test: `tests/services/test_search_engine/test_bm25_recall.py`

**Interface:**
```python
class BM25Recall:
    def __init__(self, lance_store: LanceStore): ...
    async def recall(self, query: str, k: int = 100) -> list[tuple[int, float]]:
        """Returns [(node_id, bm25_score), ...]"""
```

**TDD Steps:** Write test → verify fail → implement (thin wrapper over `lance_store.fts_search`) → verify pass → commit.

---

### Task 11: TopologyRecall

**Files:**
- Create: `services/search_engine/recall/topology.py`
- Test: `tests/services/test_search_engine/test_topology_recall.py`

**Interface:**
```python
class TopologyRecall:
    def __init__(self, graph_store: Neo4jGraphStore): ...
    async def recall(self, seed_node_ids: list[int], hops: int = 3) -> list[tuple[int, float]]:
        """Traverse Abstraction tree from seeds. Returns [(node_id, hop_distance), ...]"""
```

**Implementation:** Call `graph_store.get_subgraph(seed_node_ids, hops, edge_types=["abstraction"])`, then assign scores inversely proportional to hop distance.

**TDD Steps:** Write test → verify fail → implement → verify pass → commit.

---

### Task 12: ResultMerger + SearchEngine

**Files:**
- Create: `services/search_engine/merger.py`
- Create: `services/search_engine/engine.py`
- Test: `tests/services/test_search_engine/test_merger.py`
- Test: `tests/services/test_search_engine/test_engine.py`

**ResultMerger interface:**
```python
class ResultMerger:
    async def merge(
        self,
        results: dict[str, list[tuple[int, float]]],
        k: int = 50,
    ) -> list[tuple[int, float, list[str]]]:
        """Normalize scores, weighted sum, dedup, return top-k."""
```

**SearchEngine interface:** (see design doc §4.1)
```python
class SearchEngine:
    async def search_nodes(self, query, embedding, k, filters, paths) -> list[ScoredNode]: ...
    async def search_edges(self, query, embedding, k, filters, paths) -> list[ScoredHyperEdge]: ...
```

**SearchEngine.search_nodes flow:**
1. Parallel: VectorRecall + BM25Recall
2. Take vector top-10 as seeds → TopologyRecall
3. ResultMerger.merge(three results)
4. Load node details from LanceStore
5. Apply filters
6. Return `list[ScoredNode]`

**TDD Steps:** Write tests for merger (normalize, dedup, weighted sort) → implement → write tests for engine (mock recall components) → implement → commit.

---

## Phase 4: services/commit_engine

**Reference:** Design doc `commit-engine-design.md` — 11 public methods across 6 classes.

### Task 13: Commit Data Models

**Files:**
- Modify: `libs/models.py` (add Commit, CommitRequest, etc.)
- Test: `tests/libs/test_models.py` (extend)

**Add to `libs/models.py`:**
```python
class Commit(BaseModel):
    commit_id: str
    status: Literal["pending_review", "reviewed", "rejected", "merged"]
    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]
    check_results: dict | None = None
    review_results: dict | None = None
    merge_results: dict | None = None
    created_at: datetime
    updated_at: datetime
```

**TDD Steps:** Write test → implement → commit.

---

### Task 14: CommitStore

**Files:**
- Create: `services/commit_engine/__init__.py`
- Create: `services/commit_engine/store.py`
- Test: `tests/services/test_commit_engine/__init__.py`
- Test: `tests/services/test_commit_engine/test_store.py`

**Interface:**
```python
class CommitStore:
    async def save(self, commit: Commit) -> str: ...
    async def get(self, commit_id: str) -> Commit | None: ...
    async def update(self, commit_id: str, **fields) -> None: ...
```

**Implementation:** Backed by a LanceDB table for commit persistence.

**TDD Steps:** Write test → implement → commit.

---

### Task 15: Validator

**Files:**
- Create: `services/commit_engine/validator.py`
- Test: `tests/services/test_commit_engine/test_validator.py`

**Interface:**
```python
class Validator:
    async def validate(self, operations: list[Operation]) -> list[ValidationResult]:
        """Structural validation only — no LLM."""
```

**Validates:**
- `add_edge`: tail/head non-empty, type is valid, referenced node_ids exist
- `modify_edge`: edge_id exists
- `modify_node`: node_id exists

**TDD Steps:** Write test for each validation rule → implement → commit.

---

### Task 16: DedupChecker

**Files:**
- Create: `services/commit_engine/dedup.py`
- Test: `tests/services/test_commit_engine/test_dedup.py`

**Interface:**
```python
class DedupChecker:
    async def check(self, contents: list[str]) -> list[list[DedupCandidate]]:
        """Multi-path recall for dedup candidates. No LLM."""
```

**Implementation:** Uses `SearchEngine.search_nodes` with vector + bm25 paths (no topology) for each new node content.

**TDD Steps:** Write test → implement → commit.

---

### Task 17: Reviewer (LLM stub)

**Files:**
- Create: `services/commit_engine/reviewer.py`
- Test: `tests/services/test_commit_engine/test_reviewer.py`

**Interface:**
```python
class Reviewer:
    async def review(self, commit: Commit, depth: str = "standard") -> ReviewResult: ...
```

**Phase 1 implementation:** Use a pluggable `LLMClient` interface. Create a stub/mock that returns pass for tests. Real LLM integration is a separate task.

**TDD Steps:** Write test with mock LLM → implement → commit.

---

### Task 18: Merger + CommitEngine

**Files:**
- Create: `services/commit_engine/merger.py`
- Create: `services/commit_engine/engine.py`
- Test: `tests/services/test_commit_engine/test_merger.py`
- Test: `tests/services/test_commit_engine/test_engine.py`

**Merger interface:**
```python
class Merger:
    async def merge(self, commit: Commit) -> MergeResult:
        """Triple-write: LanceDB + Neo4j + VectorSearch + trigger BP."""
```

**CommitEngine interface:** (see design doc §6.1)
```python
class CommitEngine:
    async def submit(self, request: CommitRequest) -> CommitResponse: ...
    async def review(self, commit_id: str, depth: str) -> ReviewResponse: ...
    async def merge(self, commit_id: str, force: bool) -> MergeResponse: ...
    async def get_commit(self, commit_id: str) -> Commit: ...
```

**CommitEngine.submit flow:**
1. Validator.validate(operations)
2. DedupChecker.check(new_node_contents)
3. CommitStore.save(commit) → status = pending_review
4. Return CommitResponse with check_results

**TDD Steps:** Write merger test (mock storage) → implement → write engine test (full workflow) → implement → commit.

---

## Phase 5: services/inference_engine

**Reference:** Design doc `inference-engine-design.md` — 2 public methods + internal FactorGraph + BP.

### Task 19: FactorGraph

**Files:**
- Create: `services/inference_engine/__init__.py`
- Create: `services/inference_engine/factor_graph.py`
- Test: `tests/services/test_inference_engine/__init__.py`
- Test: `tests/services/test_inference_engine/test_factor_graph.py`

**Interface:**
```python
class FactorGraph:
    def add_variable(self, node_id: int, prior: float) -> None: ...
    def add_factor(self, edge_id: int, tail: list[int], head: list[int], probability: float) -> None: ...
    @classmethod
    def from_subgraph(cls, nodes: list[Node], edges: list[HyperEdge]) -> "FactorGraph": ...
```

**Test:** Build a small factor graph, verify variable/factor counts, verify `from_subgraph` factory.

**TDD Steps:** Write test → implement → commit.

---

### Task 20: BeliefPropagation

**Files:**
- Create: `services/inference_engine/bp.py`
- Test: `tests/services/test_inference_engine/test_bp.py`

**Interface:**
```python
class BeliefPropagation:
    def __init__(self, damping: float = 0.5, max_iterations: int = 50, convergence_threshold: float = 1e-6): ...
    def run(self, graph: FactorGraph) -> dict[int, float]:
        """Returns {node_id: belief}."""
```

**Test scenarios:**
- Single factor: A → B with p=0.8 → B's belief should be influenced
- Chain: A → B → C → beliefs propagate
- Convergence: run on a small loop, verify it converges within max_iterations

**TDD Steps:** Write test → implement with NumPy → commit.

---

### Task 21: InferenceEngine

**Files:**
- Create: `services/inference_engine/engine.py`
- Test: `tests/services/test_inference_engine/test_engine.py`

**Interface:**
```python
class InferenceEngine:
    async def compute_local_bp(self, center_node_ids: list[int], hops: int = 3) -> dict[int, float]: ...
    async def run_global_bp(self) -> None: ...
```

**compute_local_bp flow:**
1. `storage.graph.get_subgraph(center_node_ids, hops)`
2. Batch `storage.graph.get_hyperedge(eid)` for each edge
3. `storage.lance.load_nodes_bulk(node_ids)` for priors
4. `FactorGraph.from_subgraph(nodes, edges)`
5. `BeliefPropagation.run(graph)`
6. `storage.lance.update_beliefs(results)`

**TDD Steps:** Write test (mock storage, verify BP called and beliefs written back) → implement → commit.

---

## Phase 6: services/gateway

**Reference:** Design doc `api-gateway-design.md` — 10 endpoints.

### Task 22: App Setup + Dependencies

**Files:**
- Create: `services/gateway/__init__.py`
- Create: `services/gateway/app.py`
- Create: `services/gateway/deps.py`
- Test: `tests/services/test_gateway/__init__.py`
- Test: `tests/services/test_gateway/test_app.py`

**Implementation:** FastAPI app factory + dependency injection (see design doc §5).

**TDD Steps:** Write test (app starts, health endpoint) → implement → commit.

---

### Task 23: Commit Routes

**Files:**
- Create: `services/gateway/routes/__init__.py`
- Create: `services/gateway/routes/commits.py`
- Test: `tests/services/test_gateway/test_commits.py`

**Endpoints:** POST /commits, GET /commits/{id}, POST /commits/{id}/review, POST /commits/{id}/merge, POST /commits/batch

**TDD Steps:** Write test (using FastAPI TestClient + mocked engine) → implement routes → commit.

---

### Task 24: Read + Search Routes

**Files:**
- Create: `services/gateway/routes/read.py`
- Create: `services/gateway/routes/search.py`
- Test: `tests/services/test_gateway/test_read.py`
- Test: `tests/services/test_gateway/test_search.py`

**Endpoints:** GET /nodes/{id}, GET /hyperedges/{id}, GET /nodes/{id}/subgraph, POST /search/nodes, POST /search/hyperedges

**TDD Steps:** Write test → implement routes → commit.

---

## Phase 7: Integration

### Task 25: End-to-End Integration Tests

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_e2e.py`

**Test full scenarios from design docs:**

1. **Research Agent flow:** search → submit commit → review → merge → verify node in graph → search finds new node
2. **Batch ingest:** batch submit → auto review → verify merge results
3. **Edge retraction:** submit modify_edge(retracted) → review → merge → verify BP recalculation
4. **Overlap detection:** submit with duplicate text → review detects overlap → merge rejects → resubmit with node_id reference → merge succeeds

**TDD Steps:** Write test → wire everything together → fix issues → commit.

---

## Summary

| Phase | Tasks | Components | Test Count (est.) |
|-------|-------|------------|-------------------|
| 1 | 1–2 | Project + Models | ~7 |
| 2 | 3–8 | Storage Layer | ~25 |
| 3 | 9–12 | Search Engine | ~15 |
| 4 | 13–18 | Commit Engine | ~20 |
| 5 | 19–21 | Inference Engine | ~10 |
| 6 | 22–24 | Gateway | ~15 |
| 7 | 25 | Integration | ~5 |
| **Total** | **25** | **All** | **~97** |

**Key design docs to reference during implementation:**
- `docs/plans/2026-03-02-storage-layer-design.md` — 20 methods, all interfaces
- `docs/plans/2026-03-02-commit-engine-design.md` — 11 methods, 3-step workflow
- `docs/plans/2026-03-02-search-engine-design.md` — 6 methods, 3-path recall
- `docs/plans/2026-03-02-inference-engine-design.md` — 2 methods, BP algorithm
- `docs/plans/2026-03-02-api-gateway-design.md` — 10 endpoints
- `docs/plans/2026-03-02-lkm-api-design-v2.md` — Full API spec with request/response schemas
