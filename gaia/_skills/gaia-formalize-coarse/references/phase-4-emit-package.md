# Emit the Gaia Package (mechanics)

The emission mechanics for **workflow steps 2, 3, 5, and 6**. The package is
built **incrementally**, not dumped at the end: scaffold (step 2), write the
conclusion claims into their modules (step 3), then per conclusion append its
leaf premises and `derive(...)` (step 5), then finalize — decompose shared
factors, write priors + references, compile (step 6).

## Goal

Produce a `<name>-gaia/` package on disk per the Gaia DSL surface (run
`gaia sdk` for the `claim` / `derive` / `decompose` / `question` rules, body
discipline, and label conventions; `gaia pkg scaffold` for the layout). When
finalized, the package must compile with `gaia build compile` and pass
`gaia build check --hole .` (`gaia build check --help` for flags).

## Authoring surface — write the DSL directly

**Writing the DSL via the Python SDK is the primary authoring path.** Emit by
writing Python source files directly (the file-write tool of your choice), not
by driving the `gaia author` CLI one statement at a time. The `gaia author` CLI
exists as an optional convenience; it writes the *same* statements one per
invocation, which for a whole-paper package is dozens of round-trips. Each
module is built up directly: its conclusion claims in step 3, then its leaf
premises and `derive(...)` appended in step 5 — compile-check the module as it
takes shape, with a full compile at finalize.

Before emitting, read the canonical DSL cheat sheet:

```bash
gaia sdk            # writes ./gaia-sdk/ — SDK reference + one-page CHEATSHEET.md
```

The cheat sheet is authoritative for every primitive (`claim`, `note`,
`question`, `derive`, `register_prior`, distributions, relations). The
sections below are just the sequencing of those primitives for a single paper.

The DSL primitives this skill emits:

| Emission | DSL primitive |
|---|---|
| Whole-paper motivation | `note(...)` (in `motivation.py`) |
| Paper-level open problem | `question(...)` (in `motivation.py`) |
| Conclusion / weak-point / highlight claim | `claim(...)` |
| Transcribed figure / table context | `note(...)` (optional) |
| Deduction (1+ premises → conclusion) | `derive(...)` |
| Shared-factor split (Pattern 3 only) | `decompose(...)` |
| Leaf prior record | `register_prior(...)` |

## Naming and labels (decide before scaffolding)

### Package name and import name

- Extract the paper's reference key from its bibliographic metadata
  (`<FirstAuthorSurname><Year>`, e.g., `Liu2015`). If multiple papers shared a
  key in this run, append `a`, `b`, ...
- Derive a short topic slug (1–4 lowercase tokens) from the paper title or the
  dominant conclusion's title.
- Package directory: `<author-lowercase><year>-<topic-slug>-gaia` (kebab case),
  e.g., `liu2015-fibonacci-anyons-gaia`.
- Python import name: derived by `gaia pkg scaffold` from `--name` by stripping
  the trailing `-gaia` and converting hyphens to underscores
  (`liu2015-fibonacci-anyons-gaia` → `liu2015_fibonacci_anyons`).

If the paper Markdown is missing author / year, fall back to `<topic-slug>-gaia`
and note the metadata gap in the hand-off report.

### Claim labels

