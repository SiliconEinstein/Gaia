# Gaia Documentation

## Source of Truth

The canonical specifications for Gaia live in [`foundations/`](foundations/README.md):

- [Product Scope](foundations/product-scope.md) — what Gaia is and is not
- [System Overview](foundations/system-overview.md) — architecture layers and runtime flow
- [Domain Model](foundations/domain-model.md) — nodes, hyperedges, commits, and vocabulary
- [Language Spec](foundations/language/gaia-language-spec.md) — Gaia Language semantics, package surface, and conformance rules
- [CLI Command Lifecycle](foundations/cli/command-lifecycle.md) — build / review / infer / publish pipeline
- [Theoretical Foundation](foundations/theory/theoretical-foundation.md) — Jaynes framework, Gaia identity, plausible reasoning
- [Inference Theory](foundations/theory/inference-theory.md) — BP algorithm, lattice theory, edge semantics
- [Server Architecture](foundations/server/architecture.md) — registry-based server design

Start there for any question about current architecture, contracts, or semantics.

## Directory Map

| Directory | Contents | Status |
|-----------|----------|--------|
| `foundations/` | Product scope, system overview, domain model, language spec, CLI specs | **Current** — canonical specs |
| `design/` | Scaling belief propagation, related work | **Reference** — evergreen design notes |
| `examples/` | Einstein elevator, Galileo tied-balls worked examples | **Reference** — evergreen examples |
| `archive/` | Historical design docs and implementation plans from the initial build-out | **Historical** — preserved for context |

## Other Entry Points

- [Module Map](module-map.md) — current repo structure, module boundaries, and dependency flow
- [Architecture Re-baseline](architecture-rebaseline.md) — diagnosis of structural issues and recommended cleanup path
- [Repository README](../README.md) — quick start, runtime overview, and API entry points
