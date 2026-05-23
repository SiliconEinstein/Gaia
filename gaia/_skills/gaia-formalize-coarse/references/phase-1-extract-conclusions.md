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

### What is a conclusion

A conclusion is **new author-asserted knowledge** that would not exist if this
paper had not been written:

- a newly derived formula, theoretical relation, or analytical result;
- a quantitatively new numerical or experimental value, scaling law, phase
  boundary, or benchmark;
- a newly proposed algorithm, computational scheme, or experimental method.

It is **not**:

- a restatement of prior work;
- a trivial corollary of the paper's own assumptions;
- a rhetorical claim of importance, motivation, or future work;
- a reformulation that adds no information.

### Atomicity

Each conclusion must answer **exactly one** citable epistemic question
about the paper — one new bound, one new relation, one new procedure, one
new measured value, one new comparison outcome, one new causal attribution,
one new generalization result, etc. If a candidate body answers two,
split it into two conclusions.

This rule is **field-agnostic**: the same one-question-per-conclusion
discipline applies whether the paper is a theorem in pure math, a
clinical-trial endpoint in medicine, a benchmark result in ML, a causal
estimate in social science, or a measurement in experimental physics.

Do **not** pre-classify a conclusion by "type" (analytical / empirical /
methodological / etc.) here, and do **not** pre-assign it a Phase 3
`weak_types` pattern. The nine `weak_types` keys describe *threats to a
conclusion's derivation*, not *what kind of conclusion it is*; a single
conclusion typically rests on several patterns simultaneously, and the
pattern assignment happens per weak point in Phase 3, not per conclusion
here. Phase 1's only job for atomicity is to enforce the
one-question-per-conclusion split.

**Common under-splitting traps to avoid:**

Each trap is illustrated with examples from different fields to make
clear that the trap is structural, not domain-specific.

- **Definition + headline result.** A new bound (e.g., "the scheme is
  parametrically valid when $\omega_D \ll E_F$, $\omega_c^2 \ll \omega_p^2$,
  $T \ll \omega_c$") and the downstream result that uses it are *two*
  conclusions, not one — the bound is a citable regime claim on its own.
  Outside physics, the same trap appears in a clinical RCT that introduces
  a new operational criterion alongside its prevalence: "the protocol's
  prespecified no-disease-activity criterion at week 24 (combining OCT
  central-subfield thickness, BCVA, hemorrhage status, and investigator
  judgment) is met by 65% of treated participants" is two conclusions —
  the criterion is a methodological contribution citable by anyone
  designing a similar extended-dosing regimen, separate from the
  empirical prevalence it yielded in this particular cohort.
- **Procedure + the value it produced.** "Cluster-DiagMC achieves
  γ~$10^5$ at $n=6$ and reproduces $P(0,0)=0.0504(3)$" is two
  conclusions: the algorithm's measured speedup, and the agreement with
  the polarization baseline. Each has different evidence and different
  weak points. Outside physics, the same trap appears in a clinical RCT
  conclusion that bundles regimen with outcome: "faricimab dosed every
  16 weeks after a four-monthly loading phase produces +11.4 ETDRS
  letters at week 52 with a mean of 6.2 injections" is two — the dosing
  regimen is a methodological contribution that downstream trials could
  reuse for a different outcome, and the measured BCVA change is an
  empirical efficacy result that a different regimen could equally have
  produced.
- **Theorem + worked example.** A general formal claim and the explicit
  worked-example calculation that motivates it (e.g., "the third-order
  four-diagram cancellation drops by $\sim 3.48 \times 10^{-3}$") are two
  conclusions when the worked example is a separate quantitative finding.
  Outside physics, the same trap appears in causal-inference methodology
  papers that bundle theory with demonstration: a new identifiability
  theorem for an estimand under stated assumptions, and a worked example
  applying the resulting estimator to a specific competing-events dataset
  to produce a numerical estimate, are two conclusions — the theorem is
  a formal contribution citable by anyone working with that estimand
  class, and the worked example is an empirical instantiation citable
  only by people analyzing that specific data.
- **Mechanism + benchmark.** "The downfolded Migdal–Eliashberg equation
  reproduces the toy-model $T_c$ to within $0.2\%$" — the mechanism (the
  equation) is one conclusion (analytical); the benchmark agreement is
  another (comparative). Outside physics, the same trap appears in
  algorithmic system papers that bundle a method with its benchmark:
  "DVL pre-integration is linearized in the rotation update, avoiding
  full re-integration inside the nonlinear solver, and AQUA-SLAM
  achieves lower translation RMSE than five baselines on the WaveTank
  dataset" is two — the linearization mechanism is a methodological
  contribution that downstream SLAM systems could adopt with a different
  baseline set, and the WaveTank RMSE comparison is an empirical
  benchmark result that could come from a different underlying
  algorithmic choice.

**Split test.** After writing a candidate body, ask: *if I deleted any one
clause, would I lose an answer to a distinct citable question?* If yes,
split that clause off. If the body merely loses an aside that does not
answer its own citable question, it is one conclusion.

**Standalone-citation test.** Would each candidate stand on its own as a
sentence the paper could have published as a stand-alone bullet in the
abstract? If yes, it is an atomic conclusion. If two candidates can only
be cited together (because one is an aside of the other), they are one.

### Self-containment as you write

Every conclusion's working-note text must already meet the
self-containment criterion that Phase 4 will demand:

- All symbols and acronyms defined in-text on first use.
- The system / model / dataset / regime described inside the proposition.
- Inline numerical values, equation forms, or experimental setups instead of
  pointers like "Eq. (3)" or "Fig. 4".
- Concrete subject in every sentence (the model, the estimator, the
  measurement) — not "the paper" or "this work".

This is the rule the legacy step-4 prompt enforced; here it is enforced at
the moment the conclusion is written, not as a post-hoc rewrite.

### Fidelity

- Do not strengthen heuristic claims into established facts.
- Do not supply missing derivations.
- Do not import outside knowledge.
- Preserve the authors' epistemic hedging exactly (regimes, error bars,
  speculative qualifiers).

