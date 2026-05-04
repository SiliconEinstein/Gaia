# Claim Formula Schema Design

**Status:** Target design (proposal)
**Branch:** `feat/v05-claim-formula-schema` (off `v0.5`)
**Target release:** v0.6 (built on v0.5 foundation)
**Date:** 2026-05-04

## 1. Background and Motivation

### 1.1 Pain points observed in v0.5

| # | Pain | Today | Root cause |
|---|---|---|---|
| 1 | General–specific claims are disconnected | `for x in range: claim(f"P({x})")` produces N atomic claims with no propagating edge to a "general claim" | Quantification is lost in Python; only the author's mind links general ↔ specific |
| 2 | Evidence numbers duplicated 2–3 times | `Binomial(n=395, p=0.75)` and `claim("295 of 395 ...")` and rationale all carry the same numbers, agent must keep them in sync manually | Variables are not first-class; numbers live as Python locals or markdown text |
| 3 | Causal claims have no structural hook | A claim like "rising CO₂ causes warming" is opaque markdown — internal entities (CO₂, temperature) cannot be addressed | Claim content has no internal structure beyond the markdown string |
| 4 | Variable types implicit | Quantifying over "Particle" vs "Real" has no schema enforcement | No typed term layer |

### 1.2 First-principles separation

The fix is not to thicken Claim with ad-hoc fields. It is to acknowledge that today Gaia conflates two layers:

```
┌────────────────────────────────────────────────────────────┐
│  Gaia Lang  (lifted / template / logic)                    │
│  ──────────                                                 │
│  Variables, Domains, Function symbols, Predicates,          │
│  Connectives, Quantifiers — formula AST per Claim           │
└────────────────────────┬───────────────────────────────────┘
                         │  Compiler  (= grounding pass)
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Gaia IR  (grounded / propositional / probability)         │
│  ──────────                                                 │
│  Boolean Knowledge nodes + Operator factors + Strategies    │
│  + Parameterization → BP runs here                          │
└────────────────────────────────────────────────────────────┘
```

**Lang is lifted; IR is grounded.** The compiler is the grounding pass. This mirrors the Markov-Logic-Network and ProbLog tradition: high-level logic templates are grounded into a propositional graphical model for inference.

**IR does not change in this design.** All structural extensions land in Lang. The compiler emits today's IR `Operator` / `Strategy` / `Knowledge` shape; IR consumers (BP, storage, review) are unaffected.

## 2. Knowledge Tree Extension

```
Knowledge                       (base — content, provenance, metadata)
├── Note                        (non-probabilistic, no prior)
├── Question                    (research question, no prior)
├── Claim                       (proposition, has prior, +formula, +kind)
├── Variable                    (NEW — typed term, holds symbol/domain/optional value)
└── Domain                      (NEW — user-defined typed sort, e.g. Particle, F2_plant)
```

### 2.1 Variable

A typed term referenceable by claims, formulas, models, and actions. Carries identity, provenance, and optional bound value.

```python
@dataclass
class Variable(Knowledge):
    symbol: str                 # identifier used in formulas, e.g. "n", "p", "x"
    domain: DomainRef           # primitive built-in OR a Domain Knowledge ref
    value: Any | None = None    # optional bound constant (e.g. 395)
    # content (description), provenance, metadata inherited from Knowledge
```

Binding semantics (CONSTANT / FREE / BOUND_BY_CLAIM) are **not** an authored field. The compiler infers binding from how the variable is used (see §6).

### 2.2 Domain

A user-declared typed sort. Used to type variables and to provide enumerable members for grounding quantifiers.

```python
@dataclass
class Domain(Knowledge):
    members: list[Any] | DomainSpec   # enumerable, finite for now
    # content (description), provenance, metadata inherited
```

### 2.3 Primitive types (built-in, NOT Knowledge)

```
Nat            # non-negative integers
Real           # real numbers
Probability    # [0, 1] interval
Bool           # {true, false}
```

Primitives are runtime constants exposed by `gaia.lang`; they do not register as Knowledge nodes. Only user-declared `Domain` instances participate in the Knowledge tree.

## 3. Formula AST

A small, complete first-order term/formula language. Lives in `gaia/lang/formula/`.

### 3.1 Term

```
Term ::= Variable                      # a typed variable reference
       | Constant(value, primitive)    # 0.75, 395, "abc", True
       | FunctionApp(symbol, args)     # E(x), V(x, y)
       | ArithOp(op, left, right)      # n + k, n * 2
```

