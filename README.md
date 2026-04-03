# Gaia Lang

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/SiliconEinstein/Gaia/graph/badge.svg)](https://codecov.io/gh/SiliconEinstein/Gaia)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python DSL for authoring machine-readable scientific knowledge. Gaia Lang lets researchers declare propositions, logical constraints, and reasoning strategies as Python objects, then compiles them into a canonical intermediate representation (Gaia IR) for inference via belief propagation.

## Quick Example

```python
from gaia.lang import claim, setting, contradiction, deduction

# Declare knowledge
aristotle = setting("Aristotle's doctrine: heavier objects fall faster.")
heavy_faster = claim("Observations show heavier stones fall faster in air.")
composite_slower = claim("A tied composite should fall slower (light part drags heavy).")
composite_faster = claim("A tied composite should fall faster (greater total mass).")

# Logical constraint
paradox = contradiction(composite_slower, composite_faster,
    reason="Same premise yields opposite predictions")

# Reasoning strategy
vacuum_law = claim("In vacuum all bodies fall at the same rate.")
galileo_argument = deduction(
    premises=[paradox, heavy_faster],
    conclusion=vacuum_law,
    reason="Contradiction in Aristotle's doctrine forces a new law",
)
```

## Install

```bash
pip install gaia-lang
```

For development:

```bash
git clone https://github.com/SiliconEinstein/Gaia.git
cd Gaia && uv sync
```

## CLI Workflow

```
gaia init → gaia compile → gaia check → gaia add → gaia infer → gaia register
(scaffold)   (DSL → IR)    (validate)  (add deps)  (BP preview)  (registry PR)
```

| Command | Purpose |
|---------|---------|
| `gaia init <name>` | Scaffold a new Gaia knowledge package |
| `gaia compile [path]` | Compile Python DSL to Gaia IR (`.gaia/ir.json`) |
| `gaia check [path]` | Validate package structure and IR consistency |
| `gaia add <package>` | Install a registered Gaia package from the [official registry](https://github.com/SiliconEinstein/gaia-registry) |
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
from gaia.lang import claim, setting

aristotle = setting("Aristotle: heavier objects fall faster.")
heavy_faster = claim("Heavy stones fall faster in air.")
composite_slower = claim("Tied composite should be slower (light drags heavy).")
composite_faster = claim("Tied composite should be faster (greater total mass).")
vacuum_law = claim("In vacuum all bodies fall at the same rate.")
```

`src/galileo_falling_bodies/reasoning.py` — declare constraints and strategies:

```python
from gaia.lang import contradiction, deduction
from .knowledge import composite_slower, composite_faster, heavy_faster, vacuum_law

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
from .. import heavy_faster, composite_slower, composite_faster, vacuum_law, galileo_argument

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        review_claim(heavy_faster, prior=0.8,
            judgment="supporting",
            justification="Well-documented observation in air."),
        review_claim(composite_slower, prior=0.6,
            judgment="tentative",
            justification="Plausible under Aristotelian framework."),
        review_claim(composite_faster, prior=0.6,
            judgment="tentative",
            justification="Also plausible under Aristotelian framework."),
        review_claim(vacuum_law, prior=0.3,
            judgment="tentative",
            justification="Not yet established — the argument should raise this."),
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
Inferred 4 beliefs from 4 priors and 0 strategy parameter records
BP converged: True after 12 iterations
Review: self_review
Output: .gaia/reviews/self_review/beliefs.json
```

`beliefs.json` contains the posterior probability for each claim after propagation — for example, `vacuum_law` should rise above its 0.3 prior because the deductive argument from the contradiction supports it.

If multiple reviews exist, specify which one: `gaia infer --review self_review .`

**6. Publish**

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
