# Trace: Gaia

### EARS — Progress (2026-04-20 14:50)
<!-- concepts: compile-time-formalization, support-strategy, hypothesis-testing -->
Found that `support` and `compare` were missing from `_COMPILE_TIME_FORMAL_STRATEGIES` in `compile.py`. Without compile-time formalization, these strategies stay as bare `Strategy` in IR and get lowered as ternary IMPLICATION factors (instead of binary SOFT_ENTAILMENT CPT). The ternary helper claim blocks backward message propagation, preventing hypothesis differentiation in abduction structures. Adding `support` and `compare` to the set fixes lowering → hypothesis_mutation goes from 0.33 to 0.47 in the luria-delbruck package.

### EARS — Progress (2026-04-20 19:15)
<!-- concepts: gaia-lang-v6, likelihood-library, reference-semantics -->
Integrating GPT Pro's v6 IR and Lang design specs into the repo (PR #450). Key design decisions made in this session:

1. **Knowledge object references in parameterized Claims**: Decided that Knowledge-typed parameters (Setting, Claim) use `[@param_name]` reference syntax in docstring templates, while value-typed parameters (int, float, str) use `{param_name}` format substitution. Two syntaxes coexist — compiler resolves `[@...]` first, then applies `str.format()`.

2. **Standard likelihood library**: Instead of requiring users to manually declare 5+ assumption Claims for every AB test, provide `ab_test(counts, target)` one-line helpers that auto-generate standard assumptions (RandomAssignment, ConsistentLogging, NoEarlyStopping) as parameterized Claims referencing the experiment Setting. Users can override via manual `likelihood_from()`.

3. **No `Ref[T]` wrapper**: Considered `Ref[T]` generic type vs direct object passing vs string labels. Chose direct object passing (`experiment: Setting`) — simplest, type-safe, consistent with existing Strategy API where premises are passed as objects.

### EARS — Session Start (2026-05-04 10:35)
<!-- concepts: gaia-lang-v6, infer-strategy, likelihood-gating -->
- Task: Review PR 504 — "Gate infer likelihoods with given claims"
- Why: User wants code review on the infer() gating mechanism before merge

### EARS — Commit Digest (2026-05-04 10:40)
<!-- concepts: gaia-lang-v6, infer-strategy, code-review -->
Reviewed PR 504 implementing `given` gating for `infer()`. Implementation is correct:
- API: `infer()` returns evidence claim, helper stays internal as warrant, `p_e_given_not_h` defaults to 0.5
- CPT construction: binary for no gates, switch CPT with neutral 0.5 baseline when gate is false
- BP semantics verified via lowering tests: gate unlikely → neutral, gate likely → activates CPT, evidence observed → gate belief increases
- Review integration: gate claims appear in audit questions
- All tests pass (78 tests), CI green, docs complete
Left review comment on PR (can't approve own PR).

### EARS — Progress (2026-05-05 01:03)
<!-- concepts: causal-reasoning, do-calculus, kernel-vs-adapter -->
Designed v0.6 causal reasoning spec on top of PR #505's `Causes(X, Y)` marker. Decisions: (1) α architecture — `gaia.causal` kernel module with networkx as kernel dep; y0 stays `gaia[causal-do]` extra because its base install pulls pandas/sklearn/statsmodels (3 heavyweights we don't use). (2) Pgmpy avoided entirely — `do(X=x).query(Y)` numeric answers go through a `mutilate(fg, intervened)` helper (~15 lines) on Gaia's existing FactorGraph, then standard BP/JT engine. Pearl truncated factorization maps cleanly because each `P(v|pa(v))` is exactly one factor with `conclusion=v`. (3) Counterfactuals (level 3) deferred to v0.7+ — they need exogenous noise + parameterized structural equations, which is a Gaia world-view surgery, not just adapters. (4) Variable nodes need synthetic IDs because PR #505 §2.4 says Variables don't get IR Knowledge / QIDs — chose `@var:{namespace}:{package}:{symbol}` with `@` prefix so `is_qid()` returns False, no consumer confuses CNID vs QID. Spec at docs/specs/2026-05-05-causal-reasoning-design.md.

### EARS — Progress (2026-05-05 14:33)
<!-- concepts: causal-reasoning, predicate-vs-propositional, modality-aware-mutilation -->
Patching causal spec on docs/causal-design-revisions branch. Two big design decisions baked in this round: (1) **modality-aware mutilation** — `do()` only severs causal factors; deduction-derived factors and EQUIVALENCE/CONJUNCTION/DISJUNCTION operator factors are preserved. Justified by 8 thought experiments showing this is forced by the meaning of `do()` (interventions act on the world, not on logical statements). The earlier "definitional flag" escape hatch is dropped — redundant under first principles. (2) **per-instance grounding** for `forall(p, Causes(X(p), Y(p)))` — strict dual to v0.5's existing logical-quantifier grounding (`gaia/lang/compiler/lower_formula.py:107-192`). Follow-up review tightened the runtime contract to provenance-tagged causal `CONDITIONAL` CPT factors, generated CNID variables, and the existing `causal()` helper; `causes()` remains the formula helper.

### EARS — Progress (2026-05-05 15:42)
<!-- concepts: causal-reasoning, cpt-contract, cnid-grounding -->
Tightened the PR 521 causal spec after review. The authoring surface now keeps `Causes(...)` as the AST dataclass, keeps `causes(...)` as the formula helper, and extends the existing `causal(...)` helper for CPD-bearing declarations; no public `cause()` helper is introduced. D2's machine contract is now a provenance-tagged causal `CONDITIONAL` CPT factor: noisy-OR is a leak-aware authoring transform, not the stored runtime primitive, and `mutilate()` filters on `factor.metadata["modality"] == "causal"` instead of trying to recover IR claim metadata after lowering. Causal universal grounding now emits per-instance causal Knowledge plus generated CNID variables, not Variable Knowledge nodes.
