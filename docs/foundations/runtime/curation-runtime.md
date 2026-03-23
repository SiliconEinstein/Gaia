# Curation Runtime

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Component |
| Related | [../contracts/services/curation-service.md](../contracts/services/curation-service.md), [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md), [loop-analysis.md](loop-analysis.md), [server-architecture.md](server-architecture.md) |

## Purpose

This document defines how curation currently executes in code, as distinct from the responsibility contract of `CurationService`.

## Current Runtime Shape

Curation currently exists as an offline library workflow centered on:

- `run_curation(...)` in [`libs/curation/scheduler.py`](../../../libs/curation/scheduler.py)

It is not currently exposed as a stable independent network service. Instead, it is a shared-side maintenance pipeline that can be run by an internal worker, batch job, or future service shell.

## Current Pipeline

The current curation pipeline is:

1. load global nodes and factors from storage
2. cluster similar nodes
3. deduplicate by content hash
4. run abstraction over eligible clusters
5. detect conflicts
6. inspect structure
7. generate cleanup plan
8. execute approved cleanup
9. persist resulting node and factor updates

This is materially more than a placeholder. It already exists as executable code and test-covered library behavior.

## Main Runtime Components

The curation runtime currently composes several concrete modules:

- clustering
- deduplication
- abstraction
- conflict detection
- structural inspection
- cleanup planning
- cleanup execution
- curation review of suggestions

The main runtime driver is `run_curation(...)`, but it delegates real work to multiple component modules under [`libs/curation/`](../../../libs/curation/).

## Storage Dependency

Curation runtime is explicitly storage-backed.

It depends on:

- `StorageManager.list_global_nodes()`
- `StorageManager.list_factors()`
- `StorageManager.upsert_global_nodes(...)`
- `StorageManager.write_factors(...)`

So curation is not an author-side package operation. It is a shared-state maintenance runtime operating on LKM state.

## Relationship To BP

Curation runtime is not itself "the BP service", but it already uses BP-based diagnostics.

Current code builds factor graphs from stored nodes and factors in order to support:

- oscillation-style conflict surfacing
- sensitivity-style conflict analysis

This is why [loop-analysis.md](loop-analysis.md) sits next to curation runtime in the runtime tree: loop diagnostics already matter operationally for curation.

## LLM Use At Runtime

Curation runtime already has model-assisted pieces, but they are embedded inside the offline maintenance flow rather than exposed as a separate external workflow surface.

Examples include:

- `AbstractionAgent`
- `CurationReviewer`

This matches the current foundations stance:

- curation is primarily internal to Gaia LKM
- not every investigation task is automatically externalized

## What Curation Runtime Is Not

The current curation runtime is not:

- a submission-scoped review path
- a CLI authoring step
- a publicly stabilized API surface
- a generic marketplace of external research jobs

It is an internal shared-state maintenance runtime.

## Relationship To Investigation Artifacts

Curation runtime is the main current owner of longer-lived investigation-oriented runtime work, such as:

- contradiction candidates
- independent-evidence style audits
- hidden-premise investigations
- abstraction follow-up work

Those artifact classes are defined contractually in [../contracts/artifacts/investigation-artifacts.md](../contracts/artifacts/investigation-artifacts.md); this document describes how curation currently processes and persists the results operationally.

## Out Of Scope

This document does not define:

- abstract curation responsibility boundaries
- authoring semantics
- high-level scientific reasoning theory
- low-level storage schema definitions

## Migration Note

This document replaces the earlier placeholder-only curation runtime note. The key correction is that curation should now be understood as a real offline maintenance pipeline in the current codebase, not merely as a future label attached to the backend.
