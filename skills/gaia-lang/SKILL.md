---
name: gaia-lang
description: "Gaia Lang DSL reference — knowledge declarations, logical operators, reasoning strategies, module organization, and export conventions."
---

# Gaia Lang DSL Reference

Complete reference for authoring Gaia knowledge packages using the Python DSL.

## 1. Imports

```python
from gaia.lang import (
    claim, setting, question,                              # Knowledge
    contradiction, equivalence, complement, disjunction,   # Operators
    noisy_and, infer, deduction, abduction, analogy,       # Strategies
    extrapolation, elimination, case_analysis,
    mathematical_induction, induction, composite,
)
```

## 2. Knowledge Types

### `claim(content, *, title=None, given=None, background=None, parameters=None, provenance=None, **metadata)`

The only type that carries probability in BP.

```python
# Simple claim
tc = claim("Tc of MgB2 is 39K")

# Claim with sugar: given= auto-creates a noisy_and strategy
tc_prediction = claim(
    "BCS theory predicts Tc ~ 39K for MgB2",
    given=[bcs_theory, mgb2_phonon_spectrum],
)

# Claim with background context (settings/questions, not logical premises)
result = claim(
    "The ball reaches the ground in 1.4s",
    background=[experimental_setup, newtonian_gravity],
)

# Parameterized universal claim
universal = claim(
    "Material X is a superconductor below Tc(X)",
    parameters=[{"name": "X", "type": "material"}],
)

# Claim with provenance (cross-package attribution)
imported = claim(
    "Electron-phonon coupling drives conventional SC",
    provenance=[{"package_id": "bcs-theory", "version": "1.0.0"}],
)

# Claim with title
titled = claim("H = p^2/2m + V(x)", title="Hamiltonian of the system")
```

### `setting(content, *, title=None, **metadata)`

Background context. No probability, no BP participation.
Use for: math definitions, experimental conditions, established principles.
Referenced via `background=` on claims or strategies.

```python
setup = setting("A ball is dropped from 10m height in vacuum")
definition = setting("Let G = 6.674e-11 N m^2 kg^-2")
```

### `question(content, *, title=None, **metadata)`

Open inquiry. No probability, no BP participation.

```python
q = question("What is the critical temperature of this material?")
```

## 3. Operators (Deterministic Constraints)

All operators take Knowledge inputs and an optional `reason: str`. Each returns a helper claim that can be used as a premise in strategies.

| Function | Semantics | Helper claim meaning |
|----------|-----------|---------------------|
| `contradiction(a, b)` | not(A and B) | `not_both_true(A, B)` |
| `equivalence(a, b)` | A = B | `same_truth(A, B)` |
| `complement(a, b)` | A XOR B | `opposite_truth(A, B)` |
| `disjunction(*claims)` | at least one true | `any_true(C0, C1, ...)` |

```python
# Two hypotheses cannot both be true
not_both = contradiction(hypothesis_a, hypothesis_b, reason="Mutually exclusive mechanisms")

# Two formulations are logically equivalent
same = equivalence(formulation_1, formulation_2, reason="Algebraic rearrangement")

# Exactly one of two alternatives holds
one_of = complement(conventional_sc, unconventional_sc, reason="Exhaustive classification")

# At least one explanation must be true
at_least_one = disjunction(
    mechanism_a, mechanism_b, mechanism_c,
    reason="These exhaust known possibilities",
)
```

## 4. Strategies

All strategies set `conclusion.strategy` and auto-register. All accept optional `reason: str | list = ""` and `background: list[Knowledge] | None = None`.

### Direct Strategies (map to IR without formalization)

#### `noisy_and(premises, conclusion, *, reason="", background=None)`

All premises jointly support conclusion with conditional probability p. This is what `claim(given=[...])` creates implicitly. Most common strategy type.

Review requires: `conditional_probability` (single float).

```python
conclusion = claim("MgB2 has two superconducting gaps")
noisy_and(
    [band_structure_evidence, tunneling_data, specific_heat_anomaly],
    conclusion,
    reason="Three independent lines of evidence converge",
)
```

#### `infer(premises, conclusion, *, reason="", background=None)`

General CPT with 2^k entries. Rarely used directly.

Review requires: `conditional_probabilities` (list of 2^N floats).

