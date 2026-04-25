---
name: gaia-lang
description: "Gaia Lang v0.5 DSL reference for authoring packages with claim/note, action verbs, relation verbs, composition, priors, and legacy boundaries."
---

# Gaia Lang DSL Reference

Use this skill when writing or editing Gaia package source code. Prefer the
current v0.5 authoring surface. Do not introduce legacy `support()`,
`noisy_and()`, `setting()`, `contradiction()`, `abduction()`, or `induction()`
unless you are intentionally editing compatibility tests or migrating an old
package.

## Imports

```python
from gaia.lang import (
    claim,
    note,
    question,
    observe,
    derive,
    compute,
    infer,
    associate,
    equal,
    contradict,
    exclusive,
    compose,
)
```

Optional Boolean helpers are also available:

```python
from gaia.lang import not_, and_, or_
```

Use `~a`, `a & b`, and `a | b` when working with `Claim` objects directly.

## Knowledge

### `claim(content, *, title=None, background=None, parameters=None, provenance=None, **metadata)`

Use `claim()` for propositions that can carry probability during inference.

```python
model = claim("The medium-resistance model explains ordinary falling in air.")
observation = claim("Heavy bodies often fall faster than light bodies in air.")
```

### `note(content, *, title=None, format="markdown", **metadata)`

Use `note()` for non-probabilistic context: definitions, setup, variable
bindings, or explanatory background. Notes are usually attached with
`background=`.

```python
setup = note("Tied-body setup: a heavy ball and a light ball are bound together.")
```

### `question(content, *, title=None, **metadata)`

Use `question()` for open research questions. Questions do not participate in
BP.

## Action Verbs

Action verbs create reviewable warrants and compile to Gaia IR. They are the
normal way to connect claims in v0.5 packages.

### `observe(conclusion, *, given=(), background=None, rationale="", label=None)`

Use for empirical observations or measurements. A root `observe(...)` claim is
still an independent probabilistic input: grounding is qualitative, not a
numeric prior.

```python
obs = observe(
    "The measured transition temperature is near 39 K.",
    rationale="Reported in the experiment.",
)
```

### `derive(conclusion, *, given=(), background=None, rationale="", label=None)`

Use when the conclusion follows deterministically once the given claims and
rationale are accepted.

```python
prediction = derive(
    "The model predicts equal falling speed in vacuum.",
    given=model,
    background=[vacuum_setup],
    rationale="If the medium causes the in-air difference, removing it removes the difference.",
)
```

### `compute(ClaimType, *, fn=None, given=(), background=None, rationale="", label=None)`

Use for deterministic calculations. It can be called directly or used as a
decorator with a `Claim` return annotation.

### `infer(evidence, *, hypothesis, p_e_given_h, p_e_given_not_h, background=None, rationale="", label=None)`

Use for an explicit probabilistic evidence link. Extract the uncertain pieces
as claims first; do not hide missing premises inside prose rationale.

```python
likelihood = infer(
    observation,
    hypothesis=model,
    p_e_given_h=0.9,
    p_e_given_not_h=0.2,
    rationale="The observation is much more likely if the model is correct.",
)
```

`infer(...)` returns a generated likelihood helper claim. Do not assign an
external prior to that helper.

### `associate(a, b, *, p_a_given_b, p_b_given_a, prior_a=None, prior_b=None, background=None, rationale="", label=None)`

Use for a symmetric probabilistic association. At least one base-rate anchor
must be available, either through `prior_a`, `prior_b`, or `priors.py`.

## Relation Verbs

Relation verbs return generated helper claims and compile to deterministic
operators.

```python
same = equal(prediction, observation, rationale="The prediction matches the observation.")
conflict = contradict(a, b, rationale="Both claims cannot hold in the same setup.")
choice = exclusive(left, right, rationale="The alternatives form a closed binary partition.")
```

Do not assign external priors to relation helper claims.

## Composition

Use `@compose(...)` when a named workflow of actions should be reviewed as a
unit.

```python
@compose(name="example:workflow", version="1.0", rationale="Reusable analysis path.")
def workflow(model):
    prediction = derive("Prediction.", given=model, rationale="Model entails it.")
    return prediction
```

The decorated function returns its normal conclusion claim. The runtime records
a `Compose` action containing the child actions, inferred inputs, background,
and conclusion.

## Priors

External priors belong only on independent probabilistic inputs to exported
goals.

Put them in `priors.py`:

```python
from . import observation, model

PRIORS: dict = {
    observation: (0.9, "Directly measured."),
    model: (0.5, "Neutral before this argument."),
}
```

Do not assign priors to derived claims, relation helpers, structural expression
helpers, likelihood helpers, association helpers, or generated formalization
internals. Use `gaia check --hole .` to identify independent degrees of
freedom.

## Labels And Exports

Let `gaia compile` infer labels from public Python variable names. Do not set
`.label` manually in normal package code.

```python
main_result = claim("The main result.")
__all__ = ["main_result"]
```

Only define `__all__` in the package `__init__.py`. Use it for exported
cross-package interface claims.

## Legacy Boundary

The following APIs exist only for compatibility and tests:

- `setting()` / `context()` -> use `note()`
- `contradiction()` / `equivalence()` / `complement()` / `disjunction()` -> use relation verbs or Boolean helpers
- `support()` / `noisy_and()` / old positional `infer([premises], conclusion)` -> use `derive()` or explicit probabilistic `infer(...)`
- `deduction()` -> use `derive()`
- `abduction()` / `induction()` / `composite()` -> model the claims, relations, and probabilistic links explicitly, or use `@compose(...)` for reusable workflows

If you must touch legacy code, keep it isolated and make tests explicit with the
`legacy_dsl` marker.

## Anti-Patterns

| Anti-pattern | Use instead |
|--------------|-------------|
| `noisy_and(...)` in package source | `derive(...)` or explicit `infer(...)` |
| `support(..., prior=...)` for vague uncertainty | Extract uncertain premises as claims and use `infer(...)` when probabilistic |
| `setting(...)` for background | `note(...)` |
| `contradiction(a, b, prior=...)` | `contradict(a, b, rationale=...)` |
| Priors on derived/helper claims | Priors only on independent probabilistic inputs |
| Manual `.label = ...` | Assign to a public Python variable |
