---
name: gaia-review
description: |
  Use when assigning priors to a Gaia knowledge package via `priors.py` and
  `register_prior` against warrant Claims. Carries the prior-assignment guide
  (evidence-level → prior-range table, warrant priors via `register_prior`,
  abduction π(Alt) explanatory-power semantics encoded as the
  `p_e_given_h` / `p_e_given_not_h` likelihood ratio) and the iteration loop.
  Different from `gaia inquiry review` — that is a graph-health publish-gate
  verb; this skill is the prior-assignment workflow.
---

## Intent

Assign priors to a Gaia knowledge package via `priors.py` plus `register_prior`
against labelled warrant Claims, run belief propagation, and iterate until the
package is internally consistent and publish-ready. The primary audience is a
reviewer working a package after formalization Passes 1-5, and the artifact
this skill produces is a complete `priors.py` (one entry per independent claim
that needs one) backed by a re-run of `gaia run infer` whose result
interpretation matches the reviewer's intent. Every prior is paired with a
justification string. The two prior surfaces — claim priors (on independent
claims) and warrant priors (on the auto-generated helper Claim emitted by
`derive` / `infer`) — stay disciplined apart so evidence is not double-counted.

## CLI invocations

The CLI verbs this skill drives (one summary per row; full flag descriptions
live behind `--help`).

- `gaia build check <pkg>` — package summary; each independent claim is
  annotated with `prior=X` or `⚠ no prior (defaults to 0.5)`, with a
  trailing "Holes (no prior set): N" line.
- `gaia build check <pkg> --brief` — per-module overview: settings, claims
  (role-tagged: independent / derived / structural / background / scaffolded /
  orphaned), strategies (premise labels, conclusion, prior, reason),
  operator constraints (`contradict`, `equal`, `exclusive`).
- `gaia build check <pkg> --hole` — split listing of every independent
  claim into **Holes** (QID, content, status — no prior set) and **Covered**
  (prior value, justification — prior present). This is the report the
  iteration loop drives against.
- `gaia build check <pkg> --show <module-or-label>` — expand a single
  module (full claim content + warrant trees, composite sub-strategies
  inlined) or a single claim/strategy label (full content, plus the
  premise list and every strategy that concludes to it). Use this to read
  enough context for a defensible prior before writing it down.
- `gaia build check <pkg> --gate` — publish-readiness gate; exits
  non-zero on threshold failure. The right thing to run last, when the
  iteration loop reports clean.
- `gaia author register-prior --claim <label> --value <prob>
  --justification <text> [--file priors.py]` — appends a
  `register_prior(...)` statement to the target file. When `--file priors.py`
  is passed, the CLI auto-injects `from <import_name> import <claim>` if the
  import is missing, so the resulting file matches the hand-authored
  pattern. `--value` accepts either a numeric literal (`0.7`) or a bare
  Python identifier resolved against the module scope
  (`PRIOR_MENDELIAN_MODEL`) — useful when priors live in a sibling
  constants file.
- `gaia run infer <pkg>` — run belief propagation; writes
  `.gaia/beliefs.json` (per-claim belief, per-strategy posterior). Pass
  `--depth N` to pull beliefs from sibling packages for joint inference.

## Pre-review inspection loop

Before writing any prior, understand what the package wants from you.

1. `gaia build check <pkg> --brief` — scan the structural shape: which
   modules exist, how claims are grouped, what warrants tie them together,
   what operators constrain them.
2. `gaia build check <pkg> --hole` — read the Holes list and the Covered
   list together. Holes tell you what's missing; Covered shows you what
   the package's previous reviewer thought defensible (audit those too —
   sloppy priors do not become defensible by living in the file).
3. `gaia build check <pkg> --show <label>` — for each claim that's
   genuinely unfamiliar, expand it. The skill's main failure mode is
   assigning a number without having read the content.

Every independent claim falls into one of four roles. The role determines
whether you set a prior, and roughly where it should land.

