# Phase 2 — Reconstruct the Reasoning Chain

Load this file after Phase 1 is complete. Phase 2 produces the per-conclusion
reasoning chains that will populate the `rationale=` field of each
`derive(...)` in Phase 4.

## Goal

For every Phase 1 conclusion, reconstruct the paper's own reasoning trace
from foundational material (definitions, assumptions, experimental setups,
upstream conclusions, prior cited results) to the conclusion itself.

The trace is held in working notes as an ordered list of step strings per
conclusion. Each step is one logical move. Steps are not claims; they are
prose that becomes part of `derive(...)`'s `rationale=`.

## Reconstruction Methodology

The reconstruction method is **shared with `gaia-formalize-fine`** — load and
apply:

- [`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md)
  — topological ordering on the logic graph, per-conclusion reconstruction of
  root and derived conclusions, the premise / background split, surfacing
  implicit premises, and the seven step-writing rules.

Coarse-specific points on top of the shared methodology:

- Coarse emits a **reduced DSL**: each derived conclusion becomes exactly one
  `derive(...)` whose premises are the union of its upstream conclusions and
  (after Phase 3) its weak-point claims. This skill emits no `infer` /
  `observe` / `compute`, so the shared file's verb-specific remarks for those
  verbs do not apply here. The **one** exception is `decompose(...)`, emitted
  solely for the Phase 3 shared-factor (Pattern 3) case — to split a weak point
  that shares a latent cause into that cause plus its residual without deleting
  the original (see Phase 3 "Shared-factor evidence" and Phase 4).
- The reconstructed step list stays in working notes (schema below); it
  becomes the `--rationale` prose in Phase 4, not a file on disk now.

## Independence Check

Before closing Phase 2, verify each derived conclusion's premise set encodes
genuinely independent support — apply
[`../../_shared/formalize-independence.md`](../../_shared/formalize-independence.md).
At Phase 2 the load-bearing case is **Pattern 1c** (derived-premise
redundancy): if an upstream conclusion reaches the current conclusion *only*
through another upstream conclusion, drop it from the premise set so the same
support does not enter the conclusion twice. **Pattern 3** (leaf premises that
share a latent cause) is handled later, in Phase 3, once the weak-point leaves
exist — by `decompose` rather than by dropping premises.

## Working Notes Schema

```yaml
reasoning_chains:
  - conclusion_id: 1
    title: <repeats Phase 1 title>
    upstreams: []
    steps:
      - "1. <full prose for step 1>."
      - "2. <full prose for step 2>."
      - ...
  - conclusion_id: 2
    title: ...
    upstreams: [1]
    steps:
      - "1. From conclusion 1's result, ... is treated as known: <inlined statement>."
      - "2. <bridging step>."
      - ...
```

Step ids are **local** to each conclusion's chain (1, 2, 3, ... per chain).
The numbered Markdown formatting carries through to the final `derive(...)`
`rationale=` field in Phase 4.

## Phase-Completion Gate

Before moving to Phase 3:

- Every Phase 1 conclusion has a reasoning chain in working notes.
- Each chain processes the conclusion in topological order on the logic
  graph.
- No step contains a paper-internal pointer (Eq./Fig./Table/Sec./Appendix)
  whose content has not been inlined.
- Every flagged logical gap or heuristic move is recorded as such, not
  silently repaired.
- Each derived conclusion's premise set has passed the independence check.
- The next todo is marked in progress before loading
  `phase-3-review-weak-points.md`.
