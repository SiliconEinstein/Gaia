# Graph IR

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-12 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [language/gaia-language-spec.md](language/gaia-language-spec.md), [language/gaia-language-design.md](language/gaia-language-design.md), [review/publish-pipeline.md](review/publish-pipeline.md), [review/package-artifact-profiles.md](review/package-artifact-profiles.md), [theory/scientific-ontology.md](theory/scientific-ontology.md), [theory/inference-theory.md](theory/inference-theory.md), [bp-on-graph-ir.md](bp-on-graph-ir.md) — BP on Graph IR, [server/storage-schema.md](server/storage-schema.md) |
| V1 实现 specs | [../../superpowers/specs/2026-03-17-simplified-global-canonicalization-design.md](../../superpowers/specs/2026-03-17-simplified-global-canonicalization-design.md) — 简化版 Global Canonicalization, [../../superpowers/specs/2026-03-17-curation-service-design.md](../../superpowers/specs/2026-03-17-curation-service-design.md) — Curation Service |

---

## 1. Purpose

This document defines the Graph IR — a structural factor graph intermediate representation that sits between Gaia Language and belief propagation.

Gaia Language is the authored surface. Graph IR is the submitted structural form that machines reason over. BP runs on Graph IR plus either an author-local parameterization overlay or a registry-managed global inference state, not on the language surface directly.

This document is **structural first**. It defines the submitted graph shape and identity layers. Exact BP runtime lowering rules may evolve and are defined by [theory/inference-theory.md](theory/inference-theory.md) and [bp-on-graph-ir.md](bp-on-graph-ir.md). Readers should not treat every current runtime choice described here as a permanent ontology commitment.

## 2. Problem

The current architecture compiles factor graphs directly from ChainExpr structures as ephemeral runtime artifacts. Storage-schema.md states: "因子图不持久存储，每次 BP 运行时从 Knowledge + Chain + ProbabilityRecord 动态构建."

This causes:

1. **No canonical identity** — the same proposition in different languages, packages, or editorial styles has no mechanism to be recognized as the same knowledge
2. **No schema/ground distinction** — universally quantified propositions and their concrete instances are not formally distinguished
3. **BP coupled to authoring surface** — two separate compilation paths (hypergraph and DSL) with no shared canonical form
4. **No auditable lowering** — the mapping from source to factor graph is implicit

## 3. Solution

Add Graph IR as an explicit layer between Gaia Language and BP.

```
Gaia Lang Source (authored package source)
    │
    ▼
gaia build (compile + elaborate + IR generation, deterministic)
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
Agent skill: local parameterization (non-submitted)
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
Server/global BP runs on
(Global Canonical Graph + registry-managed GlobalInferenceState)
```

Graph IR is a **first-class submission artifact**. The package submits both its deterministic raw graph and its package-local canonical graph during `gaia publish`; author-local priors and factor probabilities are intentionally excluded. The review layer records probability judgments in the review report, and the registry then maps package-local canonical nodes into the global graph and maintains a global inference state.

## 4. Factor Graph Structure

Graph IR is a factor graph — a bipartite graph with knowledge-bearing nodes plus factor nodes. The key distinction is that knowledge identity exists at three layers:

1. **RawKnowledgeNode** — deterministic output of `gaia build`
2. **LocalCanonicalNode** — package-scoped semantic identity produced by agent canonicalization
3. **GlobalCanonicalNode** — review/registry-assigned global identity in the merged graph

The factor schema is shared across all three layers. Only the node ID namespace changes.

### 4.1 Raw Knowledge Nodes

`RawKnowledgeNode` is the deterministic, source-faithful node emitted by `gaia build`.