- **Independent (need prior).** A leaf claim — not concluded by any
  warrant. These must appear in `priors.py`. Prior reflects evidence
  strength for the claim itself.
- **Derived (BP propagates — do NOT set prior).** A claim that *is* the
  conclusion of one or more warrants. The inference engine assigns 0.5 as
  an uninformative prior automatically; BP then pulls the belief up (or
  down) based on the warrants and their premises. Setting an explicit
  prior here double-counts evidence — the same support flows in twice,
  once via your prior and once via the warrant — and corrupts the belief.
- **Background-only.** A claim used only as a premise in `note` /
  background slots, never the conclusion of a warrant. Treat like an
  independent claim; priors typically sit high (0.90-0.95) because
  background is rarely contested in the package's own frame.
- **Orphaned.** A claim referenced nowhere active, or only via a hanging
  reference. Set a prior to keep the inference engine from erroring; then
  decide whether the orphan should be wired in or removed.

## `priors.py` shape

The conventional file lives at `src/<package>/priors.py` and contains
`register_prior(...)` calls — one per leaf claim that needs an external
prior. Each call names a Claim object, a probability, and a justification:

```python
from . import obs, hypothesis, evidence
from gaia.engine.lang import register_prior

register_prior(obs,        0.9, justification="Well-documented experimental result.")
register_prior(hypothesis, 0.5, justification="Theoretical prediction, not yet confirmed.")
register_prior(evidence,   0.8, justification="Consistent with multiple observations.")
```

`apply_package_priors()` auto-discovers `priors.py` at compile time, runs
each `register_prior` call, and writes the prior + justification into the
target claim's metadata; no separate sidecar file is needed, and
`gaia run infer` reads metadata directly. The `justification=` keyword is
required and engines reject empty values — write one sentence that names
the evidence, not a placeholder.

`gaia author register-prior` is the CLI front door for the same call
shape. Passing `--file priors.py` appends a `register_prior(...)` call
to the target file and auto-injects the necessary import.

The legacy `PRIORS = {...}` dict form is rejected at compile time with a
migration error — `register_prior` is the only supported shape in v0.5.

## Warrant priors via `register_prior`

Warrants — `derive`, `infer`, and the other v6 verbs — do not accept a
`prior=` kwarg. They each emit an auto-generated helper Claim
representing the implication itself; warrant uncertainty is expressed by
attaching a prior to that helper via `register_prior`. The warrant prior
answers: **if every premise of this warrant were certainly true, how
confident am I in the conclusion?** It is pinned on the implication, not
on the conclusion.

To make a warrant prior addressable, give the action a `label`, then
register a prior against the labelled Claim from `priors.py`:

```python
# src/my_package/derivations.py
from gaia.engine.lang import derive
from . import hypothesis, obs

strat_h_explains = derive(
    obs, given=[hypothesis],
    rationale="Hypothesis predicts the observation exactly.",
    label="h_explains_obs",
)
```

```python
# src/my_package/priors.py
from gaia.engine.lang import register_prior
from . import strat_h_explains

register_prior(
    strat_h_explains, 0.9,
    justification="Premises rigidly entail the observation modulo standard-method uncertainty.",
)
```

This is different from a claim prior. Setting a 0.9 prior on `obs` in
`priors.py` says "I'm 90% confident in `obs` standing alone, from the
direct evidence I have for it." Registering 0.9 against the warrant
Claim says "given the premises, the implication to `obs` holds with 90%
confidence." The two compose multiplicatively through BP; mistaking one
for the other inflates beliefs.

## Prior-assignment guide

Two tables, both load-bearing. The first picks claim priors for
independent claims; the second picks warrant priors registered against
labelled `derive` / `infer` warrants.

### Claim priors — evidence level → prior range

| Evidence level | Prior range | Examples |
|---|---|---|
| Well-established fact | 0.85-0.95 | Reproducible experiments, textbook results |
| Supported by evidence | 0.65-0.85 | Multiple consistent observations |
| Tentative / uncertain | 0.40-0.65 | Single observation, theoretical prediction |
| Weak / speculative | 0.20-0.40 | Extrapolation, analogy from a distant domain |

