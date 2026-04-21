# Gaia Lang v6 Design

> **Status:** Target design  
> **Date:** 2026-04-21  
> **Scope:** Gaia Lang authoring DSL — Knowledge types, verb system (Support/Relate/Infer), parameterized Claims, InquiryState, Quality Gate  
> **Supersedes:** [2026-04-18-gaia-lang-v6-design.md](2026-04-18-gaia-lang-v6-design.md), [2026-04-20-gaia-lang-v6-strategy-warrant-spec.md](2026-04-20-gaia-lang-v6-strategy-warrant-spec.md)  
> **Companion:** [2026-04-21-gaia-ir-v6-design.md](2026-04-21-gaia-ir-v6-design.md)  
> **Non-goal:** Composition (induction/abduction/compose), standard inference library (ab_test/binomial_test), exhaust() relation.

---

## 0. Design Goals

1. **Claim-first authoring**: Authors declare Claims, then connect them with warranted reasoning verbs.
2. **Three verb categories**: Support (directional), Relate (logical), Infer (statistical).
3. **No probability on Strategy**: Uncertainty is expressed through explicit premise Claims, not edge weights.
4. **Warrant is review state**: ReviewManifest records whether each reasoning step has been accepted by a reviewer.
5. **Parameterized Claims**: Docstring templates with `[@ref]` for Knowledge parameters and `{param}` for value parameters.
6. **IR-first compilability**: Every construct compiles to Gaia IR. No new IR node types beyond what the companion IR spec defines.

---

## 1. Knowledge Type System

### 1.1 Type hierarchy

```
Knowledge              ← Plain text, not in reasoning graph
├── Context            ← Raw unformalized text (lab notes, paper excerpts)
├── Setting            ← Formalized background (definitions, conditions), no probability
├── Claim              ← Proposition with prior, participates in BP
│   └── User subclasses ← Parameterized domain types
└── Question           ← Open inquiry, organizes investigation
```

### 1.2 Context

Stores raw text or artifact excerpts that have not yet been formalized into Claims.

```python
ctx = Context("""
Experiment exp_123 ran from March 1 to March 14.
Control A had 10,000 users and 500 conversions.
Treatment B had 10,000 users and 550 conversions.
""")
```

- Does not enter BP.
- Cannot be a Strategy premise.
- Claims may reference Context via Grounding `source_refs`.

### 1.3 Setting

Formalized background context, convention, scope, or units.

```python
lab = Setting("Blackbody cavity experiment at thermal equilibrium.")
exp = Setting("AB test exp_123: 50/50 hash-based randomization, March 1-14.")
```

- No prior/posterior.
- May appear in Strategy `background`.
- If a background proposition is uncertain, it should be a Claim, not a Setting.

### 1.4 Claim

The only user-facing object with prior/posterior belief.

```python
quantum_hyp = Claim("Energy exchange is quantized.", prior=0.5)
```

Core rule: **every exported or non-root Claim needs a warrant** — a Strategy or Relation connecting it to the reasoning graph. A Claim with a prior but no warrant is a structural hole.

### 1.5 Question

Inquiry lens. Organizes exploration but does not enter BP.

```python
q = Question("Should variant B be shipped?", targets=[ship_b])
```

---

## 2. Parameterized Claims

### 2.1 Class definition = predicate schema

Users define parameterized Claim classes by inheriting from Claim. The docstring is a `str.format()` template. Type annotations define parameters:

```python
class CavityTemperature(Claim):
    """Cavity temperature is set to {value}K."""
    value: float

class InfoTransfer(Claim):
    """Information can transfer from {src} to {dst}."""
    src: MoleculeType
    dst: MoleculeType
```

Instance = ground formula:

```python
T = CavityTemperature(value=5000.0)
# T.content = "Cavity temperature is set to 5000.0K."
```

### 2.2 Two kinds of parameters

- **Value parameters** (`int`, `float`, `str`, `Enum`): use `{param_name}` template substitution.
- **Knowledge parameters** (`Setting`, `Claim`, or subclasses): use `[@param_name]` reference syntax. Compiler resolves to the referenced node's QID.

```python
class ABCounts(Claim):
    """[@experiment] recorded {ctrl_k}/{ctrl_n} control and {treat_k}/{treat_n} treatment conversions."""
    experiment: Setting    # Knowledge parameter — [@experiment]
    ctrl_n: int            # value parameter — {ctrl_n}
    ctrl_k: int
    treat_n: int
    treat_k: int
```

