# Gaia Language v3 Design

**Date:** 2026-03-18
**Supersedes:** 2026-03-17-gaia-lang-v2-design.md (v2 Typst DSL)
**Scope:** Simplify v2 — remove tactics, clarify probability model, streamline proof obligations

## Motivation

v2 introduced Lean-inspired proof blocks and 9 reasoning strategy tactics (`#deduce`, `#by_contradiction`, `#synthesize`, etc.). In practice these tactics are purely narrative annotations — they don't affect the factor graph, proof state analysis doesn't use them, and the reviewer/LLM can infer reasoning strategy from prose. They add syntax complexity without structural value.

v3 strips the DSL to its essential structural primitives: declarations that create graph nodes, `#premise` that creates edges, and `#claim_relation` that creates constraint factors. Everything else is natural language.

### Design Principles

1. **Only structural primitives get syntax** — if it doesn't affect the factor graph, it's prose
2. **Uncertainty lives in the right place** — π on nodes, p on factors, b computed by BP
3. **Minimal proof obligation** — hole detection is a dependency completeness check, not a proof state machine
4. **Extensible tactic interface** — currently only `#premise`, but designed for future additions (e.g., `#toolcall` for external verification)

## Declarations

Five declaration types, each generating a node in the knowledge graph and a Typst `<label>` for `@name` cross-referencing.

| Function | Purpose | Proof block |
|----------|---------|-------------|
| `#claim(name)[statement][proof]` | Assertion needing justification | Required (no proof = hole if used as premise) |
| `#claim_relation(name, type:, between:)[desc?]` | Relation constraint between declarations | Not needed — relation declaration is self-complete |
| `#observation(name)[content]` | Empirical fact | No |
| `#setting(name)[content]` | Definitional assumption / precondition | No |
| `#question(name)[content]` | Open question | No |

### `#claim` — Assertions

A claim with a proof block generates a noisy-AND factor in the graph. The proof block contains `#premise` declarations and natural language argumentation.

```typst
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  绑球矛盾推翻旧定律、介质分析排除干扰因素、
  斜面实验提供正面支持。三条独立线索汇聚，在真空中结论成立。
]
```

A claim without a proof block is valid but creates a **hole** if used as `#premise` elsewhere.

```typst
#claim("heavier_falls_faster")[重者下落更快。]
// No proof block — hole if referenced as premise
```

### `#claim_relation` — Relation Constraints

Declares a structural constraint between two declarations. The `between` parameters automatically become premises — no manual `#premise` needed. No proof block needed — the relation declaration itself is complete.

```typst
#claim_relation("tied_balls_contradiction",
  type: "contradiction",
  between: ("composite_is_slower", "composite_is_faster")
)
```

With optional description:

```typst
#claim_relation("tied_balls_contradiction",
  type: "contradiction",
  between: ("composite_is_slower", "composite_is_faster")
)[两者由同一前提推出却互相矛盾。]
```

Supported relation types:

| type | Constraint factor | BP semantics |
|------|------------------|--------------|
| `"contradiction"` | mutex | A=1 ∧ B=1 → ε (near-impossible) |
| `"equivalence"` | biconditional | A≠B → ε (penalized) |

`#claim_relation` vs `#claim`:

| | `#claim` | `#claim_relation` |
|-|----------|-------------------|
| Premises | Manual `#premise()` | Auto from `between` |
| Proof block | Needed (else hole) | Not needed |
| Factor type | noisy-AND | Constraint (mutex / equiv) |
| Hole detection | Yes | No — always complete |

### `#observation`, `#setting`, `#question`

These are leaf declarations — no proof needed, never holes.

```typst
#observation("medium_density_observation")[
  介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
]

#setting("thought_experiment_env")[
  假想环境：无空气阻力的理想条件下进行思想实验。
]

#question("experimental_verification")[
  能否设计实验直接验证真空中的等速下落预测？
]
```

## Proof Blocks

A proof block is the second content block of `#claim`. It contains:

1. **`#premise("name")` declarations** — structural, creates input edges to the noisy-AND factor
2. **Natural language prose** — argumentation, narrative, context. No special syntax needed.
3. **`@name` references** — Typst native cross-references for inline citation (no structural effect)

