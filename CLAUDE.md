# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gaia is a Large Knowledge Model (LKM) — a billion-scale reasoning hypergraph for knowledge representation and inference. It stores propositions as nodes and reasoning relationships as hyperedges, with a Git-like commit workflow (submit → review → merge) and probabilistic inference via loopy belief propagation.

**Stack:** Python 3.12+, FastAPI, Pydantic v2, LanceDB, Neo4j, NumPy/PyArrow

## Common Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run all tests (auto-skips Neo4j tests if unavailable)
pytest

# Run tests with coverage
pytest --cov=libs --cov=services tests

# Run a single test file / single test
pytest tests/libs/storage/test_lance_store.py
pytest tests/libs/test_models.py::test_node_defaults

# Run only non-Neo4j tests
pytest -m "not neo4j"

# Lint and format
ruff check .
ruff format .

# Run the API server (Neo4j auth is disabled locally)
GAIA_LANCEDB_PATH=./data/lancedb/gaia \
  uvicorn services.gateway.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Seed databases with fixture data (run once after clone)
python scripts/seed_database.py --fixtures-dir tests/fixtures --db-path ./data/lancedb/gaia

# Run frontend dev server
cd frontend && npm install && npm run dev
```

All async tests run automatically via `asyncio_mode = "auto"`.

## Architecture

### Layer Structure

```
services/gateway/        → FastAPI HTTP API (routes, dependency injection)
    ↓ uses
services/search_engine/  → Multi-path recall (vector + BM25 + topology) + score merging
services/commit_engine/  → 3-step commit workflow (submit → review → merge)
services/inference_engine/→ Loopy belief propagation on factor graphs
    ↓ uses
libs/models.py           → Core Pydantic models (Node, HyperEdge, Commit, Operations)
libs/storage/            → Storage backends (LanceDB, Neo4j, Vector Index)
```

Dependencies flow downward only. `libs` has no service dependencies. Services depend on `libs` but not on each other (except gateway depends on all services).

### Storage Layer (`libs/storage/`)

Three complementary backends managed by `StorageManager`:

| Backend | Store Class | Purpose |
|---------|------------|---------|
| **LanceDB** | `LanceStore` | Node content, metadata, BM25 full-text search |
| **Neo4j** | `Neo4jGraphStore` | Graph topology, hyperedge relationships (`:TAIL`/`:HEAD`) |
| **Vector** | `VectorSearchClient` (ABC) | Embedding similarity search; local impl uses LanceDB |

Neo4j is optional — the system degrades gracefully without it. All writes go through triple-write in the commit engine merger: LanceDB nodes → Neo4j edges → Vector embeddings.

### Core Data Models (`libs/models.py`)

- **Node** — A proposition with `content`, `prior`, `belief`, `keywords`, `type` (paper-extract, abstraction, deduction, conjecture)
- **HyperEdge** — A reasoning link with `tail[]` → `head[]`, `probability`, `reasoning` steps, `type` (paper-extract, abstraction, induction, contradiction, retraction)
- **Commit** — A batch of operations with status state machine: `pending_review` → `reviewed` → `merged` (or `rejected`)

### Key Patterns

- **Fully async** — all I/O is `async def`, tests use `asyncio_mode = "auto"`
- **Dependency injection** — `services/gateway/deps.py` holds a global `Dependencies` singleton initialized at startup; tests inject custom instances via `create_app(dependencies=...)`
- **Graceful degradation** — Neo4j, vector search, and LLM review are all optional; topology recall is skipped when graph is unavailable
- **Commit workflow** — operations (AddEdge, ModifyNode, ModifyEdge) are validated, reviewed (stub LLM auto-approves in Phase 1), then merged to all backends
- **Search merging** — three recall paths run in parallel, scores are min-max normalized, weighted (vector=0.5, bm25=0.3, topology=0.2), deduped, and top-k filtered
- **ID generation** — file-based with asyncio lock (`libs/storage/id_generator.py`), single-process safe

### API Routes (`services/gateway/routes/`)

- **`commits.py`** — `POST /commits`, `GET /commits/{id}`, `POST /commits/{id}/review`, `POST /commits/{id}/merge`
- **`read.py`** — `GET /nodes/{id}`, `GET /hyperedges/{id}`, `GET /nodes/{id}/subgraph`
- **`search.py`** — `POST /search/nodes`, `POST /search/hyperedges`

### Dependency Injection

`services/gateway/deps.py` holds a global `Dependencies` singleton initialized during FastAPI startup. All engines receive `StorageManager` and are wired together there.

## Testing

- Tests live in `tests/` mirroring the source structure
- Neo4j tests (`tests/libs/storage/test_neo4j_store.py`) require a running Neo4j instance; CI provides one via service container
- E2E integration tests (`tests/integration/test_e2e.py`) run without Neo4j using `tmp_path` for ephemeral LanceDB
- Test fixtures in `tests/fixtures/` — note `embeddings.json` is git-ignored (large file)

## Code Style

- Ruff for linting/formatting, line length 100, target Python 3.12
- Type hints use PEP 604 union syntax (`X | None` not `Optional[X]`)
- Google-style docstrings
- Pydantic v2 API: `.model_dump()`, `.model_validate()`, `.model_validate_json()`

## Design Documents

Detailed design specs live in `docs/plans/` covering API design, storage layer, commit engine, search engine, inference engine, and gateway. The system-level design overview is at `docs/design/phase1_billion_scale.md`.
