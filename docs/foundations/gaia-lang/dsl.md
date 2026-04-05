---
status: current-canonical
layer: gaia-lang
since: v5-phase-1
---

# Gaia Lang DSL Reference

## Overview

Gaia Lang is a Python 3.12+ internal DSL for declarative knowledge authoring. Package authors use it to declare propositions, logical constraints, and reasoning strategies. Every declaration auto-registers to a `CollectedPackage` via Python `contextvars` -- writing declarations at module scope is sufficient.

```python
from gaia.lang import (
    claim, setting, question,                              # Knowledge
    contradiction, equivalence, complement, disjunction,   # Operators
    noisy_and, infer, deduction, abduction, analogy,       # Strategies
    extrapolation, elimination, case_analysis,
    mathematical_induction, composite,
)
```

The runtime dataclasses `Knowledge`, `Strategy`, and `Operator` are also exported for type annotations.

---

## Knowledge Declarations

All knowledge functions return a `Knowledge` dataclass. The three types correspond to the Gaia IR taxonomy in [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md).

### `claim()`

```python
def claim(
    content: str, *,
    given: list[Knowledge] | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Knowledge
```

The only knowledge type carrying probability in BP. When `given` is provided, a `noisy_and` strategy is auto-created linking those premises to this claim. `background` attaches setting context without making it a logical premise. `parameters` enables universal quantification (e.g., `[{"name": "x", "type": "material"}]`). `provenance` records source attribution as `[{"package_id": ..., "version": ...}]`.

```python
orbit = claim("The Earth orbits the Sun.")

# given= auto-creates noisy_and strategy
evidence = claim("Stellar parallax is observed.")
heliocentric = claim("The heliocentric model is correct.", given=[evidence])
# heliocentric.strategy.type == "noisy_and"

# Universal claim
bcs = claim(
    "forall {x}. superconductor({x}) -> zero_resistance({x})",
    parameters=[{"name": "x", "type": "material"}],
)

# With provenance and background
ctx = setting("High-pressure experiments at 200 GPa.")
measurement = claim(
    "LaH10 exhibits superconductivity at 250 K.",
    background=[ctx],
    provenance=[{"package_id": "paper:drozdov2019", "version": "1.0.0"}],
)
```

### `setting()`

```python
def setting(content: str, **metadata) -> Knowledge
```

Background context. No probability, no BP participation. Used for experimental conditions, domain assumptions, and variable bindings for universal claims.

```python
context = setting("Experiments conducted at room temperature and 1 atm.")
binding = setting("x = YBCO")
```

### `question()`

```python
def question(content: str, **metadata) -> Knowledge
```

Open inquiry. No probability, no BP participation. Expresses research directions.

```python
open_problem = question("What is the maximum Tc in hydrogen-rich superconductors?")
```

---

## Operators

Operators declare deterministic logical constraints between claims. Each function creates an `Operator` (auto-registered) and returns a helper claim usable in further reasoning. For formal definitions and truth tables, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 2.

### `contradiction(a, b, *, reason="")`

`not(A and B)`. Returns helper claim `not_both_true(A, B)`.

```python
classical = claim("Light is purely a wave.")
photoelectric = claim("Light shows particle behavior.")
conflict = contradiction(classical, photoelectric, reason="Incompatible models")
```

### `equivalence(a, b, *, reason="")`

`A = B` (same truth value). Returns helper claim `same_truth(A, B)`.

### `complement(a, b, *, reason="")`

`A != B` (XOR). Returns helper claim `opposite_truth(A, B)`.

### `disjunction(*claims, reason="")`

At least one true. Returns helper claim `any_true(C0, C1, ...)`.

```python
mech_a = claim("Phonon-mediated pairing.")
mech_b = claim("Spin-fluctuation pairing.")
some = disjunction(mech_a, mech_b, reason="At least one mechanism operates")
```

All operator signatures follow the same pattern -- `Knowledge` inputs, optional `reason: str`, returns a `Knowledge` helper claim.

---

## Strategies

Strategies declare how premises support a conclusion. They carry all uncertainty -- probability parameters live at this layer. All strategy functions set `conclusion.strategy` and auto-register. The `steps` parameter accepts `list[str | dict[str, Any]]` for documenting reasoning. For IR schemas, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 3.

### Direct Strategies

Map directly to IR without compile-time formalization.

#### `noisy_and(premises, conclusion, *, steps=None, reason="")`

All premises jointly necessary, supporting conclusion with conditional probability p. This is what `claim(..., given=[...])` creates implicitly. The most common strategy type.

```python
a = claim("Evidence A.")
b = claim("Evidence B.")
h = claim("Hypothesis.")
noisy_and(premises=[a, b], conclusion=h, steps=["Both lines converge."])
```

#### `infer(premises, conclusion, *, steps=None, reason="")`

General CPT reasoning with 2^k parameters. Rarely used directly.

### Named Strategies

Named strategies express recognized reasoning patterns. At compile time, the IR formalizer expands them into `FormalStrategy` instances with canonical operator skeletons (see [../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)).

#### `deduction(premises, conclusion, *, background=None, steps=None, reason="")`

Premises logically entail the conclusion. Requires at least 2 premises (`ValueError` otherwise). Typical use: instantiating a universal claim.

```python
law = claim("forall {x}. P({x})", parameters=[{"name": "x", "type": "material"}])
in_scope = claim("YBCO is in scope.")
instance = claim("P(YBCO)")
deduction(premises=[law, in_scope], conclusion=instance, background=[setting("x = YBCO")])
```

#### `abduction(observation, hypothesis, alternative=None, *, steps=None, reason="")`

Inference to the best explanation. The formalizer generates a disjunction between hypothesis and alternative (auto-generated if omitted).

