# Phase 1 — Extract Conclusions, Motivation, Open Questions, Logic Graph

Load this file when `gaia-formalize-coarse` starts. Do not load later phase
files until this phase is complete.

## Goal

Read the paper end-to-end and identify, in working notes:

1. **Motivation** — the unresolved scientific problem-state that necessitated
   the paper's work (paper-level, single block).
2. **Conclusions** — the genuinely new contributions established by the paper,
   each as an atomic scientific proposition.
3. **Open questions** — scientifically meaningful issues the paper explicitly
   leaves unresolved (paper-level, single block).
4. **Logic graph** — directed dependency edges among conclusions: an edge
   `A → B` means the paper's own reasoning uses A in deriving B.

These four objects are held in working notes only. Phase 4 is the only phase
that writes files.

## Suitability Gate

Before extraction, decide whether the paper is amenable to formalization:

- A review article, survey, or perspective without original results.
- A paper without identifiable structured contributions (no derivations, no
  new measurements, no new methods).
- A corrupted / abstract-only paper text.

If any holds, **stop here**. Do not invent contributions. Record the reason in
working notes; Phase 4 will write a `<package_name>.skip.md` file instead of
the package.

## Extraction Rules

The methodology for identifying conclusions and writing each one is **shared
with `gaia-formalize-fine`** and lives in `_shared/`. Load both files now and
apply them as you extract:

- [`../../_shared/formalize-extract-conclusions.md`](../../_shared/formalize-extract-conclusions.md)
  — what counts as a new conclusion, fidelity to the paper, self-contained
  claim bodies, content format, figures and tables transcribed as prose, the
  no-paper-internal-pointer rule, the `refs` whitelist, and citation form.
- [`../../_shared/formalize-atomicity.md`](../../_shared/formalize-atomicity.md)
  — the one-question-per-claim rule, the theory/experiment and method/result
  corollaries, the under-splitting traps, and the split and
  standalone-citation tests.

Coarse-specific points on top of the shared rules:

- Phase 1 extracts **conclusions only**. Weak points are extracted later, in
  Phase 3, as leaf premises — they are not conclusions and are not subject to
  the "what counts as a conclusion" test here.
- Conclusions live in working notes (schema below), not on disk; Phase 4 is
  the only phase that emits files.
- The figure / equation / citation pointers collected per the shared file's
  `refs` whitelist become the `refs` metadata on each `claim(...)` in Phase 4.

## Motivation Block

Write a single paragraph (3–6 sentences) capturing:

- The physical / scientific context — research area, phenomenon under study,
  broader scientific goal.
- The prior state of knowledge — methods, approximations, or phenomenological
  treatments that existed and their specific shortcomings.
- The scientific consequences of those gaps — what could not be predicted,
  understood, or measured before this paper.

Style: narrative, like an Introduction-section paragraph. Not a checklist of
"lack of X". Do **not** include the paper's solutions — motivation is the
pre-paper state.

## Open Questions Block

Write a single paragraph capturing what the paper itself leaves unresolved:
explicit future work, acknowledged limitations, conjectures, unresolved
regimes. Do not invent new open problems and do not weaken accepted
conclusions into open questions.

## Logic Graph

Build the directed dependency graph among conclusions — an edge `A → B` means
the paper's own reasoning uses A in deriving B — per the "The logic graph"
section of
[`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md).
Phase 2 consumes this graph for topological ordering.

## Working Notes Schema

Hold Phase 1 output in scratch as something like:

```yaml
suitability: ok | skip
skip_reason: <if skipping>

motivation: |
  <single paragraph>

conclusions:
  - id: 1
    title: <≤ 25-word descriptor>
    body: <self-contained scientific proposition>
    citation_keys: ["Smith2020"]
    artifact_anchors:
      - kind: figure
        source: Smith2020
        locator: "Fig. 2"
      - kind: table
        source: Smith2020
        locator: "Table I"
    inline_equations: ["Eq. (5) content must be transcribed into body if load-bearing"]
  - id: 2
    title: ...
    body: ...
    citation_keys: ...
    artifact_anchors: ...

logic_graph:
  - from: 1
    to: 2
  - from: 1
    to: 3

open_questions: |
  <single paragraph>
```

The `id` integers are local to this paper and are referenced by Phases 2 and
3. They will not appear in the emitted Gaia DSL — the final claim labels are
minted in Phase 4 from the paper key plus a semantic suffix.

## Phase-Completion Gate

Before moving to Phase 2:

- Suitability decision is made; if skipping, stop here and note for Phase 4.
- Every retained conclusion passes the atomicity, fidelity, and
  self-containment checks from the `_shared/` files.
- The logic graph is acyclic and minimal.
- Motivation and open-question paragraphs are present (or recorded as
  "no motivation block" / "no open questions" if genuinely absent).
- The next todo is marked in progress before loading
  `phase-2-build-reasoning-chain.md`.
