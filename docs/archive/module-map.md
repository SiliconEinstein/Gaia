# Gaia Module Map

This document describes the current module structure in the repository. It is the best starting point if you want to understand how the codebase is organized today.

For historical planning documents, see [archive/plans/README.md](archive/plans/README.md). For a higher-level assessment of the current structure and where it should be cleaned up next, see [architecture-rebaseline.md](architecture-rebaseline.md).

## Top-Level Layout

| Path | Role | Notes |
|------|------|-------|
| `libs/` | Shared library layer | Data models, language runtime, inference, embeddings, storage adapters, vector search abstraction |
| `cli/` | Gaia CLI | Typer-based commands: init, build, review, infer, publish, show, search, clean |
| `services/` | Runtime backend modules | Commit, search, review pipeline, job manager, FastAPI gateway |
| `frontend/` | React dashboard | Browsing, search, graph exploration, commit flows |
| `scripts/` | One-off operational scripts | Seeding, migration, data extraction |
| `tests/` | Test suite | Mirrors `libs/` and `services/`, plus integration coverage |
| `docs/` | Documentation | Current module map, design references, examples, archived plans |
| `.claude/skills/` | Local Codex skills | Workflow helpers for this repo |

## Backend Module Boundaries

### `libs/`

`libs/` is the shared foundation layer. It should stay small and reusable.

| Module | Responsibility |
|--------|----------------|
| `libs/models.py` | Shared Pydantic models for nodes, hyperedges, commits, and API payloads |
| `libs/embedding.py` | Embedding model interface and local stub implementation |
| `libs/storage/config.py` | Storage configuration |
| `libs/storage/manager.py` | Composition root for storage backends |
| `libs/storage/lance_store.py` | Node and metadata persistence in LanceDB |
| `libs/storage/neo4j_store.py` | Graph topology persistence in Neo4j |
| `libs/storage/kuzu_store.py` | Graph topology persistence in Kuzu (local default) |
| `libs/storage/vector_search/` | Vector search abstraction and LanceDB-backed implementation |
| `libs/storage/id_generator.py` | ID allocation |
| `libs/lang/` | Gaia Language: models, loader, resolver, elaborator, compiler, runtime |
| `libs/graph_ir/` | Graph IR lowering, local canonicalization artifacts, parameterization, and factor-graph adaptation |
| `libs/inference/` | Factor graph construction and loopy belief propagation |

`libs/` should not accumulate workflow-heavy logic. If a module coordinates search, review, inference, or commit workflows, it belongs in `services/`.

### `services/`

`services/` contains backend modules with application logic.

| Module | Responsibility | Main dependencies |
|--------|----------------|-------------------|
| `services/search_engine/` | Multi-path node and edge search | `libs/storage`, `libs/embedding` |
| `services/commit_engine/` | Submit, validate, review, and merge commit workflow | `libs/storage`, `services/search_engine`, `services/review_pipeline`, `services/job_manager` |
| `libs/inference/` | Factor graph construction and loopy belief propagation | Pure library, no service dependencies |
| `services/review_pipeline/` | Operator pipeline for embeddings, NN search, join, verify, and BP scoring | `libs/storage`, `libs/embedding` |
| `services/job_manager/` | Async job tracking used by review and batch APIs | internal service dependency |
| `services/gateway/` | FastAPI app, dependency wiring, and HTTP routes | all service modules |

### `cli/`

The Gaia CLI is a Typer-based command-line tool for the local knowledge-authoring workflow.

| Command | Responsibility |
|---------|----------------|
| `init` | Scaffold a new knowledge package (package.yaml + starter module) |
| `build` | Parse language source, resolve refs, lower Graph IR → `graph_ir/` artifacts |
| `review` | Current shipped compatibility helper for local self-review sidecars in `.gaia/reviews/` |
| `infer` | Derive local parameterization from local Graph IR + local review sidecars, run loopy BP → local belief preview |
| `publish` | Triple-write to LanceDB + Kuzu (--local) or git commit (--git). Server mode deferred. |
| `show` | Inspect a declaration and its connected chains |
| `search` | Full-text search over published nodes in local LanceDB |
| `clean` | Remove build artifacts (.gaia/) |

