# Graph IR Design

> **Date:** 2026-03-12
> **Status:** Approved design
> **Related docs:**
> - [Gaia Language Spec](../foundations/language/gaia-language-spec.md)
> - [Gaia Language Design](../foundations/language/gaia-language-design.md)
> - [Relation Type Design](2026-03-10-relation-type-design.md)
> - [Publish Pipeline](../foundations/review/publish-pipeline.md)
> - [Type System Direction](../foundations/language/type-system-direction.md)

## Problem

The current Gaia architecture has no explicit intermediate representation between the Gaia Lang surface (authored YAML) and BP execution. Factor graphs are compiled directly from ChainExpr structures as runtime artifacts with no formal identity, canonicalization, or schema/ground distinction.

This causes several problems:

1. **No canonical identity** — the same proposition expressed in different languages, packages, or editorial styles has no mechanism to be recognized as the same knowledge
2. **No schema/ground distinction** — universally quantified propositions (with free variables) and their concrete instances are not formally distinguished, losing the logical relationship between them
3. **BP runs on raw language surface** — tightly coupling inference to authoring syntax
4. **No auditable lowering** — the mapping from source to factor graph is implicit, making review and verification difficult

## Solution

Add an explicit **Graph IR** layer — a factor graph intermediate representation that sits between Gaia Lang and BP.

```
Gaia Lang Source (authored YAML)
    │
    ▼
gaia build (deterministic compile + elaborate + IR generation)
    │
    ▼
Raw Graph IR
(RawKnowledgeNode + FactorNode, 1:1 source mapping)
    │
    ▼
Agent skill: package-local canonicalization
    │
    ▼
Local Canonical Graph
(LocalCanonicalNode + FactorNode, package-scoped semantic merge)
    │
    ▼
author-local parameterization (non-submitted)
    │
    ▼
gaia infer — local BP runs on
(Local Canonical Graph + local parameterization)
    │
    ▼
gaia publish — submit
(source + raw graph + local canonical graph + canonicalization log)
    │
    ▼
Review Engine — verify raw rebuild, audit local canonicalization,
                write review report judgments, global matching
    │
    ▼
Global Canonical Graph
(GlobalCanonicalNode + review/registry-managed CanonicalBinding records)
    │
    ▼
registry GlobalInferenceState + global BP
```

**Graph IR is a first-class submission artifact**, not an internal build byproduct. The package submits both its deterministic raw graph and its package-local canonical graph during `gaia publish`; author-local probabilities are intentionally excluded, review writes any probability judgments into the review report, and the registry maintains the global inference state.

## Factor Graph Structure

Graph IR is a factor graph — a bipartite graph with knowledge-bearing nodes plus factor nodes. The key distinction is that knowledge identity exists at three layers:

1. **RawKnowledgeNode** — deterministic output of `gaia build`
2. **LocalCanonicalNode** — package-scoped semantic identity produced by agent canonicalization
3. **GlobalCanonicalNode** — review/registry-assigned global identity in the merged graph

The factor schema is shared across all three layers. Only the node ID namespace changes.

### Raw Knowledge Nodes

```
RawKnowledgeNode = {
  raw_node_id: str
  knowledge_type: str
  kind: str | None
  content: str
  parameters: [Parameter]
  source_refs: [SourceRef]
  metadata: dict?
}

Parameter = {
  name: str
  constraint: str
}

SourceRef = {
  package: str
  version: str
  module: str
  knowledge_name: str
}
```

Only byte-identical elaborated content is merged at this layer. Semantic equivalence is deferred.

### Local Canonical Nodes

```
LocalCanonicalNode = {
  local_canonical_id: str
  package: str
  knowledge_type: str
  kind: str | None
  representative_content: str
  parameters: [Parameter]
  member_raw_node_ids: [str]
  source_refs: [SourceRef]
  metadata: dict?
}
```

`LocalCanonicalNode` is structural only. Local priors and reasoning probabilities live in a separate author-local parameterization overlay and are not submitted.

### Global Canonical Nodes

```
GlobalCanonicalNode = {
  global_canonical_id: str
  knowledge_type: str
  kind: str | None
  representative_content: str
  parameters: [Parameter]
  member_local_nodes: [LocalCanonicalRef]
  provenance: [PackageRef]
  metadata: dict?
}

LocalCanonicalRef = {
  package: str
  version: str
  local_canonical_id: str
}

PackageRef = {
  package: str
  version: str
}
```

`GlobalCanonicalNode` is also structural only. Review/server-side priors and runtime beliefs are supplied by registry-managed `GlobalInferenceState`.

`global_canonical_id` is registry-assigned and opaque. V1 recommends a stable non-semantic format such as `gcn_<ULID>`. New IDs are allocated only when the corresponding binding decision is `create_new`.