```python
result = claim("System is in phase X")
infer(
    [temperature_condition, pressure_condition],
    result,
    reason="Phase diagram lookup",
)
```

### Named Strategies (auto-formalized at compile time)

#### `deduction(premises, conclusion, *, reason="", background=None)`

Strict logical entailment. Requires >= 1 premise.
If ALL premises are true, conclusion MUST be true (math proof, logical syllogism).

Review requires: NO parameters (deterministic).

Key test: "If premises are all true, is this conclusion NECESSARILY true?"
- Yes -> deduction
- No (approximations, empirical judgment, omitted premises) -> noisy_and

```python
theorem = claim("The series converges")
deduction(
    [bounded_above, monotonically_increasing],
    theorem,
    reason="Monotone convergence theorem",
    background=[real_analysis_definition],
)
```

#### `abduction(observation, hypothesis, alternative=None, *, reason="", background=None)`

Inference to best explanation. If `alternative` is omitted, the compiler auto-generates one.
Returns a Strategy (not Knowledge) -- assign to a variable for review reference.

Review: use `review_generated_claim(strategy, "alternative_explanation", prior=...)` for auto-generated alternatives.

```python
obs = claim("Resistance drops to zero below 39K")
hyp = claim("MgB2 is a superconductor")

# With explicit alternative
alt = claim("Measurement artifact")
s = abduction(obs, hyp, alt, reason="Best explanation for zero resistance")

# Without alternative (compiler generates one)
s = abduction(obs, hyp, reason="Best explanation for zero resistance")
```

#### `analogy(source, target, bridge, *, reason="", background=None)`

`bridge` asserts structural similarity. Premises: [source, bridge] -> target.

```python
source = claim("BCS theory explains superconductivity in Al")
target = claim("BCS theory explains superconductivity in MgB2")
bridge = claim("MgB2 shares phonon-mediated pairing with Al")
analogy(source, target, bridge, reason="Same mechanism, different material")
```

#### `extrapolation(source, target, continuity, *, reason="", background=None)`

`continuity` asserts conditions remain similar. Premises: [source, continuity] -> target.

```python
source = claim("Model predicts Tc=39K at ambient pressure")
target = claim("Model predicts Tc=45K at 10GPa")
continuity = claim("Phonon spectrum varies smoothly with pressure")
extrapolation(source, target, continuity, reason="Smooth pressure dependence")
```

#### `elimination(exhaustiveness, excluded, survivor, *, reason="", background=None)`

Process of elimination. `excluded` is a list of `(candidate, evidence_against)` tuples.

```python
exhaustive = claim("The pairing mechanism is phonon, magnon, or plasmon mediated")
phonon = claim("Phonon-mediated pairing")
magnon = claim("Magnon-mediated pairing")
plasmon = claim("Plasmon-mediated pairing")
no_magnon = claim("Neutron scattering rules out magnon exchange")
no_plasmon = claim("Optical data rules out plasmon exchange")

elimination(
    exhaustive,
    excluded=[(magnon, no_magnon), (plasmon, no_plasmon)],
    survivor=phonon,
    reason="Only phonon mechanism remains",
)
```

#### `case_analysis(exhaustiveness, cases, conclusion, *, reason="", background=None)`

`cases` is a list of `(case_condition, case_implies_conclusion)` tuples.

```python
exhaustive = claim("Temperature is either above or below Tc")
above_tc = claim("T > Tc")
below_tc = claim("T < Tc")
above_implies = claim("If T > Tc then resistance is finite")
below_implies = claim("If T < Tc then resistance is finite for non-SC")
conclusion = claim("Normal metals have finite resistance at all T")

case_analysis(
    exhaustive,
    cases=[(above_tc, above_implies), (below_tc, below_implies)],
    conclusion=conclusion,
    reason="Covers all temperature regimes",
)
```

#### `mathematical_induction(base, step, conclusion, *, reason="", background=None)`

Premises: [base, step] -> conclusion.

```python
base = claim("P(1) holds: sum of first 1 natural number equals 1(1+1)/2")
step = claim("If P(k) holds then P(k+1) holds")
conclusion = claim("For all n >= 1, sum of first n natural numbers equals n(n+1)/2")
mathematical_induction(base, step, conclusion, reason="Standard induction on n")
```

