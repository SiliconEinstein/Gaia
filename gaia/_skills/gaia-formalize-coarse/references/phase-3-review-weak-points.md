# Phase 3 — Audit Weak Points and Highlights, Calibrate Probabilities

Load this file after Phase 2 is complete. Phase 3 is the analytical heart of
the skill: it produces the load-bearing uncertainties (weak points) and
load-bearing strengths (highlights) for each conclusion, and the leaf-claim
prior calibrations that drive `priors.py`.

## Goal

For every Phase 1 conclusion, audit the reasoning chain reconstructed in
Phase 2 and produce in working notes:

1. **Weak points** — load-bearing uncertainties between the paper's evidence
   and the conclusion. Each weak point will become a leaf `claim(...)` plus a
   `register_prior(...)` entry in Phase 4.
2. **Highlights** — load-bearing strengths whose presence is a substantive
   reason to credit the conclusion. Highlights are working-notes only; they
   inform the qualitative warrant-strength prose Phase 4 writes into each
   `derive(...)` `--rationale`, but do not enter the executable DSL.
3. **Per-conclusion synthesis** — an integrated `prior_probability` and a
   short narrative explaining how the weak points and highlights interact for
   that conclusion.

## What Counts as a Weak Point

A weak point is a **load-bearing uncertainty** in the path from evidence to
conclusion. It is **not** a generic limitation, a caveat about future work,
or a boilerplate hedge. A claim is a weak point only if **weakening or
negating it would materially weaken, invalidate, or narrow the conclusion**.

### Classify by Argument Pattern, Not by Field

For each conclusion, identify which of the following nine reasoning patterns
its derivation rests on, then surface weak points specific to those
patterns. Do not classify by academic field (physics, ML, biology).

1. **`measurement`** — does the observed/measured/computed quantity really
   capture the stated object? Cues: proxies, instrument assumptions, label
   noise, construct validity, simulation fidelity.
2. **`causal`** — does the evidence support a causal mechanism rather than
   mere association? Cues: confounders, reverse causality, missing
   interventional controls.
3. **`model`** — is the model / idealization / simplification / asymptotic
   regime adequate? Cues: validity regime, neglected terms, linearization,
   mean-field assumptions.
4. **`statistical`** — is the treatment of uncertainty / sample size /
   significance strong enough? Cues: sample size, posterior choices, error
   bars, ignored correlations.
5. **`generalization`** — does extrapolation from tested cases to the
   broader target scope hold? Cues: dataset-specific artifacts, regime
   extrapolation, benchmark-vs-deployment gap.
6. **`comparative`** — is the comparison fair and the baseline appropriate?
   Cues: baseline strength, hyperparameter asymmetry, metric choice, leakage.
7. **`formal`** — is the mathematical / logical / algorithmic transition
   fully established? Cues: skipped proofs, regularity assumptions,
   convergence, limit exchange.
8. **`computational`** — is the code / solver / numerical method reliable?
   Cues: tolerance, stability, code correctness, seed dependence.
9. **`external`** — is a cited result / dataset / pretrained component
   applicable here? Cues: results used outside their stated regime,
   pretrained components not re-validated.

A single conclusion typically rests on several patterns simultaneously. Tag
each weak point with 1–3 of these patterns (`weak_types`), in dominance
order — first key is the dominant pattern.

### Gating Questions for Each Candidate Weak Point

Before committing to a weak point, it must pass all five:

- **Which conclusion does it threaten?** — Name **one** conclusion by
  Phase 1 id. Every weak point is bound to a single conclusion — the one
  whose derivation it directly undermines. If the underlying scientific
  uncertainty seems to threaten several conclusions, apply the
  weak-point ↔ one-conclusion (strict) discipline: pick the conclusion
  with the most catastrophic failure mode (tie-break by smaller id), and
  let cross-conclusion influence propagate through the logic graph
  (`W → C2 → C4` if C2 is upstream of C4) rather than re-binding W to C4.
  For independent conclusions that share a foundational assumption with no
  logic-graph link, the BP-invisible effect on the other conclusion(s) is
  noted in working notes as `also_threatens` (working-notes only — not
  emitted into the executable DSL).