Template rendering order:
1. Compiler binds Knowledge-typed parameters to their labels (for `[@...]` resolution).
2. Refs resolver processes `[@...]` references.
3. `str.format()` substitutes value-typed parameters.

### 2.3 Param dataclass

```python
@dataclass
class Param:
    name: str
    type: type
    value: Any = UNBOUND  # sentinel, not None
```

### 2.4 Partial binding

Unbound parameters remain as `{param_name}` or `[@param_name]` placeholders. Partial binding is supported:

```python
dna_transfer = InfoTransfer(src=MoleculeType.DNA)
# dst unbound, content = "Information can transfer from DNA to {dst}."
```

### 2.5 Enum domains

For Enum-typed parameters, domain is automatically derived from `Enum.__members__`. `gaia check --inquiry` shows grounding coverage:

```
Goal: info_transfer (exported, parameterized)
  Grounded: 4/9 bindings
  Ungrounded: 5 bindings
```

### 2.6 Python as predicate logic

- Python `for` = ∀ (universal quantification)
- Python `if` = conditional
- Python function = parameterized schema
- Python Enum = finite domain

```python
for src, dst, name, evidence in confirmed_transfers:
    reported = Claim(f"{name} reports transfer from {src} to {dst}.")
    observe(conclusion=reported, rationale=f"{name}: {evidence}")
    derive(
        conclusion=InfoTransfer(src=src, dst=dst),
        given=reported,
        rationale=f"{name} confirmed by independent evidence.",
    )
```

v6 supports single-level ∀. Nested quantifiers and lifted inference are deferred.

---

## 3. Grounding

Grounding explains why a root Claim can have a prior. It is not a Strategy and does not enter BP.

```python
uv_data = Claim(
    "Measured spectrum deviates from Rayleigh-Jeans law.",
    prior=0.95,
    grounding=Grounding(
        kind="source_fact",
        rationale="Extracted from Fig.2 of [@Planck1901].",
    ),
)
```

Recommended grounding kinds:

```
assumption       — "I assume this is true based on domain knowledge."
source_fact      — "Extracted from a specific source."
definition       — "True by definition."
imported         — "Imported from another package."
judgment         — "Expert or LLM judgment."
open             — "No justification yet."
```

Lint rule:

```
A root Claim with a non-default prior should have grounding or incoming Strategy support.
```

---

## 4. Verb System

Gaia Lang v6 verbs are organized into three categories:

| Category | Verbs | Semantics |
|---|---|---|
| **Support** | `derive()`, `observe()`, `compute()` | Directional: given → conclusion |
| **Relate** | `equal()`, `contradict()` | Logical constraint: connect two Claims |
| **Infer** | `infer()` | Statistical inference: P(E\|H) update |

### 4.1 Common parameters

All verbs share:

| Parameter | Type | Meaning |
|---|---|---|
| `given` | `Claim \| tuple[Claim, ...]` | Probabilistic conditions. Tuple auto-compiles to conjunction. |
| `background` | `list[Setting]` | Non-probabilistic context. Not in BP. |
| `rationale` | `str` | Required. Why this step is valid. |

No verb has a `prior` parameter. Uncertainty is on Claims.

---

## 5. Support Verbs

### 5.1 derive

Logical derivation. The most common support verb.

```python
derive(
    conclusion: Claim,
    given: Claim | tuple[Claim, ...],
    background: list[Setting] = [],
    rationale: str = "",
)
```

```python
derive(
    conclusion=quantum_hyp,
    given=(planck_result, uv_data),
    rationale="Planck spectrum matches observed data and resolves UV catastrophe.",
)
```

Compiles to `FormalStrategy(type="deduction")`:

```
G = AllTrue(planck_result, uv_data)
S = Implies(G, quantum_hyp)
assertions = [S]
```

### 5.2 observe

Empirical observation or measurement. Structurally identical to deduction, but with different review semantics.

```python
observe(
    conclusion: Claim,
    given: Claim | tuple[Claim, ...] = (),
    background: list[Setting] = [],
    rationale: str = "",
)
```

**With premises** (conditional observation):

