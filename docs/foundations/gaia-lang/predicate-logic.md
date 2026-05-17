---
status: current-canonical
layer: gaia-lang
since: v0.5
---

# Predicate Logic In Gaia Lang

Gaia Lang has a small, typed predicate-logic layer for writing structured
claims. It is not a separate theorem prover. It is an authoring layer that lets
package authors say, in machine-readable form, what variables, domains,
predicates, connectives, and quantifiers a claim is about.

The compiler then lowers the supported subset into the existing Gaia IR:
ordinary claim nodes, deterministic operators, generated helper claims, and
deduction-style strategies. The BP backend still runs on a ground binary claim
graph. Predicate logic helps authors produce that graph more precisely.

This document explains the model from first principles. You do not need to
already know first-order logic to read it.

Source references:

- `gaia/engine/lang/runtime/domain.py`
- `gaia/engine/lang/runtime/variable.py`
- `gaia/engine/lang/formula/term.py`
- `gaia/engine/lang/formula/predicate.py`
- `gaia/engine/lang/formula/connective.py`
- `gaia/engine/lang/formula/quantifier.py`
- `gaia/engine/lang/dsl/formula.py`
- `gaia/engine/lang/dsl/sugar.py`
- `gaia/engine/lang/compiler/lower_formula.py`
- `tests/gaia/engine/lang/test_formula_lowering.py`
- `tests/gaia/engine/lang/test_milestone_a_smoke.py`

---

## 1. Why This Layer Exists

Most Gaia claims can be written as ordinary prose:

```python
from gaia.engine.lang import claim

heliocentric = claim("The heliocentric model is correct.", prior=0.8)
```

That is enough when the claim is a closed proposition: it is either true or
false as a whole.

Some scientific claims are more structured:

- "The parameter theta equals 0.75."
- "295 of 395 F2 plants are dominant."
- "Rising CO2 causes temperature change."
- "Every particle in this finite domain is stable."
- "Some particle in this finite domain is stable."
- "Claim A implies Claim B."

Prose can describe these, but Gaia needs more than prose when a later compiler
or reviewer must inspect bindings, generate grounded instances, or lower a
Boolean structure into operators. The predicate-logic layer supplies that
structure.

The key distinction is:

| Author writes | Gaia stores | Why it matters |
|---|---|---|
| prose claim | one ordinary `Claim` | good for human-readable assertions |
| `claim(formula=...)` | `Claim` plus Formula AST metadata/lowering | good for variables, predicates, connectives, and quantifiers |
| action verb such as `derive(...)` | Strategy/operator/warrant IR | good for reviewable reasoning steps between claims |

Predicate logic describes the internal shape of one claim. Actions describe how
claims support, contradict, or probabilistically relate to each other.

---

## 2. The Mental Model

In classical predicate logic, a formula such as `Stable(x)` has three pieces:

1. A variable `x`.
2. A predicate symbol `Stable`.
3. A domain of things that `x` can range over.

Gaia keeps the same idea, but uses Python objects:

```python
from gaia.engine.lang import Domain, PredicateSymbol, UserPredicate, Variable

Particle = Domain("Particles in this toy model", members=["p1", "p2"])
x = Variable(symbol="x", domain=Particle)
Stable = PredicateSymbol(name="Stable", arg_domains=(Particle,))

formula = UserPredicate(Stable, (x,))
```

Read this as: "`Stable(x)` where `x` ranges over `Particle`."

Nothing has entered IR yet. `Domain`, `Variable`, and `PredicateSymbol` are
Gaia Lang authoring objects. They help build a `Formula`. The formula becomes
part of Gaia IR only when it is attached to a `Claim` and compiled:

```python
from gaia.engine.lang import ClaimKind, claim, forall

law = claim(
    "Every particle is stable.",
    formula=forall(x, UserPredicate(Stable, (x,))),
    kind=ClaimKind.QUANTIFIED,
    prior=0.9,
)
law.label = "stable_all"
```

