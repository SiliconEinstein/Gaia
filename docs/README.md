# Gaia Documentation

## Source of Truth

The canonical specifications for Gaia live in [`foundations/`](foundations/README.md):

- [Documentation Policy](foundations/documentation-policy.md) — how active foundation docs are structured and maintained
- [System Overview](foundations/system-overview.md) — Gaia CLI, Gaia LKM, and top-level artifact flow
- [Terminology](foundations/semantics/terminology.md) — canonical terminology for CLI, LKM, service, engine, server, package, and artifact
- [Product Scope](foundations/product-scope.md) — what Gaia is and is not
- [Language Spec](foundations/contracts/authoring/gaia-language-spec.md) — Gaia Language semantics, Typst package surface, and conformance rules
- [Graph IR](foundations/contracts/authoring/graph-ir.md) — structural contract between authored packages and downstream reasoning/runtime
- [CLI Lifecycle](foundations/contracts/lifecycles/cli-lifecycle.md) — local build / infer / publish lifecycle
- [Theoretical Foundation](foundations/theory/theoretical-foundation.md) — Jaynes framework and plausible reasoning motivation
- [Inference Theory](foundations/theory/inference-theory.md) — current semantic operator theory
- [Server Architecture](foundations/server/architecture.md) — current runtime/backend implementation

Start there for any question about current architecture, contracts, or semantics.

## Directory Map

| Directory | Contents | Status |
|-----------|----------|--------|
| `foundations/` | Active foundation docs organized around meaning, contracts, and runtime | **Current** — canonical specs |
| `design/` | Scaling belief propagation, related work | **Reference** — evergreen design notes |
| `examples/` | Einstein elevator, Galileo tied-balls worked examples | **Reference** — evergreen examples |
| `archive/` | Historical design docs and implementation plans from the initial build-out | **Historical** — preserved for context |

## Other Entry Points

- [Module Map](module-map.md) — current repo structure, module boundaries, and dependency flow
- [Architecture Re-baseline](architecture-rebaseline.md) — diagnosis of structural issues and recommended cleanup path
- [Repository README](../README.md) — quick start, runtime overview, and API entry points
