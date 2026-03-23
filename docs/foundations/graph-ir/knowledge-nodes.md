# Knowledge Nodes

> **Status:** Current canonical

This document defines the knowledge node schemas at each of Graph IR's three identity layers. Knowledge nodes are the variable nodes in Gaia's factor graph -- they represent propositions with quantifiable uncertainty.

For factor nodes (the constraint nodes that connect knowledge nodes), see [factor-nodes.md](factor-nodes.md). For the BP behavior of different knowledge types, see [../cli/gaia-lang/knowledge-types.md](../cli/gaia-lang/knowledge-types.md).

## 1. RawKnowledgeNode (from `gaia build`)

```
RawKnowledgeNode:
    raw_node_id:    str              # sha256(knowledge_type + content + sorted(parameters))
    knowledge_type: str              # claim | setting | question | action | contradiction | equivalence
    content:        str
    parameters:     list[Parameter]  # empty = ground, non-empty = schema (universally quantified)
    source_refs:    list[SourceRef]
```

Raw nodes are deterministic and content-addressed: the same source always produces the same `raw_node_id`. Only byte-identical content is merged at this layer.

**Identity rule**: `raw_node_id = sha256(knowledge_type + content + sorted(parameters))`. This means two declarations with identical type, content, and parameters will share the same raw node ID even if they appear in different source files within the package.

**Schema vs ground**: A node with non-empty `parameters` is a schema (universally quantified proposition). A node with empty `parameters` is a ground (concrete) proposition. Schema nodes may generate instantiation factors when elaborated into ground instances.

Output artifact: `graph_ir/raw_graph.json`

## 2. LocalCanonicalNode (package-scoped semantic merge)

```
LocalCanonicalNode:
    local_canonical_id:     str
    knowledge_type:         str
    representative_content: str
    parameters:             list[Parameter]
    member_raw_node_ids:    list[str]   # one or more raw nodes merged
```

An agent skill partitions raw nodes into semantic equivalence groups within the package. Every raw node maps to exactly one local canonical node. Singletons (one raw node per canonical node) are valid and are the default when no agent-assisted clustering is performed.

**Representative content**: When multiple raw nodes merge into one local canonical node, one is chosen as the representative. The selection strategy is currently first-encountered; smarter selection is a potential improvement.

Output artifacts: `graph_ir/local_canonical_graph.json` + `graph_ir/canonicalization_log.json`

## 3. GlobalCanonicalNode (registry-assigned, after review)

```
GlobalCanonicalNode:
    global_canonical_id: str                  # registry-assigned, opaque (e.g., gcn_<sha256[:16]>)
    knowledge_type:      str                  # claim, question, etc.
    kind:                str | None            # sub-classification
    representative_content: str               # content from the first contributing node
    parameters:          list[Parameter]       # for schema nodes
    member_local_nodes:  list[LocalCanonicalRef]  # all local nodes bound to this
    provenance:          list[PackageRef]      # which packages contributed
    metadata:            dict | None           # includes source_knowledge_names for ext: resolution
```

Global canonical nodes are assigned by the review/registry layer after publish. They are not authored locally. Identity is recorded via `CanonicalBinding` records.

**Cross-package resolution**: The `source_knowledge_names` metadata field enables resolution of `ext:package.name` cross-package references. When a later package references a node from an earlier package, the canonicalization engine can find the corresponding global node via this field.

> **Aspirational**: full global canonicalization with rebuttal cycle is target architecture. Current implementation uses simplified embedding-similarity matching at publish time.

## 4. CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:  str
    global_canonical_id: str
    package_id:          str
    match_type:          str    # "match_existing" | "create_new"
```

Each binding records the decision made during global canonicalization: whether a local node was matched to an existing global node or caused creation of a new one. Bindings are finalized after review approval.

## Output Artifacts

| Stage | Artifact | Contents |
|---|---|---|
| `gaia build` | `graph_ir/raw_graph.json` | All `RawKnowledgeNode`s + `FactorNode`s |
| `gaia build` | `graph_ir/local_canonical_graph.json` | All `LocalCanonicalNode`s + `FactorNode`s (re-keyed) |
| `gaia build` | `graph_ir/canonicalization_log.json` | Raw-to-local mapping decisions |
| Review/integrate | `CanonicalBinding` records | Local-to-global mapping decisions |

## Source

- `libs/graph_ir/models.py` -- `RawKnowledgeNode`, `LocalCanonicalNode`, `FactorNode`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
