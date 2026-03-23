# Gaia System Overview

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Overview |
| Scope | Repo-wide |
| Related | [semantics/terminology.md](semantics/terminology.md), [foundation/gaia-overview.md](foundation/gaia-overview.md), [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md), [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md), [contracts/lifecycles/lkm-package-lifecycle.md](contracts/lifecycles/lkm-package-lifecycle.md), [runtime/server-architecture.md](runtime/server-architecture.md) |

## Purpose

This document describes the top-level structure of Gaia.

It is the canonical orientation doc for how the major parts of the system fit together. It does not try to fully specify every workflow or runtime detail.

For terminology, see [semantics/terminology.md](semantics/terminology.md).

## Primary Split: Gaia CLI and Gaia LKM

Gaia has two primary active sides:

- **Gaia CLI** — the local author-side toolchain
- **Gaia LKM** — the shared-side knowledge core and system of record

This is the primary conceptual split for active foundation docs.

```
┌─────────────────────────────────────────────────────────────┐
│ Researcher / agent                                         │
│ writes Typst package source and runs local commands        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Gaia CLI                                                    │
│ local authoring, build, infer, publish                     │
│ local Typst package source + local .gaia/ artifacts        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Gaia LKM                                                    │
│ shared knowledge state, review, rebuttal, integration,     │
│ curation, search, and shared inference surfaces            │
└─────────────────────────────────────────────────────────────┘
```

## Gaia CLI

Gaia CLI is the local toolchain for authors, researchers, and agents.

Its canonical local lifecycle is:

- `build`
- `infer`
- `publish`

The CLI is responsible for:

- working from local Typst package source
- producing local build and inference artifacts under `.gaia/`
- giving users a local preview before shared-side submission
- publishing package artifacts outward

Important boundary:

- `review` is not part of the canonical CLI lifecycle
- current `main` does not ship a standalone `gaia review` command in `cli/main.py`; review logic currently appears as embedded preview runtime inside local infer and local publish flows

For CLI details, see [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md).

## Gaia LKM

Gaia LKM is the shared-side knowledge core and system of record.

It is responsible for the shared workflows that happen after local publication reaches the shared side, including:

- review
- rebuttal handling
- integration into shared knowledge state
- curation and maintenance
- shared discovery and search surfaces
- larger-scale inference and graph-wide maintenance

Important boundary:

- Gaia LKM is the primary shared-side foundation term
- `Gaia Cloud` may still be used as a product or deployment alias
- `cloud` does not imply remote-only deployment; a local or self-hosted LKM deployment is still valid

Current detailed shared-side docs now primarily live in:

- [contracts/lifecycles/lkm-package-lifecycle.md](contracts/lifecycles/lkm-package-lifecycle.md)
- [contracts/services/service-boundaries.md](contracts/services/service-boundaries.md)

## Service, Engine, and Server

Within Gaia LKM, active docs should distinguish three different ideas:

- **Service** — a responsibility boundary such as `ReviewService` or `CurationService`
- **Engine** — an internal algorithmic component such as a BP engine
- **Server** — the current running backend implementation

This distinction matters because:

- a `service` is part of the conceptual architecture
- an `engine` is an internal execution component
- a `server` is a runtime/deployment term, not the best name for the entire shared side

For current backend runtime details, see [runtime/server-architecture.md](runtime/server-architecture.md).

## Artifact Flow

At a high level, Gaia moves artifacts through the following path:

1. A user or agent authors a Typst package locally.
2. Gaia CLI builds that source into deterministic local artifacts.
3. Gaia CLI optionally runs local inference for preview.
4. Gaia CLI publishes a package artifact outward.
5. Gaia LKM processes the shared-side lifecycle around that package: review, rebuttal, integration, and curation.

This split is why CLI and LKM should be documented separately even when they share code.

## Current Runtime on `main`

The current `main` branch already includes several runtime surfaces:

- Gaia CLI
- shared-side backend/runtime modules
- storage-backed local and shared execution paths

The active foundations reset should describe those surfaces using the Gaia CLI / Gaia LKM conceptual split, while keeping runtime implementation details in runtime-oriented docs.

## Related Documents

- [semantics/terminology.md](semantics/terminology.md) — canonical terminology
- [foundation/gaia-overview.md](foundation/gaia-overview.md) — Gaia's overall positioning
- [product-scope.md](product-scope.md) — migration-era product scope and baseline
- [contracts/authoring/gaia-language-spec.md](contracts/authoring/gaia-language-spec.md) — author-facing package surface
- [contracts/authoring/graph-ir.md](contracts/authoring/graph-ir.md) — structural IR contract
- [contracts/lifecycles/cli-lifecycle.md](contracts/lifecycles/cli-lifecycle.md) — local CLI lifecycle
- [contracts/lifecycles/lkm-package-lifecycle.md](contracts/lifecycles/lkm-package-lifecycle.md) — shared-side package lifecycle
- [runtime/server-architecture.md](runtime/server-architecture.md) — current backend/runtime