### 3.2 Predicate (atomic formula)

```
Predicate ::= Equals(Term, Term)             # via ==
            | Greater / Less / GE / LE       # via > < >= <=
            | NotEquals                      # via !=
            | UserPredicate(symbol, args)    # user-declared
            | Causes(Term, Term)             # built-in causal predicate (v0.6 marker)
            | ClaimAtom(claim_label)         # treat a separate Claim's truth as atomic
```

`ClaimAtom` is the bridge that lets a formula reference *another claim by label*. It is what makes `formula = lnot(land(claimA, claimB))` work — the leaves are claim atoms, not just predicates over terms.

### 3.3 Connectives and Quantifiers (compound formula)

```
Formula ::= Predicate
          | land(F1, F2, ...)        # ∧
          | lor(F1, F2, ...)         # ∨
          | lnot(F)                  # ¬
          | implies(F1, F2)          # →
          | iff(F1, F2)              # ↔
          | forall(Variable, F)      # ∀ — variable must have a Domain
          | exists(Variable, F)      # ∃
```

Python `and`/`or`/`not` cannot be overloaded, so connectives are named functions. Comparisons (`==`, `<`, `>`, `<=`, `>=`, `!=`) are overloaded on `Term` via dunder methods.

### 3.4 Function symbol declaration

User-declared function symbols are declared once and used as terms:

```python
E = function("E", Particle, Real)        # E: Particle → Real
V = function("V", Particle, Particle, Real)  # V: Particle × Particle → Real
```

`function(...)` returns a callable that, when invoked, builds a `FunctionApp` AST node.

### 3.5 User-declared predicate symbol

```python
Stable = predicate("Stable", Particle)              # Stable(x): Particle → Bool
Bonds = predicate("Bonds", Particle, Particle)      # Bonds(x, y)
```

## 4. Claim Extension

Two new fields added to `Claim`:

```python
@dataclass
class Claim(Knowledge):
    # existing
    content: str                  # human-readable markdown
    prior: float | None = None
    parameters: list[Parameter] = ...
    background: list[Knowledge] = ...
    provenance: list[...] = ...
    metadata: dict = ...

    # NEW
    formula: Formula | None = None   # structured assertion (None → propositional atom)
    kind: ClaimKind = ClaimKind.GENERAL
```

