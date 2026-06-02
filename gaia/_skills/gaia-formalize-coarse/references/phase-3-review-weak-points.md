# Audit Weak Points and Highlights, Calibrate Probabilities

The analytical heart of the skill. It supplies two things: the **per-conclusion**
weak points and highlights (leaf premises) emitted in **workflow step 5**
alongside each `derive(...)`, and the **global shared-factor (Pattern 3)** scan
run in the **finalize step 6**. The leaf-premise prior calibrations here drive
`priors.py` (also step 6).

## Goal

In step 5, for the conclusion you are working on, audit its reasoning chain and
emit:

1. **Weak points** — non-trivial load-bearing premises the conclusion rests on
   that the reviewer is *less* sure of. Each is a leaf `claim(...)` in the
   conclusion's `given=[...]` plus a `register_prior(...)` entry (lower prior).
2. **Highlights** — non-trivial load-bearing premises the conclusion rests on
   that the reviewer is *very* sure of. Same treatment: a leaf `claim(...)` plus
   a `register_prior(...)` entry (higher prior).
   Weak points and highlights are the **same kind of leaf premise** — both go in
   the conclusion's `given=[...]`; the only difference is the prior magnitude and
   the `weak_point` / `highlight` tag. A highlight is extracted because it is
   non-trivial and worth making explicit, not to raise belief; as a high-prior
   premise it is near-inert in BP, which is fine.
3. **Per-conclusion synthesis** — a short narrative (no prior number)
   explaining how the premises (upstream conclusions, weak points, highlights)
   interact for that conclusion. Every conclusion must end with ≥1 premise — no
   isolated conclusions.

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

### Relations between premises

A relation between two premises is fine **when it genuinely holds and is
coherent**; the right tool depends on the case, and exactly one configuration is
incoherent. (Leaf premises feed a `derive(...)` **conjunctively** — the
conclusion is supported when its premises jointly hold.)

- **Same proposition** (two premises restate one fact — e.g. a qualitative and a
  numeric form of one `measurement`) → **reuse one claim object** in both places
  rather than coupling two claims with `equal`; the `equal` verb is rarely needed
  at the premise layer.
- **Correlated** (shared sample / instrument / dataset / lemma) → **`decompose`**
  (Pattern 3, finalize): extract the shared cause as one node both premises route
  through — not `associate`. See "Shared-factor evidence" below.
- **The conclusion rests on a logical combination of A and B** (it follows from a
  *relationship* between them, not from "A and B both") → **materialize the
  combination as one premise node** in `given=`:
  - "**one of A, B holds**" (case analysis — the conclusion follows either way)
    → simply `C = A | B` (`|` is `lor`; a disjunction is accepted directly as a
    premise). A and B keep their own prose and priors; the disjunction is their
    deterministic function — no prior, enters as an anonymous structural node,
    which is fine. Use `decompose(either, parts=[A, B], formula=lor(A, B))` (or a
    labelled `claim(..., formula=lor(A, B))`) only when the combined proposition
    should be a **named, reviewable** node.
  - "**exactly one (not both)**" → that disjunction premise **plus** an
    `exclusive(A, B)` constraint (A and B are alternatives here, not conjunctive
    co-premises, so the constraint is coherent).
- **A genuine `contradict` / `exclusive` between premises of *different*
  conclusions** (e.g. C1 assumes the weak-coupling regime, C2 the strong-coupling
  regime — mutually exclusive) → **add it**: `exclusive(p1, p2)` /
  `contradict(p1, p2)`. It is coherent (a hard constraint over two prior-bearing
  leaves — it compiles and infers) and **more faithful** than lifting to a
  conclusion-level `contradict(C1, C2)`, which overstates the incompatibility
  when the conclusions have other support. Lift to the conclusion layer only
  when the two **conclusions** are themselves incompatible.

