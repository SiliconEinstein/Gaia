# Canonicalization

> **Status:** Current canonical

Canonicalization is the process of mapping knowledge nodes across Graph IR's three identity layers: raw nodes to local canonical nodes (within a package), and local canonical nodes to global canonical nodes (across packages).

## Local Canonicalization

**Scope**: one package, during `gaia build`.

Local canonicalization partitions raw nodes into semantic equivalence groups within the package. Every raw node maps to exactly one local canonical node.

### Automatic singleton mode

The default `gaia build` creates a trivial canonicalization where each raw node becomes its own local canonical node (1:1 mapping). This is a valid canonicalization -- singletons are always acceptable.

### Agent-assisted clustering

An optional agent skill can inspect the raw graph and cluster semantically similar nodes. For example, two raw nodes with slightly different wording but the same meaning can be merged into one local canonical node. The agent produces:

- A refined `local_canonical_graph.json` with merged nodes
- A `canonicalization_log.json` recording which raw nodes merged and why

### Canonicalization log

```
CanonicalizationLog:
    entries: list[CanonicalizationEntry]

CanonicalizationEntry:
    raw_node_ids:          list[str]    # raw nodes in this group
    local_canonical_id:    str          # assigned local canonical ID
    merge_reason:          str | None   # why these were merged (agent explanation)
```

The log provides auditability: reviewers can inspect why nodes were merged and challenge incorrect groupings.

## Global Canonicalization

**Scope**: cross-package, during LKM review/integration.

Global canonicalization maps local canonical nodes to global canonical nodes. When a new package is ingested, each of its local nodes is either:

- **match_existing**: bound to an existing `GlobalCanonicalNode` that expresses the same proposition.
- **create_new**: a new `GlobalCanonicalNode` is created for this previously unseen proposition.

This enables the global knowledge graph to recognize that semantically equivalent propositions from different packages refer to the same knowledge.

### Match strategy

The similarity engine supports two modes:

**Embedding similarity (primary)**: batch-embeds query and candidate contents, computes cosine similarity, returns best match above threshold.

**TF-IDF fallback**: when no embedding model is available, uses scikit-learn's `TfidfVectorizer` for pairwise cosine similarity. Slower and less accurate but requires no external API.

The default match threshold is `0.90`. A match must exceed this threshold to be accepted.

### Filtering rules

Before similarity computation, candidates are filtered:

- **Type match required**: only candidates with the same `knowledge_type` are eligible.
- **Kind match for some types**: `question` and `action` types additionally require matching `kind`.
- **Relation types excluded**: `contradiction` and `equivalence` are package-local relations and never match across packages.

### Claims-only default

By default, only `claim` nodes are canonicalized. Settings, questions, and actions remain package-local unless explicitly included via `canonicalizable_types` configuration. The rationale: claims are truth-apt propositions that participate in BP and benefit from cross-package identity.

### Factor lifting

After node canonicalization, local factors are rewritten with global IDs:

1. Build `lcn_ -> gcn_` mapping from bindings.
2. Build `ext: -> gcn_` mapping from global node metadata (`source_knowledge_names`).
3. For each local factor, resolve all premise, context, and conclusion IDs.
4. Factors with unresolved references are dropped (logged in `unresolved_cross_refs`).

For server-side implementation details, see `../lkm/global-canonicalization.md`.

## Source

- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