### Canonical Bindings

`CanonicalBinding` is review/registry-side metadata, not a Graph IR node or factor. It records which global identity a package-local canonical node maps to after review.

```
CanonicalBinding = {
  package: str
  version: str
  local_graph_hash: str
  local_canonical_id: str
  decision: match_existing | create_new
  global_canonical_id: str
  decided_at: str
  decided_by: str
  reason: str?
}
```

Constraints:

- one approved binding per `(package, version, local_graph_hash, local_canonical_id)`
- one binding points to exactly one `global_canonical_id`
- multiple local nodes may bind to the same global node
- for `question` and `action`, binding requires same root type and same `kind`
- non-identity relations (`refines`, `contradicts`, `missing_ref`) are handled separately and are not part of `CanonicalBinding`

### Global Inference State

```
GlobalInferenceState = {
  graph_hash: str
  node_priors: dict[str, float]
  factor_parameters: dict[str, FactorParams]
  node_beliefs: dict[str, float]
  updated_at: str
}
```

`GlobalInferenceState` is registry-managed runtime state derived from approved review reports, `CanonicalBinding`, and the current global graph.

### Factor Nodes

Factors define constraints between knowledge nodes. They carry no belief. Each factor is self-contained: it directly references its connected knowledge nodes.

```
FactorNode = {
  factor_id: str
  type: reasoning | instantiation | mutex_constraint | equiv_constraint
  premises: [str]
  contexts: [str]
  conclusion: str
  source_ref: SourceRef?
  metadata: dict?
}
```

Field semantics:

- `premises` — direct-dependency knowledge nodes
- `contexts` — indirect-dependency knowledge nodes; no BP edges, influence folded into a separately generated reasoning-factor probability
- `conclusion` — the single knowledge node produced or controlled by the factor

In a raw graph these IDs are `raw_node_id`s. In a local canonical graph they are `local_canonical_id`s. In the global graph they are `global_canonical_id`s.

### Factor Types

| Factor type | Generated by | Connects | Factor function |
|-------------|-------------|----------|-----------------|
| `reasoning` | chain_expr apply/lambda step | premise variables ↔ conclusion variables | Standard reasoning reliability factor |
| `instantiation` | Elaboration (schema → ground) | schema variable ↔ ground variable | Implication: schema=true → instance=true |
| `mutex_constraint` | Contradiction variable node | Contradiction node ↔ contradicted nodes | `f(a,b,e) = e·(1-a·b) + (1-e)·1` |
| `equiv_constraint` | Equivalence variable node | Equivalence node ↔ equated nodes | `f(a,b,e) = e·exp(-λ(a-b)²) + (1-e)·1` |

**Relation nodes and their constraint factors always appear as pairs.** The Relation node's runtime belief controls the constraint factor's strength; its prior comes from local overlay or registry `GlobalInferenceState`, depending on the active graph layer.

### Type-Specific BP Semantics

| Root type | `node = true` means | May appear as premise? | May appear as conclusion? |
|-----------|---------------------|------------------------|---------------------------|
| `claim` | the asserted proposition holds | Yes | Yes |
| `setting` | the contextual assumption/definition holds | Yes | Yes |
| `question` | the question is valid, well-posed, and sufficiently motivated | No | Yes |
| `action` | the action is admissible or appropriate in context | Yes | Yes |
| `contradiction` / `equivalence` | the relation itself holds | Yes | Yes |

V1 relation constraints:

- `Equivalence` is type-preserving.
- For `question` and `action`, `Equivalence` is only valid between nodes with the same root type and the same `kind`.
- `Contradiction` is only defined for `claim`, `setting`, and `relation` nodes in V1; it is not defined for `question` or `action`.

## Schema and Ground Nodes

After `gaia build` elaboration, some knowledge objects may still contain free variables. These represent universally quantified propositions.

### Definition

- **Schema node**: `parameters` is non-empty. Semantics: `∀x. P(x)` — for all valid substitutions, the proposition holds.
- **Ground node**: `parameters` is empty. Semantics: `P(a)` — a concrete proposition about specific objects.

### Example

```
Schema:          "对{A}和{B}进行对比分析"        parameters: [A, B]
Partial ground:  "对{A}和真空环境进行对比分析"     parameters: [A]
Full ground:     "对亚里士多德假说和真空环境进行对比分析"  parameters: []
```

### Instantiation Factor

Instantiation is a structural relationship produced deterministically by elaboration. It is modeled as a factor node (not a variable node) because it has no uncertainty — if the substitution is correct, the instantiation holds.

```
V_schema ─── F_instantiation(bindings={B: vacuum}) ─── V_partial_ground
V_partial_ground ─── F_instantiation(bindings={A: aristotle}) ─── V_full_ground
```