### Composite Strategies

#### `induction(items, law=None, *, alt_exps=None, background=None, reason="")`

Multiple observations -> general law. CompositeStrategy wrapping abductions.
Two modes: **top-down** (observations + law) and **bottom-up** (bundle existing abductions).
`alt_exps` is optional: provide alternative explanations per observation (top-down only).

```python
obs1 = claim("Sample A shows zero resistance below 39K")
obs2 = claim("Sample B shows zero resistance below 39K")
obs3 = claim("Sample C shows zero resistance below 39K")
law = claim("MgB2 universally superconducts below 39K")

# Top-down: observations → law
induction(
    [obs1, obs2, obs3],
    law,
    reason="Consistent across multiple samples",
)

# With per-observation alternatives
alt1 = claim("Sample A contaminated")
alt2 = claim("Sample B contaminated")
induction(
    [obs1, obs2],
    law,
    alt_exps=[alt1, alt2],
    reason="Consistent across samples, contamination unlikely",
)

# Bottom-up: bundle existing abductions
abd1 = abduction(obs1, law, alt1)
abd2 = abduction(obs2, law, alt2)
induction([abd1, abd2])
```

#### `composite(premises, conclusion, *, sub_strategies, reason="", background=None, type="infer")`

Hierarchical composition. Only leaf sub-strategies need review parameters.

```python
intermediate = claim("Intermediate result")
final = claim("Final conclusion")

s1 = deduction([axiom_a, axiom_b], intermediate, reason="From axioms")
s2 = noisy_and([intermediate, empirical_data], final, reason="Combined evidence")

composite(
    [axiom_a, axiom_b, empirical_data],
    final,
    sub_strategies=[s1, s2],
    reason="Two-stage argument",
)
```

## 5. Module Organization

- One module per chapter/section of source material
- Introduction -> `motivation.py`, Section II -> `s2_xxx.py`, etc.
- Module docstring becomes section title
- Each knowledge node goes in the module where it first appears
- Later modules import from earlier ones: `from .motivation import some_claim`
- `__init__.py` re-exports everything

```
src/my_package/
    __init__.py          # re-exports all public symbols
    motivation.py        # "Introduction and Motivation"
    s2_background.py     # "Section 2: Background"
    s3_results.py        # "Section 3: Results"
    s4_discussion.py     # "Section 4: Discussion"
```

Example `__init__.py`:

```python
from .motivation import *
from .s2_background import *
from .s3_results import *
from .s4_discussion import *
```

## 6. Exports and Labels

`__all__` controls visibility:
- Listed in `__all__` -> **exported** (cross-package interface, other packages can import)
- No `_` prefix -> **public** (visible to review)
- `_` prefix -> **private** (package-internal helper)

```python
__all__ = ["main_theorem", "key_observation"]  # exported

main_theorem = claim("...")           # exported (in __all__)
supporting_lemma = claim("...")       # public (no underscore, not in __all__)
_helper = claim("...")                # private (underscore prefix)
```

Labels are auto-assigned from Python variable names by `gaia compile`. NEVER set `.label` manually.

```python
# CORRECT: label "tc_prediction" assigned automatically
tc_prediction = claim("Tc of MgB2 is 39K")

# WRONG: never do this
tc_prediction.label = "tc_prediction"  # anti-pattern
```

## 7. Anti-patterns (HARD GATE -- these produce invalid packages)

| Anti-pattern | Why it fails | Correct approach |
|-------------|-------------|-----------------|
| `Package(...)` context manager | Removed in v5 | Use module structure + `pyproject.toml` |
| Manually setting `.label = "name"` | Labels auto-assigned from variable names | Just assign to a variable |
| `setting` or `question` as strategy premises | Settings/questions have no probability | Use `background=` parameter instead |
| Building `FormalExpr` by hand | Compiler handles formalization | Use named strategies (deduction, abduction, etc.) |
| `from gaia.gaia_ir import ...` | Module renamed | Use `from gaia.ir import ...` |
| `dependencies = ["gaia-lang"]` in pyproject.toml | CLI provided externally, not a package dep | Omit gaia-lang from dependencies |
| Omitting `[build-system]` in pyproject.toml | Required for `uv sync` in CI | Always include build-system section |
