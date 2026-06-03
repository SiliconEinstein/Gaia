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

Before extraction, decide whether the paper is amenable to formalization
(the full statement is in SKILL.md "Suitability Gate"):

- A review article, survey, or perspective without original results.
- A paper without identifiable structured contributions (no derivations, no
  new measurements, no new methods).
- A corrupted / abstract-only paper text.
- A paper whose **core contribution is Bayesian / statistical model
  comparison** — coarse emits only `derive`, so this loses its epistemic
  structure; redirect to `gaia-formalize-fine` rather than coarsening.

For the first three, **stop here** — do not invent contributions; write a single
`<package_name>.skip.md` recording the reason, and do not scaffold a package.
For the fourth, redirect rather than produce a coarsened package.

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

## Mark each main conclusion in the root `__all__`

A package's exported surface is its main conclusions, and the engine reads
the surface from the **root** `src/<import_name>/__init__.py`'s `__all__`
(section modules' own `__all__` are not propagated upward). Because the
conclusion's status as "main conclusion of this paper" is decided exactly
when it is written in step 3, the `__all__` entry is added **here**, not
deferred to finalize.

For each conclusion you emit as `claim(...)` in step 3:

1. Mint its label per the naming rule in `phase-4-emit-package.md`
   ("Claim labels").
2. Write the `claim(...)` into its section module.
3. In the root `src/<import_name>/__init__.py` (which you write — flat layout,
   see phase-4 step 2), add `from .<section> import <label>` and list the label
   in `__all__`. The engine matches `__all__` against registered knowledge by
   label string, but having the name actually importable keeps the Python
   convention honest and lets downstream code
   `from <import_name> import <label>` cleanly.

What does **not** go in `__all__`:

- The motivation `note(...)` and the open-problem `question(...)` in
  `motivation.py` — these are framing / record, not contributions.
- Weak points and highlights (step 5 leaf premises) — these are audit
  material, not contributions.
- Decompose parts (shared cause + residuals from Pattern 3 at finalize) —
  these are internal restructurings of leaf premises.
- `derive(...)` labels and `register_prior(...)` records — these are
  reasoning steps and prior records, not exported surface.

> **Why curated, not permissive.** Downstream tools — `gaia register`'s
> release manifest, `gaia inquiry review`'s dependency walk,
> `_github.py`'s README rendering, `lkm_explorer`, starmap, the
> `gaia-publish` skill — all treat the IR `exported` flag as "this paper's
> headline contributions" and visualise / list them as ★ headline nodes. If
> every BP-participating knowledge ends up in `__all__`, those views fill
> with intermediate derives and audit claims and lose their signal — so list
> only the main conclusions. Root `__all__` is the single source of truth and
> is validated at compile.

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
in `motivation.py` alongside the motivation note.

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

### No relation verbs between conclusions

The derive logic graph is the **only** structure among conclusions. Do **not**
scan for or emit `equal` / `contradict` / `exclusive` / `associate` between
conclusions:

- **`contradict` / `exclusive`** — a paper does not establish two mutually
  incompatible propositions *as its conclusions*. When the contribution itself
  *is* a relationship ("A and B are incompatible", "A is equivalent to B"), that
  relationship is its own `claim(...)`, not a relation verb between two other
  conclusions.
- **`associate`** — between two conclusions it is either redundant with the
  derive graph (double-counting, or a cycle when it runs opposite a derive edge)
  or a coupling too weak to model.
- **`equal`** — two conclusions that are genuinely the same proposition should be
  **merged**, not coupled. The one legitimate conclusion-level `equal` — between
  a theory atom and the experiment atom of the **same quantity** — arises from
  the atomicity split in step 5.1 (see phase-2 / phase-4 step 5), not from a scan
  here. A general theorem versus a *separate* experimental validation has
  different truth conditions and is **not** equal'd: the two stay independent
  conclusions, linked (if at all) only by a derive edge.

If two conclusions are in genuine tension the paper does not resolve, note it as
an **unmodelled tension** in the hand-off — do not force a relation. (Relations
between *premises* are a separate matter — see phase-3 "Relations between
premises".)

## Step gate (before step 5)

Before starting the per-conclusion step:

- Suitability decision is made; if skipping, stop and write the `.skip.md`.
- Every conclusion has been written as a `claim(...)` in its section module and
  passes the atomicity, fidelity, and self-containment checks from `_shared/`.
- The logic graph over the written conclusions is acyclic and minimal.
- No relation verbs were added between conclusions — the derive logic graph is
  the only inter-conclusion structure (a conclusion-level `equal` appears only
  if a same-quantity theory/experiment split in step 5.1 warrants it).
- `motivation.py` contains the motivation `note(...)` and the paper-level
  open-problem `question(...)`.
