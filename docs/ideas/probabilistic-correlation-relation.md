# Probabilistic Correlation Relation for Gaia v0.5

> **Status:** Idea
>
> This note records a possible replacement for the current v6 `infer()`
> surface. It is not an implementation plan. The goal is to clarify the
> semantic center before changing the DSL, IR, or BP lowering.

## 1. Motivation

The current v6 design exposes statistical evidence as:

```python
infer(
    hypothesis=H,
    evidence=E,
    p_e_given_h=...,
    p_e_given_not_h=...,
)
```

This is mathematically standard when there is a generative model, but it is
often awkward for LLM-assisted scientific formalization:

- `not H` is usually an under-specified contrast class.
- `not E` is often not a clean logical complement of the evidence event.
- LLMs are usually better at judging positive relationships than open-ended
  complement classes.
- The word `infer` sounds like a reasoning action, while the object being
  authored is really a probabilistic relation between two Claims.

The design question is whether Gaia should treat this as a `Relate`-like
primitive rather than a `Support`-like or `Infer`-like primitive.

## 2. Jaynes Interpretation

In Jaynes-style probability, probabilities are always conditional on an
information state:

```text
P(A | I)
```

For Gaia, `I` must be a declared, reviewable context, not the LLM's hidden chain
of thought. It may include:

- the definitions of the two Claims,
- accepted background Claims and Settings,
- source excerpts or data tables,
- measurement protocol,
- sample scope or population,
- parameter ranges and error models,
- calibration rubric.

The LLM's private deliberation is not part of `I`. If a chain-of-thought step
uses a load-bearing assumption, that assumption should be promoted into a Claim,
Setting, or Context item before it can condition a Gaia probability.

## 3. Core Idea

Replace the conceptual primitive:

```text
infer H from E
```

with:

```text
A and B have a calibrated probabilistic relation under context I.
```

A possible Lang surface is:

```python
relation = correlate(
    A,
    B,
    context=[...],
    p_a_given_b=...,
    p_b_given_a=...,
    p_a=...,  # or p_b=...
    rationale="...",
)
```

This declares a binary probabilistic relation:

```text
P(A | B, I)
P(B | A, I)
P(A | I) or P(B | I)
```

At least one base-rate anchor is required, because `P(A|B,I)` and `P(B|A,I)`
alone only determine the ratio:

```text
P(A | I) / P(B | I) = P(A | B, I) / P(B | A, I)
```

If both base rates are provided, Gaia checks coherence:

```text
P(A | B, I) * P(B | I) ~= P(B | A, I) * P(A | I)
```

## 4. Why This Is Better Than Bare `infer`

The relation is not fundamentally:

```text
H -> E
```

or:

```text
E -> H
```

Those are two coordinate systems for the same joint distribution. The authored
object is the joint relation between two claims under a declared context.

For scientific model-based cases, users may still prefer likelihood language:

```text
P(E | H, I)
P(E | A, I)
```

where `A` is an explicit contrast or baseline. For LLM-assisted judgment, users
may prefer positive-direction questions:

```text
P(E | H, I)
P(H | E, I)
P(E | I)
```

Both can lower to a binary factor after coherence checks. The key improvement is
that Gaia no longer forces authors to name `not H` or `not E` unless those
complements are actually meaningful in the domain.

## 5. Helper Claim Semantics

`correlate()` should return a relation helper Claim, not a conclusion Claim:

```text
"A and B have a calibrated probabilistic relation under I."
```

The helper is reviewable. It represents the assertion that the relation is
well-defined and calibrated, not that either `A` or `B` is true.

Gaia may classify the relation shape from the conditional probabilities and
base rates:

```text
positive_association
negative_association
near_independence
approximate_equivalence
asymmetric_evidence_for_a
asymmetric_evidence_for_b
incoherent
```

Classification should be based on relative update, not only absolute
conditional probabilities.

For example, `B` is evidence for `A` when:

```text
P(A | B, I) > P(A | I)
```

or, in odds form:

```text
logit P(A | B, I) - logit P(A | I) > 0
```

This matters for rare hypotheses. `P(A|B,I)` can be small in absolute terms but
still be strong evidence if it greatly exceeds `P(A|I)`.

## 6. Relation to Soft Logical Relations

The probabilities can also be read as soft implications:

```text
P(B | A, I)  ~=  A softly implies B
P(A | B, I)  ~=  B softly implies A
```

Therefore:

```text
approximate_equal(A, B)
```

is a special case where both directions are strong and the base rates are
compatible.

Likewise, an approximate contradiction should not be inferred merely from low
`P(A|B,I)` or low `P(B|A,I)`. It is only well-defined when the relevant
negative propositions are themselves clear:

```text
A softly implies not B
B softly implies not A
```

Because `not A` and `not B` are often hard to define, `approximate_contradict`
should be a derived or guarded relation, not the default interpretation of a
low correlation.

## 7. `evidence_for` as a Wrapper

The user-facing scientific language may still want:

```python
evidence_for(
    hypothesis=H,
    evidence=E,
    context=[...],
    calibration=...,
)
```

This can be a wrapper over `correlate(H, E, ...)`:

```text
A = H
B = E
P(A | B, I) = P(H | E, I)
P(B | A, I) = P(E | H, I)
```

It returns a relation helper Claim such as:

```text
"E is evidence for H under I."
```

This helper is more specific than the generic correlate helper, but the
probabilistic core is the same.

## 8. Relation to A/B Tests

A/B tests are not the primitive; they are calibration helpers for this
primitive.

For example:

```python
evidence_for(
    hypothesis=treatment_improves_conversion,
    evidence=observed_lift,
    context=[experiment_design],
    calibration=ABTest(
        control_successes=...,
        control_total=...,
        treatment_successes=...,
        treatment_total=...,
        prior_alpha=1.0,
        prior_beta=1.0,
        min_lift=0.0,
    ),
)
```

The A/B helper computes quantities such as:

```text
P(treatment_rate > control_rate | data, I)
Bayes factor or likelihood ratio, if a contrast model is specified
credible interval for the lift
```

The relation helper Claim is still the same kind of object: a reviewable
probabilistic relation between the hypothesis Claim and the evidence Claim.

## 9. Possible Lowering

Short term, `correlate()` can lower to the existing `Strategy(type="infer")`
conditional factor after converting the supplied calibration into a CPT. The IR
can preserve the author-facing calibration in metadata:

```json
{
  "pattern": "probabilistic_relation",
  "relation_kind": "correlate",
  "calibration": {
    "kind": "conditional_pair",
    "p_a_given_b": 0.8,
    "p_b_given_a": 0.7,
    "p_a": 0.3
  },
  "compiled": {
    "premises": ["A"],
    "conclusion": "B",
    "conditional_probabilities": [...]
  }
}
```

Medium term, Gaia may introduce a more direct BP factor for calibrated binary
relations. That would avoid forcing the relation into a directional `premises`
and `conclusion` shape.

## 10. Review Questions

ReviewManifest entries for `correlate()` should not ask whether a derivation is
valid. They should ask whether the probabilistic relation is well-defined:

- Are `A`, `B`, and context `I` defined clearly?
- Is `I` declared publicly, without hidden chain-of-thought assumptions?
- Are the conditional probabilities estimated under the same `I`?
- Is the provided base-rate anchor reasonable?
- Are the probability entries coherent?
- Does the rationale hide load-bearing assumptions that should be promoted to
  Claims or Settings?
- Is the inferred helper shape, such as evidence-for or approximate-equivalence,
  justified by relative update rather than absolute probability alone?

## 11. Non-goals

This note does not propose:

- replacing `equal()` or `contradict()` for deterministic logical relations,
- adding a full causal modeling language,
- requiring LLMs to produce exact probabilities when qualitative calibration
  would be more reliable,
- treating hidden chain-of-thought as Gaia context,
- committing to a new IR top-level primitive before the relation semantics are
  stable.

## 12. Working Recommendation

For v0.5 iteration, the cleanest path is:

1. Treat the current `infer()` concept as a probabilistic relation, not a
   support action.
2. Prototype a Lang surface named `correlate()` that returns a reviewable
   relation helper Claim.
3. Provide `evidence_for()` as a scientific wrapper over `correlate()`.
4. Keep the existing `Strategy(type="infer")` lowering path initially, but
   preserve the original calibration form in metadata.
5. Classify helper relation shape from relative update against base rates.

This keeps the semantics Jaynes-compatible while making LLM-assisted
formalization ask easier, positive-direction probability questions.
