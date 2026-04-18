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
    support, compare, deduction, abduction, induction,     # Strategies
    analogy, extrapolation, elimination, case_analysis,
    mathematical_induction, composite, infer, fills,
    # noisy_and,  # deprecated -- use support()
)
```

## 2. Knowledge Types

### `claim(content, *, title=None, background=None, parameters=None, provenance=None, **metadata)`

The only type that carries probability in BP. Use explicit strategies (`support`, `deduction`, etc.) to connect claims via reasoning.

```python
# Simple claim
tc = claim("Tc of MgB2 is 39K")

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

All operators take Knowledge inputs and optional `reason: str` + `prior: float`. `reason` and `prior` must be paired: both or neither. Each returns a helper claim that can be used as a premise in strategies. Prior values must be within Cromwell bounds `[1e-3, 0.999]`.

| Function | Semantics | Helper claim meaning |
|----------|-----------|---------------------|
| `contradiction(a, b)` | not(A and B) | `not_both_true(A, B)` |
| `equivalence(a, b)` | A = B | `same_truth(A, B)` |
| `complement(a, b)` | A XOR B | `opposite_truth(A, B)` |
| `disjunction(*claims)` | at least one true | `any_true(C0, C1, ...)` |

```python
# Two hypotheses cannot both be true
not_both = contradiction(hypothesis_a, hypothesis_b,
    reason="Mutually exclusive mechanisms", prior=0.99)

# Two formulations are logically equivalent
same = equivalence(formulation_1, formulation_2,
    reason="Algebraic rearrangement", prior=0.95)

# Exactly one of two alternatives holds
one_of = complement(conventional_sc, unconventional_sc,
    reason="Exhaustive classification", prior=0.95)

# At least one explanation must be true
at_least_one = disjunction(
    mechanism_a, mechanism_b, mechanism_c,
    reason="These exhaust known possibilities", prior=0.9,
)
```

## 4. Strategies

All strategies auto-register. All accept optional `reason: str | list = ""` and `background: list[Knowledge] | None = None`.

### Leaf Strategies

#### `support(premises, conclusion, *, reason="", prior=None, background=None)`

**The most common strategy type.** Soft deduction based on the directed `implication` operator (A=1 → B must =1): premises jointly support conclusion via forward implication. Same structure as `deduction` (conjunction + directed implication) but with an author-specified prior on the implication warrant. `reason` and `prior` must be paired: both or neither.

```python
conclusion = claim("MgB2 has two superconducting gaps")
support(
    [band_structure_evidence, tunneling_data, specific_heat_anomaly],
    conclusion,
    reason="Three independent lines of evidence converge",
    prior=0.85,
)
```

#### `deduction(premises, conclusion, *, reason="", prior=None, background=None)`

Strict logical entailment based on the directed `implication` operator. Same skeleton as `support` (conjunction + directed implication) but semantically rigid (deterministic). Requires >= 1 premise. `reason` and `prior` must be paired: both or neither.

Key test: "If premises are all true, is this conclusion NECESSARILY true?"
- Yes -> deduction
- No (approximations, empirical judgment, omitted premises) -> support

```python
theorem = claim("The series converges")
deduction(
    [bounded_above, monotonically_increasing],
    theorem,
    reason="Monotone convergence theorem",
    prior=0.99,
    background=[real_analysis_definition],
)
```

#### `compare(pred_h, pred_alt, observation, *, reason="", prior=None, background=None)`

Compare two predictions against an observation. Compiles to 2 equivalence operators (matching each prediction to observation) + 1 implication (inferential ordering). Auto-generates a `comparison_claim` as the conclusion. `reason` and `prior` must be paired: both or neither.

```python
pred_h = claim("H predicts 3:1 ratio.")
pred_alt = claim("Alt predicts continuous distribution.")
obs = claim("Observed 2.96:1 ratio.")
comp = compare(pred_h, pred_alt, obs,
    reason="H matches observation much better", prior=0.9)
# comp.conclusion is the auto-generated comparison claim
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

#### `fills(source, target, *, mode=None, strength="exact", background=None, reason="")`

Cross-package interface bridging. `strength` is `"exact"` | `"partial"` | `"conditional"`. `mode` is `"deduction"` | `"infer"` | `None` (auto-resolved).

```python
local_evidence = claim("Our measurement confirms the prediction.")
fills(local_evidence, imported_interface_claim, strength="exact")
```

#### `noisy_and()` (deprecated)

**Deprecated -- use `support()` instead.** Emits `DeprecationWarning`. Compiles to `support` internally.

### Named Strategies (auto-formalized at compile time)

#### `abduction(support_h, support_alt, comparison, *, background=None, reason="")`

Inference to best explanation. Takes three Strategy objects: two `support` strategies (for the hypothesis and alternative) and one `compare` strategy. Auto-generates a `composition_warrant` claim. Conclusion comes from the comparison strategy's conclusion.

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

#### `induction(support_1, support_2, law, *, background=None, reason="")`

Binary composite strategy: two support strategies jointly confirm a law. Chainable: `induction(prev_induction, new_support, law)`. Auto-generates a `composition_warrant` claim.

```python
law = claim("MgB2 universally superconducts below 39K")
obs1 = claim("Sample A shows zero resistance below 39K")
obs2 = claim("Sample B shows zero resistance below 39K")
obs3 = claim("Sample C shows zero resistance below 39K")

