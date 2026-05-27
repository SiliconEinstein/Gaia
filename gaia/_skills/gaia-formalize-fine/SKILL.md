---
name: gaia-formalize-fine
description: |
  Use when formalising a knowledge source (scientific paper, textbook chapter,
  technical report) into a Gaia knowledge package and you want the thorough,
  audit-grade treatment. Walks a six-pass pipeline — extract → connect → check
  completeness → refine strategy types → verify structural integrity → polish
  for standalone readability — with a compile + check loop after every pass and
  a prior-assignment + inference tail. Emits the package source, `priors.py`,
  and `ANALYSIS.md`. This is the **Paper → package** entry point when depth
  matters: the slow, exhaustive sibling of `gaia-formalize-coarse` (which is a
  quick four-phase single-pass for one paper). Reach for `gaia-formalize-fine`
  when the source is load-bearing, multi-section, or destined for publication;
  reach for `gaia-formalize-coarse` for a fast first cut of a single paper.
---

# Knowledge-package formalization

Drive an agent through formalising a source (scientific paper, textbook chapter, technical report) into a Gaia knowledge package. The output is DSL source under `src/<pkg>/` — `claim`, `derive`, `infer`, `observe`, `compute`, `equal`, `contradict`, `exclusive`, `decompose`, `note`, `question`, `compose` statements authored either via the `gaia author <verb>` CLI or by hand — plus `priors.py` for leaf-claim priors, plus a critical-analysis `ANALYSIS.md` deliverable. Every CLI verb the skill calls is on `gaia` today; the skill is the methodology that surrounds them.

## Overview

Formalization is a **six-pass** process. Each pass builds on the previous one. Do not skip passes or combine them.

**Key principle: formalization is incremental.** After completing each pass, write code, compile, and check. Do not wait until all passes are done before writing code. Feedback from `gaia build compile` and `gaia build check` is critical input for the next pass.

```
Pass 1: Extract                 → write DSL code
  ↓ gaia build compile + gaia build check
Pass 2: Connect                 → wire premises to conclusions with derive / infer / observe / compute / decompose; add equal / contradict / exclusive
  ↓ gaia build compile + gaia build check
Pass 3: Check completeness      → @labels audit, missing reasoning, isolated nodes
  ↓ gaia build compile + gaia build check
Pass 4: Refine strategy types   → tighten infer → derive / compute / observe / compose
  ↓ gaia build compile + gaia build check
Pass 5: Structural integrity    → operator semantics, double-counting elimination, hidden-evidence-in-reason, shared-dependency extraction
  ↓ gaia build compile + gaia build check
Pass 6: Polish                  → self-containedness, figures, formatting
  ↓ gaia build compile + gaia build check
gaia build check --hole         → write priors.py
  ↓
gaia run infer .                → .gaia/beliefs.json
  ↓ Interpret BP results (see ../_shared/bp-interpretation.md)
  ↓ ┐
    │ structural issues  → back to Pass 1-5
    │ prior issues       → revise priors.py
    └ otherwise          → ANALYSIS.md → gaia run render --target github
```

| Pass | Focus | Core question |
|------|-------|---------------|
| 1 | Content extraction | Are claims and notes extracted? Atomic? |
| 2 | Reasoning connections | Are derivations, inferences, observations, computes, and structural relations modelled? |
| 3 | Content completeness | Any missing premises, orphans, or `@label` errors? |
| 4 | Strategy precision | Is each author verb the right one (`derive` vs `infer` vs `compute` vs `observe` vs `compose`)? |
| 5 | Structural integrity | Is evidence independent? Are `contradict` / `exclusive` semantics correct? |
| 6 | Standalone readability | Can a reviewer understand everything without the source? |

## Scope

Formalize the **complete** source — not just the main result. A partial formalization leaves reasoning gaps: premises without support, alternatives without comparison, intermediate steps without justification. If the source is too large (a full textbook, say), formalize one chapter at a time, each as a separate Gaia package.

## CLI invocations referenced by this skill

The methodology below leans on this fixed set of CLI calls. Drill into `gaia <group> <verb> --help` when you need exact flags.

