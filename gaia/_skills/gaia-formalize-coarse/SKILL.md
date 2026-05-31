---
name: gaia-formalize-coarse
description: |
  Use for a quick, single-paper formalization into a Gaia knowledge package:
  read one academic paper (Markdown preferred; plain-text or other readable
  formats also accepted) and emit a standalone `<name>-gaia/` package. Builds
  the package incrementally: scaffold; write the conclusions (with motivation
  and open questions); organize the cross-conclusion logic graph; then per
  conclusion emit its weak points, highlights, and `derive(...)`; then finalize
  (shared-factor decomposition, leaf priors, mark `__all__` with conclusions
  only, references, compile). Gated by an
  upfront suitability check (skip review/survey/perspective papers and
  corrupted paper text). Surfaces 9 argument-pattern weak-point types
  (`measurement`, `causal`, `model`, `statistical`, `generalization`,
  `comparative`, `formal`, `computational`, `external`).
  This is the **Paper → package** entry point when speed matters — the quick
  single-pass sibling of `gaia-formalize-fine` (the thorough
  six-pass treatment). Reach for `gaia-formalize-coarse` for a fast first cut
  of one paper; reach for `gaia-formalize-fine` when the source is
  load-bearing, multi-section, or destined for publication. Use whenever the
  user asks to "formalize a
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

The canonical DSL surface is whatever `gaia sdk` emits — run it to drop a
self-contained SDK reference + one-page cheat sheet into `./gaia-sdk/`; that is
the version-matched, runtime-accessible source of truth for every verb, term,
and distribution. Package layout comes from `gaia pkg scaffold`. This skill
defines the paper-driven workflow that produces packages conforming to that
surface; it does not restate the DSL spec. (The fuller human docs live under
`docs/for-users/` when running inside the repo, but the skill relies on
`gaia sdk`, not those paths.)

```
paper.{md,txt,...}
  |
  v
gaia-formalize-coarse
  (standalone Gaia package source for that paper)
```

`gaia-formalize-coarse` is the **quick paper-driven** sibling of
[`../gaia-formalize-fine/SKILL.md`](../gaia-formalize-fine/SKILL.md) — the
thorough six-pass treatment of the same paper-driven route. Both start from one
paper and audit its derivations into a package of identical shape; coarse is the
fast single-pass cut, fine the exhaustive six-pass one.

## Output Mode

This skill operates in **single-paper batch mode** only:

- Input: one paper text file (`.md` preferred; plain-text and other readable
  formats also accepted) plus a desired package name (or one inferred from
  the paper's first author + year).
- Output: a fresh standalone `<name>-gaia/` package directory.

Refresh / multi-paper batches are out of scope; if the user wants to merge a
paper into an existing multi-paper package, the workflow is to produce the
single-paper package here and then hand it off to a downstream merge step.

## Workflow

The package is built **incrementally** — scaffold first, then write the DSL into
each module as it is organized — not analyzed in full and dumped at the end.
Create a session todo list with the six steps below and work them in order.

1. **Suitability gate** (below) — decide whether the paper is formalizable; skip
   with a `.skip.md` note if not.
2. **Scaffold the package.** Read the DSL surface (`gaia sdk`), then
   `gaia pkg scaffold` and add one module per source section. See
   [`references/phase-4-emit-package.md`](references/phase-4-emit-package.md).
3. **Write the conclusions.** Walk the paper section by section. For each
   section, emit its conclusions as `claim(...)` into the section's module.
   Into the introduction module (`motivation.py`), emit the whole-paper
   motivation as a single `note(...)` (framing prose, no truth value) **and**
   the paper's overall open problem as a single `question(...)` (the
   research question the paper as a whole sets out to answer). Methodology:
   [`references/phase-1-extract-conclusions.md`](references/phase-1-extract-conclusions.md).
   (At this point `motivation.py` holds the motivation note + the open-problem
   question; section modules hold conclusion claims only — no derives, no leaf
   premises.)
4. **Organize the logic graph.** With every conclusion now written, lay out the
   directed dependencies among them (`A → B` = the paper uses A to derive B).
   Same methodology file as step 3.
