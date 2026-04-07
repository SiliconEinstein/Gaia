# Gaia Lang

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/SiliconEinstein/Gaia/graph/badge.svg)](https://codecov.io/gh/SiliconEinstein/Gaia)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python DSL for authoring machine-readable scientific knowledge. Gaia Lang lets researchers declare propositions, logical constraints, and reasoning strategies as Python objects, then compiles them into a canonical intermediate representation (Gaia IR) for inference via belief propagation.

## Quick Example

Galileo's thought experiment: tie a heavy stone 🪨 to a light stone 🪶. Does the composite fall faster or slower?

```python
from gaia.lang import claim, contradiction, deduction, abduction

# 📋 The observation everyone agrees on
obs_daily = claim("Heavy objects fall faster than light ones in air.")

# 🏛️ Two competing explanations
aristotle = claim("🏛️ Speed is proportional to weight — heavier = faster.")
air_resistance = claim("🌬️ The speed difference is caused by air resistance, not weight.")

# 🔍 Abduction: which explanation better accounts for the observation?
abduction(observation=obs_daily, hypothesis=air_resistance, alternative=aristotle,
    reason="Both explain why heavy objects fall faster in air.")

# 🤔 Meanwhile, Aristotle's doctrine implies contradictory predictions
composite_slower = claim("🪨🪶 The composite falls SLOWER than the heavy stone alone.")
composite_faster = claim("🪨🪶 The composite falls FASTER than either stone alone.")
deduction(premises=[aristotle], conclusion=composite_slower,
    reason="If heavier = faster, the light stone drags the heavy one back.")
deduction(premises=[aristotle], conclusion=composite_faster,
    reason="If heavier = faster, the heavier composite must fall faster.")

# ⚔️ Same premise, opposite conclusions — that's a contradiction!
paradox = contradiction(composite_slower, composite_faster,
    reason="Aristotle's own logic predicts both faster AND slower")

# 💡 Remove the air, remove the difference
vacuum_law = claim("💡 In vacuum, all bodies fall at the same rate.")
deduction(premises=[air_resistance], conclusion=vacuum_law,
    reason="If air resistance is the sole cause, removing it means all fall equally.")
```

`gaia compile . && gaia infer .` compiles this into a factor graph and runs belief propagation:

```mermaid
graph TD
    obs_daily["📋 Daily observation (0.90 → 1.00 📈)"]:::premise
    aristotle["🏛️ Aristotle: heavier = faster (0.90 → 0.07 📉)"]:::premise
    air_resistance["🌬️ Air resistance (0.50 → 0.94 📈)"]:::derived
    composite_slower["🪨🪶 < 🪨 Composite slower (0.60 → 0.40 📉)"]:::derived
    composite_faster["🪨🪶 > 🪨 Composite faster (0.60 → 0.40 📉)"]:::derived
    paradox["⚔️ paradox (0.98)"]:::derived
    vacuum_law["💡 Vacuum law (0.30 → 0.96 📈)"]:::derived
    strat_0(["🔍 abduction"])
    obs_daily --> strat_0
    aristotle --> strat_0
    strat_0 --> air_resistance
    strat_1(["🧠 deduction"])
    aristotle --> strat_1
    strat_1 --> composite_slower
    strat_2(["🧠 deduction"])
    aristotle --> strat_2
    strat_2 --> composite_faster
    strat_3(["🧠 deduction"])
    air_resistance --> strat_3
    strat_3 --> vacuum_law
    oper_0{{"⊗ contradiction"}}:::contra
    composite_slower --- oper_0
    composite_faster --- oper_0
    oper_0 --- paradox

    classDef setting fill:#f0f0f0,stroke:#999,color:#333
    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333
    classDef derived fill:#ddffdd,stroke:#44bb44,color:#333
    classDef contra fill:#ffebee,stroke:#c62828,color:#333
```

| Claim | Prior | → | Belief | |
|-------|------:|---|-------:|---|
| 📋 Daily observation | 0.90 | → | **1.00** | 📈 confirmed by both explanations |
| 🏛️ Aristotle's law | 0.90 | → | **0.07** | 📉 contradiction propagates back — refuted |
| 🌬️ Air resistance | 0.50 | → | **0.94** | 📈 abduction: the better explanation wins |
| 🪨🪶 Composite slower | 0.60 | → | **0.40** | 📉 contradiction forces mutual exclusion |
| 🪨🪶 Composite faster | 0.60 | → | **0.40** | 📉 symmetric with composite slower |
| 💡 Vacuum law | 0.30 | → | **0.96** | 📈 Galileo wins — remove air, all fall equally |

Note how the contradiction and abduction are independent subgraphs, yet BP automatically combines both lines of evidence: the contradiction refutes Aristotle (0.90 → 0.07) while the abduction elevates air resistance (0.50 → 0.94), and together they lift the vacuum law from a speculative 0.30 to a near-certain **0.96** — no new experimental data needed, just the structure of the reasoning itself.

## Install

```bash
pip install gaia-lang
```

For development:

```bash
git clone https://github.com/SiliconEinstein/Gaia.git
cd Gaia && uv sync
```

### Claude Code Plugin

Gaia provides a [Claude Code](https://claude.ai/code) plugin with skills that guide the full knowledge formalization workflow — from reading a paper to publishing a Gaia package on GitHub.

```bash
# 1. Add the Gaia marketplace (one-time setup)
/plugin marketplace add SiliconEinstein/Gaia

# 2. Install the gaia plugin
/plugin install gaia
```

**Available skills:**

| Skill | Purpose |
|-------|---------|
| `/gaia` | Entry point — routes to the right skill based on your request |
| `/gaia:formalization` | Four-pass paper formalization: extract nodes → connect strategies → check completeness → refine types |
| `/gaia:gaia-cli` | CLI reference — `gaia init`, `compile`, `infer`, `check`, `register`, `add` |
| `/gaia:gaia-lang` | DSL reference — knowledge types, operators, strategies, metadata, package structure |
| `/gaia:review` | Write review sidecars — assign priors, judge strategies, parameterize inference |
| `/gaia:publish` | Generate GitHub presentation (`--github` skeleton → narrative README → push) |

### Formalize a Paper End-to-End

With the plugin installed, formalizing a scientific paper into a Gaia knowledge package is a three-step process:

1. **`/gaia:formalization`** — Point Claude at your paper (PDF or text in `artifacts/`). The skill guides a four-pass process: extract knowledge nodes, connect reasoning strategies, check completeness, and refine strategy types. Output: a compilable Gaia package with review sidecar.

2. **`/gaia:publish`** — After `gaia compile . --github` generates the skeleton, this skill fills in the narrative README, writes section summaries, and pushes to GitHub. Your repo gets a human-readable presentation of the formalized knowledge with interactive graphs.

3. **`gaia register`** — Submit the package to the [Gaia Official Registry](https://github.com/SiliconEinstein/gaia-registry) so others can `gaia add` it as a dependency.

## CLI Workflow

```
gaia init → gaia add → write package → gaia compile → write review → gaia infer → gaia compile --github → /gaia:publish → gaia register
(scaffold)  (add deps)   (DSL code)     (DSL → IR)   (self-review)  (BP preview)  (GitHub skeleton)      (fill narrative) (registry PR)
```

| Command | Purpose |
|---------|---------|
| `gaia init <name>` | Scaffold a new Gaia knowledge package |
| `gaia add <package>` | Install a registered Gaia package from the [official registry](https://github.com/SiliconEinstein/gaia-registry) |
| `gaia compile [path]` | Compile Python DSL to Gaia IR (`.gaia/ir.json`) |
| `gaia compile --github [path]` | Generate GitHub presentation skeleton (`.github-output/`): wiki, README, React Pages, graph.json |
| `gaia compile --module-graphs [path]` | Generate per-module detailed reasoning graphs to `docs/detailed-reasoning.md` |
| `gaia check [path]` | Validate package structure and IR consistency (used by registry CI) |
| `gaia infer [path]` | Run belief propagation with a review sidecar |
| `gaia register [path]` | Submit package to the [Gaia Official Registry](https://github.com/SiliconEinstein/gaia-registry) |

## Create a Knowledge Package

**1. Initialize**

```bash
gaia init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
```

This scaffolds a complete package with `pyproject.toml` (including `[tool.gaia]`
config and a generated UUID), the correct `src/` directory layout, and a DSL
template. Package name must end with `-gaia`.

**2. Write DSL declarations**

Organize your knowledge in separate modules under the package directory. `gaia compile` imports the top-level package, so any file transitively imported from `__init__.py` is automatically discovered.

`src/galileo_falling_bodies/knowledge.py` — declare propositions:

```python
from gaia.lang import claim

aristotle = claim("Aristotle's doctrine: the heavier an object is, the faster it falls.")
heavy_faster = claim("A heavy stone falls faster than a light one in air.")
composite_slower = claim("The composite should fall slower — the light stone drags the heavy one back.")
composite_faster = claim("The composite should fall faster — the combined weight is greater.")
vacuum_law = claim("In vacuum all bodies fall at the same rate.")
```

`src/galileo_falling_bodies/reasoning.py` — declare constraints and strategies:

```python
from gaia.lang import contradiction, deduction
from .knowledge import aristotle, composite_slower, composite_faster, heavy_faster, vacuum_law

deduction(premises=[aristotle], conclusion=composite_slower,
    reason="If heavier = faster, then the light stone must slow down the heavy one.")
deduction(premises=[aristotle], conclusion=composite_faster,
    reason="If heavier = faster, then the heavier composite must fall faster.")

paradox = contradiction(composite_slower, composite_faster,
    reason="Same premise yields opposite conclusions")

galileo_argument = deduction(
    premises=[paradox, heavy_faster],
    conclusion=vacuum_law,
    reason="Contradiction in Aristotle's doctrine forces a new law",
)
```

`src/galileo_falling_bodies/__init__.py` — re-export all declarations:

```python
from .knowledge import aristotle, heavy_faster, composite_slower, composite_faster, vacuum_law
from .reasoning import paradox, galileo_argument

__all__ = [
    "aristotle", "heavy_faster", "composite_slower",
    "composite_faster", "vacuum_law",
    "paradox", "galileo_argument",
]
```

**3. Compile and validate**

```bash
gaia compile .
gaia check .
```

**4. Write a review sidecar** to assign priors and strategy parameters for inference.

Reviews live in `src/galileo_falling_bodies/reviews/`. Each review is a Python file exporting a `REVIEW` bundle — different reviewers can assign different priors to the same knowledge.

`src/galileo_falling_bodies/reviews/self_review.py`:

```python
from gaia.review import ReviewBundle, review_claim, review_strategy
from .. import aristotle, heavy_faster, galileo_argument

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        review_claim(aristotle, prior=0.9,
            judgment="supporting",
            justification="Widely accepted for 2000 years, matches everyday experience."),
        review_claim(heavy_faster, prior=0.8,
            judgment="supporting",
            justification="Well-documented observation in air."),
        review_strategy(galileo_argument,
            judgment="formalized",
            justification="Classic reductio ad absurdum."),
    ],
)
```

**5. Run belief propagation**

```bash
gaia infer .
```

The engine compiles the IR into a factor graph, automatically selects the best algorithm (exact junction tree for small graphs, loopy BP for larger ones), and writes results to `.gaia/reviews/self_review/`:

```
Inferred 5 beliefs from 2 priors and 0 strategy parameter records
Method: JT (exact), 2ms
Review: self_review
Output: .gaia/reviews/self_review/beliefs.json
```

`beliefs.json` contains the posterior probability for each claim after propagation:

| Claim | Prior | → | Posterior | |
|-------|------:|---|----------:|---|
| `aristotle` | 0.90 | → | **0.01** | ⬇️ contradiction propagates back — Aristotle refuted |
| `heavy_faster` | 0.80 | → | **0.67** | ⬇️ pulled down by the deduction chain |
| `composite_slower` | — | → | **0.34** | ⬇️ contradiction forces mutual exclusion |
| `composite_faster` | — | → | **0.34** | ⬇️ symmetric with `composite_slower` |
| `vacuum_law` | — | → | **0.83** | ⬆️ deduction from the contradiction raises belief |

If multiple reviews exist, specify which one: `gaia infer --review self_review .`

**6. Generate GitHub presentation**

```bash
gaia compile . --github
```

Generates a `.github-output/` directory with:
- **README.md** skeleton with coarse Mermaid overview graph and conclusion table
- **Wiki pages** — structured claim reference with QID, prior, belief, reasoning
- **graph.json** — knowledge graph data for interactive visualization
- **narrative-outline.md** — topologically ordered outline for the `/gaia:publish` skill

Run `gaia infer .` first so the output includes up-to-date belief values. Then use `/gaia:publish` to fill in the narrative and push to GitHub.

**7. Publish**

```bash
git tag v1.0.0 && git push origin main --tags
gaia register . --registry-dir ../gaia-registry --create-pr
```

## Install a Package

Add a registered Gaia knowledge package as a dependency:

```bash
gaia add galileo-falling-bodies-gaia
```

This queries the [Gaia Official Registry](https://github.com/SiliconEinstein/gaia-registry)
for the package metadata, resolves the latest version, and calls `uv add` with
a pinned git URL. Use `--version` to pin a specific version:

```bash
gaia add galileo-falling-bodies-gaia --version 1.0.0
```

## DSL Surface

### Knowledge

| Function | Description |
|----------|-------------|
| `claim(content, *, given, background, parameters, provenance)` | Scientific assertion — the only type carrying probability |
| `setting(content)` | Background context — no probability, no BP participation |
| `question(content)` | Open research inquiry |

### Operators (deterministic constraints)

| Function | Semantics |
|----------|-----------|
| `contradiction(a, b)` | A and B cannot both be true |
| `equivalence(a, b)` | A and B share the same truth value |
| `complement(a, b)` | A and B have opposite truth values |
| `disjunction(*claims)` | At least one must be true |

### Strategies (reasoning declarations)

| Function | Description |
|----------|-------------|
| `noisy_and(premises, conclusion)` | All premises jointly support conclusion |
| `infer(premises, conclusion)` | General conditional probability table |
| `deduction(premises, conclusion)` | Deductive reasoning (conjunction → implication) |
| `abduction(observation, hypothesis)` | Inference to best explanation |
| `analogy(source, target, bridge)` | Analogical transfer |
| `extrapolation(source, target, continuity)` | Continuity-based prediction |
| `elimination(exhaustiveness, excluded, survivor)` | Process of elimination |
| `case_analysis(exhaustiveness, cases, conclusion)` | Case-by-case reasoning |
| `mathematical_induction(base, step, conclusion)` | Inductive proof |
| `induction(observations, law)` | Multiple observations supporting a general law |
| `composite(premises, conclusion, sub_strategies)` | Hierarchical composition |

## Architecture

```
gaia/
├── lang/       DSL runtime, declarations, and compiler
├── ir/         Gaia IR schema, validation, formalization
├── bp/         Belief propagation engine (4 backends)
├── cli/        CLI commands (init, compile, check, add, infer, register)
└── review/     Review sidecar model
```

## Documentation

- [DSL Reference](docs/foundations/gaia-lang/dsl.md)
- [Package Model](docs/foundations/gaia-lang/package.md)
- [Knowledge & Reasoning Semantics](docs/foundations/gaia-lang/knowledge-and-reasoning.md)
- [CLI Workflow](docs/foundations/cli/workflow.md)
- [Gaia IR Specification](docs/foundations/gaia-ir/02-gaia-ir.md)
- [Registry Design](docs/specs/2026-04-02-gaia-registry-design.md)

## Testing

```bash
pytest
ruff check .
ruff format --check .
```

## License

MIT