```
RawKnowledgeNode:
    raw_node_id:     str              # content hash: sha256(knowledge_type + content + sorted(parameters))
    knowledge_type:  str              # claim | setting | question | action |
                                      # contradiction | equivalence
    kind:            str | None       # root-type-specific kind label; for Question/Action
                                      # equivalence in V1 requires same root type and same kind
    content:         str              # node content (may contain parameter placeholders like {X})
    parameters:      list[Parameter]  # empty = ground node, non-empty = schema node (∀-quantified)
    source_refs:     list[SourceRef]  # traces back to Gaia Lang source objects
    metadata:        dict | None      # optional extensible metadata

Parameter:
    name:            str              # placeholder name, e.g. "A", "X"
    constraint:      str              # constraint description (includes knowledge type and semantic limits)

SourceRef:
    package:         str
    version:         str              # package semver, e.g. "1.2.0"
    module:          str
    knowledge_name:  str
```

Only byte-identical elaborated content is merged at this layer. Semantic equivalence is deferred.

### 4.2 Local Canonical Nodes

`LocalCanonicalNode` is a package-scoped semantic identity produced by the canonicalization skill. Every raw node maps to exactly one local canonical node. Singletons are allowed; semantic merges produce multi-member local canonical nodes.

```
LocalCanonicalNode:
    local_canonical_id: str             # stable ID for this package-local merge set
    package:            str
    knowledge_type:     str
    kind:               str | None
    representative_content: str
    parameters:         list[Parameter]
    member_raw_node_ids: list[str]      # one or more RawKnowledgeNode IDs
    source_refs:        list[SourceRef]
    metadata:           dict | None
```

`LocalCanonicalNode` is structural only. It does not store priors, posteriors, or factor probabilities. Author-local inference parameters may be derived after canonicalization, but they are not part of the submitted Graph IR.

### 4.3 Global Canonical Nodes

`GlobalCanonicalNode` is assigned by the review/registry layer after publish. It is not authored locally and is not chosen by the package agent.

```
GlobalCanonicalNode:
    global_canonical_id: str
    knowledge_type:      str
    kind:                str | None
    representative_content: str
    parameters:          list[Parameter]
    member_local_nodes:  list[LocalCanonicalRef]
    provenance:          list[PackageRef]
    metadata:            dict | None

LocalCanonicalRef:
    package:             str
    version:             str
    local_canonical_id:  str

PackageRef:
    package:             str
    version:             str
```

`GlobalCanonicalNode` is also structural only. Review/server-side priors and BP state are maintained outside the submitted graph and are discussed in [bp-on-graph-ir.md](bp-on-graph-ir.md).

`global_canonical_id` is registry-assigned and opaque. V1 recommends a stable non-semantic format such as `gcn_<ULID>`. New IDs are allocated only when a binding decision is `create_new`; `match_existing` always reuses the existing global ID. Global IDs do not encode content, type, or provenance.

### 4.4 Canonical Bindings

`CanonicalBinding` is a **review/registry-side identity record**. It is not authored in Gaia Lang, not submitted by the package, and not part of the BP graph itself. Its only job is to record which GlobalCanonicalNode a package's LocalCanonicalNode maps to after review.

```
CanonicalBinding:
    package:              str
    version:              str
    local_graph_hash:     str
    local_canonical_id:   str
    decision:             str              # match_existing | create_new
    global_canonical_id:  str
    decided_at:           str              # timestamp
    decided_by:           str
    reason:               str | None
```

**CanonicalBinding constraints:**

- Each `(package, version, local_graph_hash, local_canonical_id)` has exactly one approved binding.
- A binding points to exactly one `global_canonical_id`.
- Multiple local nodes from different packages may bind to the same global node.
- For `question` and `action`, binding is only valid when root type and `kind` both match.
- `CanonicalBinding` expresses identity assignment only. Relations such as `refines`, `contradicts`, or `missing_ref` stay in review findings and/or global graph relations; they are not encoded in the binding record.

### 4.5 Global Inference State

`GlobalInferenceState` is registry-managed runtime state for the global graph. V1 keeps priors and current beliefs together in one object rather than splitting them into separate layers.

