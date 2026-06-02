# Reconstruct the Reasoning Chain

Methodology for the **derive** part of **workflow step 5** (per conclusion, in
topological order). It produces the reasoning chain that becomes the
`rationale=` of each conclusion's `derive(...)`.

## Goal

For each **atomic** conclusion (after step 5's atomicity re-check, taken in
topological order on the step-4 logic graph), reconstruct the paper's own
reasoning trace from foundational material (definitions, assumptions,
experimental setups, upstream conclusions, prior cited results) to the
conclusion itself. **The trace content matches the conclusion's nature**:
a theoretical conclusion gets its mathematical / logical derivation; an
experimental measurement gets the experimental procedure (setup, instrument,
sampling, how the value was read out); a computational result gets the
method + parameters + numerical run. After an atomicity split, the theory atom
and the experiment atom each get their own chain — do not collapse them into
one trace.

The trace is an ordered list of step strings — each step one logical move.
Steps are not claims; they are the prose written directly into that
conclusion's `derive(...)` `rationale=` when you emit it in step 5.

## Reconstruction Methodology

The reconstruction method is **shared with `gaia-formalize-fine`** — load and
apply:

- [`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md)
  — topological ordering on the logic graph, per-conclusion reconstruction of
  root and derived conclusions, the premise / background split, surfacing
  implicit premises, and the seven step-writing rules.

Coarse-specific points on top of the shared methodology:

- Coarse emits a **reduced DSL**: **every** conclusion becomes exactly one
  `derive(...)` whose premises are the union of its upstream conclusions and
  its leaf premises (weak points and highlights surfaced by the
  phase-3 audit). **Every upstream conclusion the reasoning depends on must be
  in the premise set** — if the paper's reasoning for conclusion C uses
  conclusions A and B, both A and B appear in C's `given`. A conclusion that
  is a logic-graph root (no upstream) is **not** left without premises: the
  phase-3 audit will give it at least one leaf premise carrying its support.
  There are no isolated conclusions. This skill emits no `infer` /
  `observe` / `compute`, so the shared file's verb-specific remarks for those
  verbs do not apply here. **Relation verbs are allowed when the paper itself
  states or strongly implies them** — `equal` / `contradict` / `exclusive`
  (hard) and `associate` (soft — the exception) — at the conclusion-graph layer
  (phase-1 step 4 §Relations between conclusions) and between premises where a
  relation genuinely holds and is coherent (phase-3 "Relations between
  premises"); the one thing never to do is `contradict` / `exclusive` between
  two co-premises of one `derive`. `decompose(...)` is emitted in the finalize
  step (step 6) for the shared-factor (Pattern 3) case — to split a leaf
  premise that shares a latent cause into that cause plus its residual
  without deleting the original (see phase-3 "Shared-factor evidence").

## Per-derive independence (Pattern 1c)

When you assemble a conclusion's `derive(...)` premise set in step 5, apply the
Pattern 1c check from
[`../../_shared/formalize-independence.md`](../../_shared/formalize-independence.md):
if an upstream conclusion reaches this conclusion *only* through another
upstream conclusion, drop it from `given` so the same support does not enter
twice. (**Pattern 3** — leaf premises across conclusions sharing a latent cause
— is the global finalize-step scan, by `decompose`, not a per-derive drop.)

## Per-conclusion checks (within step 5)

As you emit each conclusion's `derive(...)`:

- Its reasoning chain is an ordered, numbered list of logical moves, written
  straight into `rationale=` (no intermediate artifact) — phrase the steps the
  way they should read in the final package; step numbers are local to the chain.
- The chain processes the conclusion in topological order on the logic graph.
- No step contains a paper-internal pointer (Eq./Fig./Table/Sec./Appendix)
  whose content has not been inlined.
- Every flagged logical gap or heuristic move is stated as such, not silently
  repaired.
- `given=` contains every upstream conclusion this one depends on per the logic
  graph (none dropped except by the Pattern 1c check above), plus this
  conclusion's leaf premises (weak points + highlights from phase-3).
