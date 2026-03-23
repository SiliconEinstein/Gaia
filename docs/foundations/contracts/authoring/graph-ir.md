# Graph IR

| Field | Value |
|---|---|
| Status | Current canonical |
| Level | Spec |
| Scope | Subsystem |
| Related | [gaia-language-spec.md](gaia-language-spec.md), [../lifecycles/cli-lifecycle.md](../lifecycles/cli-lifecycle.md), [../../semantics/scientific-knowledge.md](../../semantics/scientific-knowledge.md), [../../semantics/knowledge-relations.md](../../semantics/knowledge-relations.md), [../../graph-ir.md](../../graph-ir.md) |

## Purpose

This document defines the current Graph IR structural contract between authored Gaia packages and downstream inference/runtime processing.

The older detailed Graph IR draft remains useful as migration-era background material, but this file is now the canonical contract home.

## Core Role

Graph IR is the explicit structural layer between:

- the authored package surface
- local and shared-side reasoning/runtime layers

Its purpose is to make the lowering boundary auditable and machine-readable.

Gaia should not reason directly over authored source text. It should reason over an explicit structural representation derived from that source.

## Current Artifact Boundary

At the local build boundary, the important Graph IR artifacts are:

- raw graph
- local canonical graph
- canonicalization log

Local parameterization and local inference state are downstream overlays, not part of the Graph IR structural contract itself.

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

## Current Object Models

The current local Graph IR models are defined in `libs/graph_ir/models.py`. The important structural objects are:

- `RawGraph`
- `RawKnowledgeNode`
- `LocalCanonicalGraph`
- `LocalCanonicalNode`
- `FactorNode`
- `SourceRef`

### Raw graph

The current `RawGraph` contract includes:

- package identity
- package version
- `knowledge_nodes`
- `factor_nodes`

### Raw knowledge node

The current `RawKnowledgeNode` contract includes:

- deterministic `raw_node_id`
- `knowledge_type`
- optional `kind`
- visible `content`
- optional `parameters`
- one or more `source_refs`
- optional `metadata`

### Local canonical node

The current `LocalCanonicalNode` contract includes:

- `local_canonical_id`
- package name
- `knowledge_type`
- optional `kind`
- representative content
- member raw-node IDs
- source refs
- optional metadata

### Factor node

The current `FactorNode` contract includes:

- deterministic `factor_id`
- `type`
- `premises`
- `contexts`
- optional `conclusion`
- optional `source_ref`
- optional `metadata`

The presence of both `premises` and `contexts` is part of the structural contract even though the current v4 Typst surface mostly emits `premises` only.

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

## Current v4 Lowering Shape

The current shipped Typst v4 compiler path lowers package source into Graph IR with the following stable shape.

### Knowledge-bearing nodes

Current v4 lowering emits local knowledge-bearing nodes for:

- `setting`
- `question`
- `claim`
- `action`
- explicit relation nodes that become knowledge types such as `contradiction` or `equivalence`

### External references

Current v4 lowering also emits explicit external nodes for cross-package references declared through the active package-linking surface.

These external nodes are structurally present in the raw graph and remain identifiable as external provenance rather than silently collapsing into local authored identity.

### Reasoning factors

Current v4 lowering emits `infer` factors from authored `from:` dependencies.

At this boundary the stable contract is:

- `premises` are explicit
- `conclusion` points to the supported node
- current local v4 authoring does not yet emit separate authored `contexts`

### Constraint factors

Current v4 lowering emits constraint structure for:

- `contradiction`
- `equivalence`

These arise from explicit authored relation declarations rather than from downstream discovery alone.

### Broader factor families

The wider Graph IR/runtime ecosystem may also contain factor families such as:

- `instantiation`
- `abstraction`

Those are real Graph IR concepts in the broader system, but they are not the primary factor families emitted by the current local Typst v4 authoring path.

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

That older file is now a detailed migration-era reference, not the canonical contract home.

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

This file is now the canonical home for the Graph IR contract in the new tree.

The older detailed Graph IR draft remains available as background reference, but future structural contract changes should land here first.
