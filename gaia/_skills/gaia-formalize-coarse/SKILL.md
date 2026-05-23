---
name: gaia-formalize-coarse
description: |
  Use for a quick, single-paper formalization into a Gaia knowledge package:
  read one academic paper (Markdown preferred; plain-text or other readable
  formats also accepted) and emit a standalone `<name>-gaia/` package. Runs a
  four-phase analytical workflow (Phase 1 extract conclusions / motivation /
  open questions / cross-conclusion logic graph; Phase 2 reconstruct each
  conclusion's reasoning chain; Phase 3 audit weak points and highlights,
  calibrate leaf priors; Phase 4 emit Gaia DSL package files), gated by an
  upfront suitability check (skip review/survey/perspective papers and
  corrupted paper text). Surfaces 9 argument-pattern weak-point types
  (`measurement`, `causal`, `model`, `statistical`, `generalization`,
  `comparative`, `formal`, `computational`, `external`). Cross-grounds the
  paper against LKM's existing knowledge graph in Phase 1b via
  `gaia search lkm knowledge`, filtering on `provenance.source_packages` and
  verifying reasoning-chain closure via `gaia search lkm reasoning --claim-id`.
  This is the **Paper → package** entry point when speed matters — the quick
  four-phase single-pass sibling of `gaia-formalize-fine` (the thorough
  six-pass treatment). Reach for `gaia-formalize-coarse` for a fast first cut
  of one paper; reach for `gaia-formalize-fine` when the source is
  load-bearing, multi-section, or destined for publication. For the
  LKM-driven (not paper-driven) route that grows a multi-paper graph, use
  the `gaia-explore` orchestrator client instead. Use whenever the user asks to "formalize a
  paper into Gaia", "produce a Gaia package from this paper", "turn this
  paper into a knowledge package", or any variant where the upstream is a
  single paper text and the requested output is Gaia DSL — even if the user
  does not explicitly mention Gaia DSL syntax.
---

# Formalize

## Mission

Read a single academic paper (Markdown preferred; plain-text or other
readable text formats also accepted), audit it as a scientific reasoning
reviewer would, and emit a standalone Gaia knowledge package that
compiles via `gaia build compile` and propagates beliefs via `gaia run infer`. The
agent running this skill does the analytical work itself; it does not
orchestrate a separate extraction pipeline and does not produce intermediate
XML artifacts.

Gaia knowledge-package shape is the canonical Gaia spec — see
`docs/for-users/language-reference.md` and `docs/for-users/quick-start.md` in
this repo. This skill defines the paper-driven workflow that produces packages
conforming to that spec.

```
paper.{md,txt,...}
  |
  v
gaia-formalize-coarse
  (standalone Gaia package source for that paper)
```

`gaia-formalize-coarse` is the **quick paper-driven** sibling of
[`../gaia-formalize-fine/SKILL.md`](../gaia-formalize-fine/SKILL.md) (the
thorough six-pass treatment of the same paper-driven route) and of the
**`gaia-explore`** orchestrator client — the **LKM-driven** turn loop that grows
a Gaia package from LKM evidence chains (a sibling of `gaia`, run as
`gaia-explore turn <pkg>`; not a registered skill). All three produce package
outputs of identical shape, but enter the graph from different directions: the
two `gaia-formalize-*` skills start from one paper and audit its derivations
(coarse = fast single-pass, fine = exhaustive six-pass); `gaia-explore` starts
from LKM search and grows a frontier across many papers.

## Output Mode

This skill operates in **single-paper batch mode** only:

- Input: one paper text file (`.md` preferred; plain-text and other readable
  formats also accepted) plus a desired package name (or one inferred from
  the paper's first author + year).
- Output: a fresh standalone `<name>-gaia/` package directory.

Refresh / multi-paper batches are out of scope; if the user wants to merge a
paper into an existing multi-paper package, the workflow is to produce the
single-paper package here and then hand it off to a downstream merge step.

## Progressive Workflow

At the start of each `gaia-formalize-coarse` run, create a session todo list
with the four items below. Mark only Phase 1 as in progress. Do not load later
phase documents until the current phase is complete; each later phase depends
on the working notes produced by the earlier phases.

1. **Extract conclusions, motivation, open questions, and the
   cross-conclusion logic graph** — load
   [`references/phase-1-extract-conclusions.md`](references/phase-1-extract-conclusions.md).
2. **Reconstruct each conclusion's reasoning chain** — load
   [`references/phase-2-build-reasoning-chain.md`](references/phase-2-build-reasoning-chain.md).
3. **Audit weak points and highlights, calibrate probabilities** — load
   [`references/phase-3-review-weak-points.md`](references/phase-3-review-weak-points.md).
   Phase 3 also contains the **Phase 1b LKM reverse-provenance trace** —
   a best-effort cross-grounding pass against LKM's existing graph via
   `gaia search lkm knowledge`. Skipped silently when the paper is
   not yet in the LKM corpus.
4. **Emit the Gaia package and audit log** — load
   [`references/phase-4-emit-package.md`](references/phase-4-emit-package.md).

After each phase, immediately mark the corresponding todo complete, mark the
next one in progress, and only then load the next phase document. Phases 1–3
produce structured working notes (held in the agent's scratch, not on disk).
Phase 4 is the only phase that writes files.

The four-phase split is mental scaffolding, not a contract with the user.
The agent must treat the phases as cumulative — the package emitted in Phase
4 must reflect the conclusions, reasoning chains, weak points, and
highlights surfaced in Phases 1–3 as a single coherent body of work, not as
independent passes.

## Suitability Gate

Before Phase 1 begins, decide whether the paper is amenable to formalization.
Skip with a short note if:

- The paper is a review, survey, or perspective without original results.
- The paper has no identifiable structured contributions (no derivations, no
  measurements, no method introductions).
- The paper text is corrupted, truncated, or contains only abstract/metadata.

In any of these cases, do not emit a Gaia package. Write a single
`<package_name>.skip.md` next to the input that records the reason in one
paragraph. Do not invent contributions to fill the gap.

## Non-Negotiable Invariants

- **Self-contained `claim(...)` text.** The string body of every `claim(...)`
  must read as a first-class scientific proposition independent of the paper.
  This is the same rule the legacy step 4 prompt enforced — here it is
  enforced at the moment the claim is written, not as a post-hoc rewrite.
  Setup, symbols, regimes, and inlined figure/table content live inside the
  claim string itself; structural pointers ("Eq. (3)", "Fig. 4",
  "Section II") are forbidden inside the claim body.
- **Paper text is the only source of truth.** Do not introduce external
  knowledge, repair missing arguments, or upgrade speculative claims. If a
  symbol is undefined in the paper, leave it undefined and surface the gap
  in the hand-off report. (Phase 1b LKM cross-grounding is the one
  exception — it queries LKM purely to *audit* what the paper said, never
  to augment paper content.)
- **Two claim kinds only.** A `claim(...)` is either a step-1 root
  conclusion or a step-3 weak point used as a leaf premise (the leaf gets
  a paired `register_prior(...)`). A reasoning step is not a claim; it is
  text that lives inside a `derive(...)` `rationale=` field.
- **One epistemic question per conclusion.** Each conclusion `claim(...)`
  body answers exactly one citable question — "what is the new bound /
  relation / procedure / value / agreement?" — not several. A paragraph
  that bundles a procedure, the value it produced, and the benchmark it
  passed is three conclusions, not one. See
  `phase-1-extract-conclusions.md` for the split test and common
  under-splitting traps.
- **One deduction per derived conclusion.** Each conclusion that has at
  least one upstream conclusion or one weak point becomes the conclusion
  of exactly one
  `derive(conclusion, given=[premises], rationale=..., label=...)`.
  Premises are the union of the conclusion's upstream conclusions (from
  the cross-conclusion logic graph) and its weak-point claims. The
  engine `derive(...)` signature accepts only
  `{given, background, rationale, label}` — no `metadata=` kwarg, so
  warrant-strength intent lives in `--rationale` prose.
- **Highlights are working-notes only.** Step-3 highlights characterize
  *why* a conclusion is unusually solid, but they do not enter the
  executable DSL — Gaia's BP semantics already handle credit through
  priors and the `derive(...)` warrant. Highlights inform the qualitative
  warrant-strength prose Phase 4 writes into each deduction's
  `--rationale`.
- **Probability calibration via `register_prior(...)`.** Leaf-claim priors
  come from step-3 calibrations (`prior_probability` for the weak point,
  capped at 0.9). Each justification ends with `TODO:review`. Do not
  invent priors that contradict the reviewer's calibration in working
  notes.

## Responsibility Boundaries

- This skill owns the four analytical passes (plus the Phase 1b LKM
  reverse-trace audit) and the Gaia package emission.
- It does not own package-shape — that is the canonical Gaia spec (see
  `docs/for-users/`). This skill consumes those rules where they apply and
  adds paper-decomposition workflow on top.
- It does not run `gaia build compile` / `gaia run infer` itself; the caller runs
  those quality gates after emission. Surfaced compile errors come back as
  Phase 4 follow-up obligations, not as a built-in step.
- It does not orchestrate the existing `paper-extract` Python pipeline.
  The Python pipeline is a parallel route from paper to XML; this skill
  is the direct route from paper to Gaia.
- It does not own the LKM API surface — Phase 1b shells out to the
  `gaia search lkm` CLI (`knowledge` / `reasoning --claim-id`). Flags, auth,
  and known quirks live behind `gaia search lkm <verb> --help`.
- Multi-paper merges, cross-paper contradictions, and downstream rendering
  are separate concerns handled by other tools.

## Reference Files

### Local (this skill)

- [`references/phase-1-extract-conclusions.md`](references/phase-1-extract-conclusions.md)
  — conclusions, motivation, open questions, cross-conclusion logic graph.
- [`references/phase-2-build-reasoning-chain.md`](references/phase-2-build-reasoning-chain.md)
  — per-conclusion reasoning reconstruction.
- [`references/phase-3-review-weak-points.md`](references/phase-3-review-weak-points.md)
  — weak-point and highlight audit, probability calibration, and the
  Phase 1b LKM reverse-provenance trace.
- [`references/phase-4-emit-package.md`](references/phase-4-emit-package.md)
  — composing Phase 1–3 working notes into Gaia DSL package files.

### Gaia knowledge-package contract (this repo's docs)

- `docs/for-users/quick-start.md` — end-to-end Gaia knowledge-package
  workflow, including single-paper package layout and file templates.
- `docs/for-users/language-reference.md` — `claim` / `derive` /
  `question` emission rules, generic `lkm_id` / `provenance_source`
  metadata semantics, deduction warrant calibration, label rules, and
  `references.json` (CSL-JSON) conventions.
- `docs/for-users/cli-commands.md` — full CLI reference (`gaia build compile`
  / `build check` / `run infer` / `run render`).
- `docs/for-users/hole-bridge-tutorial.md` — prior calibration tutorial.

For runtime help, prefer `gaia <group> <cmd> --help`.

Sibling skills (this registry):

- LKM search is the native `gaia search lkm` CLI (`knowledge` /
  `reasoning [--claim-id]` / `nodes` / `package` / `auth`), used by the
  Phase 1b reverse-provenance trace. Verify flags with
  `gaia search lkm <verb> --help`.
- The **`gaia-explore`** orchestrator client (run `gaia-explore turn <pkg>`; a
  sibling of `gaia`, not a registered skill) — the LKM-driven exploration turn
  loop producing the same Gaia knowledge-package output shape from a different
  upstream.