- `gaia pkg scaffold --target <name>-gaia --name <name>-gaia --namespace <ns> [--with-uuid] [--description "..."]` — fresh package skeleton (`pyproject.toml`, `src/<import_name>/__init__.py`, `.gaia/.gitkeep`). The import name is derived from `--name` (strip the trailing `-gaia`, hyphens → underscores); the CLI emits a JSON envelope. Does not create `artifacts/` or `references.json` — make those manually.
- `gaia pkg add-module --name <module> --target <name>-gaia [--imports <verbs>]` — scaffold a sibling module under `src/<import_name>/` (e.g. `motivation`, `s2_xxx`, `priors`). `--imports` pre-seeds DSL-verb imports (e.g. `--imports register_prior`).
- `gaia build compile <pkg>` — lower DSL → IR (`.gaia/ir.json`). Run after every pass.
- `gaia build check <pkg>` — structural validation + role classification (independent / derived / structural / background / scaffolded / orphaned). Use between passes:
  - `gaia build check <pkg> --brief` — per-module overview with strategy summaries.
  - `gaia build check <pkg> --show <module-or-label>` — expand a single module / claim / warrant tree.
  - `gaia build check <pkg> --hole` — list independent claims missing priors (with content + QID).
  - `gaia build check <pkg> --gate` — publish-readiness gate (CI-friendly, non-zero on failure).
- `gaia author <verb>` — append a DSL statement and re-check. The verbs you will use most:
  - `gaia author claim` — declare a `claim(...)` knowledge node (use when first surfacing a proposition).
  - `gaia author note` — declare a `note(...)` background statement (use for mathematical definitions, formal setups, fundamental principles).
  - `gaia author question` — declare a `question(...)` research question.
  - `gaia author derive --conclusion ... --given ...` — author a directed implication: premises rigidly support the conclusion. Carry `--rationale` for the natural-language justification; relation quality is reviewed through the rationale and gate workflow, not through a prior on the derived conclusion or helper.
  - `gaia author infer --evidence ... --hypothesis ... --p-e-given-h ...` — author a Bayesian update on new evidence; the `--p-e-given-h` likelihood is required, `--p-e-given-not-h` defaults to 0.5.
  - `gaia author observe --conclusion ... [--value ... --error ...]` — author a measurement event tied to a Claim, Variable, or Distribution.
  - `gaia author compute --conclusion-type ... --fn ... --given ...` — author a deterministic-computation step (a named callable produces the result Claim).
  - `gaia author decompose --whole ... --parts ... --formula-template and|or|atom` — split a composite claim into atomic parts.
  - `gaia author equal --a ... --b ...` — equate two claims (logical equivalence).
  - `gaia author contradict --a ... --b ...` — assert NOT (A AND B): both cannot be true, but both can be false.
  - `gaia author exclusive --a ... --b ...` — assert A XOR B: exactly one must be true (exhaustive + mutually exclusive).
  - `gaia author compose --from-file pattern.py` — register a `@compose`-decorated reusable reasoning pattern.
  - `gaia author register-prior --claim ... --value ... --justification ... [--file priors.py]` — write a `register_prior(...)` statement; auto-injects the import if the target file is a sibling.
- `gaia run infer <pkg>` — run BP, emit `.gaia/beliefs.json`. Pass `--depth N` (>0) to merge dependency packages' factor graphs for joint cross-package inference.
- `gaia run render <pkg> --target github` — generate `.github-output/` README + narrative outline (handoff to `../gaia-publish/SKILL.md`).
- `gaia run render <pkg> --target docs` — per-module Mermaid graphs in `docs/detailed-reasoning.md`.
- `gaia run render <pkg> --target obsidian` — `gaia-wiki/` skeleton (handoff to `../gaia-obsidian-wiki/SKILL.md`).

Author verbs accept either an existing identifier (`--conclusion my_claim`) or auto-author the conclusion in-line (`--conclusion-content "..."`). Every authored statement supports `--dsl-binding-name` (Python LHS) and `--label` (engine `label=` kwarg) — assign both when the statement needs to appear in `gaia build check --brief` output and be referenceable by downstream verbs.

## Pass 0 — Prepare artifacts

Copy the source materials into the package's `artifacts/` directory, and create a `references.json` for bibliographic citations.

```
my-package-gaia/
├── artifacts/
│   ├── paper.pdf
│   ├── paper.md
│   └── figures/...
├── references.json
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── motivation.py
│       └── ...
└── pyproject.toml
```

`gaia pkg scaffold` creates `pyproject.toml`, `src/<import_name>/__init__.py`, and
`.gaia/.gitkeep`; per-section modules (`motivation.py`, `s2_xxx.py`, ...) are added
with `gaia pkg add-module`. Neither command creates `artifacts/` or
`references.json` — make those manually.

### `references.json`

Bibliographic citations in CSL-JSON format (dict-by-key), shared across the entire package. Start with a minimal skeleton; fill incrementally as citations are needed during Passes 1-4:

```json
{
  "Dias2020": {
    "type": "article-journal",
    "title": "Room-temperature superconductivity in a carbonaceous sulfur hydride"
  }
}
```

