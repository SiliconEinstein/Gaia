# Pass 4 — Refine strategy types

Load this file after Pass 3 is complete and its compile + check loop passes.
When this pass is done, run the inner loop again and load
`pass-5-structural-integrity.md`.

Passes 2-3 produce a graph dominated by `infer` (the general fall-back). Pass 4 tightens each relation into the most specific verb that still fits the source.

### Author-verb reference

| Verb | Semantics | When to use | Author-side cost |
|----------|-----------|-------------|--------------|
| `derive` | Directed implication: premises jointly support conclusion | Step-by-step derivations, theoretical results read off a formal framework, computation-application chains | Detailed `rationale`; review / gate checks judge relation quality |
| `infer` | Bayesian update: explicit P(E\|H), optional P(E\|~H) | Theory-vs-experiment fit, single-evidence updates to a hypothesis | `--p-e-given-h` (required), `--p-e-given-not-h` (defaults 0.5) |
| `compute` | Deterministic mapping: callable `fn` produces conclusion from premises | Closed-form computations where the function is in code | `--fn` identifier of a callable; conclusion is the function's output Claim |
| `observe` | Measurement event tying Claim / Variable / Distribution to data | Experimental observations that anchor the graph | `--value` / `--error` for quantity form, or discrete observation against a premise list |
| `composition` | Reusable multi-step pattern: `@composition`-decorated function | Recurring derivation patterns that need a named, registered shape | Author the `pattern.py` and register via `gaia author composition --from-file` |
| `decompose` | Structural split: composite → atomic parts via `and`/`or`/`atom` | Aggregate claim is best read as the conjunction of independently judgeable parts | `--formula-template` or `--formula-expr` |

Also available as **structural verbs** (modelled in Pass 2 alongside the rest, not in Pass 4):

| Verb | Semantics | When to use |
|----------|-----------|-------------|
| `contradict(a, b)` | NOT (A AND B) — cannot both be true | Incompatible hypotheses |
| `exclusive(a, b)` | A XOR B — exactly one true | Exhaustive binary choice |
| `equal(a, b)` | A = B — logically equivalent | Two formulations of the same proposition |

### Decision tree

```
For each `infer` relation drafted in Pass 2:

    Is the conclusion a measured datum (or a Variable/Distribution observed at a value)?
        YES → observe
        NO  ↓
    Is the conclusion produced by a closed-form computation in code (named callable f over premises)?
        YES → compute
        NO  ↓
    Does the source present this as a deterministic step-by-step derivation that, given the premises,
    is the intended way to reach the conclusion (with at most residual numerical or approximation uncertainty)?
        YES → derive   (write the residual caveats in `rationale`; do not add a prior to the derived conclusion/helper)
        NO  ↓
    Is this a Bayesian update where the evidence's likelihood under hypothesis and under its negation
    is what carries the inferential weight (e.g. theory predicts X, experiment measured X')?
        YES → infer    (with explicit --p-e-given-h, and --p-e-given-not-h when known)
        NO  ↓
    Is the conclusion best read as the conjunction or disjunction of independently judgeable atomic parts?
        YES → decompose   (--formula-template and|or|atom)
        NO  ↓
    Does the same multi-step pattern recur across multiple conclusions, and is naming intermediate
    propositions worthwhile?
        YES → composition (extract into a @composition pattern; per-call the wrapper authors a derive over
                          the composition's intermediate Claims)
        NO  → keep infer (with the most informative likelihood you can justify)
```

### Recasting legacy reasoning patterns

The release/0.4 SKILL talked about several named reasoning patterns. Several have clean v0.5 idioms; some do not. Be honest about the gap.

**Strict mathematical deduction** ("if all premises true, conclusion necessarily true"): use `derive` and make the `rationale` explicit enough for review. `derive` carries the conjunction + directed-implication skeleton. There is no separate "deduction" verb in v0.5.

**Soft / probabilistic support** ("premises usually imply the conclusion, with uncertainty"): prefer `infer` when the source supplies likelihood-style evidence. If the source frames the step as a derivation with residual caveats, use `derive` and spell those caveats out in `rationale`; review / gate checks judge whether the step is acceptable. Do not express reasoning-step uncertainty by adding a prior to the derived conclusion or to a generated helper.

**Theory-experiment comparison ("abduction")**: extract the theoretical prediction and the experimental observation as separate claims (Pass 1), then use `infer(evidence=obs, hypothesis=pred, --p-e-given-h ...)`. When several alternative theories compete, chain `infer` against each candidate hypothesis with its own likelihoods. When the alternatives are mutually exclusive in the paper's framing, add `exclusive(a, b)` for the two-alternative case or `decompose --formula-template or` for three or more (`exclusive` is strictly binary). The abduction *concept* — the prior on the alternative reflects explanatory power for the specific observation, not the alternative's truth in general — survives intact; that deep guide lives in `../../gaia-review/SKILL.md`.

**Repeated-observation generalisation ("induction")**: there is no single v0.5 verb. The recommended idiom is `derive` over a `compose`'d generalisation step. Specifically: author each observation as its own claim, then either (a) for the simple flat case, `derive(law, given=[obs_a, obs_b, obs_c], rationale=...)`, or (b) when the generalisation involves a named pattern, define a `@composition` function that takes the observations and the law and returns the law's `derive` step, and register it via `gaia author composition --from-file`. The underlying judgement — each observation must be **independent**; if dependent, extract the shared dependency as an explicit claim in Pass 5 — still applies.

