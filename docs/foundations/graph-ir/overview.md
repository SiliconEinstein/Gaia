# Graph IR Overview

> **Status:** Current canonical

## Purpose

Graph IR (Intermediate Representation) is the structural factor graph that sits between Gaia Language and belief propagation. It is the **contract** between the CLI (local authoring tools) and the LKM (global knowledge engine).

Gaia Language is the authored surface. Graph IR is the machine-readable structural form that BP reasons over. BP runs on Graph IR plus a parameterization overlay -- not on the language surface directly.

Graph IR is a **first-class submission artifact**. During `gaia publish`, the package submits both its raw graph and its local canonical graph.

## Three Identity Layers

Graph IR defines three identity layers, each representing a different stage of knowledge identity resolution:

### 1. Raw Graph (deterministic, from `gaia build`)

The raw graph is the direct, deterministic output of compiling Typst source. Raw nodes are content-addressed: the same source always produces the same raw graph. Only byte-identical content is merged at this layer.

Output artifact: `graph_ir/raw_graph.json`

### 2. Local Canonical Graph (package-scoped semantic merge)

An agent skill partitions raw nodes into semantic equivalence groups within the package. Every raw node maps to exactly one local canonical node. Singletons (one raw node per canonical node) are valid and are the default for `gaia build` without agent review.

Output artifacts: `graph_ir/local_canonical_graph.json` + `graph_ir/canonicalization_log.json`

### 3. Global Canonical Graph (registry-assigned, after review)

Global canonical nodes are assigned by the review/registry layer after publish. They are not authored locally. Identity is recorded via `CanonicalBinding` records that link local canonical nodes to their global counterparts.

> **Aspirational**: full global canonicalization with rebuttal cycle is target architecture. Current implementation uses simplified embedding-similarity matching at publish time.

For node schemas at each layer, see [knowledge-nodes.md](knowledge-nodes.md).

## Canonical JSON and Graph Hash

The local canonical graph has a deterministic JSON serialization. The `local_graph_hash` (SHA-256 of the canonical JSON) serves as an integrity check -- the review engine re-compiles the raw graph from source and verifies it matches the submitted hash.

This hash is also used to bind parameterization overlays to a specific graph version (see [parameterization.md](parameterization.md)).

## Build-Time Generation Rules

The compiler translates Gaia Language surface constructs into knowledge nodes and factor nodes:

| Source construct | Knowledge node(s) | Factor node(s) |
|---|---|---|
| `#claim` / `#setting` / `#question` / `#action` (no `from:`) | One knowledge node | None |
| `#claim(from: ...)` / `#action(from: ...)` | One knowledge node | One reasoning factor |
| `#relation(type: "contradiction", between: ...)` | One contradiction node | One mutex_constraint factor |
| `#relation(type: "equivalence", between: ...)` | One equivalence node | One equiv_constraint factor |
| Schema elaboration (parameterized node) | Instance node | One instantiation factor per schema-instance pair |

For knowledge node schemas, see [knowledge-nodes.md](knowledge-nodes.md). For factor node schemas and type definitions, see [factor-nodes.md](factor-nodes.md).

## Factor Nodes

Factors are shared across all three identity layers -- only the node ID namespace changes. Each factor encodes a reasoning link or structural constraint between knowledge nodes. Factor structure is defined once in [factor-nodes.md](factor-nodes.md); the computational semantics (potential functions) are defined in [../bp/potentials.md](../bp/potentials.md).

## Parameterization

Graph IR deliberately separates structure from parameters. Priors and conditional probabilities live in overlay objects that reference the graph by hash, not inline in the graph. See [parameterization.md](parameterization.md).

## Canonicalization

The process of mapping nodes across identity layers (raw to local canonical to global canonical) is described in [canonicalization.md](canonicalization.md).

## Source

- `libs/graph_ir/models.py` -- `RawGraph`, `LocalCanonicalGraph`, `FactorNode`
- `libs/graph_ir/typst_compiler.py` -- `compile_v4_to_raw_graph()`
- `libs/graph_ir/build_utils.py` -- `build_singleton_local_graph()`
- `libs/graph_ir/adapter.py` -- builds `FactorGraph` from local canonical graph
- `libs/storage/models.py` -- `FactorNode`, `CanonicalBinding`, `GlobalCanonicalNode`
