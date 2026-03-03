# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gaia is a Large Knowledge Model (LKM) for billion-scale reasoning over academic knowledge. It stores propositions as nodes and reasoning relationships as hyperedges in a hypergraph, with a Git-like commit workflow (submit → review → merge) and probabilistic inference via loopy belief propagation.

## Commands

### Install
```bash
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests                                          # all tests
pytest tests/libs/test_models.py                      # single file
pytest tests/libs/test_models.py::test_node_defaults  # single test
pytest -m "not neo4j" tests                           # skip Neo4j tests
pytest --cov=libs --cov=services tests                # with coverage
```

Neo4j tests are auto-skipped when Neo4j is unavailable (detected in `tests/conftest.py`). All async tests run automatically via `asyncio_mode = "auto"`.

### Lint & Format
```bash
ruff check .     # lint
ruff format .    # format
```

Style: 100-char line length, Python 3.12 target.

### Run Server
```bash
uvicorn services.gateway.app:create_app --reload --host 0.0.0.0 --port 8000
```

### Seed Database
```bash
python scripts/seed_database.py --fixtures-dir tests/fixtures --db-path /data/lancedb/gaia --neo4j-password testpassword
```

## Architecture

### Two-Package Monorepo

- **`libs/`** — Shared models and storage abstractions (no business logic)
- **`services/`** — Four service modules, each with its own engine

### Storage Layer (`libs/storage/`)

Three complementary backends managed by `StorageManager` (a thin container, no business logic):

| Backend | Store Class | Purpose |
|---------|------------|---------|
| **LanceDB** | `LanceStore` | Node content, metadata, BM25 full-text search |
| **Neo4j** | `Neo4jGraphStore` | Graph topology, hyperedge relationships (`:TAIL`/`:HEAD`) |
| **Vector** | `VectorSearchClient` (ABC) | Embedding similarity search; local impl uses LanceDB |

Neo4j is optional — the system degrades gracefully without it. Configuration lives in `libs/storage/config.py` (`StorageConfig`).

### Service Engines (`services/`)

| Engine | Path | Responsibility |
|--------|------|----------------|
| **CommitEngine** | `services/commit_engine/` | 3-step workflow: validate → LLM review (stub in Phase 1) → merge to storage |
| **SearchEngine** | `services/search_engine/` | Multi-path recall (vector + BM25 + topology) with score normalization and merging |
| **InferenceEngine** | `services/inference_engine/` | Loopy belief propagation on factor graphs extracted from Neo4j |
| **Gateway** | `services/gateway/` | FastAPI app factory, dependency injection (`deps.py`), route handlers |

### Core Data Models (`libs/models.py`)

- **Node** — A proposition with `content`, `prior`, `belief`, `keywords`, `type` (paper-extract, join, deduction, conjecture)
- **HyperEdge** — A reasoning link with `tail[]` → `head[]`, `probability`, `reasoning` steps, `type` (paper-extract, join, meet, contradiction, retraction)
- **Commit** — A batch of operations with status state machine: `pending_review` → `reviewed` → `merged` (or `rejected`)

### API Routes (`services/gateway/routes/`)

- **`commits.py`** — `POST /commits`, `GET /commits/{id}`, `POST /commits/{id}/review`, `POST /commits/{id}/merge`
- **`read.py`** — `GET /nodes/{id}`, `GET /hyperedges/{id}`, `GET /nodes/{id}/subgraph`
- **`search.py`** — `POST /search/nodes`, `POST /search/hyperedges`

### Dependency Injection

`services/gateway/deps.py` holds a global `Dependencies` singleton initialized during FastAPI startup. All engines receive `StorageManager` and are wired together there.

## Design Documents

Detailed design specs live in `docs/plans/` covering API design, storage layer, commit engine, search engine, inference engine, and gateway. The system-level design overview is at `docs/design/phase1_billion_scale.md`.
