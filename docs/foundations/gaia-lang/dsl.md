---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Gaia Lang DSL Reference

## Overview

Gaia Lang is a Python 3.12+ internal DSL for declarative knowledge authoring. Package authors use it to declare propositions, logical constraints, and reasoning actions. Every declaration auto-registers to a `CollectedPackage` via Python `contextvars` -- writing declarations at module scope is sufficient.

For the conceptual model behind the surface (Knowledge / Action hierarchy, formula claims, action lowering, operator semantics) see [knowledge-and-reasoning.md](knowledge-and-reasoning.md). For the typed predicate-logic model (`Variable`, `Domain`, formula AST, `forall` / `exists`, and grounding boundaries), see [predicate-logic.md](predicate-logic.md). This file is the per-name reference.

```python
from gaia.engine.lang import (
    # Knowledge
    claim, note, question, Domain,
    # Formula primitives (terms, predicates, connectives, quantifiers)
    Variable, Nat, Real, Probability, Bool,
    ClaimAtom, Constant, FunctionSymbol, FunctionApp, PredicateSymbol, UserPredicate,
    Equals, NotEquals, Greater, GreaterEqual, Less, LessEqual, Causes,
    land, lor, lnot, implies, iff, forall, exists,
    # Structured-formula sugar (parameter / causal claims)
    parameter, causal,
    # Action verbs (recommended v0.5 surface)
    observe, derive, compute, infer, associate,
    equal, contradict, exclusive, decompose,
    depends_on, candidate_relation, tension,  # scaffold-only, not addressable via @label
    compose,               # @compose decorator
    # Lifted Bayes module (lazy-loaded)
    bayes,
    # Compatibility aliases and legacy/experimental APIs
    setting, context,
    contradiction, equivalence, complement, disjunction,   # v5 compatibility
    support, compare, deduction, abduction, induction,     # legacy strategies
    analogy, extrapolation, elimination, case_analysis,
    mathematical_induction, composite, fills,
    # noisy_and,  # deprecated; lowers to legacy support
)
```

The runtime dataclasses `Knowledge`, `Claim`, `Note`, `Question`, `Action`, `Compose`, `Strategy`, `Step`, `Operator`, and the role-projection helpers `roles_for_claim` / `roles_for_package` are also exported for type annotations.

---

## Knowledge Declarations

Knowledge functions return `Knowledge` dataclasses. `claim(...)` returns `Claim`; `note(...)` returns `Note`; `question(...)` returns `Question`. The three types correspond to the Gaia IR taxonomy in [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md).

### `claim()`

```python
def claim(
    content: str,
    proposition: BoolExpr | None = None,
    *,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    formula: Any = None,
    kind: ClaimKind = ClaimKind.GENERAL,
    tolerance: float | None = None,
    **metadata,
) -> Claim
```

The only knowledge type carrying probability in BP. `background` attaches notes without making them logical premises. `parameters` records lightweight parameter metadata on an opaque prose claim; use `formula=forall(...)` / `formula=exists(...)` when Gaia should actually inspect and lower a quantified predicate formula. `proposition` is the continuous-predicate shorthand produced by comparing a `Distribution` to a value. Inline `prior=` is a compatibility shortcut routed through `register_prior(..., source_id="claim_inline")`; packages that need provenance-rich priors should prefer `priors.py`. `provenance` records source attribution as `[{"package_id": ..., "version": ...}]`. Use action verbs (`observe`, `derive`, `compute`, `infer`) and relation verbs (`equal`, `contradict`, `exclusive`) to connect claims in new v0.5 packages.

