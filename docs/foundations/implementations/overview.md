# Implementation Overview

> **Status:** Current canonical

This document describes the implemented architecture of Gaia as it exists in the codebase today. For product-level framing, see `docs/foundations_archive/system-overview.md`. For module boundaries and dependency flow, see `docs/module-map.md`.

## Layered Architecture

```
Entry Points
  CLI  (cli/)                    — gaia init/build/infer/publish/show/search/clean
  Server  (services/gateway/)    — FastAPI HTTP API
  Pipeline scripts  (scripts/)   — paper-to-typst, seed, migration

         ↓ call

Engines
  Graph IR Compiler  (libs/graph_ir/)    — Typst → Raw Graph → Local Canonical Graph
  BP Engine  (libs/inference/)           — Sum-product loopy belief propagation
  Canonicalization  (libs/global_graph/) — Local node → Global node mapping
  Review Pipeline  (services/review_pipeline/) — Operator pipeline for review scoring
  Curation  (services/curation/)         — Offline graph maintenance

         ↓ use

Storage
  LanceDB  (libs/storage/lance_content_store.py)  — Content + FTS + metadata
  Neo4j/Kuzu  (libs/storage/neo4j_graph_store.py, kuzu_graph_store.py)  — Graph topology
  LanceDB Vector  (libs/storage/lance_vector_store.py)  — Embedding similarity
```

Dependencies flow strictly downward. `libs/` has no service dependencies. The CLI and server are independent product surfaces sharing the same `libs/` layer.

## End-to-End Data Flow

The primary data path through the system:

```
1. Author Typst package (*.typ files + typst.toml)
       ↓
2. gaia build / typst_loader
   libs/lang/typst_loader.py  →  load_typst_package_v4()
       ↓
3. Graph IR Compiler
   libs/graph_ir/typst_compiler.py  →  compile_v4_to_raw_graph()
   libs/graph_ir/build_utils.py     →  build_singleton_local_graph()
       ↓  produces RawGraph + LocalCanonicalGraph + LocalParameterization
4. Local BP (gaia infer)
   libs/graph_ir/adapter.py  →  build factor graph from local canonical graph
   libs/inference/bp.py      →  run sum-product BP
       ↓  produces local belief preview
5. Global Canonicalization (server pipeline)
   libs/global_graph/canonicalize.py  →  map local nodes to global nodes
       ↓  produces CanonicalBindings + GlobalCanonicalNodes + global factors
6. Persist (StorageManager three-write)
   libs/storage/manager.py  →  content → graph → vector
       ↓
7. Curation (offline)
   services/curation/  →  similarity clustering, contradiction discovery
       ↓
8. Global BP (server)
   Same libs/inference/ engine on the global canonical graph
```

Steps 1-4 happen locally (CLI). Steps 5-8 happen on the server. The same BP engine (`libs/inference/`) is used for both local and global inference -- the only difference is graph scope and parameterization source.

## Code Locations

| Component | Path | Key entry points |
|-----------|------|------------------|
| **Typst loader** | `libs/lang/typst_loader.py` | `load_typst_package_v4()` |
| **Graph IR compiler** | `libs/graph_ir/typst_compiler.py` | `compile_v4_to_raw_graph()` |
| **Local canonicalization** | `libs/graph_ir/build_utils.py` | `build_singleton_local_graph()` |
| **Graph IR models** | `libs/graph_ir/models.py` | `RawGraph`, `LocalCanonicalGraph`, `FactorNode` |
| **BP adapter** | `libs/graph_ir/adapter.py` | Builds `FactorGraph` from Graph IR |
| **Factor graph** | `libs/inference/factor_graph.py` | `FactorGraph` class |
| **BP algorithm** | `libs/inference/bp.py` | `BeliefPropagation` class |
| **Global canonicalization** | `libs/global_graph/canonicalize.py` | `canonicalize_package()` |
| **Similarity matching** | `libs/global_graph/similarity.py` | `find_best_match()` |
| **Storage manager** | `libs/storage/manager.py` | `StorageManager` class |
| **Content store** | `libs/storage/lance_content_store.py` | `LanceContentStore` class |
| **Graph store** | `libs/storage/neo4j_graph_store.py` | `Neo4jGraphStore` class |
| **CLI commands** | `cli/` | Typer-based: init, build, infer, publish, etc. |
| **Server gateway** | `services/gateway/` | FastAPI app with route groups |
| **Pipeline scripts** | `scripts/` | paper-to-typst, seeding, migration |

## Key Architectural Decisions

**Graph IR as explicit layer.** The system does not compile factor graphs directly from authored source. Instead, Typst packages are compiled to a deterministic, auditable Graph IR (Raw Graph), then locally canonicalized, then optionally globally canonicalized. This separation keeps BP decoupled from the authoring surface.

**Structure vs. parameters separated.** Graph IR captures structural relationships (who supports whom). Priors, conditional probabilities, and beliefs live in separate overlay objects (`LocalParameterization`, `GlobalInferenceState`). This allows the same structure to be re-evaluated with different probability inputs.

**Three-write atomicity.** Package ingestion writes to content store (source of truth), graph store (topology), and vector store (embeddings) in sequence with a "preparing" to "committed" visibility gate. See `docs/foundations/implementations/storage.md`.

**Graceful degradation.** Graph and vector stores are optional. The system operates with content store alone, losing topology queries and vector search but retaining all core functionality.
