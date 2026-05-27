# Extracting a paper's conclusions

Shared reference for `gaia-formalize-coarse` and `gaia-formalize-fine`. Both
skills begin by reading the paper and identifying its genuine new
contributions as claims; this file is the canonical statement of *what* to
extract and *how each extracted claim must read*. Reference, not procedure —
no frontmatter, not itself a skill.

This file does **not** own extraction mechanics — working notes vs incremental
DSL, module layout, the `note` / `question` node kinds, label minting — those
belong to the calling skill. Atomicity (one claim = one question) has its own
file, `formalize-atomicity.md`.

## What counts as a conclusion

A conclusion is **new author-asserted knowledge that would not exist if this
paper had not been written**:

- a newly derived formula, theoretical relation, or analytical result;
- a quantitatively new numerical or experimental value, scaling law, phase
  boundary, or benchmark;
- a newly proposed algorithm, computational scheme, or experimental method.

It is **not**:

- a restatement of prior work;
- a trivial corollary of the paper's own assumptions;
- a rhetorical claim of importance, motivation, or future work;
- a reformulation that adds no information.

## Fidelity to the paper

The paper text is the only source of truth. While extracting:

- Do not strengthen heuristic claims into established facts.
- Do not supply missing derivations or repair broken arguments.
- Do not import outside knowledge, even to "fix" an undefined symbol — leave
  it undefined and surface the gap.
- Preserve the authors' epistemic hedging exactly: regimes, error bars,
  speculative qualifiers, modal force ("suggests" stays "suggests").

## Write every claim self-contained

Each claim body must be a complete proposition a reviewer can judge without
reading the paper or any other claim:

- **Symbols** — every mathematical symbol gets a brief meaning on first use in
  that body (`$\alpha$ (ratio of XX to YY)`), not bare (`$\alpha \ll 1$`).
  Each claim is independent; re-explain a symbol even if another claim already
  did.
- **Acronyms** — expanded on first use in that body, every time.
- **Setup** — the system / model / dataset / regime is described inside the
  proposition, not assumed.
- **Concrete subject** — every sentence's subject is the model, the
  estimator, the measurement — never "the paper" or "this work".
- **No bare comparatives** — not "significantly larger than X" or "nearly
  exact agreement"; give both numbers.
- **Inline values, not pointers** — write the equation, the value, the setup
  into the body; never "Eq. (3)" or "Fig. 4" (see "No paper-internal
  pointers" below).

## Content format

Claim bodies support Markdown — use it for structure:

- **Tables** — Markdown tables for structured data.
- **Math** — `$...$` inline, `$$...$$` display. LaTeX, not Unicode math
  symbols.
- **Lists** — bullets to enumerate conditions or items.
- **Emphasis** — bold / italic for key values or terms.

## Figures and tables → inline as prose

The paper Markdown does not carry figure pixels. When the paper's argument
relies on what a figure or table shows, transcribe the quantitative content
into the claim body: the specific values, the curve shape, the trend, the
comparison.

```python
tc_data = claim(
    "Measured superconducting transition temperatures:\n\n"
    "| Material | $T_c$ (K) | Pressure (GPa) |\n"
    "|----------|-----------|----------------|\n"
    "| LaH10    | 250       | 200            |\n"
    "| H3S      | 203       | 150            |",
    title="Tc measurements",
)
```

The claim body carries everything needed for judgement. A figure/table
reference in `metadata` is for **traceability only**, never for conveying
information the body omitted.

## No paper-internal pointers; refs whitelist

Structural pointers into the paper — `Eq. (5)`, `Fig. 3`, `Table I`,
`Sec. II`, `Appendix A`, `Theorem 2`, `Lemma M`, footnotes — must not appear
inside a claim body. Resolve every such pointer by inlining its content.

For traceability, note the figures / tables / equations / external citations
that primarily evidence each conclusion. The **only three** pointer kinds that
may be retained (as `refs` metadata) are:

- **`figure`** — a figure or table (`Fig. 2`, `Table I`).
- **`equation`** — an equation referenced by number (`Eq. (5)`).
- **`citation`** — an external bibliographic reference. Convert the paper's
  numeric citations (`[33]`, `Ref. 5`) to a key of first-author surname plus
  year (`Smith2020`); the same key goes into `references.json`.

Section / appendix / paragraph / theorem / lemma / footnote pointers are
**not** legitimate `refs` entries — inline their content instead.

## Citation form in prose

External citations in any prose (claim bodies, rationales) use the `[@key]`
form, where `key` matches an entry in `references.json`
(`<FirstAuthorSurname><Year>`, e.g. `[@Smith2020]`). Never leave numeric
paper-style citations (`[33]`, `Ref. 5`, `Smith et al., 2020`) in prose;
convert at write time. If a key cannot be derived from the paper's
bibliography, use bare `@unknown_<n>` (**no brackets** — bracketed
`[@unknown_n]` fails the compiler's strict-reference check; bare `@key` is
opportunistic) and surface the gap. The full citation contract lives in
`docs/for-users/language-reference.md`.

## Extract both sides of every comparison

When the paper compares a theoretical prediction against an experimental
observation, extract **both** as separate claims (atomicity requires this too
— see `formalize-atomicity.md`), so the verification relation can be wired
later. When several competing theories are compared against one observation,
extract **each** competing prediction as its own claim.

When the paper argues one general rule is confirmed by repeated independent
observations (multiple samples, labs, conditions), extract **each
observation** as its own claim plus the candidate rule as its own claim. The
wiring — and the independence judgement those observations must satisfy — is
covered in `formalize-reasoning-chains.md` and `formalize-independence.md`.
