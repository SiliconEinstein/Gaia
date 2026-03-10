# Relation Type Design

> **Issue:** #62
> **Status:** Approved design
> **Related docs:**
> - [Type System Direction](../foundations/language/type-system-direction.md)
> - [Design Rationale](../foundations/language/design-rationale.md)
> - [Gaia Language Spec](../foundations/language/gaia-language-spec.md)
> - [Galileo Example](../examples/galileo_tied_balls.md)

## Problem

Contradiction and retraction are currently modeled as untyped strings (`edge_type` field on ChainExpr and HyperEdge). There is no formal type definition, no judgment rules, and no provenance tracking. A contradiction is simultaneously a Claim node (carrying belief) and an edge (carrying structural information), creating redundant dual modeling.

## Design Decisions

### 1. Relation is the 8th Root Type

Relation joins the existing 7 Knowledge root types (Claim, Question, Setting, Action, Expr, Ref, Module) as a first-class declaration.

**Rationale:** Relations like "A contradicts B" and "A is equivalent to B" are not claims (they don't assert propositional content), not actions (they don't describe procedures), and not expressions (they don't compose reasoning steps). They are a distinct kind of knowledge — **structural assertions about logical relationships between other knowledge objects**.

### 2. V1 Subtypes: Contradiction and Equivalence

**Contradiction** — declares that two or more claims are mutually exclusive.

**Equivalence** — declares that two or more claims express the same proposition (possibly derived through different reasoning paths).

Support is deferred. It may be better modeled through standard deduction chains rather than a separate Relation subtype.

### 3. Retraction is an Action, Not a Relation

Retraction is a directed, dynamic operation ("weaken this claim because of that contradiction"), not a symmetric, static fact.

| | Contradiction | Equivalence | Retraction |
|---|---|---|---|
| Nature | Static logical relationship | Static logical relationship | Dynamic operation |
| Symmetry | Symmetric | Symmetric | Asymmetric |
| Type | Relation | Relation | Action (RetractAction) |

RetractAction signature:

```
RetractAction : (target: Claim, reason: Contradiction) → BeliefUpdate
```

### 4. Relation is Truth-Apt

Relation has `prior` and `belief` fields and participates in BP as a variable node. This unifies the current dual modeling (Claim node + edge) into a single declaration.

The belief in a Relation controls its effect strength:
- High belief in a Contradiction → strong mutual exclusion constraint
- Low belief → weak constraint (maybe these claims don't really contradict)
- High belief in an Equivalence → strong evidence bridge
- Low belief → weak bridge

### 5. Relation Replaces ChainExpr's edge_type

ChainExpr currently carries an `edge_type` field (deduction/contradiction/retraction). With Relation as a root type:
- ChainExpr drops `edge_type`
- ChainExpr gains `produces` — a Ref to the Relation it establishes
- The Relation itself carries the semantic information

## Type Hierarchy

```
Knowledge (root)
  ├── Claim          (existing)
  ├── Question       (existing)
  ├── Setting        (existing)
  ├── Action         (existing)
  │     └── RetractAction  (new)
  ├── Expr           (existing)
  ├── Ref            (existing)
  ├── Module         (existing)
  └── Relation       (new — 8th root type)
        ├── Contradiction
        └── Equivalence
```

### Core Attributes

| Attribute | Relation | Claim | Action |
|---|---|---|---|
| truth-apt | Yes | Yes | No |
| BP participation | Yes (variable node + factor) | Yes (variable node) | No |
| prior/belief | Yes | Yes | No |
| Can be produced by ChainExpr | Yes | Yes | N/A |

## YAML Surface Syntax

### Contradiction

```yaml
relation tied_balls_contradiction:
  type: contradiction
  between:
    - ref: tied_pair_slower_than_heavy
    - ref: tied_pair_faster_than_heavy
  prior: 0.95
```

### Equivalence

```yaml
relation newton_galileo_equivalence:
  type: equivalence
  between:
    - ref: galileo_vacuum_prediction
    - ref: newton_mass_independent
  prior: 0.90
```

### RetractAction

```yaml
- type: retract_action
  name: retract_aristotle
  target: heavier_falls_faster
  reason: tied_balls_contradiction
  prior: 0.96
```

### ChainExpr Producing a Relation

```yaml
chain_expr contradiction_reasoning:
  steps:
    - step: 1
      ref: tied_pair_slower_than_heavy
    - step: 2
      apply: expose_mutual_exclusion
      args:
        - ref: tied_pair_slower_than_heavy
          dependency: direct
        - ref: tied_pair_faster_than_heavy
          dependency: direct
      prior: 0.97
    - step: 3
      produces: tied_balls_contradiction
```

## Factor Graph Compilation and BP Semantics

### Compilation Rules

Each Relation compiles to one variable node (for the Relation's own belief) plus one constraint factor node (connecting the related claims).

**Contradiction:**

```
Contradiction(A, B, prior=p)
  → variable node: V_contradiction (prior=p)
  → factor node:   f_mutex(V_A, V_B, V_contradiction)
```

**Equivalence:**

```
Equivalence(A, B, prior=p)
  → variable node: V_equivalence (prior=p)
  → factor node:   f_equiv(V_A, V_B, V_equivalence)
```

### Factor Functions

**Contradiction (mutex) factor:**

```
f_mutex(a, b, e) = e · (1 - a·b) + (1-e) · 1
```

- `e` high → penalizes `a` and `b` being simultaneously high
- `e` low → no constraint
- BP naturally propagates inconsistency back to shared premises

**Equivalence (information bridge) factor:**

```
f_equiv(a, b, e) = e · exp(-λ(a-b)²) + (1-e) · 1
```

- `e` high → strong constraint pulling `a ≈ b`, evidence flows bidirectionally
- `e` low → no constraint
- λ controls strictness (fixed in V1)

The equivalence factor derives from Jaynes' total probability formula:

```
P(A) = P(A | A≡B) · P(A≡B) + P(A | ¬(A≡B)) · P(¬(A≡B))
```

When P(A≡B) = 1.0, P(A) = P(B) — beliefs synchronize completely. When P(A≡B) < 1.0, evidence flows partially through the bridge. After convergence, both claims' beliefs incorporate evidence from both reasoning paths, typically resulting in beliefs higher than either alone.

### RetractAction BP Semantics

RetractAction does not directly participate in BP. Its role is:

1. Create a retraction edge from the Contradiction to the target claim in the graph
2. BP's message propagation through the contradiction factor **automatically** weakens the target's belief
3. RetractAction provides **intent declaration** and **provenance record**

Without RetractAction, BP still weakens shared premises (via contradiction factor). With RetractAction, there is an explicit record of "which contradiction caused which claim to be weakened."

## Provenance DAG

### Design

Provenance tracking uses existing reference mechanisms — no new types needed. The causal chain is:

```
ChainExpr (reasoning that discovers the relationship)
    ↓ produces
Relation (declares the contradiction/equivalence)
    ↓ referenced by
RetractAction (intent: weaken target because of this contradiction)
    ↓ BP propagation
target Claim (belief updated)
```

### Galileo Example (Refactored)

```yaml
# 1. Reasoning chain produces the Contradiction
chain_expr contradiction_reasoning:
  steps:
    - step: 1
      ref: tied_pair_slower_than_heavy
    - step: 2
      apply: expose_mutual_exclusion
      args:
        - ref: tied_pair_slower_than_heavy
          dependency: direct
        - ref: tied_pair_faster_than_heavy
          dependency: direct
      prior: 0.97
    - step: 3
      produces: tied_balls_contradiction

# 2. Contradiction declaration
relation tied_balls_contradiction:
  type: contradiction
  between:
    - ref: tied_pair_slower_than_heavy
    - ref: tied_pair_faster_than_heavy
  prior: 0.95

# 3. RetractAction records intent
retract_action retract_aristotle:
  target: heavier_falls_faster
  reason: tied_balls_contradiction
  prior: 0.96
```

### Query Capabilities

The provenance DAG supports backward tracing:

- **"Why did heavier_falls_faster lose belief?"** → find retract_aristotle → find tied_balls_contradiction → find contradiction_reasoning
- **"What did tied_balls_contradiction affect?"** → find all RetractActions referencing it → find their targets

### Storage

Provenance relationships use existing Ref mechanism. `RetractAction.reason` is a Ref to a Relation. `ChainExpr.produces` is a Ref to a Relation. No new storage model required.

## Impact on Existing System

| Component | Change |
|---|---|
| `libs/dsl/models.py` | Add Relation, Contradiction, Equivalence, RetractAction classes |
| `libs/models.py` | HyperEdge.type adds relation-related types |
| ChainExpr | Remove `edge_type` field, add `produces` field pointing to Relation |
| Factor graph compiler | Add Relation → variable node + constraint factor compilation rules |
| BP engine | Add mutex factor and equiv factor message propagation functions |
| Galileo example | Refactor: split contradiction_chain/retraction_chain into Relation + RetractAction |

## V1 Scope

**In scope:**
- Relation root type definition (Contradiction, Equivalence)
- RetractAction as Action subtype
- Factor graph compilation rules for both subtypes
- BP factor functions (mutex, equiv)
- Provenance DAG via existing Ref mechanism
- Galileo example refactored to use new types
- Kernel judgments for Relation well-formedness

**Out of scope (deferred):**
- Automatic contradiction/equivalence detection
- Support as Relation subtype
- Review pipeline integration for Relation validation
- Cross-package Relation merging/deduplication

## Kernel Judgments

New judgments for the V1 kernel:

**Relation formation:**
- `Γ ⊢ relation r ok` — Relation is well-formed (between references resolve, types are compatible)

**Relation type checking:**
- `Γ ⊢ contradiction(A, B) ok` — A and B are both truth-apt (Claim or Setting)
- `Γ ⊢ equivalence(A, B) ok` — A and B are the same Knowledge kind

**RetractAction typing:**
- `Γ ⊢ retract(target, reason) ok` — target is truth-apt, reason is a Contradiction Relation

**Belief participation:**
- `Γ ⊢ relation r belief_bearing` — all Relations are belief-bearing (truth-apt by definition)

**Graph compilation:**
- `Γ ⊢ relation r lowers_to (var_node, factor_node)` — Relation compiles to variable + constraint factor