The compiled graph does not contain a special "first-order logic engine". It
contains:

- the source claim `stable_all`;
- one generated instance claim for each finite domain member;
- one deduction-style implication from `stable_all` to each instance.

That is the design center: **author structured formulas, compile to a ground
claim graph**.

---

## 3. Vocabulary

### Domain

A `Domain` is a finite, enumerable sort. It answers the question "what values
can this variable range over?"

```python
from gaia.engine.lang import Domain

Particle = Domain("Particles in this toy model", members=["p1", "p2", "p3"])
```

Current contract:

- `members` must be a non-empty `list`.
- `Domain` is Lang-only. It subclasses `Knowledge` for identity/provenance, but
  it is not registered as an IR knowledge node.
- Quantifier lowering currently requires a finite `Domain`; it does not lower
  `forall(x, ...)` when `x.domain` is a primitive such as `Nat` or `Real`.

Use a `Domain` when Gaia should enumerate all possible values.

### Primitive Types

Gaia also has four built-in primitive type tokens:

```python
from gaia.engine.lang import Bool, Nat, Probability, Real
```

They validate literal values:

| Primitive | Accepted values |
|---|---|
| `Nat` | non-negative Python `int`, excluding `bool` |
| `Real` | Python `int` or `float`, excluding `bool` |
| `Probability` | number in `[0.0, 1.0]`, excluding `bool` |
| `Bool` | Python `bool` |

Use primitive types for measured values, scalar parameters, Boolean switches,
and Bayes-model variables.

Primitive domains are not enumerable. That is why the compiler cannot currently
expand `forall(n, ...)` over `Nat`: there is no finite member list to ground.

### Variable

A `Variable` is a typed term with a symbol, a domain, and optionally a bound
value:

```python
from gaia.engine.lang import Nat, Variable

n = Variable(symbol="n", domain=Nat)
n_obs = Variable(symbol="n_obs", domain=Nat, value=395)
```

Current contract:

- `symbol` must be a non-empty string.
- `domain` must be a primitive type or a finite `Domain`.
- If `value` is set, it must be accepted by the domain.
- `Variable` is Lang-only and does not become an IR knowledge node by itself.
- `Variable` carries the term marker used by the formula AST.

There are three common uses:

| Variable shape | Meaning |
|---|---|
| `Variable("x", Domain(...))` with no value | free variable, often bound by `forall` / `exists` |
| `Variable("n", Nat)` with no value | primitive quantity being described |
| `Variable("k_obs", Nat, value=295)` | observed/bound primitive value |

### Term

A `Term` is a value-bearing expression. Predicates talk about terms.

Current term nodes:

| Term node | Meaning |
|---|---|
| `Variable` | typed variable, possibly with a bound value |
| `Constant(value, primitive)` | primitive literal value |
| `FunctionApp(symbol, args)` | typed user function application |
| `ArithOp(op, left, right)` | arithmetic expression over terms |

Example:

```python
from gaia.engine.lang import Constant, FunctionApp, FunctionSymbol, Real

Energy = FunctionSymbol(
    name="Energy",
    arg_domains=(Particle,),
    result_domain=Real,
)
energy_x = FunctionApp(Energy, (x,))
zero = Constant(0, Real)
```

`Constant` currently takes a primitive type, not a finite `Domain`.

### Predicate

A predicate is a truth-valued formula over terms. It says something that can be
true or false.

Current atomic formulas:

| Formula node | Meaning |
|---|---|
| `Equals(left, right)` | term equality |
| `NotEquals(left, right)` | term inequality |
| `Greater`, `GreaterEqual`, `Less`, `LessEqual` | numeric/comparable relation |
| `UserPredicate(symbol, args)` | user-declared predicate application |
| `ClaimAtom(claim)` | bridge from an existing `Claim` to formula land |

Example:

```python
from gaia.engine.lang import Greater

positive_energy = Greater(energy_x, zero)
```