For every conclusion, mint a label `<key>_c<id>_<semantic_suffix>`, where the
suffix is 1–4 tokens drawn from the conclusion's title (lowercase, ASCII,
underscores only). (Mint a conclusion's label when you write it in step 3.)

For every weak point, mint `<key>_c<id>_wp_<semantic_suffix>`; for every
highlight, `<key>_c<id>_hl_<semantic_suffix>` (the `_wp_` / `_hl_` infix is the
only marker distinguishing the two leaf-premise kinds). (Mint these in step 5.)

Label rules (canonical: the "label rules" in the `gaia sdk` reference):

- Valid Gaia QID: `[a-z_][a-z0-9_]*`. Lowercase letters, digits, underscores.
- No hyphens, no dots, no uppercase, no diacritics.
- 1–4 token semantic suffixes; do not pack the body into the label.

The Python LHS binding name (the variable the rest of the package references)
should equal the label, so a claim is `liu2015_c1_yield = claim(...)`.

## Workflow step 2 — Scaffold the package and add one module per section

Bootstrap the package directory:

```bash
gaia pkg scaffold \
    --target <name>-gaia \
    --name <name>-gaia \
    --namespace <namespace> \
    --with-uuid \
    --description "<one-line description from the motivation note>"
```

This writes `pyproject.toml` (with `[tool.gaia] type = "knowledge-package"` and
a minted `uuid`), `src/<import_name>/__init__.py`, and `.gaia/.gitkeep`. Use the
namespace the calling SOP chose for this run.

**Organize by section — one module (Python file) per source section.** This
matches `gaia-formalize-fine` and the upstream knowledge-package convention,
and keeps the package traceable back to the paper:

- Introduction / motivation → `motivation.py`
- Section II / Methods → `s2_methods.py`
- Section III / Results → `s3_results.py`
- Section IV / Discussion (if a distinct section) → `s4_discussion.py`
- Leaf priors → `priors.py`

Add each section module:

```bash
gaia pkg add-module --name <module_name> --target <name>-gaia
gaia pkg add-module --name priors --imports register_prior --target <name>-gaia
```

**Place each knowledge node in the earliest module where it first appears.**
Content from the Introduction goes into `motivation.py`. A conclusion stated in
Results goes into `s3_results.py`. Claims in `motivation.py` can be freely
referenced as premises / `background=` by later modules — module membership does
not restrict cross-module references; later modules `from .motivation import ...`.

If the paper has no clean section structure, a single `__init__.py` is
acceptable — but prefer per-section whenever the paper has identifiable sections.

## Workflow step 3 — Write the conclusions into their modules

Write each conclusion as a `claim(...)` into the module of the section where it
is established. In `motivation.py` (the introduction module), also emit the
whole-paper motivation as a single `note(...)` and the paper's overall open
problem as a single `question(...)`. At this point `motivation.py` holds the
motivation note + the open-problem question; section modules hold conclusion
claims only — no leaf premises, no derives. A section module under
construction in step 3:

```python
"""<Section heading — the module's docstring is the section title>."""

from gaia.engine.lang import claim, question, note

liu2015_c3_yield = claim(
    "<self-contained conclusion body, numbers + units inline>",
    title="<short title>",
    label="liu2015_c3_yield",
)
```

- **Motivation** — one `note(...)` in `motivation.py` summarizing the
  whole-paper motivation (the pre-paper problem-state, framing prose with no
  truth value). Distinct from the open problem below: the note is the *context*
  that necessitated the work; the question is the *research question* the work
  sets out to answer.
- **Conclusions** — one `claim(...)` per conclusion. Body = the self-contained
  body; do not rewrite it. Mint the label (above). The figure / table / citation
  `refs` collected in step 3 attach here.
- **Open problem (paper-level)** — one `question(...)` in `motivation.py`
  recording the paper's overall research question, bound `<key>_problem`.
  Single question at the paper level (not per conclusion). The paper's
  "future work" / unanswered next-step statements are not modelled — leave
  them out.

### Append each main conclusion to the root `__all__`

As you write each conclusion, also update the **root** package
`src/<import_name>/__init__.py` so the conclusion is part of the package's
exported surface. The engine reads `__all__` only from the root; section
modules' `__all__` are not propagated (`_record_root_exports` in
`gaia/engine/packaging.py`).
Methodology — including which knowledge kinds belong in `__all__` and why
coarse picks the curated surface — is in
[`phase-1-extract-conclusions.md`](phase-1-extract-conclusions.md)
("Mark each main conclusion in the root `__all__`"); the code shape is:

```python
# src/<import_name>/__init__.py
"""<package one-line description>."""

from gaia.engine.lang import claim

from .s2_methods import liu2015_c1_protocol
from .s3_results import liu2015_c3_yield, liu2015_c4_agreement

__all__ = [
    "liu2015_c1_protocol",
    "liu2015_c3_yield",
    "liu2015_c4_agreement",
]

from .authored import *  # scaffold-default re-export; harmless here
```

