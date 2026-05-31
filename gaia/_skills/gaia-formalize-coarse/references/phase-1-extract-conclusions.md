# Extract Conclusions, Motivation, Open Questions, Logic Graph

Methodology for **workflow steps 3–4**: writing the conclusions (step 3) and
organizing the logic graph among them (step 4). Conclusions are written
directly as `claim(...)` into their section modules as they are identified — the
DSL package is the only artifact.

## Goal

Read the paper end-to-end and identify:

1. **Motivation** — the unresolved scientific problem-state that necessitated
   the paper's work (paper-level, single block; framing prose with no truth
   value → a `note(...)` in `motivation.py`).
2. **Conclusions** — the genuinely new contributions established by the paper,
   each as an atomic scientific proposition (each → a `claim(...)` in the
   module of the section where it is established).
3. **Open problem** — the paper's overall research question (paper-level,
   single → a `question(...)` in `motivation.py`).
4. **Logic graph** — directed dependency edges among conclusions: an edge
   `A → B` means the paper's own reasoning uses A in deriving B.

Conclusions are emitted directly into their section modules in step 3; the
motivation note and the paper-level open-problem question both go in
`motivation.py`. The logic graph (step 4) is held in context — it drives which
upstream conclusions each `derive(...)` lists in step 5. No intermediate
YAML/JSON artifact.

## Suitability Gate

Before extraction, decide whether the paper is amenable to formalization:

- A review article, survey, or perspective without original results.
- A paper without identifiable structured contributions (no derivations, no
  new measurements, no new methods).
- A corrupted / abstract-only paper text.

If any holds, **stop here**. Do not invent contributions. Write a single
`<package_name>.skip.md` recording the reason, and do not scaffold a package.

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

- Step 3 emits **conclusions only**. Weak points and highlights come later, in
  step 5, as leaf premises — they are not conclusions and are not subject to
  the "what counts as a conclusion" test here.
- Each conclusion is written as a `claim(...)` into the module of the section
  where it is **established** (so dependencies run forward and later modules can
  `import` it). Place a result mentioned early but established later in the
  later section's module.
- The figure / equation / citation pointers collected per the shared file's
  `refs` whitelist become the `refs` metadata on each `claim(...)`.

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

## Open Problem (paper-level, single question)

In Gaia, a `question(...)` records a research question. The coarse skill emits
**one** `question(...)` at the paper level — the paper's overall open problem,
i.e. the research question the paper as a whole sets out to answer. It lives
in `motivation.py` alongside the motivation note. This matches the legacy
paper-extract pipeline B (top-level `<problem>研究问题描述...</problem>`
mapped to `type="question"`).

State the open problem as a concrete research question, not a restatement of
the conclusions in interrogative form and not a generic field-wide question.

Paper-stated "future work" / next-step questions the paper does **not** answer
are not modelled. Leave them out of the package.

## Logic Graph

This is **step 4**, after every conclusion is written. Build the directed
dependency graph among the conclusions — an edge `A → B` means the paper's own
reasoning uses A in deriving B — per the "The logic graph" section of
[`../../_shared/formalize-reasoning-chains.md`](../../_shared/formalize-reasoning-chains.md).
Step 5 consumes this graph: each conclusion's `derive(...)` lists its upstream
conclusions in topological order. The graph is held in context (it maps onto
the `derive` `given=` references — no intermediate artifact).

## Step gate (before step 5)

Before starting the per-conclusion step:

- Suitability decision is made; if skipping, stop and write the `.skip.md`.
- Every conclusion has been written as a `claim(...)` in its section module and
  passes the atomicity, fidelity, and self-containment checks from `_shared/`.
- The logic graph over the written conclusions is acyclic and minimal.
- `motivation.py` contains the motivation `note(...)` and the paper-level
  open-problem `question(...)`.