```python
orbit = claim("The Earth orbits the Sun.")

# Connect claims with the recommended action surface
evidence = claim("Stellar parallax is observed.")
heliocentric = claim("The heliocentric model is correct.")
derive(heliocentric, given=evidence, rationale="Parallax confirms orbital motion.")

# Lightweight universal prose claim (metadata only; not parsed as a formula)
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

## Structured Formula Claim Sugar

For the full typed model behind these helpers, including `Variable`, `Domain`,
`PredicateSymbol`, `UserPredicate`, `ClaimAtom`, `forall`, `exists`, and the
compiler lowering rules, see [predicate-logic.md](predicate-logic.md).

The structured formula helpers return ordinary `Claim` objects with
`Claim.formula` and `Claim.kind` set. They do not introduce new IR knowledge
types; the compiler records bindings and formula descriptors on today's claim
nodes.

### `parameter(variable, value, *, describe=None, prior=None, label=None, ...)`

Creates a `ClaimKind.PARAMETER` claim whose formula is
`Equals(variable, Constant(value, variable.domain))`. The variable must use a
built-in primitive domain (`Nat`, `Real`, `Probability`, or `Bool`).

```python
p = Variable(symbol="p", domain=Probability)
h = parameter(
    p,
    0.75,
    describe="Mendelian 3:1 segregation fixes P(dominant) at 0.75.",
    prior=0.5,
)
```

The compiled source claim gets an IR parameter and `metadata.formula_bindings`
for `p = 0.75`.

### Structured measured values

Observation is represented by `observe(...)`, not by a claim kind. For measured
values, write an ordinary formula claim and then mark it with a zero-premise
`observe(...)`.

```python
n = Variable(symbol="n", domain=Nat)
k = Variable(symbol="k", domain=Nat)
d = observe(
    claim(
        "Observed 295 dominant phenotypes out of 395 F2 plants.",
        formula=land(equals(n, Constant(395, Nat)), equals(k, Constant(295, Nat))),
    ),
    rationale="Extracted from the reported count table.",
)
```

The primitive bindings are still copied back to the source claim. A
zero-premise observation pins the claim to `1 - CROMWELL_EPS`.

### `causal(cause, effect, *, describe=None, prior=None, label=None, ...)`

Creates a `ClaimKind.CAUSAL` claim with top-level `Causes(cause, effect)`.
In v0.5 this is a structured marker only: it records cause/effect descriptors
on the source claim and does not imply Pearl-style intervention semantics.

```python
co2 = Variable(symbol="co2", domain=Real)
temp = Variable(symbol="temp", domain=Real)
c = causal(co2, temp, describe="Rising CO2 causes warming.", prior=0.9)
```

### `gaia.engine.lang.bayes`

Use `gaia.engine.lang.bayes` for structured model-data likelihood updates. It replaces
ad hoc evidence helpers with explicit hypothesis, data, model, and likelihood
atoms:

```python
from gaia.engine.lang import Constant, Nat, Probability, Variable, bayes, claim, equals, observe, parameter

theta = Variable(symbol="theta", domain=Probability)
k = Variable(symbol="k", domain=Nat, value=295)
n = 395

