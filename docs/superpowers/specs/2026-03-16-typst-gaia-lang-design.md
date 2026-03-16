# Typst-based Gaia Language Design

**Date:** 2026-03-16
**Scope:** POC — authoring surface + `gaia build` (Markdown output)
**Fixture:** galileo_falling_bodies only

## Motivation

Current YAML authoring surface is verbose, mixes structure with parameterization (prior), and lacks variable-binding safety. Typst offers content blocks as first-class citizens, a native package system, variable references with compile-time checking, and dual output (readable document + structured data).

## Core Principle: Separation of Concerns

- **Authoring** (`.typ` files) — structure and content only, no priors
- **Review** (sidecar YAML) — LLM assigns priors after reading rendered Markdown
- **Inference** (Graph IR + BP) — out of scope for this POC

## Package Structure

Uses Typst's native package system:

```
galileo_falling_bodies/
  typst.toml              # Typst-native manifest (name, version, authors)
  lib.typ                 # Entrypoint: imports modules, declares exports
  motivation.typ
  setting.typ
  aristotle.typ
  reasoning.typ
  follow_up.typ
```

### typst.toml

```toml
[package]
name = "galileo_falling_bodies"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Galileo Galilei"]
description = "伽利略落体论证 — 绑球思想实验推翻亚里士多德落体定律"
```

### lib.typ (entrypoint)

```typst
#import "@gaia/lang": *
#import "motivation.typ"
#import "setting.typ"
#import "aristotle.typ"
#import "reasoning.typ"
#import "follow_up.typ"

#package("galileo_falling_bodies",
  modules: (motivation, setting, aristotle, reasoning, follow_up),
  export: (
    reasoning.vacuum_prediction,
    reasoning.aristotle_contradicted,
    follow_up.follow_up_question,
  ),
)

#export-graph()
```

## Authoring Surface

### Knowledge Functions

Each knowledge type is a function. Behavior differs inside vs outside a chain:

| Function | Outside chain | Inside chain |
|---|---|---|
| `claim(name, ...)` | Independent node, no premise | Chain step, supports premise, pipeline auto-inject |
| `setting(name, ...)` | Independent node | Chain step (rare) |
| `question(name, premise:, ctx:)` | Independent node | Chain step |
| `contradiction(name, ...)` | Not allowed | Chain step, generates mutex_constraint |
| `equivalence(name, ...)` | Not allowed | Chain step, generates equiv_constraint |

### Function Signature

```
claim(name, premise: (), ctx: ())[content]
```

- `name` — identifier within module
- `premise:` — named parameter, list of premise names (strings)
- `ctx:` — named parameter, list of context names (strings). Named `ctx` instead of `context` because `context` is a reserved keyword in Typst.
- `[content]` — Typst content block, natural language description
- No `prior:` parameter — priors come from review step

### References

```typst
#use("aristotle.heavier_falls_faster")
```

Registers an external knowledge reference. Always place as content (never capture with `#let`, see "Typst Content Model Constraint" below). Reference imported knowledge by its string name in `premise:` and `ctx:` parameters.

### Chains

```typst
#chain("chain_name")[
  #claim("step_1")[...]
  #claim("step_2", premise: ("external_ref",))[...]
]
```

Rules:
- **Auto-inject:** previous step automatically becomes first premise of next step
- **Explicit premise: overrides auto-inject** — if `premise:` is provided, no auto-injection
- **Last step = conclusion**
- **Never capture with `#let`** — `#let result = chain(...)` discards all state updates inside the chain body

### Typst Content Model Constraint

In Typst, `#let x = func()` captures the return value but **discards the content** produced by `func()`, including `state.update()` calls. Since `@gaia/lang` functions use `state.update()` to register nodes and factors, they must **always be placed as content** — never captured with `#let`.

**Wrong (0 nodes registered):**
```typst
#let heavier = claim("heavier_falls_faster")[text]  // state.update() is LOST
```

**Correct:**
```typst
#claim("heavier_falls_faster")[text]  // state.update() is placed in document
#claim("step_2", premise: ("heavier_falls_faster",))[...]  // reference by string name
```

This applies to all knowledge functions (`claim`, `setting`, `question`, `contradiction`, `equivalence`), `chain`, and `use`.

### Module Declaration

```typst
#module("name", title: "optional title")
```

One module per `.typ` file.

## Full Example: reasoning.typ

