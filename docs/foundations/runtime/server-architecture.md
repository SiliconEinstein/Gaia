# Server Architecture

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Architecture |
| Scope | Subsystem |
| Related | [../system-overview.md](../system-overview.md), [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md), [review-runtime.md](review-runtime.md), [curation-runtime.md](curation-runtime.md), [storage-schema.md](storage-schema.md), [../server/architecture.md](../server/architecture.md) |

## Purpose

This document defines the current backend/runtime architecture that exists in the repository today.

It avoids a common mistake in older docs: treating every target shared-side design as if it were already deployed. The current runtime is smaller and more concrete than that.

## Current Runtime Shape

The current Gaia backend is best understood as:

- a set of reusable library pipelines
- a storage facade (`StorageManager`)
- optional local or batch-style execution contexts
- curation and inference helpers that operate over stored graph state

It is **not yet** best described as a fully separated network service platform with a stable external API and independently deployed review and curation services.

## Main Runtime Pieces

### 1. CLI entrypoints

[`cli/main.py`](../../../cli/main.py) is currently the primary shipped execution shell.

It drives:

- local build
- local infer
- local publish
- local search

This means the repository's current "server-side" runtime remains closely coupled to reusable library code rather than isolated behind a dedicated API application.

### 2. Reusable pipeline layer

[`libs/pipeline.py`](../../../libs/pipeline.py) is the main execution spine for:

- `pipeline_build(...)`
- `pipeline_review(...)`
- `pipeline_infer(...)`
- `pipeline_publish(...)`

These functions are usable from CLI and from future batch or service runtimes.

### 3. Storage facade

[`libs/storage/manager.py`](../../../libs/storage/manager.py) is the central backend runtime facade.

It coordinates:

- content persistence
- graph topology persistence
- vector persistence
- package ingestion
- factor and global-node writes
- canonical binding writes
- global inference-state access

This is the most concrete shared-side backend element currently present in the repo.

### 4. Review runtime path

The current review path is mostly embedded runtime logic rather than a standalone deployed service.

Today it is implemented through:

- `pipeline_review(...)`
- `ReviewClient` / `MockReviewClient`
- local callers in CLI and tests

The details live in [review-runtime.md](review-runtime.md).

### 5. Curation runtime path

The current curation path is a distinct offline runtime flow:

- `run_curation(...)`
- curation clustering
- abstraction agent
- conflict detection
- cleanup planning and execution

The details live in [curation-runtime.md](curation-runtime.md).

## Library-First, Service-Ready

The best concise description of today's backend architecture is:

- **library-first**
- **service-ready**

That means:

- important responsibility boundaries already exist conceptually
- reusable runtime modules already exist in code
- but the repository does not yet expose all of those boundaries as separately deployed network services

This is why foundations should distinguish carefully between:

- `Gaia LKM`
- `service`
- `server`

The LKM and service model are conceptually stable earlier than the final deployment topology.

## Current Execution Modes

The runtime currently supports three practical execution modes.

### Local embedded mode

Used by the CLI:

- run pipelines directly in-process
- own the storage manager locally
- write to local LanceDB and graph storage

### Batch and worker style mode

Supported by the library structure:

- pass in a pre-initialized `StorageManager`
- reuse the same pipelines in a longer-lived process
- treat curation and publish as worker-style jobs

### Future networked mode

Clearly anticipated by the architecture, but not yet a stable shipped surface:

- external API entrypoints
- submission endpoints
- queue-backed service orchestration

## What The Current Backend Is Not Yet

The repository does not yet contain a fully settled answer for all of the following:

- a stable public LKM API contract
- a dedicated always-on review service runtime
- a dedicated always-on curation service runtime
- a production-grade network service shell wrapping all backend flows

So older "server" documents should be read as useful design pressure, not as literal description of the shipped runtime.

## Relationship To Storage

The current backend is storage-centered.

In practice:

- the content store is the main source of truth
- graph and vector stores are attached through `StorageManager`
- publish, curation, and shared inference utilities all depend on stored package and graph state

That runtime data model is defined in [storage-schema.md](storage-schema.md).

## Relationship To Service Contracts

The conceptual split between:

- `ReviewService`
- `CurationService`

is real and important, even though the runtime implementation is still largely library-first.

Those conceptual contracts are defined in:

- [../contracts/services/service-boundaries.md](../contracts/services/service-boundaries.md)
- [../contracts/services/review-service.md](../contracts/services/review-service.md)
- [../contracts/services/curation-service.md](../contracts/services/curation-service.md)

## Out Of Scope

This document does not define:

- high-level scientific reasoning theory
- authoring syntax
- storage field-by-field schema detail
- BP semantics beyond runtime ownership boundaries

## Migration Note

This document intentionally avoids repeating the older "Gaia Server" target architecture as if it were already deployed. The active runtime is smaller and more concrete: reusable pipelines plus storage plus offline maintenance utilities. That is the correct base to document before introducing a fuller network service shell.
