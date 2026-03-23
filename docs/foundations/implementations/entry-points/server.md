# API Server

> **Status:** Current canonical — target evolution noted

The Gaia server (`services/gateway/`) is a FastAPI application providing HTTP access to published knowledge. It is read-heavy today; the only write path is bulk package ingest.

## Application Factory

`services/gateway/app.py` exports `create_app(dependencies=None)`:

- Loads `.env` in production; skips when test dependencies are injected
- Registers a lifespan handler that calls `Dependencies.initialize()` at startup and `Dependencies.cleanup()` at shutdown
- Adds CORS middleware (allows `localhost:5173` for the frontend dev server)
- Mounts the single `packages` router and a `/health` endpoint

Run with:

```bash
GAIA_LANCEDB_PATH=./data/lancedb/gaia \
  uvicorn services.gateway.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

## Dependency Injection

`services/gateway/deps.py` defines a `Dependencies` class holding a `StorageManager` singleton. A module-level `deps` instance is imported by route handlers. Tests inject custom dependencies via `create_app(dependencies=...)`, which propagates them to the global singleton.

## Route Groups

All routes live in `services/gateway/routes/packages.py`:

**Write**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/packages/ingest` | Ingest a complete package (knowledge, chains, modules, probabilities, beliefs, embeddings) |

**Read — Packages**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/packages` | List packages (paginated) |
| `GET` | `/packages/{id}` | Get single package |

**Read — Knowledge**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/knowledge` | List knowledge items (paginated, optional type filter) |
| `GET` | `/knowledge/{id}` | Get single knowledge item |
| `GET` | `/knowledge/{id}/versions` | Version history |
| `GET` | `/knowledge/{id}/beliefs` | Belief snapshot history |

**Read — Modules & Chains**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/modules` | List modules (optional package filter) |
| `GET` | `/modules/{id}` | Get single module |
| `GET` | `/modules/{id}/chains` | Chains in a module |
| `GET` | `/chains` | List chains (paginated, optional module filter) |
| `GET` | `/chains/{id}` | Get single chain |
| `GET` | `/chains/{id}/probabilities` | Probability history for a chain |

**Graph**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/graph` | Knowledge nodes + chain edges for DAG visualization (optional package filter) |

## Storage Initialization

At startup, `Dependencies.initialize()` creates a `StorageManager` from `StorageConfig` (reads `GAIA_LANCEDB_PATH`, `GAIA_NEO4J_URI`, etc. from environment). The `StorageManager` initializes content, graph, and vector stores. Route handlers call `_require_storage()` which returns the manager or raises HTTP 503 if not initialized.

## Code Paths

| Component | File |
|-----------|------|
| App factory | `services/gateway/app.py` |
| Dependencies | `services/gateway/deps.py` |
| Routes | `services/gateway/routes/packages.py` |
| Storage manager | `libs/storage/manager.py` |
| Storage config | `libs/storage/config.py` |

## Current State

The server is a read-heavy API with a single bulk-write endpoint (`/packages/ingest`). All data is ingested via `StorageManager.ingest_package()` with three-write atomicity (content, graph, vector). The frontend at `localhost:5173` consumes these endpoints for DAG visualization and knowledge browsing.

## Review Flow (Target Architecture)

> **Target design -- not yet implemented as described.**

The target write side replaces the single bulk-ingest endpoint with a **Review Service** that manages the full package lifecycle through four stages:

### 1. Validation

The server re-compiles the submitted package source independently (never trusting the client-side compilation). It diffs the re-compiled raw graph against the submitted `raw_graph.json`. Any mismatch is a blocking finding and the submission is rejected.

### 2. Canonicalization Audit

The `CanonicalizationAuditor` examines the submitted local canonical graph and its canonicalization log. It checks each `LocalCanonicalNode` grouping decision for correctness. Erroneous merges are blocking; missed merges are advisory.

### 3. Multiple Agent Review

Multiple independent review agents evaluate the package in parallel. Each agent assesses reasoning quality, dependency annotations, and logical validity, producing independent probability judgments. Agents do not see each other's reviews or the author's self-review probabilities. The combined output is a `PeerReviewReport`. Blocking findings trigger a rebuttal cycle (up to 5 rounds); if unresolved, the submission escalates to human review.

### 4. Gatekeeper

The gatekeeper synthesizes all review results into a final accept/reject decision:

- **GlobalMatcher** embeds each `LocalCanonicalNode`, searches the global graph, and decides `match_existing` or `create_new` for each -- producing a list of `CanonicalBinding` records.
- **Integrator** writes bindings, creates or updates `GlobalCanonicalNode` entries, writes `FactorNode` records to the global graph (remapping premises/conclusion to `global_canonical_id`), refreshes `GlobalInferenceState` from the review report, and marks the package `merged`.
- **BPService** is scheduled asynchronously to run belief propagation on the updated global graph.

### Service Choreography

The Review Service (internally called `IngestionService`) orchestrates six components:

| Component | Responsibility |
|-----------|---------------|
| `Compiler` | Re-compile package source (deterministic lowering) |
| `GraphVerifier` | Diff submitted raw graph against re-compiled result |
| `CanonicalizationAuditor` | Audit local canonical graph grouping decisions |
| `ReviewEngine` | Peer review: reasoning quality and probability judgments |
| `GlobalMatcher` | Search global graph, assign global identity per local node |
| `Integrator` | Write bindings, update global nodes and factors, refresh inference state |

Package status follows a state machine: `submitted` -> `validating` -> `auditing_canonicalization` -> `multi_agent_reviewing` -> `gatekeeper` -> `integrating` -> `merged` (or `rejected` / `needs_revision` at any blocking stage). External API status collapses to: `submitted`, `reviewing`, `integrating`, `merged`, `rejected`.

### Offline Maintenance

Two additional write-side services run offline after integration:

- **CurationService** -- graph structure maintenance: similar-conclusion clustering, contradiction discovery, structural inspection, cleanup.
- **BPService** -- runs global belief propagation on the cleaned graph, updating `GlobalInferenceState.node_beliefs` and writing `BeliefSnapshot` history.

Curation runs first (structure), then BP runs on the cleaned graph (inference).

## Target State

- **Write side:** Add server-side `ReviewService` (LLM review on ingest) and `CurationService` (background graph maintenance) as separate route groups or background workers.
- **Read side split:** Separate read routes into distinct routers (packages, knowledge, graph) for clearer ownership and independent scaling.
- Wire `gaia publish --server` to `POST /packages/ingest`.
