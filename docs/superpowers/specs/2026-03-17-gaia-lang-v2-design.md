# Gaia Language v2 Design

**Date:** 2026-03-17
**Supersedes:** 2026-03-16-typst-gaia-lang-design.md (v1 Typst DSL)
**Scope:** Typst DSL redesign — Lean-inspired proof system + noisy-AND factor mapping

## Motivation

v1 DSL uses `#chain` as a linear step container with auto-inject semantics. This creates a mismatch with the noisy-AND factor model: chain steps become factor nodes, but the actual inference structure is fan-in (multiple independent premises → one conclusion). The chain's linear narrative conflates proof structure with factor graph topology.

v2 redesigns the DSL around the insight that **each conclusion is a claim with a proof**, directly inspired by Lean's `theorem ... := by ...` pattern. This gives us:

1. **Clean noisy-AND mapping** — each proven claim = one factor, premises explicitly declared
2. **Proof state tracking** — automatic hole detection, like Lean's `sorry`
3. **Separation of concerns** — factor graph structure (premises) vs. human narrative (proof text) vs. context (references)

## Core Concept Model

### Declarations

All top-level knowledge is expressed through declaration functions. Each generates a Typst `<label>` for cross-referencing via `@name`.

| Function | Purpose | Requires proof |
|----------|---------|---------------|
| `#claim(name)[statement]` | Assertion needing proof | Yes (no proof = hole) |
| `#claim(name)[statement][proof]` | Proven assertion | — |
| `#claim_relation(name, type:, between:)[desc]` | Relation between declarations | Yes (no proof = hole) |
| `#claim_relation(name, type:, between:)[desc][proof]` | Proven relation | — |
| `#observation(name)[content]` | Empirical fact | No |
| `#setting(name)[content]` | Definitional assumption / precondition | No |
| `#question(name)[content]` | Open question | No |

### Universal Parameter: `type:`

All declarations accept `type:` (default `"natural"`):

```typst
#claim("gravity_formula", type: "python")[
  def gravitational_acceleration(m1, m2, r):
      return G * m1 * m2 / r**2
]
```

| type | Verification | CI requirement |
|------|-------------|---------------|
| `"natural"` (default) | BP probabilistic inference | None |
| `"python"` | Lint + test | ruff, pytest |
| `"lean4"` | Formal proof checking | lean build |

Formal declarations passing CI get belief ≈ 1 - ε. Failing = hole.

### Storage Model Mapping

| Declaration | `Knowledge.type` value |
|-------------|----------------------|
| `#claim` | `"claim"` |
| `#claim_relation` | `"contradiction"` or `"equivalence"` (from `type:` param) |
| `#observation` | `"observation"` (new — add to `Knowledge.type` enum) |
| `#setting` | `"setting"` |
| `#question` | `"question"` |

### Relation Types

`#claim_relation` supports:

- `type: "contradiction"` — mutual exclusion constraint
- `type: "equivalence"` — biconditional constraint

```typst
#claim_relation("tied_balls_contradiction",
  type: "contradiction",
  between: ("tied_pair_slower", "tied_pair_faster"),
)[同一定律自相矛盾。]
```

## Proof Block and Tactics

A proof block is the optional second content block of `#claim` / `#claim_relation`. It contains **tactics** and free-form prose that explain the reasoning from premises to conclusion.

Proof blocks can mix formalized parts (tactics) with informal parts (prose). Tactics tell the reviewer which reasoning strategy is being used; prose provides natural-language elaboration. Not every paragraph needs a tactic — the author formalizes what they choose to.

### Tactics

Every tactic has the form: `#tactic_name` + optional name + content body.

```typst
// Anonymous — most cases
#deduce[reasoning content...]

// Named — when other steps need to @ref this step
#deduce("step_name")[reasoning content...]
```

#### Structural Tactic

| Tactic | Purpose | Factor graph effect |
|--------|---------|-------------------|
| `#premise("name")` | Declare independent premise | **Input edge** to noisy-AND factor |

