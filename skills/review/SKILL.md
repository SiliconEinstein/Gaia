---
name: review
description: "Write review sidecars for Gaia knowledge packages — assign priors, strategy parameters, interpret BP results, and iterate."
---

## 1. Overview

A review sidecar assigns probability parameters to a knowledge package's claims and strategies. These parameters drive belief propagation (BP) inference. Multiple reviewers can independently review the same package, each producing a different sidecar.

### Pre-Review: Inspect the Package

Before writing the review sidecar, use `gaia check --brief` to understand the package structure:

```bash
gaia check --brief .                  # Overview: all modules, claims, strategies with priors
gaia check --show <module_name> .     # Expanded module: full claim content + warrant trees
gaia check --show <claim_label> .     # Detail: specific claim's warrant tree with premises
```

**`--brief` output shows:**
- Per-module breakdown of settings, claims (with role: independent/derived/structural), and strategies
- Strategy summaries with premise labels, conclusion, prior, and reason
- Operator constraints (contradiction, equivalence) with their targets

**`--show <module>` expands:**
- Full claim content (not truncated) with role and prior
- Complete warrant trees for each strategy, including composite sub-strategy expansion
- All operator details

**`--show <label>` expands:**
- A specific claim's content and all strategies that conclude to it
- Premises listed with their content, enabling prior assessment

Use `--brief` to identify which claims need priors (independent premises), then use `--show` to read the full content before assigning priors. Every claim and strategy should have a visible name — if anything shows as `_anon_xxx`, the package has unnamed nodes that should be fixed before review.

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

Assign parameters to a strategy. Only needed for `infer` strategies (full CPT). `support`, `deduction`, `compare`, and other named strategies carry their parameters in the DSL and do not need review_strategy.

- `subject`: reference to the strategy variable from the package
- `conditional_probability`: single float (legacy, for backward compatibility)
- `conditional_probabilities`: list of 2^N floats for `infer` (full CPT)
- `judgment`: `"formalized"`, `"tentative"`, etc.

### review_generated_claim(subject, role, *, prior, judgment, justification, occurrence=0, metadata=None)

Assign a prior to an auto-generated claim (e.g., abduction's alternative).

- `subject`: the Strategy that generated the claim
- `role`: `"alternative_explanation"` for abduction alternatives
- `prior`: float 0-1
- `occurrence`: index when a strategy generates multiple claims of the same role (default 0)

## 4. What Needs Review

Use `gaia check --brief` to identify what needs review. The output classifies claims by role:

- **Independent (need prior):** Listed under "Independent premises" — these MUST have priors in the review sidecar or `priors.py`
- **Derived (BP propagates):** Do NOT set priors — inference assigns 0.5 automatically
- **Background-only:** Need priors (typically 0.90-0.95)
- **Orphaned:** Need priors to avoid inference errors

| What | Function | Required parameter |
|------|----------|--------------------|
| Leaf claim (not derived by any strategy) | `review_claim` | `prior` |
| Orphaned claim (only used as background) | `review_claim` | `prior` (typically 0.90-0.95) |
| `infer` strategy | `review_strategy` | `conditional_probabilities` (2^N floats) |
| Auto-generated abduction alternative | `review_generated_claim` | `prior` |
| `support` strategy | No review needed | Prior specified in DSL (author-specified) |
| `deduction` strategy | No review needed | Deterministic |
| `compare` strategy | No review needed | Prior specified in DSL (author-specified) |
| Other named strategies (analogy, etc.) | No review needed | Auto-formalized, deterministic |
| `induction` | No direct review | Review sub-strategies individually |
| `composite` | No direct review | Review leaf sub-strategies |

**Derived conclusions** (claims that ARE the conclusion of a strategy): do NOT set a prior. The inference engine automatically assigns uninformative priors (0.5); their beliefs are entirely determined by BP propagation. Setting an explicit prior double-counts evidence.

## 5. Prior Assignment Guide

### How to choose priors

| Evidence level | Prior range | Examples |
|---------------|-------------|---------|
| Well-established fact | 0.85-0.95 | Reproducible experiments, textbook results |
| Supported by evidence | 0.65-0.85 | Multiple consistent observations |
| Tentative / uncertain | 0.40-0.65 | Single observation, theoretical prediction |
| Weak / speculative | 0.20-0.40 | Extrapolation, analogy |

### Prior on support/deduction warrant

For `support()` and `deduction()`, the prior on the implication warrant is specified directly in the DSL via the `prior=` parameter (not in the review sidecar). Ask: "If all premises are definitely true, how confident am I in the conclusion?"

| Reasoning quality | Prior value | Examples |
|-------------------|-------------|---------|
| Near-certain (rigid deduction) | 0.95-0.99 | Mathematical proofs, logical syllogisms |
| Strong support | 0.80-0.95 | Straightforward numerical calculation |
| Reliable but approximate | 0.60-0.80 | Standard approximation method |
| Moderate confidence | 0.40-0.60 | Empirical rule of thumb |

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

- Reasoning chain is broken -- some `support` strategy missing a `prior`, or an `infer` strategy missing review parameters.
- Check that all `support` strategies have `prior=` specified in the DSL.
- Check review sidecar for missing `infer` strategy reviews.

## 7. Complete Example

```python
from gaia.review import ReviewBundle, review_claim, review_strategy, review_generated_claim
from .. import obs, hypothesis, evidence, conclusion, _strat_abd

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

        # Note: support/deduction/compare strategies carry their priors in the DSL
        # (via the prior= parameter) and do NOT need review_strategy.
        # Only `infer` strategies need review_strategy with conditional_probabilities.

        # abduction alternative -- needs prior reflecting explanatory power
        review_generated_claim(_strat_abd, "alternative_explanation",
            prior=0.3,
            judgment="tentative",
            justification="Alternative theory predicts 1.9K but observation is 1.2K -- poor explanatory fit."),
    ],
)
```
