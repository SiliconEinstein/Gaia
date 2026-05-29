# Phase 4 — Emit the Gaia Package

Load this file after Phase 3 is complete. This is the only phase that writes
files. It composes the working notes from Phases 1–3 into a standalone Gaia
knowledge package on disk.

## Goal

Produce a `<name>-gaia/` package on disk per the Gaia knowledge-package spec
(file layout: `docs/for-users/quick-start.md`; `claim` / `derive` /
`question` body discipline, label rules: `docs/for-users/language-reference.md`).
After emission, the package must compile with `gaia build compile` and pass
`gaia build check --hole .` (see `docs/for-users/cli-commands.md`).

## Authoring surface — write the DSL directly

**Writing the DSL via the Python SDK is the primary authoring path.** Phase 4
emits modules by writing Python source files directly (the file-write tool of
your choice), not by driving the `gaia author` CLI one statement at a time. The
`gaia author` CLI exists as an optional convenience; it writes the *same*
statements one per invocation, which for a whole-paper package is dozens of
round-trips. A direct module write is one file per section, then a single
compile.

Before emitting, read the canonical DSL cheat sheet:

```bash
gaia sdk            # writes ./gaia-sdk/ — SDK reference + one-page CHEATSHEET.md
```

The cheat sheet is authoritative for every primitive (`claim`, `note`,
`question`, `derive`, `register_prior`, distributions, relations). Phase 4
below is just the sequencing of those primitives for a single paper.

The DSL primitives this skill emits:

| Phase 4 emission | DSL primitive |
|---|---|
| Motivation question | `question(...)` |
| Conclusion / weak-point claim | `claim(...)` |
| Transcribed figure / table context | `note(...)` (optional) |
| Deduction (1+ premises → conclusion) | `derive(...)` |
| Leaf prior record | `register_prior(...)` |

## Step 0 — Decide the package name and import name

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

## Step 1 — Mint claim labels

For every Phase 1 conclusion, mint a label `<key>_c<id>_<semantic_suffix>`,
where the suffix is 1–4 tokens drawn from the conclusion's title (lowercase,
ASCII, underscores only).

For every Phase 3 weak point, mint a label `<key>_c<id>_wp_<semantic_suffix>`.

Label rules (canonical: `docs/for-users/language-reference.md` "label rules"):

- Valid Gaia QID: `[a-z_][a-z0-9_]*`. Lowercase letters, digits, underscores.
- No hyphens, no dots, no uppercase, no diacritics.
- 1–4 token semantic suffixes; do not pack the body into the label.

The Python LHS binding name (the variable the rest of the package references)
should equal the label, so a claim is `liu2015_c1_yield = claim(...)`.

## Step 2 — Scaffold the package and add one module per section

Bootstrap the package directory:

```bash
gaia pkg scaffold \
    --target <name>-gaia \
    --name <name>-gaia \
    --namespace <namespace> \
    --with-uuid \
    --description "<one-line description from Phase 1 motivation>"
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

## Step 3 — Write each section module directly

For each section module, use the file-write tool to emit the whole file in one
write. A module looks like:

```python
"""<Section heading — the module's docstring is the section title>."""

from gaia.engine.lang import claim, derive, question, note
# later modules also import upstream claims they premise on:
# from .motivation import liu2015_problem
# from .s2_methods import liu2015_c1_protocol

# --- conclusions (Phase 1, this section) ---
liu2015_c3_yield = claim(
    "<self-contained conclusion body, numbers + units inline>",
    title="<short title>",
    label="liu2015_c3_yield",
)

# --- weak-point leaf claims (Phase 3, bound to this section's conclusions) ---
liu2015_c3_wp_sample = claim(
    "<self-contained weak-point body>",
    title="<short title>",
    label="liu2015_c3_wp_sample",
)