CLI source lives in `cli/`, with language parsing in `libs/lang/`, Graph IR handling in `libs/graph_ir/`, and BP in `libs/inference/`. Build output includes Graph IR artifacts under `graph_ir/` (raw graph, local canonical graph, canonicalization log, local parameterization); the shipped `review` command writes local self-review sidecars under `.gaia/reviews/`.

### `services/gateway/routes/`

The gateway has five route groups:

| File | Scope |
|------|-------|
| `routes/commits.py` | commit CRUD, review, merge |
| `routes/read.py` | nodes, hyperedges, subgraphs, contradictions, stats |
| `routes/search.py` | node and hyperedge search |
| `routes/batch.py` | batch commit, read, subgraph, and search jobs |
| `routes/jobs.py` | job status and result retrieval |

## Frontend Structure

`frontend/src/` is currently organized by UI surface rather than by backend service:

| Path | Responsibility |
|------|----------------|
| `api/` | HTTP clients and request/response types |
| `pages/` | route-level pages such as dashboard, browser, graph explorer, node, edge, and commit panel |
| `components/browser/` | table and filtering UI for browsing |
| `components/graph/` | graph canvas, legend, controls, popup, subgraph loading |
| `components/commit/` | commit detail and commit creation UI |
| `components/layout/` | app shell and sidebar |
| `components/shared/` | shared rendering helpers |
| `hooks/` | React Query and page-level data hooks |
| `lib/` | graph transforms and rendering helpers |

## Dependency Flow

The current intended dependency direction is:

```text
libs/models + libs/storage + libs/embedding + libs/inference + libs/lang
    -> services/search_engine
    -> services/review_pipeline
    -> services/commit_engine
    -> services/gateway          (HTTP product surface)

libs/models + libs/storage + libs/graph_ir + libs/inference + libs/lang
    -> cli/                      (CLI product surface)

frontend -> services/gateway
scripts -> libs/ and services/ as needed
tests -> mirror all layers
```

The gateway and CLI are independent product surfaces. Both depend on `libs/` but not on each other. The gateway additionally uses `services/` for commit, search, and review workflows. The CLI uses `libs/lang/` for language parsing and `libs/inference/` for belief propagation directly.

## What Was Unclear Or Conflicting

These are the main documentation and structure mismatches visible today:

1. The repository `README.md` described the system at a high level, but it did not map the real module boundaries. `review_pipeline`, `job_manager`, batch APIs, and job APIs were effectively hidden.
2. `docs/plans/README.md` (now `docs/archive/plans/README.md`) mixed active and historical language. Several documents were labeled as active even though the codebase has already moved past them.
3. The repo had no single "current architecture" document. Readers had to infer structure from source layout plus old planning docs.
4. `docs/plans/` and `docs/design/` serve different purposes, but that distinction was not stated clearly.
5. Storage terminology is slightly ahead of implementation. The config still contains production-oriented ByteHouse fields, while the current code path is primarily LanceDB + Neo4j + vector search.

## Improvement Priorities

The most useful next cleanup steps are:

1. Add short README files inside major service modules such as `services/commit_engine/`, `services/review_pipeline/`, and `services/gateway/` so the module boundaries are documented where people work.
2. Decide whether `review_pipeline` is a stable top-level service or a private dependency of `commit_engine`. Right now it behaves like a first-class backend module but is barely documented outside the code.
3. Clarify the intended production storage story. The code exposes ByteHouse-related config, but the current repo structure centers on LanceDB, Neo4j, and the local vector search abstraction.
4. Historical plans are now archived in `docs/archive/plans/`. Current operational guidance belongs in `README.md`, `docs/README.md`, or per-module READMEs.
5. Consider a small naming pass across docs so "node", "proposition", and "claim" are used more consistently where they refer to the same domain object.
