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
    claim, note, question,                                 # Knowledge
    not_, and_, or_,                                      # Propositional expressions
    contradict, equal, exclusive,                         # Reviewable relations
    observe, derive, compute, infer,                       # Recommended actions

    # Compatibility aliases and legacy/experimental APIs
    setting, context,
    contradiction, equivalence, complement, disjunction,   # v5 compatibility
    support, compare, deduction, abduction, induction,     # Legacy strategies
    analogy, extrapolation, elimination, case_analysis,
    mathematical_induction, composite, fills,
    # noisy_and,  # deprecated legacy compatibility
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

The only knowledge type carrying probability in BP. `background` attaches notes without making them logical premises. `parameters` enables universal quantification (e.g., `[{"name": "x", "type": "material"}]`). `provenance` records source attribution as `[{"package_id": ..., "version": ...}]`. Use action verbs (`observe`, `derive`, `compute`, `infer`) and relation verbs (`equal`, `contradict`, `exclusive`) to connect claims in new v0.5 packages.

```python
orbit = claim("The Earth orbits the Sun.")

# Connect claims with the recommended action surface
evidence = claim("Stellar parallax is observed.")
heliocentric = claim("The heliocentric model is correct.")
derive(heliocentric, given=evidence, rationale="Parallax confirms orbital motion.")

# Universal claim
bcs = claim(
    "forall {x}. superconductor({x}) -> zero_resistance({x})",
    parameters=[{"name": "x", "type": "material"}],
)

# With provenance and background
ctx = note("High-pressure experiments at 200 GPa.")
measurement = claim(
    "LaH10 exhibits superconductivity at 250 K.",
    background=[ctx],
    provenance=[{"package_id": "paper:drozdov2019", "version": "1.0.0"}],
)
```

### `note()`

```python
def note(
    content: str, *,
    title: str | None = None,
    format: str = "markdown",
    **metadata,
) -> Knowledge
```

Background context. No probability, no BP participation. Used for experimental conditions, domain assumptions, and variable bindings for universal claims.

```python
context = note("Experiments conducted at room temperature and 1 atm.")
binding = note("x = YBCO")
```

`setting(...)` and `context(...)` are deprecated compatibility aliases for `note(...)`.

### `question()`

```python
def question(content: str, *, title: str | None = None, **metadata) -> Knowledge
```

Open inquiry. No probability, no BP participation. Expresses research directions.

```python
open_problem = question("What is the maximum Tc in hydrogen-rich superconductors?")
```

---

## Recommended Action Verbs

Action verbs are the canonical v0.5 way to turn explicit premises into reviewable warrants.

### `observe(conclusion, *, given=(), background=None, rationale="", label=None)`

Empirical observation. With no `given`, it records grounding on the conclusion and still creates a reviewable observation warrant. A root observation is also an independent probabilistic input for `gaia check --hole`.

### `derive(conclusion, *, given=(), background=None, rationale="", label=None)`

Deterministic derivation. Use when the conclusion follows from the explicit `given` claims once the rationale is accepted.

### `compute(ClaimType, *, fn=None, given=(), background=None, rationale="", label=None)`

Deterministic computation. Use either `compute(ResultClaim, fn=..., given=...)` or `@compute` with a `Claim` return annotation.

### `infer(evidence, *, hypothesis, p_e_given_h, p_e_given_not_h, background=None, rationale="", label=None)`

Probabilistic prediction/evidence link. Use after extracting the uncertain parts into explicit claims; `infer(...)` should not be a hiding place for missing premises.

---

## Operators

Operators declare deterministic logical constraints between claims. Each function creates an `Operator` (auto-registered) and returns a helper claim usable in further reasoning. For formal definitions and truth tables, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 2.

### Propositional Expression Helpers

Use `~a`, `a & b`, and `a | b` for direct Boolean construction. These return structural helper claims and do not create review warrants.

```python
not_a = ~a          # same as not_(a)
both = a & b        # same as and_(a, b)
either = a | b      # same as or_(a, b)
```

The explicit functions `not_(a)`, `and_(a, b, ...)`, and `or_(a, b, ...)` are also exported. Python keywords `not`, `and`, and `or` cannot be overloaded; `Claim.__bool__` raises to prevent accidental Python control-flow truth tests.

### Propositional Analysis Helpers

`gaia.logic` provides non-persistent analysis helpers over compiled Gaia operator graphs:

- `simplify_proposition(graph, knowledge_id)`
- `to_cnf_proposition(graph, knowledge_id, simplify=False)`
- `to_dnf_proposition(graph, knowledge_id, simplify=False)`
- `to_nnf_proposition(graph, knowledge_id)`
- `are_equivalent(graph, left_knowledge_id, right_knowledge_id)`
- `is_satisfiable(graph, knowledge_id)`

These helpers recursively expand deterministic IR operators into a Boolean backend representation for formula simplification, normal-form conversion, equivalence checks, and satisfiability checks. The backend expression is an analysis artifact only; Gaia IR remains the source of truth.

### Reviewable Relation Verbs

Use v6 relation verbs when the author is making a semantic judgment that reviewers should inspect:

- `equal(a, b, *, rationale="", label=None)` declares equivalent truth.
- `contradict(a, b, *, rationale="", label=None)` declares the claims cannot both be true.
- `exclusive(a, b, *, rationale="", label=None)` declares a closed binary partition, exactly one true.

Each relation returns a reviewable warrant helper claim and compiles to the corresponding deterministic IR operator.

### v5 Compatibility Operators

These functions remain for older packages. New v0.5 packages should prefer structural expressions (`~`, `&`, `|`) for direct Boolean construction and relation verbs (`equal`, `contradict`, `exclusive`) for reviewable semantic judgments.

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

The compatibility operator signatures follow the same pattern -- `Knowledge` inputs, optional `reason` + `prior` (must be paired: both or neither), returns a `Knowledge` helper claim. In new packages, do not assign external priors to structural or relation helper claims; their truth is determined by the declared operator and review status.

---

## Legacy / Experimental Strategy APIs

These APIs remain available for older packages and for experiments with named reasoning patterns. New v0.5 packages should normally use the action verbs (`observe`, `derive`, `compute`, `infer`) and relation verbs (`equal`, `contradict`, `exclusive`) above. If uncertainty appears in a reasoning step, first extract it into explicit claims; do not hide it inside prose rationale or a broad legacy strategy.

### Leaf Strategies

#### `support(premises, conclusion, *, background=None, reason="", prior=None)`

Legacy soft deduction based on the directed `implication` operator (A=1 -> B must =1): premises jointly support conclusion via forward implication. Same structure as `deduction` (conjunction + directed implication) but with an author-specified prior on the implication warrant. Requires at least 1 premise. Prefer `derive(...)` for deterministic steps and `infer(...)` for explicit probabilistic prediction/evidence links.

`reason` and `prior` must be paired: both or neither.

```python
a = claim("Evidence A.")
b = claim("Evidence B.")
h = claim("Hypothesis.")
support(premises=[a, b], conclusion=h,
    reason="Both lines of evidence converge.", prior=0.85)
```

#### `deduction(premises, conclusion, *, background=None, reason="", prior=None)`

Legacy rigid deduction based on the directed `implication` operator: premises logically entail the conclusion. Same skeleton as `support` (conjunction + directed implication), but semantically a deterministic logical derivation. Requires at least 1 premise. In new packages, prefer `derive(...)`.

`prior` is accepted for legacy compatibility, but current BP lowering ignores it for deduction. Accepted review makes the deduction warrant part of the information set `I`; it does not assign a numeric confidence to the deduction step.

```python
law = claim("forall {x}. P({x})", parameters=[{"name": "x", "type": "material"}])
in_scope = claim("YBCO is in scope.")
instance = claim("P(YBCO)")
deduction(premises=[law, in_scope], conclusion=instance,
    background=[setting("x = YBCO")],
    reason="Universal instantiation")
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

#### Legacy `infer(premises, conclusion, *, background=None, reason="")`

Deprecated v5 CPT form. Use `infer(evidence, hypothesis=..., p_e_given_h=..., p_e_given_not_h=...)` instead.

#### `fills(source, target, *, mode=None, strength="exact", background=None, reason="")`

Declares that a source claim fills a target premise interface (cross-package bridging). `strength` is `"exact"` | `"partial"` | `"conditional"`. `mode` is `"deduction"` | `"infer"` | `None` (auto-resolved).

```python
# In a downstream package, fill an interface claim from another package
local_evidence = claim("Our measurement confirms the prediction.")
fills(local_evidence, imported_interface_claim, strength="exact")
```

#### `noisy_and()` (deprecated)

Emits `DeprecationWarning`. Compiles to legacy `support` internally.

### Named Strategies

Named strategies express recognized reasoning patterns. They are legacy/experimental in v0.5. At compile time, the IR formalizer expands them into `FormalStrategy` instances with canonical operator skeletons. Use them when you are deliberately testing that pattern; do not use them as the default authoring surface for new packages.

#### `abduction(support_h, support_alt, comparison, *, background=None, reason="")`

Experimental inference-to-best-explanation pattern. Takes three Strategy objects: two `support` strategies (for the hypothesis and alternative) and one `compare` strategy. Auto-generates a `composition_warrant` claim. Conclusion comes from the comparison strategy's conclusion.

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

Experimental binary composite strategy: two support strategies jointly confirm a law. Chainable: `induction(prev_induction, new_support, law)`. Auto-generates a `composition_warrant` claim.

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

Legacy hierarchical composition of sub-strategies. Requires at least one (`ValueError` otherwise). Sub-strategies can nest recursively. At lowering time, sub-strategies are expanded into the factor graph.

---

## Labels and Cross-Referencing

**Automatic inference.** When compiled via `gaia compile`, module-level variable names in `__all__` become labels:

```python
bg = note("Context.")              # label = "bg"
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

## Legacy Complete Example

This older example is retained to document compatibility behavior. New v0.5 examples should follow the README style: `claim`/`note` plus `observe`/`derive`/`compute`/`infer` and reviewable relation verbs.

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
