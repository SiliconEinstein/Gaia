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

A proof block is the optional second content block of `#claim` / `#claim_relation`. It contains **tactics** that transform the proof state from premises to conclusion.

### Tactics

| Tactic | Purpose | Factor graph effect |
|--------|---------|-------------------|
| `#premise("name")` | Declare independent premise | **Input edge** to noisy-AND factor |
| `#derive("name")[content]` | Derive intermediate conclusion | Not visible to engine |
| `#contradict("a", "b")` | Annotate contradiction between two derives | None (proof narrative only) |
| `#equate("a", "b")` | Annotate equivalence between two derives | None (proof narrative only) |
| `@name` (in text) | Reference for context | No structural effect |

**Important:** `#contradict` and `#equate` inside proof blocks are **narrative annotations** — they help human/LLM reviewers understand the proof structure but have no effect on the factor graph. The enclosing `#claim`'s noisy-AND factor (from `#premise` declarations) is the only factor emitted. For factor-graph-level constraints, use top-level `#claim_relation` instead.

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
  reasoning.typ           # Module
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
      {"tactic": "premise|derive|contradict|equate", "name": "...", "content": "..."}
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
- `#derive` → proof trace only
- `#contradict` / `#equate` inside proofs → narrative only, no factors
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

## Complete Example: reasoning.typ

```typst
#import "@gaia/lang": *

#module("reasoning", title: "核心推理 — 伽利略的论证")

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
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势。
]

// ── Tied balls contradiction ──
#claim("tied_balls_contradiction")[
  在假设"重者下落更快"的前提下，
  绑球系统同时被预测为更快和更慢，产生矛盾。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")

  #derive("tied_pair_slower")[
    由 @heavier-falls-faster，轻球天然比重球慢。
    在 @thought-experiment-env 中，轻球应拖慢重球，
    复合体 HL 的下落速度应慢于单独的重球 H。
  ]
  #derive("tied_pair_faster")[
    但按 @heavier-falls-faster 的同一定律，
    复合体 HL 总重量大于 H，应比 H 更快。
  ]
  #contradict("tied_pair_slower", "tied_pair_faster")
]

// ── Medium elimination ──
#claim("air_resistance_is_confound")[
  日常观察到的速度差异更应被解释为介质阻力造成的表象，
  而不是重量本身决定自由落体速度的证据。
][
  #premise("medium_density_observation")
  #premise("everyday_observation")

  #derive("medium_difference_shrinks")[
    从水到空气，随着介质变稀薄，轻重物体的速度差异持续缩小，
    说明差异更像是外部阻力效应。
  ]
]

// ── Final synthesis ──
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  #derive("inclined_plane_supports")[
    斜面实验显示不同重量的小球获得近似一致的加速趋势，
    支持"重量不是决定落体快慢的首要因素"。
  ]

  综合三条线索：绑球矛盾推翻旧定律、
  介质分析排除干扰因素、斜面实验提供正面支持。
  在 @vacuum-env 下，结论成立。
]
```

## Changes from v1

### Removed
- `#chain` — replaced by proof blocks on `#claim`
- Chain auto-inject — replaced by explicit `#premise` / `@ref`
- `ctx:` parameter — context is just `@ref` in text, no structural role

### Added
- **Proof block** — `#claim`'s second content block
- **Tactics** — `#premise`, `#derive`, `#contradict`, `#equate`
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
- Extended tactics (`#induce`, `#by_cases`, `#observe` etc.) — add as needed
- Review pipeline / Inference pipeline
- Cross-package `#use` resolution
- Retraction relation type — deferred to future `#claim_relation(type: "retraction", ...)` extension

## Future Extensions

### Extended Tactics
Additional reasoning patterns, each with different link strength priors:

| Tactic | Pattern | Typical link strength |
|--------|---------|----------------------|
| `#derive` | Deductive | High |
| `#induce` | Inductive generalization | Medium |
| `#by_cases` | Case analysis | Depends on exhaustiveness |
| `#observe` | Introduce empirical evidence | Medium-low |

### Lean-like Features
- **Proof state visualization** — show hypotheses + remaining goals at each tactic step
- **Tactic extensibility** — user-defined tactics as Typst functions
- **Auto-tactics** — system-suggested proof steps (LLM-assisted)
