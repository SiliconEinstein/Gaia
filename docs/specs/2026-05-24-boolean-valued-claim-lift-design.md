# RFC: Boolean-valued types as claim-equivalent at verb boundaries

**Date**: 2026-05-24
**Status**: Draft
**Builds on**: PR #658 (`feat(lang): coerce Claim to ClaimAtom in connectives; dunder ops return Formula`, 2026-05-17)
**Does not change**: Formula AST purity; Claim/Formula layer separation; existing `claim()` signatures

## 1. Summary

PR #658 deliberately kept Formula a pure read-only AST: `a & b` returns
`Land(...)`, materialization happens only at `claim(formula=...)`. This
RFC extends that design with a single observation:

> Every type Gaia uses to express a Boolean-valued assertion — `Claim`,
> `ClaimAtom`, propositional connectives (`Land`/`Lor`/`Lnot`/`Implies`/
> `Iff`), quantifiers (`Forall`/`Exists`), predicate formulas (`Equals`/
> `Greater`/`UserPredicate`/...), and `BoolExpr` — is **claim-equivalent
> at the verb boundary**. Each maps to a Bernoulli random variable in BP,
> so at the verb layer (`exclusive`, `derive`, `infer`, `register_prior`,
> ...) any Boolean-valued expression can stand where a `Claim` is required.

Implementation is one helper function `_lift_to_claim(value)` invoked at
each Claim-accepting verb's entry. Formula AST stays pure; the lift is
the materialization boundary that PR #658 already located at
`claim(formula=...)`, just applied automatically when the user feeds a
Boolean-valued expression directly to a verb.

## 2. Motivation

### 2.1 The ergonomic gap PR #658 left open

PR #658 introduced `Claim.__and__/__or__/__invert__` returning Formula
nodes. The canonical post-#658 idiom is:

```python
helper = claim("R_i premises hold.", formula=p1 & p2)
exclusive(helper, neg, rationale="...", label="...")
```

But the *natural* idiom users try first is:

```python
exclusive(p1 & p2, neg, rationale="...", label="...")
```

This fails with `AttributeError: 'Land' object has no attribute 'label'`
— a leaky-abstraction error message that doesn't tell the user how to
recover. Users either:

- Fall back to the deprecated `and_(p1, p2)` (defeating the migration)
- Write `claim("desc", formula=p1 & p2)` (correct but verbose; the
  description string is usually pure ceremony for an internal helper)
- Invent miscalibrated workarounds (the BoardgameQA case, §2.2)

### 2.2 Concrete evidence: BoardgameQA benchmark

The BoardgameQA→Gaia skill in `gaia-boardgameqa-benchmark/` translates
defeasible-reasoning items into Gaia knowledge packages. Its §4
"override-gate conjunction" pattern needs sharp Bayesian conjunctions
of rule premises. The skill author *intended* deterministic AND but,
faced with `a & b` returning Formula and `claim(formula=...)` being
verbose, instead used:

```python
helper = claim("R_i premises hold.")
infer(evidence=helper, hypothesis=p1, given=[p2],
      p_e_given_h=0.999, p_e_given_not_h=0.001)
```

This *simulates* sharp conjunction via an `infer` CPT with extreme
likelihood ratios — but the CPT's non-`all-true` cells default to
MaxEnt 0.5. With one premise at CWA (≈0.05), the helper's marginal
lands near 0.525 instead of ≈ p₁·p₂.

Three of ten BoardgameQA validation items lose threshold mapping
because of this:

| Item | Pre-fix | Current skill (`infer(CONJ_HI/LO)`) | One-line skill fix (`and_(p1, p2)`) |
|------|---------|-------------------------------------|------|
| P8   | 0.26    | 0.108 → unknown (gold disproved)    | **0.055 → disproved ✓** |
| P12  | 0.95    | 0.203 → unknown (gold disproved)    | (predicted to flip) |
| P16  | n/a     | 0.841 → unknown (gold proved)       | **0.951 → proved ✓** |

The skill *can* fix itself by switching to `and_(...)` — a path PR #658
deprecated. The right systemic fix is to make `p1 & p2` work at the verb
boundary, so the skill (and any future user hitting the same trap)
doesn't have to fall back to deprecated APIs.