**The one incoherent case — never do this.** A `contradict` / `exclusive`
between two **co-premises of the same `derive`** (both conjunctively required):
the conjunction with an always-false pair never fires, so it just zeroes the
conclusion. If two things one derivation jointly needs really cannot both hold,
the paper's argument is flawed — surface that as one **low-prior weak point**
("the derivation jointly requires X and Y, which cannot both hold"), not as a
relation.

### A premise that relates to an earlier conclusion

While auditing, you may find that a weak point / highlight is really tied to an
**already-established conclusion**. Resolve it by the strength of the tie, not
with a relation verb:

- **Tight** (the earlier conclusion genuinely supports this one) → it is an
  **upstream premise**: put the earlier conclusion in this conclusion's `given=`
  (a logic-graph edge); do not also emit it as a separate leaf premise.
- **Weak** → do **not** model it; a faint link adds noise and double-counting
  risk for little signal.
- **Clear but not a derivation** (a definite relationship the paper states that
  is neither "uses-to-derive" nor a logical identity) → **materialize it as an
  explicit `claim(...)` + `derive(...)`**, not a soft `associate` — an explicit
  node is transparent and reviewable where a soft coupling is not. The new claim
  must be a genuinely new, separately-supportable proposition that does not
  re-import evidence already counted elsewhere (or you have only moved the
  double count).

### Gating Questions for Each Candidate Weak Point

Before committing to a weak point, it must pass all six:

- **Which conclusion(s) does it threaten?** — Most weak points undermine
  exactly one conclusion's derivation; name it by conclusion label and bind there.
  When the uncertainty seems to threaten several conclusions, distinguish two
  cases:
  - **Linked by the logic graph** (`W → C2 → C4` with C2 upstream of C4): bind
    `W` to the upstream conclusion only (C2) and let the influence propagate to
    C4 through the graph — re-binding `W` to C4 as well would double-count it.
  - **A genuinely shared foundational cause across conclusions with no
    logic-graph link** — this is Pattern 3. Extract the shared cause as one
    weak-point claim and premise it into each conclusion's `derive(...)` it
    bounds (see "Shared-factor evidence" below). It enters the graph once and is
    BP-visible to every dependent; directed implication factors mean feeding it
    to several conclusions carries no fan-out penalty. Do **not** demote the
    effect on the other conclusions to a working-notes `also_threatens` note —
    that hides a real dependency from inference.
- **Which part of that conclusion's derivation depends on it?** — Point to
  the specific argumentative move (a step in the reasoning chain, an
  experimental design choice, an assumption, a comparison).
- **If false or weaker, what specifically would fail?** — Describe the
  concrete failure: which part of the conclusion collapses, narrows, or
  becomes unsupported.
- **Is the failure specific and load-bearing?** — If the same objection
  could be pasted against almost any paper in the field, it is not specific.
- **Is it already captured by an upstream conclusion in `given=`?** — A weak
  point is the **residual** load-bearing factor not already represented by the
  conclusion's upstream premises. If the same uncertainty is already an upstream
  conclusion (or is carried by one), do not duplicate it as a leaf premise here;
  it would double-count the same evidence.
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

### Shared-factor evidence (independence — Pattern 3)

This is the **finalize step (step 6)** — run it once, globally, after every
conclusion's leaf premises exist. The independence scan covers **every
evidential factor that enters a conclusion's warrant — weak points AND
highlights together**, not weak points alone. Both are evidence about the
conclusion: a weak point lowers credence, a highlight raises it, and either is
double-counted (or, across the two, left incoherent) when two factors are
really driven by the **same latent cause**. Common shared causes: the same
sample / cohort / specimen, the same instrument or measurement, the same
software / numerical method, the same external assumption or lemma. Scan the
full factor set — every weak point and every highlight, across all conclusions,
not just within one — for groups that share a cause. This is Gaia "Pattern 3 — unmodelled shared
dependency"; see
[`../../_shared/formalize-independence.md`](../../_shared/formalize-independence.md).

The operation is the same **globally over the whole factor set, independent of
which conclusion each factor bounds**: separate the shared cause from each
factor's residual.

