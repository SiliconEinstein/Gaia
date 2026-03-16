# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gaia is a Large Knowledge Model (LKM) — a billion-scale reasoning hypergraph for knowledge representation and inference. It stores knowledge as propositions and reasoning relationships via Graph IR (factor graphs), with a publish pipeline (build → canonicalize → publish → review → integrate) and probabilistic inference via loopy belief propagation.

**Stack:** Python 3.12+, FastAPI, Pydantic v2, LanceDB, Neo4j/Kuzu, NumPy/PyArrow

## Common Commands

```bash
# Install dependencies (always use uv, never pip)
uv sync

# Run all tests (auto-skips Neo4j tests if unavailable)
pytest

# Run tests with coverage
pytest --cov=libs --cov=services tests

# Run a single test file / single test
pytest tests/libs/storage/test_lance_content.py
pytest tests/libs/storage/test_models.py::test_knowledge_defaults

# Lint and format
ruff check .
ruff format .

# Run the API server
GAIA_LANCEDB_PATH=./data/lancedb/gaia \
  uvicorn services.gateway.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Run frontend dev server
cd frontend && npm install && npm run dev
```

All async tests run automatically via `asyncio_mode = "auto"`.

## Architecture

### Layer Structure

```
services/gateway/        → FastAPI HTTP API (routes, dependency injection)
    ↓ uses
libs/storage/            → Storage backends (LanceDB content, Neo4j/Kuzu graph, LanceDB vector)
libs/storage/models.py   → Core Pydantic models (Knowledge, Chain, Module, Package, etc.)
libs/inference/          → BP algorithm (factor graph, belief propagation)
libs/lang/               → Gaia Language compiler and runtime
```

Dependencies flow downward only. `libs` has no service dependencies.

### Storage Layer (`libs/storage/`)

Three complementary backends managed by `StorageManager`:

| Backend | Store Class | Purpose |
|---------|------------|---------|
| **LanceDB** | `LanceContentStore` | Knowledge content, metadata, BM25 full-text search |
| **Neo4j/Kuzu** | `Neo4jGraphStore` / `KuzuGraphStore` | Graph topology (Knowledge→Chain relationships via `:PREMISE`/`:CONCLUSION`) |
| **Vector** | `LanceVectorStore` | Embedding similarity search |

Graph backend is optional — the system degrades gracefully without it. All writes go through three-write in `StorageManager.ingest_package()`: Content → Graph → Vector.

### Core Data Models (`libs/storage/models.py`)

- **Knowledge** — A proposition with `content`, `prior`, `type` (claim/question/setting/action), `keywords`, versioned by `(knowledge_id, version)`
- **Chain** — A reasoning link with `steps[]` (each step has `premises[]` → `conclusion`), `type` (deduction/induction/abstraction/contradiction/retraction)
- **Module** — Groups knowledge + chains within a package
- **Package** — A complete knowledge container (git repo)
- **ProbabilityRecord** — Per-step probability with source tracking
- **BeliefSnapshot** — BP result history

### Key Patterns

- **Fully async** — all I/O is `async def`, tests use `asyncio_mode = "auto"`
- **Dependency injection** — `services/gateway/deps.py` holds a global `Dependencies` singleton initialized at startup; tests inject custom instances via `create_app(dependencies=...)`
- **Graceful degradation** — Graph and vector stores are optional
- **Three-write atomicity** — `ingest_package()` writes Content (source of truth) → Graph → Vector with "preparing" → "committed" visibility gating
- **Versioned identity** — Knowledge keyed by `(knowledge_id, version)`, graph nodes use composite `knowledge_id@version`

### API Routes (`services/gateway/routes/`)

- **`packages.py`** — `POST /packages/ingest`, `GET /packages/{id}`, `GET /knowledge/{id}`, `GET /knowledge/{id}/versions`, `GET /knowledge/{id}/beliefs`, `GET /modules/{id}`, `GET /modules/{id}/chains`, `GET /chains/{id}/probabilities`

### Dependency Injection

`services/gateway/deps.py` holds a global `Dependencies` singleton initialized during FastAPI startup with a `StorageManager`.

## Testing

- Tests live in `tests/` mirroring the source structure
- Neo4j tests require a running Neo4j instance; CI provides one via service container
- E2E integration tests in `tests/integration/` exercise HTTP endpoints with real storage
- Test fixtures in `tests/fixtures/storage/` — paper fixtures for package ingest testing

## Code Style

- Ruff for linting/formatting, line length 100, target Python 3.12
- Type hints use PEP 604 union syntax (`X | None` not `Optional[X]`)
- Google-style docstrings
- Pydantic v2 API: `.model_dump()`, `.model_validate()`, `.model_validate_json()`

## Worktrees

Worktrees live in `.worktrees/` (gitignored). Create new worktrees there:

```bash
git worktree add .worktrees/<name> -b feature/<name>
```

## Workflow

每项工作完成后，**必须**提交 PR 到 main。流程：

1. 完成开发并确认测试通过
2. 运行 ruff lint 和 format 检查：
   ```bash
   ruff check .
   ruff format --check .
   ```
3. 修复所有 lint/format 错误
4. 提交 commit，push 分支，创建 PR
5. 创建 PR 后，**必须**用 `gh run list` 检查 CI 是否通过，若失败则查看日志修复：
   ```bash
   gh run list --branch <branch> --limit 1
   gh run view <run-id> --log-failed
   ```

## Design Documents

Current specs live in `docs/foundations/` (product scope, system overview, domain model, language spec, CLI, server architecture, storage schema). Historical design and planning docs are archived in `docs/archive/`.
