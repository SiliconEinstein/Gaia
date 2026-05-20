---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Formula Logic In Gaia Lang

Formula logic is Gaia's bridge between human-readable scientific claims and
machine-readable logical structure. It lets an author attach a `Formula` AST to
a `Claim`:

```python
claim("A and B are both true.", formula=land(ClaimAtom(a), ClaimAtom(b)))
```

The prose remains the reviewer-facing scientific statement. The formula is the
structured contract that Gaia can compile, validate, lower, and inspect.

This page explains where formula logic sits in the Gaia stack. The detailed
syntax for variables, domains, predicates, and quantifiers is in
[Predicate Logic In Gaia Lang](predicate-logic.md). BP-side probability scoring
for logic warnings is in [Diagnostic Probabilities](../bp/diagnostic-probabilities.md).

Source references:

- `gaia/engine/lang/runtime/knowledge.py`
- `gaia/engine/lang/formula/`
- `gaia/engine/lang/dsl/formula.py`
- `gaia/engine/lang/compiler/lower_formula.py`
- `gaia/engine/lang/compiler/compile.py`
- `gaia/engine/ir/formula.py`
- `gaia/engine/ir/logic/diagnostics.py`
- `tests/gaia/lang/test_formula_lowering.py`
- `tests/gaia/logic/test_formula_diagnostics.py`

---

## 1. What Formula Logic Defines

Formula logic defines the internal shape of a claim. It answers questions like:

- Which existing claims are being combined?
- Is the claim an alias of another claim?
- Is it a conjunction, disjunction, negation, implication, or equivalence?
- Does a finite quantifier expand into grounded instances?
- Is one claim's formula internally inconsistent?
- Do two different claims make formula-level commitments that cannot both hold?

Formula logic does **not** decide whether the claim is scientifically true. That
belongs to priors, evidence, reasoning actions, BP, and reviewer judgment.

| Layer | Owns |
|---|---|
| Claim prose | The self-contained scientific statement a reviewer reads. |
| `formula=` AST | The machine-readable logical shape of that statement. |
| `FormulaGraph` | The compiled, persistent formula structure in Gaia IR. |
| Formula lowering | Generated operators, helper claims, and metadata for the supported subset. |
| Formula diagnostics | Fatal local defects and non-fatal cross-claim warnings. |
| BP probability scoring | Optional ranking of diagnostic warnings under a belief graph. |

The key authoring rule is: **a formula should make a claim more inspectable, not
replace the claim text.** Formula-bearing claims should still be self-contained
prose statements.

---

## 2. Authoring Model

A formula is attached to a claim:

```python
from gaia.engine.lang import ClaimAtom, claim, land, lnot

a = claim("A is true.")
a.label = "a"
b = claim("B is true.")
b.label = "b"

both = claim(
    "A is true and B is false.",
    formula=land(ClaimAtom(a), lnot(ClaimAtom(b))),
)
both.label = "a_and_not_b"
```

`ClaimAtom(x)` is the bridge from ordinary claim truth values into formula land.
Connectives such as `land`, `lor`, `lnot`, `implies`, and `iff` build a Boolean
formula over those atoms.

For predicate logic, the formula can instead be built from variables, domains,
predicates, comparisons, and quantifiers. See
[Predicate Logic In Gaia Lang](predicate-logic.md) for the term-level details.

Formula logic is different from reasoning actions:

| Use this | When |
|---|---|
| `claim(formula=...)` | The formula is part of the claim's internal logical shape. |
| `derive(...)`, `observe(...)`, `compute(...)` | You are asserting a reviewable support step between claims. |
| `contradict(...)`, `equal(...)`, `exclusive(...)` | You are asserting a relation between claims as authored reasoning. |
| `associate(...)` | You are adding a probabilistic relation between claim variables. |

---

## 3. Compilation Contract

During `compile_package_artifact(pkg)`, the compiler processes local claims that
carry `formula`.

For each formula claim, Gaia currently does two things:

1. It records a `FormulaGraph` in the compiled `LocalCanonicalGraph`.
2. It lowers the supported subset into ordinary Gaia IR objects:
   - `ClaimAtom(x)` can become an alias relation to claim `x`.
   - `land`, `lor`, `lnot`, `implies`, and `iff` lower to deterministic
     operators.
   - atomic predicate/comparison formulas record formula metadata and may
     generate formula-atom helper claims when they appear inside connectives.
   - finite-domain `forall` and `exists` lower to grounded instance claims plus
     implication, disjunction, or equivalence operators depending on shape.

The compiled graph remains a Gaia claim graph. There is no separate theorem
prover hidden inside Gaia Lang. Formula logic gives the compiler and reviewers a
structured object to inspect.

Generated formula helpers use metadata such as:

- `formula_lowering`
- `generated_kind`
- `helper_kind`
- `source_claim`
- `formula_atom`
- `formula_bindings`

These helpers are implementation artifacts. Package authors should not treat
them as independent scientific claims or assign them manual priors.

---

## 4. FormulaGraph

`FormulaGraph` is the persistent IR representation of a formula. It stores:

- `source_claim` — the claim whose formula produced the graph
- `root` — the root formula node id
- `nodes` — atoms, operators, quantifiers, variables, and related descriptors
- `edges` — roles such as `operand`, `antecedent`, `consequent`,
  `bound_variable`, and `body`

Why keep a `FormulaGraph` if lowering already emits operators?

- Lowering serves BP and inference.
- `FormulaGraph` preserves the author's formula shape for validation,
  diagnostics, review, and future richer logic tools.

This is why diagnostics inspect `LocalCanonicalGraph.formula_graphs` directly
instead of trying to reconstruct formula intent from BP factors.

---

## 5. Diagnostics Semantics

Formula diagnostics inspect formula structure and return a
`FormulaDiagnosticReport`:

```python
from gaia.engine.ir.logic import inspect_formula_graphs

report = inspect_formula_graphs(compiled.graph)
```

The current diagnostics subset projects propositional formula graphs to SymPy.
It supports claim atoms and Boolean connectives. Quantifier roots and other
unsupported shapes are preserved in `FormulaGraph`, but formula diagnostics
report them as outside the current propositional subset rather than pretending
to prove first-order statements.

Severity follows a small operational contract:

| Situation | Severity | Why |
|---|---|---|
| One claim's own formula is unsatisfiable | `fatal` | The claim is malformed as a logical object. |
| One claim's own formula is tautological | `warning` | The claim may be uninformative, but it is not invalid. |
| One formula repeats operands | `info` | Cleanup signal. |
| Two claims cannot both hold | `warning` | Cross-claim conflict is review evidence, not a compile failure. |
| One claim entails another | `info` | Useful relation; policy may rank it later. |

The important boundary is same-claim vs cross-claim:

- `claim("A and not A", formula=land(ClaimAtom(a), lnot(ClaimAtom(a))))`
  is fatal for that claim.
- A pair of separately authored claims whose formulas are `A` and `not A`
  produces a warning, because each claim has its own prior and belief.

Cross-claim diagnostics carry a `DiagnosticCondition`, such as `A and B`, that
downstream BP code can score. The diagnostics layer itself does not run BP.

---

## 6. Worked Physics Example

This example uses two self-contained claims about the BICEP2 CMB B-mode result.
Each claim explains the jargon it uses, so a reviewer can read either one
without chasing earlier declarations.