- **Which part of that conclusion's derivation depends on it?** — Point to
  the specific argumentative move (a Phase 2 step, an experimental design
  choice, an assumption, a comparison).
- **If false or weaker, what specifically would fail?** — Describe the
  concrete failure: which part of the conclusion collapses, narrows, or
  becomes unsupported.
- **Is the failure specific and load-bearing?** — If the same objection
  could be pasted against almost any paper in the field, it is not specific.
- **Is the claim already directly established by the paper?** — If the paper
  proves it, validates it with independent evidence, or it is a universally
  accepted fact, it is not a weak point.

### Do Not Extract

- Definitions ("let $H$ denote the Hamiltonian").
- Direct reported observations (what a figure or table shows).
- Mechanical algebra or identities.
- Generic limitations ("no model is perfect", "more data would be better").
- Background facts not in question here.
- Caveats that do not affect the conclusion.

### Shared-factor weak points

If two weak points on the same conclusion share an underlying factor — same
approximation, same dataset, same lemma, same external assumption — extract
the shared factor as a separate weak-point claim and let both supports
threaten that one factor. This is the same shared-factor extraction logic the
`gaia-explore` orchestrator client bakes into its survey instructions (route
two supports converging on one target through an extracted shared-factor claim
so BP does not double-count them) on the `derive(...)` warrant surface (legacy
`support()`); see `docs/for-users/language-reference.md` (`derive` semantics)
for the canonical statement.

## What Counts as a Highlight

A highlight is a **load-bearing strength**: a specific element of the
derivation that gives the conclusion substantively more credit than a
default well-written paper would have, and whose absence would leave the
conclusion materially less credible. Use the same nine patterns
(`strength_types`) to classify.

### Common Forms of Highlight

- **Independent validation / cross-check** — the same claim reached by two
  independent methods (analytical vs. simulation, two non-overlapping
  datasets, etc.).
- **Formal proof or rigorous derivation** — a step typically assumed in the
  field is here actually proved or bounded.
- **Quantitative agreement with prior independent results** — the paper's
  number reproduces a previously reported, independently obtained value
  within stated error bars.
- **Strong baseline / ablation design** — credible, well-tuned baseline plus
  ablations that isolate the contribution.
- **Statistical robustness** — large sample, multiple seeds, sensitivity
  sweeps, calibrated intervals beyond the field's default.
- **Computational reproducibility / numerical control** — explicit
  convergence tests, solver-tolerance sweeps, code/data release sufficient
  for re-execution.
- **Direct mechanistic evidence** — interventional controls, ablation
  experiments, do-style interventions when the conclusion is mechanistic.
- **Tight scope discipline** — the conclusion is explicitly bounded to the
  regime where evidence is strong; out-of-scope claims declared as conjecture.

### Gating Questions for Each Candidate Highlight

- **Which conclusion does it underwrite?** — Name by id.
- **Which part of the derivation gains credit?** — Point to the specific
  move whose strength is materially elevated.
- **What concretely would the conclusion lose without it?** — Describe the
  loss: which quantitative figure, qualitative regime, comparative ranking,
  or interpretive attribution would no longer be credibly supported.
- **Is the strength specific and load-bearing?** — If the same praise could
  be pasted onto any competently written paper, it is not specific.
- **Is the strength actually supplied?** — If the paper merely declares the
  property without evidence (claims robustness without showing the sweep),
  it is not a highlight.

### Do Not Extract

- Restatement of the conclusion (the conclusion is not its own highlight).
- Generic compliments about clarity, importance, writing.
- Standard-practice elements (routine train/test split, ordinary baseline,
  ordinary statistical reporting).
- Strengths with no specific conclusion-level credibility effect.
- Mere absence of weakness.

## Body-Writing Rule (Same for Weak Points and Highlights)

Each weak point and each highlight gets a **body** — a self-standing
scientific proposition that, in Phase 4, will become the string body of a
`claim(...)` (for weak points) or a working-notes line (for highlights;
highlights do not enter the executable DSL — see formalize/SKILL.md).
The writing rules are identical:

- **Self-standing setup**: every model / system / procedure / dataset /
  regime / variable named inside the body must be **introduced inside the
  same body**. If the claim concerns "a model", first characterize that
  model; do not appeal to "the model" as if the reader knows.
- **Paper-specific specifics**: concrete quantities, parameter values,
  regimes, equation forms, dataset identifiers — not abstract placeholders.
- **Inlined content, not pointers**: any equation, value, protocol,
  figure/table finding, or cited result the body relies on must appear,
  translated into prose, inside the body itself. No "Eq. (5)" or "Fig. 3"
  inside the body.
- **Atomic**: one claim per body. Two independent claims become two findings.
- **LaTeX math** inside `$...$`; no Unicode math symbols.
- **No cross-finding references**: "see P2" / "as in H1" not allowed inside
  the body.
- **Concrete subject**: the procedure, the estimator, the model, the
  measurement — not "the paper" or "this work".

The reviewer fields (`weakness_reason`, `failure_mode` for weak points;
`credit` for highlights) are reviewer commentary written **about** the body
and live in Phase 3 working notes only — they do not enter the executable
DSL and do not get emitted as audit artifacts in the post-purge SOP. They
inform the qualitative warrant-strength prose Phase 4 writes into each
deduction's `--rationale` and the agent's own hand-off narrative.

## Reviewer-Field Writing Rules (`weakness_reason` / `failure_mode` / `credit`)

These three fields are where Phase 3's analytical value materializes for the
reviewing agent. Gaia's BP propagation only consumes the numeric
`prior_probability` on leaf claims (via `register_prior`); the textual
reasoning behind those numbers — what makes a weak point worth surfacing,
what would break if it failed, why a highlight underwrites the conclusion —
lives only in working notes and informs the warrant-strength prose Phase 4
writes into each deduction's `--rationale`. Sloppy writing here means
Phase 4's rationale and the agent's own hand-off narrative are unjustified.

All three are read alongside the `body` they annotate and may freely refer
to its contents — they do **not** need to restate the body's setup, and
they are **not** self-standing on their own.

### `weakness_reason` — critique, not description

`weakness_reason` is the reviewer's **critical judgment of why the claim
in `body` is uncertain on its own merits**. It is a critique, not a
description of what the paper does.

Substantive critique draws on (any of):

- the alternative formulations the body's claim rules out;
- known counter-cases or competing conventions in the field;
- evidence that the choice was made for tractability or convention rather
  than empirical grounding;
- the specific kind of derivation or evidence that would be needed to
  establish the claim, which the paper does not provide.

Paper-structure references (Section / Eq / Fig / footnote) are permitted
only as supplementary citations attached to the critique; they must not
carry the reasoning. A `weakness_reason` whose content reduces to
describing where in the paper the claim is made, or how the paper sets it
up, is paper-description, not critique, and must be rewritten.

**Judgment test (self-check).** Strip every paper-structure reference out
of the field and read what remains. If what remains is substantive
reasoning about why the claim is dubious on its own merits, the field is
correctly written. If what remains is empty or vacuous, the field must be
rewritten.

### `failure_mode` — concrete counterfactual, not hedging

`failure_mode` is the reviewer's **counterfactual reasoning about what
breaks in the threatened conclusion if the claim in `body` turns out to
be false or weaker**.

It must contain all four of:

1. **An explicit counterfactual premise** — "If [body claim] fails in
   way W, ...", stating the specific form of failure (not just negation
   of the claim).
2. **An identifiable downstream consequence in the conclusion** — a
   specific quantitative figure, a qualitative regime, a comparative
   ranking, or an interpretive attribution that breaks, narrows, flips,
   or becomes unsupported.
3. **The mechanism** — the intermediate step in the derivation that
   stops working, linking "body false" to "conclusion damaged".
4. **The scope of damage** — full invalidation / narrowing of valid
   regime / quantitative shift / alternative-mechanism substitution.

**What is not a `failure_mode`:**

