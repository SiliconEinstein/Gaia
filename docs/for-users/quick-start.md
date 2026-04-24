# Quick Start

> **Status:** Current canonical

Create, build, and publish your first Gaia knowledge package in 10 minutes.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

Verify both are available:

```bash
python3 --version   # 3.12+
uv --version
```

## Install Gaia

```bash
pip install gaia-lang
```

Verify:

```bash
gaia --help
```

## Create a Package

```bash
gaia init my-first-gaia
```

The name **must** end with `-gaia`. This creates:

```
my-first-gaia/
  pyproject.toml              # [tool.gaia] metadata
  src/my_first/
    __init__.py               # DSL declarations
  .gitignore
```

## Edit Your Package

Open `src/my_first/__init__.py` and replace the template:

```python
"""Galileo's tied-body contradiction for Aristotle's falling-body model."""

from gaia.lang import claim, contradict, derive, note

# Model under test
aristotle_law = claim(
    "Aristotle's weight-speed model says heavier objects naturally fall faster."
)

# Thought experiment setup
thought_experiment = note(
    "Consider a heavy ball (H) and a light ball (L). "
    "Now tie them together into a composite body (H+L)."
)

# Two contradictory predictions from Aristotle's law
composite_slower = derive(
    "Under Aristotle's law, H+L falls slower than H alone, "
    "because L acts as a drag on H.",
    given=aristotle_law,
    background=[thought_experiment],
    rationale="The light body should retard the heavy body when tied together.",
)

composite_faster = derive(
    "Under Aristotle's law, H+L falls faster than H alone, "
    "because H+L is heavier than H.",
    given=aristotle_law,
    background=[thought_experiment],
    rationale="The composite body is heavier than H alone.",
)

# These two predictions contradict each other
tied_balls = contradict(
    composite_slower, composite_faster,
    rationale="The same setup cannot make H+L both slower and faster than H alone.",
)

__all__ = ["tied_balls"]
```

Key points:

- `note()` declares background context (no probability, not debatable)
- `claim()` declares propositions that carry probability in inference
- `derive()` connects explicit premises to deterministic conclusions
- `contradict()` declares a reviewable relation between two claims
- `__all__` lists exported conclusions (the package's external interface)

## Compile

```bash
cd my-first-gaia
gaia compile .
```

This produces `.gaia/ir.json` (the compiled knowledge graph) and `.gaia/ir_hash` (integrity hash).

## Validate

```bash
gaia check .
```

Check reports structural errors, independent premises, derived conclusions, and prior coverage. Fix any errors before proceeding.

Use `gaia check --brief .` for a per-module overview, or `gaia check --hole .` for a detailed prior coverage report.

## Assign Priors

Independent probabilistic inputs need external priors. Derived claims and relation helper claims do not. Create `src/my_first/priors.py`:

```python
"""Priors for independent premises."""

from . import aristotle_law

PRIORS: dict = {
    aristotle_law: (0.5, "Neutral before inspecting the tied-body contradiction."),
}
```

Each entry maps an independent claim to `(prior_probability, justification)`. Priors follow Cromwell bounds, so use values between 0.001 and 0.999 rather than exact 0 or 1.

Re-compile to pick up the priors:

```bash
gaia compile .
gaia check --hole .    # Shows covered inputs and any MaxEnt independent DOF
```

## Infer

Run belief propagation to compute posterior beliefs:

```bash
gaia infer .
```

Sample output:

```
Algorithm: junction_tree (exact, treewidth=2)
Converged after 2 iterations

Beliefs:
  aristotle_law:  prior=0.50  ->  belief decreases after the contradiction
  tied_balls:     no prior    ->  relation helper is constrained by contradict()
```

The contradiction is not a prior by itself. It is a reviewable relation that constrains the graph; BP then computes how the model belief moves. See the README for the fuller Galileo example that adds the medium-resistance model and the vacuum prediction.

## Render

Generate documentation from the compiled package:

```bash
gaia render . --target docs
```

This produces `docs/detailed-reasoning.md` with per-module Mermaid reasoning graphs.

## Next Steps

- [Language Reference](language-reference.md) — full cheat sheet for all knowledge types, operators, and strategies
- [CLI Commands](cli-commands.md) — complete reference for all `gaia` commands
- [Hole And Bridge Tutorial](hole-bridge-tutorial.md) — cross-package dependency resolution with `fills()`
