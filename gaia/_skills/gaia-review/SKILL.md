---
name: gaia-review
description: |
  Use when assigning priors to a Gaia knowledge package via `priors.py` and
  inline `prior=` warrant pairing. Carries the prior-assignment guide
  (evidence-level → prior-range table, derive warrant priors, abduction
  π(Alt) explanatory-power semantics) and the iteration loop. Different from
  `gaia inquiry review` — that is a graph-health publish-gate verb; this skill
  is the prior-assignment workflow.
---

## Intent

Assign priors to a Gaia knowledge package via `priors.py` plus inline `prior=`
warrant pairing, run belief propagation, and iterate until the package is
internally consistent and publish-ready. The primary audience is a reviewer
working a package after formalization Passes 1-5, and the artifact this skill
produces is a complete `priors.py` (one entry per independent claim that needs
one) backed by a re-run of `gaia run infer` whose result interpretation
matches the reviewer's intent. Every prior is paired with a justification
string; every warrant `prior=` is paired with a `reason=`; the two prior
surfaces — claim priors (in `priors.py`) and warrant priors (inline on
`derive` / `infer` etc.) — stay disciplined apart so evidence is not
double-counted.

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

The conventional file lives at `src/<package>/priors.py` and exports a
module-level `PRIORS: dict` mapping Knowledge objects to
`(prior_float, justification_string)` tuples:

```python
from . import obs, hypothesis, evidence

PRIORS: dict = {
    obs:        (0.9, "Well-documented experimental result."),
    hypothesis: (0.5, "Theoretical prediction, not yet confirmed."),
    evidence:   (0.8, "Consistent with multiple observations."),
}
```

`apply_package_priors()` auto-discovers `priors.py` at compile time and
writes each prior + justification into the claim's metadata; no separate
sidecar file is needed, and `gaia run infer` reads metadata directly. The
justification is required and engines reject empty values — write one
sentence that names the evidence, not a placeholder.

`gaia author register-prior` is the CLI front door for the same shape.
Passing `--file priors.py` appends a `register_prior(...)` call to the
target file and auto-injects the necessary import; the call form and the
dict form coexist (the engine picks up both).

## Inline `prior=` warrant pairing

Warrants — `derive`, `infer`, and any other strategy that accepts
`prior=` — carry their own prior, separate from claim priors. The
warrant prior answers: **if every premise of this warrant were certainly
true, how confident am I in the conclusion?** It is pinned on the
implication itself, not on the conclusion.

```python
strat_h_explains = derive(
    [hypothesis], obs,
    reason="Hypothesis predicts the observation exactly.", prior=0.9,
)
```

