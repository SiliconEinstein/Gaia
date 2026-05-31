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
3. **Open questions, one per conclusion** — for each conclusion, the driving
   research question it answers (each → a `question(...)` in the same module
   as its conclusion).
4. **Logic graph** — directed dependency edges among conclusions: an edge
   `A → B` means the paper's own reasoning uses A in deriving B.

Conclusions, the motivation note, and each conclusion's driving question are
emitted directly to the modules in step 3. The logic graph (step 4) is held in
context — it drives which upstream conclusions each `derive(...)` lists in
step 5. No intermediate YAML/JSON artifact.

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

## Open Questions (one per conclusion — the driving question it answers)

In Gaia, an "open question" is a **driving research question** — the question
the paper is trying to answer. It pairs with the conclusion that answers it:
the `question(...)` records the question, the `claim(...)` records the paper's
answer. Per the legacy paper-extract pipeline ("该结论对应的子问题") and fine's
pass-1 ("Driving questions for the source"), this is the canonical model.

For **each conclusion**, identify the question it answers and write it (in
step 3) as a `question(...)` in the same module as the conclusion claim. The
question text states the unresolved problem this conclusion addresses — not
restatements of the conclusion in interrogative form, and not generic field-wide
questions. Atomic conclusion ↔ atomic driving question.

Paper-stated "future work" / "things left for follow-ups" that the paper itself
does **not** answer is not a driving question of any conclusion in this paper.
Leave it out of the package; the skill does not model future-work statements.

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
- The motivation note is emitted in `motivation.py`; every conclusion has its
  driving question (`question(...)`) emitted alongside it in its section module.
