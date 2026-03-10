# Foundations

This directory is the working area for Gaia's next foundation reset.

Use it when the task affects any of the following:

- overall architecture
- module boundaries
- API contracts
- graph model semantics
- storage schema or backend capability assumptions
- domain vocabulary

## Current status

Gaia now has a documented re-baselining diagnosis in [../architecture-rebaseline.md](../architecture-rebaseline.md).

The execution plan for that reset lives here:

**Global (cross-subsystem):**

- [Foundation Reset Plan](foundation-reset-plan.md)
- [Product Scope](product-scope.md)
- [System Overview](system-overview.md)
- [Domain Model](domain-model.md)

**Theory:**

- [Theoretical Foundation](theory/theoretical-foundation.md) — Jaynes 纲领
- [Inference Theory](theory/inference-theory.md) — BP 算法理论

**Language:**

- [Gaia Language Spec](language/gaia-language-spec.md)
- [Gaia Language Design](language/gaia-language-design.md)
- [Language Design Rationale](language/design-rationale.md)
- [Type System Direction](language/type-system-direction.md)

**CLI:**

- [Gaia CLI Runtime Boundaries](cli/boundaries.md)
- [Gaia CLI Command Lifecycle](cli/command-lifecycle.md)

**Review:**

- [Build, Alignment, and Review Architecture](review/architecture.md)

**Server:**

- [Server Architecture](server/architecture.md)

## Intended outputs

The plan is to establish a small set of durable foundation docs before major code restructuring resumes:

1. `product-scope.md`
2. `domain-model.md`
3. `theory/theoretical-foundation.md` (Jaynes-centered theoretical foundation)
4. `theory/inference-theory.md` (BP algorithm and inference theory)
5. `language/gaia-language-spec.md` (Gaia Language spec)
6. `cli/boundaries.md` (Gaia CLI runtime layering)
7. `review/architecture.md` (shared build, alignment, and review architecture across CLI and server)
8. `server/architecture.md` (Server architecture)
9. `server/graph-spec.md`
10. `server/storage-schema.md` (Server storage schema)
11. `server/module-boundaries.md`
12. `server/api-contract.md`

Those files do not all exist yet. This directory is the place where they should be created and kept current.

## Folder Layout

- `theory/`: Theoretical foundations (Jaynes, BP algorithm) — shared mathematical basis
- `language/`: Gaia formal language spec, design, and design rationale
- `cli/`: Gaia CLI runtime boundaries and future CLI-specific docs
- `review/`: Shared build, alignment, review, and package environment semantics
- `server/`: Server architecture, storage schema, API contracts

## Historical docs

Historical design documents and implementation plans from the initial build-out are preserved in [`../archive/`](../archive/).

## Working rule

When a change affects architecture or cross-module behavior, the relevant foundation doc should be updated in the same branch, or the PR should explicitly state why the docs are being deferred.
