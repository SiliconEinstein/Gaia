# StorageManager + Three-Write Design (Chunk 5/6)

## Goal

Implement `StorageManager` — a unified facade that coordinates all three storage backends (ContentStore, GraphStore, VectorStore) with three-write consistency and graceful degradation.

## Architecture

Single class in `libs/storage_v2/manager.py`. Domain services interact only with StorageManager, never individual backends.

```
StorageManager
├── content_store: LanceContentStore        (required)
├── graph_store: GraphStore | None           (optional — Kuzu or Neo4j)
└── vector_store: VectorStore | None         (optional)
```

## Initialization & Lifecycle

- Constructor takes `StorageConfig`, instantiates concrete stores based on config fields
- `async initialize()` — calls `content_store.initialize()` + `graph_store.initialize_schema()` (if present)
- `async close()` — calls `graph_store.close()` (if present)

## Three-Write: `ingest_package()`

Main write path. Accepts: `package`, `modules`, `closures`, `chains`, `embeddings: list[ClosureEmbedding] | None`.

Write order: **ContentStore → GraphStore → VectorStore**

Compensating rollback on failure:
- GraphStore fails → `content_store.delete_package(package_id)`
- VectorStore fails → `graph_store.delete_package(package_id)` + `content_store.delete_package(package_id)`

If a store is `None`, its step is skipped silently.

## Other Write Paths

Passthrough with optional graph sync:

- `add_probabilities(records: list[ProbabilityRecord])` → content_store.write_probabilities() + graph_store.update_probability() for each
- `write_beliefs(snapshots: list[BeliefSnapshot])` → content_store.write_belief_snapshots() + graph_store.update_beliefs()
- `write_resources(resources, attachments)` → content_store.write_resources() + graph_store.write_resource_links()

## Read Methods

Thin delegation — each method forwards to the appropriate store:

- `get_closure()`, `get_closure_versions()`, `get_package()`, `get_module()` → content_store
- `get_chains_by_module()`, `get_probability_history()`, `get_belief_history()` → content_store
- `get_resources_for()` → content_store
- `search_bm25()`, `list_closures()`, `list_chains()` → content_store
- `get_neighbors()`, `get_subgraph()`, `search_topology()` → graph_store (or empty results)
- `search_vector()` → vector_store (or empty list)

## Degraded Mode

- `content_store` is **required** — constructor raises `ValueError` if LanceDB path is invalid
- `graph_store` is `None` when `config.graph_backend == "none"` — topology queries return `Subgraph(closure_ids=set(), chain_ids=set())`; topology search returns `[]`
- `vector_store` is `None` when no vector config — vector search returns `[]`

## Embedding Generation

Not owned by StorageManager. Callers provide pre-computed embeddings via `Closure.embedding` field or `ClosureEmbedding` objects. StorageManager only forwards to VectorStore.

## Test Strategy

Two test files, both using real embedded backends (LanceDB + Kuzu in tmp_path):

### `test_manager.py`
- Init with all stores, init with graph=None, init with vector=None
- Read delegation (closure, package, module, chains, etc.)
- Degraded reads (graph=None returns empty Subgraph, vector=None returns [])

### `test_three_write.py`
- Successful ingest (all three stores populated)
- Ingest with graph=None (content + vector only)
- Ingest with vector=None (content + graph only)
- Rollback on graph failure (content cleaned up)
- Rollback on vector failure (content + graph cleaned up)
- Passthrough writes: probabilities, beliefs, resources

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rollback strategy | Compensating actions | Uses existing `delete_package()` methods, simple, fits single-process model |
| Embedding generation | External | StorageManager is pure storage coordinator, not a compute pipeline |
| Read methods | Thin delegation | No cross-store enrichment needed at this layer |
| Store optionality | graph + vector optional | Matches v1 graceful degradation pattern |
