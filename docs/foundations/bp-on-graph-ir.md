# Belief Propagation on Graph IR

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-12 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [graph-ir.md](graph-ir.md) — Graph IR 结构定义, [theory/inference-theory.md](theory/inference-theory.md) — BP 算法理论, [theory/theoretical-foundation.md](theory/theoretical-foundation.md) — Jaynes 纲领 |

---

## 1. Purpose

This document defines how belief propagation runs on Graph IR. It covers local parameterization overlays, global inference state, factor functions, gate semantics for Relations, instantiation factor semantics, and the interaction between schema and ground nodes during BP.

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

`factor_parameters` is keyed by `factor_id`. Full IDs or unambiguous `factor_id` prefixes are allowed. A valid overlay must provide priors for every belief-bearing node in the active local graph and `conditional_probability` for every `reasoning` factor in that graph. Missing entries make the overlay invalid; BP does not fall back to hidden defaults.

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

### 3.1 Reasoning Factor

Generated from ChainExpr — one reasoning factor per chain. Connects premise knowledge nodes (direct dependencies) to a single conclusion knowledge node with a conditional probability.

**Structure:**

```
FactorNode:
    type:                    reasoning
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
- By Graph IR V1 constraints, `question` nodes may only appear as conclusions, not premises. `action` nodes may appear in either position.

**Potential:**

| All premises true? | Conclusion value | Potential |
|-------------------|-----------------|-----------|
| Yes | 1 | `conditional_probability` |
| Yes | 0 | `1 - conditional_probability` |
| No | any | `1.0` (unconstrained) |

When any premise is false, the factor imposes no constraint — the conclusion is free to take any value based on other factors.

**Subtypes:**

| Subtype | Difference | conditional_probability constraint |
|---------|-----------|-----------------------------------|
| deduction | Standard (above) | May be 1.0 |
| induction | Standard (above) | Must be < 1.0 (lattice-theoretic: §2 of inference-theory.md) |
| abstraction | Standard (above) | May be 1.0 |
| retraction | Inverted: conclusion=1 with prob `1-p` | — |

Retraction inverts the potential — it weakens the conclusion rather than supporting it.

**ChainExpr-level granularity:** Each ChainExpr compiles to one reasoning factor, not one per step. Intermediate steps within the chain are internal to the factor. This is correct because intermediate nodes are either deterministic transformations or not independently meaningful knowledge units — only the premises (self-review–identified weak points with direct dependency) and the conclusion are semantically meaningful inputs/outputs of the factor.

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

### 3.3 Mutex Constraint Factor (Contradiction)

Generated from Contradiction relation nodes. Penalizes the all-true configuration of contradicted claims.

**Structure:**

```
FactorNode:
    type:                    mutex_constraint
    premises:                [graph-layer node IDs of constrained claim nodes]
    contexts:                []
    conclusion:              graph-layer node ID of Contradiction node (read-only gate)
```

The `conclusion` field holds the Contradiction knowledge node, which acts as a **read-only gate** — BP reads its runtime belief to determine constraint strength but does not send messages back to it. See §4 for gate semantics. The gate node's initial prior comes from `node_priors[conclusion]`.

**Potential:**

```
f_mutex(a₁, a₂, ..., aₙ) =
    (1 - effective_prob)    if all aᵢ = 1
    1.0                     otherwise
```

Where `effective_prob = belief(gate node)`, clamped to [ε, 1−ε].

**BP behavior:**

When two contradicted claims both have evidence, the mutex factor sends inhibitory messages to both. The weaker claim (lower belief from other factors) gets suppressed more — Jaynes' "weaker evidence yields first" emerges naturally.

### 3.4 Equiv Constraint Factor (Equivalence)

Generated from Equivalence relation nodes. Rewards agreement between equated claims.

**Structure:**

```
FactorNode:
    type:                    equiv_constraint
    premises:                [graph-layer node IDs of equated claim nodes]
    contexts:                []
    conclusion:              graph-layer node ID of Equivalence node (read-only gate)
```

Same gate pattern as mutex_constraint — the `conclusion` holds the Equivalence knowledge node as a read-only gate. The gate node's initial prior comes from `node_priors[conclusion]`.

Graph IR V1 additionally constrains `question`/`action` equivalence to same-root-type, same-`kind` pairs; BP assumes those structural checks have already passed before the factor is built.

**Potential:**

```
f_equiv(a, b) =
    effective_prob          if a == b     (agreement rewarded)
    1 - effective_prob      if a != b     (disagreement penalized)
