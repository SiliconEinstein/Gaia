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

### Relations between conclusions

Not every connection between two conclusions is a derivation. Some pairs are
**logical relations** the paper itself states (or strongly implies): "Model A
and Model B cannot both be right"; "this theoretical prediction and that
experimental value are the same proposition"; "these two outcomes exhaust the
possibilities and the data picks one". Capture these at step 4 alongside the
derivation edges — they sit at the same conclusion-graph layer.

The verbs (canonical surface: `gaia sdk`):

| Verb | Semantics | Use when |
|---|---|---|
| `equal(a, b, rationale=…)` | both must hold the same truth value | A theoretical prediction and the matching experimental observation; word form vs equation form of the same proposition; "Y₁ = Y₂ within stated error bars". After atomicity-splitting a theory+experiment bundle in step 5.1, the resulting atoms typically deserve an `equal(...)` between them. |
| `contradict(a, b, rationale=…)` | NOT (A AND B) — both cannot be true, but both **can** be false | Two competing hypotheses the paper says are incompatible (a third option may still exist). |
| `exclusive(a, b, rationale=…)` | A XOR B — exactly one must be true (exhaustive + mutually exclusive; **strictly binary**) | The paper frames the alternatives as exhaustive — exactly one wins. For ≥3 alternatives use `decompose(formula=lor(...))` (see phase-4 step 6a) instead. |
| `associate(a, b, p_a_given_b=…, p_b_given_a=…, rationale=…)` | symmetric probabilistic association (no logical entailment); pass `pattern="equal"` / `"contradict"` / `"exclusive"` when you mean a soft version of the hard relation | The paper hints at a relation but the strength is judgment-bound — e.g. "results A and B point in the same direction" without a logical equivalence; or competing-models language that does not actually exhaust the space. The two `p_*` conditionals are reviewer-judged honest estimates, not derived from data. |

**Discipline — the three are not interchangeable.** The table lists the verbs;
which one (and whether to use any) is governed by:

- **`equal` (and any near-`equal` soft form) — guard against double counting.**
  `equal(C1, C2)` asserts the two are the *same* truth, so any evidence their
  derivations share would be counted on both ends of the identity. The fix is
  **not** to avoid `equal` when paths share evidence — it is to make the sharing
  explicit first: extract every shared dependency into one node both derivations
  route through (`decompose`, Pattern 3). Once the graph is faithful, exact
  inference discounts the shared part and credits only the independent premises
  as genuine cross-validation (canonical case: a theory atom and the experiment
  atom that measured it). The test is *"are all shared dependencies modelled as
  shared nodes?"*, not *"do they share evidence?"*. If, after extraction,
  nothing independent distinguishes the two, they are one proposition →
  **merge**, do not `equal`.
- **`contradict` / `exclusive` — get the logical relation right.** No
  double-counting concern (these forbid truth combinations, they do not merge
  evidence); the risk is asserting a relation that is not real — a wrong hard
  `contradict` / `exclusive` silently distorts every downstream belief. Use the
  hard verb only when the paper establishes genuine incompatibility
  (`contradict`) or an exhaustive binary (`exclusive`).
- **`associate` is the exception, not the default "softener".** Before reaching
  for it: a *clear* relation the paper states is better **materialized as an
  explicit `claim(...)` + `derive(...)`** (transparent, reviewable) than encoded
  as a soft coupling; a *weak* relation is better left **unmodelled** (note it in
  the hand-off). Reserve `associate(pattern=…)` for the narrow case where you are
  confident an `equal` / `contradict` / `exclusive`-type relation holds but
  **not** that it is a hard logical constraint — and even then it is most
  defensible for `contradict` / `exclusive` (hedging a structural claim you are
  unsure of). Soft `associate(pattern="equal")` between two conclusions is
  discouraged: "softly the same proposition" is usually really a derivation or a
  correlation (model it as such), and at the conclusion layer the soft form
  anchors a missing marginal with an uninformed MaxEnt prior.

**Rationale discipline (all relations).** The `rationale=` must (1) say *why
these two specific relata* stand in this relation in the paper's setting, not
restate the verb; (2) cite the paper-textual evidence with `[@key]` (no
`Eq.` / `Fig.` / `Sec.` pointers); (3) for `associate`, additionally justify
both conditionals. A rationale that reduces to "they look related" is not
reviewable and must be rewritten before emit.

The labelling rule: a relation between conclusions `C_i` and `C_j` lives in
the **module of the later (downstream) conclusion** — so the relation can
`import` both relata. Mint the label as `<key>_rel_<short_suffix>` (e.g.
`liu2015_rel_theory_match`). Relations do **not** carry priors
(hard relations are deterministic; `associate` carries its conditionals
directly), so they get no `register_prior` entry and they are **not** added
to root `__all__`.

What NOT to model:

- "In tension but can both be true" — flag in the hand-off report as an
  unmodelled tension; do not force a `contradict`. A wrong `contradict`
  silently distorts every downstream belief.
- Quantitative-difference observations where the paper doesn't actually
  claim "these are the same proposition" — use a `derive(...)` instead.
- Field-wide rivalries the paper does not itself adjudicate.

## Step gate (before step 5)

Before starting the per-conclusion step:

- Suitability decision is made; if skipping, stop and write the `.skip.md`.
- Every conclusion has been written as a `claim(...)` in its section module and
  passes the atomicity, fidelity, and self-containment checks from `_shared/`.
- The logic graph over the written conclusions is acyclic and minimal.
- Conclusion-level relations (equal / contradict / exclusive / associate) the
  paper states or strongly implies have been identified, located in their
  downstream module, and labelled.
- `motivation.py` contains the motivation `note(...)` and the paper-level
  open-problem `question(...)`.