```
GlobalInferenceState:
    graph_hash:          str
    node_priors:         dict[str, float]   # keyed by full global_canonical_id
    factor_parameters:   dict[str, FactorParams]
    node_beliefs:        dict[str, float]   # keyed by full global_canonical_id
    updated_at:          str
```

`GlobalInferenceState` is not a package artifact. It is derived and maintained by the registry from approved review reports, CanonicalBinding records, and the current Global Canonical Graph.

### 4.6 Factor Nodes

Factors define constraints between knowledge nodes. They carry no belief. Each factor is self-contained: it directly references its connected knowledge nodes.

```
FactorNode:
    factor_id:              str
    type:                   str              # reasoning | instantiation |
                                             # mutex_constraint | equiv_constraint
    premises:               list[str]        # node IDs in this graph layer
    contexts:               list[str]        # node IDs in this graph layer
    conclusion:             str              # node ID in this graph layer (singular)
    source_ref:             SourceRef | None
    metadata:               dict | None      # optional extensible metadata
```

**Field semantics:**

- `premises` — knowledge nodes with strong, load-bearing dependency. If a premise is false, the conclusion's validity is undermined.
- `contexts` — knowledge nodes with weak/background dependency. Contexts do not create BP edges; their influence is consumed later by either local parameterization or registry-side global inference-state updates when a reasoning-factor probability is assigned.
- `irrelevant` is a valid review/self-review classification for a mentioned reference or candidate, but it does not appear in Graph IR factor connectivity. V1 Graph IR only stores `premises` and `contexts`.
- `conclusion` — the single knowledge node produced or controlled by this factor. For reasoning and instantiation factors, this is the reasoning conclusion that receives BP messages normally. For constraint factors (`mutex_constraint`, `equiv_constraint`), current runtime references still use the Relation knowledge node here. Whether that relation behaves as a read-only gate or a full BP participant is a **runtime-lowering question**, not a structural Graph IR requirement; see [bp-on-graph-ir.md](bp-on-graph-ir.md) and [theory/inference-theory.md](theory/inference-theory.md).

In a raw graph these IDs are `raw_node_id`s. In a local canonical graph they are `local_canonical_id`s. In the global graph they are `global_canonical_id`s.

**Cross-package reference lowering (V1):**

- Author-facing source references remain package-scoped. Search and registry layers may surface server-side canonical identities, but submitted package source still records a reference to a concrete package knowledge unit rather than to a `global_canonical_id`.
- Exported external knowledge may lower to either `premises` or `contexts`, depending on its authored dependency role.
- Non-exported external knowledge may be referenced only as `context`. It does not provide an independent cross-package premise-bearing interface until the source package promotes it to `export`.

### 4.7 Factor Types

The factor type names below are the **current structural schema identifiers** used in Graph IR and storage-adjacent code paths. They should be read separately from the higher-level operator families in [theory/inference-theory.md](theory/inference-theory.md), which may use cleaner target-design terminology.

| Factor type | Generated by | premises | contexts | conclusion | Extra runtime parameterization |
|-------------|-------------|----------|----------|------------|------------------------------|
| `reasoning` | ChainExpr | direct-dep knowledge nodes | indirect-dep knowledge nodes | reasoning conclusion | `conditional_probability` supplied outside Graph IR |
| `instantiation` | Elaboration | `[schema node]` | `[]` | instance node | None (deterministic) |
| `mutex_constraint` | Contradiction declaration | constrained claim nodes | `[]` | Contradiction node (read-only gate) | Gate node prior supplied outside Graph IR |
| `equiv_constraint` | Equivalence declaration | equated claim nodes | `[]` | Equivalence node (read-only gate) | Gate node prior supplied outside Graph IR |

**Reasoning factor granularity:** one FactorNode per ChainExpr (not per step). A ChainExpr represents one complete reasoning unit from premises to conclusion. Intermediate steps within the chain are internal to the factor and do not appear as separate knowledge nodes. See §6.1 for the generation rule.

