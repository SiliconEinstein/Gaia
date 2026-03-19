# Belief Propagation on Graph IR

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-19 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [graph-ir.md](graph-ir.md) — Graph IR 结构定义, [theory/inference-theory.md](theory/inference-theory.md) — BP 算法理论, [theory/theoretical-foundation.md](theory/theoretical-foundation.md) — Jaynes 纲领 |

---

## 1. Purpose

This document defines how belief propagation runs on Graph IR. It covers local parameterization overlays, global inference state, factor functions, instantiation factor semantics, and the interaction between schema and ground nodes during BP.

For the Graph IR structure itself (raw nodes, local canonical nodes, global canonical nodes, factor nodes, canonicalization), see [graph-ir.md](graph-ir.md). For general BP theory (sum-product algorithm, damping, convergence), see [theory/inference-theory.md](theory/inference-theory.md).

## 2. BP on the Factor Graph

BP does **not** run on raw Graph IR. Raw Graph IR is the deterministic audit artifact. BP runs on:

- the **Local Canonical Graph + author-local parameterization overlay** for package-local inference (`gaia infer`)
- the **Global Canonical Graph + registry-managed GlobalInferenceState** for server/global inference

Both graphs share the same structural schema, so the BP mechanics below are identical once node references are resolved into the active graph layer and the corresponding probability input is supplied.

Graph IR is a bipartite factor graph. BP runs standard sum-product message passing over the structural graph plus the active probability input:

```
Knowledge nodes ←→ Factor nodes ←→ Knowledge nodes
```

### 2.1 Local Parameterization Overlay

Graph IR deliberately omits priors, posteriors, and reasoning probabilities. Local BP receives them through a separate overlay:

```
Parameterization:
    schema_version: str
    graph_scope: "local" | "global"
    graph_hash: str
    node_priors: dict[str, float]
    factor_parameters: dict[str, FactorParams]
    metadata: dict | None

FactorParams:
    conditional_probability: float          # reasoning factors only
```

This overlay exists only for author-local preview inference.

Local overlay keys are resolved as follows:

- local inference accepts full `local_canonical_id`s or unambiguous local ID prefixes

`factor_parameters` is keyed by `factor_id`. Full IDs or unambiguous `factor_id` prefixes are allowed. A valid overlay must provide priors for every belief-bearing node in the active local graph and `conditional_probability` for every `infer` or `abstraction` factor in that graph. Missing entries make the overlay invalid; BP does not fall back to hidden defaults.

### 2.2 Global Inference State

Global BP consumes a registry-managed runtime object rather than a submitted overlay:

```
GlobalInferenceState:
    graph_hash: str
    node_priors: dict[str, float]         # keyed by full global_canonical_id
    factor_parameters: dict[str, FactorParams]
    node_beliefs: dict[str, float]        # keyed by full global_canonical_id
    updated_at: str
```

`GlobalInferenceState` may be seeded from approved review-report judgments, but the review report is not itself a BP input artifact. Registry/runtime code normalizes those judgments into the current global graph state before BP runs.

Messages are 2-vectors `[p(x=0), p(x=1)]`, always normalized. The algorithm follows the same schedule as inference-theory.md §1.5:

1. Compute all knowledge→factor messages (exclude-self rule)
2. Compute all factor→knowledge messages (marginalize over other variables)
3. Apply damping + normalization
4. Compute beliefs
5. Check convergence

Cromwell's rule: all priors and probabilities are clamped to [ε, 1−ε] (ε = 1e-3) when local overlays or global inference state are loaded, preventing degenerate potentials.

## 3. Factor Functions

Each factor type defines a potential function that determines how messages propagate through it. Factor nodes reference their connected knowledge nodes via the `premises`, `contexts`, and `conclusion` fields defined in [graph-ir.md](graph-ir.md) §4; probability-like values come from the active local overlay or global inference state.

### 3.1 Infer Factor

Generated from ChainExpr — one factor per chain. Connects premise knowledge nodes (direct dependencies) to a single conclusion knowledge node with a conditional probability. Covers both deduction (p=1.0) and induction (p<1.0) — the probability is a parameter constraint, not a type distinction.

**Structure:**

```
FactorNode:
    type:                    infer
    premises:                [graph-layer node IDs of direct-dep knowledge nodes]
    contexts:                [graph-layer node IDs of indirect-dep knowledge nodes]
    conclusion:              graph-layer node ID of conclusion knowledge node
```

Parameterization input:

```
factor_parameters[factor_id].conditional_probability
```