5. **Per conclusion, in topological order: derive + weak points + highlights.**
   For each conclusion, work in this conceptual order:
   1. **Atomicity re-check before the derive.** Building the evidence chain
      often exposes a still-bundled conclusion — most commonly a theoretical
      prediction fused with its experimental measurement, or a method fused
      with the value it produced. If so, split it into atomic claims **now**
      per `_shared/formalize-atomicity.md` ("Separate theory from experiment",
      "Separate method from result"): replace the bundled claim in the module
      with the atomic ones, update the logic graph, and proceed with each atomic
      conclusion separately in step 5.
   2. Summarize the paper's reasoning chain **for this (now-atomic)
      conclusion specifically** — the chain's content matches the conclusion's
      nature: a theoretical conclusion gets its mathematical / logical
      derivation; an experimental measurement gets the experimental procedure
      (setup, instrument, sampling, how the value was read out); a computational
      result gets the method + parameters + numerical run. After an atomicity
      split, the theory atom and the experiment atom each get their own chain;
      do not collapse them. This prose becomes that conclusion's `derive(...)`
      `rationale=`.
   3. From the reasoning, identify the upstream conclusions it depends on
      (from the step-4 logic graph) — these go in `given=` first.
   4. Surface its weak points and highlights as the **residual** load-bearing
      factors — the uncertainties and strengths in the reasoning that the
      upstream conclusions do **not** already capture. (If a factor is already
      represented by an upstream conclusion, do not duplicate it as a leaf
      premise here.) These go in `given=` after the upstream conclusions.
   5. Emit the leaf-premise `claim(...)`s and the `derive(...)` into the
      conclusion's module; compile-check before moving on.

   Methodology:
   [`references/phase-2-build-reasoning-chain.md`](references/phase-2-build-reasoning-chain.md)
   (reasoning chains / derive) and
   [`references/phase-3-review-weak-points.md`](references/phase-3-review-weak-points.md)
   (weak points, highlights, prior calibration).
6. **Finalize.** Run the global independence (Pattern 3) scan over all leaf
   premises and `decompose` shared causes; write `priors.py` (a
   `register_prior` per leaf premise); mark the public surface in the root
   `__init__.py`'s `__all__` (conclusions + motivation note + open-problem
   question only — no leaf premises); write `references.json`; run the full
   `gaia build compile` and the self-check. See phase-3 (independence) and
   phase-4 (priors, `__all__`, references, compile, self-check).

Load each methodology file as you reach the step that needs it; you may load
several at once (steps 3–6 draw on all four). The step split is scaffolding for
sequencing the build, not independent passes — the finished package must be one
coherent body of work.

## Suitability Gate

Before scaffolding (step 1), decide whether the paper is amenable to
formalization. Skip with a short note if:

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
  in the hand-off report.