```

Where `effective_prob = belief(gate node)`, clamped to [ε, 1−ε].

For n-ary equivalence (3+ members), decompose into pairwise constraints: equiv(a, b, c) → factors for (a, b), (a, c), (b, c).

**BP behavior:**

The equiv factor acts as an evidence bridge — belief flows bidirectionally between equated claims, weighted by the equivalence strength. If one claim receives new evidence, the other's belief increases proportionally.

## 4. Gate Semantics for Relations

### 4.1 The Problem

A Relation (Contradiction or Equivalence) is both:
- A **knowledge node** with its own belief ("how confident are we that this relationship holds?")
- The source of a **constraint factor** that constrains other knowledge nodes

If the Relation node participates in its own constraint factor as a normal conclusion, BP creates a feedback loop: the constrained claims' beliefs influence the Relation's belief, which influences the constraint strength, which influences the claims' beliefs.

### 4.2 Design Decision: Read-Only Gate via `conclusion` Field

For constraint factors (`mutex_constraint`, `equiv_constraint`), the `conclusion` field holds the Relation knowledge node as a **read-only gate**. This differs from reasoning factors where `conclusion` receives messages normally.

The factor type determines the semantics of `conclusion`:

| Factor type | `conclusion` semantics |
|-------------|-------------------|
| `reasoning` | Normal conclusion — receives factor→knowledge messages |
| `instantiation` | Normal conclusion — receives factor→knowledge messages |
| `mutex_constraint` | Read-only gate — belief read, no messages sent back |
| `equiv_constraint` | Read-only gate — belief read, no messages sent back |

```
Constraint factor BP participants: only the premise knowledge nodes
Gate (conclusion): the Relation (read-only — receives no messages from this factor)

V_claim_A ───┐                    V_contradiction (conclusion, read-only gate)
V_claim_B ───┤── F_mutex               │
             │      │                   │
             │      └── reads belief ───┘  (one-directional, no messages sent back)
             │
             └── F_mutex sends messages to V_claim_A, V_claim_B
                 but NOT to V_contradiction