```python
from gaia.engine.lang import ClaimAtom, associate, claim, land, lnot
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.ir.logic import inspect_formula_graphs

with CollectedPackage("cmb_bmode_logic_e2e", namespace="physics", version="0.1.0") as pkg:
    bmode_excess = claim(
        "BICEP2 reports a degree-scale CMB B-mode excess, meaning an unexpectedly "
        "strong curl-like polarization pattern in the cosmic microwave background "
        "on degree angular scales.",
        prior=0.9,
    )
    bmode_excess.label = "bmode_excess"

    primordial_tensor = claim(
        "The B-mode excess is dominated by primordial tensor modes, meaning "
        "gravitational-wave fluctuations from early-universe inflation rather than "
        "later astrophysical foregrounds.",
        prior=0.4,
    )
    primordial_tensor.label = "primordial_tensor"

    tensor_interpretation = claim(
        "BICEP2 interpretation: BICEP2 reports a degree-scale CMB B-mode excess, "
        "meaning an unexpectedly strong curl-like polarization pattern in the "
        "cosmic microwave background; this claim says the excess is mainly a "
        "primordial tensor signal, meaning gravitational-wave fluctuations from "
        "early-universe inflation rather than later astrophysical foregrounds.",
        formula=land(ClaimAtom(bmode_excess), ClaimAtom(primordial_tensor)),
        prior=0.4,
    )
    tensor_interpretation.label = "bicep2_tensor_interpretation"

    dust_interpretation = claim(
        "Planck foreground interpretation: BICEP2 reports a degree-scale CMB "
        "B-mode excess, meaning an unexpectedly strong curl-like polarization "
        "pattern in the cosmic microwave background; this claim says the excess "
        "is mainly Galactic dust foreground, meaning polarized emission from "
        "dust in the Milky Way, not primordial tensor modes from inflationary "
        "gravitational waves.",
        formula=land(ClaimAtom(bmode_excess), lnot(ClaimAtom(primordial_tensor))),
        prior=0.6,
    )
    dust_interpretation.label = "planck_dust_interpretation"

    tension = associate(
        tensor_interpretation,
        dust_interpretation,
        p_a_given_b=0.5,
        p_b_given_a=0.75,
        pattern=None,
        rationale=(
            "Corpus/reviewer state still gives nontrivial belief to both historical "
            "interpretations, so the logic warning should be probability-scored."
        ),
        label="bmode_interpretation_tension",
    )
    tension.label = "bmode_tension_helper"

artifact = compile_package_artifact(pkg)
report = inspect_formula_graphs(artifact.graph)
```

The formulas state:

```text
tensor interpretation = bmode_excess AND primordial_tensor
dust interpretation   = bmode_excess AND NOT primordial_tensor
```

Formula diagnostics therefore emit a `cross_claim_incompatibility` warning. The
warning is not fatal because the incompatible statements are separate claims.
The optional `associate(...)` relation belongs to the belief graph; it lets a
reviewer-facing layer score how likely the active warning is under current
beliefs. When scoring formula diagnostics, use
`belief_graph_for_formula_scoring(artifact.graph)` so compiler-generated formula
operators do not condition on the warning being scored.

---

## 7. Design Boundaries

Formula logic defines structure, not truth:

- It does not assign priors. Priors belong on independent claim variables.
- It does not make generated helpers independent scientific facts.
- It does not decide whether a physical explanation is correct.
- It does not turn cross-claim disagreement into a compile error.
- It does not replace review policy.

Formula logic also does not replace reasoning actions. If an author wants to
assert that one claim supports another, use a support action. If an author wants
to assert that two claims cannot both be true, use `contradict(...)`. If the
author wants a claim's own internal statement to expose a Boolean or predicate
shape, use `claim(formula=...)`.

## 8. Related Docs

- [Predicate Logic In Gaia Lang](predicate-logic.md) — variables, domains,
  predicates, comparisons, and quantifiers.
- [Knowledge Types and Reasoning Semantics](knowledge-and-reasoning.md) —
  relation between Knowledge, Reasoning, actions, and formula claims.
- [Gaia IR — FormulaGraph validation](../gaia-ir/08-validation.md) — structural
  validation for formula graphs.
- [Gaia IR Lowering](../gaia-ir/07-lowering.md) — backend-facing lowering
  boundary.
- [Diagnostic Probabilities](../bp/diagnostic-probabilities.md) — downstream BP
  scoring of diagnostic conditions.
