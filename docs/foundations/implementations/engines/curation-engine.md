# Curation Engine

> **Status:** Current canonical — target evolution noted

The curation engine performs offline maintenance on the global knowledge graph: deduplicating nodes, discovering abstractions, detecting contradictions, and cleaning up structural issues. It lives in `libs/curation/` with orchestration in `scripts/pipeline/run_curation_db.py`.

## 6-Step Pipeline

The curation pipeline runs as stage 6 of the batch pipeline. It reads global nodes and factors from the database, processes them through six steps, and writes results back.

1. **Clustering** (`libs/curation/clustering.py`) — Groups similar nodes using embedding similarity (via `DPEmbeddingModel`). Excludes schema nodes and already-connected pairs. Threshold: 0.85.

2. **Deduplication** (`libs/curation/dedup.py`) — Identifies exact duplicates by content hash. Returns merge suggestions with target IDs and evidence.

3. **Abstraction** (`libs/curation/abstraction.py`) — Uses an LLM (`AbstractionAgent`) to analyze clusters and propose schema (abstraction) nodes. Creates new `kind: "schema"` global canonical nodes with `instantiation` factors linking them to instance nodes. Also detects contradiction candidates within clusters.

4. **Conflict Detection** (`libs/curation/conflict.py`) — Two-level conflict detection using BP diagnostics. Level 1 (`detect_conflicts_level1`) analyzes convergence diagnostics for oscillation and residual signals. Level 2 (`detect_conflicts_level2`) performs perturbation probing on flagged nodes.

5. **Structure Audit** (`libs/curation/structure.py`) — Inspects the global graph for structural issues: orphan nodes, dangling factor references, cycles, and other anomalies. Returns a report with errors, warnings, and info items.

6. **Cleanup** (`libs/curation/cleanup.py`) — Generates a cleanup plan from all suggestions and conflict candidates, categorizing them as auto-approve, needs-review, or discard. Executes approved operations (merges, deletions) with an audit log.

## Supporting Modules

| Module | Purpose |
|--------|---------|
| `models.py` | Data models: `SimilarityCluster`, `MergeSuggestion`, `ConflictCandidate`, `CleanupPlan` |
| `similarity.py` | Pairwise similarity computation |
| `operations.py` | Merge and delete operations on the node/factor graph |
| `audit.py` | `AuditLog` for tracking all curation decisions |
| `reviewer.py` | LLM-based review of merge/abstraction suggestions |
| `scheduler.py` | `run_curation()` entry point exported from `__init__.py` |
| `prompts/` | LLM prompt templates for abstraction and review |

## Orchestration

`scripts/pipeline/run_curation_db.py` is the standalone orchestrator:

1. Connects to storage via `StorageManager` (LanceDB + optional graph backend)
2. Loads all global canonical nodes and factors
3. Runs the 6 steps sequentially, accumulating suggestions and conflict candidates
4. Computes diff (added/removed nodes and factors)
5. Writes results back: deletes removed nodes/factors, upserts remaining/new ones
6. Saves a JSON report with per-step timing, counts, and details

CLI arguments: `--db-path`, `--graph-backend`, `--report-path`, `--llm-model`.

## Code Paths

| Component | File |
|-----------|------|
| Clustering | `libs/curation/clustering.py` |
| Deduplication | `libs/curation/dedup.py` |
| Abstraction agent | `libs/curation/abstraction.py` |
| Conflict detection | `libs/curation/conflict.py` |
| Structure audit | `libs/curation/structure.py` |
| Cleanup execution | `libs/curation/cleanup.py` |
| DB orchestrator | `scripts/pipeline/run_curation_db.py` |
| Embedding model | `libs/embedding.py:DPEmbeddingModel` |

## Current State

Working as a DB-native batch script. Uses real LLM calls (via `litellm`) for the abstraction step and real embeddings for clustering. Tested against a graph of ~5 papers. Writes curated results (new schema nodes, updated factors, removed duplicates) back to storage.

## Target State

- Move orchestration to a server-side `CurationService` that runs as a scheduled background job after package ingest.
- Add incremental curation (process only newly ingested packages rather than the full graph).
- Expose curation reports via the API for frontend visualization.