- **Two claim kinds only.** A `claim(...)` is either a step-1 root
  conclusion or a step-3 leaf premise (a weak point or a highlight) used in a
  conclusion's `given=[...]` with a paired `register_prior(...)`. A reasoning
  step is not a claim; it is text that lives inside a `derive(...)`
  `rationale=` field. *Exception — Pattern 3:* when step-3 finds leaf premises
  that share a latent cause, each is `decompose`d into a shared-cause claim
  plus a residual claim; those parts are the prior-bearing leaf premises and
  the original is kept as the composed whole (see the "Shared-factor
  evidence" guidance in phase-3, run at the finalize step).
- **One epistemic question per conclusion.** Each conclusion `claim(...)`
  body answers exactly one citable question — "what is the new bound /
  relation / procedure / value / agreement?" — not several. A paragraph
  that bundles a procedure, the value it produced, and the benchmark it
  passed is three conclusions, not one. See
  `phase-1-extract-conclusions.md` for the split test and common
  under-splitting traps.
- **One deduction per conclusion; no isolated conclusions.** Every
  conclusion is the conclusion of exactly one
  `derive(conclusion, given=[premises], rationale=..., label=...)`. There is
  no such thing as an isolated conclusion — a conclusion always rests on
  something. The `given` is built in order: first the conclusion's upstream
  conclusions (every conclusion it depends on per the cross-conclusion logic
  graph must appear), then its leaf premises (weak points and highlights). A root
  conclusion with no upstream still has ≥1 leaf premise carrying its support.
  The engine `derive(...)` signature accepts only
  `{given, background, rationale, label}` — no `metadata=` kwarg, so
  warrant-strength intent lives in `rationale=` prose.
- **Weak points and highlights are the same kind of leaf premise.** Both are
  non-trivial propositions the conclusion's derivation rests on, emitted as a
  `claim(...)` in the conclusion's `given=[...]` with a paired
  `register_prior(...)`. They are not distinguished mechanically — the only
  difference is the prior magnitude (a weak point is a premise the reviewer is
  less sure of, lower prior; a highlight is one the reviewer is very sure of,
  higher prior) plus a `weak_point` / `highlight` tag. A highlight is extracted
  because it is non-trivial and worth making explicit and reviewable, not to
  raise the conclusion's belief; as a high-prior premise it is near-inert in BP,
  which is fine. Neither is working-notes-only.
- **Only leaf premises carry priors.** A `register_prior(...)` is emitted for
  every leaf premise (weak point and highlight alike) and for nothing else.
  Conclusions never get a direct prior — their belief propagates through their
  `derive(...)` from the premises. (Since there are no isolated conclusions,
  there is no leaf conclusion to prior.) **Let the reviewer judge each prior on
  its merits — there is no fixed range or cap.** A weak point is not forced
  below any threshold; a highlight is not forced above one. The only bounds are
  BP validity (strictly between 0 and 1; use ~0.001 and ~0.999 as the practical
  extremes). Each justification ends with `TODO:review`.
- **Conclusions are exported; leaf premises are not.** The package's external
  interface — what other knowledge packages may reference — is its
  **conclusions** (every `claim(...)` written in step 3) plus the motivation
  `note(...)` and the open-problem `question(...)` in `motivation.py`. Weak
  points and highlights are audit-internal commentary; decompose parts (shared
  cause + residuals from Pattern 3) are likewise internal. Concretely: in the
  root `src/<import_name>/__init__.py`, replace the scaffolded
  `__all__: list[str] = []` with the conclusion / note / question labels;
  leave the `_wp_` and `_hl_` leaf-premise labels out. (The default
  `__all__ = []` is treated as "export every labeled claim" by the engine,
  including leaf premises — which is wrong for a finished package.) The
  package's section modules (`s2_methods.py`, etc.) keep their own scaffolded
  `__all__: list[str] = []` — only the root list drives the IR `exported` flag.

## Responsibility Boundaries

- This skill owns the paper-driven analytical workflow and the Gaia package emission.
- It does not own package-shape — that is the canonical DSL surface (`gaia sdk`)
  plus the `gaia pkg scaffold` layout. This skill consumes those where they
  apply and adds paper-decomposition workflow on top.
- The finalize step runs `gaia build compile` itself to validate the
  directly-written modules and iterates until it compiles clean. It does not run
  `gaia run infer` / `gaia inquiry review` — those downstream quality gates are
  caller obligations surfaced in the hand-off report.
- It does not orchestrate the existing `paper-extract` Python pipeline.
  The Python pipeline is a parallel route from paper to XML; this skill
  is the direct route from paper to Gaia.
- It does not query LKM. Formalization is a paper → package transformation;
  consuming the knowledge graph is a separate, LKM-driven concern handled
  elsewhere.
- Multi-paper merges, cross-paper contradictions, and downstream rendering
  are separate concerns handled by other tools.

## Reference Files

### Local (this skill)

- [`references/phase-1-extract-conclusions.md`](references/phase-1-extract-conclusions.md)
  — conclusions, motivation, open questions, cross-conclusion logic graph.
- [`references/phase-2-build-reasoning-chain.md`](references/phase-2-build-reasoning-chain.md)
  — per-conclusion reasoning reconstruction.
- [`references/phase-3-review-weak-points.md`](references/phase-3-review-weak-points.md)
  — weak-point and highlight audit (both as leaf premises) and probability
  calibration.
- [`references/phase-4-emit-package.md`](references/phase-4-emit-package.md)
  — emission mechanics: scaffold, write conclusions, per-conclusion derive +
  leaf premises, finalize (decompose, priors, `__all__`, references, compile).

### Shared formalization methodology (`../_shared/`)

Extraction, atomicity, reasoning-chain, and independence methodology shared
with `gaia-formalize-fine`; workflow steps 3–6 load these from `_shared/`:

- [`../_shared/formalize-extract-conclusions.md`](../_shared/formalize-extract-conclusions.md)
  — what counts as a conclusion, fidelity, self-contained bodies, figures as
  prose, `refs` whitelist, citation form.
- [`../_shared/formalize-atomicity.md`](../_shared/formalize-atomicity.md)
  — one-question-per-claim, under-splitting traps, the two tests.
- [`../_shared/formalize-reasoning-chains.md`](../_shared/formalize-reasoning-chains.md)
  — logic graph, topological order, reasoning-trace reconstruction, step
  rules.
- [`../_shared/formalize-independence.md`](../_shared/formalize-independence.md)
  — the no-double-counting check on each conclusion's premise set.

### Gaia DSL surface and CLI (runtime-accessible)

- **`gaia sdk`** — the canonical DSL surface: writes a self-contained SDK
  reference + one-page cheat sheet (every `claim` / `derive` / `decompose` /
  `question` rule, terms, distributions, relations, label and citation
  conventions) into `./gaia-sdk/`. **Read this before emitting; it is the
  source of truth, not the docs tree.**
- **`gaia pkg scaffold`** / **`gaia pkg add-module`** — package layout and
  module files (run them; they create the structure).
- **`gaia <group> <cmd> --help`** — per-command CLI reference
  (`gaia build compile` / `build check` / `run infer` / `inquiry review`).

The fuller human docs (`docs/for-users/quick-start.md`,
`language-reference.md`, `cli-commands.md`, `hole-bridge-tutorial.md`) exist
for deeper reference when running inside the repo, but the skill relies on
`gaia sdk` + `--help`, which match the installed version.