**Process of elimination, proof by cases, mathematical induction, cross-system analogy, extrapolation beyond measured range:** these patterns **have no single-verb v0.5 form**. The recommended idiom for each:

- *Process of elimination:* `decompose --formula-template or` over the exhaustive option set + `derive(survivor, given=[evidence_eliminating_alt_1, evidence_eliminating_alt_2, ...])`. The disjunctive decomposition guarantees the survivor must be the one true option; the `derive` carries the per-alternative refutation reasoning. (`exclusive(a, b)` is strictly binary — exactly two options — so it only fits the n=2 case; for n≥3 alternatives use `decompose --formula-template or`.)
- *Proof by cases:* one `derive(conclusion, given=[case_k_premise, conclusion_holds_in_case_k])` per case, plus a `decompose --formula-template or` over the case predicates (or `exclusive(a, b)` when there are exactly two cases — `exclusive` is binary only).
- *Mathematical induction:* one `derive` for the base case, one `derive` for the inductive step (`P(n) ⇒ P(n+1)`), and a `derive(for_all_law, given=[base_case, inductive_step])` whose rationale references the inductive schema. **The engine does not enforce the inductive schema** — it treats this as a generic two-premise `derive`. The author must carry the "this is induction over N" framing in the `rationale` text, and the Pass 5 reviewer must verify the base case + step actually warrant the universal. Do not assume the engine guarantees the quantifier reasoning.
- *Analogy* and *extrapolation:* author the structural-similarity / continuity premise as a `claim`, then `derive(target, given=[source, similarity_premise])` or `derive(extrapolated, given=[measured_range_result, continuity_premise])`. The justification quality lives in the leaf-prior calibration for the similarity / continuity premise plus the relation `rationale` and review outcome — see `../../gaia-review/SKILL.md`.

If your source has a derivation that does not map cleanly onto any of these idioms, that is signal: capture the gap in `ANALYSIS.md` under "unmodelled reasoning" so a reviewer can examine it.

### Strategy variable naming

Every relation that produces a Claim or helper **must** be assigned to a named public variable (no `_` prefix). This is required so that the relation appears in `gaia build check --brief` output and can be referenced by downstream verbs.

When using `gaia author <verb>`, set `--dsl-binding-name` (Python LHS) and `--label` (engine `label=` kwarg) together for any relation that needs to be cited downstream. Use descriptive names like `derive_tc_al`, `compose_workflow`, `infer_theory_vs_exp`.

### Claim variable naming

Every Claim **must** be assigned to a named variable (no `_` prefix for claims that need to be visible). Anonymous `claim()` calls or `_`-prefixed claims will not get labels and become invisible in CLI output. The only exception: `__` double-underscore prefix is reserved for compiler-generated helper Claims.

### When to reach for `compose`

`compose` is the v0.5 way to capture **complex reasoning with meaningful intermediate steps**. Two triggers:

1. **3+ premises and no `decompose` fit.** A flat `derive` over 4+ premises suffers the BP multiplicative effect — small uncertainties on each premise compound on the conclusion. If you can name meaningful intermediate propositions (not stubs introduced purely to split the call), refactor into a `@composition` pattern whose intermediate Claims are independently judgeable.
2. **Recurring pattern.** The same shape of derivation appears across multiple conclusions. Register it once via `gaia author composition --from-file` and reuse.

If decomposition would be forced — no meaningful intermediate proposition exists — 3 premises is acceptable to keep as `derive` or `infer`; 4+ premises must decompose, otherwise BP multiplicative effect will severely suppress belief.

### Pass 4 reflection

After refining all relations, verify:

- **Every theory-vs-experiment `infer` has a meaningful alternative?** When the source compares competing hypotheses, did you extract each alternative and either chain `infer` against it or wire `exclusive` across the candidates? Remember: the prior on the alternative reflects its **explanatory power** for the specific observation, not its truth in general — see `../../gaia-review/SKILL.md` for the deep guide.
- **Each repeated-observation `derive` over independent observations?** For `derive(law, given=[obs_a, obs_b, ...])`, each observation should provide independent evidence. If observations are dependent (shared sample, shared instrument), extract the shared dependency as an explicit claim in Pass 5.
- **`infer` likelihoods anchored?** Every `infer` call has `--p-e-given-h` from the source. If `--p-e-given-not-h` is left at 0.5, it is a fall-back — when the source's framing supplies a competing-explanation likelihood, set it explicitly.

### Post-refinement check

After refining all relations, check the **verb distribution**:

- If `derive` accounts for more than 70% of relations, review whether some should be `infer` (theory-vs-experiment fit) or `compose`'d (multi-step generalisation).
- Papers with extensive experimental validation typically have many `infer` calls.
- Discussion / conclusion sections that synthesise multiple results often have a `compose`'d generalisation step.

Also check **reasoning chain depth** (hops from leaf to exported conclusion):

- Maximum recommended depth: **3 hops**.
- If a derived conclusion has belief < 0.4, the chain is likely too deep.
- Fix by flattening: make intermediate claims into leaf premises, or restructure into wider (more premises per relation) rather than deeper (more relations in series).
