# Graph IR

> **Status:** Current canonical

Graph IR is the structural factor graph intermediate representation between Gaia Language and belief propagation. This document defines the contract: what Graph IR contains, its identity layers, and its key data structures. For full design details, see `docs/foundations_archive/graph-ir.md`.

## Purpose

Gaia Language is the authored surface. Graph IR is the machine-readable structural form that BP reasons over. BP runs on Graph IR plus a parameterization overlay -- not on the language surface directly.

Graph IR is a **first-class submission artifact**. During `gaia publish`, the package submits both its raw graph and its local canonical graph.

## Three Identity Layers

### 1. Raw Graph (deterministic, from `gaia build`)

```
RawKnowledgeNode:
    raw_node_id:    str          # sha256(knowledge_type + content + sorted(parameters))
    knowledge_type: str          # claim | setting | question | action | contradiction | equivalence
    content:        str
    parameters:     list[Parameter]   # empty = ground, non-empty = schema (universally quantified)
    source_refs:    list[SourceRef]
```

Raw nodes are deterministic: the same source always produces the same raw graph. Only byte-identical content is merged at this layer.

Output: `graph_ir/raw_graph.json`

### 2. Local Canonical Graph (package-scoped semantic merge)

```
LocalCanonicalNode:
    local_canonical_id:     str
    knowledge_type:         str
    representative_content: str
    parameters:             list[Parameter]
    member_raw_node_ids:    list[str]   # one or more raw nodes merged
```

An agent skill partitions raw nodes into semantic equivalence groups within the package. Every raw node maps to exactly one local canonical node. Singletons are valid.

Output: `graph_ir/local_canonical_graph.json` + `graph_ir/canonicalization_log.json`

### 3. Global Canonical Graph (registry-assigned, after review)

```
GlobalCanonicalNode:
    global_canonical_id: str     # registry-assigned, opaque (e.g., gcn_<ULID>)
    knowledge_type:      str
    member_local_nodes:  list[LocalCanonicalRef]
    provenance:          list[PackageRef]
```

Assigned by the review/registry layer after publish. Not authored locally. Identity is recorded via `CanonicalBinding` records.

> **Aspirational**: full global canonicalization with rebuttal cycle is target architecture. Current implementation uses simplified embedding-similarity matching at publish time.

## Factor Nodes

Factors are shared across all three identity layers -- only the node ID namespace changes.

```
FactorNode:
    factor_id:   str              # f_{sha256[:16]}
    type:        str              # reasoning | instantiation | mutex_constraint | equiv_constraint
    premises:    list[str]        # strong dependency (BP edges)
    contexts:    list[str]        # weak dependency (no BP edges)
    conclusion:  str              # single output node
```

See `docs/foundations/gaia-concepts/factor-design.md` for type-by-type semantics.

## Local Parameterization Overlay

Structure is separated from parameters. Priors and conditional probabilities live in a non-submitted overlay:

```
LocalParameterization:
    graph_hash:         str
    node_priors:        dict[str, float]         # keyed by local_canonical_id
    factor_parameters:  dict[str, FactorParams]  # keyed by factor_id
```

This overlay is derived locally for `gaia infer` preview. It is **not submitted** during `gaia publish`. The review engine makes independent probability judgments.

## Canonical JSON and Graph Hash

The local canonical graph has a deterministic JSON serialization. The `local_graph_hash` (SHA-256 of the canonical JSON) serves as an integrity check -- the review engine re-compiles the raw graph from source and verifies it matches the submitted hash.

## Build-Time Generation Rules

| Source construct | Knowledge node(s) | Factor node(s) |
|---|---|---|
| Claim, Setting, Question, Action | One raw node per elaborated object | -- |
| `#claim(from: ...)` / `#action(from: ...)` | -- | One reasoning factor per ChainExpr |
| `#relation(type: "contradiction")` | One contradiction node | One mutex_constraint factor |
| `#relation(type: "equivalence")` | One equivalence node | One equiv_constraint factor |
| Schema elaboration | Instance node | One instantiation factor per pair |

## Implementation

| Component | Location |
|---|---|
| Graph IR models | `libs/graph_ir/models.py` -- `RawGraph`, `LocalCanonicalGraph`, `FactorNode` |
| Raw graph compiler | `libs/graph_ir/typst_compiler.py` -- `compile_v4_to_raw_graph()` |
| Local canonicalization | `libs/graph_ir/build_utils.py` -- `build_singleton_local_graph()` |
| BP adapter | `libs/graph_ir/adapter.py` -- builds `FactorGraph` from local canonical graph |
| Storage models | `libs/storage/models.py` -- `FactorNode`, `CanonicalBinding`, `GlobalCanonicalNode` |

## Source

- `docs/foundations_archive/graph-ir.md` -- full Graph IR specification
- `docs/foundations/implementations/overview.md` -- end-to-end data flow