Round to two decimals. A claim with 0.83 vs 0.85 is not meaningfully
distinguishable; pretending otherwise is false precision.

### Warrant priors — reasoning quality → prior range

For a `register_prior(strat_label, X, ...)` against a labelled `derive`
warrant, ask: "if all premises are definitely true, how confident am I
in the conclusion?"

| Reasoning quality | Prior value | Examples |
|---|---|---|
| Near-certain (rigid derivation) | 0.95-0.99 | Mathematical proofs, logical syllogisms |
| Strong support | 0.80-0.95 | Straightforward numerical calculation |
| Reliable but approximate | 0.60-0.80 | Standard approximation method |
| Moderate confidence | 0.40-0.60 | Empirical rule of thumb |

A `derive` warrant whose prior sits below 0.40 is a smell — either the
reasoning is too weak to count as a derivation (consider whether it
should be an `infer` against new evidence instead), or the prior is
under-estimating actual support.

## π(Alt) for abductive reasoning — CRITICAL

Abductive reasoning — concluding a hypothesis because it best explains an
observation — is a reasoning pattern, not a DSL function. In v0.5 it is
expressed via `infer(...)`, whose canonical shape names the evidence,
the hypothesis, and the two likelihoods that govern the Bayesian update:
`p_e_given_h` (required) and `p_e_given_not_h` (optional, defaults to
0.5). The differential the legacy `abduction(...)` framing called
π(H)/π(Alt) lives in **the ratio** of these likelihoods; the concept
survives even though the function name does not.

The explanatory-power question represents **how well the alternative
account fits the specific observation in front of you**:

- NOT "is the negation of H true in general?"
- NOT "is the alternative's computation correct?"
- But: "can `not H` **alone** account for this observation?"

The mechanical answer: pick `p_e_given_not_h` to reflect that, and let
the ratio `p_e_given_not_h / p_e_given_h` carry the discrimination.

### Worked example — placebo vs drug efficacy

`Obs = patient symptoms changed after taking the drug`,
`H = the drug is effective`, and the alternative is `not H` (the drug
is not effective; observed change must come from something else, e.g.
placebo).

The question is not whether the placebo effect exists (it does). The
question is whether the placebo effect, alone, can account for **this
specific observation**.

- If Obs is mild subjective improvement (reduced pain score on a
  self-report scale): `p_e_given_h` is high (~0.9) and `p_e_given_not_h`
  sits comparable (~0.5). Placebo routinely produces this magnitude of
  change; the observation is genuinely ambiguous between H and `not H`,
  and the likelihood ratio (~0.55) confers little discrimination.
- If Obs is dramatic objective change (80% tumor shrinkage measured on
  imaging): `p_e_given_h` stays high (~0.9) but `p_e_given_not_h`
  collapses (~0.05). Placebo cannot plausibly drive cellular tumor
  regression at that magnitude; the ratio (~0.06) makes the observation
  highly discriminating on its own.

The same H, the same Obs, two completely different
`p_e_given_not_h` values — because the likelihood is keyed to the
**specific observation**, not to the alternative's standalone
plausibility.

### Expressed as `infer(...)` in v0.5

A `derive` warrant cannot carry this asymmetry — `derive` says "given
premises, conclusion holds with warrant prior P", and that is one
number. The abductive case wants two: how well does H explain Obs (high
— that is why we are entertaining H), and how well does `not H` explain
Obs (low — that is why H wins). The `infer(...)` warrant fits because
its two-likelihood signature **is** the Bayesian update:

```python
from gaia.engine.lang import infer
from . import hypothesis, obs

strat_h_vs_not_h = infer(
    obs, hypothesis=hypothesis,
    p_e_given_h=0.9,
    p_e_given_not_h=0.05,
    rationale="Observation specifically expected under H; magnitude unattainable by the documented alternative.",
    label="h_vs_not_h",
)
```

