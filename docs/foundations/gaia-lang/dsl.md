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
    support, compare, deduction, abduction, induction,     # Strategies
    analogy, extrapolation, elimination, case_analysis,
    mathematical_induction, composite, infer, fills,
    # noisy_and,  # deprecated -- use support()
)
```

The runtime dataclasses `Knowledge`, `Strategy`, `Step`, and `Operator` are also exported for type annotations.

---

## Knowledge Declarations

All knowledge functions return a `Knowledge` dataclass. The three types correspond to the Gaia IR taxonomy in [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md).

### `claim()`

```python
def claim(
    content: str, *,
    title: str | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Knowledge
```

The only knowledge type carrying probability in BP. `background` attaches setting context without making it a logical premise. `parameters` enables universal quantification (e.g., `[{"name": "x", "type": "material"}]`). `provenance` records source attribution as `[{"package_id": ..., "version": ...}]`. Use explicit strategy functions (`support`, `deduction`, etc.) to connect claims.

```python
orbit = claim("The Earth orbits the Sun.")

# Connect claims with explicit strategies
evidence = claim("Stellar parallax is observed.")
heliocentric = claim("The heliocentric model is correct.")
support([evidence], heliocentric, reason="Parallax confirms orbital motion.", prior=0.9)

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
def setting(content: str, *, title: str | None = None, **metadata) -> Knowledge
```

Background context. No probability, no BP participation. Used for experimental conditions, domain assumptions, and variable bindings for universal claims.

```python
context = setting("Experiments conducted at room temperature and 1 atm.")
binding = setting("x = YBCO")
```

### `question()`

```python
def question(content: str, *, title: str | None = None, **metadata) -> Knowledge
```

Open inquiry. No probability, no BP participation. Expresses research directions.

```python
open_problem = question("What is the maximum Tc in hydrogen-rich superconductors?")
```

---

## Operators

Operators declare deterministic logical constraints between claims. Each function creates an `Operator` (auto-registered) and returns a helper claim usable in further reasoning. For formal definitions and truth tables, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 2.

### `contradiction(a, b, *, reason="", prior=None)`

`not(A and B)`. Returns helper claim `not_both_true(A, B)`.

```python
classical = claim("Light is purely a wave.")
photoelectric = claim("Light shows particle behavior.")
conflict = contradiction(classical, photoelectric,
    reason="Incompatible models", prior=0.99)
```

### `equivalence(a, b, *, reason="", prior=None)`

`A = B` (same truth value). Returns helper claim `same_truth(A, B)`.

### `complement(a, b, *, reason="", prior=None)`

`A != B` (XOR). Returns helper claim `opposite_truth(A, B)`.

### `disjunction(*claims, reason="", prior=None)`

At least one true. Returns helper claim `any_true(C0, C1, ...)`.

```python
mech_a = claim("Phonon-mediated pairing.")
mech_b = claim("Spin-fluctuation pairing.")
some = disjunction(mech_a, mech_b,
    reason="At least one mechanism operates", prior=0.95)
```

All operator signatures follow the same pattern -- `Knowledge` inputs, optional `reason` + `prior` (must be paired: both or neither), returns a `Knowledge` helper claim. Prior values must be within Cromwell bounds `[1e-3, 0.999]`.

---

## Strategies

Strategies declare how premises support a conclusion. They carry all uncertainty -- probability parameters live at this layer. All strategy functions set `conclusion.strategy` and auto-register. The `reason` parameter accepts `str | list[str | Step]` for documenting reasoning steps. For IR schemas, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 3.

### Leaf Strategies

#### `support(premises, conclusion, *, background=None, reason="", prior=None)`

**The most common strategy type.** Soft deduction based on the directed `implication` operator (A=1 -> B must =1): premises jointly support conclusion via forward implication. Same structure as `deduction` (conjunction + directed implication) but with an author-specified prior on the implication warrant. Requires at least 1 premise.

`reason` and `prior` must be paired: both or neither.

```python
a = claim("Evidence A.")
b = claim("Evidence B.")
h = claim("Hypothesis.")
support(premises=[a, b], conclusion=h,
    reason="Both lines of evidence converge.", prior=0.85)
```

#### `deduction(premises, conclusion, *, background=None, reason="", prior=None)`

Rigid deduction based on the directed `implication` operator: premises logically entail the conclusion. Same skeleton as `support` (conjunction + directed implication), but semantically a deterministic logical derivation. Requires at least 1 premise. Use when the reasoning involves no uncertainty beyond the premises themselves (math proofs, logical syllogisms). If the reasoning has uncertainty, use `support`.

```python
law = claim("forall {x}. P({x})", parameters=[{"name": "x", "type": "material"}])
in_scope = claim("YBCO is in scope.")
instance = claim("P(YBCO)")
deduction(premises=[law, in_scope], conclusion=instance,
    background=[setting("x = YBCO")],
    reason="Universal instantiation", prior=0.99)
```

#### `compare(pred_h, pred_alt, observation, *, background=None, reason="", prior=None)`

Compare two predictions against an observation. Compiles to 2 equivalence operators (matching each prediction to observation) + 1 implication (if alt matches, does h also match?). Auto-generates a `comparison_claim` as the conclusion.

```python
pred_h = claim("H predicts 3:1 ratio.")
pred_alt = claim("Alt predicts continuous distribution.")
obs = claim("Observed 2.96:1 ratio.")
comp = compare(pred_h, pred_alt, obs,
    reason="H matches observation much better", prior=0.9)
# comp.conclusion is the auto-generated comparison claim
```

#### `infer(premises, conclusion, *, background=None, reason="")`

General CPT reasoning with 2^k parameters. Rarely used directly.

#### `fills(source, target, *, mode=None, strength="exact", background=None, reason="")`

Declares that a source claim fills a target premise interface (cross-package bridging). `strength` is `"exact"` | `"partial"` | `"conditional"`. `mode` is `"deduction"` | `"infer"` | `None` (auto-resolved).

```python
# In a downstream package, fill an interface claim from another package
local_evidence = claim("Our measurement confirms the prediction.")
fills(local_evidence, imported_interface_claim, strength="exact")
```

#### `noisy_and()` (deprecated)

**Deprecated -- use `support()` instead.** Emits `DeprecationWarning`. Compiles to `support` internally.

### Named Strategies

Named strategies express recognized reasoning patterns. At compile time, the IR formalizer expands them into `FormalStrategy` instances with canonical operator skeletons.

#### `abduction(support_h, support_alt, comparison, *, background=None, reason="")`

Inference to the best explanation. Takes three Strategy objects: two `support` strategies (for the hypothesis and alternative) and one `compare` strategy. Auto-generates a `composition_warrant` claim. Conclusion comes from the comparison strategy's conclusion.

```python
H = claim("Discrete heritable factors.")
alt = claim("Blending inheritance.")
obs = claim("F2 ratio is 2.96:1.")
pred_h = claim("H predicts 3:1.")
pred_alt = claim("Blending predicts continuous.")

s_h = support([H], obs, reason="H explains ratio", prior=0.9)
s_alt = support([alt], obs, reason="Blending explains ratio", prior=0.5)
comp = compare(pred_h, pred_alt, obs, reason="H matches better", prior=0.9)
abd = abduction(s_h, s_alt, comp, reason="Both explain same observation")
# abd.conclusion is comp.conclusion (the comparison claim)
```

#### `induction(support_1, support_2, law, *, background=None, reason="")`

Binary composite strategy: two support strategies jointly confirm a law. Chainable: `induction(prev_induction, new_support, law)`. Auto-generates a `composition_warrant` claim.

```python
law = claim("Mendel's law of segregation.")
obs1 = claim("Seed shape 2.96:1.")
obs2 = claim("Seed color 3.01:1.")
obs3 = claim("Flower color 3.15:1.")

s1 = support([law], obs1, reason="law predicts 3:1", prior=0.9)
s2 = support([law], obs2, reason="law predicts 3:1", prior=0.9)
s3 = support([law], obs3, reason="law predicts 3:1", prior=0.9)

ind_12 = induction(s1, s2, law=law, reason="shape and color are independent traits")
ind_123 = induction(ind_12, s3, law=law, reason="flower color independent of seed traits")
```

#### `analogy(source, target, bridge, *, background=None, reason="")`

Analogical reasoning. `bridge` asserts structural similarity. Premises: `[source, bridge]`; conclusion: `target`.

```python
src = claim("BCS theory explains conventional superconductors.")
tgt = claim("Analogous mechanism in heavy-fermion superconductors.")
bridge = claim("Both share Cooper-pair condensate.")
analogy(source=src, target=tgt, bridge=bridge)
```

#### `extrapolation(source, target, continuity, *, background=None, reason="")`

`continuity` asserts conditions remain similar. Premises: `[source, continuity]`; conclusion: `target`.

#### `elimination(exhaustiveness, excluded, survivor, *, background=None, reason="")`

Process of elimination. `excluded` is `list[tuple[Knowledge, Knowledge]]` where each tuple is `(candidate, evidence_against)`. Premises flatten to `[exhaustiveness, cand1, ev1, cand2, ev2, ...]`.

```python
exhaustive = claim("Cause is bacterial, viral, or autoimmune.")
bacterial = claim("Bacterial.")
neg_bac = claim("Antibiotics test negative.")
viral = claim("Viral.")
neg_vir = claim("Viral panel negative.")
survivor = claim("Autoimmune.")
elimination(exhaustiveness=exhaustive,
    excluded=[(bacterial, neg_bac), (viral, neg_vir)], survivor=survivor)
```

#### `case_analysis(exhaustiveness, cases, conclusion, *, background=None, reason="")`

`cases` is `list[tuple[Knowledge, Knowledge]]` where each tuple is `(case_condition, case_implies_conclusion)`. Premises flatten to `[exhaustiveness, case1, impl1, case2, impl2, ...]`.

#### `mathematical_induction(base, step, conclusion, *, background=None, reason="")`

Premises: `[base, step]`.

```python
base = claim("P(0) holds.")
step = claim("P(n) implies P(n+1).")
conclusion = claim("P(n) for all n >= 0.")
mathematical_induction(base=base, step=step, conclusion=conclusion)
```

### Composite Strategy

#### `composite(premises, conclusion, *, sub_strategies, background=None, reason="", type="infer")`

Hierarchical composition of sub-strategies. Requires at least one (`ValueError` otherwise). Sub-strategies can nest recursively. At lowering time, sub-strategies are expanded into the factor graph.

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

## Reference Syntax

Claim content and strategy reasons may contain references using the
unified `@` syntax:

- `[@label]` -- strict reference to a local or imported knowledge node, or
  to a citation key in `references.json`. Missing key is a compile error.
- `@label` -- opportunistic reference (Pandoc narrative form). Missing key
  is treated as literal text.
- `\@label` -- escape, forces literal.

Compile enforces two invariants: (1) a key cannot exist in both the label
table and `references.json` (collision -> compile error), and (2) a single
`[...]` group cannot mix knowledge refs and citations (mixed group ->
compile error).

The full grammar, resolution rules, and rendering pipeline are specified
in [References & `@` Syntax Unification Design](../../specs/2026-04-09-references-and-at-syntax.md).

---

## Complete Example

**`pyproject.toml`:**

```toml
[project]
name = "galileo-tied-balls-gaia"
version = "1.0.0"

[tool.gaia]
namespace = "github"
type = "knowledge-package"
```

**`galileo_tied_balls/__init__.py`:**

```python
"""Galileo's tied-balls thought experiment against Aristotelian physics."""
from gaia.lang import claim, contradiction, deduction, support, setting

aristotelian = setting("In Aristotelian physics, heavier objects fall faster.")

heavy_fast = claim("A heavy ball falls faster than a light ball.")
light_slow = claim("A light ball falls slower than a heavy ball.")

tied_heavier = claim("A heavy+light tied system is heavier than the heavy ball alone.")
tied_faster = claim("The tied system falls faster.")
support([tied_heavier, heavy_fast], tied_faster,
    reason="Heavier system should fall faster.", prior=0.95)
drag_slower = claim("The light ball drags, so tied system falls slower.")
support([light_slow, heavy_fast], drag_slower,
    reason="Light ball acts as drag.", prior=0.95)

paradox = contradiction(tied_faster, drag_slower,
    reason="Opposite predictions from same premises.", prior=0.99)

uniform_rate = claim("All bodies fall at the same rate regardless of weight.")
binding = setting("Consider any two bodies A, B with different weights.")
prediction = claim("A and B hit the ground simultaneously.")
deduction(premises=[uniform_rate, tied_heavier], conclusion=prediction,
    background=[binding],
    reason="Direct logical consequence of uniform fall.", prior=0.99)

__all__ = [
    "aristotelian", "heavy_fast", "light_slow", "tied_heavier",
    "tied_faster", "drag_slower", "paradox", "uniform_rate",
    "binding", "prediction",
]
```

Compile: `gaia compile path/to/galileo-tied-balls-gaia/`

This produces `.gaia/ir.json` containing the `LocalCanonicalGraph` with all nodes, operators, and strategies assigned QIDs under `github:galileo_tied_balls::`.
