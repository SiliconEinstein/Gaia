# Storage

> **Status:** Current canonical

This document describes the storage layer as implemented. For the original design rationale, see `docs/foundations_archive/server/storage-schema.md`.

## Three Backends

The storage layer uses three complementary backends, all managed by `StorageManager` (`libs/storage/manager.py`):

| Backend | Class | Purpose | Required? |
|---------|-------|---------|-----------|
| **LanceDB Content** | `LanceContentStore` | All entity persistence, BM25 full-text search | Yes (source of truth) |
| **Neo4j / Kuzu Graph** | `Neo4jGraphStore` / `KuzuGraphStore` | Graph topology for traversal queries | Optional |
| **LanceDB Vector** | `LanceVectorStore` | Embedding similarity search | Optional |

The content store is always required and serves as the source of truth. Graph and vector stores are optional -- the system degrades gracefully without them, losing topology traversal and vector search respectively.

### Backend Selection

Configured via `StorageConfig` (`libs/storage/config.py`):

- **LanceDB**: Local path or remote S3/TOS URI. Remote mode uses `storage_options` with TOS access keys.
- **Graph backend**: `"kuzu"` (embedded, local default), `"neo4j"` (server), or `"none"`.
- **Vector store**: Always created alongside the content store (same LanceDB connection, separate table).

See `libs/storage/manager.py:StorageManager.initialize()`.

## StorageManager

`StorageManager` is the unified facade. Domain services interact only with this class, never with individual stores directly.

Key responsibilities:

- **Initialization**: Instantiates and connects all configured stores.
- **Three-write atomicity**: Coordinates multi-store writes with visibility gating.
- **Read delegation**: Passes reads through to the appropriate store, with visibility filtering for graph queries.
- **Graceful degradation**: Returns empty results when optional stores are unavailable.

## Three-Write Atomicity

See `libs/storage/manager.py:StorageManager.ingest_package()`.

Package ingestion follows a four-step protocol:

```
1. Write package with status="preparing"  (invisible to reads)
2. Write to ContentStore:  package, modules, knowledge, chains, factors, submission_artifact
3. Write to GraphStore:    topology (knowledge→chain relationships), factor topology
4. Write to VectorStore:   embeddings
5. Flip status to "merged"  (visible to reads)
```

On failure, data stays in "preparing" status -- invisible to readers and safe to retry. The content store is always written first as the source of truth.

## LanceDB Tables

All tables are defined as PyArrow schemas in `libs/storage/lance_content_store.py`:

### Core entity tables

| Table | Key | Purpose |
|-------|-----|---------|
| `packages` | `(package_id, version)` | Package metadata, status, modules list |
| `modules` | `module_id` | Module metadata, chain_ids, export_ids |
| `knowledge` | `(knowledge_id, version)` | Versioned propositions with type, content, prior, keywords |
| `chains` | `chain_id` | Reasoning chains with typed steps (premises -> conclusion) |

### Inference tables

| Table | Key | Purpose |
|-------|-----|---------|
| `probabilities` | `(chain_id, step_index)` | Step reliability scores from various sources |
| `belief_history` | `(knowledge_id, version, bp_run_id)` | BP result snapshots over time |

### Graph IR tables

| Table | Key | Purpose |
|-------|-----|---------|
| `factors` | `factor_id` | Persistent factors from Graph IR compilation |
| `canonical_bindings` | `(package, version, local_canonical_id)` | Local-to-global node mappings |
| `global_canonical_nodes` | `global_canonical_id` | Deduplicated cross-package knowledge identities |
| `global_inference_state` | singleton `_id` | Registry-managed global BP state (priors, beliefs, factor params) |

### Resource tables

| Table | Key | Purpose |
|-------|-----|---------|
| `resources` | `resource_id` | Resource metadata (images, code, datasets) |
| `resource_attachments` | `(resource_id, target_id)` | Many-to-many links to knowledge/chains/modules |
| `submission_artifacts` | `(package_name, commit_hash)` | Immutable snapshots for audit |

## Core Data Models

Defined in `libs/storage/models.py`:

- **`Knowledge`**: Versioned proposition with `(knowledge_id, version)` identity. Types: `claim`, `question`, `setting`, `action`, `contradiction`, `equivalence`. Prior is constrained to `(0, 1]`.
- **`Chain`**: Reasoning link with `steps: list[ChainStep]`. Each step has `premises: list[KnowledgeRef]`, `reasoning: str`, `conclusion: KnowledgeRef`. Types: `deduction`, `induction`, `abstraction`, `contradiction`, `retraction`, `equivalence`.
- **`Module`**: Groups knowledge and chains within a package. Roles: `reasoning`, `setting`, `motivation`, `follow_up_question`, `other`.
- **`Package`**: Top-level container, keyed by `(package_id, version)`. Status lifecycle: `preparing` -> `submitted` -> `merged` | `rejected`.
- **`FactorNode`**: Persistent factor with `type`, `premises[]`, `contexts[]`, `conclusion`. Types: `infer`, `instantiation`, `abstraction`, `contradiction`, `equivalence`.
- **`GlobalCanonicalNode`**: Cross-package dedup identity with `member_local_nodes[]` and `provenance[]`.
- **`CanonicalBinding`**: Maps `(package, version, local_canonical_id)` to `global_canonical_id` with decision audit trail.
- **`GlobalInferenceState`**: Singleton holding `node_priors`, `factor_parameters`, and `node_beliefs` for the global graph.