**Constraint factor note:** for `mutex_constraint` and `equiv_constraint`, the `conclusion` field currently holds the Relation knowledge node. Historical runtime paths interpret this as a read-only gate. Target BP theory may instead treat the relation as a normal participant. The structural Graph IR schema does not by itself settle that runtime question.

### 4.8 Factor Functions

Each factor type defines a potential function. Summary:

| Factor type | Key semantics |
|-------------|--------------|
| `reasoning` | All premises true → conclusion follows with a parameterized `conditional_probability` |
| `instantiation` | Deterministic implication: schema=true → instance=true |
| `mutex_constraint` | Penalizes all contradicted claims being simultaneously true |
| `equiv_constraint` | Rewards agreement between equated claims |

For detailed factor function definitions, BP behavior, and gate semantics for Relations, see [bp-on-graph-ir.md](bp-on-graph-ir.md).

### 4.9 Type-Specific BP Semantics (V1)

Graph IR may preserve multiple authored root types, but they do not all become ordinary domain-BP variables:

| Root type | `node = true` means | May appear as premise? | May appear as conclusion? |
|-----------|---------------------|------------------------|---------------------------|
| `claim` | the asserted proposition holds | Yes | Yes |
| `setting` | the contextual assumption/definition holds | Yes | Yes |
| `question` | inquiry artifact; not a default truth-apt domain proposition | No | No (unless a specialized runtime lowering says otherwise) |
| `action` | procedural declaration; not a default truth-apt domain proposition | Lowering-specific, not directly | Lowering-specific, not directly |
| `contradiction` / `equivalence` | the relation itself holds | Yes | Yes |

V1 relation constraints:

- `Equivalence` is type-preserving.
- For structurally preserved `question` and `action` nodes, `Equivalence` is only valid between nodes with the same root type and the same `kind`.
- `Contradiction` is only defined for `claim`, `setting`, and relation nodes in V1; it is not defined for `question` or bare `action` declarations.

## 5. Schema and Ground Nodes

### 5.1 Definition

After `gaia build` elaboration, some knowledge objects may still contain unbound parameters (placeholders like `{X}`). These represent universally quantified propositions.

- **Schema node**: `parameters` is non-empty. Semantics: `∀x. P(x)`.
- **Ground node**: `parameters` is empty. Semantics: `P(a)`.

A partially instantiated node with k remaining unbound parameters out of n total is also a schema node — it represents `∀x₁...xₖ. P(a₁, ..., aₙ₋ₖ, x₁, ..., xₖ)`.

### 5.2 Instantiation

Instantiation is the relationship between a schema and its ground instance, produced deterministically by elaboration. It is modeled as a **factor node** (not a knowledge node) because it carries no uncertainty — if the substitution is correct, the instantiation holds.

Each instantiation factor is **binary** — it connects exactly one schema node (premise) to one instance node (conclusion):

```
V_schema ─── F_instantiation ─── V_partial
    premises:   [V_schema]
    conclusion: V_partial

V_partial ─── F_instantiation ─── V_ground
    premises:   [V_partial]
    conclusion: V_ground
```

The deductive direction (schema → instance) is modeled by `premises=[schema], conclusion=instance`. Inductive strengthening (multiple instances supporting the schema) emerges naturally from BP: each instantiation factor sends a backward message to the shared schema node, and BP aggregates these messages at the schema node.

The instantiation factor's implication semantics ensure:

- Instance belief drops → schema belief drops (counterexample weakens universal)
- Schema belief high → all instances receive support
- Multiple high-belief instances → inductive strengthening of schema (via BP message aggregation at the shared schema node)

### 5.3 All Knowledge Types Can Be Parameterized

Parameters are not limited to Actions. Any knowledge type can have parameters:

```
Schema claim:    "在{X}条件下，{Y}是混淆变量"
Ground claim:    "在落体实验条件下，空气阻力是混淆变量"

Schema setting:  "{X}环境下的{Y}实验条件"
Ground setting:  "真空环境下的落体实验条件"

Schema action:   "对{A}和{B}进行对比分析"
Ground action:   "对亚里士多德假说和真空环境进行对比分析"
```

## 6. Build: Deterministic Graph IR Generation

`gaia build` generates raw Graph IR deterministically from elaborated source. No LLM, no judgment.

### 6.1 Generation Rules

| Source construct | Raw knowledge node(s) generated | Factor node(s) generated |
|-----------------|--------------------------------|--------------------------|
| Claim, Setting, Question, Action | One RawKnowledgeNode per elaborated object | — |
| Contradiction declaration | Contradiction RawKnowledgeNode | mutex_constraint factor |
| Equivalence declaration | Equivalence RawKnowledgeNode | equiv_constraint factor |
| ChainExpr | — | One reasoning factor per ChainExpr |
| Elaboration instantiation | — | One instantiation factor per schema→instance pair |

### 6.2 Build-Time Merge

Only one case merges at build time: **content hash identity**. If two elaborated knowledge objects produce byte-identical content after elaboration, they map to the same RawKnowledgeNode with combined `source_refs`.

Equivalence declarations are NOT merged at build time. They become Equivalence RawKnowledgeNodes + equiv_constraint factors in the raw Graph IR. Whether to merge the equated nodes is a package-local or global canonicalization judgment.

Question and Action may still be present structurally in Graph IR, but they are not ordinary domain-BP variables by default. Any specialized runtime handling for them belongs to lowering-specific semantics, not to the core Graph IR contract. For cross-package references, only exported external nodes may appear in `premises`; non-exported external references must lower to `contexts`.

### 6.3 Build Output

```
graph_ir/raw_graph.json
```

## 7. Three-Layer Canonicalization

### 7.1 Layer 1: Structural (gaia build, deterministic)

| Operation | Condition | Result |
|-----------|-----------|--------|
| Generate raw knowledge nodes | Each elaborated knowledge object | 1:1 mapping |
| Generate reasoning factors | Each ChainExpr | One factor: premises (direct deps) + contexts (indirect deps) → conclusion |
| Generate instantiation factors | Each schema→instance pair from elaboration | Binary factor: premises=[schema] → conclusion=instance |
| Generate Relation node + constraint factor | Relation declaration | Preserve as knowledge node + factor pair |
| Content hash merge | Byte-identical elaborated content | Merge nodes, combine source_refs |

Output:

```
graph_ir/raw_graph.json
```

### 7.2 Layer 2: Package-Local Semantic Canonicalization (agent skill)

The agent receives raw Graph IR and produces a **package-local canonical graph**. This layer is where semantic equivalence inside one package is normalized.

What the agent does:

1. Examine RawKnowledgeNodes in the raw Graph IR
2. Partition them into package-local equivalence groups
3. Create one LocalCanonicalNode per group
4. Redirect factor references from `raw_node_id` to `local_canonical_id`
5. For Equivalence RawKnowledgeNodes: if confident they hold, their members may share a LocalCanonicalNode and the Equivalence node + factor pair can be removed from the local graph; if uncertain, preserve them as ordinary nodes/factors
6. Record every grouping judgment in a canonicalization log

For `question` and `action` nodes, semantic grouping and equivalence must remain within the same `kind`.

What the agent does NOT do:

- Modify the raw graph
- Change raw-node content, IDs, or source refs
- Inject new review-discovered knowledge directly into the submitted local graph
- Attach external search candidates directly to the submitted local graph
- Create new factor types
- Attach submitted probability parameters to Graph IR

If self-review or search discovers a missing premise, context, or external reference that should become part of the package, the agent must update source explicitly and re-run `gaia build`. Submitted `local_canonical_graph.json` stays package-local: it is a canonicalization of package-owned raw nodes, not a workspace scratch graph.

Output:

```
graph_ir/local_canonical_graph.json
graph_ir/canonicalization_log.json
```