BP semantics (implication factor):

| schema | instance | factor value |
|--------|----------|-------------|
| true | true | 1.0 — consistent |
| true | false | 0.0 — contradiction: universal holds but instance doesn't |
| false | true | 1.0 — instance can hold without universal |
| false | false | 1.0 — consistent |

BP naturally propagates:
- Instance belief drops → schema belief drops (counterexample weakens universal)
- Schema belief high → all instances receive support
- Multiple instances with high belief → inductive strengthening of schema

## Build: Deterministic Graph IR Generation

`gaia build` generates raw Graph IR deterministically from elaborated source. No LLM, no judgment.

### Generation Rules

| Source construct | Variable node(s) | Factor node(s) |
|-----------------|-------------------|-----------------|
| Claim, Setting, Question, Action | One raw knowledge node per elaborated object | — |
| Contradiction declaration | Contradiction variable node | mutex_constraint factor |
| Equivalence declaration | Equivalence variable node | equiv_constraint factor |
| chain_expr apply/lambda step | — | reasoning factor |
| Elaboration instantiation | — | instantiation factor + bindings |

### Automatic Merge (build-time, deterministic)

Only one case merges at build time: **content hash identity**. If two elaborated knowledge objects produce byte-identical content, they map to the same raw knowledge node. `source_refs` of both are combined.

**Equivalence declarations are NOT merged at build time.** They become Equivalence knowledge nodes + equiv_constraint factors in the raw Graph IR. Whether to merge the equated nodes is an agent judgment (Layer 2) or review engine judgment (Layer 3).

Question nodes may only appear as factor conclusions in V1. Action nodes may appear as either premises or conclusions.

### Build Output

```
.gaia/graph/raw_graph.json    -- raw Graph IR (factor graph)
```

## Agent Canonicalization

The agent skill receives raw Graph IR and performs **package-local semantic canonicalization**.

### What the Agent Does

1. Examine raw knowledge nodes in the raw Graph IR
2. Partition nodes that express the same proposition despite different content (e.g. different languages, editorial variants, synonymous phrasing)
3. Create one `LocalCanonicalNode` per package-local equivalence group
4. Redirect all factor references from `raw_node_id` to the new `local_canonical_id`
5. Record the structural grouping decision in a canonicalization log

For `question` and `action` nodes, semantic grouping and equivalence must remain within the same `kind`.

### What the Agent Does NOT Do

- Modify raw graph contents
- Rewrite raw node contents, IDs, or source refs
- Attach submitted probability parameters to Graph IR

### Equivalence Node Handling

When the agent encounters an Equivalence variable node (from author declaration):

| Agent judgment | Action |
|----------------|--------|
| Confident the equivalence holds | Create a local canonical merge set, redirect factor refs to the `LocalCanonicalNode`, remove Equivalence node + equiv factor pair if no longer needed |
| Uncertain | Leave Equivalence node + equiv factor in Graph IR for BP to reason about |

### Output

```
.gaia/graph/local_canonical_graph.json     -- package-local canonical Graph IR
.gaia/graph/canonicalization_log.json -- merge decisions with reasons
```

Canonicalization log format:

```yaml
canonicalization_log:
  - local_canonical_id: lcn_001
    members: [rn_007, rn_012]
    reason: "Synonymous: both express 'air resistance is the confounding variable'"
  - local_canonical_id: lcn_002
    members: [rn_003, rn_015]
    reason: "Same proposition in Chinese and English"
```

## BP Execution

`gaia infer` runs BP on the **package-local canonical graph** plus a non-submitted local parameterization overlay. Raw Graph IR is audit input, not the runtime inference graph.

Minimal local overlay shape:

```
Parameterization = {
  schema_version: str
  graph_scope: "local"
  graph_hash: str
  node_priors: dict[str, float]        # keyed by local_canonical_id or unambiguous local ID prefix
  factor_parameters: dict[str, FactorParams]
  metadata: dict?
}

FactorParams = {
  conditional_probability: float
}
```

The loader resolves local ID prefixes against the active local graph before BP. Prefix lookup is namespace-local and must be unambiguous. Every belief-bearing LocalCanonicalNode and every `reasoning` FactorNode in the active local graph must be parameterized.

Variable nodes send messages to their connected factor nodes. Factor nodes send messages back to their connected variable nodes. Messages iterate until convergence.

All factor types (reasoning, instantiation, mutex_constraint, equiv_constraint) participate in BP through their respective factor functions.

## Publish and Review

### Submission

`gaia publish` submits four artifacts:

1. **Gaia Lang source** — package.yaml + module YAMLs
2. **Raw Graph IR** — raw_graph.json
3. **Local canonical Graph IR** — local_canonical_graph.json
4. **Canonicalization log** — agent's merge decisions with reasons

### Review Engine Verification

The review engine performs three layers of verification:

**Layer 1: Source ↔ raw Graph IR correspondence**

Review engine independently executes `gaia build` (re-compile + re-elaborate) to produce its own raw Graph IR. It diffs this against the submitted raw Graph IR. Any unexplained differences are a blocking finding.

**Layer 2: Canonicalization audit**

Review engine evaluates each local canonicalization decision:
- Are the merged raw nodes truly semantically equivalent? (blocking if wrong)
- Are there obvious equivalences the agent missed? (advisory)

Review engine does not consume the author's local priors or reasoning probabilities. If it makes probability judgments, they are written directly into the review report under the submitted `local_graph_hash`.

**Layer 3: Global matching**

Review engine uses the submitted local canonical nodes to search the global graph:
- Finds duplicate, conflicting, or related existing knowledge
- Generates findings (duplicate, conflict, missing_ref, etc.)
- Follows the standard review → rebuttal → editor cycle per publish-pipeline.md

Identity assignment itself is recorded separately as `CanonicalBinding` on the review/registry side. The package does not submit bindings.

For `question` and `action` nodes, global matching and equivalence must also remain within the same root type and the same `kind`.

### Verification Severity

| Check | Failure meaning | Severity |
|-------|----------------|----------|
| Source → raw IR rebuild mismatch | Raw Graph IR tampered or build version mismatch | blocking |
| Unreasonable local merge | Agent canonicalization error | blocking |
| Missed merge | Agent didn't discover a semantic equivalence | advisory |
| Global duplicate/conflict | Must declare relationship with existing knowledge | blocking |

## Three-Layer Canonicalization Summary

```
Layer 1 (structural)     gaia build        deterministic, no LLM      raw-node layer
    ↓ can't catch →
Layer 2 (semantic)       agent skill       judgment, auditable         package-local canonical layer
    ↓ can't catch →
Layer 3 (global)         review engine     global search + review      global canonical layer
```

| Layer | Trigger | Who decides | Scope |
|-------|---------|-------------|-------|
| 1. Structural | `gaia build` | Compiler (content hash, ref resolution) | Within package, deterministic raw nodes |
| 2. Semantic | Agent canonicalization skill | Agent judgment, review engine verifies | Within package, local canonical nodes |
| 3. Global | `gaia publish` → review engine | Review engine + rebuttal cycle | Across all packages, global canonical nodes |

Each layer handles only what it can reliably do, passing unresolved cases to the next layer.

## Relationship to Existing Design

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| BP input | Compiled directly from ChainExpr | Local BP runs on canonical graph + local overlay; global BP runs on canonical graph + `GlobalInferenceState` |
| Factor graph | Runtime artifact, no formal spec | First-class IR with defined schema |
| Canonicalization | Not addressed | Three-layer: raw → local canonical → global canonical |
| Publish artifact | Source only | Source + raw graph + local canonical graph + canonicalization log (no author-local probabilities) |
| Review engine scope | Source review only | Source review + IR correspondence + canonicalization audit + review-report probability judgments |
| Schema/ground | Not distinguished | Explicit via parameters + instantiation factors |

### What Does NOT Change

- Gaia Lang source syntax and semantics
- Package structure (package.yaml + module YAMLs)
- CLI commands (build, infer, publish)
- Publish pipeline flow (self-review → graph construction / optional local parameterization → publish → peer review)
- Relation type design (Contradiction, Equivalence as root types)
- Review → rebuttal → editor cycle

### Publish Pipeline Integration

The existing publish pipeline (publish-pipeline.md) is extended, not replaced:

- `gaia build` now also produces raw Graph IR alongside elaborated artifacts
- The "graph construction" agent skill is refined to "package-local canonicalization" — build creates raw nodes, the agent creates local canonical nodes
- `gaia publish` submits both raw and local canonical Graph IR artifacts alongside source
- Review engine adds correspondence verification and canonicalization audit to its existing responsibilities while optionally writing probability judgments into the review report

## Open Questions

1. **Graph IR serialization format** — YAML vs JSON vs binary. JSON is natural for factor graph structure; YAML for human readability during development.
2. **Local canonical ID generation** — stable within a package, but should it be deterministic or opaque?
3. **Global canonical ID generation** — registry-assigned ID format and collision policy.
4. **Partial ground node representation** — how to represent free variable placeholders in `content` strings consistently across packages.
5. **Graph IR versioning** — schema version for the IR format itself, to support future extensions.
6. **Incremental build** — can `gaia build` incrementally update Graph IR when only some modules change?