```python
calibrated = Claim("Spectrometer calibration is within tolerance.", prior=0.95)

observe(
    conclusion=uv_data,
    given=calibrated,
    background=[lab, spectrometer],
    rationale="Measured at 5 frequency points with calibrated UV-visible spectrometer.",
)
```

Compiles to `FormalStrategy(type="observation")`.

**Without premises** (root fact):

```python
observe(
    conclusion=uv_data,
    background=[lab],
    rationale="Measured at 5 frequency points.",
)
```

Does NOT generate a Strategy. Instead adds `Grounding(kind="source_fact")` to the Claim.

### 5.3 compute

Deterministic code execution. Available as both a function and a `@compute` decorator.

#### Primitive: `compute()` function

```python
result = compute(
    fn=planck_spectrum_fn,
    conclusion=SpectralRadiance,
    given=(T, freq),
    rationale="Planck's law: B(ν,T) = (2hν³/c²) · 1/(exp(hν/kT) - 1).",
)
```

#### Sugar: `@compute` decorator

```python
@compute
def planck_spectrum(T: CavityTemperature, freq: TestFrequency) -> SpectralRadiance:
    """Planck's law: B(ν,T) = (2hν³/c²) · 1/(exp(hν/kT) - 1)."""
    import math
    h, c, k = 6.626e-34, 3e8, 1.38e-23
    return (2 * h * freq.value**3 / c**2) / (math.exp(h * freq.value / (k * T.value)) - 1)

result = planck_spectrum(CavityTemperature(value=5000.0), TestFrequency(value=1e15))
```

Decorator extracts:
- Input types from function signature → type constraints on given
- Output type from return annotation → conclusion Claim class
- Docstring → rationale

Compiles to `Strategy(type="computation")` + `ComputationMethod`.

**Compute chains**: One compute's output (Claim subclass) can be input to another compute, automatically forming reasoning chains.

---

## 6. Relate Verbs

Relate verbs create logical constraints between two Claims. They compile to Operators and return helper Claims.

### 6.1 equal

Declares two Claims are equivalent/consistent.

```python
agreement = equal(
    prediction, observation,
    rationale="The predicted Planck spectrum agrees with measured data.",
)
```

Returns `Equivalence` helper Claim. Compiles to `Operator(type="equivalence")`.

### 6.2 contradict

Declares two Claims are contradictory.

```python
conflict = contradict(
    classical_prediction, observed_finite,
    rationale="Classical theory predicts divergence, but observation reports finite radiation.",
)
```

Returns `Contradiction` helper Claim. Compiles to `Operator(type="contradiction")`.

### 6.3 Using helper Claims

Returned helper Claims can be used as premises in downstream derive:

```python
agreement = equal(quantum_prediction, observation, rationale="...")
conflict = contradict(classical_prediction, observation, rationale="...")

derive(
    conclusion=quantum_hyp,
    given=(agreement, conflict),
    rationale="Quantum prediction matches and classical contradicts observation.",
)
```

---

## 7. Infer Verb

### 7.1 infer

Statistical evidence update based on Jaynes/Bayes framework. All parameters are keyword-only.

```python
infer(
    *,
    hypothesis: Claim,
    evidence: Claim,
    background: list[Setting | Claim] = [],
    p_e_given_h: float,
    p_e_given_not_h: float,
    rationale: str = "",
) -> StatisticalSupport
```

No `given` parameter — assumptions and conditions go in `background` (not in BP). If assumptions are questionable, reviewer rejects the Strategy via ReviewManifest.

```python
support = infer(
    hypothesis=quantum_hyp,
    evidence=spectrum_data,
    background=[exp_setting, reliable_measurement, calibrated],
    p_e_given_h=0.9,
    p_e_given_not_h=0.05,
    rationale="Planck spectrum is highly expected under quantum theory, very unlikely under alternatives.",
)
```

Returns `StatisticalSupport` helper Claim. Compiles to `Strategy(type="infer", premises=[H], conclusion=E)` + CPT `[p_e_given_not_h, p_e_given_h]`.

### 7.2 Semantics

`infer()` creates a bidirectional factor between hypothesis and evidence:

```
odds(H) *= P(E|H) / P(E|¬H)
```

The factor has exactly two CPT entries — no gate complexity. Assumptions are review context, not probabilistic variables. If an assumption is wrong, the reviewer rejects the Strategy entirely rather than attenuating it probabilistically.

