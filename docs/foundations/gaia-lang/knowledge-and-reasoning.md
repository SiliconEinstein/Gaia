---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Knowledge Types and Reasoning Semantics

This document bridges the Gaia Lang v0.5 Python DSL to the Gaia IR semantics layer. It covers:

- The **Knowledge** hierarchy authors declare (`Claim`, `Note`, `Question`, plus `ClaimKind` shape discriminators).
- The **GaiaGraph / Reasoning** hierarchy that connects claims (`Directed`, `Relation`, `Decompose`, `Compose`) plus `Scaffold` records for unfinished formalization.
- How Reasoning records lower to IR (strategies, operators, helper claims, `Compose` nodes) and how formula claims lower to IR operators.
- How typed predicate-logic formulas (`Variable`, `Domain`, predicates, connectives, `forall` / `exists`) fit inside `Claim.formula`.
- The legacy v5 **named strategies** (`support`, `deduction`, `abduction`, ...) that remain as a compatibility surface but are no longer the recommended way to author new packages.

Source references: `gaia/engine/lang/runtime/knowledge.py`, `gaia/engine/lang/runtime/action.py`, `gaia/engine/lang/runtime/composition.py`, `gaia/engine/lang/runtime/roles.py`, `gaia/engine/lang/dsl/` (support, relate, decompose, infer_verb, associate_verb, propositional, scaffold), `gaia/engine/lang/formula/`, `gaia/engine/bayes/`, `gaia/engine/lang/compiler/compile.py`, `gaia/engine/ir/knowledge.py`, `gaia/engine/ir/operator.py`, `gaia/engine/ir/strategy.py`, `gaia/engine/ir/formalize.py`, `gaia/engine/bp/potentials.py`.

---

## 1. Two Parallel Hierarchies

In v0.5 the authoring layer has **two parallel class trees**, both registered to the active `CollectedPackage`:

```
Knowledge
├── Claim (carries prior)
│     formula: Formula | None
│     kind: ClaimKind
│       GENERAL
│       PARAMETER
│       QUANTIFIED
├── Note  (no prior)
│     ├── Setting (deprecated)
│     └── Context (deprecated)
└── Question

GaiaGraph
├── Scaffold
│     ├── DependsOn
│     └── CandidateRelation
└── Reasoning
      ├── Directed
      │     ├── Derive / Observe / Compute
      │     └── Infer
      ├── Relation
      │     ├── Equal / Contradict / Exclusive
      │     └── Associate
      ├── Decompose
      └── Compose
```

`Knowledge` and `GaiaGraph` are **siblings**, not parent/child. Knowledge is *what is being claimed*; Reasoning is *how the author is formally connecting claims*; Scaffold is an explicit marker for work that is not formal yet. The legacy `Action` name remains as a compatibility alias for `Reasoning`.