`#premise` is the **only** tactic that affects the factor graph. All other tactics are narrative annotations.

#### Reasoning Strategy Tactics

These tell the reviewer **which reasoning strategy** is being used, so they know what to check. None affect the factor graph.

| Tactic | Strategy | Reviewer checks |
|--------|----------|----------------|
| `#deduce` | Deductive reasoning | Does the conclusion follow from the premises? |
| `#abduction` | Inference to best explanation | Are there alternative explanations? Is the evidence reliable? |
| `#by_contradiction` | Reductio ad absurdum | Are the derived conclusions truly mutually exclusive? |
| `#by_cases` | Case analysis | Are the cases exhaustive? Does each case hold? |
| `#by_induction` | Inductive generalization | Are the samples sufficient? Any counterexamples? |
| `#by_analogy` | Analogical reasoning | Are the compared objects truly similar? Do differences affect the conclusion? |
| `#by_elimination` | Process of elimination | Are the alternatives exhaustive? Is each elimination justified? |
| `#by_extrapolation` | Trend extrapolation / limit argument | Is the trend monotonic? Is the limit reasonable? |
| `#synthesize` | Convergence of multiple evidence lines | Are the evidence lines independent? Any contradictory evidence ignored? |

#### Other References

| Syntax | Purpose | Factor graph effect |
|--------|---------|-------------------|
| `@name` (in text) | Reference for context | No structural effect |

#### Nesting

Tactics can nest. For example, `#by_contradiction` contains `#deduce` steps:

```typst
#by_contradiction[
  #deduce[From the hypothesis, the composite should be slower.]
  #deduce[But by the same law, the composite should be faster.]
]
```

### Premise vs. Context

This distinction is critical for factor graph construction:

- **Premise** (`#premise`): explicitly declared, becomes an independent input edge in the noisy-AND factor. All premises of a claim must be mutually independent.
- **Context** (`@ref` in text): informational reference for human readers. No effect on factor graph structure.

### Proof State

Build-time analysis automatically categorizes all declarations:

```
✓ established:
  tied_balls_contradiction    (proof: 2 premises, 2 derives, 1 contradict)
  vacuum_prediction           (proof: 3 premises, 1 derive)

○ axioms (no proof needed):
  thought_experiment_env      (setting)
  medium_density_observation  (observation)

? holes:
  heavier_falls_faster        (claim, used as premise, no proof)

? questions:
  follow_up_question          (open)
```

Rules:
- `#setting` / `#observation` / `#question` → never holes
- `#claim` / `#claim_relation` with proof → established
- `#claim` / `#claim_relation` without proof, used as `#premise` → **hole**
- `#claim` without proof, never used → standalone declaration (warning)

**Cross-module semantics:** Hole detection is **package-wide**. If module A defines `#claim("X")` without proof, and module B uses `#premise("X")`, then `X` is a hole in the package. The hole is reported at the declaration site (module A), not the usage site.

## Factor Graph Mapping

### `#claim` with proof → noisy-AND reasoning factor

```
For each #claim with proof block:
  1. Collect all #premise("name") → independent input edges
  2. The claim itself → output (conclusion)
  3. Emit one noisy-AND factor node
  4. #derive nodes → stored in proof trace only, not in factor graph
  5. #contradict / #equate inside proof → narrative only, no factor emitted
```

### `#claim_relation` → constraint factor

```
For each #claim_relation:
  1. between: ("a", "b") → the constrained variable nodes
  2. type: "contradiction" → mutex_constraint factor
     type: "equivalence" → equiv_constraint factor
  3. If proof block present → additionally emit a noisy-AND factor
     for the relation node itself (with #premise as inputs)
```

### Summary

Example factor graph from galileo fixture:

```
heavier_falls_faster ──────┐
thought_experiment_env ────┤→ tied_balls_contradiction
                           │
medium_density_observation ┤→ air_resistance_is_confound
everyday_observation ──────┘

tied_balls_contradiction ──┐
air_resistance_is_confound ┤→ vacuum_prediction
inclined_plane_observation ┘
```

