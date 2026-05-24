"""The one-page ``CHEATSHEET.md`` distillation of the Gaia DSL surface.

A tight, copy-pasteable reference: every verb / term / distribution with a
one-line example. Source material: ``docs/for-users/language-reference.md``
(the existing cheat sheet) + the README v0.5 surface table. Kept static
here so ``gaia sdk`` needs no docs-tree access at runtime.
"""

from __future__ import annotations

CHEATSHEET_MD = """\
# Gaia DSL cheat sheet (v0.5)

One page, every verb/term/distribution with a copy-pasteable example.
**Author your DSL directly** — write these statements in
`src/<pkg>/__init__.py` (or your own modules). The `gaia author` CLI is an
optional convenience; it writes the same statements into the re-exported
`authored/` submodule.

## Imports

```python
from gaia.engine.lang import (
    claim, note, question,                                  # Knowledge
    Variable, Nat, Real, Probability, Bool, Constant,       # Formula terms
    parameter,                                              # Structured formula claims
    ClaimAtom, land, lnot, lor, implies, iff, equals,       # Propositional formula helpers
    forall, exists,                                         # First-order quantifiers
    contradict, equal, exclusive, associate,                # Reviewable relations
    depends_on, candidate_relation, materialize,            # Scaffold annotations
    observe, derive, compute, infer, decompose,             # Recommended actions
    compose, composition,                                   # Action composition
    register_prior,                                         # External prior records
    Normal, LogNormal, Beta, Gamma, StudentT,               # Distribution factories
    Cauchy, ChiSquared, Binomial, Poisson,
)
import gaia.engine.bayes as bayes                           # Bayes hypothesis comparison
```

## Knowledge

```python
h = claim("Heavier bodies fall faster in air.", title="Daily observation")
n = note("Framing: this is a thought experiment, not an observed fact.")
q = question("Does weight set the natural falling speed?")
```

## Reviewable relations

```python
equal(prediction, observation, rationale="Prediction matches the data.")
contradict(pred_a, pred_b, rationale="Same setup, incompatible predictions.")
exclusive(model_a, model_b, rationale="Competing explanations of one fact.")
associate(claim_a, claim_b, rationale="Loosely related; not entailment.")
```

## Recommended actions

```python
derive("Composite should fall faster.", given=[model_a], rationale="...")
observe("F1 offspring are uniformly dominant.", rationale="Qualitative F1 result.")
compute(result, fn=my_fn, given=[x, y], rationale="Deterministic computation.")
infer(hypothesis, given=[evidence], rationale="Probabilistic support.")
decompose(whole, parts=[part_a, part_b], rationale="Whole = sum of parts.")
```

## Scaffold annotations

```python
depends_on(downstream, given=[upstream])
candidate_relation(claims=[claim_a, claim_b], pattern="equal")
materialize(candidate)
```

## Action composition

```python
@composition
def my_argument():
    ...                                # group several actions as one unit
compose(action_a, action_b)            # combine actions explicitly
```

## Typed terms + formulas

```python
k = Variable(symbol="k", domain=Nat, value=295)            # Nat / Real / Probability / Bool
c = Constant(value=3.14, domain=Real)
parameter("p is a probability", predicate=equals(p, Constant(value=0.75, domain=Probability)))
land(a, b); lnot(a); lor(a, b)                             # ∧ / ¬ / ∨
implies(a, b); iff(a, b); equals(x, y)                    # → / ↔ / =
forall(x, body); exists(x, body)                          # ∀ / ∃
```

## Priors

```python
register_prior(daily_observation, value=0.90,
               justification="Familiar empirical background.")
```

## Distributions

```python
Normal("noise", mu=0.0, sigma=1.0)
LogNormal("scale", mu=0.0, sigma=1.0)
Beta("rate", alpha=2.0, beta=2.0)
Gamma("shape", alpha=2.0, beta=1.0)
StudentT("heavy tails", nu=3.0, mu=0.0, sigma=1.0)
Cauchy("location", x0=0.0, gamma=1.0)
ChiSquared("variance", k=2.0)
Binomial("F2 dominant count", n=395, p=3/4)
Poisson("event count", lam=4.0)
```

## Bayes: hypothesis vs data

```python
import gaia.engine.bayes as bayes

m1 = bayes.model(mendel_model, observable=k_dominant,
                 distribution=Binomial("Mendel 3:1", n=395, p=3/4),
                 rationale="...")
m2 = bayes.model(diffuse_model, observable=k_dominant,
                 distribution=Binomial("diffuse", n=395, p=0.5),
                 rationale="...")
bayes.compare(count_observation, models=[m1, m2], rationale="...")
```

---

Full per-symbol reference (signatures + docstrings) sits alongside this
file in the SDK reference directory. After authoring, compile and run:

```bash
gaia build compile ./my-pkg-gaia
gaia run infer ./my-pkg-gaia
```
"""


__all__ = ["CHEATSHEET_MD"]