Canonicalization log records only structural grouping decisions:

```yaml
canonicalization_log:
  - local_canonical_id: lcn_007
    members: [raw_007, raw_012]
    reason: "Synonymous: both express 'air resistance is the confounding variable'"
  - local_canonical_id: lcn_003
    members: [raw_003, raw_015]
    reason: "Same proposition in Chinese and English"
```

Every RawKnowledgeNode must map to exactly one LocalCanonicalNode. A one-member local canonical node is valid and is the fallback when no merge is justified.

### 7.3 Local Parameterization (author-local, non-submitted)

After package-local canonicalization, author tooling may derive a **local parameterization overlay** for preview inference. This overlay is not part of Graph IR and is not submitted during `gaia publish`.

Typical local path:

```
graph_ir/local_parameterization.json
```

Minimal shape:

```
Parameterization = {
  schema_version: str
  graph_scope: "local"
  graph_hash: str
  node_priors: dict[str, float]
  factor_parameters: dict[str, FactorParams]
  metadata: dict?
}

FactorParams = {
  conditional_probability: float
}
```

Typical contents include:

- node priors keyed by full `local_canonical_id` or by an unambiguous local ID prefix
- reasoning-factor `conditional_probability` keyed by full `factor_id` or by an unambiguous local ID prefix

The overlay loader resolves local prefixes against the active local graph before BP starts. Prefix lookup is namespace-local (`node_priors` only against `local_canonical_id`s, `factor_parameters` only against `factor_id`s) and must resolve uniquely; ambiguous or missing prefixes make the overlay invalid. Every belief-bearing LocalCanonicalNode and every `reasoning` FactorNode in the active local graph must be parameterized; otherwise the overlay is invalid.

This separation keeps structural submission auditable while allowing local `gaia infer` to use author-side judgment.

### 7.4 Layer 3: Global Canonicalization (review engine / registry)

The review engine uses the package's LocalCanonicalNodes to search the global graph:

1. Embed each LocalCanonicalNode
2. Search existing global graph for high-similarity matches
3. For each local node, choose one of:
   - map to an existing GlobalCanonicalNode
   - create a new GlobalCanonicalNode
4. Record any prior / conditional-probability judgments directly in the review report; these are not taken from the author's local parameterization
5. Agent responds via rebuttal cycle (accept mapping, or rebuttal → explain difference)
6. After approval, the registry records one `CanonicalBinding` per LocalCanonicalNode, updates the target GlobalCanonicalNode's membership/provenance lists, and refreshes `GlobalInferenceState`

Non-identity findings such as `refines`, `contradicts`, or missing references are handled separately through review findings and global graph relations; they are not part of the binding decision itself.

For `question` and `action` nodes, global matching and equivalence must also remain within the same root type and the same `kind`.

This layer owns **global identity assignment**. Package-local canonicalization does not choose the final global identity.

Each layer handles only what it can reliably do, passing unresolved cases to the next.

## 8. Publish and Review

### 8.1 Submission Artifacts

`gaia publish` submits four artifacts:

1. **Gaia Lang source** — source package files (for example Typst package source in v4)
2. **Raw Graph IR** — raw_graph.json
3. **Local Canonical Graph** — local_canonical_graph.json
4. **Canonicalization log** — agent's local grouping decisions

The package does **not** submit `CanonicalBinding`. Binding is created only by the review/registry side after identity assignment.
The package also does **not** submit review-discovered weak-point candidates or ad hoc external search candidates as structural nodes. Those only enter submitted Graph IR after they are written back into source and rebuilt.

### 8.2 Review Engine Verification

**Layer 1: Source ↔ Raw Graph IR correspondence**

The review engine independently executes `gaia build` to produce its own raw Graph IR. It diffs this against the submitted `raw_graph.json`. Any mismatch is a blocking finding.

**Layer 2: Raw → Local canonicalization audit**

