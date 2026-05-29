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
  (after Phase 3) its leaf premises (weak points and highlights). This skill
  emits no `infer` /
  `observe` / `compute`, so the shared file's verb-specific remarks for those
  verbs do not apply here. The **one** exception is `decompose(...)`, emitted
  solely for the Phase 3 shared-factor (Pattern 3) case — to split a weak point
  that shares a latent cause into that cause plus its residual without deleting
  the original (see Phase 3 "Shared-factor evidence" and Phase 4).

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

## Holding Phase 2 output

For each conclusion, hold its reasoning chain in context as an ordered, numbered
list of step strings (and which upstream conclusions it builds on). No
intermediate YAML/JSON — this prose **is** the `derive(...)` `rationale=` field
Phase 4 emits, so write the numbered steps the way they should read in the final
package. Step numbers are local to each conclusion's chain.

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
