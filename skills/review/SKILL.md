---
name: review
description: "Assign priors to Gaia knowledge packages via priors.py — prior assignment guide, BP result interpretation, and iteration workflow."
---

## 1. Overview

Priors are set via two mechanisms:

1. **`priors.py`** — assigns priors to leaf claims (independent premises). Exports a `PRIORS: dict` mapping Knowledge objects to `(prior, justification)` tuples.
2. **Inline `reason+prior` pairing** — strategies accept `prior=` directly in the DSL (e.g., `support(..., prior=0.85, reason="...")`).

Both are baked into claim metadata at compile time. `gaia infer` reads metadata directly — no separate sidecar file needed.

### Pre-Review: Inspect the Package

Before writing `priors.py`, use `gaia check` to understand the package structure and prior coverage:

```bash
gaia check .                          # Summary: independent claims annotated with prior status
gaia check --hole .                   # All independent claims: holes (no prior) + covered (with prior)
gaia check --brief .                  # Per-module overview: claims, strategies, operators
gaia check --show <module_name> .     # Expanded module: full claim content + warrant trees
gaia check --show <claim_label> .     # Specific claim's warrant tree with premises
```

**`gaia check .`** annotates each independent premise with `prior=X` or `⚠ no prior (defaults to 0.5)`. Shows a "Holes (no prior set): N" count in the summary.

**`gaia check --hole .`** splits all independent claims into **Holes** (QID, content, status) and **Covered** (prior value, justification). See §4 for the review workflow built around this output.

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

## 2. priors.py

Create `src/<package>/priors.py`:

```python
from . import obs, hypothesis, evidence

PRIORS: dict = {
    obs: (0.9, "Well-documented experimental result."),
    hypothesis: (0.5, "Theoretical prediction, not yet confirmed."),
    evidence: (0.8, "Consistent with multiple observations."),
}
```

The file must export a `PRIORS` dict. Each key is a Knowledge object imported from the package; each value is a `(prior_float, justification_string)` tuple.

`apply_package_priors()` discovers `priors.py` automatically at load time and writes `prior` into each claim's metadata before compilation.

## 3. What Needs Priors

Use `gaia check --hole` to identify hole claims (independent premises without priors), and `gaia check --brief` to see the full structure. The output classifies claims by role:

- **Independent (need prior):** Listed under "Independent premises" — these MUST have priors in `priors.py`
- **Derived (BP propagates):** Do NOT set priors — inference assigns 0.5 automatically
- **Background-only:** Need priors (typically 0.90-0.95)
- **Orphaned:** Need priors to avoid inference errors

| What | Where to set prior |
|------|--------------------|
| Leaf claim (not derived by any strategy) | `priors.py` |
| Orphaned claim (only used as background) | `priors.py` (typically 0.90-0.95) |
| `support` / `deduction` / `compare` warrant | Inline `prior=` in DSL |
| `infer` strategy CPT | `conditional_probabilities` in review sidecar (legacy) |
| Other named strategies (analogy, etc.) | Auto-formalized, deterministic |
| `induction` / `composite` | Review sub-strategies individually |

**Derived conclusions** (claims that ARE the conclusion of a strategy): do NOT set a prior. The inference engine automatically assigns uninformative priors (0.5); their beliefs are entirely determined by BP propagation. Setting an explicit prior double-counts evidence.

### Review workflow

1. **`gaia check --brief .`** — review the package structure and warrant priors. Check that `support`/`compare` warrant priors (`prior=` in DSL) reflect reasoning strength, and that `composite` strategy warrant priors are reasonable. Verify operator semantics (contradiction vs complement, see §5).
2. **`gaia check --hole .`** — shows all independent claims: holes (missing prior, with content and QID) and covered (with prior value and justification). Review covered priors for reasonableness; identify holes to fill.
3. **Write `priors.py`** — for each hole, assign a prior (see §5 for guidance). Use `gaia check --show <label> .` when you need the full warrant tree for context. Adjust any covered priors or DSL warrant priors that look wrong.
4. **`gaia check --hole .`** — confirm "All independent claims have priors assigned."
5. **`gaia infer .`** — run BP and interpret results (see §6).