`formula = None` is fully supported — a Claim without a formula is a propositional atom (today's behavior, unchanged for unstructured claims).

### 4.1 ClaimKind enum

| kind | Meaning | Typical formula shape | Sugar constructor |
|---|---|---|---|
| `GENERAL` | Default. May or may not have a formula. | any | `claim(...)` |
| `PARAMETER` | Asserts that a Variable takes a specific value | `Equals(var, const)` | `parameter(var, value, ...)` |
| `OBSERVATION` | Records observed values for one or more Variables | conjunction of `Equals` | `observation(var=val, ...)` |
| `QUANTIFIED` | Universally or existentially quantified body | `forall(...)` or `exists(...)` | `claim(..., formula=forall(...))` (no extra sugar) |
| `CAUSAL` | Asserts a causal relation between Variables (v0.6 hook) | `Causes(...)` at top level | `causal(cause_var, effect_var, ...)` |

**Truth condition:** A Claim with a `formula` is true iff the formula is true under the current variable bindings and the environment. `prior` expresses the marginal belief in this truth before evidence updates.

**Sugar constructors are non-load-bearing.** They lower to `claim(content=..., formula=..., kind=..., prior=...)`. Authors who prefer the explicit form can always use `claim(...)` directly.

## 5. Author DSL

Surface area introduced (Lang only, IR untouched).

### 5.1 Declaring building blocks

```python
# Custom domain (user-declared sort)
Particle = domain("Particle", members=[p1, p2, p3])

# Variable: the only constructor; presence of `value=` distinguishes the use
n = variable("n", Nat, value=395)            # constant
k = variable("k_dominant", Nat, value=295)
p = variable("p_dominant", Probability)      # awaiting a constraining claim
x = variable("x", Particle)                  # logical, will be quantifier-bound

# Function and predicate symbols
E = function("E", Particle, Real)            # E: Particle → Real
Stable = predicate("Stable", Particle)       # Stable(x): Particle → Bool
```

### 5.2 Building formulas

Operator overloading on `Term`:

```python
p == 0.75            # Equals(p, 0.75)
E(x) > 0             # Greater(E(x), 0)
n + k                # Add(n, k)
n != 0               # NotEquals(n, 0)
```

Named connectives and quantifiers (Python `and`/`or`/`not` are not overloadable):

```python
land(P, Q)           # P ∧ Q
lor(P, Q)            # P ∨ Q
lnot(P)              # ¬ P
implies(P, Q)        # P → Q
iff(P, Q)            # P ↔ Q

forall(x, body)      # ∀ x: body
exists(x, body)      # ∃ x: body
causes(x, y)         # Causes(x, y), the built-in causal predicate marker

bind(p, 0.75)        # alias for (p == 0.75); reads as "binding"
```

### 5.3 Sugar constructors for common claim kinds

```python
# Parameter assertion: "variable v takes value k under this hypothesis"
H = parameter(p, 0.75, prior=0.5,
              describe=f"Mendelian 3:1 segregation: P(dominant) = {p}.")

# Observation: "these variables took these observed values"
D = observation(n=n, k=k, prior=0.95,
                describe=f"{k} of {n} F2 plants are dominant.")

# Causal claim
C = causal(co2_level, temperature, prior=0.9,
           describe="Rising CO₂ causes increased global mean temperature.")

# Universally quantified claim — no specialized sugar; use `claim(formula=forall(...))`
universal_law = claim(
    "All particles have positive energy.",
    formula=forall(x, E(x) > 0),
    prior=0.95,
)
```

### 5.4 Existing actions accept Variable references

`evidence` / `infer` / `associate` etc. **do not change shape**, but their model arguments now accept `Variable` references in place of literals:

```python
evidence(D, hypothesis=H,
         model=Binomial(n=n, p=p),     # n, p are Variables — bound from H/D
         p_data_given_not_h=0.5,
         given=[independent_trials_valid])
```

The action reads `H.formula` to determine variable bindings (e.g., `Equals(p, 0.75)` → bind `p=0.75` for likelihood evaluation). For an `OBSERVATION` claim with `value` on its variables, observed values are read directly.

## 6. Variable Binding Semantics

Authors do not write a `binding` field on Variable. The compiler infers binding from usage in a single pass over the package:

| Usage in package | Inferred binding |
|---|---|
| `Variable.value is not None` | **CONSTANT** — fixed value |
| Variable appears in `forall(v, ...)` or `exists(v, ...)` body | **FREE** within that quantifier scope |
| Variable appears in `Equals(v, const)` (or `bind(v, const)`) inside a Claim's formula | **BOUND_BY_CLAIM** — value tied to the truth of that Claim |
| Variable referenced but none of the above | **UNBOUND** — compiler emits a warning |

A Variable can have **different bindings in different scopes** — e.g., `p` may be CONSTANT for one variant package and BOUND_BY_CLAIM for another. The compiler tracks this per scope.

## 7. Compiler: Lang → IR Lowering

The compiler produces today's IR shapes. Authors never touch IR types directly.

### 7.1 Formula → IR Operator graph

A Claim with `formula=land(P, Q)` (where P, Q are `ClaimAtom`s referring to existing claims A, B):
- Emit one **helper Knowledge** node representing the conjunction-result, with `prior` carried from the Claim
- Emit `Operator(operator=CONJUNCTION, variables=[A, B], conclusion=helper)`

A Claim with `formula=Equals(p, 0.75)` (parameter assertion):
- Emit a **propositional atom Knowledge** in IR (no internal connectives — the formula is a single predicate over a Variable)
- Record the binding `(p, 0.75)` in `Knowledge.parameters` for downstream consumers (e.g., `evidence`'s likelihood model)

Compound formulas (e.g., `land(equals(...), implies(...))`) lower bottom-up — each non-atomic node emits a helper Knowledge plus the matching Operator. Equivalent in factor-graph topology to today's hand-written `and_/or_/contradiction/...` helper claims.

### 7.2 Quantifier grounding

```
forall(x: Particle, body(x))
   →   for v in Particle.members:
           emit grounded_body_v ← compile(body[x ↦ v])
       emit one universal-claim Knowledge G with prior from the source Claim
       emit Strategy(NOISY_AND or CONJUNCTION, premises=[grounded_body_v...], conclusion=G)
```

`exists(x, body)` lowers symmetrically with `DISJUNCTION`.

The instantiation parameter `x ↦ v` is recorded in each `grounded_body_v.parameters` — preserving provenance back to the lifted claim.

### 7.3 Causal claim (v0.5 marker, v0.6 semantics)

In v0.5, `Causes(X, Y)` lowers to a propositional atom Knowledge with metadata `{"causal": {"cause": X.id, "effect": Y.id}}`. BP treats it as a regular claim. v0.6 introduces an interventional factor type that consumes this metadata; until then, downstream consumers can read the marker but no special inference happens.

### 7.4 Variable provenance into IR

Because IR is grounded:
- **Variables do not appear as IR Knowledge nodes.**
- A Variable's symbol, domain, and instantiation parameters are written into the IR `Knowledge.parameters` of every grounded claim that references it.
- The Lang-level Variable still exists in storage at the Lang layer, addressable by qualified ID (for tooling, rendering, review).

### 7.5 What `evidence` reads

When an `evidence(D, hypothesis=H, model=...)` action is compiled, the compiler:
1. Resolves Variable references in `model` to concrete values:
   - If the Variable is `CONSTANT`: use its `value`.
   - If the Variable is `BOUND_BY_CLAIM` and the binding claim is H (or a premise of H): read the bound value from the claim's `formula`.
   - If the Variable is `OBSERVATION`-bound on D: read from D.
2. Builds the IR Strategy node with concrete numeric parameters.

This is what eliminates the duplicate-numbers pain: numbers live in Variable definitions, not in claim text or model literals.

## 8. Migration of Existing v0.5 Packages

### 8.1 What must change

Today's helper-creating DSL functions are subsumed by formula AST:

| Today (v0.5) | Tomorrow (v0.6) |
|---|---|
| `helper = and_(P, Q)` | `claim(..., formula=land(P, Q))` |
| `helper = or_(P, Q)` | `claim(..., formula=lor(P, Q))` |
| `helper = not_(P)` | `claim(..., formula=lnot(P))` |
| `helper = contradiction(P, Q, prior=0.99)` | `claim(..., formula=lnot(land(P, Q)), prior=0.99)` |
| `helper = equivalence(P, Q, prior=0.99)` | `claim(..., formula=iff(P, Q), prior=0.99)` |
| `helper = complement(P, Q)` | `claim(..., formula=lnot(iff(P, Q)))` (XOR) |
| `helper = disjunction(P, Q, ...)` | `claim(..., formula=lor(P, Q, ...))` |

The IR-level shape produced is **identical**. The migration is purely at the authoring surface.

### 8.2 Deprecation policy

Recommend keeping the existing functions as deprecated aliases for **one minor version** (v0.6 ships both, v0.7 deletes the aliases):

```python
def and_(*claims, **kwargs):
    warnings.warn("and_() is deprecated; use claim(formula=land(...))", DeprecationWarning)
    # forward to the new lowering
    ...
```

This gives existing packages (Mendel, Galileo, Superconductivity, …) one release cycle to migrate. A migration codemod (AST-level rewrite) is in scope as a follow-up tool.

### 8.3 Scope of migration in this design

The migration codemod is a **separate** workstream. This design ships the new authoring surface and the deprecated aliases; package migration happens incrementally afterward.

## 9. Implementation Milestones

Three independent PR slices, ordered by dependency:

### Milestone A — Knowledge tree + Formula AST (Lang only, no DSL)

- `gaia/lang/runtime/variable.py`: `Variable` Knowledge subclass
- `gaia/lang/runtime/domain.py`: `Domain` Knowledge subclass + primitives module
- `gaia/lang/formula/`: Term / Predicate / Connective / Quantifier dataclasses, no operator overloading yet
- `gaia/lang/runtime/knowledge.py`: add `formula`, `kind` fields to Claim
- Tests: dataclass construction, equality, serialization

### Milestone B — DSL surface + compiler lowering

- `gaia/lang/dsl/formula.py`: operator overloading on Term, `forall/exists/land/lor/lnot/implies/iff/causes/bind` helpers
- `gaia/lang/dsl/declarations.py`: `variable / domain / function / predicate` declarations
- `gaia/lang/dsl/sugar.py`: `parameter / observation / causal` claim sugar
- `gaia/lang/compiler/lower_formula.py`: Formula → IR Operator graph
- `gaia/lang/compiler/grounding.py`: Quantifier grounding pass
- `gaia/lang/compiler/binding.py`: Variable binding inference
- Tests: end-to-end Mendel example, quantification grounding, parameter binding into evidence

### Milestone C — Migration tooling + deprecation

- Wrap `and_/or_/not_/contradiction/equivalence/complement/disjunction` with `DeprecationWarning`
- Codemod: `gaia migrate-formula <package>` rewrites old DSL calls to new formula form
- Migrate first-party packages (Mendel, Galileo, Superconductivity) in separate PRs
- Update gaia-lang docs

Each milestone is independently shippable. Milestone A introduces no new author-facing surface; B is the user-visible feature; C is migration cleanup.

## 10. Out of Scope / Deferred to v0.6+

| Item | Why deferred |
|---|---|
| **Causal `do`-calculus / intervention semantics** | v0.5 ships only the `Causes(X, Y)` predicate as a marker. The interventional factor type and SCM machinery come in v0.6. |
| **Higher-order quantification** (over predicates / functions) | Not needed for the v0.5 use cases (Mendel, Galileo, etc.). Adds significant typing complexity. |
| **Open / infinite domains** | First version requires `Domain.members` to be finite & enumerable. Lazy / open-world domains are a v0.7 topic. |
| **Decompose action** (point 2 from the brainstorm) | Pain point 2 (claims that aren't atomic) is solved by a separate `decompose` action on top of formula AST — not by a schema change. Designed in a separate spec. |
| **Role-on-action-graph** (point 6) | Roles (hypothesis / prediction / observation) belong on the action graph node, not on Claim. Separate spec. |
| **`KnowledgeType` enum collision in IR** | IR's `KnowledgeType` enum currently lists claim/note/question/setting/action — Variable/Domain are Lang-only and do not need an IR enum entry. Keep IR enum unchanged. |

## 11. Open Questions

1. **Operator precedence for connectives.** `land(P, lor(Q, R))` is unambiguous but verbose. Should we overload `&` and `|` on Formula too (Z3-style)? Trade-off: shorter syntax vs additional dunder collisions. **Recommendation:** ship without `&/|` in milestone B; add later if authors ask.
2. **Sugar for `kind=QUANTIFIED`.** Currently no shorthand; author writes `claim(formula=forall(...))`. Whether to add a `universal(x, body, prior=...)` helper is open.
3. **Codemod fidelity.** Some existing helper-claim authors set custom `metadata`/`reason` that have no direct formula equivalent. Codemod policy for these edge cases TBD.

## 12. Examples

### 12.1 Mendel — old vs new

**Old (v0.5):**

```python
H = claim("Mendelian 3:1 segregation holds.", prior=0.5)
D = claim("Observed 295 dominant phenotypes out of 395 F2 plants.", prior=0.95)

evidence(
    D,
    hypothesis=H,
    model=Binomial(n=395, p=0.75),     # 395 and 0.75 duplicated
    p_data_given_not_h=0.5,
    given=[independent_trials_valid],
    rationale="Under 3:1 segregation, dominant phenotype count follows Binomial(n=395, p=0.75).",
)
```

**New (v0.6):**

```python
n = variable("n", Nat, value=395)
k = variable("k_dominant", Nat, value=295)
p = variable("p_dominant", Probability)

H = parameter(p, 0.75, prior=0.5,
              describe=f"Mendelian 3:1 segregation: P(dominant) = {p}.")

D = observation(n=n, k=k, prior=0.95,
                describe=f"{k} of {n} F2 plants are dominant.")

evidence(D, hypothesis=H,
         model=Binomial(n=n, p=p),
         p_data_given_not_h=0.5,
         given=[independent_trials_valid])
```

Numbers (395, 295, 0.75) appear once. Variables flow through prose (via f-string), formula payload (via sugar), and likelihood model (via direct reference).

### 12.2 Universal claim with quantification

```python
Particle = domain("Particle", members=load_particles())
x = variable("x", Particle)
E = function("E", Particle, Real)

universal_law = claim(
    "All particles have positive energy.",
    formula=forall(x, E(x) > 0),
    prior=0.95,
)

# Specific instance contributing evidence to the universal claim
specific = claim(
    f"Particle p_1 has positive energy.",
    formula=(E(p_1) > 0),
    prior=0.97,
)
# Compiler grounds universal_law: emits one Knowledge node per particle plus
# a NOISY_AND/CONJUNCTION strategy connecting them to the universal claim.
# Evidence on `specific` propagates to `universal_law` through that factor.
```

### 12.3 Causal claim (v0.6 marker)

```python
co2 = variable("co2_level", Real)
temp = variable("temperature", Real)

C = causal(co2, temp, prior=0.9,
           describe="Rising CO₂ causes increased global mean temperature.")
# Lowers to claim(formula=Causes(co2, temp), kind=CAUSAL, ...).
# In v0.5 BP treats it as a regular Boolean claim; v0.6 introduces interventional
# factor semantics that read the (cause, effect) marker.
```
