# Gaia

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/SiliconEinstein/Gaia/graph/badge.svg)](https://codecov.io/gh/SiliconEinstein/Gaia)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Large Knowledge Model (LKM) — a reasoning hypergraph for knowledge representation and probabilistic inference.

Gaia packages knowledge as **Typst documents** with typed declarations (claims, settings, questions, actions, relations). The compiler extracts a **factor graph** (Graph IR), a review step assigns priors and parameters, and **loopy belief propagation** computes posterior beliefs.

## Quick Start

```bash
# Install (requires Python 3.12+, uv)
uv sync

# Create a new knowledge package
gaia init my_package && cd my_package

# Build — compile Typst → Graph IR, generate markdown and proof state
gaia build --proof-state

# Run all tests
pytest
```

## Authoring a Package

A Gaia package is a Typst project:

```
my_package/
  typst.toml          # package manifest (name, version, entrypoint)
  lib.typ             # entry: imports runtime, includes module files
  gaia.typ            # runtime import shim
  motivation.typ      # module — questions that motivate the work
  reasoning.typ       # module — claims with proofs
  gaia-deps.yml       # (optional) cross-package references
```

Declarations use five functions — each produces a labeled, extractable figure:

```typst
#import "gaia.typ": *
#show: gaia-style

#setting[The universe is spatially flat.] <setting.flat_universe>

#claim(kind: "observation")[
  Type Ia supernovae show accelerating expansion.
] <observation.sn_data>

#claim(from: (<observation.sn_data>, <setting.flat_universe>))[
  Dark energy accounts for ~68% of total energy density.
][
  Given SN data @observation.sn_data and flatness @setting.flat_universe,
  the energy budget requires a dark energy component.
] <reasoning.dark_energy>

#relation(type: "contradiction", between: (<reasoning.dark_energy>, <other.qft_prediction>))[
  The observed value differs from QFT predictions by ~120 orders of magnitude.
] <reasoning.vacuum_catastrophe>
```

Labels follow `<filename.name>` convention. `from:` declares premises (reasoning edges). `between:` declares structural constraints. See [language spec](docs/foundations/language/gaia-language-spec.md) for the full reference.

## Pipeline

```
gaia build                Typst → load → compile → canonicalize → Graph IR
gaia build --proof-state                          → proof state report
gaia infer                mock review → local parameterization → BP → beliefs
gaia publish --local      → storage (LanceDB + graph DB)
```

### Proof State

Every node is classified after compilation:

| Category | Meaning |
|----------|---------|
| **established** | Has proof (conclusion of a reasoning factor or relation) |
| **assumption** | Setting — contextual choice, no proof needed, but challengeable |
| **hole** | Used as premise but has no proof in this package, including observations without experimental justification |
| **imported** | External reference (from another package via `gaia-deps.yml`) |
| **question** | Open inquiry |
| **standalone** | Declared but unreferenced and unproven |

Gaia does not currently expose an `axiom` proof-state bucket or API key. If future inference or explanation tooling needs multiple alternative starting-point sets, those will be modeled as explicit `assumption basis` / proof-view metadata layered on top of the same graph, not as a node-level type.

## Architecture

```
cli/                 → gaia CLI (build, init, publish, search, clean)
libs/lang/           → Typst DSL loader, compiler, proof state analysis
libs/graph_ir/       → Graph IR: RawGraph → LocalCanonicalGraph → factors
libs/inference/      → Belief propagation on factor graphs
libs/storage/        → Storage backends (LanceDB, Neo4j/Kuzu, vector)
libs/typst/          → Typst runtime library (gaia-lang-v4/)
libs/pipeline.py     → Unified pipeline: build → review → infer → publish
services/gateway/    → FastAPI HTTP API
frontend/            → React dashboard
```

### Storage

| Backend | Purpose |
|---------|---------|
| **LanceDB** | Knowledge content, metadata, BM25 full-text search |
| **Neo4j / Kuzu** | Graph topology (Knowledge → Chain via :PREMISE/:CONCLUSION) |
| **Vector Index** | Embedding similarity search |

## Documentation

| Path | Content |
|------|---------|
| [docs/foundations/language/](docs/foundations/language/) | Language spec, design, design rationale |
| [docs/foundations/](docs/foundations/) | Domain model, Graph IR, BP theory, storage schema |
| [docs/superpowers/specs/](docs/superpowers/specs/) | Design specs (Graph IR compiler, v4 DSL, etc.) |
| [docs/module-map.md](docs/module-map.md) | Current repo structure and module boundaries |

## Testing

```bash
pytest                                     # all tests (auto-skips Neo4j if unavailable)
pytest --cov=libs --cov=services tests     # with coverage
ruff check . && ruff format --check .      # lint
```

## Tech Stack

**Backend:** Python 3.12+, FastAPI, Pydantic v2, LanceDB, Neo4j/Kuzu, NumPy, PyArrow, typst-py

**Frontend:** React, TypeScript, Vite, Ant Design, React Query, vis-network, KaTeX