The legacy v5 `Strategy / CompositeStrategy / FormalStrategy / Operator` runtime classes remain available under `gaia.engine.lang.compat`, with deprecated top-level fallback for older code (see [§7 Legacy Compatibility Surface](#7-legacy-compatibility-surface)), but new packages should author exclusively with `Claim` / `Note` / `Question` plus the action verbs.

---

## 2. Knowledge Types

Three Knowledge subclasses exist. Reference IR schema: [Gaia IR — Knowledge](../gaia-ir/02-gaia-ir.md).

### 2.1 Claim

The only Knowledge type carrying a prior probability. Claims are BP variable nodes.

```python
from gaia.engine.lang import claim

orbit = claim("The Earth orbits the Sun.", prior=0.99)
```

Each `Claim` has a **shape discriminator** `kind: ClaimKind` and an optional structured `formula` payload:

| `ClaimKind` value | Meaning | Typical author surface |
|---|---|---|
| `GENERAL` | default; opaque content, formula optional | bare `claim(...)` |
| `PARAMETER` | asserts a `Variable` takes a specific value | `parameter(var, value, ...)` sugar |
| `QUANTIFIED` | top-level `Forall` / `Exists` in `formula` | `claim(formula=Forall(...))` |

`ClaimKind` is **not** a role label (hypothesis / prediction / observation-as-evidence) — those live on action graph nodes (see `roles_for_claim`). It is a structural shape so the compiler can lower the formula payload appropriately. See [§5 Formula Claims](#5-formula-claims), [Formula Logic In Gaia Lang](formula-logic.md), and [Predicate Logic In Gaia Lang](predicate-logic.md).

A `Claim` is **closed** if `parameters=[]` and **universal** if quantified `Variables` appear. Opaque universal prose can record `parameters=[...]`; executable finite-domain quantification should use `claim(formula=Forall(...))` / `claim(formula=Exists(...))`, which the compiler lowers as described in [§5 Formula Claims](#5-formula-claims).

### 2.2 Note

Background context — not a probabilistic proposition.

```python
from gaia.engine.lang import note

binding = note("x = YBCO")
```

- Does not participate in BP.
- May be passed via the `background=` parameter on any action.
- May appear in `metadata.refs` for weak association.
- Cannot appear as the conclusion of any action.

`Setting` and `Context` are deprecated v5 aliases of `Note` and remain only for compatibility (the metadata still records `legacy_kind` for round-trip).

### 2.3 Question

Open research inquiry documenting what the package investigates.

```python
from gaia.engine.lang import question

open_problem = question("What is the maximum Tc in hydrogen-rich superconductors?")
```

No prior, no BP participation; same positional constraints as `Note`.

---

## 3. Action Types

Actions are author-facing verbs that connect claims. Every action is dataclass-style: it auto-registers to the current package on construction, carries a `label` (which becomes a QID at compile time), a `rationale`, optional `background` notes, and an internal `warrants: list[Claim]` of helper claims that reviewers see. Source: `gaia/engine/lang/runtime/action.py`, `gaia/engine/lang/dsl/`.

### 3.1 Support — directional reasoning

`Support` actions establish a `given → conclusion` direction. They all share the same shape (`given: tuple[Claim, ...]`, `conclusion: Claim`) and lower to the same operator skeleton (conjunction over `given` + directed `implication` to `conclusion`); the subclass choice records *what kind of step* the author took, not a different factor type. Each Support action emits an `implication_warrant` helper claim that reviewers gate.

| Verb | Subclass | Intended use |
|---|---|---|
| `derive(c, given=..., rationale=...)` | `Derive` | Logical derivation from accepted premises |
| `observe(c, given=..., rationale=...)` | `Observe` | Empirical observation. `given=()` is allowed and still produces a reviewable warrant; Python runtime records the action on `Claim.from_actions`, and compiled IR records the review metadata under `metadata["supported_by"]` |
| `compute(C, fn=..., given=..., rationale=...)` or `@compute` | `Compute` | Deterministic code execution; `code_hash` records the function source SHA-256 |

Support actions return the **conclusion** Claim. Authors typically chain calls by name:

```python
from gaia.engine.lang import claim, derive, observe

evidence = claim("Stellar parallax is observed.")
heliocentric = claim("The heliocentric model is correct.")
observe(evidence, rationale="Parallax measurement campaign 1838.")
derive(heliocentric, given=evidence, rationale="Parallax confirms orbital motion.")
```

### 3.2 Probabilistic reasoning — soft probabilistic constraint

Probabilistic reasoning verbs carry author-specified conditional probabilities and lower to probabilistic factors. They emit warrant metadata/helper claims that reviewers gate. `infer(...)` is a `Directed` reasoning record and returns the evidence claim; `associate(...)` is a `Relation` reasoning record and returns its association helper because the relation itself is the authored semantic object (see [§4.3 Action Label References](#43-action-label-references)).

#### `infer(evidence, *, hypothesis, given=(), p_e_given_h, p_e_given_not_h=0.5, ...)`

Bayesian update: given a hypothesis Claim `H`, evidence Claim `E`, and explicit `P(E|H) / P(E|¬H)`, the action commits the author to a 2×2 (or 2^(k+1) when `given` adds `k` gating premises) CPT.

- Without `given`: factor is `H → E`, CPT = `[P(E|¬H), P(E|H)]`.
- With `given=G`: factor uses premises `[H, *G]`. When any of `G` is false, the CPT entry collapses to `0.5` (the soft-implication baseline) — the relation becomes neutral when its enabling preconditions are not in force. This is the *infer-with-given gating* contract introduced in v0.5.
- `p_e_given_h` and `p_e_given_not_h` may be a literal float **or** a Claim whose first numeric `parameter("value", ...)` is read at compile time.

Returns the evidence Claim. The author should prefer `bayes.model(...) + bayes.likelihood(...)` (see [§6 Bayes Module](#6-bayes-module)) when the probability is an instance of a predictive distribution.

#### `associate(a, b, *, p_a_given_b, p_b_given_a, pattern=None, ...)`

Symmetric pairwise potential between two Claims. At least one independent marginal prior declared on `a` / `b`, or supplied by the package priors layer, must resolve so the joint table is well-defined. `associate(...)` itself records only the two conditional constraints; model-derived marginals belong in `gaia.engine.bayes`. Returns the association warrant helper Claim.

### 3.3 Relation reasoning — hard constraint between Claims

Relation reasoning records assert that the truth values of the named Claims jointly satisfy a deterministic relation. They lower to IR operators with the truth tables in [§8 Operator Truth Tables](#8-operator-truth-tables) and emit a relation-result helper Claim that the reviewer gates.

| Verb | Subclass | Lowering | Returned helper |
|---|---|---|---|
| `equal(a, b, ...)` | `Equal` | `equivalence([a, b], helper)` | `same_truth(a, b)` |
| `contradict(a, b, ...)` | `Contradict` | `contradiction([a, b], helper)` | `not_both_true(a, b)` |
| `exclusive(a, b, ...)` | `Exclusive` | `complement([a, b], helper)` | XOR helper |
| `decompose(whole, parts=..., formula=...)` | `Decompose` | formula lowering of `parts` + `equivalence(whole, formula_helper)` | `whole == formula(parts)` |

`decompose` is a reasoning verb, but not a relation. It takes a `Formula`
payload and the compiler validates that the formula's `ClaimAtom` set exactly
matches `parts`, that `whole` does not appear in the formula, and that no
decomposition cycle exists. Source: `gaia/engine/lang/dsl/decompose.py`.

### 3.4 Scaffold — authoring metadata only

Scaffold actions exist purely as authoring breadcrumbs and **do not enter IR or BP**. They are not reviewable warrants. Currently:

- `depends_on(conclusion, given=...)` (`DependsOn`) — marks unformalized dependencies that the author intends to formalize later.
- `candidate_relation(claims=[...], pattern=...)` (`CandidateRelation`) — records a hypothesized relation with `pattern=None`, `"equal"`, `"contradict"`, or `"exclusive"` before the author is ready to formalize it.
- `materialize(scaffold, by=...)` — records that a scaffold has been formalized by one or more formal graph records.

Scaffold actions compile only into `.gaia/formalization_manifest.json`. They are
**not addressable** via `[@label]` references because they leave no IR target.

### 3.5 Compose — action-level composition

`@compose(name=..., version=..., warrants=None, ...)` decorates a Python function as a named action workflow. Inside the function the author calls other action verbs; calling the decorated function:

1. Captures every action emitted inside the call into a `Compose` runtime object.
2. Records `inputs` (Knowledge values passed as args, plus claims captured from background and child actions), `actions` (the ordered list of children, by reference or by id), and `conclusion` (the function's return value, which **must** be a `Claim`).
3. Emits a single IR `Compose` node with deterministic `structure_hash` over the tuple of input QIDs, action QIDs, conclusion QID, warrant QIDs, and background QIDs.

`Compose` is the **only** Action subclass that survives into the IR `LocalCanonicalGraph` as a first-class node (`composes: list[Compose]`). All other Actions are projected onto strategies, operators, and helper claims with reverse `action_label` metadata. Source: `gaia/engine/lang/runtime/composition.py`, `gaia/engine/ir/compose.py`.

---

## 4. Action Lowering

The compiler (`gaia/engine/lang/compiler/compile.py`) walks the package's registered actions in declaration order and projects each one onto IR objects. Three things happen for every action:

1. **Action QID assigned.** `_action_label(action, pkg, action_index)` returns `{namespace}:{package}::{label or _anon_action_NNN}`.
2. **Lowered target produced.** Depending on the action subclass (table below), one or more IR objects are created.
3. **Reverse linkage attached.** The action QID is written to the lowered objects' `metadata["action_label"]` and recorded in two tables on the `CompiledPackage`:
   - `action_label_map: dict[str, str]` — action QID → primary IR target QID
   - `target_action_labels_by_id: dict[str, str]` — IR target QID → action QID

### 4.1 Lowering Map

| Action subclass | IR target | Helper claim emitted | Primary target for label resolution |
|---|---|---|---|
| `Derive / Observe / Compute` | `FormalStrategy` (conjunction + directed implication) | `implication_warrant` (review=true) | Strategy ID → warrant helper Claim QID (via `metadata['warrants']`) |
| `Infer` | `Strategy(type=infer)` with CPT | warrant helper Claim (review=true) | Strategy ID → warrant helper Claim QID |
| `Associate` | `Strategy(type=associate)` with pairwise CPT | association helper Claim (review=true) | Strategy ID → association helper Claim QID |
| `Equal` | `Operator(operator=equivalence)` | `equivalence_result` helper (review=true) | Operator ID → helper Claim QID |
| `Contradict` | `Operator(operator=contradiction)` | `contradiction_result` helper (review=true) | Operator ID → helper Claim QID |
| `Exclusive` | `Operator(operator=complement)` | `complement_result` helper (review=true) | Operator ID → helper Claim QID |
| `Decompose` | formula operators over `parts` + `Operator(operator=equivalence, [whole, formula_helper])` | formula-derived helpers + decomposition helper | Operator ID → decomposition helper Claim QID |
| `Compose` | `gaia.engine.ir.Compose` first-class node | (none directly) | `Compose` node QID |
| `DependsOn` | (not lowered) | (none) | not addressable |
| `CandidateRelation` | (not lowered) | (none) | not addressable |

**Note:** `action_label_map` stores Strategy/Operator IDs (e.g., `lcs_*`, `lco_*`), not Knowledge QIDs directly. When resolving action label references in text, the compiler looks up the Strategy/Operator's `metadata['warrants']` to find the warrant helper Knowledge node(s) for provenance attribution. Exception: `Observe` actions with no premises (`given=()`) map directly to the conclusion Claim QID because they represent grounding observations with no inferential warrant.

### 4.2 Helper Claim Visibility

Most action helpers carry `metadata["review"] = true` and `metadata["helper_kind"]` indicating the lowering origin (`implication_warrant`, `equivalence_result`, `association`, ...). Reviewers see them in the review manifest. They carry no independent prior — their distribution is fully determined by the IR operator they back, except for `infer` / `associate` warrants which encode the author's CPT.

Structural-expression helpers from the deprecated function-call compatibility helpers `not_(A)`, `and_(A, B)`, and `or_(A, B)` use `metadata["review"] = false` and the kinds `negation_result / conjunction_result / disjunction_result`; they are non-reviewable scaffolding for propositional algebra and are detected by `gaia.engine.ir.knowledge.is_structural_expression_helper`.

The modern `Claim` dunder shortcuts `~A`, `A & B`, and `A | B` no longer create helper `Claim` objects. They return Formula AST nodes (`Lnot`, `Land`, `Lor`) that become graph structure only when attached to an authored claim with `claim(..., formula=...)`.

The IR-side public/private boundary for these helpers — including which helper Claims may be referenced from outside their FormalStrategy and which must stay encapsulated — is defined in [gaia-ir/04-helper-claims.md](../gaia-ir/04-helper-claims.md). Action lowering follows that boundary: the warrant helper for a `Derive` / `Observe` / `Compute` / `Infer` / `Associate` is a public Claim (reviewable, addressable via `[@label]`); the intermediate `conjunction_result` of a multi-premise `Derive` lives inside the FormalStrategy's `formal_expr` as a private node and is not addressable.

### 4.3 Action Label References

Author-side `[@label]` and `@label` references in claim content, action `rationale`, and notes resolve through a single `label_to_id` table built from:

- every Knowledge `label` (claims, notes, questions, helper claims), and
- every Action `label` registered on the package (resolved to the action's primary target QID per [§4.1](#41-lowering-map)).

A label collision between a Claim and an Action in the same package is a compile error (`ambiguous reference key`). `DependsOn` labels are intentionally not addressable. Cross-package action references follow the same rules as cross-package Claim references once the registry supports them.

Reference: `docs/specs/2026-05-10-action-label-references-design.md`, issue #539.

### 4.4 Compiler extension registry

Action lowering is dispatched through a small registry in
`gaia/engine/lang/compiler/extensions.py`. Peer engine modules, such as
`gaia.engine.bayes`, register lowerers by stable name:

- `register_action_lowerer(name, *, handles, lower)` — add or replace a lowerer
  selected by a predicate over runtime `Action` objects.
- `registered_action_lowerers()` — return the current registry snapshot.

This is an engine-extension hook, not a package-author DSL surface. The
generated compiler reference currently renders `gaia.engine.lang.compiler`, not
the private `extensions` submodule, so the source docstrings remain the
authority for this hook.

---

## 5. Formula Claims

`Claim.formula` carries an optional `Formula` AST that the compiler lowers to IR operators alongside the claim. The formula vocabulary lives in `gaia/engine/lang/formula/` and is exported from `gaia.engine.lang`:

- **Terms.** `Variable`, `Constant`, `FunctionApp`, `ClaimAtom` (lifts a Claim into the formula universe).
- **Predicates.** `Equals`, `NotEquals`, `Greater / GreaterEqual / Less / LessEqual`, `UserPredicate`.
- **Connectives.** `Land`, `Lor`, `Lnot`, `Implies`, `Iff`.
- **Quantifiers.** `Forall(var, body)`, `Exists(var, body)`.
- **Domains.** `Bool`, `Nat`, `Real`, `Probability` (in `gaia.engine.lang.formula.primitives`).

For a reader-facing explanation of where formula-bearing claims sit in the
authoring/compile/review stack, see [Formula Logic In Gaia Lang](formula-logic.md).
For the term-level predicate model, including the difference between opaque
`parameters=[...]` and executable `claim(formula=...)`, see
[Predicate Logic In Gaia Lang](predicate-logic.md).

The compiler handles formula claims via `gaia/engine/lang/compiler/lower_formula.py` after the action pass. It (a) emits IR operators for each connective node (`conjunction / disjunction / negation / implication / equivalence`), (b) records variable bindings on the source Claim's `metadata.formula_bindings`, (c) generates intermediate helper Claims for sub-expressions.

As authoring sugar, propositional connectives accept raw `Claim` operands and coerce them to `ClaimAtom(...)`; explicit `ClaimAtom` remains the canonical bridge in the AST. Thus `claim("A and B.", formula=a & b)`, `claim("A and B.", formula=land(a, b))`, and `claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))` lower to the same connective operator shape.

One sugar helper in `gaia/engine/lang/dsl/sugar.py` maps directly onto a
non-default `ClaimKind` value:

| Sugar | Produces | `ClaimKind` |
|---|---|---|
| `parameter(var, value, prior=...)` | `Equals(var, Constant(value))` | `PARAMETER` |

Structured observed values are authored as formula claims and then marked with
the `observe(...)` action; observation is an action/role, not a `ClaimKind`.
`parameter(...)` and observed formula claims participate in the lifted Bayes
pipeline (see [§6](#6-bayes-module)). Causal mechanism authoring is intentionally
not represented as a marker-only `ClaimKind` or formula predicate; until a
first-class causal mechanism surface lands, write causal statements as ordinary
claims and connect support through reasoning actions.

Schema reference: `docs/specs/2026-05-04-claim-formula-schema-design.md`.

---

## 6. Bayes Module

`gaia.engine.bayes` provides the lifted authoring surface for model-data likelihood updates:

- **Distribution literals.** `bayes.Normal(mu=..., sigma=...)`, `bayes.Binomial(n=..., p=...)`, etc., backed by `scipy.stats`. They are typed values, not Knowledge nodes.
- **`bayes.model(hypothesis, observable=..., distribution=...)`.** Returns a predictive-model helper Claim backed by a `PredictiveModel(BayesInference)` record that ties one hypothesis Claim to one predictive distribution over an observable Variable.
- **`bayes.data(observable, value=..., error=...)`.** Returns an observed formula Claim consumable by `bayes.likelihood(...)`; scalar `error` is stored as zero-mean Normal additive noise.
- **`bayes.likelihood(data, model=..., against=[...], exclusivity=...)`.** Returns a model-preference helper Claim backed by a `Likelihood(BayesInference)` record. Lowers to `infer` strategies plus rigid relation operators expressing the chosen exclusivity contract (e.g., `exhaustive_pairwise_complement`).

`bayes.model / bayes.likelihood` helper records go through the standard action lowering pipeline ([§4](#4-action-lowering)); they share the `action_label_map` table and emit helper Claims that the reviewer sees. See [bayes.md](bayes.md) for the executable Mendel example, the full distribution list, and `gaia build check` diagnostics.

Spec references: `docs/specs/2026-05-04-bayes-module-design.md` and `docs/specs/2026-05-05-bayes-actions-design.md`.

---

## 7. Legacy Compatibility Surface

The v5 strategy DSL remains available for backward compatibility under `gaia.engine.lang.compat`. **New v0.5 packages should not use it.** Deprecated top-level fallback imports and legacy verb calls emit a `DeprecationWarning`; the compatibility surface is scheduled for removal once existing packages have migrated.

| Legacy verb | v0.5 replacement |
|---|---|
| `support([P], C, prior=...)` | `derive(C, given=[P])` (deterministic) or `infer(P, hypothesis=C, p_e_given_h=..., p_e_given_not_h=...)` (probabilistic — `P` is the evidence we observe, `C` is the hypothesis whose belief we want to update). For exclusive model comparison, prefer `bayes.likelihood(...)`. |
| `deduction([P], C)` | `derive(C, given=[P])` |
| `infer([premises], conclusion, ...)` | `infer(evidence, hypothesis=..., given=..., p_e_given_h=..., p_e_given_not_h=...)` |
| `compare(pred_h, pred_alt, observation, ...)` | author the equivalences and implication explicitly, or use `bayes.likelihood(...)` |
| `abduction(...)` | author observation + alternative + comparison explicitly |
| `induction(s1, s2, law, ...)` | declare each support step with `derive` / `observe` and let factor-graph topology accumulate evidence |
| `analogy / extrapolation / elimination / case_analysis / mathematical_induction` | author the deterministic operator skeleton with `derive` + relation verbs |
| `noisy_and(...)` | delegates to legacy `support()`; use `derive(...)` for deterministic reasoning or `infer(...)` / `bayes.likelihood(...)` for probabilistic evidence links |
| `contradiction(a, b, ...)` | `contradict(a, b, ...)` |
| `equivalence(a, b, ...)` | `equal(a, b, ...)` |
| `complement(a, b, ...)` | `exclusive(a, b, ...)` |
| `disjunction(*claims, ...)` | author with `lor(...)` formula or explicit `Operator(disjunction, ...)` |

When legacy named-strategy verbs are used, the compiler still routes them through `formalize_named_strategy()` (`gaia/engine/ir/formalize.py`), which expands them to a `FormalStrategy` containing helper claims plus a deterministic operator skeleton (conjunction + directed implication, optionally with extra equivalence / disjunction operators). The expansion preserves the behavior documented in the v5 reference; consult git history or `gaia/engine/ir/formalize.py` for the per-strategy templates.

Legacy `Strategy / CompositeStrategy / FormalStrategy / Operator` objects also remain importable from `gaia.engine.lang.compat` for type annotations and for code that constructs IR-shaped objects directly. Direct `gaia.engine.lang` access is only a deprecated fallback for older packages.

---

## 8. Operator Truth Tables

Operators encode **deterministic logical constraints**. Each operator type has a fully determined potential matrix — no free parameters. Reference: [Gaia IR — Operators](../gaia-ir/02-gaia-ir.md), `gaia/engine/bp/potentials.py`.

### 8.1 Arity Rules

| Operator | `variables` | `conclusion` |
|----------|-------------|--------------|
| `implication` | exactly 1 (antecedent A) | consequent B |
| `equivalence` | exactly 2 (A, B) | helper claim |
| `contradiction` | exactly 2 (A, B) | helper claim |
| `complement` | exactly 2 (A, B) | helper claim |
| `conjunction` | >= 2 (A1, ..., Ak) | result M |
| `disjunction` | >= 2 (A1, ..., Ak) | result D |

The `conclusion` never appears in `variables` — inputs and output are strictly separated.

### 8.2 Truth Tables

All potentials use Cromwell softening: logical "true" maps to `1 - eps`, logical "false" maps to `eps`, where `eps = CROMWELL_EPS = 1e-3`.

**Implication** — `implication_potential(A, B)`: forbid A=1, B=0.

| A | B | psi |
|---|---|-----|
| 0 | 0 | 1 - eps |
| 0 | 1 | 1 - eps |
| 1 | 0 | eps |
| 1 | 1 | 1 - eps |

**Conjunction** — `conjunction_potential(inputs, M)`: M = AND(inputs).

| all inputs = 1? | M | psi |
|-----------------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Disjunction** — `disjunction_potential(inputs, D)`: D = OR(inputs).

| any input = 1? | D | psi |
|-----------------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Equivalence** — `equivalence_potential(A, B, H)`: H = (A == B).

| A == B? | H | psi |
|---------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

**Contradiction** — `contradiction_potential(A, B, H)`: H = NOT(A AND B).

| A=1 and B=1? | H | psi |
|---------------|---|-----|
| yes | 0 | 1 - eps |
| yes | 1 | eps |
| no | 0 | eps |
| no | 1 | 1 - eps |

**Complement** — `complement_potential(A, B, H)`: H = (A XOR B).

| A != B? | H | psi |
|---------|---|-----|
| yes | 1 | 1 - eps |
| yes | 0 | eps |
| no | 1 | eps |
| no | 0 | 1 - eps |

### 8.3 Helper Claims

Operators that emit a relation-result conclusion (`equivalence`, `contradiction`, `complement`, `disjunction`) produce a **helper Claim** — an ordinary Claim node with metadata marking it as structural. Helper Claims carry no independent prior; their distribution is fully determined by the operator's truth table. Reference: [Helper Claims](../gaia-ir/04-helper-claims.md).

---

## 9. DSL → IR Mapping Summary

| Authoring object | IR object | Key transformation |
|---|---|---|
| `Claim` (no formula) | `Knowledge(type=claim)` | QID assigned, `content_hash = SHA-256(type \| format \| content \| sorted(parameters))` |
| `Claim` (with formula) | `Knowledge(type=claim)` + formula-derived `Operator`s + helper `Knowledge`s | formula lowered via `lower_claim_formula()`; bindings stored on source claim metadata |
| `Note` / `Question` | `Knowledge(type=note / question)` | QID assigned; no prior, no operator participation |
| `Support` action (`Derive / Observe / Compute`) | `FormalStrategy` (conjunction + implication) + warrant helper `Knowledge` | action QID linked via `metadata["action_label"]`; warrant helper has `review=true` |
| `Infer` / `Associate` action | `Strategy` with explicit CPT + warrant helper `Knowledge` | warrant helper is the primary label resolution target |
| `Equal` / `Contradict` / `Exclusive` action | `Operator` + helper `Knowledge` | top-level operator gets `lco_*` ID; helper is reviewable |
| `Decompose` action | formula `Operator`s over `parts` + `Operator(equivalence, [whole, formula_helper])` | enforces atomic-parts match and acyclicity |
| `@compose`-decorated function | `gaia.engine.ir.Compose` first-class IR node | structure-hashed over inputs, child actions, conclusion, warrants |
| `DependsOn` action | (not lowered) | authoring metadata only |

Identity assignment:

- **Knowledge IDs.** Local declarations get QIDs from the package's namespace and name. Anonymous nodes get auto-generated labels (`_anon_001`, `_anon_002`, ...).
- **Action IDs.** Same QID space; anonymous actions get `_anon_action_001`, etc.
- **Strategy IDs.** Deterministically computed as `lcs_{SHA-256(scope | type | sorted(premises) | conclusion | structure_hash)[:16]}`.
- **Operator IDs.** Top-level operators get `lco_{SHA-256(operator | sorted(var_ids) | conclusion_id)[:16]}`.
- **Compose IDs.** `lcm_{structure_hash}` over the canonicalized payload.

Reference: [Identity And Hashing](../gaia-ir/03-identity-and-hashing.md), [Lowering](../gaia-ir/07-lowering.md).

---

## 10. Cromwell's Rule

All probabilities in Gaia IR are clamped to `[eps, 1 - eps]` where `CROMWELL_EPS = 1e-3` (defined in `gaia/engine/ir/parameterization.py` and `gaia/engine/bp/factor_graph.py`). This applies to:

- `PriorRecord.value` (claim priors)
- `Strategy.conditional_probabilities` (CPT entries on `infer` / `noisy_and` strategies)
- `Strategy.p_a_given_b` / `Strategy.p_b_given_a` (conditional entries on `associate` strategies)
- All factor potential values (truth-table entries use `1 - eps` instead of 1, `eps` instead of 0)
- Author-supplied `p_e_given_h` / `p_e_given_not_h` on `infer`

The rule ensures that no assignment is assigned zero probability, preserving BP's ability to revise any belief given sufficient evidence. Reference: [Parameterization](../gaia-ir/06-parameterization.md).