Keys must follow Pandoc citation-key grammar (letters, digits, `_`, `-`, `.`, `:`, `/`). Each entry requires `type` (CSL 1.0.2) and `title` at minimum. Add new entries as you hit citations; do not enumerate everything upfront. Complete metadata (authors, DOI, volume, pages) is filled in during Pass 6.

`references.json` is optional — without it, `[@...]` citations are not available.

Both PDF and markdown formats are supported for artifacts. Throughout formalization, refer back to the originals in `artifacts/` to keep numbers, formulas, and reasoning steps consistent with the source.

## Progressive Workflow

After Pass 0, create a session todo list with the seven items below. Mark only
Pass 1 in progress. Do not load a later pass's reference file until the current
pass is complete **and** its compile + check inner loop passes — each pass
builds on the working state the earlier passes produced.

1. **Pass 1 — Extract knowledge nodes** — load
   [`references/pass-1-extract.md`](references/pass-1-extract.md).
2. **Pass 2 — Connect: write reasoning relations** — load
   [`references/pass-2-connect.md`](references/pass-2-connect.md).
3. **Pass 3 — Check completeness** — load
   [`references/pass-3-completeness.md`](references/pass-3-completeness.md).
4. **Pass 4 — Refine strategy types** — load
   [`references/pass-4-strategy-types.md`](references/pass-4-strategy-types.md).
5. **Pass 5 — Verify structural integrity** — load
   [`references/pass-5-structural-integrity.md`](references/pass-5-structural-integrity.md).
6. **Pass 6 — Polish for standalone readability** — load
   [`references/pass-6-polish.md`](references/pass-6-polish.md).
7. **Prior assignment, inference, ANALYSIS.md, render** — load
   [`references/priors-analysis-render.md`](references/priors-analysis-render.md).

Run the compile + check inner loop (below) after every pass. The six-pass
split is cumulative scaffolding — the emitted package must reflect all passes
as one coherent body of work, not six independent passes.


## Inner loop: compile + check after every pass

After completing each pass, write code, compile, and check.

```bash
gaia build compile <pkg>          # DSL → .gaia/ir.json
gaia build check <pkg>            # summary with prior annotations on independent claims
gaia build check <pkg> --hole     # detailed hole report: which claims still need priors
gaia build check <pkg> --brief    # overview: all modules with relation summaries
gaia build check <pkg> --show s6_xxx   # expanded view of a specific module
gaia build check <pkg> --show label    # detail view of a specific claim's warrant tree
```

**What to check in default output:**
- Each independent premise shows `prior=X` if set, or `⚠ no prior` if missing.
- The summary shows "Holes (no prior set): N" when any holes remain.

**What to check in `--hole` output:**
- Every hole claim has its content and QID listed — use this to write `priors.py` entries.
- Every covered claim shows its prior value and justification — verify these are reasonable.

**What to check in `--brief` output:**
- Every relation should show named labels (not `_anon_xxx`). If a relation's conclusion shows `_anon_xxx`, the Python LHS was not set — re-author with `--dsl-binding-name`.
- Claims should show their role (independent / derived / structural / background / scaffolded / orphaned) and prior if set.
- Use `--show <module>` to inspect full claim content and warrant trees for review readiness.