### 2.3 The deeper insight: Curry–Howard at the Claim/Formula boundary

Gaia's two layers already encode a proposition/term distinction:

| Universe | Members | BP semantics |
|---|---|---|
| **Proposition** (Boolean-valued) | `Claim`, `ClaimAtom`, `Land`/`Lor`/`Lnot`/`Implies`/`Iff`, `Forall`/`Exists`, `Equals`/`Greater`/`UserPredicate`/..., `BoolExpr` | Boolean RV (Bernoulli variable in factor graph) |
| **Term** (typed-value) | `Variable`, `Constant`, `FunctionApp`, `Distribution`, ... | Typed value in domain (Nat / Real / Probability / ...) |

A BP factor graph variable is, by definition, a Bernoulli random variable
— its marginal is `P(X = true) ∈ [0, 1]`. So *any expression in the
Proposition universe is a candidate BN node*. The current
`claim(formula=...)` ceremony is a deliberate placement of the
"materialization" boundary, not a fundamental type restriction.

PR #658 already partially acted on this insight: `Claim.__and__` accepts
`Claim | Formula` and coerces Claim operands to `ClaimAtom` inside
`Land(...)`. That coercion is exactly "Claim is Boolean-valued and so is
ClaimAtom, so they're interchangeable in connective slots." This RFC
generalises the same principle from connective slots to verb argument
slots.

### 2.4 What gets fixed beyond `a & b`

A unified Boolean-valued rule covers more than just propositional
conjunctions. Each of these currently requires `claim(...)` wrapping;
under this RFC they all work directly at the verb boundary:

| Today | With this RFC |
|---|---|
| `helper = claim("k > 0.5", proposition=k > 0.5)`; `derive(c, given=[helper])` | `derive(c, given=[k > 0.5])` |
| `helper = claim("x = 5", formula=Equals(x, Constant(5)))`; `infer(evidence=helper, ...)` | `infer(evidence=Equals(x, Constant(5)), ...)` |
| `helper = claim("forall x P", formula=Forall(x, P_atom))`; `exclusive(helper, neg)` | `exclusive(Forall(x, P_atom), neg)` |

