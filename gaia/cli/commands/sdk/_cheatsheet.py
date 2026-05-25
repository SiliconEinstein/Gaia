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

## Authoring guidelines (read first)

1. **Logical structure is the foundation; computed belief is a reference.**
   Get the relations right — which claims premise which, which observations
   constrain which hypotheses, which assertions are mutually exclusive. The
   posterior `gaia run infer` returns reflects the structure you wrote; if
   the structure is wrong, the number is precisely as wrong. Treat a
   suspicious posterior as a structural-debugging signal first, not as the
   final answer.

2. **Avoid double-counting evidence.** Each piece of evidence should enter
   the graph at most once. If observation A is downstream of observation B
   (or both are downstream of a common cause), independently relating both
   to the same hypothesis inflates posterior confidence. Model the shared
   cause as a single Claim and connect it ONCE.

3. **Surface weak points as Claims, not buried assumptions.** If a reasoning
   step depends on something you're not fully confident in (small sample,
   indirect proxy, a plausible-but-untested mechanism), do NOT bury it in a
   `rationale` string. Extract it to its own Claim, put it in `given=[...]`,
   and `register_prior` it with your honest uncertainty so that uncertainty
   propagates through inference.

## Imports

```python
from gaia.engine.lang import (
    claim, note, question,                                  # Knowledge
    Variable, Nat, Real, Probability, Bool, Constant,       # Formula terms
    parameter,                                              # Structured formula claims
    ClaimAtom, land, lnot, lor, implies, iff, equals,       # Propositional formula helpers
    forall, exists,                                         # First-order quantifiers
    contradict, equal, exclusive,                           # Reviewable relations — hard
    associate,                                              # Reviewable relations — soft
    depends_on, candidate_relation, materialize,            # Scaffold annotations
    observe, derive, compute, decompose,                    # Reasoning actions — hard
    infer,                                                  # Reasoning actions — soft
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
# `claim` is a proposition that participates in BP and carries an optional
# prior probability. If unset, the claim is treated as MaxEnt (no external
# prior). Use `register_prior(h, value=..., justification=...)` to attach one.

n = note("Framing: this is a thought experiment, not an observed fact.")
# `note` is context / framing only — no truth value, does not participate in BP.

q = question("Does weight set the natural falling speed?")
# `question` records an open question — no truth value of its own.
```

## Reviewable relations — hard (no probability parameters)

Deterministic logical assertions over the relata's truth values. No conditional
probabilities; lowering uses fixed factors.

```python
equal(prediction, observation, rationale="...")     # both must hold the same truth value
contradict(pred_a, pred_b, rationale="...")         # the two cannot both be true
exclusive(model_a, model_b, rationale="...")        # competing explanations; at most one is true
```

## Reviewable relations — soft (explicit conditional probabilities)

You estimate both directions of the association. There is no logical entailment.

```python
associate(claim_a, claim_b,
          p_a_given_b=0.85,   # P(claim_a is true | claim_b is true)
          p_b_given_a=0.40,   # P(claim_b is true | claim_a is true)
          rationale="...")
```

## Reasoning actions — hard (no probability parameters)

No probability arguments; relate claims by deterministic logic, or, for `observe`,
by pinning the observed claim's prior to ~1 − ε.

If a derivation depends on an uncertain intermediate step (small n, indirect
proxy, contested mechanism), do **NOT** bury it in `rationale`. Extract it as a
separate Claim, put it in `given=[...]`, and `register_prior` it so the
uncertainty enters the inference. This makes weak points explicit and reviewable.

```python
derive("Composite should fall faster.",
       given=[model_a, weak_step_premise],   # premises (extract uncertain steps to their own Claims)
       rationale="...")

observe("F1 offspring are uniformly dominant.", rationale="...")
# Pins the observed claim's prior to ~1 − ε.

compute(result, fn=my_fn, given=[x, y], rationale="...")
# Deterministic functional computation: result = fn(x, y).

decompose(whole, parts=[part_a, part_b], formula=..., rationale="...")
# whole ≡ formula(parts) — equivalence by decomposition.
```

## Reasoning actions — soft (explicit conditional probabilities)

The single soft reasoning action. Bayesian update: how strongly does the
evidence shift belief in the hypothesis? YOU estimate the two conditionals.

```python
infer(evidence,
      hypothesis=H,
      given=[scope_assumption_1, scope_assumption_2],   # assumptions under which the likelihoods hold
      p_e_given_h=0.90,        # P(observing this evidence | H is true)
      p_e_given_not_h=0.10,    # P(observing this evidence | H is false)
      rationale="...")
```

The likelihood ratio `p_e_given_h / p_e_given_not_h` controls update strength.
A ratio of 1 produces no update; the larger the ratio, the more the evidence
pushes posterior(H) above prior(H). If any claim in `given=` is uncertain
(carries a prior < 1), that uncertainty attenuates the update — surface the
scope assumptions honestly rather than asserting them silently.

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