# --- deductions (one per derived conclusion in this section) ---
liu2015_c3_chain = derive(
    liu2015_c3_yield,
    given=[liu2015_c1_protocol, liu2015_c3_wp_sample],
    rationale="<Phase 2 numbered chain prose; warrant-strength intent inline>",
    label="liu2015_c3_chain",
)
```

Emission rules (carried over from the per-statement CLI path):

1. **Motivation as `question(...)`** — one `question(...)` in `motivation.py`
   for Phase 1's motivation block, bound as `<key>_problem`.
2. **Conclusions** — one `claim(...)` per Phase 1 conclusion, in topological
   order, in the module for the section where it first appears. Body = the
   self-contained body from Phase 1 working notes; do not rewrite here.
3. **Weak-point leaf claims** — one `claim(...)` per Phase 3 weak point, each
   defined exactly once. A weak point that undermines a single conclusion is a
   premise in that one conclusion's deduction; when the conclusions are linked
   by the logic graph, bind it upstream and let it propagate rather than
   re-listing it downstream. A Phase 3 **shared-factor** weak point (one cause
   that genuinely bounds several conclusions with no logic-graph link between
   them) is the exception: list it in the `given=[...]` of each conclusion it
   bounds, so the shared uncertainty enters once and reaches every dependent.
   This does not incur a fan-out penalty — deduction implication factors are
   directed. The per-conclusion **residuals** of that group stay as ordinary
   single-conclusion weak points, each listed only in its own conclusion's
   `given=[...]`.
4. **Deductions** — one `derive(conclusion, given=[...], rationale=..., label=...)`
   per derived conclusion. The `given=` list is the union of upstream conclusion
   bindings and this conclusion's weak-point bindings.
   - **Do not pass `metadata=` to `derive(...)`** — the engine signature accepts
     only `{given, background, rationale, label}`. The same applies to
     `contradict` / `equal` / `exclusive` / `observe`. Warrant-strength intent
     lives in `rationale` prose, not a metadata kwarg.
   - Warrant-strength intent: when Phase 2 surfaced an explicit logical gap, say
     so in the rationale; when Phase 3 surfaced a highlight underwriting a step,
     say so. The numerical prior surface lives only on leaf claims in `priors.py`.
5. **Open questions (optional, opt-in)** — only when the user asks, emit
   `question(...)` bound as `<key>_open_question_<n>`.

The string body of every `claim(...)` / `question(...)` is the self-contained
body from working notes — no further rewriting in Phase 4. The Phase 1
self-containment discipline and the Phase 3 body-writing rule already satisfy
the body requirements; this phase only places and emits.

## Step 4 — Write `priors.py`

For every **leaf** claim, emit a `register_prior(...)`:

- Every Phase 3 weak point is a leaf — its `prior_probability` from working
  notes goes here, capped at 0.9 (floor 0.001).
- A Phase 1 conclusion with **no** upstream conclusions and **no** weak points
  is also a leaf — its prior comes from Phase 3's per-conclusion
  `prior_probability`, capped at 0.9.

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

Justification format: one line, terse rationale (model assumption / empirical
pattern / cited result) ending with `TODO:review`. Pull it from the weak point's
`weakness_reason` (compressed to one sentence) or the conclusion's `narrative`.

## Step 5 — Write `references.json`

Emit a CSL-JSON object keyed by citation key. Each entry:

- `type`: `article-journal` (default; switch to `paper-conference`,
  `book-chapter`, etc. only if the paper clearly indicates so).
- `title`, `DOI`, `container-title`, `issued`, `author` — from the paper's own
  metadata. Do not invent fields; omit missing ones.

Full schema: `docs/specs/2026-04-09-references-and-at-syntax.md`.

## Step 6 — Compile once, then fix

Run a single full-package compile:

```bash
gaia build compile <name>-gaia/
```

If it fails, read **all** diagnostics at once, fix the offending module(s), and
recompile. Repeat until clean. A full compile catches cross-module issues
(cyclic imports, unresolved references, IR-hash drift, manifest emission) that a
per-statement check cannot.

## Step 7 — Self-Check Before Reporting Complete

After a clean compile, verify the SOP-owned semantic content:

1. Every leaf claim (every weak point + any isolated conclusions) has a
   `register_prior(...)` entry; no prior exceeds 0.9 or falls below 0.001.
2. Every `register_prior(...)` justification ends with `TODO:review`.
3. Every `claim(...)` body passes the self-standing test: stripped of all
   surrounding context, can a reader unfamiliar with the paper identify the
   model / system / regime, the symbols, and the claim? If any body fails,
   rewrite it before reporting completion.
4. **Pointer and citation hygiene** (both must pass):
   - **4a.** No paper-internal pointer (`Eq. (X)` / `Fig. Y` / `Table Z` /
     `Sec. W` / `Appendix A` / `Theorem N` / `Lemma M`) appears inside a
     `claim(...)` body, a `derive(...)` rationale, or a `register_prior(...)`
     justification. External `[@key]` citations are allowed in any prose.
   - **4b.** Every prose citation uses `[@key]` form, where `key` matches an
     entry in `references.json`. Numeric paper-style citations (`[33]`,
     `Ref. 5`, `Smith et al., 2020`) must not survive — convert at write time.
     Unresolvable citations are emitted as `@unknown_<n>` (bare, **no brackets**
     — bracketed `[@unknown_n]` fails the strict-reference check).
5. `references.json` contains an entry for every `[@key]` cited in any prose.

If any check fails, fix it and recompile before reporting completion.

## Step 8 — Hand Off

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

This skill does not run the quality gates itself beyond the Step 6 compile;
surfaced inquiry-review findings come back as a follow-up obligation.