### 7.3 Three sources of P(E|H) values

| Source | Example |
|---|---|
| Formula-computed | `p_h, p_not_h = two_binomial_lr(counts)` then pass to `infer()` |
| LLM/human judgment | Directly estimate P(E\|H) and P(E\|¬H) |
| External import | Import Bayes factor from statistical software |

### 7.4 Standard library helpers (deferred)

Convenience wrappers like `ab_test()`, `binomial_test()`, `t_test()` are deferred. They are not core DSL — just Python functions that compute P(E|H) and call `infer()`.

---

## 8. ReviewManifest

### 8.1 Warrant

Users do not write Warrant objects directly. When the compiler emits a Strategy, a Warrant is automatically generated in ReviewManifest with `status="unreviewed"`.

Audit questions are auto-generated from Strategy type using `[@...]` templates:

| Strategy type | Audit question template |
|---|---|
| deduction | "Do the listed premises suffice to establish [@conclusion]?" |
| observation | "Is the observation of [@conclusion] reliable under the stated conditions?" |
| computation | "Is the computation of [@conclusion] correctly implemented?" |
| infer | "Is the statistical association between [@hypothesis] and [@evidence] valid at the stated probabilities?" |
| equal | "Are [@a] and [@b] truly equivalent?" |
| contradict | "Do [@a] and [@b] truly contradict?" |

### 8.2 Review workflow

```bash
gaia check --warrants              # Export all warrants with audit questions
gaia check --warrants --blind      # Export with empty status (avoid anchoring bias)
```

Reviewer sets status for each Warrant:

```
accepted        — Strategy participates in inference
rejected        — Strategy is excluded
needs_inputs    — Missing premise Claims needed
unreviewed      — Default; Strategy does NOT participate (pessimistic)
```

If reviewer marks `needs_inputs`, the fix is to add explicit Claims to the reasoning graph and regenerate.

### 8.3 Multi-round review

Same Strategy can be reviewed multiple times (different rounds). Latest status determines whether it participates.

---

## 9. InquiryState

### 9.1 Concept

InquiryState is a goal-oriented reasoning progress snapshot — shows each exported Claim's dependency tree, warrant coverage, and structural holes.

### 9.2 CLI integration

```bash
gaia check                     # Structural validation
gaia check --holes             # Show structural holes
gaia check --inquiry           # Goal-oriented InquiryState
gaia check --warrants          # Export warrant list
gaia check --warrants --blind  # Blank-slate mode
gaia check --gate              # Quality gate
```

### 9.3 InquiryState output

```
$ gaia check --inquiry

Package: blackbody-radiation-gaia
  Context: Planck's analysis of blackbody radiation spectrum (1900)...

━━━ Goal 1: quantum_hyp (exported) ━━━
  Status: WARRANTED (2/3 accepted)

  quantum_hyp ← derive(planck_result, uv_data) [accepted ✓]
  │  "Planck spectrum resolves UV catastrophe."
  │
  ├─ planck_result ← compute(T, freq) [accepted ✓]
  │  "Planck's law: B(ν,T) = ..."
  │
  └─ uv_data ← observe() [unreviewed ⚠]
     "Measured at 5 frequency points..."

  quantum_hyp ⊥ classical_hyp ← contradict [accepted ✓]

━━━ Summary ━━━
  Exported goals:      1
  Accepted warrants:   2/3
  Unreviewed:          1 (blocks inference)
  Structural holes:    0
```

### 9.4 Hole types

| Type | Meaning | Severity |
|---|---|---|
| **Unwarranted** | Claim has no Strategy/Operator connection (even if it has a prior) | Structural hole |
| **Unreviewed** | Has warrant but not yet accepted | Blocks inference |

Core principle: **prior ≠ justification**. A Claim without a warrant is a hole regardless of its prior.

---

## 10. Quality Gate

Configurable quality gate for CI:

```toml
# pyproject.toml
[tool.gaia.quality]
min_posterior = 0.7    # Minimum posterior for exported Claims
# allow_holes defaults to false
```

```bash
gaia check --gate   # Fails if quality criteria not met
```

Quality gate checks:
1. No structural holes (exported Claims must have warrant chains)
2. All Strategies in warrant chains must be accepted
3. All exported Claims meet minimum posterior threshold