One `infer` call captures both branches: `p_e_given_h` carries how well
H predicts Obs; `p_e_given_not_h` carries the strongest alternative's
fit for the same Obs. BP performs the Bayesian update directly from this
pair.

### Comparing two named hypotheses (not just H vs `not H`)

If the package needs a comparative across two distinct hypotheses (H vs
Alt), not just H vs its complement, the parallel-`infer` pattern is
acceptable BUT must couple the branches via `exclusive(H, Alt)` or
`contradict(H, Alt)`. Two independent Bayesian updates are not
equivalent to one comparative update unless the factor graph wires the
hypotheses together:

```python
from gaia.engine.lang import infer, exclusive
from . import hypothesis, alt_hypothesis, obs

# Couple the branches so BP treats them as a closed partition.
h_xor_alt = exclusive(hypothesis, alt_hypothesis, rationale="The two competing accounts are mutually exclusive and exhaustive within the paper's framing.", label="h_xor_alt")

strat_h = infer(
    obs, hypothesis=hypothesis,
    p_e_given_h=0.9, p_e_given_not_h=0.05,
    rationale="Observation specifically expected under H.",
    label="infer_h",
)
strat_alt = infer(
    obs, hypothesis=alt_hypothesis,
    p_e_given_h=0.4, p_e_given_not_h=0.6,
    rationale="Observation only weakly expected under Alt; Alt fails to discriminate.",
    label="infer_alt",
)
```

Without `exclusive` / `contradict` the two updates float as independent
likelihood factors and the comparative belief math does not hold.

### Rule of thumb

If `p_e_given_not_h ≥ p_e_given_h`, the evidence provides little
discriminating power. Either the observation is genuinely weak (it does
not distinguish H from its alternative, and you should not be drawing
the conclusion from it alone) or `p_e_given_not_h` is being overstated
(most often: the reviewer is scoring the alternative's general
plausibility instead of its fit to *this* observation). When in doubt,
push back on the `rationale` string — "alternative poorly matches
observation" is a placeholder, not a discrimination story.

## BP result interpretation

After `gaia run infer`, the package writes per-claim beliefs and
per-strategy posteriors to `.gaia/beliefs.json`. Interpretation — what
counts as normal vs abnormal, which problems map to which fixes — lives
in `../_shared/bp-interpretation.md` so this skill and `gaia-formalization`
share one canonical copy. Read it after the first `gaia run infer` of an
iteration cycle; don't infer-then-tweak without it.

## Iteration loop

Five steps, repeated until clean.

1. `gaia build check <pkg> --brief` — read structure, confirm role
   assignments still match your reading of the package.
2. `gaia build check <pkg> --hole` — read Holes + Covered; decide what
   priors to write or revise.
3. Write `priors.py` — register claim priors for independent / background
   / orphan claims, and register warrant priors against labelled `derive`
   / `infer` warrants that need them. Use `gaia author register-prior
   --file priors.py` for the bulk-add path so the import injection
   happens automatically; hand-edit when an entry needs commentary or
   careful ordering.
4. `gaia build check <pkg> --hole` — confirm "All independent claims
   have priors assigned." If you broke something (a deleted import, a
   typo in a claim name), the diagnostics will surface here, not later.
5. `gaia run infer <pkg>` — run BP; interpret `.gaia/beliefs.json` via
   `../_shared/bp-interpretation.md`. If the interpretation flags
   problems (a derived belief stuck near 0.5, a contradict-pair that
   does not pick a side, an unexpectedly low independent belief), the
   loop returns to step 2 — adjust priors or warrant priors, never
   silently move on.

Once the loop reports clean and the interpretation matches intent, run
`gaia build check <pkg> --gate` for the publish-readiness gate and pass
the package downstream.

## Complete example

A minimal package showing the two prior surfaces side by side: claim
priors via `register_prior` against independent / background / orphan
claims, and warrant priors via `register_prior` against labelled
`derive` / `infer` warrants.