h_3_1 = parameter(theta, 0.75, prior=0.5, label="h_3_1")
h_null = parameter(theta, 0.5, prior=0.5, label="h_null")
data = claim("Observed k = 295 dominant plants.", formula=equals(k, Constant(295, Nat)))
observe(data, rationale="F2 count table reports 295 dominant phenotypes.")
model_3_1 = bayes.model(
    h_3_1,
    observable=k,
    distribution=bayes.Binomial(n=n, p=theta),
)
model_null = bayes.model(
    h_null,
    observable=k,
    distribution=bayes.Binomial(n=n, p=theta),
)
comparison = bayes.likelihood(
    data,
    model=model_3_1,
    against=[model_null],
    exclusivity="exhaustive_pairwise_complement",
)
```

`bayes.likelihood(...)` lowers to existing `infer` strategies plus rigid
relation operators. See [bayes.md](bayes.md) for the executable example,
distribution list, and `gaia build check` diagnostics. There is no public
`observation(...)` helper in v0.5; structured measured values are normal formula
claims marked by the `observe(...)` action.

---

## Recommended Action Verbs

Action verbs are the canonical v0.5 way to turn explicit premises into reviewable warrants.
Support verbs (`observe`, `derive`, `compute`) and `infer(...)` return the produced or affected claim.
`associate(...)` and formal relation verbs return generated reviewable helper claims because the relation itself is the semantic object reviewers inspect.

### `observe(conclusion, *, given=(), background=None, rationale="", label=None)`

Empirical observation. With no `given`, it pins the conclusion to `1 - CROMWELL_EPS` and appends an `Observe` action to `Claim.from_actions`; the compiled IR records the reviewable observation warrant in `metadata["supported_by"]`. With `given`, it lowers as an observation-pattern support edge from the premises to the conclusion and does not assign a prior.

There is a second overload for continuous measurements:

```python
observe(distribution, *, value, error=None, source_refs=None, rationale="", label=None)
```

It produces an observed claim and continuous-likelihood metadata for the distribution diagnostics.

### `derive(conclusion, *, given=(), background=None, rationale="", label=None)`

Deterministic derivation. Use when the conclusion follows from the explicit `given` claims once the rationale is accepted.

### `compute(ClaimType, *, fn=None, given=(), background=None, rationale="", label=None)`

Deterministic computation. Use either `compute(ResultClaim, fn=..., given=...)` or `@compute` with a `Claim` return annotation.

### `infer(evidence, *, hypothesis, given=(), p_e_given_h, p_e_given_not_h=0.5, background=None, rationale="", label=None)`

Low-level probabilistic prediction/evidence link with a hand-written CPT. Prefer
`bayes.model(...)` + `bayes.likelihood(...)` when the probability comes from
a predictive distribution and observed data. Use `infer(...)` when the author is
directly committing to `P(E|H)` and `P(E|not H)`.
Returns the evidence claim. The action still creates an internal likelihood helper as the review target for accepting the probability warrant.

Without `given`, the compiled BP factor is `H -> E` with CPT `[P(E|not H), P(E|H)]`. With `given=G`, the compiled factor uses premises `[H, G]` and CPT `[0.5, 0.5, P(E|not H,G), P(E|H,G)]`, so the relation becomes neutral when `G` is false. `p_e_given_not_h` defaults to `0.5`, the soft-implication baseline.

### `associate(a, b, *, p_a_given_b, p_b_given_a, background=None, rationale="", label=None)`

Symmetric probabilistic association between two claims. Returns a generated association helper claim and lowers to a pairwise potential between `a` and `b`. At least one independent marginal prior for `a` or `b` must resolve from the claim/priors layer. Statistical model-derived marginals should be represented through `gaia.engine.lang.bayes` outputs, not inline `associate(...)` arguments.

### `decompose(whole, *, parts, formula, background=None, rationale="", label=None, metadata=None)`

Declares `whole` as propositionally equivalent to a `Formula` over atomic `parts`. The compiler checks that the formula's `ClaimAtom` set exactly matches `parts`, that `whole` does not appear in the formula, and that no decomposition cycle exists. Returns the `whole` claim. The compiler emits formula/equivalence helper nodes for lowering, but the generated helper claims themselves are not direct review targets; the review manifest gates the decomposition equivalence operator/action. See [decompose action design](../../specs/2026-05-05-decompose-action-design.md).

```python
from gaia.engine.lang import ClaimAtom, claim, decompose, implies, land

A = claim("A")
B = claim("B")
D = claim("D")
C = claim("C")
decompose(
    whole=C,
    parts=(A, B, D),
    formula=land(ClaimAtom(A), implies(ClaimAtom(B), ClaimAtom(D))),
)
```

### `depends_on(conclusion, *, given=..., rationale="", label=None)`

Scaffold-only action marking unformalized dependencies. **Does not enter IR or BP** and is not addressable via `[@label]` references. Use it while drafting a package to record "I know the full formalization will go here; here is what the conclusion depends on."

### `candidate_relation(a, b, *, proposed, background=None, rationale="", label=None)`

Scaffold-only action for a hypothesized relation that is worth recording but not yet ready to enter formal semantics. `proposed` is a short label such as `"equal"`, `"contradict"`, `"exclusive"`, `"associate"`, or `"tension"`. It writes only to `.gaia/formalization_manifest.json`.

### `tension(a, b, *, background=None, rationale="", label=None)`

Thin wrapper for `candidate_relation(a, b, proposed="tension", ...)`.

### `@compose(name, version, background=None, warrants=None, rationale="", label=None)`

Decorates a Python function as a named action workflow. Calling the function returns its normal conclusion claim, while the runtime records a `Compose` DAG containing the child action targets, explicit inputs, background, optional compose-level warrants, and conclusion. Child action warrants stay owned by their child actions; compose-level warrants are only the warrants passed to `@compose(...)`.

---

## Operators

Operators declare deterministic logical constraints between claims. Each function creates an `Operator` (auto-registered) and returns a helper claim usable in further reasoning. For formal definitions and truth tables, see [../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md), Section 2.

### Structured Formula Replacements

Use explicit formula claims for new structural Boolean construction. Referenced
claims must be wrapped in `ClaimAtom`, which lets the compiler use the existing
claim's IR node as the formula operand.

```python
from gaia.engine.lang import ClaimAtom, claim, land, lnot, lor

