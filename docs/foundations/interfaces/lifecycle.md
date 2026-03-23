# Lifecycle

> **Status:** Current canonical

Gaia has three nested lifecycles: the CLI lifecycle (local, single package), the LKM lifecycle (server-side, global graph), and the pipeline lifecycle (batch orchestration).

## 1. CLI Lifecycle (local, single package)

The local workflow for a single package:

```
author  ->  build  ->  [self-review]  ->  [graph-construction]  ->  infer  ->  publish
```

### `gaia build`

Deterministic lowering from Typst source to Graph IR.

- **Input**: package source (`.typ` files + `typst.toml`).
- **Output**: `.gaia/graph/raw_graph.json`, `.gaia/graph/local_canonical_graph.json`, `.gaia/graph/canonicalization_log.json`.
- **What it does**: validates package structure, extracts knowledge via `typst query`, compiles raw graph, builds singleton local canonical graph.
- **What it does NOT do**: no LLM calls, no search, no probability assignment.

### Agent skills (optional, recommended)

- **Self-review**: two-round LLM evaluation of reasoning quality. Produces candidate weak points and conditional priors as local sidecar artifacts.
- **Graph-construction**: inspects raw graph, clusters semantically similar nodes, produces refined local canonical graph and optional local parameterization.

If review discovers missing premises or references, the agent updates source and re-runs `gaia build`.

### `gaia infer`

Local belief propagation preview.

- **Input**: local canonical graph + local parameterization overlay.
- **Output**: local belief preview under `.gaia/infer/`.
- **What it does**: adapts local canonical graph to a `FactorGraph`, derives parameterization from local review sidecars, runs sum-product BP with damping.
- **Scope**: package-local only. Does not query or modify the global graph.

### `gaia publish`

Submission handoff from local to shared system.

- **Input**: source + raw graph + local canonical graph + canonicalization log.
- **Output**: package submission to registry (local LanceDB or remote server).
- **What it does**: converts local canonical graph + review output to storage models, ingests via `StorageManager`.
- **What it does NOT submit**: author-local parameterization, self-review priors, local belief previews.

## 2. LKM Lifecycle (server-side, after publish)

After a package is published, the server-side lifecycle takes over:

```
validate  ->  canonicalize  ->  review  ->  [rebuttal cycle]  ->  integrate  ->  curate  ->  global BP
```

### Validate

The review engine re-compiles the raw graph from submitted source. Any mismatch with the submitted `raw_graph.json` is a blocking finding.

### Canonicalize (global)

The review engine maps each `LocalCanonicalNode` to a `GlobalCanonicalNode`:
- Embed each local node and search the global graph for matches.
- For each local node: match to an existing global node or create a new one.
- Record one `CanonicalBinding` per local node after approval.

### Review

Independent peer review: reasoning quality, duplicate detection, missing references, conflict identification. Produces a peer review report with findings (blocking or advisory) and optional probability judgments.

### Rebuttal cycle

If blocking findings exist, the author may accept revisions or write rebuttals. The cycle repeats up to 5 rounds. Unresolved after 5 rounds escalates to human (`under_debate`).

> **Aspirational**: the full review -> rebuttal -> editor cycle is target architecture. Current implementation uses simplified automatic canonicalization at publish time.

### Integrate

Approved packages are merged into the global graph. `CanonicalBinding` records are finalized, `GlobalInferenceState` is updated.

### Curate

Offline graph maintenance by the `CurationService`:
- Similarity clustering (find near-duplicate global nodes).
- Contradiction discovery (detect conflicts across packages).
- Structure inspection (graph health checks).
- Cleanup (merge confirmed duplicates, remove stale entries).

### Global BP

The `BPService` runs sum-product BP on the global canonical graph with registry-managed `GlobalInferenceState`. Same algorithm as local BP, different scope and parameterization source.

## 3. Pipeline Lifecycle (batch orchestration)

Pipeline scripts (`scripts/pipeline/`) orchestrate the CLI lifecycle in batch:

```
xml-to-typst → build-graph-ir → local-bp → global-canon → persist → curation → global-bp
```

Used for seeding the knowledge base from existing papers. The pipeline does **not** call the CLI commands — it invokes stage scripts directly (`build_graph_ir.py`, `run_local_bp.py`, `persist_to_db.py`, etc.) via `run_full_pipeline.py`. See `docs/foundations/implementations/entry-points/pipeline.md` for the full 7-stage breakdown.

## Artifacts at Each Stage

| Stage | Key artifacts |
|---|---|
| Source | `.typ` files, `typst.toml`, `gaia-deps.yml` |
| Build | `raw_graph.json`, `local_canonical_graph.json`, `canonicalization_log.json` |
| Self-review | review sidecars (candidate weak points, conditional priors) |
| Infer | `local_parameterization.json`, belief preview |
| Publish | submission to registry (source + raw + local canonical + log) |
| Review | peer review report (findings + probability judgments) |
| Integrate | `CanonicalBinding` records, updated `GlobalCanonicalNode`s |
| Curate | clustering results, conflict reports, cleanup actions |
| Global BP | updated `GlobalInferenceState` (node beliefs) |

## Source

- `docs/foundations_archive/cli/command-lifecycle.md` -- CLI command contracts
- `docs/foundations_archive/review/publish-pipeline.md` -- review pipeline target architecture
- `docs/foundations/implementations/overview.md` -- end-to-end data flow
