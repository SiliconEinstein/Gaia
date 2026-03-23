# CLI Entry Point

> **Status:** Current canonical — target evolution noted

The Gaia CLI (`cli/main.py`) is a Typer application providing single-package interactive workflows: init, build, infer, publish, search, and clean.

## Commands

| Command | Description |
|---------|-------------|
| `gaia init <name>` | Scaffold a new Typst knowledge package with v4 DSL runtime |
| `gaia build [path]` | Load, compile, and canonicalize a Typst package |
| `gaia infer [path]` | Run mock review + local belief propagation on a built package |
| `gaia publish [path]` | Publish via `--git`, `--local` (LanceDB + Kuzu), or `--server` |
| `gaia search <query>` | BM25 full-text search over published knowledge in LanceDB |
| `gaia clean [path]` | Remove `.gaia/` build artifacts |

## Build Flow

`gaia build` runs the unified `pipeline_build()` from `libs/pipeline.py`:

```
typst_loader.load_typst_package_v4(pkg_path)
    → compile_v4_to_raw_graph(graph_data)
    → build_singleton_local_graph(raw_graph)
    → save artifacts to .gaia/graph/ and .gaia/build/
```

Output formats: `--format md` (default), `json`, `typst`, `all`. The optional `--proof-state` flag runs `libs/lang/proof_state.analyze_proof_state()` and writes a proof state report.

## Infer Flow

`gaia infer` chains three pipeline functions:

1. `pipeline_build()` — rebuild the package
2. `pipeline_review(build, mock=True)` — derive priors and factor params via `MockReviewClient`
3. `pipeline_infer(build, review)` — adapt graph to factor graph, run `BeliefPropagation`, output beliefs

Results are saved to `.gaia/infer/infer_result.json`.

## Publish --local Flow

`gaia publish --local` runs the full four-step pipeline:

1. `pipeline_build()` — load and compile
2. `pipeline_review(build, mock=True)` — mock review (LLM review not yet wired to CLI)
3. `pipeline_infer(build, review)` — local BP
4. `pipeline_publish(build, review, infer, db_path=...)` — convert Graph IR to storage models, three-write via `StorageManager` into LanceDB + Kuzu

The `--db-path` option (or `GAIA_LANCEDB_PATH` env var) controls the LanceDB location.

## Search

`gaia search` queries published knowledge via `LanceContentStore`:

- Primary: BM25 full-text search via LanceDB FTS index
- Fallback: SQL `LIKE` filter for CJK/unsegmented text
- `--id <knowledge_id>`: direct lookup with latest belief from `belief_history`

## Code Paths

| Function | File |
|----------|------|
| CLI app + commands | `cli/main.py` |
| Pipeline functions | `libs/pipeline.py` (`pipeline_build`, `pipeline_review`, `pipeline_infer`, `pipeline_publish`) |
| Typst loader | `libs/lang/typst_loader.py` |
| Graph IR compiler | `libs/graph_ir/typst_compiler.py` |
| Mock/LLM review | `cli/llm_client.py` |
| BP engine | `libs/inference/bp.py` |
| Storage manager | `libs/storage/manager.py` |

## Current State

All commands are working. `publish --server` is stubbed (exits with "not yet implemented"). Review always uses `MockReviewClient` in the CLI; real LLM review is only available via the pipeline scripts.

## Target State

- Add `gaia review` command that invokes real LLM review via `ReviewClient` and saves a review sidecar file.
- Wire `publish --server` to the gateway API's `POST /packages/ingest` endpoint.