1. **Decompose: shared cause + residuals.** When two or more factors are driven
   by one common cause, do not collapse them to the bare cause — that throws
   away what each factor says *beyond* the cause. Split into:
   - the **shared cause** → one claim `C` with one prior: the single factual
     limitation both factors rest on (e.g. "each locus was genotyped in only
     21–42 individuals");
   - each factor's **residual** → its own claim: what that factor asserts *given*
     `C` (e.g. for C2 "the diversity statistics Na / H_O are imprecise at this
     sample size"; for C4 "the linkage-disequilibrium test is underpowered at
     this sample size"). The residuals are conditionally independent given `C`,
     so they stay as separate independent factors.
   **Keep the original factor — do not delete it.** It may be the conclusion of
   another reasoning step or a premise of more than one derivation; rewriting it
   away breaks those references. Realise the split with `decompose(...)`, which
   keeps the original as the `whole` and makes the shared cause and residual its
   atomic prior-bearing parts. Do this whether the factors sit under the same
   conclusion or different ones; never bind the cause to one conclusion and hide
   its effect on the others in working notes. A shared cause reaching several
   conclusions carries **no fan-out penalty** — deduction implication factors
   are directed, so the conclusion does not drag the shared antecedent backward.
   See [`../../_shared/formalize-independence.md`](../../_shared/formalize-independence.md)
   ("Decompose, do not delete the original") for the canonical statement.
2. **No residual → merge.** If a factor is nothing but the shared cause (its
   residual is empty / negligible), there is nothing to keep separately:
   collapse the near-duplicates to the single shared-cause claim. This is the
   degenerate case of operation 1.

How each factor type realises this:

- **Weak points** — keep each original weak-point claim and emit
  `decompose(original_wp, parts=[shared_cause, residual], formula=land(...))`.
  The `shared_cause` claim is reused as a part in **every** weak point that
  shares it, so the shared uncertainty enters the graph once; each `residual` is
  its own part, independent given the cause. Both the shared cause and every
  residual are new standalone claims and must be rewritten **self-contained**
  (name the system, symbols, units, regime — a residual readable only as "the
  rest of <original>" is not acceptable). This shared-cause split is the main
  place coarse emits `decompose` (see `phase-4-emit-package.md`, step 6); the
  only other use is the optional named-disjunction premise in "Relations between
  premises".
- **Highlights** — a highlight is a leaf premise too, so a shared cause among
  highlights is decomposed exactly as for weak points (one shared-cause claim
  reused across each highlight's decomposition; per-highlight residuals).
- **A weak point and a highlight on the same cause** — the same cause cannot
  coherently both weaken and strengthen the conclusion. Before decomposing,
  reconcile: decide the direction the cause genuinely bears (or that it is a
  strength bounded by a caveat) so it is represented once, not as an independent
  weak point and an independent highlight pulling opposite ways.

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
- **Is it already captured by an upstream conclusion in `given=`?** — A highlight
  is the **residual** load-bearing strength not already represented by the
  conclusion's upstream premises. If the strength is already carried by an
  upstream conclusion, do not duplicate it as a leaf premise.
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
scientific proposition that, when emitted in step 5, becomes the string body
of a leaf `claim(...)` (the same for weak points and highlights; both are
emitted into the conclusion's `given=[...]` with a `register_prior(...)`,
differing only in prior magnitude — see SKILL.md). The writing
rules are identical:

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

The reviewer reasoning (`weakness_reason`, `failure_mode` for weak points;
`credit` for highlights) is commentary written **about** the body. It is not a
separate stored field — it is written directly into the DSL prose: the
`register_prior(...)` `justification` (for weak points / highlights) and the
threatened conclusion's `derive(...)` `rationale` (warrant strength, credit).

## Reviewer-Reasoning Writing Rules (`weakness_reason` / `failure_mode` / `credit`)

This reasoning is where this audit's analytical value materializes. Gaia's BP
propagation only consumes the numeric `prior_probability` on leaf claims (via
`register_prior`); the textual reasoning behind those numbers — what makes a
weak point worth surfacing, what would break if it failed, why a highlight
underwrites the conclusion — is written into the `register_prior(...)`
`justification` and the `derive(...)` `rationale` emitted in steps 5–6. Sloppy
writing here means those justifications and rationales are unjustified.

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

Each leaf premise — weak point **and** highlight alike — carries a single
`prior_probability`. That one number is all the package needs: it is emitted by
`register_prior(...)` and is the only calibration BP consumes. **Judge it on its
merits; there is no fixed range or cap, and the `weak_point` / `highlight` tag
does not pin it.** Use the full range; do not default everything to 0.7–0.8. A
weak point typically lands lower because the reviewer is less sure of it; a
highlight typically lands high (0.90+) because the reviewer is very sure of it —
but those are consequences of the judged credibility, not rules.

- **`prior_probability`** — the leaf premise's intrinsic credibility on its own
  merits.
  - **0.90–0.999** — the reviewer is very sure of it: an independently verified
    fact, a settled result, a strong cross-check. Most highlights land here.
    Near the top of this band the premise is near-inert in BP (it barely caps
    the conclusion), which is expected and fine.
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
  - Only hard bounds are BP validity: strictly between 0 and 1, so ~0.001 and
    ~0.999 are the practical extremes (Cromwell). **No 0.9 cap** — a premise the
    reviewer is genuinely near-certain of belongs at 0.95–0.999.

`prior_probability` is the single number `register_prior(...)` emits in step 6.
There are no separate `p1` / `p2` (sufficiency / necessity) numbers to record:
the premise→conclusion link is the deterministic `derive(...)` implication, not
a soft conditional, so BP has nowhere to consume them. How the premise bears on
the conclusion — what follows if it holds, what breaks if it fails — is captured
in prose: the `register_prior(...)` `justification` and the `derive(...)` `rationale=`.

## Per-Conclusion Synthesis

After all weak points and highlights for a conclusion are recorded, write a
synthesis **narrative** for that conclusion. There is **no** per-conclusion
prior number: a conclusion never carries a `register_prior` — only its leaf
premises do, and its belief propagates through its `derive(...)`. The narrative
is the reviewer's holistic weighing, and it becomes part of the conclusion's
`derive(...)` `rationale=` (emitted in step 5).

**Every conclusion must leave this audit with at least one premise** — an
upstream conclusion, a weak point, or a highlight. A logic-graph root with no
upstream and no weak point still needs ≥1 **highlight** carrying its support
(e.g. "the measurement was performed reliably under conditions X"). There are
no isolated conclusions; "I found neither a weak point nor a highlight" means
this audit is incomplete for that conclusion, not that it is premise-free.

**Escape hatch when the paper itself supplies no premise.** A common
audit-incomplete case is a paper that states a load-bearing assumption
without justifying it ("we assume X"), or asserts a result with no visible
derivation or measurement. **Do not skip the conclusion, and do not invent
a justification.** The paper's silence is itself the load-bearing factor —
extract it as a **`formal`** weak point whose body names the missing
justification ("the paper asserts assumption X without supplying a
derivation, citation, or measurement"), set a moderate-to-low
`prior_probability` reflecting the reviewer's residual doubt about an
unjustified step, and write the `weakness_reason` as "no derivation /
citation / measurement is offered by the paper for this load-bearing step"
and the `failure_mode` as "if X turns out false, [the specific downstream
collapse]". This is **not** a hedging weak point — it is the honest, paper-
faithful representation of a real gap, and it lets the conclusion enter
step 5 without violating the no-isolated-conclusion invariant.

- **`narrative`** (2–4 sentences in reviewer voice) — articulates how the
  attached weak points and highlights interact for this conclusion. Cover
  at least 2–3 of:
  - **Layer of unreliability** — which layer(s) are weak: qualitative
    direction, quantitative magnitude, mechanism / attribution,
    generalization scope, error / uncertainty.
  - **Dominant risks vs refinements** — among the weak points, which would
    materially collapse the conclusion (show-stoppers) versus which only
    shift magnitude (refinements). Reference by leaf-premise label.
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

If a conclusion has no weak points, it must still have at least one highlight
(its support) plus, if derived, its upstream conclusions — so the narrative
always has premises to weigh. A conclusion with no weak point and no highlight
and no upstream is isolated, which is not allowed: go back and surface its
supporting premise.

## How this analysis maps to the DSL

There is no intermediate working-notes YAML/JSON. Each leaf premise (weak point
or highlight) maps directly to DSL as you emit it (step 5), and its reviewer
reasoning lives in the DSL's own prose fields:

- **body** → the `claim(...)` string.
- **`weak_point` / `highlight` tag + `weak_types` / `strength_types`** → passed
  as `claim(...)` metadata kwargs (e.g.
  `claim(body, ..., weak_point=True, weak_types=["measurement", "model"])`);
  they land in the claim's `**metadata` and are **advisory audit tags only** —
  they do not affect compilation or BP. The load-bearing distinction between a
  weak point and a highlight is the prior magnitude plus the `_wp_` / `_hl_`
  label infix, not these tags.
- **`prior_probability`** → the `register_prior(...)` `value`.
- **`weakness_reason` + `failure_mode`** (for weak points) → written into the
  `register_prior(...)` `justification` (why this prior; what breaks if the
  premise fails). They are not a separate stored field.
- **`credit`** (for highlights) → written into the threatened conclusion's
  `derive(...)` `rationale` (the warrant-strength prose).
- which conclusion(s) it bounds → the `given=[...]` membership (a Pattern 3
  shared cause bounds several; everything else bounds one).
- **per-conclusion synthesis narrative** → becomes part of the conclusion's
  `derive(...)` `rationale`. There is no per-conclusion prior number; a
  conclusion never gets a `register_prior` (only its leaf premises do).

Use local ids for in-context cross-reference if helpful; the final DSL labels
are minted at emit time (step 3 for conclusions, step 5 for leaf premises)
from the paper key plus a semantic suffix.

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

## Gate (step 5 per conclusion + step 6 finalize)

Across the per-conclusion step and the finalize step, confirm:

- Every conclusion has gone through both weak-point and highlight gating.
- Every retained weak point and highlight passes its six gating questions
  and is not on its do-not-extract list.
- Every body satisfies the self-standing rule.
- Each weak point has `prior_probability`, `weakness_reason`, `failure_mode`.
- Each highlight has `prior_probability`, `credit` (same leaf-premise shape as a
  weak point; the prior just lands higher).
- Every `weakness_reason` passes its judgment test (strip paper-structure
  references; substantive critique remains).
- Every `failure_mode` carries all four components (counterfactual
  premise, downstream consequence, mechanism, scope of damage) and is not
  one of the listed non-`failure_mode` shapes. Weak points whose
  `failure_mode` cannot be made concrete are removed, not hedged.
- Every `credit` integrates the three aspects (failure preempted, layer
  underwritten, scope of credit) and is not generic praise or
  paper-description.
- Each conclusion has a synthesis `narrative` (no prior number).
- **No isolated conclusion**: every conclusion has at least one premise (an
  upstream conclusion, a weak point, or a highlight). A root with no upstream
  and no weak point has been given ≥1 supporting highlight.
- The full evidence set — weak points AND highlights, across all
  conclusions — has been scanned for shared-factor groups (Pattern 3) and
  resolved globally by `decompose`: each original weak point is kept and split
  into a reused shared-cause part plus its own residual part, both rewritten
  self-contained (near-duplicates with no residual merged instead); shared-factor
  highlights stated once; a factor shared by a weak point and a highlight netted
  out and counted once, coherently.
- The next todo is marked in progress before loading
  `phase-4-emit-package.md`.