## Graph Store Topology

The graph store (Neo4j or Kuzu) maintains topology for traversal queries:

- Knowledge nodes keyed by composite `knowledge_id@version`
- `:PREMISE` and `:CONCLUSION` relationships from chains
- Factor topology links
- Global canonical node topology and bindings

The graph store is always secondary to the content store. It is populated during the three-write protocol and can be rebuilt from content store data.

## Complete Schema Reference

Field-level definitions for all core models, verified against `libs/storage/models.py`.

### Knowledge

| Field | Type | Description |
|-------|------|-------------|
| `knowledge_id` | `str` | Globally unique identifier |
| `version` | `int` | Explicit version number; `(knowledge_id, version)` is the composite key |
| `type` | `Literal["claim", "question", "setting", "action", "contradiction", "equivalence"]` | Root declaration type |
| `kind` | `str \| None` | Root-type-specific subtype label (e.g., `observation` for a claim, `python` for an action) |
| `content` | `str` | Proposition text |
| `parameters` | `list[Parameter]` | Empty = ground node; non-empty = schema node (universally quantified) |
| `prior` | `float` | Reviewed prior in `(0, 1]`; historical/provenance reference at the package level |
| `keywords` | `list[str]` | Search keywords |
| `source_package_id` | `str` | Package that created this version |
| `source_package_version` | `str` | Semver of the source package (default `"0.1.0"`) |
| `source_module_id` | `str` | Module within the source package |
| `created_at` | `datetime` | Creation timestamp |
| `embedding` | `list[float] \| None` | Optional embedding vector |

Derived property: `is_schema` = `len(parameters) > 0`.

`Parameter` has two fields: `name: str` (placeholder name, e.g. `"A"`) and `constraint: str` (constraint description).

### FactorNode

| Field | Type | Description |
|-------|------|-------------|
| `factor_id` | `str` | Unique factor identifier |
| `type` | `Literal["infer", "instantiation", "abstraction", "contradiction", "equivalence"]` | Factor type (code uses `infer` where archive design says `reasoning`) |
| `premises` | `list[str]` | Knowledge node IDs -- direct dependencies, create BP edges |
| `contexts` | `list[str]` | Knowledge node IDs -- indirect dependencies, do NOT create BP edges |
| `conclusion` | `str \| None` | Single knowledge node ID; `None` for constraint factors |
| `package_id` | `str` | Owning package |
| `source_ref` | `SourceRef \| None` | Traceability back to authoring layer |
| `metadata` | `dict \| None` | Arbitrary metadata |

Derived properties: `is_constraint` = type in `{contradiction, equivalence}`; `bp_participant_ids` = premises only for constraint factors, premises + conclusion otherwise.

`SourceRef` fields: `package: str`, `version: str`, `module: str`, `knowledge_name: str`.

### CanonicalBinding

| Field | Type | Description |
|-------|------|-------------|
| `package` | `str` | Source package name |
| `version` | `str` | Source package version |
| `local_graph_hash` | `str` | Hash of the local graph at binding time |
| `local_canonical_id` | `str` | Local canonical node ID within the package |
| `decision` | `Literal["match_existing", "create_new"]` | How the global identity was assigned |
| `global_canonical_id` | `str` | Registry-assigned global identity |
| `decided_at` | `datetime` | When the decision was made |
| `decided_by` | `str` | Who/what made the decision |
| `reason` | `str \| None` | Optional justification |

### GlobalCanonicalNode

| Field | Type | Description |
|-------|------|-------------|
| `global_canonical_id` | `str` | Registry-assigned opaque ID (e.g., `gcn_<ULID>`) |
| `knowledge_type` | `str` | Root type of the knowledge concept |
| `kind` | `str \| None` | Subtype label |
| `representative_content` | `str` | Representative text for display and search |
| `parameters` | `list[Parameter]` | Schema parameters (empty for ground nodes) |
| `member_local_nodes` | `list[LocalCanonicalRef]` | All local nodes bound to this global identity |
| `provenance` | `list[PackageRef]` | Packages that contributed to this node |
| `metadata` | `dict \| None` | Arbitrary metadata |

Supporting types: `LocalCanonicalRef` = `(package, version, local_canonical_id)`; `PackageRef` = `(package, version)`.

### GlobalInferenceState

| Field | Type | Description |
|-------|------|-------------|
| `graph_hash` | `str` | Hash of the global graph structure at update time |
| `node_priors` | `dict[str, float]` | Priors keyed by `global_canonical_id` |
| `factor_parameters` | `dict[str, FactorParams]` | Runtime factor params keyed by `factor_id` |
| `node_beliefs` | `dict[str, float]` | BP-computed beliefs keyed by `global_canonical_id` |
| `updated_at` | `datetime` | Last update timestamp |

`FactorParams` has one field: `conditional_probability: float`.

Probability and structure are strictly separated: Graph IR stores only structure; `GlobalInferenceState` stores all runtime parameters. It is a registry-managed singleton, not a package artifact.

## Current State

The storage layer is working in production with remote LanceDB (S3/TOS) and Neo4j. Local development uses embedded LanceDB and optionally Kuzu. BM25 full-text search is available via LanceDB's built-in FTS indexing. The three-write protocol is exercised by both the CLI publish path and the server ingestion pipeline.

## Target State

The storage layer is stable. No major schema changes are planned. The `global_inference_state` table was recently added to support server-side global BP and may see minor field additions as the inference pipeline matures.