`UserPredicate` uses an explicit symbol:

```python
from gaia.engine.lang import PredicateSymbol, UserPredicate

Stable = PredicateSymbol(name="Stable", arg_domains=(Particle,))
stable_x = UserPredicate(Stable, (x,))
```

`PredicateSymbol` arity must be at least 1. If you want a proposition with no
arguments, use a `Claim`, not a zero-argument predicate.

### Connective

Connectives build larger formulas from smaller formulas:

| Helper | AST class | IR operator when lowered |
|---|---|---|
| `land(a, b, ...)` | `Land` | `conjunction` |
| `lor(a, b, ...)` | `Lor` | `disjunction` |
| `lnot(a)` | `Lnot` | `negation` |
| `implies(a, b)` | `Implies` | `implication` |
| `iff(a, b)` | `Iff` | `equivalence` |

`land` and `lor` require at least two operands. Python keywords `and`, `or`,
and `not` cannot be overloaded safely for Gaia claims, so the DSL uses explicit
function names.

Example over existing claims:

```python
from gaia.engine.lang import ClaimAtom, claim, implies

a = claim("A holds.")
b = claim("B holds.")
rule = claim("A implies B.", formula=implies(ClaimAtom(a), ClaimAtom(b)))
```

`ClaimAtom` is the bridge. It says "use the truth value of this existing Gaia
claim as an atom inside the formula."

### Quantifier

Quantifiers bind a free variable:

```python
from gaia.engine.lang import exists, forall

all_stable = forall(x, UserPredicate(Stable, (x,)))
some_stable = exists(x, UserPredicate(Stable, (x,)))
```

Current contract:

- The bound variable must be a `Variable`.
- The bound variable must be free: `value is None`.
- The body must be a `Formula`.
- Compiler lowering currently supports a single top-level `Forall` or `Exists`
  over a finite `Domain`.
- Nested quantifiers are not a supported lowering contract today.

---

## 4. Two Ways To Attach Structure To A Claim

Gaia has two related but different mechanisms:

### 4.1 Opaque `parameters=[...]`

The older/simple mechanism is a prose claim with a `parameters` list:

```python
law = claim(
    "forall {x}. superconductor({x}) -> zero_resistance({x})",
    parameters=[{"name": "x", "type": "material"}],
)
```

This records parameter metadata on the IR `Knowledge`. It does not parse the
string, build predicate AST nodes, or generate grounded instances. Use it when
you need a human-readable universal claim but do not need compiler-supported
formula lowering.

### 4.2 Structured `formula=...`

The executable predicate-logic mechanism is `claim(formula=...)`:

```python
from gaia.engine.lang import ClaimKind, Domain, PredicateSymbol, UserPredicate, Variable
from gaia.engine.lang import claim, forall

Material = Domain("Materials in this package", members=["YBCO", "LaH10"])
x = Variable(symbol="x", domain=Material)
Superconducts = PredicateSymbol(name="Superconducts", arg_domains=(Material,))

law = claim(
    "Every listed material superconducts.",
    formula=forall(x, UserPredicate(Superconducts, (x,))),
    kind=ClaimKind.QUANTIFIED,
    prior=0.7,
)
law.label = "all_materials_superconduct"
```

This is what the formula compiler reads.

As a rule of thumb:

- Use `parameters=[...]` for a lightweight, mostly narrative universal claim.
- Use `formula=...` when Gaia should inspect atoms, bindings, connectives, or
  quantifiers.

---

## 5. Structured Formula Sugar

Most authors do not need to hand-write every AST node for common data claims.
Gaia provides two formula helpers, plus the normal `observe(...)` action for
measured values.

### `parameter(variable, value, ...)`

Use this to assert that a primitive variable has a value:

```python
from gaia.engine.lang import Probability, Variable, parameter

theta = Variable(symbol="theta", domain=Probability)
h_3_1 = parameter(
    theta,
    0.75,
    describe="Mendelian 3:1 segregation fixes P(dominant) at 0.75.",
    prior=0.5,
    label="h_3_1",
)
```

It creates a `ClaimKind.PARAMETER` claim with:

```python
Equals(theta, Constant(0.75, Probability))
```

Current limit: `parameter(...)` supports primitive variables only. It does not
bind a finite `Domain` member.

### Structured observed values

Use a normal formula claim for observed primitive values, then mark it with
`observe(...)`. Observation is an action verb, not a `ClaimKind` and not a
structured-claim sugar.

```python
from gaia.engine.lang import Constant, Nat, Variable, claim, equals, land, observe

n = Variable(symbol="n", domain=Nat)
k = Variable(symbol="k", domain=Nat)

data = observe(
    claim(
        "Observed 295 dominant phenotypes out of 395 F2 plants.",
        formula=land(equals(n, Constant(395, Nat)), equals(k, Constant(295, Nat))),
    ),
    rationale="Extracted from the reported count table.",
    label="observe_f2_data",
)
data.label = "f2_data"
```

One equality records one observed binding. Multiple observed bindings should be
written as a conjunction of equalities. The compiler copies primitive formula
bindings onto the source claim as `parameters` plus `metadata.formula_bindings`;
the zero-premise `observe(...)` action pins the claim to `1 - CROMWELL_EPS`.

### Causal statements

Causal mechanism authoring is not represented by a marker-only formula
predicate or `ClaimKind`. Until Gaia grows a first-class causal mechanism
surface, write causal statements as ordinary prose claims and connect their
support through reviewable reasoning actions.

---

## 6. Lowering Contract

Formula lowering happens in `gaia/engine/lang/compiler/lower_formula.py`, after
ordinary knowledge IDs are assigned.

The compiler sees a claim such as:

```python
claim("...", formula=some_formula, kind=ClaimKind.QUANTIFIED)
```

and produces a `FormulaLoweringResult`:

- generated `Knowledge` nodes, if the formula needs helper or instance claims;
- generated `Operator` nodes, if the formula contains connectives;
- generated `Strategy` nodes, for supported universal grounding;
- metadata updates on the source claim;
- parameter updates on the source claim.

### 6.1 Atomic Formulas

Top-level atomic formulas annotate the source claim. They do not create orphan
atom claims.

Example:

```python
from gaia.engine.lang import Constant, Equals, Probability, Variable, claim

p = Variable(symbol="p", domain=Probability)
value = claim(
    "The success probability is 0.75.",
    formula=Equals(p, Constant(0.75, Probability)),
    prior=0.8,
)
value.label = "p_value"
```

Compile result:

- source claim keeps its own QID;
- `metadata.formula_lowering = "atom"`;
- `metadata.formula_atom.kind = "equals"`;
- `metadata.formula_bindings` records `p = 0.75`;
- `parameters` gets an IR `Parameter(name="p", type="Probability", value=0.75)`;
- no generated operators or strategies.

### 6.2 Claim Atoms

`ClaimAtom(existing_claim)` uses an existing Gaia claim as an atom in formula
land.

Top-level `ClaimAtom(a)` attached to a different source claim creates an
equivalence alias:

```python
from gaia.engine.lang import ClaimAtom, claim

a = claim("A.", prior=0.8)
alias = claim("Alias of A.", formula=ClaimAtom(a), prior=0.2)
```

Compile result:

- `alias.metadata.formula_atom` records the QID of `a`;
- an `equivalence` operator links `a` and `alias`;
- a generated equivalence helper claim records the structural result.

Inside larger formulas, `ClaimAtom` lets connectives refer to existing claim
nodes instead of generating new atom nodes.

### 6.3 Connectives

Connectives lower to deterministic IR operators:

```python
from gaia.engine.lang import ClaimAtom, claim, land

a = claim("A.")
b = claim("B.")
both = claim("A and B.", formula=land(ClaimAtom(a), ClaimAtom(b)))
both.label = "both"
```