s1 = support([law], obs1, reason="law predicts observation", prior=0.9)
s2 = support([law], obs2, reason="law predicts observation", prior=0.9)
s3 = support([law], obs3, reason="law predicts observation", prior=0.9)

ind_12 = induction(s1, s2, law=law, reason="Samples A and B are independent")
ind_123 = induction(ind_12, s3, law=law, reason="Sample C independent of A and B")
```

#### `composite(premises, conclusion, *, sub_strategies, reason="", background=None, type="infer")`

Hierarchical composition. Only leaf sub-strategies need prior parameters.

```python
intermediate = claim("Intermediate result")
final = claim("Final conclusion")

s1 = deduction([axiom_a, axiom_b], intermediate, reason="From axioms", prior=0.99)
s2 = support([intermediate, empirical_data], final, reason="Combined evidence", prior=0.85)

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

**WARNING: Do NOT define `__all__` in submodules.** If a submodule defines `__all__: list[str] = []`, then `from .module import *` imports nothing, and all claims in that module get anonymous labels (`_anon_xxx`). Only define `__all__` in `__init__.py` to control the package's cross-package exports.

## 6. Exports and Labels

`__all__` controls visibility:
- Listed in `__all__` -> **exported** (cross-package interface, other packages can import)
- No `_` prefix -> **public** (visible in package scope)
- `_` prefix -> **private** (package-internal helper)

```python
__all__ = ["main_theorem", "key_observation"]  # exported

main_theorem = claim("...")           # exported (in __all__)
supporting_lemma = claim("...")       # public (no underscore, not in __all__)
_helper = claim("...")                # private (underscore prefix)
```

**Abduction alternative claims must be public.** Claims used as alternatives in abduction need proper labels for `priors.py` to reference them. Use `alt_` prefix (not `_alt_`):

```python
# CORRECT: public, gets label "alt_nonspecific_binding"
alt_nonspecific_binding = claim("Non-specific binding could explain...")

# WRONG: private, gets anonymous label, cannot be reviewed
_alt_nonspecific_binding = claim("Non-specific binding could explain...")
```

Labels are auto-assigned from Python variable names by `gaia compile`. NEVER set `.label` manually.

**Strategy naming:** Strategies should also be assigned to named public variables so they appear in `gaia check --brief` output and can be referenced by name. Use descriptive names: `strat_tc_al = support(...)`, `composite_workflow = composite(...)`, `abduction_al = abduction(...)`. Bare strategy calls (e.g., `deduction(...)` without assignment) produce anonymous strategies invisible in CLI output.

```python
# CORRECT: label "tc_prediction" assigned automatically
tc_prediction = claim("Tc of MgB2 is 39K")

# WRONG: never do this
tc_prediction.label = "tc_prediction"  # anti-pattern
```

## 7. References and Citations

Claim content and strategy reasons support two kinds of references:

### Knowledge references (`@label`)

Reference other knowledge nodes by their Python variable name. Opportunistic — if the label is not found, treated as literal text (no error).

```python
reason="Based on @framework_claim, the result follows from @property_setting."
```

### Bibliographic citations (`[@key]`)

Cite entries from `references.json` (CSL-JSON, at the package root). Strict — missing key is a compile error.

```python
# In claim content
tc = claim("Tc = 287.7 K at 267 GPa [@Dias2020].", title="CSH Tc")

# In strategy reason
support([evidence], conclusion,
    reason="Following the analysis in [@Hirsch2021], the data is inconsistent.",
    prior=0.85)
```

Supports Pandoc citation syntax: `[@key1; @key2]` (group), `[see @key, pp. 33-35]` (locator), `[-@key]` (suppress author).

### references.json format

```json
{
  "Dias2020": {
    "type": "article-journal",
    "title": "Room-temperature superconductivity in a carbonaceous sulfur hydride"
  }
}
```

Each entry requires `type` (CSL 1.0.2) and `title`. Keys follow Pandoc grammar (letters, digits, `_`, `-`, `.`, `:`, `/`). File is optional.

### Rules

- **Escape**: `\@key` forces literal
- **No collision**: a key cannot exist in both the label table and `references.json` (compile error)
- **Homogeneous groups**: a single `[...]` group must be all knowledge refs or all citations, never mixed (compile error)

## 8. Anti-patterns (HARD GATE -- these produce invalid packages)

| Anti-pattern | Why it fails | Correct approach |
|-------------|-------------|-----------------|
| `Package(...)` context manager | Removed in v5 | Use module structure + `pyproject.toml` |
| Manually setting `.label = "name"` | Labels auto-assigned from variable names | Just assign to a variable |
| `setting` or `question` as strategy premises | Settings/questions have no probability | Use `background=` parameter instead |
| Using `noisy_and()` | Deprecated | Use `support()` instead |
| Old `abduction(observation, hypothesis)` signature | Redesigned | Use `abduction(support_h, support_alt, comparison)` with 3 Strategy objects |
| Providing `reason` without `prior` (or vice versa) | Must be paired | Provide both or neither |
| Building `FormalExpr` by hand | Compiler handles formalization | Use named strategies (deduction, support, etc.) |
| `from gaia.gaia_ir import ...` | Module renamed | Use `from gaia.ir import ...` |
| `dependencies = ["gaia-lang"]` in pyproject.toml | CLI provided externally, not a package dep | Omit gaia-lang from dependencies |
| Omitting `[build-system]` in pyproject.toml | Required for `uv sync` in CI | Always include build-system section |