```typst
#import "@gaia/lang": *

#module("reasoning", title: "核心推理 — 伽利略的论证")

// ── references (placed as content, never captured with #let) ──
#use("aristotle.heavier_falls_faster")
#use("aristotle.everyday_observation")
#use("setting.thought_experiment_env")
#use("setting.vacuum_env")

// ── independent knowledge (no premise, no chain) ──
#claim("medium_density_observation")[
  在不同介质中观察物体下落，会发现介质越稠密，
  速度差异越明显；介质越稀薄，差异越不明显。
]

#claim("inclined_plane_observation")[
  在斜面实验中，不同重量的球几乎同时到达底部，
  且斜面越光滑、倾角越大，差异越小。
]

// ── chain: 绑球矛盾论证 ──
// Reference knowledge by string names in premise:/ctx: parameters
#chain("tied_balls_argument")[
  #claim("tied_pair_slower",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[复合体因轻球拖拽下落更慢]

  #claim("tied_pair_faster",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[复合体总重更大下落更快]

  #contradiction("tied_balls_contradiction",
    premise: ("tied_pair_slower", "tied_pair_faster"),
  )[同一定律同时预测更慢和更快，自相矛盾，定律不成立]
]

// ── chain: 介质消除论证 ──
#chain("medium_elimination")[
  #claim("medium_difference_shrinks",
    premise: ("medium_density_observation",),
  )[介质越稀薄，差异越小]

  #claim("air_resistance_is_confound",
    premise: ("everyday_observation",),
  )[日常观察到的速度差异是介质阻力的表象]
]

// ── chain: 最终预测 ──
#chain("synthesis")[
  #claim("inclined_plane_supports",
    premise: ("inclined_plane_observation",),
  )[斜面实验支持等速下落假说]

  #claim("vacuum_prediction",
    premise: ("tied_balls_contradiction", "air_resistance_is_confound", "inclined_plane_supports"),
    ctx: ("vacuum_env",),
  )[在真空中，不同重量的物体应以相同速率下落]
]
```

## Build Output

### CLI

```
gaia build [path]                → Markdown (default)
gaia build [path] --format md    → Markdown
gaia build [path] --format json  → Structured JSON knowledge graph
gaia build [path] --format all   → Both
```

### Markdown Output

The Typst source compiles to a readable document suitable for LLM review. Structure:

```markdown
# reasoning — 核心推理 — 伽利略的论证

## References
- `law` ← aristotle.heavier_falls_faster
- `obs` ← aristotle.everyday_observation
- `te_env` ← setting.thought_experiment_env
- `vac_env` ← setting.vacuum_env

## Independent Knowledge

### medium_density_observation [claim]
在不同介质中观察物体下落，会发现介质越稠密，
速度差异越明显；介质越稀薄，差异越不明显。

### inclined_plane_observation [claim]
在斜面实验中，不同重量的球几乎同时到达底部...

## Chain: tied_balls_argument

### Step 1: tied_pair_slower [claim]
> Premise: law, te_env

复合体因轻球拖拽下落更慢

### Step 2: tied_pair_faster [claim]
> Premise: law, te_env

复合体总重更大下落更快

### Conclusion: tied_balls_contradiction [contradiction]
> Premise: tied_pair_slower, tied_pair_faster

同一定律同时预测更慢和更快，自相矛盾，定律不成立

...
```

### JSON Output (for future inference)

Extracted via `metadata()` + `typst-py` query. Structure matches current Graph IR `RawGraph` schema: knowledge_nodes + factor_nodes. Out of scope for this POC but the `@gaia/lang` library emits metadata from day one.

## Implementation: @gaia/lang Typst Library

A Typst package providing all Gaia primitives. Implemented as functions that:
1. **Render** readable content (headings, blockquotes for premises, body text)
2. **Emit** `metadata()` for structured extraction

Uses Typst `state` for:
- Tracking chain pipeline (current step output for auto-injection)
- Collecting all nodes and factors for `export-graph()`
- Detecting chain vs non-chain context

## POC Scope

### In scope
- `@gaia/lang` Typst library: `module`, `claim`, `setting`, `question`, `contradiction`, `equivalence`, `chain`, `use`, `package`, `export-graph`
- Migrate galileo_falling_bodies fixture from YAML to `.typ`
- `gaia build` command: Typst → Markdown (default output)
- Typst → JSON extraction via `typst-py` (basic wiring)

### Out of scope
- Review pipeline (`gaia review`)
- Inference pipeline (`gaia infer`)
- Other fixtures (newton, einstein, paper packages)
- Cross-package `use()` resolution at build time
- Publishing to Typst Universe

## Dependencies

- `typst` Python package (typst-py) for compilation and query
- Typst compiler (bundled via typst-py, no separate install needed)

## Key Design Decisions

1. **No prior in authoring** — priors come from review, not authoring
2. **Typst native package system** — `typst.toml` replaces `package.yaml`
3. **One module = one `.typ` file**
4. **Chain auto-pipeline** — previous step auto-injects as first premise; explicit `premise:` overrides
5. **String-name references** — all knowledge is referenced by string name, never by variable binding (`#let` discards content in Typst)
6. **No InferAction / StepApply** — reasoning content lives directly in claim/step content
7. **contradiction/equivalence are chain steps** — not standalone declarations
8. **`ctx` not `context`** — Typst reserves `context` as a keyword; we use `ctx` for the context parameter
