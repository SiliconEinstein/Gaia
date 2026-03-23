# Graph IR

| Field | Value |
|---|---|
| Status | Transitional |
| Level | Spec |
| Scope | Subsystem |
| Related | [gaia-language-spec.md](gaia-language-spec.md), [../lifecycles/cli-lifecycle.md](../lifecycles/cli-lifecycle.md), [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md), [../../semantics/knowledge-relations.md](../../semantics/knowledge-relations.md), [../../graph-ir.md](../../graph-ir.md) |

## Purpose

This document defines the Graph IR structural contract between authored Gaia packages and downstream inference/runtime processing.

It is marked `Transitional` because this is the new canonical home for the contract, but the older detailed Graph IR draft still contains migration-era field detail that has not yet been fully folded in here.

## Core Role

Graph IR is the explicit structural layer between:

- the authored package surface
- local and shared-side reasoning/runtime layers

Its purpose is to make the lowering boundary auditable and machine-readable.

Gaia should not reason directly over authored source text. It should reason over an explicit structural representation derived from that source.

## What Graph IR Must Preserve

Graph IR must preserve at least four things:

- the package-local knowledge items being reasoned about
- the structural relations or factor-like connections between them
- the source provenance needed to trace those structures back to authored source
- the package-local distinction between raw authored structure and local canonicalization

## Graph IR Artifact Layers

At the local authoring boundary, the important Graph IR artifacts are:

### Raw graph

The raw graph is the deterministic structural lowering of authored package source.

Its job is to preserve source-faithful structure before semantic merging.

### Local canonical graph

The local canonical graph is the package-local semantic consolidation layer built from the raw graph.

Its job is to express package-scoped semantic identity without claiming global shared identity.

### Canonicalization log

The canonicalization log records how raw graph structure was consolidated into the local canonical graph.

Its job is auditability, not belief calculation.

## Core Object Families

The Graph IR contract must support at least the following object families.

### Knowledge-bearing nodes

These represent the package-local knowledge items being reasoned over.

Their detailed semantic types are defined in [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md), not in this file.

### Relation or factor structure

These represent the explicit structured connections between knowledge-bearing nodes.

Their semantic families are defined in [../../semantics/knowledge-relations.md](../../semantics/knowledge-relations.md). Graph IR's job is to encode their structure, not to restate their full meaning.

### Source references

These preserve traceability back to authored package source.

### Parameterization-related placeholders or schema structure

Graph IR may preserve open structure such as templates, schema nodes, or parameterized patterns when needed for later lowering or instantiation behavior.

## Structural Invariants

The Graph IR contract must obey these invariants.

### Structural, not belief-bearing

Graph IR is structural.

It should not be the home for:

- final shared-side belief state
- registry-managed global inference state
- storage-specific runtime caches

### Package-local identity

Graph IR at this boundary is package-local.

It may preserve local canonicalization, but it does not by itself assign global LKM identity.

### Explicit dependency roles

Graph IR should preserve explicit structural roles needed for later reasoning, such as:

- strong or load-bearing inputs
- weaker background or context inputs

The exact runtime effect of those roles belongs to reasoning/runtime docs, but the structural distinction belongs here.

### Auditable lowering

It should be possible to explain how authored package source became Graph IR artifacts.

That is why raw graph, local canonical graph, and canonicalization log all matter.

## What This Document Does Not Do

This document does not try to be:

- the authored language spec
- the full runtime BP reference
- the storage schema
- the registry-side global identity model

Those belong in other docs.

## Relationship To The Existing Detailed Draft

The older [../../graph-ir.md](../../graph-ir.md) document contains migration-era detail such as:

- raw node shapes
- local and global canonical node detail
- factor node field sketches
- runtime-oriented notes that accumulated over time

This document now becomes the canonical contract home, but it remains intentionally higher-level until that detailed material is folded in and cleaned up.

## Relationship To Other Docs

- [gaia-language-spec.md](gaia-language-spec.md) defines the authored surface that lowers into Graph IR.
- [../lifecycles/cli-lifecycle.md](../lifecycles/cli-lifecycle.md) defines when Graph IR is produced in the CLI lifecycle.
- [../../graph-ir.md](../../graph-ir.md) remains the detailed migration-era reference.
- runtime inference docs define how Graph IR is consumed after this boundary.

## Out Of Scope

This document does not define:

- authored language syntax
- current runtime implementation quirks
- storage implementation details
- full registry-side global graph semantics

## Migration Note

This file now becomes the canonical home for the Graph IR contract in the new tree, but it remains `Transitional` until the remaining detailed field and invariant material is migrated out of the older legacy draft.
