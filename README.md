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

# Reasoning
vacuum_law = claim("In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster])
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
gaia compile   →   gaia check   →   gaia infer   →   gaia register
  (DSL → IR)      (validate)      (BP preview)      (registry PR)
```

| Command | Purpose |
|---------|---------|
| `gaia compile [path]` | Compile Python DSL to Gaia IR (`.gaia/ir.json`) |
| `gaia check [path]` | Validate package structure and IR consistency |
| `gaia infer [path]` | Run belief propagation with a review sidecar |
| `gaia register [path]` | Submit package to the [Gaia Official Registry](https://github.com/SiliconEinstein/gaia-registry) |

## Create a Knowledge Package

**1. Initialize**

```bash
uv init --lib galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
uv add gaia-lang
mv src/galileo_falling_bodies_gaia src/galileo_falling_bodies
```

**2. Configure `pyproject.toml`**

```toml
[project]
name = "galileo-falling-bodies-gaia"
version = "1.0.0"

[tool.gaia]
type = "knowledge-package"
uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

- Package name must end with `-gaia`
- `type` must be `"knowledge-package"`
- `uuid` is required for registry submission

**3. Write DSL declarations** in `src/galileo_falling_bodies/__init__.py`

```python
from gaia.lang import claim, setting, contradiction

aristotle = setting("Aristotle: heavier objects fall faster.")
heavy_faster = claim("Heavy stones fall faster in air.")
composite_slower = claim("Tied composite should be slower.")
composite_faster = claim("Tied composite should be faster.")

paradox = contradiction(composite_slower, composite_faster,
    reason="Same premise yields opposite conclusions")

vacuum_law = claim("In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster])

__all__ = ["aristotle", "heavy_faster", "composite_slower",
           "composite_faster", "paradox", "vacuum_law"]
```

**4. Compile and validate**

```bash
gaia compile .
gaia check .
```

**5. Publish**

```bash
git tag v1.0.0 && git push origin main --tags
gaia register . --registry-dir ../gaia-registry --create-pr
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
├── cli/        CLI commands (compile, check, infer, register)
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
