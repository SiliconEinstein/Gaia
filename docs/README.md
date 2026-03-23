# Gaia Documentation

## Source of Truth

The canonical specifications for Gaia live in [`foundations/`](foundations/README.md):

- [Documentation Policy](foundations/documentation-policy.md) — how active foundation docs are structured and maintained
- [Gaia Overview](foundations/foundation/gaia-overview.md) — what Gaia is, and the Gaia CLI / Gaia LKM split
- [Scientific Reasoning Foundation](foundations/foundation/scientific-reasoning-foundation.md) — the high-level reasoning foundation
- [System Overview](foundations/system-overview.md) — top-level artifact flow
- [Terminology](foundations/semantics/terminology.md) — canonical terminology for CLI, LKM, service, engine, server, package, and artifact
- [Scientific Knowledge](foundations/semantics/scientific-knowledge.md) — core Gaia knowledge types
- [Knowledge Relations](foundations/semantics/knowledge-relations.md) — core semantic relation families
- [Gaia Reasoning Model](foundations/semantics/gaia-reasoning-model.md) — Gaia-specific reasoning families and their role
- [Product Scope](foundations/product-scope.md) — current baseline and product-surface context
- [Language Spec](foundations/contracts/authoring/gaia-language-spec.md) — Gaia Language semantics, Typst package surface, and conformance rules
- [Graph IR](foundations/contracts/authoring/graph-ir.md) — structural contract between authored packages and downstream reasoning/runtime
- [Package Profiles](foundations/contracts/artifacts/package-profiles.md) — the main Gaia package profiles
- [CLI Lifecycle](foundations/contracts/lifecycles/cli-lifecycle.md) — local build / infer / publish lifecycle
- [LKM Package Lifecycle](foundations/contracts/lifecycles/lkm-package-lifecycle.md) — what happens after publish reaches Gaia LKM
- [Service Boundaries](foundations/contracts/services/service-boundaries.md) — ReviewService / CurationService split
- [Server Architecture](foundations/runtime/server-architecture.md) — current backend/runtime implementation
- [Inference Runtime](foundations/runtime/inference-runtime.md) — current executable inference path
- [Storage Schema](foundations/runtime/storage-schema.md) — current persistence/runtime data model

Start there for any question about current architecture, contracts, or semantics.

## Directory Map

| Directory | Contents | Status |
|-----------|----------|--------|
| `foundations/` | Active foundation docs organized around foundation, semantics, contracts, and runtime | **Current** — canonical specs |
| `design/` | Scaling belief propagation, related work | **Reference** — evergreen design notes |
| `examples/` | Einstein elevator, Galileo tied-balls worked examples | **Reference** — evergreen examples |
| `archive/` | Historical design docs and implementation plans from the initial build-out | **Historical** — preserved for context |

## Other Entry Points

- [Module Map](module-map.md) — current repo structure, module boundaries, and dependency flow
- [Architecture Re-baseline](architecture-rebaseline.md) — diagnosis of structural issues and recommended cleanup path
- [Repository README](../README.md) — quick start, runtime overview, and API entry points

Legacy bridge docs still exist under `foundations/` for compatibility, but the preferred navigation path is now `foundations/README.md` plus the new `foundation/`, `semantics/`, `contracts/`, and `runtime/` tree.