Noisy-AND + leak potential (per inference-theory.md v2.0):
- All premises true, conclusion true → p (support)
- All premises true, conclusion false → 1-p
- Any premise false, conclusion true → ε (leak)
- Any premise false, conclusion false → 1-ε

## Package Structure

Unchanged from v1. Uses Typst's native package system:

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

### Module Declaration

One module per `.typ` file:

```typst
#module("reasoning", title: "核心推理 — 伽利略的论证")
```

### Cross-Module References

Module-level `#use` imports declarations from other modules:

```typst
#use("aristotle.heavier_falls_faster")
#use("setting.thought_experiment_env")
```

This makes the name available for `#premise()` and `@ref` within the current module.

## Typst Content Model Constraint

In Typst, `#let x = func()` captures the return value but **discards content** produced by `func()`, including `state.update()` calls. Since `@gaia/lang` functions use `state.update()` to collect graph data, all DSL functions **must be placed as content** — never captured with `#let`.

```typst
// ❌ Wrong — state.update() lost
#let x = claim("name")[text]

// ✅ Correct — state.update() placed in document
#claim("name")[text]
```

All declarations use string-name references, not variable binding. Cross-references use Typst-native `@label` / `<label>` mechanism, with labels auto-generated by declaration functions.

## Build Pipeline

### Stage 1: Typst Compilation + Metadata Extraction

```
.typ source files
  ↓ typst compile (render PDF)
  ↓ typst query (extract metadata)
JSON: {declarations, factors, proof_traces, modules, exports}
```

`@gaia/lang` functions simultaneously:
1. **Render** readable document content
2. **Collect** graph structure via `state.update()` → `#export-graph()`

`#export-graph()` emits metadata with schema:

```json
{
  "declarations": [
    {"name": "...", "type": "claim|observation|setting|question",
     "module": "...", "content": "...", "content_type": "natural|python|lean4"}
  ],
  "factors": [
    {"conclusion": "...", "premises": ["..."], "factor_type": "reasoning"}
  ],
  "constraints": [
    {"type": "contradiction|equivalence", "between": ["...", "..."], "name": "..."}
  ],
  "proof_traces": [
    {"conclusion": "...", "steps": [
      {"tactic": "premise|deduce|abduction|by_contradiction|...", "name": "...", "content": "...",
       "children": [...]}
    ]}
  ],
  "modules": ["..."],
  "module_titles": {"name": "title"},
  "exports": ["..."]
}
```

### Stage 2: Proof State Analysis

Python-side analysis of extracted JSON:
- Classify declarations by proof status (established / axiom / hole / question)
- Validate premise independence
- Report holes

### Stage 3: Factor Graph Compilation

Extract noisy-AND factor graph from proof structure:
- Each proven claim → one factor node
- `#premise` → input edges
- All other tactics (`#deduce`, `#abduction`, etc.) → proof trace only, no factors
- `#claim_relation` → constraint factors (mutex/equiv)

**BP model target:** Factor graph output follows the noisy-AND + leak model defined in inference-theory.md v2.0. Default link strength `p` and leak `ε` are NOT set at build time — they are deferred to the review stage, consistent with the "no priors in authoring" principle.

### Stage 4: Formal Verification (optional)

For `type:` ≠ `"natural"`:
- Extract code blocks
- Run appropriate toolchain (ruff, lean, coqc, etc.)
- Pass → belief = 1 - ε; Fail → mark as hole

### CLI

```bash
gaia build [path]                    # Default output
gaia build [path] --format json      # Factor graph JSON
gaia build [path] --format pdf       # Typst compile to PDF
gaia build [path] --proof-state      # Proof state report
gaia build [path] --check            # Hole check + formal verification
```

## Rendering

Typst source IS the readable document. `@gaia/lang` functions render DSL into clean Typst:

### Declaration without proof

```
*heavier falls faster* (observation): 重者下落更快。 <heavier-falls-faster>
```

### Declaration with proof