This is different from a claim prior. Setting a 0.9 prior on `obs` in
`priors.py` says "I'm 90% confident in `obs` standing alone, from the
direct evidence I have for it." Setting `prior=0.9` on a `derive(...,
obs, ...)` warrant says "given the premises, the implication to `obs`
holds with 90% confidence." The two compose multiplicatively through BP;
mistaking one for the other inflates beliefs.

## Prior-assignment guide

Two tables, both load-bearing. The first picks claim priors in
`priors.py`; the second picks warrant priors paired with `derive` / `infer`
and friends.

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

For `derive(..., prior=X)` and any other warrant taking an explicit
`prior=`, ask: "if all premises are definitely true, how confident am I
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
expressed via `infer(...)` with a Bayesian update: the observation
updates belief in the hypothesis, and the warrant `prior=` plays the role
the legacy `abduction(...)` framing called π(H)/π(Alt). The concept
survives even though the function name does not.

The prior on an alternative explanation represents **explanatory power
for the specific observation in front of you**:

- NOT "is Alt true in general?"
- NOT "is Alt's computation correct?"
- But: "can Alt **alone** account for this observation, without H?"

### Worked example — placebo vs drug efficacy

`Obs = patient symptoms changed after taking the drug`,
`H = the drug is effective`, `Alt = placebo effect`.

The question is not whether the placebo effect exists (it does). The
question is whether the placebo effect, alone, can account for **this
specific observation**.

- If Obs is mild subjective improvement (reduced pain score on a
  self-report scale): π(Alt) sits moderate (~0.5). Placebo routinely
  produces this magnitude of change; the observation is genuinely
  ambiguous between H and Alt.
- If Obs is dramatic objective change (80% tumor shrinkage measured on
  imaging): π(Alt) sits very low (~0.1). Placebo cannot plausibly drive
  cellular tumor regression at that magnitude; the observation, by its
  scale, discriminates between H and Alt almost on its own.

The same Alt, the same H, two completely different π(Alt) values —
because π(Alt) is keyed to the **specific observation**, not the
alternative's standalone plausibility.

### Expressed as `infer(...)` in v0.5

A `derive` warrant cannot carry this asymmetry — `derive` says "given
premises, conclusion holds with prior P", and that's one number. The
abductive case wants two: how well does H explain Obs (high — that's why
we're entertaining H), and how well does Alt explain Obs (low — that's
why H wins). The `infer(...)` warrant fits: pair the observation as
evidence with a warrant whose `prior=` reflects the differential. A high
warrant prior on `infer([H], Obs, prior=0.9, reason="...")` says the
observation discriminates strongly in H's favour — implicitly, π(Alt) is
low. A moderate warrant prior says the observation does not discriminate
well — implicitly, π(Alt) is comparable to π(H).

```python
strat_h = infer(
    [hypothesis], obs,
    reason="Observation specifically expected under H; alternatives "
           "do not explain the magnitude of the change.",
    prior=0.9,
)
strat_alt = infer(
    [alt_hypothesis], obs,
    reason="Alternative poorly matches the specific observation.",
    prior=0.15,
)
```

The `reason=` strings carry the discriminating story; the `prior=`
numbers carry the differential weight.

### Rule of thumb

If π(Alt) ≥ π(H), the abductive step provides little support for H.
Either the evidence is genuinely weak (the observation does not
discriminate, and you should not be drawing the conclusion from it
alone) or π(Alt) is being overestimated (most often: the reviewer is
scoring Alt's general plausibility instead of its fit to *this*
observation). When in doubt, push back on the `reason=` string —
"alternative poorly matches observation" is a placeholder, not a
discrimination story.

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
3. Write `priors.py` (and any inline warrant `prior=` you owe). Use
   `gaia author register-prior --file priors.py` for the bulk-add path
   so the import injection happens automatically; hand-edit when an
   entry needs commentary or careful ordering.
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

A minimal `priors.py` (six entries — one per role, with deliberate
spread of evidence levels) and a minimal DSL snippet pairing claim
priors with warrant priors.

```python
# src/my_package/priors.py
from . import (
    observation_a,
    background_setup,
    drug_efficacy,
    alt_placebo,
    measurement_artefact,
    isolated_note,
)

PRIORS: dict = {
    # Well-documented experimental result (claim role: independent).
    observation_a:        (0.92, "Reproduced across three independent labs."),

    # Background-only — used as a premise, never derived.
    background_setup:     (0.95, "Standard textbook assumption for this regime."),

    # Theoretical prediction, not yet directly tested (independent).
    drug_efficacy:        (0.55, "Mechanistically plausible; minimal direct evidence."),

    # Alternative explanation for the same observation (independent).
    alt_placebo:          (0.30, "Placebo effect documented; modest in this regime."),

    # Weak / speculative (independent).
    measurement_artefact: (0.20, "Unlikely given protocol controls, but not excluded."),

    # Orphan kept on the priors list to silence inference-engine errors;
    # candidate for removal in the next refactor.
    isolated_note:        (0.50, "Orphan node — pending decision to wire in or drop."),
}
```

```python
# src/my_package/s2_results.py
from . import (
    observation_a,
    background_setup,
    drug_efficacy,
    alt_placebo,
)
from gaia.author import derive, infer

# Rigid derivation: premises plus background entail the calculated result.
strat_calc = derive(
    [background_setup, observation_a], drug_efficacy_predicted_value,
    reason="Standard rate-equation calculation from observed inputs.",
    prior=0.95,
)

# Abductive inference: observation discriminates between hypothesis and
# its alternative. High warrant prior on the H branch, low on the Alt
# branch — the differential carries the π(Alt) story.
strat_h = infer(
    [drug_efficacy], observation_a,
    reason="Observation expected under H; magnitude unattainable by "
           "the documented alternative.",
    prior=0.9,
)
strat_alt = infer(
    [alt_placebo], observation_a,
    reason="Alternative poorly matches the observed magnitude.",
    prior=0.15,
)
```

Note: claim priors live in `priors.py`; warrant priors live inline on the
`derive` / `infer` calls. No claim has both, and no derived claim
(anything that appears as the conclusion of a warrant) has a prior in
`priors.py`.

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
deprecated since gaia-lang 0.4.2). `priors.py` plus inline `prior=`
pairing is the only supported pattern.

## Cross-refs

- `../_shared/bp-interpretation.md` — interpretation of `gaia run infer`
  results; the iteration loop's step 5 defers to this single canonical
  table.
- `../gaia-formalization/SKILL.md` — upstream context; this skill is
  invoked from formalization Pass 5/6 once structural integrity is
  settled.