not_a = claim("not A", formula=lnot(ClaimAtom(a)))
both = claim("A and B", formula=land(ClaimAtom(a), ClaimAtom(b)))
either = claim("A or B", formula=lor(ClaimAtom(a), ClaimAtom(b)))
```

The legacy shortcuts `~a`, `a & b`, `a | b`, `not_(a)`, `and_(a, b, ...)`, and
`or_(a, b, ...)` remain exported for compatibility but emit
`DeprecationWarning`. Python keywords `not`, `and`, and `or` cannot be
overloaded; `Claim.__bool__` raises to prevent accidental Python control-flow
truth tests.

### Propositional Analysis Helpers

`gaia.engine.logic` provides non-persistent analysis helpers over compiled Gaia operator graphs:

- `simplify_proposition(graph, knowledge_id)`
- `to_cnf_proposition(graph, knowledge_id, simplify=False)`
- `to_dnf_proposition(graph, knowledge_id, simplify=False)`
- `to_nnf_proposition(graph, knowledge_id)`
- `are_equivalent(graph, left_knowledge_id, right_knowledge_id)`
- `is_satisfiable(graph, knowledge_id)`

These helpers recursively expand deterministic IR operators into a Boolean backend representation for formula simplification, normal-form conversion, equivalence checks, and satisfiability checks. The backend expression is an analysis artifact only; Gaia IR remains the source of truth.

### Reviewable Relation Verbs

The relation action verbs (`equal`, `contradict`, `exclusive`, `decompose`) belong to the Action surface and are documented above under [Recommended Action Verbs](#recommended-action-verbs). They are listed here only to flag that they compile to the deterministic `equivalence` / `contradiction` / `complement` operators (plus formula operators for `decompose`), not to a new operator type.

### v5 Compatibility Operators

These functions remain for older packages but emit `DeprecationWarning`. New
v0.5 packages should prefer formula claims for direct Boolean construction and
relation verbs (`equal`, `contradict`, `exclusive`) for reviewable semantic
judgments.

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

`prior` is accepted for legacy compatibility, but current BP lowering ignores it
for deduction. Deduction lowers as a hard conditional implication. Review
decides whether the warrant passes publication-quality gates; it does not
assign a numeric confidence to the deduction step, and it does not suppress
`gaia run infer` local preview output.

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

Deprecated v5 CPT form. Use `infer(evidence, hypothesis=..., given=..., p_e_given_h=..., p_e_given_not_h=0.5)` instead.

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

**Automatic inference.** When compiled via `gaia build compile`, module-level variable names in `__all__` become labels:

```python
bg = note("Context.")              # label = "bg"
hypothesis = claim("Hypothesis.")  # label = "hypothesis"
__all__ = ["bg", "hypothesis"]
```

**Manual labels.** Assign directly: `my_claim.label = "explicit_label"`.

**QID generation.** At compile time, labels expand to `{namespace}:{package_name}::{label}`. A claim labeled `hypothesis` in package `galileo` under namespace `github` becomes `github:galileo::hypothesis`. Namespace and package name come from `pyproject.toml`.

---

## Reference Syntax

Claim content and action `rationale` text may contain references using the
unified `@` syntax:

- `[@label]` -- strict reference to a local or imported knowledge node,
  to an action label, or to a citation key in `references.json`. Missing
  key is a compile error.
- `@label` -- opportunistic reference (Pandoc narrative form). Missing key
  is treated as literal text.
- `\@label` -- escape, forces literal.

`label` may be either a Knowledge label (the variable name of a `claim`,
`note`, or `question`, or an explicit `label=`) or an Action label (the
`label=` argument on `derive` / `observe` / `compute` / `infer`
/ `associate` / `equal` / `contradict` / `exclusive` / `decompose` / `@compose`).
Action labels resolve to the action's lowered IR target — a Strategy or
Operator ID, which then resolves to the action's warrant helper Claim for
provenance attribution. Exception: `observe()` with no premises maps directly
to the conclusion Claim. The scaffold-only `depends_on` action is **not
addressable** because it leaves no IR target.

**Semantic distinction:** This provides two ways to reference a conclusion:
- `[@conclusion_label]` references the conclusion Claim itself
- `[@action_label]` references the warrant that supports the conclusion

Example: "See [@derive_b] for the derivation of [@b]" clearly separates
the reasoning from the result.

Compile enforces three invariants: (1) a key cannot exist in both the
label table and `references.json` (collision -> compile error); (2) a
Knowledge label and an Action label cannot share a name within the same
package (collision -> compile error); (3) a single `[...]` group cannot
mix knowledge refs and citations (mixed group -> compile error).

Grammar, resolution rules, and rendering pipeline:
[References & `@` Syntax Unification Design](../../specs/2026-04-09-references-and-at-syntax.md).
Action label resolution contract:
[Action Label References Design](../../specs/2026-05-10-action-label-references-design.md).

---

## Complete Example

A v0.5 package using the recommended action surface (Galileo's tied-balls thought experiment against Aristotelian physics).

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
from gaia.engine.lang import claim, contradict, derive, note

aristotelian = note("In Aristotelian physics, heavier objects fall faster.")

heavy_fast = claim("A heavy ball falls faster than a light ball.", prior=0.9)
light_slow = claim("A light ball falls slower than a heavy ball.", prior=0.9)

tied_heavier = claim("A heavy+light tied system is heavier than the heavy ball alone.")
tied_faster = claim("The tied system falls faster.")
derive(tied_faster, given=[tied_heavier, heavy_fast],
       rationale="Heavier system should fall faster under Aristotle.",
       label="aristotle_predicts_faster")

drag_slower = claim("The light ball drags, so the tied system falls slower.")
derive(drag_slower, given=[light_slow, heavy_fast],
       rationale="Light ball acts as drag.",
       label="aristotle_predicts_slower")

paradox = contradict(tied_faster, drag_slower,
                     rationale="Aristotle predicts both faster AND slower.",
                     label="paradox")

uniform_rate = claim("All bodies fall at the same rate regardless of weight.")
binding = note("Consider any two bodies A, B with different weights.")
prediction = claim("A and B hit the ground simultaneously.")
derive(prediction, given=[uniform_rate, tied_heavier],
       background=[binding],
       rationale="Direct logical consequence of uniform fall.",
       label="uniform_fall_prediction")

__all__ = [
    "aristotelian", "heavy_fast", "light_slow", "tied_heavier",
    "tied_faster", "drag_slower", "paradox", "uniform_rate",
    "binding", "prediction",
]
```

Compile: `gaia build compile path/to/galileo-tied-balls-gaia/`

This produces `.gaia/ir.json` containing the `LocalCanonicalGraph` with all nodes, operators, helper claims, and the four action labels (`aristotle_predicts_faster`, `aristotle_predicts_slower`, `paradox`, `uniform_fall_prediction`) registered under `github:galileo_tied_balls::`. The action labels can be referenced from other claims' content via `[@aristotle_predicts_faster]`, etc.

For the v5 named-strategy example using `support` / `deduction` / `contradiction`, see git history before v0.5 — those verbs still work but emit `DeprecationWarning` and should not be used in new packages.
