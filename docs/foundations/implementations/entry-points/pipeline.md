# Batch Pipeline

> **Status:** Current canonical — target evolution noted

The batch pipeline (`scripts/pipeline/run_full_pipeline.py`) orchestrates end-to-end processing of multiple papers through 7 sequential stages. It is the primary path for seeding the knowledge graph at scale.

## 7 Stages

| # | Stage | Script | Purpose |
|---|-------|--------|---------|
| 1 | `xml-to-typst` | `scripts/paper_to_typst.py` | Convert paper XML to Typst packages (optional `--skip-llm`). **Known issue:** orchestrator path may be stale — see [#195](https://github.com/SiliconEinstein/Gaia/issues/195) |
| 2 | `build-graph-ir` | `scripts/pipeline/build_graph_ir.py` | Compile Typst packages to Raw Graph + Local Canonical Graph |
| 3 | `local-bp` | `scripts/pipeline/run_local_bp.py` | Run local belief propagation per package |
| 4 | `global-canon` | `scripts/pipeline/canonicalize_global.py` | Map local nodes to global canonical nodes (optional `--use-embedding`) |
| 5 | `persist` | `scripts/pipeline/persist_to_db.py` | Three-write to LanceDB + graph backend |
| 6 | `curation` | `scripts/pipeline/run_curation_db.py` | 6-step curation pipeline on global graph |
| 7 | `global-bp` | `scripts/pipeline/run_global_bp_db.py` | Run BP on the full global graph |

Each stage runs as a subprocess. If a stage fails, the pipeline halts immediately.

## Configuration

The pipeline reads defaults from TOML config files:

- `pipeline.toml` — base configuration (papers_dir, output_dir, concurrency, canonicalization settings)
- `pipeline.{env}.toml` — environment-specific override (loaded when `--env` or `GAIA_ENV` is set)

Config is deep-merged: environment file wins over base. The `[storage.env_mapping]` section copies environment variables (e.g., `TEST_GAIA_LANCEDB_URI` to `GAIA_LANCEDB_URI`).

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--env` | `GAIA_ENV` | Environment name (loads `pipeline.{env}.toml`) |
| `--papers-dir` | from config | Input paper directory |
| `--output-dir` | from config | Output directory for all artifacts |
| `--graph-backend` | from config | `kuzu`, `neo4j`, or `none` |
| `--use-embedding` | from config | Enable embedding-based similarity in global canonicalization |
| `--stage` | — | Run only this one stage |
| `--from-stage` | — | Resume from this stage onwards |
| `--concurrency` | from config | Parallelism for xml-to-typst stage |
| `--clean` | false | Drop all DB data before persist stage |

`--stage` and `--from-stage` are mutually exclusive.

## Directory Layout

The pipeline organizes outputs under `--output-dir`:

```
output/
  typst_packages/       # One subdirectory per paper (stages 1-3)
    paper_name/
      typst.toml
      *.typ
      .gaia/graph/      # Raw graph, local canonical graph
  global_graph/         # Global canonicalization output (stage 4)
  curation_report.json  # Curation results (stage 6)
  global_beliefs.json   # Global BP backup (stage 7)
```

## Code Paths

| Component | File |
|-----------|------|
| Orchestrator | `scripts/pipeline/run_full_pipeline.py` |
| Config loader | `run_full_pipeline.py:_load_config()` |
| Stage command builder | `run_full_pipeline.py:build_stage_command()` |
| Base config | `pipeline.toml` |

## Current State

Working for batch processing of ~5 papers. Stages execute as independent subprocesses coordinated by the orchestrator. The curation stage uses real LLM calls (via `libs/curation/abstraction.py`) and real embeddings (via `libs/embedding.DPEmbeddingModel`).

## Target State

This pipeline is temporary batch orchestration. The intended architecture replaces it with server-side jobs: ingest triggers review and canonicalization as async tasks, and curation runs as a scheduled background service. The pipeline will remain useful for initial data seeding and development.