The review engine evaluates each LocalCanonicalNode and its log entry:

- Are the grouped raw nodes truly semantically equivalent? (blocking if wrong)
- Are there obvious local equivalences the agent missed? (advisory)

The review engine does **not** read author-local node priors or reasoning probabilities. If the review process makes probability judgments, they are written directly into the review report as `node_prior_judgments` / `factor_probability_judgments` against local node/factor IDs (or unambiguous local short prefixes) under the submitted `local_graph_hash`, rather than emitted as a separate overlay artifact.

**Layer 3: Global matching**

The review engine uses LocalCanonicalNodes to search the global graph for duplicates, conflicts, and missing references. Identity assignment is recorded as `CanonicalBinding`; non-identity findings follow the standard review → rebuttal → editor cycle per [publish-pipeline.md](review/publish-pipeline.md).

### 8.3 Verification Severity

| Check | Failure meaning | Severity |
|-------|----------------|----------|
| Source → raw IR rebuild mismatch | Raw Graph IR tampered or build version mismatch | blocking |
| Unreasonable local merge | Agent package-local canonicalization error | blocking |
| Missed local merge | Agent didn't discover a package-local semantic equivalence | advisory |
| Global duplicate/conflict | Must declare relationship with existing global knowledge | blocking |

## 9. BP Execution

`gaia infer` runs local BP on `local_canonical_graph.json` plus a non-submitted local parameterization overlay. The raw graph is for deterministic rebuild and audit; it is not the local BP input.

After publish and review, server-side BP runs on the global graph over GlobalCanonicalNodes plus registry-managed `GlobalInferenceState`. Review reports may contribute prior/probability judgments, but there is no separate review-side overlay artifact in V1.

For full details on factor functions, gate semantics for Relations, schema/ground interaction during BP, local parameterization overlays, and global inference state, see [bp-on-graph-ir.md](bp-on-graph-ir.md).

## 10. Relationship to Existing System

### 10.1 What Changes

| Component | Before | After |
|-----------|--------|-------|
| Factor graph status | Ephemeral runtime artifact, not persisted | Raw graph + local canonical graph are first-class package artifacts |
| BP input | Compiled from ChainExpr or from Knowledge+Chain storage | Local BP runs on local canonical graph + local parameterization; server BP runs on global graph + `GlobalInferenceState` |
| Compilation paths | Two: DSL (CompiledFactorGraph) + hypergraph (from_subgraph) | One: build → Graph IR → BP |
| Canonicalization | None | Three-layer: structural raw nodes → package-local canonical nodes → global canonical nodes |
| Publish artifact | Source only | Source + raw graph + local canonical graph + canonicalization log |
| Review scope | Source review only | Source + raw rebuild + local canonicalization audit + review-report probability judgments + global matching |
| Node identity | int (FactorGraph) or name string (CompiledFactorGraph) | raw_node_id / local_canonical_id / global_canonical_id |
| Schema/ground | Not distinguished | Explicit via parameters + instantiation factors |

### 10.2 What Does NOT Change

- Gaia Lang source syntax and semantics
- Package structure as the authored package artifact
- CLI commands (build, infer, publish)
- Publish pipeline flow (self-review → canonicalization / optional local parameterization → publish → peer review)
- Relation type design (Contradiction, Equivalence as Knowledge root types)
- Review → rebuttal → editor cycle
- BP algorithm (sum-product with damping)
- Cromwell's rule enforcement

### 10.3 Storage Impact

Storage-schema.md currently states that factor graphs are not persisted. Under Graph IR:

- Raw Graph IR and Local Canonical Graph are persisted as package-level artifacts (alongside source)
- The storage layer needs to store or reference both `raw_graph.json` and `local_canonical_graph.json`
- The global graph additionally stores review/registry-managed GlobalCanonicalNodes plus `CanonicalBinding` records
- The existing `load_all_knowledge() + load_all_chains() → dynamic factor graph` path is progressively replaced by loading the persisted canonical graph directly
- Author-local parameterization overlays are local tooling artifacts, not publish artifacts
- Global runtime priors and beliefs live together in `GlobalInferenceState`
- Any persisted runtime probability data must use the explicit graph-layer identifiers (`local_canonical_id` / `global_canonical_id` internally, with any local short-ID prefixes resolved before inference)