The ergonomic payoff scales with how heavily a user touches predicate /
quantifier claims, which is exactly the direction Gaia is moving (per
PR #625, PR #559, etc.).

## 3. Current state (post PR #658)

### 3.1 Operator overloads

Only `Claim` exposes `__and__` / `__or__` / `__invert__` / `__rand__` /
`__ror__` (`runtime/knowledge.py:236-301`). No Formula class (ClaimAtom,
Land, Lor, Lnot) and no Term class (Variable, Constant, Equals, etc.)
overloads these. PR #658 explicitly listed "no `Formula1 & Formula2`
operator-overload" as a non-goal.

Verified empirically:

```
class        __and__   __or__   __invert__
------------ --------  -------  ----------
Claim        yes       yes      yes
ClaimAtom    no        no       no
Land         no        no       no
Lor          no        no       no
Lnot         no        no       no
Equals       no        no       no
Variable     no        no       no
```

`Variable & Variable`, `Land & Land`, `Equals(...) & Equals(...)` all
raise `TypeError: unsupported operand type(s) for &` at Python operator
dispatch. The only way to construct a Formula via operator overload is
through `Claim`.

### 3.2 The `claim()` materialization paths

`gaia/engine/lang/dsl/knowledge.py:110-...` `claim()` has three input
shapes:

- **Prose**: `claim("Heliocentric is correct.", prior=0.8)`
- **Predicate**: `claim("Reaction is fast.", k > 1e-2)` — second arg is `BoolExpr`
- **Formula**: `claim(content, formula=Forall(...))` — via keyword

These are the existing materialization entry points. They will not
change. The RFC adds a *new* materialization entry that fires at verb
boundaries, internally routing through whichever of the three shapes
matches the input type.

### 3.3 Verb consumers

The following verbs (sample) require `Claim` arguments and currently
fail on Formula / BoolExpr:

- `relate.py`: `exclusive`, `contradict`, `equal`
- `support.py`: `derive`, `observe`, `compute`
- `infer_verb.py`: `infer`
- `register_prior.py`: `register_prior`

None auto-lift. The error messages access `.label` or `.qid` directly,
leaking internal attribute names.

## 4. Proposed behaviour

### 4.1 Type-theoretic foundation: `BooleanValued`

Define a runtime-checkable marker for "Boolean-valued type":

```python
# gaia/engine/lang/_boolean_valued.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class BooleanValued(Protocol):
    """Marker: types whose values denote Boolean-valued (T/F) assertions.

    Concrete members:
      - Claim                              (probabilistic Boolean node)
      - ClaimAtom                          (Formula leaf wrapping a Claim)
      - Land / Lor / Lnot / Implies / Iff  (propositional connectives)
      - Forall / Exists                    (quantifiers — body is a Formula)
      - Equals / NotEquals / Greater / GreaterEqual / Less / LessEqual
                                           (term-level predicate Formulas)
      - UserPredicate                      (user-declared predicate Formula)
      - BoolExpr                           (Distribution comparison result)

    Excluded (Term universe):
      - Variable, Constant, FunctionApp    (Term: domain-typed value)
      - Distribution, RandomVariable       (Term: continuous/categorical value)
      - Note, Setting, etc.                (Knowledge subclasses without truth value)
    """
    __gaia_boolean_valued__: bool  # = True
```

Each Claim, ClaimAtom, and Formula class gets `__gaia_boolean_valued__ =
True` as a class attribute. `BoolExpr` gets it too. This marker is a
**zero-cost authoring annotation** — runtime check is one `hasattr`.

A predicate for the lift function:

```python
def is_boolean_valued(obj) -> bool:
    return getattr(obj, "__gaia_boolean_valued__", False)
```

(Pure structural; works on any future class that opts in.)

### 4.2 The lift function: `_lift_to_claim`

```python
# gaia/engine/lang/dsl/_lift.py

from gaia.engine.lang.runtime.knowledge import Claim, claim
from gaia.engine.lang.formula.predicate import ClaimAtom, is_formula
from gaia.engine.lang.bool_expr import BoolExpr
from gaia.engine.lang._boolean_valued import is_boolean_valued

def _lift_to_claim(value, *, verb_name: str, arg_position: str) -> Claim:
    """Lift a Boolean-valued expression to a Claim at verb boundary.

    Claim → return as-is.
    ClaimAtom → unwrap to its underlying Claim (trivial, no helper).
    Formula → materialize via `claim(formula=...)` with synthesized desc.
    BoolExpr → materialize via `claim(proposition=...)` with synthesized desc.
    Otherwise → educational TypeError.
    """
    if isinstance(value, Claim):
        return value
    if isinstance(value, ClaimAtom):
        return value.claim
    if is_formula(value):
        return claim(_synth_description(value), formula=value)
    if isinstance(value, BoolExpr):
        return claim(_synth_description(value), proposition=value)
    raise TypeError(
        f"{verb_name}() received {type(value).__name__} as {arg_position}; "
        f"expected Claim or a Boolean-valued expression "
        f"(Formula, BoolExpr, ClaimAtom). Term-level values "
        f"(Variable, Constant, Distribution) are not directly claim-able; "
        f"wrap them in a predicate first "
        f"(e.g. Equals(x, Constant(5))) or pass an explicit "
        f"claim(content=..., formula=...) helper."
    )
```

### 4.3 Synthesized descriptions

```python
def _synth_description(value) -> str:
    """Best-effort human-readable description from a Boolean-valued expression.

    Falls back to `str(value)` when no special form is recognized; all
    Formula and BoolExpr classes already implement readable `__str__`.
    """
    return str(value)
```

Example outputs (using existing `__str__` impls):

| Input | Description |
|---|---|
| `Land(ClaimAtom(a), ClaimAtom(b))` | `"all_true(a, b)"` |
| `Lor(ClaimAtom(a), Lnot(ClaimAtom(b)))` | `"any_true(a, not(b))"` |
| `Equals(x, Constant(5))` | `"x = 5"` |
| `Forall(x, P_atom)` | `"forall x. P"` |
| `k > 0.5` (BoolExpr) | `"k > 0.5"` |

These descriptions are auditable in `TRANSLATION_NOTES.md` / package
exports. Users wanting prose descriptions write `claim(content="...",
formula=...)` explicitly — that path is unchanged.

### 4.4 Memoization (per package)

Two evaluations of the same expression should produce the same helper
Claim, not two distinct ones:

```python
exclusive(a & b, neg_1)   # creates helper_1
exclusive(a & b, neg_2)   # should reuse helper_1, not create helper_2
```

Inside `_lift_to_claim`, key the helper by structural hash of the value
(Formula's `__hash__` is stable since PR #623). The cache is scoped to
the enclosing `CollectedPackage` context; cross-package reuse is not
attempted.

### 4.5 Verb-side integration

Every Claim-accepting verb gets a single line at entry:

```python
# Before
def exclusive(a: Claim, b: Claim, *, rationale: str, label: str) -> Operator:
    ...existing logic using a, b...

# After
def exclusive(a, b, *, rationale: str, label: str) -> Operator:
    a = _lift_to_claim(a, verb_name="exclusive", arg_position="first argument")
    b = _lift_to_claim(b, verb_name="exclusive", arg_position="second argument")
    ...existing logic unchanged from here...
```

Type annotations relax from `Claim` to `Claim | BooleanValued`.

Verbs to update (initial scope):
- `dsl/relate.py`: `exclusive`, `contradict`, `equal`
- `dsl/support.py`: `derive`, `observe`, `compute`
- `dsl/infer_verb.py`: `infer` (evidence, hypothesis, every entry in given)
- `dsl/register_prior.py`: `register_prior` (target claim)

`gaia.engine.lang.compat.{and_, or_, not_}` already produce Claim helpers
and need no change.

## 5. Detailed cases

For each Boolean-valued shape, show input → behaviour.

### 5.1 Claim itself

```python
exclusive(c1, c2, ...)              # _lift returns c1, c2 as-is; no helper
```

### 5.2 ClaimAtom

```python
exclusive(ClaimAtom(c1), c2, ...)   # _lift unwraps ClaimAtom → c1; no helper
```

The trivial unwrap path. No new node in BN.

### 5.3 Propositional connectives over Claims

```python
exclusive(a & b, neg, ...)
# _lift sees Land(ClaimAtom(a), ClaimAtom(b))
# → claim("all_true(a, b)", formula=Land(...))
# → helper Claim with formula attached
# → exclusive(helper, neg, ...) proceeds with helper as a Claim
```

This is the BoardgameQA case. One helper Claim per unique conjunction
within a package (per §4.4 memoization).

### 5.4 Nested propositional

```python
exclusive((a & b) | ~c, neg, ...)
# _lift sees Lor(Land(ClaimAtom(a), ClaimAtom(b)), Lnot(ClaimAtom(c)))
# → claim("any_true(all_true(a, b), not(c))", formula=Lor(...))
# → helper with formula attached
```

Single helper for the whole expression; the Formula tree is preserved
inside helper's `formula` attribute (so CNF / SAT tools on the helper
work unchanged).

### 5.5 Predicate Formula

```python
infer(evidence=Equals(x, Constant(5)), hypothesis=c, ...)
# _lift sees Equals(x, Constant(5))
# → claim("x = 5", formula=Equals(...))
# → helper Claim
```

The synthesized description "x = 5" is functional. If the user wants a
richer description ("The reagent concentration equals 5 mol/L"), they
write `claim("...", formula=Equals(...))` explicitly.

### 5.6 Quantifier Formula

```python
exclusive(Forall(x, P_atom), neg, ...)
# _lift sees Forall(variable=x, body=P_atom)
# → claim("forall x. P", formula=Forall(...))
# → helper Claim
```

The compiler's existing `lower_formula.py` handles quantifier lowering;
the lift just routes the expression through `claim(formula=...)` which
already validates quantifier semantics.

### 5.7 BoolExpr

```python
derive(c, given=[k > 0.5])
# _lift sees BoolExpr(distribution=k, op=">", value=0.5)
# → claim("k > 0.5", proposition=k > 0.5)
# → helper Claim (predicate-shape, CDF-derived prior per claim() semantics)
```

The `proposition=` path through `claim()` is used (not `formula=`)
because BoolExpr lowering goes through a different validator.

## 6. Excluded cases (Term layer)

```python
exclusive(Variable("x", Nat), c, ...)
# _lift sees Variable
# → not Claim, not ClaimAtom, not Formula, not BoolExpr
# → raise TypeError with educational message:
#   exclusive() received Variable as first argument; expected Claim or a
#   Boolean-valued expression (Formula, BoolExpr, ClaimAtom). Term-level
#   values (Variable, Constant, Distribution) are not directly claim-able;
#   wrap them in a predicate first (e.g. Equals(x, Constant(5))) or pass
#   an explicit claim(content=..., formula=...) helper.
```

Same path for `Constant`, `FunctionApp`, `Distribution`, `Note`, etc.

## 7. Backwards compatibility

- `claim(content, formula=...)`, `claim(content, proposition)`,
  `claim(content)` — **unchanged**. Existing callers work identically.
- `Claim.__and__/__or__/__invert__` — **unchanged**. Still return Formula
  nodes per PR #658.
- `gaia.engine.lang.compat.{and_, or_, not_}` — **unchanged**. Still
  produce helper Claims via `_expression_helper`. Continues to be the
  recommended path for n-ary conjunctions (where the operator-overload
  chain `(a & b) & c` would nest).
- All Formula transform tools (CNF, SAT, equivalence) — **unchanged**.
  They operate on Formula AST, which is built and stored exactly as
  before; the lift only happens at verb boundary and only touches the
  helper Claim it creates (not the Formula it wraps).
- Verb signatures: type annotations relax from `Claim` to
  `Claim | BooleanValued`. This is a runtime-compatible widening; old
  callers (passing Claim) still type-check.

Net effect: every test in the current Gaia suite that passed before
this RFC continues to pass. New behaviour adds only.

## 8. Alternatives considered

### 8.1 Status quo + better error messages

Keep current API; just rewrite `'Land' has no attribute 'label'` into
educational messages directing users to `claim(formula=...)`.

- **Pro**: zero behaviour change; lowest implementation risk.
- **Con**: the ergonomic gap stays. Users still write two lines for the
  common case. Migration from `and_()` continues to feel like a
  regression.

### 8.2 Leaf-promotion in `Claim.__and__`

Earlier draft (now deleted; was at
`docs/specs/2026-05-24-claim-operator-leaf-promotion-design.md`).
Modify `Claim.__and__` to auto-promote to a Claim helper when both
operands are atomic leaves; otherwise return Formula.

- **Pro**: closes the ergonomic gap directly in the operator overload.
- **Con**: violates PR #658's stated philosophy ("Formula stays pure
  AST"). Introduces a leaf-vs-compound distinction that surfaces as
  surprise: `a & b` returns Claim, `~a & b` returns Formula. Chain
  cases (`(a & b) & c`) produce inconsistent shapes.

### 8.3 Always-promote in `Claim.__and__`

Make `Claim.__and__` always return a helper Claim (with a Formula
attached internally).

- **Pro**: simplest mental model — "operator returns Claim".
- **Con**: every intermediate in `(a & b) | c & d` materialises a
  helper. BN explodes. Formula composition becomes mixed-type
  (Claim+Formula). Predicate cases (Equals, Forall) don't fit.

### 8.4 Closed algebra on Formula classes

Overload `__and__/__or__/__invert__` on ClaimAtom, Land, Lor, Lnot
(making the Formula layer closed under these operators), and use
flattening for `Land & Land`.

- **Pro**: cleaner algebra (chains flatten). Matches what a
  symbolic-algebra library would do.
- **Con**: PR #658 explicitly listed this as a non-goal. Doesn't close
  the verb-boundary gap on its own; would still need either lift or
  explicit `claim(formula=...)` wrap to feed verbs.

**Could be added alongside this RFC**: this RFC is silent on Formula
operator overloads. If §8.4 is also adopted, the two interact cleanly
— Formula chains flatten at construction time, single helper at lift
boundary.

### 8.5 Un-deprecate `and_()`

Simple stopgap.

- **Pro**: no code changes.
- **Con**: leaves `a & b` as a UX trap. Users naturally try `&` first.
  Endless support questions.

## 9. Implementation sketch

### Files to add

```
gaia/engine/lang/_boolean_valued.py
    + class BooleanValued(Protocol)
    + def is_boolean_valued(obj) -> bool
    + setattr on:
      - Claim                (knowledge.py)
      - ClaimAtom            (formula/predicate.py)
      - Land, Lor, Lnot,
        Implies, Iff         (formula/connective.py)
      - Forall, Exists       (formula/quantifier.py)
      - Equals, NotEquals, Greater, GreaterEqual,
        Less, LessEqual, UserPredicate
                              (formula/predicate.py)
      - BoolExpr              (bool_expr.py)

gaia/engine/lang/dsl/_lift.py
    + def _lift_to_claim(value, *, verb_name, arg_position) -> Claim
    + def _synth_description(value) -> str
    + LRU cache per CollectedPackage context
```

### Files to modify

```
gaia/engine/lang/dsl/relate.py
    M exclusive, contradict, equal — add _lift_to_claim on each arg
    M improve error messages (no longer leak '.label' AttributeError)

gaia/engine/lang/dsl/support.py
    M derive, observe, compute — lift conclusion + every given entry

gaia/engine/lang/dsl/infer_verb.py
    M infer — lift evidence, hypothesis, every given entry

gaia/engine/lang/dsl/register_prior.py
    M register_prior — lift target

gaia/engine/lang/dsl/__init__.py
    M re-export BooleanValued, is_boolean_valued for user import
```

### Tests

```
tests/gaia/lang/test_boolean_valued_lift.py (new)
    - test_claim_passthrough
    - test_claim_atom_unwrap_no_helper
    - test_propositional_formula_lifts_to_helper
    - test_nested_propositional_single_helper
    - test_predicate_formula_lifts (Equals/Greater/...)
    - test_quantifier_formula_lifts (Forall/Exists)
    - test_bool_expr_lifts_via_proposition_path
    - test_memoization_within_package
    - test_term_layer_raises_educational_error (Variable/Constant/...)
    - test_each_verb_accepts_lifted (exclusive/contradict/derive/infer/register_prior)

tests/gaia/lang/test_formula_claim_sugar.py
    + new cases: each operator-overload result also works directly in verb calls
```

Estimated 150-300 lines source + 200-300 lines tests.

## 10. Validation plan

### 10.1 Existing test suite

Full pytest suite passes unchanged (no signature changes, only widening).
PR #658's `test_formula_claim_sugar.py` and `test_propositional.py`
unaffected.

### 10.2 BoardgameQA benchmark

`gaia-boardgameqa-benchmark/runs/post_fix_run/RESULTS.md` documents 7/10
threshold-correct on the post-fix skill (v3 with `infer(CONJ_HI/LO)`
override gates). With this RFC + a one-line skill update
(`r_i_premises_hold = p1 & p2` in place of the `infer(CONJ_HI/LO)`
helper), expected outcome:

- P8: 0.108 → ≈0.055 (disproved ✓) — verified by ad-hoc patch (RESULTS §4)
- P12: 0.203 → ≈0.05 (disproved ✓) — predicted from same pattern
- P16: 0.841 → ≈0.951 (proved ✓) — verified by ad-hoc patch (RESULTS §4)
- Other 7 items: unchanged (no override-gate dependency)

Expected total: 10/10 threshold-correct on the validation set.

### 10.3 New test surface

Per §9.

## 11. Open questions

### 11.1 Should `claim()` itself accept BooleanValued directly?

Currently `claim(content=str, *, formula=Formula, proposition=BoolExpr,
...)`. With the marker, a unified `claim(content=str, *,
expression=BooleanValued, ...)` could dispatch internally based on type.

Out of scope for this RFC (it's an additional API simplification, not
required for the lift to work). Worth a separate RFC after this lands.

### 11.2 Should the lift be configurable / disable-able?

E.g. `--strict-claim-args` flag that disables lift and requires explicit
`claim(...)`. Useful for users who want maximum auditability.

Probably not needed initially — explicit `claim("desc", formula=...)`
is already the override. Worth revisiting if the synthesized-description
audit trail proves insufficient in real packages.

### 11.3 Validator regression on the `codex/references-system-consolidation` branch

A separate bug, surfaced during BoardgameQA P16 patch experiments: on
this branch, `claim(formula=a & b)` combined with `exclusive(...)`
referencing that claim triggers
`Error: Top-level Operator must set both operator_id and scope (embedded
FormalExpr operators may omit them)` (`gaia/engine/ir/validator.py:199-
203`). This is **not** addressed by this RFC and should be filed as a
separate issue.

### 11.4 BoolExpr / Formula unification

`BoolExpr(distribution, op, value)` is structurally a `Greater` /
`Less` / `Equals` predicate over Distribution + Constant. A future
refactor could fold BoolExpr into Formula's predicate layer, eliminating
the dual `proposition=` / `formula=` paths in `claim()`. After such a
refactor, this RFC's lift simplifies: drop the BoolExpr branch.

Out of scope but worth noting for forward compatibility.

## 12. Related work and inspiration

- **PR #658** (this RFC's foundation). Established the Formula/Claim
  separation and operator-overload behaviour we extend.
- **Curry–Howard correspondence**. The proposition/term split this RFC
  exploits is the same split that distinguishes types from terms in
  type theory; Gaia happens to use it for BP-variable identification.
- **PR #559**, **PR #565**, **issue #659**: lifted inference, gaia.logic
  entailment, RDF projection — all benefit from a uniform Boolean-valued
  predicate. Several of these will need a similar marker; this RFC
  provides it as a foundation.
- **SymPy** (preserved at Formula layer): symbolic algebra philosophy
  retained for Formula trees; materialisation moved to a single,
  uniform boundary.

## Appendix A: Skill author quick reference

After this RFC ships, the BoardgameQA→Gaia skill §4 override-gate
conjunction becomes:

```python
# 2-premise conjunction (most common case) — auto-lift at verb boundary
exclusive(
    p1 & p2,                                    # ← Formula auto-lifted
    claim("R_i premises do not all hold."),
    rationale="Override-gate partition for preference R_i > R_j.",
    label="exclusive_r_i_premises",
)

# 3+-premise conjunction — explicit n-ary
exclusive(
    and_(p1, p2, p3),                           # flat CONJUNCTION, no nesting
    claim("R_i premises do not all hold."),
    ...
)

# Compound expression with description — explicit
exclusive(
    claim("Detailed description.", formula=(p1 | p2) & p3),
    claim("..."),
    ...
)
```

No `infer(CONJ_HI=0.999, CONJ_LO=0.001)` workaround; no MaxEnt leak;
helper Claim's formula attribute preserves the structure for audit and
transform.

## Appendix B: Class-by-class marker assignment

```python
# gaia/engine/lang/runtime/knowledge.py
class Claim(Knowledge):
    __gaia_boolean_valued__ = True

# gaia/engine/lang/formula/predicate.py
class ClaimAtom:        __gaia_boolean_valued__ = True
class Equals:           __gaia_boolean_valued__ = True
class NotEquals:        __gaia_boolean_valued__ = True
class Greater:          __gaia_boolean_valued__ = True
class GreaterEqual:     __gaia_boolean_valued__ = True
class Less:             __gaia_boolean_valued__ = True
class LessEqual:        __gaia_boolean_valued__ = True
class UserPredicate:    __gaia_boolean_valued__ = True

# gaia/engine/lang/formula/connective.py
class Land:             __gaia_boolean_valued__ = True
class Lor:              __gaia_boolean_valued__ = True
class Lnot:             __gaia_boolean_valued__ = True
class Implies:          __gaia_boolean_valued__ = True
class Iff:              __gaia_boolean_valued__ = True

# gaia/engine/lang/formula/quantifier.py
class Forall:           __gaia_boolean_valued__ = True
class Exists:           __gaia_boolean_valued__ = True

# gaia/engine/lang/bool_expr.py
class BoolExpr:         __gaia_boolean_valued__ = True

# NOT marked (Term universe):
#   Variable, Constant, FunctionApp        (formula/term.py + runtime/variable.py)
#   Distribution                            (runtime/distribution.py)
#   Note, Setting, etc.                     (runtime/knowledge.py subclasses)
```

The marker is a single boolean class attribute. Total addition: 17
lines across 6 files.
