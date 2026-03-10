# Storage Layer V2 — Design

## Goal

Implement the new storage layer based on Gaia Language concepts (Closure, Chain, Module, Package), replacing the current Node/HyperEdge-based storage. Built in `libs/storage_v2/` alongside the old code, then swap once complete.

## Project Structure

```
libs/storage_v2/
├── __init__.py                # exports StorageManager, configs
├── models.py                  # Pydantic v2 models
├── config.py                  # StorageConfig
├── manager.py                 # StorageManager facade + three-write logic
├── content_store.py           # ContentStore ABC
├── graph_store.py             # GraphStore ABC
├── vector_store.py            # VectorStore ABC
├── lance_content_store.py     # LanceDB implementation (8 tables)
├── kuzu_graph_store.py        # Kuzu implementation
├── neo4j_graph_store.py       # Neo4j implementation
├── lance_vector_store.py      # LanceDB vector implementation
└── id_generator.py            # reuse/copy from v1

tests/fixtures/storage_v2/
├── packages.json
├── modules.json
├── closures.json
├── chains.json
├── probabilities.json
├── beliefs.json
├── resources.json
└── attachments.json

tests/libs/storage_v2/
├── conftest.py                # fixture loading, store factories
├── test_models.py
├── test_lance_content.py
├── test_graph_store.py        # parametrized: kuzu + neo4j
├── test_vector_store.py
├── test_manager.py
└── test_three_write.py

tests/integration/
└── test_storage_v2_e2e.py

scripts/
├── seed_v2.py
└── smoke_test_v2.py
```

## Data Models

Based on `docs/foundations/server/storage-schema.md`:

- **Package** — knowledge container, 1 git repo
- **Module** — cohesive knowledge unit within a package
- **Closure** — versioned knowledge object `(closure_id, version)` unique
- **Chain** — reasoning link with steps
- **ChainStep** — single reasoning step with `step_index`, `ClosureRef` premises/conclusion
- **ClosureRef** — versioned reference `(closure_id, version)`
- **ProbabilityRecord** — per-step `(chain_id, step_index)` granularity, multi-source
- **BeliefSnapshot** — per-closure BP result history
- **Resource** — multimedia metadata (files in TOS)
- **ResourceAttachment** — many-to-many link, step-level via `chain_id:step_index`
- **ImportRef** — cross-module dependency with strength

All IDs are strings (not ints).

## Storage Backend ABCs

### ContentStore (LanceDB)

Source of truth. 8 tables: packages, modules, closures, chains, probabilities, belief_history, resources, resource_attachments.

Provides: CRUD, BM25 search, BP bulk load.

### GraphStore (Kuzu / Neo4j)

Graph topology. 5 node types (Closure, Chain, Module, Package, Resource). 6 relationship types (PREMISE, CONCLUSION, BELONGS_TO, IMPORTS, ATTACHED_TO).

Belief/probability latest values redundantly stored on node properties for traversal convenience.

Provisional — depends on Phase 3 graph-spec.md.

### VectorStore (LanceDB)

Embedding similarity search. Stores `(closure_id, version, embedding)`.

## StorageManager

Unified facade. Domain services only touch StorageManager, never individual backends.

### Three-Write Consistency

`ingest_package()` writes: LanceDB first (source of truth) → Neo4j → VectorStore. Mid-flight failure rolls back all prior steps.

### Degraded Mode

- Neo4j unavailable → graph queries return empty, topology search skipped
- VectorStore unavailable → vector search skipped
- LanceDB unavailable → system unavailable

### Other Write Paths

- `add_probability()` → LanceDB + sync Neo4j property
- `write_beliefs()` → LanceDB belief_history + sync Neo4j property

## Implementation Chunks (6 PRs)

### Chunk 1: Models + ABCs
- `models.py` — all Pydantic models
- ABCs: `content_store.py`, `graph_store.py`, `vector_store.py`
- `config.py`
- All fixture JSON files
- `test_models.py`

### Chunk 2: ContentStore (LanceDB)
- `lance_content_store.py` — 8 tables, CRUD, BM25, BP bulk load
- `test_lance_content.py`

### Chunk 3: GraphStore (Kuzu + Neo4j)
- `kuzu_graph_store.py`, `neo4j_graph_store.py`
- `test_graph_store.py` — parametrized

### Chunk 4: VectorStore
- `lance_vector_store.py`
- `test_vector_store.py`

### Chunk 5: StorageManager + Three-Write
- `manager.py` — facade, three-write, rollback, degraded mode
- `test_manager.py`, `test_three_write.py`

### Chunk 6: E2E + Seed Script
- `test_storage_v2_e2e.py`
- `scripts/seed_v2.py`, `scripts/smoke_test_v2.py`

## Test Framework

### Three Levels

**Unit tests** — each store implementation in isolation against real embedded backends (LanceDB `tmp_path`, Kuzu `tmp_path`). No mocks for storage. Neo4j auto-skipped if unavailable.

**Integration tests** — StorageManager as a whole. Ingest → read → search → BP load. Three-write consistency, rollback, degraded mode.

**E2E (non-test env)** — seed script + smoke test against live server with real backends.

### Fixture Strategy

All fixture data in `tests/fixtures/storage_v2/*.json`. No inline test data.

```python
# conftest.py pattern
def load_fixture(name: str) -> list[dict]:
    path = Path(__file__).parents[2] / "fixtures" / "storage_v2" / f"{name}.json"
    return json.loads(path.read_text())

@pytest.fixture
def closures() -> list[Closure]:
    return [Closure.model_validate(d) for d in load_fixture("closures")]
```

### Store Factory Fixtures

```python
@pytest.fixture
async def content_store(tmp_path) -> LanceContentStore:
    store = LanceContentStore(str(tmp_path / "lance"))
    await store.initialize()
    return store

@pytest.fixture(params=["kuzu", "neo4j"])
async def graph_store(request, tmp_path) -> GraphStore:
    if request.param == "neo4j":
        pytest.importorskip("neo4j")
        # connect or skip
    else:
        store = KuzuGraphStore(str(tmp_path / "kuzu"))
        await store.initialize_schema()
        return store
```

### Neo4j in Tests

Kuzu-only for local/CI by default. Neo4j tests auto-skip when unavailable. Same `GraphStore` ABC ensures interface parity.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Namespace | `libs/storage_v2/` | Build alongside old code, delete old when done |
| IDs | String (not int) | Align with Gaia Language naming: `package.module.name` |
| Fixtures | JSON files, not inline | Reusable across test levels, reviewable, versionable |
| Neo4j testing | Auto-skip pattern | Zero-config local dev, CI has service container |
| Chunk order | Models → Content → Graph → Vector → Manager → E2E | Each builds on previous, independently mergeable |