Compile result:

- `Operator(operator="conjunction")`;
- variables are the QIDs of `a` and `b`;
- conclusion is the QID of `both`.

For a nested formula, Gaia generates private helper claims for intermediate
sub-expressions:

```python
from gaia.engine.lang import ClaimAtom, claim, implies, land

rule = claim(
    "A and B imply C.",
    formula=implies(land(ClaimAtom(a), ClaimAtom(b)), ClaimAtom(c)),
)
```

The conjunction gets a generated helper claim. The implication then uses that
helper as its antecedent. These helpers are structural, generated, and not
independent probabilistic inputs.

### 6.4 Universal Quantification

`Forall(variable, body)` lowers only when `variable.domain` is a finite
`Domain`.

```python
from gaia.engine.lang import ClaimKind, Domain, PredicateSymbol, UserPredicate, Variable
from gaia.engine.lang import claim, forall

Particle = Domain("Particles", members=["p1", "p2"])
x = Variable(symbol="x", domain=Particle)
Stable = PredicateSymbol(name="Stable", arg_domains=(Particle,))

universal = claim(
    "Every particle is stable.",
    formula=forall(x, UserPredicate(Stable, (x,))),
    kind=ClaimKind.QUANTIFIED,
    prior=0.9,
)
universal.label = "stable_all"
```

Compile result:

- generated instance claims:
  - `Stable(p1)`;
  - `Stable(p2)`;
- each instance gets:
  - `metadata.generated = True`;
  - `metadata.formula_lowering = "forall_instance"`;
  - `metadata.source_claim = <stable_all QID>`;
  - `metadata.binding = {"symbol": "x", "value": "p1" or "p2", ...}`;
  - `parameters = [Parameter(name="x", type="Particles", value=...)]`;
- one deduction-style strategy per member:
  - premise: source universal claim;
  - conclusion: generated instance claim;
  - metadata: `formula_lowering = "forall_grounding"`;
  - formal expression contains one implication from source to instance.

Important semantic point: Gaia does **not** lower `forall x. P(x)` as "all
instances conjoined imply the universal." It lowers the universal claim forward
to each finite instance. The universal claim remains a claim with its own prior
or review-supplied belief. Evidence from particular instances can still
interact with the graph through ordinary BP structure, but there is no complete
lifted universal-inference engine here.

If the variable uses a primitive domain:

```python
from gaia.engine.lang import Nat, Variable, forall

n = Variable(symbol="n", domain=Nat)
```

then `claim(formula=forall(n, ...))` currently raises during lowering, because
`Nat` is not enumerable.

### 6.5 Existential Quantification

`exists(variable, body)` also requires a finite `Domain` (the underlying AST node `Exists` is what `gaia.engine.lang.formula` exposes; `exists` is the recommended top-level helper).

```python
from gaia.engine.lang import ClaimKind, claim, exists

some_stable = claim(
    "Some particle is stable.",
    formula=exists(x, UserPredicate(Stable, (x,))),
    kind=ClaimKind.QUANTIFIED,
    prior=0.6,
)
some_stable.label = "stable_some"
```

Compile result for a two-member domain:

- generated instance claims `Stable(p1)` and `Stable(p2)`;
- one `disjunction` operator:
  - variables: the instance claim QIDs;
  - conclusion: source existential claim.

Read this as: the existential source claim is true exactly when at least one
generated instance is true.

For a singleton domain, the compiler uses `equivalence` between the source
claim and the single generated instance, because "some member satisfies P" is
the same as "the only member satisfies P."

### 6.6 Unsupported Lowering

The AST can represent more than the current compiler lowers. Unsupported forms
fail early instead of silently compiling to the wrong graph.

Current non-goals:

- no full first-order theorem prover;
- no infinite-domain grounding;
- no lifted BP backend;
- no nested-quantifier lowering contract;
- no automatic Skolemization for `forall x exists y`;
- no zero-arity predicate symbols;
- no `parameter(...)` sugar or special observation helper for finite `Domain`
  values.

---

## 7. Worked Example

This example is small enough to inspect by hand. It says:

1. There are two particles in this package.
2. Every listed particle is stable.
3. Particle `p1` is observed stable.

```python
from gaia.engine.lang import (
    ClaimKind,
    Domain,
    PredicateSymbol,
    UserPredicate,
    Variable,
    claim,
    forall,
    observe,
)

Particle = Domain("Particles in the toy experiment", members=["p1", "p2"])
x = Variable(symbol="x", domain=Particle)
Stable = PredicateSymbol(name="Stable", arg_domains=(Particle,))

all_stable = claim(
    "Every listed particle is stable.",
    formula=forall(x, UserPredicate(Stable, (x,))),
    kind=ClaimKind.QUANTIFIED,
    prior=0.7,
)
all_stable.label = "all_stable"

p1_stable = claim("Particle p1 is stable.")
p1_stable.label = "p1_stable"
observe(
    p1_stable,
    rationale="The detector classified p1 as stable.",
    label="observe_p1_stable",
)
```

What compiles:

- `all_stable` is an ordinary claim with a formula payload.
- The compiler generates `__forall_x_...` instance claims for `x = "p1"` and
  `x = "p2"` from the quantified formula.
- The compiler emits one deduction-style grounding strategy from `all_stable`
  to each generated instance.
- `p1_stable` is a separate authored claim. If the package wants it to be the
  same semantic node as the generated `Stable(p1)` instance, the author should
  add an explicit relation or reuse the generated-instance pattern through a
  future higher-level API. Gaia does not guess identity from similar prose.

This last point matters. Predicate formulas make structure explicit, but they
do not replace canonicalization or relation review. Two statements that look
similar to a human still need an explicit identity/equivalence path before Gaia
treats them as the same node.

---

## 8. How To Choose The Right Surface

| Need | Use |
|---|---|
| A simple scientific assertion | `claim("...")` |
| Background text with no truth variable | `note("...")` |
| A scalar parameter value | `parameter(variable, value, ...)` |
| Observed primitive values | `claim(formula=...)` plus `observe(...)` |
| Boolean structure over existing claims | `claim(formula=land(...))`, `implies(...)`, etc. |
| A finite-domain universal or existential claim | `claim(formula=forall(...))` / `claim(formula=exists(...))` |
| A reviewable derivation between claims | `derive(conclusion, given=..., rationale=...)` |
| A probabilistic likelihood relation | `infer(...)` or `gaia.engine.bayes` |
| A hypothesized relation not ready for semantics | `candidate_relation(claims=[...], pattern=...)` |

Do not hide semantic structure in prose if the compiler or reviewer needs to
inspect it. Conversely, do not build a formula AST when the claim is simply a
closed proposition.

---

## 9. Relationship To Other Gaia Docs

- [DSL API Reference](../../reference/engine/lang/dsl.md) lists the generated per-name API surface.
- [Knowledge Types and Reasoning Semantics](knowledge-and-reasoning.md)
  explains how `Claim.formula`, `ClaimKind`, actions, and formula lowering fit
  into the broader Gaia Lang model.
- [Gaia IR Structure](../gaia-ir/02-gaia-ir.md) defines the persistent IR
  objects that formula lowering emits.
- [Lowering](../gaia-ir/07-lowering.md) explains the backend-facing boundary
  from IR to factor graph.
- [BP Inference](../bp/inference.md) explains how the ground factor graph is
  consumed by the inference backend.

The short version:

```text
Gaia Lang formula AST
  -> compile
  -> ground Gaia IR claims/operators/strategies
  -> lower_local_graph(...)
  -> BP / exact inference over binary variables
```

Predicate logic is the first step of that pipeline, not a replacement for the
rest of it.