## 4. Prior Assignment Guide

### How to choose priors

| Evidence level | Prior range | Examples |
|---------------|-------------|---------|
| Well-established fact | 0.85-0.95 | Reproducible experiments, textbook results |
| Supported by evidence | 0.65-0.85 | Multiple consistent observations |
| Tentative / uncertain | 0.40-0.65 | Single observation, theoretical prediction |
| Weak / speculative | 0.20-0.40 | Extrapolation, analogy |

### Prior on support/deduction warrant

For `support()` and `deduction()`, the prior on the implication warrant is specified directly in the DSL via the `prior=` parameter. Ask: "If all premises are definitely true, how confident am I in the conclusion?"

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
- If Obs is a mild subjective improvement (e.g., reduced pain score): pi(Alt) should be moderate (~0.5), because placebo effect commonly produces such outcomes
- If Obs is a large objective change (e.g., tumor shrank 80%): pi(Alt) should be very low (~0.1), because placebo effect cannot explain this magnitude of change
- Key: pi(Alt) is NOT "does the placebo effect exist?" (it does) — it is "can it account for **this specific observation**?"

**Rule of thumb:** If pi(Alt) >= pi(H), the abduction provides little support for H. Either the evidence is genuinely weak, or pi(Alt) is overestimated.

## 5. Interpret BP Results

After `gaia infer .`, check:

| Check | Normal | Abnormal |
|-------|--------|----------|
| Independent premises | belief approx prior (small change) | belief significantly pulled down -- downstream constraint conflict |
| Derived conclusions | belief > 0.5 (pulled up) | belief < 0.5 -- see below |
| Contradiction | one side high, one low ("picks a side") | both low -- prior allocation problem |

### Common problems and fixes

**Derived conclusion belief too low (< 0.3):**

- Reasoning chain too deep -- multiplicative effect. Use `composite` to control depth.
- Premise priors too low. Revisit `priors.py`.
- Strategy `prior=` too low.

**Contradiction does not "pick a side":**

- Both sides' priors do not reflect the actual evidence strength difference.
- Fix: lower the prior of the side that should be refuted.

**Derived conclusion belief approx 0.5 (not pulled up):**

- Reasoning chain is broken -- some `support` strategy missing a `prior=`, or an `infer` strategy missing parameters.
- Check that all `support` strategies have `prior=` specified in the DSL.

## 6. Complete Example

```python
# src/my_package/priors.py
from . import obs, hypothesis, evidence

PRIORS: dict = {
    # Leaf claims -- need priors
    obs: (0.9, "Well-documented experimental result."),
    hypothesis: (0.5, "Theoretical prediction, not yet confirmed."),
    evidence: (0.8, "Consistent with multiple observations."),
}
```

```python
# src/my_package/s2_results.py (inline warrant priors)
strat_h_explains = support(
    [hypothesis], obs,
    reason="Hypothesis predicts the observation", prior=0.9,
)
strat_alt_explains = support(
    [alt_hypothesis], obs,
    reason="Alternative poorly matches observation", prior=0.15,
)
```

## Legacy: Review Sidecar (Deprecated)

> **Deprecated since gaia-lang 0.4.2.** The review sidecar pattern (`ReviewBundle` / `review_claim()` / `review_strategy()`) is retained for backward compatibility but will be removed in a future major release. Use `priors.py` and inline `reason+prior` pairing instead.

The old API is still importable from `gaia.review`:

```python
from gaia.review import ReviewBundle, review_claim, review_strategy, review_generated_claim
```

Calling any of these functions emits a `DeprecationWarning`. Existing packages with `reviews/self_review.py` will continue to work, but new packages should use `priors.py`.