### Evidence localization

For each conclusion, note the figures / tables / equations / external
citations that primarily evidence it. These notes become the `refs`
metadata on the `claim(...)` in Phase 4 (the `refs` metadata field is
documented in `docs/for-users/language-reference.md`).

Allowed pointer kinds — these are the **only three** that may end up in
`refs`:

- **`figure`** — a figure or table in the paper (e.g. `Fig. 2`, `Table I`).
- **`equation`** — an equation referenced by number (e.g. `Eq. (5)`).
- **`citation`** — an external bibliographic reference. Convert numeric
  citations from the paper (e.g. `[33]`, `Ref. 5`) to a key matching the
  paper's first-author surname plus year (e.g. `Smith2020`); the same key
  goes into `references.json` in Phase 4.

Section, appendix, paragraph, theorem, lemma, and footnote pointers are
**not** legitimate `refs` entries and must not be retained. If a conclusion
is rooted in "Section IV" of the paper, the relevant content has to be
inlined into the conclusion's body itself; do not preserve the section
pointer.

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

For each ordered pair `(A, B)` of conclusions, decide whether the paper's
own argumentation **uses** A in deriving B. Add an edge `A → B` if and only if:

- The reasoning that establishes B explicitly or implicitly relies on A's
  result as a premise or intermediate step, **and**
- The reliance is traceable to the paper text, not to your own reasoning
  about the subject matter.

Rules:

- The graph must be acyclic.
- Independent conclusions have no edges; that is expected.
- Edges must be **direct**: if A → B and B → C, do not also add A → C unless
  the paper uses A directly in deriving C without going through B.
- Topical similarity ≠ derivation dependency.
- Two conclusions appearing in the same downstream application ≠ derivation
  dependency.

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
- Every retained conclusion passes atomicity, fidelity, and self-containment
  checks.
- The logic graph is acyclic and minimal.
- Motivation and open-question paragraphs are present (or recorded as
  "no motivation block" / "no open questions" if genuinely absent).
- The next todo is marked in progress before loading
  `phase-2-build-reasoning-chain.md`.