Do **not** add to `__all__`: the motivation `note(...)`, the open-problem
`question(...)`, weak point / highlight leaf-premise claims (step 5),
decompose parts (step 6 shared cause + residuals), or any relation labels
(see below). Section modules (`motivation.py`, `s2_methods.py`, …) keep
their scaffolded `__all__: list[str] = []` unchanged.

### Conclusion-level relations (also step 4 emission)

When step 4 (logic graph) surfaces `equal` / `contradict` / `exclusive` /
`associate` relations between conclusions, emit them into the **downstream-most
module among the two relata** so the relation can `import` both. Methodology
is in `phase-1-extract-conclusions.md` (§Relations between conclusions);
the code shape:

```python
from gaia.engine.lang import equal, contradict, exclusive, associate

from .s2_methods import liu2015_c1_theory_prediction
from .s3_results import liu2015_c3_experiment_value

# Hard: theory atom and experiment atom express the same proposition
liu2015_rel_theory_match = equal(
    liu2015_c1_theory_prediction,
    liu2015_c3_experiment_value,
    rationale="The theoretical prediction P = 0.42 ± 0.03 and the measured value …",
    label="liu2015_rel_theory_match",
)

# Hard: two competing hypotheses the paper says cannot both hold
liu2015_rel_models_incompatible = contradict(
    liu2015_c2_model_a, liu2015_c2_model_b,
    rationale="A and B predict opposite signs of the response …",
    label="liu2015_rel_models_incompatible",
)

# Hard: exhaustive binary choice (use decompose(formula=lor(...)) for n≥3)
liu2015_rel_binary_outcome = exclusive(
    liu2015_c4_outcome_pos, liu2015_c4_outcome_neg,
    rationale="On this benchmark the metric is signed; one of the two must hold.",
    label="liu2015_rel_binary_outcome",
)

# Soft: judgement-bound association (no logical entailment)
liu2015_rel_soft_assoc = associate(
    liu2015_c5_method, liu2015_c5_outcome,
    p_a_given_b=0.75, p_b_given_a=0.40,
    pattern="equal",
    rationale="The paper presents them as broadly consistent under regime X, but …",
    label="liu2015_rel_soft_assoc",
)
```

Relations carry no `register_prior` (hard verbs are deterministic;
`associate` carries its conditionals directly) and are **not** in `__all__`.

## Workflow step 5 — Per conclusion: leaf premises + derive

Walk the conclusions in topological order on the logic graph. For each
conclusion, follow this conceptual order before emitting:

1. **Atomicity re-check before the derive.** Building the evidence chain often
   exposes a still-bundled conclusion — most commonly a theoretical prediction
   fused with its experimental measurement (or a method fused with its
   produced value). Per `_shared/formalize-atomicity.md` ("Separate theory from
   experiment", "Separate method from result"), split it now: replace the
   bundled `claim(...)` in the module with the atomic ones, update the logic
   graph, and proceed with each atomic conclusion separately.
2. Summarize the paper's reasoning chain **for this (now-atomic) conclusion
   specifically** — the chain's content matches the conclusion's nature: a
   theoretical conclusion gets its mathematical / logical derivation; an
   experimental measurement gets the experimental procedure (setup, instrument,
   sampling, how the value was read out); a computational result gets the
   method + parameters + numerical run. After an atomicity split, the theory
   atom and the experiment atom each get their own chain; do not collapse them.
   This prose becomes `rationale=`.
3. From the reasoning, identify which upstream conclusions it depends on (from
   the step-4 logic graph) — these are the first entries in `given=`.
4. Surface the **residual** weak points and highlights — the load-bearing
   uncertainties and strengths the reasoning rests on **beyond** what the
   upstream conclusions already capture. A factor already represented by an
   upstream conclusion is not duplicated here; only the new, this-derivation-
   specific factors become leaf premises.
5. Emit the leaf-premise `claim(...)`s, then the `derive(...)`. Append both to
   the conclusion's module, then compile-check before moving on:

```python
from .s2_methods import liu2015_c1_protocol   # upstream conclusion it depends on

# leaf premises (weak points + highlights) — same shape; only the prior
# (set in priors.py) and the _wp_ / _hl_ infix differ:
liu2015_c3_wp_sample = claim("<weak-point body>", title="...", label="liu2015_c3_wp_sample")
liu2015_c3_hl_crosscheck = claim("<highlight body>", title="...", label="liu2015_c3_hl_crosscheck")

liu2015_c3_chain = derive(
    liu2015_c3_yield,
    given=[liu2015_c1_protocol, liu2015_c3_wp_sample, liu2015_c3_hl_crosscheck],
    rationale="<reasoning chain; warrant-strength intent inline>",
    label="liu2015_c3_chain",
)
```

- **Leaf-premise claims (weak points + highlights)** — one `claim(...)` each;
  same kind of leaf premise, differing only in prior magnitude (weak points
  lower, highlights higher) and the `_wp_` / `_hl_` infix. Each is defined once.
- **One `derive(...)` per conclusion** (every conclusion — there are no isolated
  conclusions). Build `given=` **in order**: first the upstream conclusions it
  depends on (every one, topological order), then this conclusion's leaf
  premises. A root with no upstream still has its ≥1 supporting leaf premise.
  Apply the Pattern 1c check (drop an upstream that reaches the conclusion only
  through another upstream).
  - **Do not pass `metadata=` to `derive(...)`** — the signature is
    `{given, background, rationale, label}` (same for `contradict` / `equal` /
    `exclusive` / `observe`). Warrant-strength intent lives in `rationale=`
    prose, not a kwarg; the numeric prior surface lives only on leaf premises.

The string body of every `claim(...)` / `question(...)` is the self-contained
body — no rewriting at emit time; the extraction and body-writing discipline
already satisfied the requirements.

## Workflow step 6 — Finalize

### 6a. Shared-factor decomposition (Pattern 3, global)

Run the independence scan over **all** leaf premises (phase-3 "Shared-factor
evidence"). For each group sharing a latent cause, do **not** delete the
originals — keep each and emit a `decompose(...)` splitting it into the shared
cause and its residual:

```python
decompose(
    c2_wp_sample_size,
    parts=[sample_size_limit, c2_resid],
    formula=land(sample_size_limit, c2_resid),
    rationale="...",
)
```

The `sample_size_limit` claim (the shared cause) is reused as a part across
every original in the group, so the shared uncertainty enters the graph once;
each residual is its own part. Shared cause and residual are new self-contained
`claim(...)`s. This is the only place coarse uses `decompose`.

### 6b. Write `priors.py`

Emit a `register_prior(...)` for **every leaf premise and nothing else**.
Conclusions never get a prior — there are no isolated conclusions (every
conclusion is the conclusion of a `derive(...)`), so a conclusion's belief
always propagates from its premises; it is never a leaf.

- Every leaf premise from the step-5 audit — weak point **and** highlight —
  is a leaf; its reviewer-judged prior goes here verbatim. No cap: weak points
  land lower, highlights higher (often 0.9+); the only bounds are BP validity
  (strictly between 0 and 1, practical extremes ~0.001 / ~0.999).

```python
"""Leaf-claim priors."""

from gaia.engine.lang import register_prior
from .s3_results import liu2015_c3_wp_sample

register_prior(
    liu2015_c3_wp_sample,
    value=0.55,
    justification="<one-line rationale ending in TODO:review>",
)
```

Justification format: one line, terse rationale ending with `TODO:review`. This
is where the reviewer reasoning from the step-5 audit lives — for a weak point,
the `weakness_reason` plus the `failure_mode` (why it is uncertain and what
breaks if it fails) compressed to one sentence; for a highlight, why the
reviewer is near-certain of it. There is no separate stored field — the
justification string is the reasoning.

### 6c. Write `references.json`

Emit a CSL-JSON object keyed by citation key. Each entry:

- `type`: `article-journal` (default; switch to `paper-conference`,
  `book-chapter`, etc. only if the paper clearly indicates so).
- `title`, `DOI`, `container-title`, `issued`, `author` — from the paper's own
  metadata. Do not invent fields; omit missing ones.

Full schema: `docs/specs/2026-04-09-references-and-at-syntax.md`.

### 6d. Full compile, then fix

Run the full-package compile (per-module compile-checks already happened in
step 5; this catches cross-module issues):

```bash
gaia build compile <name>-gaia/
```

If it fails, read **all** diagnostics at once, fix the offending module(s), and
recompile. Repeat until clean. A full compile catches cross-module issues
(cyclic imports, unresolved references, IR-hash drift, manifest emission) that a
per-statement check cannot.

### 6e. Self-check before reporting complete

After a clean compile, verify the SOP-owned semantic content:

1. **No isolated conclusion.** Every conclusion is the conclusion of exactly
   one `derive(...)`; none is left without a deduction. `gaia inquiry review`
   (the caller's hand-off gate) reports any orphaned claim — but catch it here
   first by confirming every conclusion written in step 3 appears as a
   `derive` conclusion.
2. Every leaf premise (every weak point, every highlight) has a
   `register_prior(...)` entry, and **no conclusion has one**; every prior is
   strictly between 0 and 1 (practical extremes ~0.001 / ~0.999) — no 0.9 cap.
3. Every `register_prior(...)` justification ends with `TODO:review`.
4. Every `claim(...)` body passes the self-standing test: stripped of all
   surrounding context, can a reader unfamiliar with the paper identify the
   model / system / regime, the symbols, and the claim? If any body fails,
   rewrite it before reporting completion.
5. **Pointer and citation hygiene** (both must pass):
   - **5a.** No paper-internal pointer (`Eq. (X)` / `Fig. Y` / `Table Z` /
     `Sec. W` / `Appendix A` / `Theorem N` / `Lemma M`) appears inside a
     `claim(...)` body, a `derive(...)` rationale, or a `register_prior(...)`
     justification. External `[@key]` citations are allowed in any prose.
   - **5b.** Every prose citation uses `[@key]` form, where `key` matches an
     entry in `references.json`. Numeric paper-style citations (`[33]`,
     `Ref. 5`, `Smith et al., 2020`) must not survive — convert at write time.
     Unresolvable citations are emitted as `@unknown_<n>` (bare, **no brackets**
     — bracketed `[@unknown_n]` fails the strict-reference check).
6. `references.json` contains an entry for every `[@key]` cited in any prose.
7. **Public surface (`__all__`)**: the root `src/<import_name>/__init__.py`
   has a non-empty `__all__` listing **every main conclusion** written in
   step 3 — and nothing else. No motivation `note(...)` label, no
   open-problem `question(...)` label, no `_wp_` / `_hl_` leaf-premise
   label, no `derive(...)` label, no relation label (`equal` / `contradict` /
   `exclusive` / `associate`), no `register_prior` label, no shared-cause /
   residual label from 6a. The scaffold default `__all__: list[str] = []` must
   have been replaced in step 3 as each conclusion was written; an empty or
   missing `__all__` exports nothing, so downstream tools would see a package
   with no headline contributions.

If any check fails, fix it and recompile before reporting completion.

### 6f. Hand off

Report to the user:

- The path of the emitted `<name>-gaia/` directory.
- The counts: conclusions, weak points, deductions, priors, plus the
  `gaia build compile` IR-side counts (knowledge / strategy / operator).
- The three follow-up quality-gate commands the user is expected to run:
  - `gaia build compile <name>-gaia/` — full-package compile.
  - `gaia run infer <name>-gaia/` — belief propagation; emits
    `.gaia/beliefs.json` for downstream posterior inspection.
  - `gaia inquiry review --strict <name>-gaia/` — strict warrant / obligation /
    duplicate-control review.

This skill does not run the quality gates itself beyond the finalize compile;
surfaced inquiry-review findings come back as a follow-up obligation.