### Writing Style

Proof blocks follow academic citation conventions: **state the argument first, then cite the supporting premise.** Like a paper's inline citation, `@ref` appears after the claim it supports, not before.

```typst
#claim("air_resistance_is_confound")[
  速度差异是介质阻力的表象，不是重量决定速度的证据。
][
  #premise("medium_density_observation")

  如果速度差异由介质阻力造成，那么介质越稀薄差异越小。
  实验中恰好观察到了这一规律 @medium-density-observation ，
  说明介质阻力是更好的解释。
]
```

For multi-premise proofs, use Typst lists to organize reasoning steps, each citing the relevant premise:

```typst
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  + 绑球思想实验表明旧定律自相矛盾 @tied-balls-contradiction 。
  + 日常观察到的速度差异实为介质阻力的表象 @air-resistance-is-confound 。
  + 斜面实验从正面提供了等速趋势的证据 @inclined-plane-observation 。

  三条独立线索汇聚，在真空中结论成立。
]
```

### `#premise` — The Only Structural Tactic

`#premise` is the only tactic that affects the factor graph. It declares an independent input edge to the noisy-AND factor for the enclosing claim.

```typst
#premise("name")
```

- Must be inside a proof block (error if outside)
- All premises of a claim must be mutually independent
- The referenced name must be a declared node (`#claim`, `#observation`, `#setting`, or `#claim_relation`)

### Future Tactic Extensions

The tactic interface is designed for future additions. Potential future tactics:

```typst
#toolcall("python", "verify_formula.py")  // External computation
#check("lean4", "proof.lean")             // Formal verification
```

These would affect the factor graph or proof obligations, distinguishing them from prose.

## Hole Detection

Build-time analysis detects incomplete argument chains. This is a simple dependency completeness check, not a proof state machine.

**Rule:** A node is a hole if and only if:
1. It is a `#claim` (not observation/setting/question/claim_relation)
2. It has no proof block
3. It is referenced as `#premise` somewhere in the package

```
$ gaia build galileo_falling_bodies --check

✓ established:
  tied_balls_contradiction
  air_resistance_is_confound
  vacuum_prediction

○ axioms (no proof needed):
  thought_experiment_env        (setting)
  medium_density_observation    (observation)

? holes:
  heavier_falls_faster          (claim, used as premise, no proof)
```

Hole detection is **package-wide** — if module A defines `#claim("X")` without proof and module B uses `#premise("X")`, then X is a hole.

## Factor Graph Mapping

### `#claim` with proof → noisy-AND factor

Each proven claim becomes one noisy-AND factor node:

```
premises (from #premise declarations) ──→ [noisy-AND] ──→ conclusion (the claim)
```

Factor potential φ(P₁,...,Pₙ, C):

```
all Pᵢ=1, C=1  →  p        (support: premises true, conclusion true)
all Pᵢ=1, C=0  →  1-p      (premises true, conclusion false)
any Pᵢ=0, C=1  →  ε        (leak: conclusion true despite failed premise)
any Pᵢ=0, C=0  →  1-ε      (expected: premise false, conclusion false)
```

### `#claim_relation` → constraint factor

```
between nodes (auto-premises) ──→ [constraint] ──→ relation node
```

Contradiction constraint: A=1 ∧ B=1 → ε (near-impossible).
Equivalence constraint: A≠B → ε (penalized).

### Example: Galileo (fine-grained decomposition)

```
heavier_falls_faster ──────────┐
thought_experiment_env ────────┤→ [f1] → composite_is_slower
                               │
heavier_falls_faster ──────────┤→ [f2] → composite_is_faster
thought_experiment_env ────────┘

composite_is_slower ───────────┤→ [constraint: contradiction]
composite_is_faster ───────────┘   → tied_balls_contradiction

medium_density_observation ────┤→ [f3] → air_resistance_is_confound

tied_balls_contradiction ──────┐
air_resistance_is_confound ────┤→ [f4] → vacuum_prediction
inclined_plane_observation ────┘
```

## Probability Model

Four distinct probabilities in the system:

| Symbol | Location | Meaning | Set by | Updated by BP? |
|--------|----------|---------|--------|---------------|
| π | node | Prior — intrinsic plausibility before reasoning | Reviewer | No |
| b | node | Belief — posterior after BP convergence | BP | Yes (this is BP's output) |
| p | factor | Conditional probability — reasoning step reliability | Reviewer | No |
| ε | factor | Leak — background probability (Cromwell bound) | Fixed 10⁻³ | No |

**BP computes b from (π, p, ε).** The reviewer provides π and p. Everything else is derived.

### Who Sets π

- **Leaf nodes** (observations, settings): reviewer sets π based on empirical reliability
- **Intermediate nodes** (claims that are conclusions of upstream factors): default π = 0.5. BP propagates upstream influence via messages. Reviewer MAY set a non-default π to encode background knowledge independent of the graph, but must avoid double-counting with BP messages.

### Who Sets p

- **Current stage**: reviewer (human or LLM) assigns p per factor
- **Future (at scale)**: p can be learned via EM when the knowledge graph has sufficient ground-truth nodes and redundant reasoning paths

### Can p = 1?

If the author has fully decomposed all uncertainty into explicit premises, the reasoning step becomes pure deduction and p ≈ 1. In practice, natural science reasoning often has irreducible uncertainty that can't be fully captured by adding premises (Hume's problem of induction). p < 1 captures the remaining uncertainty after premise decomposition.

Complementary strategies:
- **Decompose** hidden assumptions into explicit premises → p increases toward 1
- **Accept** irreducible reasoning uncertainty → p < 1 captures what remains

## Package Structure

Unchanged from v1/v2. Typst native package system:

```
galileo_falling_bodies/
  typst.toml              # Package metadata
  lib.typ                 # Entrypoint: imports, exports, export-graph()
  motivation.typ          # Module
  setting.typ             # Module
  aristotle.typ           # Module
  galileo.typ             # Module
  follow_up.typ           # Module
```

One module per `.typ` file, declared with `#module("name", title: "...")`.
Cross-module imports via `#use("module.declaration")`.

## Build Pipeline

```
.typ source files
  ↓ typst compile + typst query (metadata extraction)
JSON: {nodes, factors, constraints, modules, exports}
  ↓ hole detection (dependency completeness check)
Report: established / axioms / holes / questions
  ↓ factor graph compilation
Factor graph: noisy-AND factors + constraint factors
  ↓ review (human or LLM, per factor)
Inputs: π for premises, p for factor
  ↓ BP inference
Output: b (posterior belief) for each node
```

## Changes from v2

### Removed
- **Strategy tactics** (`#deduce`, `#abduction`, `#by_contradiction`, `#by_cases`, `#by_induction`, `#by_analogy`, `#by_elimination`, `#by_extrapolation`, `#synthesize`) — narrative annotations without structural value. Prose in proof blocks serves the same purpose.
- **Proof state machine** — replaced by simple hole detection (dependency completeness check)
- **Proof traces** — no longer needed without strategy tactics. Factor graph is derived from `#premise` declarations only.

### Changed
- **`#claim_relation`** — no longer requires proof block. `between` parameters auto-become premises. The relation declaration is self-complete.
- **Proof blocks** — now contain only `#premise` + natural language prose. Cleaner, simpler.

### Unchanged
- Declaration types: `#claim`, `#observation`, `#setting`, `#question`, `#claim_relation`
- `#premise` as the structural tactic
- Typst native package system
- `#module`, `#use`, `#export-graph`
- Metadata extraction via `typst.query()`
- "No priors in authoring" principle
- `@ref` / `<label>` native cross-references

### Added
- **Explicit probability model documentation** — π, p, ε, b clearly defined with ownership
- **Future tactic extension point** — `#premise` is the first tactic, interface designed for additions like `#toolcall`

## Future Extensions

- **External verification tactics** — `#toolcall`, `#check` for invoking Python/Lean4/etc.
- **EM parameter learning** — learn p from ground-truth nodes at scale
- **Cross-package `#use` resolution** — resolve references across packages
- **Additional relation types** — `type: "retraction"`, `type: "support"`, etc.
