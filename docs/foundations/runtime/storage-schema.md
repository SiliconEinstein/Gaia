# Storage Schema

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [server-architecture.md](server-architecture.md), [../contracts/authoring/graph-ir.md](../contracts/authoring/graph-ir.md), [../contracts/artifacts/package-profiles.md](../contracts/artifacts/package-profiles.md), [../server/storage-schema.md](../server/storage-schema.md) |

## Purpose

This document defines the current persistence-side data model used by Gaia runtime code.

It is the canonical runtime/storage companion to the higher-level contracts. Where the contracts define what kinds of artifacts and lifecycle boundaries Gaia needs, this document defines how today's implementation persists those things.

## First Principle

The current storage architecture is **multi-store, but not multi-source-of-truth**.

The runtime design is:

- one storage facade: `StorageManager`
- one primary content source of truth
- optional graph and vector backends derived from that content layer

This means storage schema must distinguish between:

- authoritative persisted entities
- derived topology and index structures
- runtime state

## Main Runtime Stores

### ContentStore

The content store is the primary source of truth.

In current code this is the LanceDB-backed implementation behind [`libs/storage/content_store.py`](../../../libs/storage/content_store.py) and [`libs/storage/lance_content_store.py`](../../../libs/storage/lance_content_store.py).

It persists:

- packages
- modules
- knowledge items
- chains
- factors
- submission artifacts
- probabilities
- belief history
- canonical bindings
- global canonical nodes
- global inference state
- resource metadata

### GraphStore

The graph store is an attached topology backend.

It is used for:

- knowledge topology
- factor topology
- global-node topology
- traversal and subgraph queries

In current code it may be:

- Kuzu
- Neo4j
- or absent

It is not the primary source of truth for package content.

### VectorStore

The vector store is an embedding and search backend.

It is used for:

- knowledge embeddings
- vector-search support

It is also not the primary source of truth for package content.

## Storage Facade

`StorageManager` is the runtime entrypoint for storage operations.

It owns:

- store initialization
- coordinated package ingestion
- probability writes
- factor writes
- global-node writes
- canonical binding writes
- global inference-state access

Domain code should describe storage behavior in terms of `StorageManager`, not in terms of individual backend tables or database drivers.

## Main Persisted Entity Families

### 1. Authored package entities

These preserve authored package structure and review-visible package outputs:

- `Package`
- `Module`
- `Knowledge`
- `Chain`
- `ProbabilityRecord`
- `Resource`
- `ResourceAttachment`

### 2. Structural graph entities

These persist Graph IR-derived or runtime-structural information:

- `FactorNode`
- `PackageSubmissionArtifact`

### 3. Shared-state and LKM entities

These support the shared identity and global-state side of Gaia LKM:

- `CanonicalBinding`
- `GlobalCanonicalNode`
- `GlobalInferenceState`

### 4. Runtime history entities

These persist runtime-derived history rather than authored source:

- `BeliefSnapshot`

## Visibility Model

Current package ingestion uses a simple visibility state machine:

1. write package as `preparing`
2. write dependent content, graph, and vector data
3. commit package by flipping it to `merged`

This means partially written package data stays invisible to normal reads until commit completes.

The key current visibility judgment is therefore:

- `merged` packages are visible
- `preparing` packages are not yet visible as committed knowledge

## What Is Actually Written Today

The current publish/runtime path writes:

- package
- modules
- knowledge items
- chains
- factors
- submission artifact
- embeddings
- probability records

Important current nuance:

- local preview BP beliefs are **not** published by `pipeline_publish(...)`
- the storage schema still supports `BeliefSnapshot`
- that table is for runtime and history use, especially future or separate BP runs, not for local publish-time preview leakage

## Schema Scope And Caveats

This document describes the current runtime schema, not an idealized future LKM schema.

That means some entity families coexist even though they represent different conceptual layers:

- package-authored objects
- structural factor-graph artifacts
- shared/global identity state

This is acceptable in the current runtime because the codebase is still consolidating around a single shared storage layer.

## Relationship To Contracts

The storage schema should be read after the contract docs, not before them.

In particular:

- [../contracts/artifacts/package-profiles.md](../contracts/artifacts/package-profiles.md) explains what kinds of packages exist
- [../contracts/authoring/graph-ir.md](../contracts/authoring/graph-ir.md) explains the structural graph contract that storage persists
- [../contracts/lifecycles/lkm-package-lifecycle.md](../contracts/lifecycles/lkm-package-lifecycle.md) explains when storage writes occur in shared-side flow

## What This Document Does Not Do

This document does not try to freeze:

- every future table name forever
- the final ideal decomposition of package-state versus LKM-state storage
- future external API payloads

Its job is narrower: describe the current runtime persistence model accurately enough for implementation and review.

## Out Of Scope

This document does not define:

- authored package syntax
- high-level scientific reasoning theory
- service ownership boundaries
- BP operator semantics

## Migration Note

This document replaces the earlier placeholder-only runtime schema note. It also corrects an older source of confusion: belief-history storage still exists, but local publish no longer turns author-local BP preview into published belief snapshots.