---

## 11. Provenance and References

v6 reuses the existing references and provenance pipeline from the [References & @ Syntax spec](2026-04-09-references-and-at-syntax.md).

All text fields that accept `[@...]` references:
- `Claim.content` and parameterized docstring templates
- `Strategy.rationale`
- `Grounding.rationale`
- Warrant `audit_question` (auto-generated with `[@...]` templates)

Resolved references are recorded in `metadata.gaia.provenance`:

```python
knowledge.metadata["gaia"]["provenance"] = {
    "cited_refs": ["Planck1901"],
    "referenced_claims": ["uv_data", "planck_result"],
}
```

---

## 12. Compilation to IR

| v6 DSL | IR compilation target |
|---|---|
| `Context(...)` | `Knowledge(type="context")` |
| `Setting(...)` | `Knowledge(type="setting")` |
| `Claim(...)` / subclasses | `Knowledge(type="claim")` + bound parameters |
| `Question(...)` | `Knowledge(type="question")` |
| `derive(...)` | `FormalStrategy(type="deduction")` + conjunction + implication helpers |
| `observe(...)` with given | `FormalStrategy(type="deduction", metadata.pattern="observation")` |
| `observe(...)` no given | `Grounding(kind="source_fact")` on the Claim |
| `compute(...)` / `@compute` | `FormalStrategy(type="deduction", metadata.compute={...})` |
| `equal(A, B)` | `Operator(type="equivalence")` + Equivalence helper |
| `contradict(A, B)` | `Operator(type="contradiction")` + Contradiction helper |
| `infer(...)` | `Strategy(type="infer", premises=[H], conclusion=E)` + CPT `[p_e_given_not_h, p_e_given_h]` + StatisticalSupport helper |
| `given=(A, B, C)` tuple | `Operator(type="conjunction")` + conjunction helper |
| `rationale=` | `steps=[Step(reasoning=rationale)]` |
| `background=` | `Strategy.background` |
| Review | `ReviewManifest` with `Review` entries |

---

## 13. v5 → v6 Migration

### 13.1 Terminology mapping

| v5 | v6 | Notes |
|---|---|---|
| `claim("...")` | `Claim("...")` or subclass | Uppercase, class style |
| `setting("...")` | `Setting("...")` | Uppercase |
| `question("...")` | `Question("...")` | Uppercase |
| `support([a], b, prior=0.9)` | `derive(conclusion=b, given=a, rationale=...)` | No prior |
| `deduction([a], b)` | `derive(conclusion=b, given=a, rationale=...)` | No prior, no type= |
| `contradiction(a, b)` | `contradict(a, b, rationale=...)` | Returns helper Claim |
| `equivalence(a, b)` | `equal(a, b, rationale=...)` | Returns helper Claim |
| `noisy_and` | Deprecated | Use `derive()` |
| `review_claim(...)` | `priors.py` PRIORS dict | Already deprecated in v5 |
| `review_strategy(...)` | ReviewManifest Warrants | Via `gaia check --warrants` |
| `composite(...)` | Deferred | Write chains manually |
| `fills(source, target)` | Unchanged | Cross-package premise bridge |

### 13.2 Compatibility

v5 function-style API (`claim()`, `support()`, `deduction()`, etc.) is preserved as a deprecated compatibility layer compiling to the same IR. New packages should use v6 API.

---

## 14. Deferred Features

The following are explicitly out of scope for v6.0:

1. **Composition**: `induction()`, `abduction()`, `compose()` — users write chains manually
2. **Standard inference library**: `ab_test()`, `binomial_test()`, `t_test()` — convenience wrappers
3. **`exhaust()` relation**: Disjunction + mutual exclusion combined
4. **Claim operator overloading**: `A & B`, `A | B`, `~A` — syntactic sugar for conjunction/disjunction/complement. `given=(A, B)` tuple suffices for conjunction in v6.
5. **Nested quantifiers**: `∀x ∃y. P(x,y)` — needs Skolemization
5. **Lifted inference**: Large domains without grounding
6. **Interactive InquiryState**: Lean-style tactic REPL
7. **`gaia run` execution protocol**: Remote compute execution and witness persistence
8. **Inquiry trace**: Timeline, failed hypotheses, experiment planning history
