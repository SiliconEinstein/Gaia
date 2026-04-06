---
name: review
description: "Write review sidecars for Gaia knowledge packages — assign priors, strategy parameters, interpret BP results, and iterate."
---

## 1. Overview

A review sidecar assigns probability parameters to a knowledge package's claims and strategies. These parameters drive belief propagation (BP) inference. Multiple reviewers can independently review the same package, each producing a different sidecar.

## 2. File Location

Reviews live in `<package>/reviews/`:

```
src/my_package/
    __init__.py
    reviews/
        __init__.py
        self_review.py
```

## 3. API

```python
from gaia.review import ReviewBundle, review_claim, review_strategy, review_generated_claim
```

### ReviewBundle

```python
REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[...],
)
```

The file must export a `REVIEW` variable. `source_id` identifies the reviewer.

### review_claim(subject, *, prior, judgment, justification, metadata=None)

Assign a prior probability to a claim.

- `subject`: reference to the claim variable from the package
- `prior`: float 0-1, your belief that the claim is true
- `judgment`: `"supporting"`, `"tentative"`, `"opposing"`, etc.
- `justification`: why you chose this prior

### review_strategy(subject, *, conditional_probability=None, conditional_probabilities=None, judgment, justification, metadata=None)

Assign parameters to a strategy.

- `subject`: reference to the strategy variable from the package
- `conditional_probability`: single float for `noisy_and` (P(conclusion | all premises true))
- `conditional_probabilities`: list of 2^N floats for `infer` (full CPT)
- `judgment`: `"formalized"`, `"tentative"`, etc.

### review_generated_claim(subject, role, *, prior, judgment, justification, occurrence=0, metadata=None)

Assign a prior to an auto-generated claim (e.g., abduction's alternative).

- `subject`: the Strategy that generated the claim
- `role`: `"alternative_explanation"` for abduction alternatives
- `prior`: float 0-1
- `occurrence`: index when a strategy generates multiple claims of the same role (default 0)

## 4. What Needs Review

| What | Function | Required parameter |
|------|----------|--------------------|
| Leaf claim (not derived by any strategy) | `review_claim` | `prior` |
| Orphaned claim (only used as background) | `review_claim` | `prior` (typically 0.90-0.95) |
| `noisy_and` strategy | `review_strategy` | `conditional_probability` (single float) |
| `infer` strategy | `review_strategy` | `conditional_probabilities` (2^N floats) |
| Auto-generated abduction alternative | `review_generated_claim` | `prior` |
| `deduction` strategy | No review needed | Deterministic |
| Other named strategies (abduction, analogy, etc.) | No review needed | Auto-formalized, deterministic |
| `induction` | No direct review | Review sub-strategies individually |
| `composite` | No direct review | Review leaf sub-strategies |

**Derived conclusions** (claims that ARE the conclusion of a strategy): do NOT set a prior. Their belief is entirely determined by BP propagation.

**Derived conclusions — prior = 0.5 or omit.** If you set a prior on a derived claim, use 0.5 (uninformative). A high prior (e.g., 0.85) double-counts evidence: the reviewer's judgment and the reasoning chain both reflect the same data. Let BP determine derived beliefs from leaf priors and strategy parameters alone.

## 5. Prior Assignment Guide

### How to choose priors

| Evidence level | Prior range | Examples |
|---------------|-------------|---------|
| Well-established fact | 0.85-0.95 | Reproducible experiments, textbook results |
| Supported by evidence | 0.65-0.85 | Multiple consistent observations |
| Tentative / uncertain | 0.40-0.65 | Single observation, theoretical prediction |
| Weak / speculative | 0.20-0.40 | Extrapolation, analogy |

### conditional_probability for noisy_and

This is P(conclusion | all premises true). Ask: "If all premises are definitely true, how confident am I in the conclusion?"

| Reasoning quality | Value | Examples |
|-------------------|-------|---------|
| Near-certain computation | 0.90-0.99 | Straightforward numerical calculation |
| Reliable but approximate | 0.70-0.90 | Standard approximation method |
| Moderate confidence | 0.50-0.70 | Empirical rule of thumb |

### pi(Alt) for abduction alternatives -- CRITICAL

The prior on an abduction alternative represents **explanatory power**: "Can Alt alone explain Obs, without the hypothesis?"

- NOT "Is Alt's calculation correct?"
- NOT "Is Alt true in general?"
- But: "Does Alt account for the specific observation?"

Example: Obs = "patient's symptoms resolved after taking the drug", H = "the drug is effective", Alt = "placebo effect"

- The question is: can the placebo effect **alone explain this specific observation**?
- If Obs is a mild subjective improvement (e.g., reduced pain score): π(Alt) should be moderate (~0.5), because placebo effect commonly produces such outcomes
- If Obs is a large objective change (e.g., tumor shrank 80%): π(Alt) should be very low (~0.1), because placebo effect cannot explain this magnitude of change
- Key: π(Alt) is NOT "does the placebo effect exist?" (it does) — it is "can it account for **this specific observation**?"

**Rule of thumb:** If pi(Alt) >= pi(H), the abduction provides little support for H. Either the evidence is genuinely weak, or pi(Alt) is overestimated.

## 6. Interpret BP Results

After `gaia infer .`, check:

| Check | Normal | Abnormal |
|-------|--------|----------|
| Independent premises | belief approx prior (small change) | belief significantly pulled down -- downstream constraint conflict |
| Derived conclusions | belief > 0.5 (pulled up) | belief < 0.5 -- see below |
| Contradiction | one side high, one low ("picks a side") | both low -- prior allocation problem |

### Common problems and fixes

**Derived conclusion belief too low (< 0.3):**

- Reasoning chain too deep -- multiplicative effect. Use `composite` to control depth.
- Premise priors too low. Revisit review sidecar.
- Strategy `conditional_probability` too low.

**Contradiction does not "pick a side":**

- Both sides' priors do not reflect the actual evidence strength difference.
- Fix: lower the prior of the side that should be refuted.

**Derived conclusion belief approx 0.5 (not pulled up):**

- Reasoning chain is broken -- some strategy missing `conditional_probability`.
- Check review sidecar for missing strategy reviews.

## 7. Complete Example

```python
from gaia.review import ReviewBundle, review_claim, review_strategy, review_generated_claim
from .. import obs, hypothesis, evidence, conclusion, _strat_na, _strat_abd

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        # Leaf claims -- need priors
        review_claim(obs, prior=0.9,
            judgment="supporting",
            justification="Well-documented experimental result."),
        review_claim(hypothesis, prior=0.5,
            judgment="tentative",
            justification="Theoretical prediction, not yet confirmed."),
        review_claim(evidence, prior=0.8,
            judgment="supporting",
            justification="Consistent with multiple observations."),

        # noisy_and strategy -- needs conditional_probability
        review_strategy(_strat_na,
            conditional_probability=0.85,
            judgment="formalized",
            justification="Standard computation, small approximation error."),

        # abduction alternative -- needs prior reflecting explanatory power
        review_generated_claim(_strat_abd, "alternative_explanation",
            prior=0.3,
            judgment="tentative",
            justification="Alternative theory predicts 1.9K but observation is 1.2K -- poor explanatory fit."),
    ],
)
```