- restating the `body` claim in the future tense;
- generic hedges ("the conclusion would be weakened", "results may be
  affected");
- re-describing the paper's conclusion without saying what fails in it;
- re-iterating why the claim is dubious (that is `weakness_reason`, not
  here).

**Diagnostic.** If you cannot write a concrete, specific consequence
under all four requirements above, the candidate is probably not
load-bearing — go back and remove it from the weak-point list rather
than fill `failure_mode` with hedging to get past this phase.

### `credit` — integrated underwriting argument, not praise

`credit` is the reviewer's **integrated argument for the role this
strength plays in the conclusion's derivation**. A single coherent piece
of reasoning (not a multi-field decomposition) that conveys three things
together:

1. **Which specific failure mode in the derivation it guards against** —
   what concrete failure (a particular alternative explanation, a
   particular extrapolation, a particular numerical artifact, a
   particular confounder, etc.) the conclusion would have been
   vulnerable to without this element.
2. **Which layer of the conclusion's credibility it underwrites** —
   qualitative direction, quantitative magnitude, mechanism /
   attribution, generalization / extrapolation scope, or error /
   uncertainty quantification.
3. **The scope of credit** — full underwriting of the conclusion /
   quantitative tightening / regime-bounded support / ruling out of a
   specific alternative explanation / extension of the conclusion's
   regime of validity.

State these as one integrated argument, not as labelled sub-fields.

**What is not a `credit`:**

- generic praise ("the conclusion is well supported", "this is good
  practice", "the paper is rigorous");
- a `credit` whose content reduces to "the paper does X" without
  naming a concrete failure preempted or a specific layer
  underwritten — that is description, not reasoning, and must be
  rewritten.

Paper-structure references (Section / Eq / Fig) are permitted only as
supplementary citations attached to the reasoning; they must not carry
the reasoning.

## Probability Calibration

Each weak point carries three numbers in `[0, 1]`. Use the full range; do
not default everything to 0.7–0.8.

- **`prior_probability`** — the weak-point claim's intrinsic credibility on
  its own merits.
  - **0.80–0.90** — standard approximation used within its **known valid
    regime**, or an empirical fact the field treats as settled. The claim
    is defensible by appeal to established practice; the only residual
    doubt is theoretical purity.
  - **0.60–0.80** — plausible but debatable in *this* setting: a reasonable
    assumption that has not been rigorously verified for the specific
    system, dataset, regime, or parameter range under study.
  - **0.40–0.60** — heuristic / extrapolative / single-anchor: assertions
    of asymptotic / functional form fit to a small number of anchor
    points, validations performed at a single parameter setting / dataset
    / subgroup / regime being generalized to other settings, cited
    results applied outside their stated regime, qualitative arguments
    substituting for a derivation, mechanistic interpretation of a single
    observed correlation. **The single biggest calibration mistake is to
    put these at 0.80** because the claim "feels reasonable" — they are
    exactly the load-bearing uncertainties this phase is meant to surface.
  - **0.20–0.40** — actively doubtful: contradicted by available evidence,
    internally inconsistent, or relying on a step the field has flagged
    elsewhere.
  - **0.001–0.20** — almost certainly wrong (rare; reserved for clear
    refutations).
  - Cap at 0.9 (no claim is absolutely certain). Lower bound 0.001
    (Cromwell).
- **`p1`** — sufficiency: if the weak-point claim is true, how strongly does
  the conclusion follow? `p1 ≈ P(conclusion | weak point true)`.
- **`p2`** — necessity: if the weak-point claim is false, how strongly does
  the conclusion fail? `p2 ≈ P(conclusion false | weak point false)`.

`prior_probability` is consumed by Phase 4's `register_prior(...)` emission
for this weak point. `p1` and `p2` are reviewer working-notes only — they
inform the qualitative warrant-strength prose Phase 4 writes into the
`derive(...)` `--rationale` but are not emitted into the package; BP does
not consume them.

## Per-Conclusion Synthesis

After all weak points and highlights for a conclusion are recorded, write a
synthesis for that conclusion:

- **`prior_probability`** (a number in `[0.001, 0.9]`) — the reviewer's
  overall credibility judgment (posterior) for the conclusion, integrating
  its weak points and highlights. This is **not** a mechanical function of
  the weak points' probabilities; it is informed by both findings. In
  Phase 4 this number is consumed in two ways: (1) for isolated
  conclusions (no upstream, no weak points → no `derive(...)`) it becomes
  the conclusion's `register_prior(...)` value because the conclusion is a
  leaf in that case; (2) for derived conclusions it informs the qualitative
  warrant-strength prose Phase 4 writes into the `derive(...)` `--rationale`
  (alongside per-highlight and per-gap commentary — see Phase 4 Step 4a).
  The engine `derive(...)` signature has no `metadata=` / `warrant_prior`
  kwarg, so warrant-strength intent does not live as a number on the
  deduction itself; numerical priors live only on leaf claims via
  `register_prior`. Calibration:
  - A conclusion with several high-`p2` weak points cannot have a high
    prior, even with highlights.
  - A conclusion with no load-bearing weak points and at least one
    substantive highlight should be close to 1.
  - A conclusion with neither weak points nor highlights (a routine
    derivation) sits in the upper-middle range, not at the ceiling.
- **`narrative`** (2–4 sentences in reviewer voice) — articulates how the
  attached weak points and highlights interact for this conclusion. Cover
  at least 2–3 of:
  - **Layer of unreliability** — which layer(s) are weak: qualitative
    direction, quantitative magnitude, mechanism / attribution,
    generalization scope, error / uncertainty.
  - **Dominant risks vs refinements** — among the weak points, which would
    materially collapse the conclusion (show-stoppers) versus which only
    shift magnitude (refinements). Reference by working-note id.
  - **Composition of risks and supports** — how weak points and highlights
    interact: compounding, cumulative, partially redundant, offsetting (a
    highlight specifically preempts a failure mode named in a weak point's
    `failure_mode`), or unprotected.
  - **Layers underwritten by highlights** — which layer(s) are positively
    supported by the highlights.
  - **Importance among highlights** — which highlights are doing the
    substantive underwriting versus confirming-but-not-essential.

The narrative is not an index. Naming weak-point and highlight ids is fine,
but a narrative that only lists ids and restates one-line content is not
doing its job.

If a conclusion has zero weak points and zero highlights, the narrative is a
single sentence stating that no load-bearing risks or distinguishing
strengths were identified.

## Working Notes Schema

```yaml
weak_points:
  - id: P1                       # ephemeral id local to working notes
    conclusion_id: 1             # the single conclusion this weak point threatens
    also_threatens: []           # audit-only: independent conclusions this assumption also affects
                                 # (BP cannot see this; do NOT add the weak point to those conclusions' deductions)
    title: <≤ 25-word descriptor>
    body: <self-standing scientific proposition>
    weak_types: [model]
    prior_probability: 0.65
    p1: 0.7
    p2: 0.85
    weakness_reason: <reviewer critique of why the body claim is uncertain>
    failure_mode: <reviewer counterfactual: what breaks in the threatened conclusion if body fails>
    citation_keys: ["SourceKey"]
    artifact_anchors:
      - {kind: figure, source: "SourceKey", locator: "Fig. 4"}
    inline_equations: ["Eq. (12) content must be transcribed into body if load-bearing"]

highlights:
  - id: H1
    conclusion_id: 1
    title: <descriptor>
    body: <self-standing scientific proposition>
    strength_types: [computational, statistical]
    credit: <reviewer integrated argument: failure preempted, layer underwritten, scope of credit>
    citation_keys: ["SourceKey"]
    artifact_anchors:
      - {kind: figure, source: "SourceKey", locator: "Fig. 4"}
    inline_equations: ["Eq. (12) content must be transcribed into body if load-bearing"]

conclusion_synthesis:
  - conclusion_id: 1
    prior_probability: 0.78
    narrative: |
      <2–4 sentences>
```

P-ids and H-ids are ephemeral and used only for cross-references in the
narrative; the final claim labels for weak points are minted in Phase 4 from
the paper key plus a semantic suffix.

## Calibration Sanity Check

After all weak points have been assigned `prior_probability`, run this
quick distributional sanity check **before** the phase-completion gate:

- If **every** weak point has `prior_probability ≥ 0.80`, the calibration
  is almost certainly miscalibrated. Load-bearing uncertainties in any
  non-trivial paper are not all "plausible standard approximations" — at
  least one is normally heuristic, extrapolative, or single-anchor and
  belongs in the 0.40–0.60 band. Re-read each weak point against the
  bands above; specifically check whether you are giving 0.80+ to a
  claim that the paper itself only supports by extrapolation, asymptotic
  fit, validation at a single parameter setting / dataset / subgroup,
  or qualitative argument.
- The opposite failure (every weak point ≤ 0.40) is also miscalibration:
  if the derivation really had that many actively doubtful steps, the
  conclusion would not be defensible at all. Re-read for whether each
  is genuinely a refutation rather than a heuristic gap.
- A healthy distribution typically spans at least two bands across the
  weak points of a paper. Aim for that, not for a uniform default.

This check guards against a known failure mode: agents tend to cluster
priors at 0.80 because the bodies "look reasonable", losing the signal
the weak-point analysis is supposed to produce.

## Phase 1b — LKM Reverse-Provenance Trace (cross-grounding)

This section is named "Phase 1b" because the *analytical role* it plays
is paper-level cross-grounding — adjacent to Phase 1's conclusion
extraction. It runs late (here, in Phase 3) only because the audit weights
it produces are consumed by the same pass that calibrates weak-point
priors. Phase 4 emit time is when the resulting `lkm_id=` metadata
actually lands on `claim(...)` calls.

### Goal

Cross-ground the paper's claims by checking whether they appear in LKM's
existing knowledge graph as evidence chains rooted in this paper's
`paper:<id>`. The pass surfaces:

- Which Phase 1 conclusions have been independently formalized by LKM
  with provenance back to *this* paper (their `gcn_*` ids become the
  `lkm_id=` metadata on the paper-extract `claim(...)`).
- Which Phase 3 weak points threaten conclusions that LKM treats as
  load-bearing for downstream multi-paper reasoning (cross-paper evidence
  fan-out). The reviewer should weight those weak points heavier in the
  per-conclusion synthesis prior: their failure doesn't just collapse one
  paper's claim, it perturbs an inter-paper reasoning chain.

This is **best-effort cross-grounding**, not a gate. Papers not yet
ingested by LKM yield no trace; that is a no-op, not a failure. The
underlying `claim(...)` bodies and conclusion list are not changed by
Phase 1b — only `lkm_id=` metadata is added in Phase 4, and the reviewer's
per-conclusion synthesis judgment may shift.

### Procedure

Use the native `gaia search lkm` CLI. Make sure an LKM access key is set —
run `gaia search lkm auth login` (or set `GAIA_LKM_ACCESS_KEY` /
`LKM_ACCESS_KEY`); check with `gaia search lkm auth status`. Verify any flag
with `gaia search lkm <verb> --help`.

1. **Identify the input paper's `paper:<id>`.** From the paper Markdown's
   bibliographic metadata (DOI, first-author surname + year). If the
   paper id cannot be derived (corrupted bibliography, unindexed
   preprint), skip Phase 1b entirely and note it in the hand-off report's
   metadata-gaps section.
2. **Query LKM by title or anchor phrase.** Use the paper title; if it is
   too generic, supplement with one or two distinctive anchor phrases
   from the paper's contribution sentences (Phase 1 working notes are a
   good source). Filter to claim-typed nodes with reasoning backing so
   the next step has something to trace. Use `--format raw-json` so the
   verbatim LKM envelope (`data.variables[]` with `provenance`, plus
   `data.papers`) is preserved for the provenance filter in step 3.

   ```bash
   gaia search lkm knowledge "<paper title or anchor phrase>" \
     --scopes claim --reasoning-only \
     --limit 50 --format raw-json --out search.json
   ```

3. **Filter `data.variables[]`** for entries whose
   `provenance.source_packages` list contains the input paper's
   `paper:<id>`. Those are LKM claims whose provenance traces back to
   this paper. Collect the matching `gcn_*` ids (each will be
   `type=claim` because of `--reasoning-only`) and their `data.papers`
   metadata into working notes.
4. **Fetch reasoning chains for each match.** For every matching
   `gcn_id`:

   ```bash
   gaia search lkm reasoning --claim-id <gcn_id> \
     --max-chains 10 --format raw-json --out reasoning_<gcn_id>.json
   ```

   Some claims may come back with no reasoning chains
   (`total_chains == 0`); treat those as `unmatched` for verdict purposes
   and move on.

5. **Verify chain closure.** For each `reasoning_chains[]` entry, examine
   the chain's `paper_id` (resolves into `data.papers`). A chain whose
   `paper_id` matches the input paper's id represents reasoning fully
   internal to this paper — expected for a typical paper-extract claim.
   A chain whose `paper_id` is a *different* paper indicates LKM has
   rooted this claim in inter-paper reasoning; this paper is feeding
   into a cross-paper provenance chain. Count the cross-paper chains per
   `gcn_id`; these are the "LKM treats as load-bearing for downstream
   reasoning" signal.

### Outputs

- **Phase 1b LKM-trace table in working notes.** Columns:
  `gcn_id | matched_paper_claim_label | chain_total | cross_paper_chains | LKM_provenance_verdict`.
  The verdict is one of `single-paper-internal`, `cross-paper-fanout`,
  or `unmatched`. Surface a summary count in the hand-off report.
- **`lkm_id=` metadata on Phase 1 conclusion claims.** Whenever a
  matched `gcn_id` corresponds to a Phase 1 conclusion (mapped by content
  similarity in working notes), record the join so Phase 4 can emit
  `lkm_id="gcn_..."` on that conclusion's `claim(...)`. Paper-extract
  emitters reuse `lkm_id` purely as a provenance join.
- **Reviewer-signal bump on cross-paper-fanout weak points.** When a
  Phase 3 weak point threatens a conclusion whose matched `gcn_id` has
  `cross_paper_chains > 0`, note the cross-paper exposure in working
  notes; the reviewer may use it to nudge the per-conclusion synthesis
  prior or the deduction warrant downward. Phase 1b does **not**
  automatically lower or raise the weak point's numeric
  `prior_probability` / `p1` / `p2` — those reflect the paper's own
  evidence, not LKM downstream consumption.

### When to skip

- **Paper not in LKM corpus.** Step 3 yields no `data.variables[]` whose
  `provenance.source_packages` includes the paper's `paper:<id>`. Note
  the skip in the hand-off report; Phase 4 emit proceeds without
  cross-grounding.
- **Network or API failure.** Best-effort. Note the failure mode (e.g.
  `code=290001` retry exhausted, network timeout) in the hand-off report
  and continue. Phase 4 emit proceeds.
- **Paper too recent for LKM ingestion cutoff.** Same handling as
  not-found.
- **`LKM_ACCESS_KEY` unavailable** (and the user declines to provide
  one). Same handling as not-found.

In every skip path, the rest of Phase 3 (weak points, highlights,
synthesis priors) is unaffected. Phase 1b is an additive audit; its
absence does not block emission.

## Phase-Completion Gate

Before moving to Phase 4:

- Every conclusion has gone through both weak-point and highlight gating.
- Every retained weak point and highlight passes its five gating questions
  and is not on its do-not-extract list.
- Every body satisfies the self-standing rule.
- Each weak point has `prior_probability`, `p1`, `p2`, `weakness_reason`,
  `failure_mode`.
- Each highlight has `credit`.
- Every `weakness_reason` passes its judgment test (strip paper-structure
  references; substantive critique remains).
- Every `failure_mode` carries all four components (counterfactual
  premise, downstream consequence, mechanism, scope of damage) and is not
  one of the listed non-`failure_mode` shapes. Weak points whose
  `failure_mode` cannot be made concrete are removed, not hedged.
- Every `credit` integrates the three aspects (failure preempted, layer
  underwritten, scope of credit) and is not generic praise or
  paper-description.
- Each conclusion has a synthesis (`prior_probability` + `narrative`).
- Phase 1b LKM reverse-trace has either run (results captured in working
  notes; `lkm_id` joins recorded for Phase 4) or been skipped with the
  skip reason noted for the hand-off report.
- The next todo is marked in progress before loading
  `phase-4-emit-package.md`.