### 10.4 Compilation Path Unification

The two existing compilation paths converge:

```
Before:
  CLI:    Gaia Lang → compile_factor_graph() → CompiledFactorGraph → FactorGraph → BP
  Server: Storage → FactorGraph.from_subgraph() → FactorGraph → BP

After:
  Unified: Gaia Lang → gaia build → raw Graph IR
                         → agent canonicalize → local canonical graph
                         → local parameterization → local BP
           gaia publish → raw + local canonical stored
                         → review report judgments + global canonicalization
                         → registry GlobalInferenceState + global BP
```

`FactorGraph.from_subgraph()` and `CompiledFactorGraph` become unnecessary once the canonical graph layers are the canonical input to BP.

## 11. V1 Implementation Status

### 11.1 Implemented

| 功能 | 状态 | 实现位置 |
|------|------|---------|
| Raw graph generation (`gaia build`) | ✓ | `libs/graph_ir/build.py` |
| Singleton local canonicalization | ✓ | `libs/graph_ir/build.py` |
| Local parameterization derivation | ✓ | `libs/graph_ir/build.py` |
| Elaboration (schema → ground + instantiation factor) | ✓ | `libs/graph_ir/build.py` |
| Retraction factor generation | ✓ | `libs/graph_ir/build.py` |
| Local BP on Graph IR | ✓ | `scripts/pipeline/run_local_bp.py` |
| Graph IR fixture viewer (frontend) | ✓ | `frontend/src/pages/v2/GraphIRViewer.tsx` |
| Graph IR output directory | ✓ | `graph_ir/` (was `.gaia/graph/`) |

### 11.2 Next: Simplified Global Canonicalization

Spec: [../../superpowers/specs/2026-03-17-simplified-global-canonicalization-design.md](../../superpowers/specs/2026-03-17-simplified-global-canonicalization-design.md)

Minimal subset of §7.4: automatic identity assignment (local node → global node) at publish time via embedding similarity. Skips rebuttal cycle and probability judgments. Conservative threshold — curation corrects missed merges later.

### 11.3 Next: Curation Service

Spec: [../../superpowers/specs/2026-03-17-curation-service-design.md](../../superpowers/specs/2026-03-17-curation-service-design.md)

Offline global graph maintenance: clustering, classification (dedup/equivalence/abstraction/induction), conflict discovery (3-level BP pipeline), structure inspection, cleanup with 3-tier auto-execution.

### 11.4 Future

- Complete review engine with rebuttal cycle and independent probability judgments
- Per-premise leak (heterogeneous noisy-AND) — see [issue #150](https://github.com/SiliconEinstein/Gaia/issues/150)
- Frozen external beliefs for local BP cross-package refs — see [issue #152](https://github.com/SiliconEinstein/Gaia/issues/152)
- LLM-based contradiction detection (curation Level 3)
- Abstraction / induction auto-creation in curation

## 12. Open Questions

1. **Graph IR serialization format** — JSON is natural for factor graph structure; YAML for human readability. Binary formats for performance.
2. **Parameter placeholder syntax** — how to consistently represent `{X}` placeholders in content strings across packages.
3. **Graph IR schema versioning** — version marker for the IR format itself.
4. **Incremental build** — can `gaia build` incrementally update raw/local graphs when only some modules change?
5. **Review-to-registry probability flow** — how review-report probability judgments are normalized and incorporated into `GlobalInferenceState`.
6. **Global graph storage** — how GlobalCanonicalNodes, `CanonicalBinding` records, and `GlobalInferenceState` are stored and indexed. Extends storage-schema.md.