- `premises` are mapped from `dependency: direct` args in ChainExpr steps. They create BP edges — BP sends and receives messages along these connections.
- `contexts` are mapped from `dependency: indirect` args. They do NOT create BP edges. Their influence is folded into `conditional_probability` when local parameterization or registry global-state updates assign that factor's probability.
- `conclusion` is the single conclusion knowledge node of the chain.
- By Graph IR constraints, `question` nodes may only appear as conclusions, not premises. `action` nodes may appear in either position.

**Potential:**

| All premises true? | Conclusion value | Potential |
|-------------------|-----------------|-----------|
| Yes | 1 | `conditional_probability` |
| Yes | 0 | `1 - conditional_probability` |
| No | any | `1.0` (unconstrained) |

When any premise is false, the factor imposes no constraint — the conclusion is free to take any value based on other factors.

**ChainExpr-level granularity:** Each ChainExpr compiles to one infer factor, not one per step. Intermediate steps within the chain are internal to the factor.

### 3.1b Abstraction Factor

Same potential semantics as `infer`, but generated from chains with `edge_type == "abstraction"`. Promoted to a top-level type for clarity.

```
FactorNode:
    type:                    abstraction
    premises:                [graph-layer node IDs of direct-dep knowledge nodes]
    conclusion:              graph-layer node ID of conclusion knowledge node
```

### 3.2 Instantiation Factor

Generated by elaboration when a schema node is instantiated into a ground node. Models the logical implication ∀x.P(x) → P(a).

**Structure:**

```
FactorNode:
    type:                    instantiation
    premises:                [graph-layer node ID of schema node]
    contexts:                []
    conclusion:              graph-layer node ID of instance node
```

Each instantiation factor is **binary** — exactly one premise (the schema) and one conclusion (the instance). The deductive direction is modeled by `premises=[schema], conclusion=instance`.

**Potential:**

| Schema (premise) | Instance (conclusion) | Potential |
|-----------------|-------------------|-----------|
| 1 (∀x.P(x) holds) | 1 (P(a) holds) | `1.0` |
| 1 (∀x.P(x) holds) | 0 (P(a) fails) | `0.0` (contradiction) |
| 0 (∀x.P(x) fails) | 1 (P(a) holds) | `1.0` (instance can hold independently) |
| 0 (∀x.P(x) fails) | 0 (P(a) fails) | `1.0` |

This is a deterministic implication — no parameterized `conditional_probability` is needed. It enforces:

- If schema is believed → instance must be believed (forward, deductive)
- If instance is disbelieved → schema must be disbelieved (backward, counterexample)
- If instance is believed → no constraint on schema (one example doesn't prove the universal)

**Inductive strengthening via BP message aggregation:**

```
V_schema ─── F_inst_1 ─── V_ground_1 (belief=0.9)
         ─── F_inst_2 ─── V_ground_2 (belief=0.85)
         ─── F_inst_3 ─── V_ground_3 (belief=0.1)   ← counterexample
```

Each instantiation factor sends a backward message to V_schema. BP aggregates these messages at the shared schema node:

- V_ground_3 has low belief → backward message through F_inst_3 pushes V_schema down
- V_schema belief drops → forward messages through F_inst_1, F_inst_2 weaken those instances
- Net effect: one strong counterexample weakens the universal and all its instances

Inductive reasoning emerges naturally from BP's message aggregation — no special-case logic needed.

### 3.3 Contradiction Factor

Generated from Contradiction relation nodes. The relation node participates as a full BP variable in `premises[0]`, enabling bidirectional message passing (Jaynes consistency).

**Structure:**

```
FactorNode:
    type:                    contradiction
    premises:                [relation_node_id, claim_a_id, claim_b_id, ...]
    contexts:                []
    conclusion:              None
```

The relation node in `premises[0]` acts as a gating variable — when active (belief high), the constraint penalizes the all-claims-true configuration. Unlike the v1.0 gate design, BP sends messages back to the relation node, allowing the system to "question the relationship itself" when evidence is strong for both claims.

**Potential:**

```
f_contradiction(c, a₁, a₂, ..., aₙ) =
    ε (≈0)                  if c = 1 and all aᵢ = 1
    1.0                     otherwise
```

Where ε = CROMWELL_EPS (1e-3).

**BP behavior:**

When the relation is active and two contradicted claims both have evidence, the factor sends inhibitory messages to both claims AND a weakening message to the relation node. Loopy BP with damping handles the resulting feedback naturally.

### 3.4 Equivalence Factor

Generated from Equivalence relation nodes. Rewards agreement between equated claims. The relation node participates in `premises[0]`.

**Structure:**

```
FactorNode:
    type:                    equivalence
    premises:                [relation_node_id, claim_a_id, claim_b_id]
    contexts:                []
    conclusion:              None
```

**Potential:**

```
f_equiv(c, a, b) =
    1.0                     if c = 0     (relation inactive — unconstrained)
    1 - ε                   if c = 1 and a == b     (agreement rewarded)
    ε                       if c = 1 and a != b     (disagreement penalized)
```

For n-ary equivalence (3+ members), decompose into pairwise constraints: equiv(a, b, c) → factors for (a, b), (a, c), (b, c). Each pairwise factor shares the same relation node in `premises[0]`.

**BP behavior:**

The equiv factor acts as an evidence bridge — belief flows bidirectionally between equated claims, weighted by the relation node's belief. The relation node itself receives messages from all pairwise factors, allowing BP to weaken the equivalence if evidence diverges.

## 4. Relation Nodes as Full BP Participants

### 4.1 Design (v2.0)

In v2.0, relation nodes (Contradiction, Equivalence) are normal BP participants in their constraint factors — placed in `premises[0]` rather than as a read-only gate in `conclusion`. This means:

- The relation node receives factor→variable messages from its constraint factor
- BP can "question the relationship" when both constrained claims have strong evidence
- Loopy BP with damping handles the resulting feedback naturally

**Rationale (Jaynes consistency):** Blocking bidirectional information flow (v1.0 gate design) violates the requirement that all propositions be updatable by evidence. When both contradicted claims have strong evidence, the correct Bayesian response is to lower confidence in the contradiction itself, not just suppress claims.

### 4.2 Structure

```
V_relation ───┐
V_claim_A  ───┤── F_contradiction ──→ (no conclusion)
V_claim_B  ───┘

All three nodes are full BP participants:
- F sends messages to V_relation, V_claim_A, V_claim_B
- V_relation, V_claim_A, V_claim_B send messages back to F
```

## 5. Schema/Ground Interaction in BP

### 5.1 Local Package BP

Within a single package's **Local Canonical Graph**, schema and ground nodes interact through binary instantiation factors. Each instantiation factor has `premises=[schema]` and `conclusion=instance`:

```
V_schema("在{X}条件下，{Y}是混淆变量")
    ├── F_inst_1: premises=[V_schema], conclusion=V_ground_1
    │   V_ground_1("在落体实验条件下，空气阻力是混淆变量")
    └── F_inst_2: premises=[V_schema], conclusion=V_ground_2
        V_ground_2("在天文观测条件下，大气折射是混淆变量")
```

BP computes beliefs for all local canonical nodes simultaneously. Forward messages flow schema→instance (deductive support). Backward messages flow instance→schema (inductive evidence). The messages aggregate at V_schema, producing inductive strengthening or counterexample weakening.

Local node priors and reasoning-factor probabilities are assumed to be provided by an author-local parameterization overlay generated after package-local canonicalization. This document does not define how the author tool chooses those values; it only defines how BP consumes them.

### 5.2 Global Graph BP

After packages are published, review/registry matching maps package-local nodes into the **Global Canonical Graph**. Schema nodes from different packages may then share one global canonical node. Ground instances from different packages that share a schema node become connected through it:

```
Package A:  F_inst_a: premises=[V_schema], conclusion=V_ground_a
Package B:  F_inst_b: premises=[V_schema], conclusion=V_ground_b
                               ↑ shared schema node
```

Evidence for V_ground_a (from Package A's reasoning chains) now indirectly supports V_ground_b (through the shared schema's aggregated belief), and vice versa. This is cross-package evidence propagation via shared abstract knowledge.

The policy for generating review-report judgments and registry `GlobalInferenceState` is intentionally deferred. This document specifies BP once a global graph and its current inference state are already instantiated; it does not yet fix how those probabilities are produced.

## 6. Factor Type Summary

| Factor type | Premises | Conclusion | Potential |
|-------------|----------|------------|-----------|
| `infer` | Direct dependencies | Conclusion node | Standard conditional (prob p) |
| `abstraction` | Direct dependencies | Conclusion node | Standard conditional (prob p) |
| `instantiation` | Schema node | Instance node | Deterministic implication |
| `contradiction` | Relation node + claim nodes | None | Penalize all-true when relation active |
| `equivalence` | Relation node + 2 claim nodes | None | Reward agreement when relation active |

`FactorNode.type` is the single source of truth for BP semantics. No `metadata.edge_type` indirection.

## Open Questions

1. **Lifted BP** — if many ground instances share the same schema and have identical local evidence, could lifted inference techniques (parfactors) avoid redundant message passing? Deferred optimization.
2. **Incremental BP** — when a new package is published and merged, can BP be run incrementally on the affected subgraph rather than the entire global graph?
3. **Equivalence decomposition** — for n-ary equivalence, pairwise decomposition is the current approach. Are there better n-ary factor functions?
4. **Probability-state generation** — how should author-local overlays, review-report judgments, and registry `GlobalInferenceState` be generated and versioned?