```python
# src/my_package/s2_results.py
from gaia.engine.lang import derive, infer
from . import (
    observation_a,
    background_setup,
    drug_efficacy,
    drug_efficacy_predicted_value,
)

# Rigid derivation: premises plus background entail the calculated result.
strat_calc = derive(
    drug_efficacy_predicted_value,
    given=[background_setup, observation_a],
    rationale="Standard rate-equation calculation from observed inputs.",
    label="strat_calc",
)

# Abductive inference: the two likelihoods carry the π(Alt) story —
# p_e_given_h says how well H predicts Obs; p_e_given_not_h says how
# well the strongest alternative predicts the same Obs.
strat_h_vs_not_h = infer(
    observation_a, hypothesis=drug_efficacy,
    p_e_given_h=0.9,
    p_e_given_not_h=0.05,
    rationale="Observation expected under H; magnitude unattainable by the documented alternative.",
    label="strat_h_vs_not_h",
)
```

```python
# src/my_package/priors.py
from gaia.engine.lang import register_prior
from . import (
    observation_a,
    background_setup,
    drug_efficacy,
    measurement_artefact,
    isolated_note,
)
from .s2_results import strat_calc, strat_h_vs_not_h

# Claim priors — one per independent / background / orphan role.

# Well-documented experimental result (claim role: independent).
register_prior(observation_a, 0.92,
               justification="Reproduced across three independent labs.")

# Background-only — used as a premise, never derived.
register_prior(background_setup, 0.95,
               justification="Standard textbook assumption for this regime.")

# Theoretical prediction, not yet directly tested (independent).
register_prior(drug_efficacy, 0.55,
               justification="Mechanistically plausible; minimal direct evidence.")

# Weak / speculative (independent).
register_prior(measurement_artefact, 0.20,
               justification="Unlikely given protocol controls, but not excluded.")

# Orphan kept on the priors list to silence inference-engine errors;
# candidate for removal in the next refactor.
register_prior(isolated_note, 0.50,
               justification="Orphan node — pending decision to wire in or drop.")

# Warrant priors — registered against the labelled warrant Claims.
register_prior(strat_calc, 0.95,
               justification="Rate-equation calculation is standard; residual uncertainty from rounding only.")
register_prior(strat_h_vs_not_h, 0.90,
               justification="Inference step itself is well-posed; uncertainty lives in the two likelihoods, not the warrant.")
```

Note: claim priors and warrant priors both flow through
`register_prior`, but they answer different questions. No independent
claim has both a claim prior and a warrant prior (warrant priors attach
only to `derive` / `infer` output Claims). No derived claim — anything
that appears as the conclusion of a warrant — gets a claim prior in
`priors.py`; BP propagates it.

## Disambiguation — this skill vs `gaia inquiry review`

This skill is the **prior-assignment workflow** — write `priors.py`,
pair inline warrant priors, run BP, iterate.

`gaia inquiry review <pkg>` is a different verb entirely: a
**graph-health publish-gate** check. It supports profiles
(`auto` / `formalize` / `explore` / `verify` / `publish`) and `--strict`
mode, writes a timestamped review artifact under
`.gaia/inquiry/reviews/`, and runs diagnostics on graph health, focus
relevance, optional inference, and publish-readiness blockers. The two
overlap only on "is this package publish-ready" — and even there,
`gaia inquiry review --mode publish --strict` is the gate, while this
skill produces the priors the gate evaluates against.

The `gaia review` CLI group on main is an empty placeholder (alpha 0:
skeleton only — no commands yet) and is not where this skill lives.

The legacy review sidecar from earlier releases — `ReviewBundle`,
`review_claim()`, `review_strategy()` — is dropped (was already
deprecated since gaia-lang 0.4.2). `priors.py` with `register_prior`
against both independent claims and labelled warrant Claims is the only
supported pattern.

## Cross-refs

- `../_shared/bp-interpretation.md` — interpretation of `gaia run infer`
  results; the iteration loop's step 5 defers to this single canonical
  table.
- `../gaia-formalization/SKILL.md` — upstream context; this skill is
  invoked from formalization Pass 5/6 once structural integrity is
  settled.
