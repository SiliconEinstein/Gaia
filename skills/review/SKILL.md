---
name: review
description: "Assign priors to Gaia v0.5 packages with priors.py, inspect hole reports, interpret BP output, and iterate on claim structure."
---

# Gaia Review And Prior Assignment

Use this skill when assigning priors, reading `gaia check --hole`, or
interpreting `gaia infer` results.

The current v0.5 review contract is simple:

- external priors go in `priors.py`;
- priors belong only to independent probabilistic inputs;
- derived claims, relation helpers, likelihood helpers, association helpers,
  and structural helpers do not receive external priors;
- root `observe(...)` claims are still independent probabilistic inputs because
  grounding/review is qualitative, not numeric;
- review sidecar APIs (`gaia.review`, `ReviewBundle`, `review_claim`,
  `review_strategy`) have been removed.

## Inspect The Package

Run these before writing priors:

```bash
gaia check .
gaia check --hole .
gaia check --brief .
gaia check --show <module_or_claim> .
```

Use `--brief` to identify independent, derived, structural, background, and
orphaned claims. Use `--show` when the full claim text or warrant tree matters
for a prior judgment.

Every claim and action that should be visible should have a stable public
Python variable name. If output contains `_anon_...`, fix the package source
before assigning priors.

## What Needs Priors

| Item | Prior? | Why |
|------|--------|-----|
| Independent claim used by exported goals | Yes | It is a boundary degree of freedom |
| Root `observe(...)` claim | Yes | Observation grounding is qualitative |
| Orphaned claim | Usually yes or remove it | It is otherwise unconstrained |
| Claim concluded by `derive(...)`, `compute(...)`, or `observe(..., given=...)` | No | BP derives its marginal |
| `infer(...)` likelihood helper | No | It is a review target for the relation |
| `associate(...)` helper | No | It encodes the association relation |
| `equal(...)`, `contradict(...)`, `exclusive(...)` helper | No | Operator structure determines it |
| Boolean helpers from `~`, `&`, `|` | No | Structural helper only |

## priors.py

Create `src/<package>/priors.py`:

```python
from . import observation, hypothesis

PRIORS: dict = {
    observation: (0.9, "Direct measurement reported in the source."),
    hypothesis: (0.5, "Neutral before applying this package's argument."),
}
```

Each key is a package object imported from the package. Each value is
`(prior_float, justification_string)`.

Use Cromwell-safe probabilities: avoid exact 0 or 1.

## Prior Ranges

| Evidence level | Typical range | Examples |
|----------------|---------------|----------|
| Well established | 0.85-0.95 | Reproducible measurements, textbook facts |
| Supported | 0.65-0.85 | Multiple consistent observations |
| Tentative | 0.40-0.65 | Single measurement, early model prediction |
| Weak/speculative | 0.20-0.40 | Extrapolation, loose analogy |

These are starting points, not a replacement for reading the warrant tree.

## Workflow

1. Run `gaia check --brief .` and inspect package shape.
2. Run `gaia check --hole .` and list independent inputs.
3. Read each claim with `gaia check --show <label> .` when needed.
4. Write or update `priors.py`.
5. Re-run `gaia compile .` and `gaia check --hole .`.
6. Run `gaia infer .`.
7. Interpret beliefs and revise either priors or package structure.

## Interpreting BP Results

| Pattern | Meaning | Likely action |
|---------|---------|---------------|
| Independent claim remains near prior | Normal | No action |
| Independent claim is pulled strongly away from prior | Downstream constraints conflict with it | Inspect contradictions and relation links |
| Derived claim stays near 0.5 | Weak or missing path from inputs | Check action graph and priors |
| Both sides of a contradiction go low | Priors do not distinguish the alternatives | Revisit input priors and relation scope |
| Unexpected high belief in a helper | Helper may be exported or treated as independent | Remove helper prior/export |

## Common Fixes

- If a claim is independent but should be derived, add `derive(...)`,
  `observe(..., given=...)`, `compute(...)`, or an explicit probabilistic
  `infer(...)` link.
- If a relation helper appears in `priors.py`, remove it.
- If uncertainty is buried in a prose rationale, extract it as a claim and wire
  it explicitly.
- If several independent claims encode the same evidence, consolidate or make
  their dependency explicit to avoid double counting.

## Removed Legacy

Do not create `review.py`, `reviews/<name>.py`, `ReviewBundle`, or
`review_claim(...)`. They are no longer part of the active codebase.