```

At each BP iteration, when computing factor→knowledge messages for a gated constraint factor:
1. Read the gate node's (conclusion's) current belief from runtime BP state
2. Use that belief as `effective_prob` in the factor function
3. Compute and send messages to the premise variables only

### 4.3 Rationale

**Separation of structure and inference.** Relations are structural assertions about logical relationships. BP computes beliefs given those relationships. BP should not modify the relationships it reasons over.

**Analogy to Lean.** Lean's kernel does not modify axioms based on how many theorems use them. Similarly, Gaia's BP should not modify a Contradiction's belief based on the beliefs of the claims it constrains.

**Contradictions must be taken seriously.** If both contradicted claims have strong evidence, the correct response is to flag the inconsistency for investigation, not to silently weaken the contradiction. Under gate semantics, the contradiction forces one claim's belief down, making the inconsistency visible.

**Relations are not immutable.** A Relation's belief CAN change — through reasoning factors that connect to it as a normal conclusion:

```
V_contradiction ← F_reasoning (chain that discovered the contradiction)
                ← F_resolution (new chain arguing they're compatible)
```

These reasoning factors have `conclusion: V_contradiction` and send normal factor→knowledge messages. The updated belief then changes the gate strength for the mutex constraint.

### 4.4 Formal Specification

For `mutex_constraint` and `equiv_constraint` factors:
- The `conclusion` node (gate) is NOT included in the factor's BP message participant set
- The factor NEVER sends messages to the `conclusion` node
- At message computation time, the gate node's current marginal belief replaces any stored probability:
  ```
  effective_prob = belief(conclusion_var)    -- clamped to [ε, 1-ε]
  ```
- If the gate node's belief is unavailable (e.g., initial iteration), fall back to the gate node's parameterized prior from `node_priors`

### 4.5 Consequences

| Scenario | Gate behavior | Effect |
|----------|-------------|--------|
| Contradiction discovered by strong reasoning | gate belief high | Strong mutex constraint, one claim suppressed |
| Contradiction later disproved by new reasoning | gate belief drops | Mutex constraint weakens, both claims can be high |
| Both contradicted claims gain evidence | gate belief unchanged | Constraint holds, system flags inconsistency |
| Equivalence with diverging evidence for equated claims | gate belief unchanged | Equiv bridge still active, partial evidence sharing |

## 5. Retraction in Graph IR

Retraction is modeled as a reasoning factor with inverted potential (§3.1 retraction subtype). The RetractAction from the Relation type design compiles to a reasoning factor:

```
FactorNode:
    type:       reasoning (subtype: retraction)
    premises:   [V_retraction_evidence]
    contexts:   []
    conclusion: V_target_claim
```

Parameterization input:

```
factor_parameters[factor_id].conditional_probability = p
```

The inverted potential means: when premises are true, conclusion=1 has potential `1-p` (weakened) rather than `p` (supported).

Retraction differs from contradiction:
- **Contradiction** is a symmetric structural relationship (all premise claims constrained symmetrically)
- **Retraction** is a directed reasoning operation (evidence weakens a specific target claim)

## 6. Schema/Ground Interaction in BP

### 6.1 Local Package BP

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

### 6.2 Global Graph BP

After packages are published, review/registry matching maps package-local nodes into the **Global Canonical Graph**. Schema nodes from different packages may then share one global canonical node. Ground instances from different packages that share a schema node become connected through it:

```
Package A:  F_inst_a: premises=[V_schema], conclusion=V_ground_a
Package B:  F_inst_b: premises=[V_schema], conclusion=V_ground_b
                               ↑ shared schema node
```

Evidence for V_ground_a (from Package A's reasoning chains) now indirectly supports V_ground_b (through the shared schema's aggregated belief), and vice versa. This is cross-package evidence propagation via shared abstract knowledge.

The policy for generating review-report judgments and registry `GlobalInferenceState` is intentionally deferred. This document specifies BP once a global graph and its current inference state are already instantiated; it does not yet fix how those probabilities are produced.

## 7. Relationship to Existing Implementation

### 7.1 What Carries Over

| Component | Current | Graph IR BP | Status |
|-----------|---------|-------------|--------|
| Sum-product algorithm | `libs/inference/bp.py` | Same algorithm | Reuse |
| Damping | `_damping` parameter | Same | Reuse |
| Cromwell's rule | Clamping at construction | Same | Reuse |
| Convergence check | max_change < threshold | Same | Reuse |
| Gate variable | `gate_var` in factor dict | Maps to `conclusion` field on constraint factors | Adapt |
| Factor potential | `_evaluate_potential()` | Extended with instantiation | Extend |

### 7.2 What Changes

| Component | Current | Graph IR BP |
|-----------|---------|-------------|
| Variable IDs | `int` | `local_canonical_id` / `global_canonical_id: str` (internal mapping to int for performance) |
| Factor structure | `premises[]`, `conclusions[]`, `probability`, `gate_var` | Structural Graph IR (`premises[]`, `contexts[]`, `conclusion`) + local overlay / global inference state |
| Factor types | deduction, induction, retraction, contradiction, relation_* | reasoning, instantiation, mutex_constraint, equiv_constraint |
| Factor granularity | One factor per step (apply/lambda) | One factor per ChainExpr |
| Instantiation factor | Does not exist | New: implication potential for schema→instance |
| Input source | `FactorGraph.from_subgraph()` or `CompiledFactorGraph` | Graph IR JSON + local overlay or `GlobalInferenceState` |
| Output target | `dict[int, float]` | Runtime belief snapshot keyed by graph-layer node ID |

### 7.3 Migration Path

The BP algorithm implementation (`libs/inference/bp.py`) requires these changes:

1. Add `instantiation` case to `_evaluate_potential()`
2. Add Graph IR → internal FactorGraph conversion (graph-layer node ID → int mapping, `conclusion` singular → conclusions list internally)
3. Load local overlay or registry `GlobalInferenceState` and map it onto node priors / factor probabilities
4. Map `conclusion` on constraint factors to existing `gate_var` mechanism
5. Map `contexts` to non-BP metadata (contexts do not create BP edges)
6. Write BP results to a runtime belief snapshot rather than mutating submitted Graph IR

## Open Questions

1. **Lifted BP** — if many ground instances share the same schema and have identical local evidence, could lifted inference techniques (parfactors) avoid redundant message passing? Deferred optimization.
2. **Incremental BP** — when a new package is published and merged, can BP be run incrementally on the affected subgraph rather than the entire global graph?
3. **Equivalence decomposition** — for n-ary equivalence, pairwise decomposition is the current approach. Are there better n-ary factor functions?
4. **Probability-state generation** — how should author-local overlays, review-report judgments, and registry `GlobalInferenceState` be generated and versioned?
