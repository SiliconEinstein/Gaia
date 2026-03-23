# Canonicalization Engine

> **Status:** Current canonical

This document describes the global canonicalization engine as implemented. For the design rationale, see `docs/foundations_archive/graph-ir.md` (sections on global canonical identity).

## What Canonicalization Does

Canonicalization maps local canonical nodes (package-scoped) to global canonical nodes (cross-package). When a new package is ingested, each of its local nodes is either:

- **match_existing**: Bound to an existing `GlobalCanonicalNode` that expresses the same proposition.
- **create_new**: A new `GlobalCanonicalNode` is created for this previously unseen proposition.

This enables the global knowledge graph to recognize that "heavier objects fall faster" in package A and "objects with greater mass descend more quickly" in package B refer to the same claim.

After node canonicalization, local factors are lifted to the global graph by replacing local canonical IDs with global canonical IDs, including resolution of `ext:` cross-package references.

## Pipeline

See `libs/global_graph/canonicalize.py:canonicalize_package()`.

```
Input:
  LocalCanonicalGraph  (from gaia build)
  LocalParameterization
  GlobalGraph  (current global state)

Steps:
  1. Filter to canonicalizable types (default: claims only)
  2. For each local node, find best match in global graph
  3. If match >= threshold → bind to existing global node
  4. If no match → create new global node
  5. Lift local factors to global IDs (resolve lcn_ and ext: references)

Output:
  CanonicalizationResult:
    bindings: list[CanonicalBinding]
    new_global_nodes: list[GlobalCanonicalNode]
    matched_global_nodes: list[str]
    global_factors: list[FactorNode]
    unresolved_cross_refs: list[str]
```

## Match Strategy

See `libs/global_graph/similarity.py:find_best_match()`.

The similarity engine supports two modes:

### Embedding similarity (primary)

When an `EmbeddingModel` is provided, the engine:
1. Batch-embeds the query content and all candidate contents.
2. Computes cosine similarity between the query embedding and each candidate.
3. Returns the best match above the threshold.

### TF-IDF fallback

When no embedding model is available, the engine uses scikit-learn's `TfidfVectorizer` to compute pairwise cosine similarity between the query and each candidate. This is slower and less accurate but requires no external API.

### Match threshold

The default threshold is `0.90` (see `canonicalize.py:MATCH_THRESHOLD`). A match must exceed this threshold to be accepted.

### Filtering rules

Before similarity computation, candidates are filtered:
- **Type match required**: Only candidates with the same `knowledge_type` are eligible.
- **Kind match for some types**: `question` and `action` types additionally require matching `kind`.
- **Relation types excluded**: `contradiction` and `equivalence` are package-local relations and never match across packages.

## Claims-Only Canonicalization

By default, only `claim` nodes are canonicalized. This is configurable via the `canonicalizable_types` parameter (typically set in `pipeline.toml`). Settings, questions, and actions remain package-local unless explicitly included.

The rationale: claims are truth-apt propositions that participate in BP and benefit from cross-package identity. Settings define context; questions frame inquiry; actions describe procedures -- these are typically package-specific.

## GlobalCanonicalNode Structure

Defined in `libs/storage/models.py:GlobalCanonicalNode`:

```
GlobalCanonicalNode:
  global_canonical_id: str        # gcn_{sha256[:16]}
  knowledge_type: str             # claim, question, etc.
  kind: str | None                # sub-classification
  representative_content: str     # content from the first contributing node
  parameters: list[Parameter]     # for schema nodes
  member_local_nodes: list[LocalCanonicalRef]  # all local nodes bound to this
  provenance: list[PackageRef]    # which packages contributed
  metadata: dict | None           # includes source_knowledge_names for ext: resolution
```

The `source_knowledge_names` metadata field enables resolution of `ext:package.name` cross-package references: when a later package references a node from an earlier package, the canonicalization engine can find the corresponding global node.

## Factor Lifting

After node canonicalization, local factors are rewritten with global IDs:

1. Build `lcn_ -> gcn_` mapping from bindings.
2. Build `ext: -> gcn_` mapping from global node metadata (`source_knowledge_names`).
3. For each local factor, resolve all premise, context, and conclusion IDs.
4. Factors with unresolved references are dropped (logged in `unresolved_cross_refs`).

## Current State

The canonicalization engine works for claims-only default mode with both embedding and TF-IDF similarity. Factor lifting resolves both local and cross-package references. The engine is exercised by the server ingestion pipeline and tested in `tests/libs/global_graph/`.

## Target State

The canonicalization engine is stable. No major architectural changes are planned. Potential minor improvements include smarter representative content selection when multiple local nodes merge into one global node, and caching of embeddings to avoid recomputation.
