# API

> **Status:** Current canonical

This document describes the HTTP API exposed by the Gaia gateway server (`services/gateway/`). This is the internal gateway API, not a formal public contract. All endpoints are subject to change.

## Server

The gateway is a FastAPI application. Routes are defined in `services/gateway/routes/packages.py`. Dependency injection is managed via a global `Dependencies` singleton in `services/gateway/deps.py`, initialized at startup with a `StorageManager`.

## Endpoints

### Package Ingest

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/packages/ingest` | Ingest a complete package (package + modules + knowledge + chains + probabilities + beliefs + embeddings) | Stable |

Request body (`IngestRequest`):
```json
{
  "package": { ... },
  "modules": [ ... ],
  "knowledge": [ ... ],
  "chains": [ ... ],
  "probabilities": [],
  "beliefs": [],
  "embeddings": []
}
```

Response (`IngestResponse`): `{ package_id, status, knowledge_count, chain_count }`.

The ingest endpoint performs three-write atomicity: content store (source of truth), graph store (topology), and vector store (embeddings).

### Package Read

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/packages` | List all packages (paginated) | Stable |
| `GET` | `/packages/{package_id}` | Get a single package | Stable |

### Knowledge Read

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/knowledge` | List knowledge items (paginated, optional `type_filter`) | Stable |
| `GET` | `/knowledge/{knowledge_id}` | Get a single knowledge item | Stable |
| `GET` | `/knowledge/{knowledge_id}/versions` | Get all versions of a knowledge item | Stable |
| `GET` | `/knowledge/{knowledge_id}/beliefs` | Get belief history for a knowledge item | Stable |

### Module Read

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/modules` | List all modules (optional `package_id` filter) | Stable |
| `GET` | `/modules/{module_id}` | Get a single module | Stable |
| `GET` | `/modules/{module_id}/chains` | Get chains for a module | Stable |

### Chain Read

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/chains` | List chains (paginated, optional `module_id` filter) | Stable |
| `GET` | `/chains/{chain_id}` | Get a single chain | Stable |
| `GET` | `/chains/{chain_id}/probabilities` | Get probability history for a chain | Stable |

### Graph

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/graph` | Get knowledge nodes and chain edges for DAG visualization (optional `package_id` filter) | Stable |

## Authentication

No authentication is implemented. The gateway is intended for internal/development use.

## Error Handling

- `404` -- resource not found (package, knowledge, module, chain).
- `503` -- storage not initialized (startup failure or missing config).

## Not Yet Implemented

The following are described in the target server architecture (`docs/foundations_archive/server/architecture.md`) but not yet exposed as HTTP endpoints:

- **Search API** (`QueryService`) -- full-text and vector search for agents. Experimental.
- **Review submission** -- peer review engine integration. Target architecture.
- **Global BP trigger** -- run global belief propagation. Target architecture.
- **Curation endpoints** -- clustering, conflict discovery, graph maintenance. Target architecture.

## Source

- `services/gateway/routes/packages.py` -- route definitions
- `services/gateway/deps.py` -- dependency injection
- `services/gateway/app.py` -- FastAPI application factory