## Common mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Theoretical prediction and experimental result mixed in one claim | Cannot model the verification relationship with `infer` | Separate into two claims + `infer(evidence=obs, hypothesis=pred)` |
| `infer` without a meaningful alternative or with `--p-e-given-not-h` left at 0.5 when the source argued otherwise | Bayesian update misses the competing-explanation force | Set `--p-e-given-not-h` from the source, or chain `infer` against each alternative hypothesis |
| `infer` alternative's prior reflects "computational correctness" instead of "explanatory power" | π(Alt) too high, weakens evidence's pull toward H | π(Alt) answers "Can Alt independently explain Obs?", not "Is Alt's calculation correct?" (see `../gaia-review/SKILL.md`) |
| Rationale written too briefly (one sentence) | Reasoning process is untraceable | Summarise derivation steps in detail, reference with `@label` |
| 4+ premise flat `derive` | Severe BP multiplicative effect | Use `compose` to decompose into sub-steps with 3 or fewer premises |
| Content not self-contained (symbols / abbreviations unexplained) | Reviewer cannot judge independently | Each claim must independently explain all symbols and abbreviations |
| Marking a questionable proposition as `note` | That proposition cannot be updated via BP | When in doubt, mark as `claim`; only mathematical definitions are `note`s |
| Marking a condition-dependent theoretical framework as `note` | Framework does not participate in BP | Condition-dependent conclusions should be claims |
| Using `derive` for a Bayesian update | Loses the explicit P(E\|H) / P(E\|~H) the source supplied | Use `infer` with `--p-e-given-h` and `--p-e-given-not-h` |
| Using `infer` for a step-by-step deterministic derivation | Forces a Bayesian update where rigid implication is the source's framing | Use `derive` with a detailed `rationale`; do not add a prior to the derived conclusion or helper |
| Using `derive` for a numerical computation whose function is in code | Loses the deterministic-mapping framing | Use `compute --fn ...` with the named callable |
| Anonymous relation (no `--dsl-binding-name`) | Relation invisible in `gaia build check --brief`, cannot be reviewed | Assign via `--dsl-binding-name <name> --label <name>` |
| `_`-prefixed claim or relation | Node invisible in CLI output, gets no label | Use public names (no `_` prefix); only `__` is reserved for compiler |
| Missing prior for orphaned claim | `gaia run infer` errors | All claims (including orphaned) need priors |
| Missing implicit premises in reasoning | Knowledge graph is incomplete | Use `gaia build check` + manual review in Pass 3 |
| Not verifying numerical values | Data errors | Cross-check every value against the source |
| Same claim in multiple paths to same conclusion | Evidence double-counted, inflated belief | Ensure each leaf enters a conclusion through exactly one path (Pass 5) |
| Repeated observations with unmodelled shared dependency | Overcounted evidence | Extract shared dependencies as explicit claims (Pass 5) |
| Wrong `contradict` (claims can both be true) | BP forced to suppress one side incorrectly | Verify structural-verb semantics in Pass 5 |
| Setting prior on derived claim | Double-counts evidence | Do not set priors for derived claims; inference engine defaults to 0.5 |
| Observation claim missing prior (classified as derived because it has incoming supports) | Observation's empirical grounding lost; belief depends entirely on theory relations instead of being anchored by data | Add observation to `priors.py` with high prior (0.9+), or use `observe` to tie it directly to a measurement value |

## Reference Files

### Passes (this skill)

- [`references/pass-1-extract.md`](references/pass-1-extract.md) — extract `claim` / `note` / `question` knowledge nodes.
- [`references/pass-2-connect.md`](references/pass-2-connect.md) — wire reasoning relations and structural verbs.
- [`references/pass-3-completeness.md`](references/pass-3-completeness.md) — `@label` / citation consistency, missing reasoning, isolated nodes.
- [`references/pass-4-strategy-types.md`](references/pass-4-strategy-types.md) — tighten `infer` into the most specific verb.
- [`references/pass-5-structural-integrity.md`](references/pass-5-structural-integrity.md) — structural-verb semantics and double-counting.
- [`references/pass-6-polish.md`](references/pass-6-polish.md) — self-containedness, figures, citation metadata.
- [`references/priors-analysis-render.md`](references/priors-analysis-render.md) — `priors.py`, inference, `ANALYSIS.md`, render handoff.

### Shared formalization methodology (`../_shared/`)

Shared with `gaia-formalize-coarse`; loaded by the passes that need them:

- [`../_shared/formalize-extract-conclusions.md`](../_shared/formalize-extract-conclusions.md) — what counts as a conclusion, fidelity, self-contained bodies, figures as prose, `refs` whitelist, citation form (Pass 1).
- [`../_shared/formalize-atomicity.md`](../_shared/formalize-atomicity.md) — one claim = one citable question, under-splitting traps, the two tests (Pass 1).
- [`../_shared/formalize-reasoning-chains.md`](../_shared/formalize-reasoning-chains.md) — logic graph, topological order, reasoning-trace reconstruction, step rules (Pass 2).
- [`../_shared/formalize-independence.md`](../_shared/formalize-independence.md) — no-double-counting check, the four patterns, shared-factor extraction (Pass 5).
- [`../_shared/bp-interpretation.md`](../_shared/bp-interpretation.md) — interpreting `.gaia/beliefs.json` (prior-assignment tail).

### Sibling skills

- [`../gaia-formalize-coarse/SKILL.md`](../gaia-formalize-coarse/SKILL.md) — the quick four-phase single-pass sibling, for a fast first cut of one paper.
- [`../gaia-review/SKILL.md`](../gaia-review/SKILL.md) — prior-assignment guide for independent leaf claims (evidence-level → prior-range tables, π(Alt) explanatory-power semantics, iteration loop).
- [`../gaia-publish/SKILL.md`](../gaia-publish/SKILL.md) — README narrative discipline after `gaia run render --target github`.
- [`../gaia-obsidian-wiki/SKILL.md`](../gaia-obsidian-wiki/SKILL.md) — rich Obsidian-vault discipline after `gaia run render --target obsidian`.