```python
obs = claim("High-Tc superconductivity observed in cuprates.")
hyp = claim("Spin-fluctuation mediates pairing.")
alt = claim("Phonon-mediated pairing explains Tc.")
abduction(observation=obs, hypothesis=hyp, alternative=alt)
```

#### `analogy(source, target, bridge, *, steps=None, reason="")`

Analogical reasoning. `bridge` asserts structural similarity. Premises: `[source, bridge]`; conclusion: `target`.

```python
src = claim("BCS theory explains conventional superconductors.")
tgt = claim("Analogous mechanism in heavy-fermion superconductors.")
bridge = claim("Both share Cooper-pair condensate.")
analogy(source=src, target=tgt, bridge=bridge)
```

#### `extrapolation(source, target, continuity, *, steps=None, reason="")`

`continuity` asserts conditions remain similar. Premises: `[source, continuity]`; conclusion: `target`.

#### `elimination(exhaustiveness, excluded, survivor, *, steps=None, reason="")`

Process of elimination. `excluded` is `list[tuple[Knowledge, Knowledge]]` where each tuple is `(candidate, evidence_against)`. Premises flatten to `[exhaustiveness, cand1, ev1, cand2, ev2, ...]`.

```python
exhaustive = claim("Cause is bacterial, viral, or autoimmune.")
bacterial = claim("Bacterial.")
neg_bac = claim("Antibiotics test negative.")
viral = claim("Viral.")
neg_vir = claim("Viral panel negative.")
survivor = claim("Autoimmune.")
elimination(exhaustiveness=exhaustive, excluded=[(bacterial, neg_bac), (viral, neg_vir)], survivor=survivor)
```

#### `case_analysis(exhaustiveness, cases, conclusion, *, steps=None, reason="")`

`cases` is `list[tuple[Knowledge, Knowledge]]` where each tuple is `(case_condition, case_implies_conclusion)`. Premises flatten to `[exhaustiveness, case1, impl1, case2, impl2, ...]`.

#### `mathematical_induction(base, step, conclusion, *, steps=None, reason="")`

Premises: `[base, step]`.

```python
base = claim("P(0) holds.")
step = claim("P(n) implies P(n+1).")
conclusion = claim("P(n) for all n >= 0.")
mathematical_induction(base=base, step=step, conclusion=conclusion)
```

### Composite Strategy

#### `composite(premises, conclusion, *, sub_strategies, background=None, steps=None, reason="", type="infer")`

Hierarchical composition of sub-strategies. Requires at least one (`ValueError` otherwise). Sub-strategies can nest recursively. At lowering time, sub-strategies are expanded into the factor graph. No `review_strategy()` call is needed for the composite itself — only leaf sub-strategies require parameters. Use `fold_composite_to_cpt()` to compute the composite's aggregate CPT for analysis.

```python
obs = claim("Observation.")
hyp = claim("Hypothesis.")
final = claim("Final conclusion.")
s1 = abduction(observation=obs, hypothesis=hyp)
s2 = noisy_and(premises=[hyp], conclusion=final)
composite(premises=[obs], conclusion=final, sub_strategies=[s1, s2])
# In the review sidecar, only s2 (noisy_and) needs a conditional_probability.
# s1 (abduction) is formalized to deterministic operators.
# The composite itself needs no parameters.
```

---

## Labels and Cross-Referencing

**Automatic inference.** When compiled via `gaia compile`, module-level variable names in `__all__` become labels:

```python
bg = setting("Context.")           # label = "bg"
hypothesis = claim("Hypothesis.")  # label = "hypothesis"
__all__ = ["bg", "hypothesis"]
```

**Manual labels.** Assign directly: `my_claim.label = "explicit_label"`.

**QID generation.** At compile time, labels expand to `{namespace}:{package_name}::{label}`. A claim labeled `hypothesis` in package `galileo` under namespace `github` becomes `github:galileo::hypothesis`. Namespace and package name come from `pyproject.toml`.

---

## Complete Example

**`pyproject.toml`:**

```toml
[project]
name = "galileo-tied-balls-gaia"
version = "1.0.0"

[tool.gaia]
namespace "github"
type = "knowledge-package"
```

**`galileo_tied_balls/__init__.py`:**

```python
"""Galileo's tied-balls thought experiment against Aristotelian physics."""
from gaia.lang import claim, contradiction, deduction, setting

aristotelian = setting("In Aristotelian physics, heavier objects fall faster.")

heavy_fast = claim("A heavy ball falls faster than a light ball.")
light_slow = claim("A light ball falls slower than a heavy ball.")

tied_heavier = claim("A heavy+light tied system is heavier than the heavy ball alone.")
tied_faster = claim("The tied system falls faster.", given=[tied_heavier, heavy_fast])
drag_slower = claim("The light ball drags, so tied system falls slower.", given=[light_slow, heavy_fast])

paradox = contradiction(tied_faster, drag_slower, reason="Opposite predictions from same premises.")

uniform_rate = claim("All bodies fall at the same rate regardless of weight.")
binding = setting("Consider any two bodies A, B with different weights.")
prediction = claim("A and B hit the ground simultaneously.")
deduction(premises=[uniform_rate, tied_heavier], conclusion=prediction, background=[binding])

__all__ = [
    "aristotelian", "heavy_fast", "light_slow", "tied_heavier",
    "tied_faster", "drag_slower", "paradox", "uniform_rate",
    "binding", "prediction",
]
```

Compile: `gaia compile path/to/galileo-tied-balls-gaia/`

This produces `.gaia/ir.json` containing the `LocalCanonicalGraph` with all nodes, operators, and strategies assigned QIDs under `github:galileo_tied_balls::`.