```
=== tied balls contradiction <tied-balls-contradiction>
*Claim:* 矛盾。

*Proof:*
- *Premise:* @heavier-falls-faster
- *Premise:* @thought-experiment-env

  1. *tied pair slower:* 复合体更慢。
  2. *tied pair faster:* 复合体更快。
  ⊥ @tied-pair-slower ↔ @tied-pair-faster
```

## Complete Example: galileo.typ

```typst
#import "@gaia/lang/v2": *

#module("galileo", title: "伽利略的论证")

// ── Cross-module imports ──
#use("aristotle.heavier_falls_faster")
#use("aristotle.everyday_observation")
#use("setting.thought_experiment_env")
#use("setting.vacuum_env")

// ── Observations (no proof needed) ──
#observation("medium_density_observation")[
  在水、油、空气等不同介质中比较轻重物体的下落，
  会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
]

#observation("inclined_plane_observation")[
  伽利略的斜面实验把下落过程放慢到可测量尺度后显示：
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，
  与"重量越大速度越大"的简单比例律并不相符。
]

// ── Tied balls contradiction ──
#claim("tied_balls_contradiction")[
  在假设"重者下落更快"的前提下，
  绑球系统同时被预测为更快和更慢，产生矛盾。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")

  #by_contradiction[
    #deduce[
      由假设，轻球天然比重球慢。
      轻球应拖慢重球，复合体 HL 速度应慢于 H。
    ]
    #deduce[
      但按同一定律，复合体 HL 总重量大于 H，
      应比 H 更快。
    ]
  ]
]

// ── Medium elimination ──
#claim("air_resistance_is_confound")[
  日常观察到的速度差异更应被解释为介质阻力造成的表象，
  而不是重量本身决定自由落体速度的证据。
][
  #premise("medium_density_observation")

  #abduction[
    如果速度差异由介质阻力造成，那么介质越稀薄差异越小。
    @medium-density-observation 正好显示了这一点，
    说明介质阻力是更好的解释。
  ]
]

// ── Final synthesis ──
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  #synthesize[
    绑球矛盾推翻旧定律、
    介质分析排除干扰因素、
    斜面实验提供正面支持。
    三条独立线索汇聚，在真空中结论成立。
  ]
]
```

## Changes from v1

### Removed
- `#chain` — replaced by proof blocks on `#claim`
- Chain auto-inject — replaced by explicit `#premise` / `@ref`
- `ctx:` parameter — context is just `@ref` in text, no structural role

### Added
- **Proof block** — `#claim`'s second content block
- **Tactics** — `#premise` (structural) + 9 reasoning strategy tactics (`#deduce`, `#abduction`, `#by_contradiction`, `#by_cases`, `#by_induction`, `#by_analogy`, `#by_elimination`, `#by_extrapolation`, `#synthesize`)
- **Proof state** — automatic established/hole/axiom tracking
- **`#observation`** — empirical fact type (no proof needed)
- **`#claim_relation`** — relation declaration (contradiction/equivalence)
- **`type:` parameter** — formal verification support (Python/Lean4/etc.)

### Unchanged
- Typst native package system (`typst.toml`)
- One module per `.typ` file
- `#module`, `#package`, `#export-graph` functions
- String-name references (Typst content model constraint)
- `@ref` / `<label>` native cross-references
- Metadata extraction via `typst.query()`
- No priors in authoring (priors come from review stage)

## Design Scope

### In scope
- `@gaia/lang` v2 Typst library: all declaration functions + tactics
- Migrate galileo_falling_bodies fixture to v2 syntax
- `gaia build --proof-state` report
- Factor graph extraction (noisy-AND structure)
- Python typst_loader adaptation for v2 metadata

### Out of scope
- Formal verification CI pipeline (`type: "python"` etc.) — future
- Review pipeline / Inference pipeline
- Cross-package `#use` resolution
- Retraction relation type — deferred to future `#claim_relation(type: "retraction", ...)` extension

## Future Extensions

### Lean-like Features
- **Proof state visualization** — show hypotheses + remaining goals at each tactic step
- **Auto-tactics** — system-suggested proof steps (LLM-assisted)
