# Prior assignment, inference, analysis, and rendering

Load this file after Pass 6 is complete. This is the tail of the workflow:
assign leaf priors, run inference, interpret the results, produce the
`ANALYSIS.md` deliverable, and hand off to rendering.

## Prior-assignment tail

After Pass 6, you have a structurally complete graph and a passing `gaia build check`. Now assign priors and run inference.

### Write `priors.py`

`priors.py` assigns priors to leaf claims. Warrant priors on `derive` (and `infer` / `compute` where relevant) are set by `gaia author register-prior --claim <warrant_label> --value ... --justification ...` against the verb's labelled output Claim (or its auto-generated warrant helper). The engine's verb signatures do not accept an inline `prior=` kwarg — `register_prior` is the only path.

**Before writing `priors.py`, run `gaia build check --hole .`** to see exactly which independent claims need priors, along with their content and current status. Use this as your checklist — address each hole, then re-run `gaia build check --hole .` to confirm "All independent claims have priors assigned."

The CLI shortcut is:

```bash
gaia author register-prior \
    --claim my_leaf_claim \
    --value 0.85 \
    --justification "Well-established by [@Smith2020] in the same regime." \
    --file priors.py
```

That command appends a `register_prior(...)` statement to `priors.py` and auto-injects the import if the target file is a sibling of `__init__.py`.

**Do NOT set priors for derived claims.** The inference engine automatically assigns uninformative priors (0.5) to derived claims. Their beliefs are determined entirely by BP propagation from leaf premises. Setting an explicit prior on a derived claim double-counts evidence: the reviewer's judgement and the reasoning chain both reflect the same underlying data. Only set priors for independent (leaf) claims that are not the conclusion of any relation.

**The π(Alt) discipline (`infer` alternatives) deserves special attention.** In the abductive pattern (theory-vs-experiment `infer`), the prior on the alternative reflects its **explanatory power for the specific observation**, not whether the alternative's computation is correct in general. The most common and consequential mistake in prior assignment is setting π(Alt) based on "the alternative's calculation is right," rather than "the alternative explains the observation." The deep guide — worked examples, rule-of-thumb checks, the explanatory-power-vs-correctness distinction — lives in `../../gaia-review/SKILL.md`. Read it before writing the prior on any abductive alternative.

The full prior-assignment guide (evidence-level → prior-range tables, warrant-prior ranges, iteration loop) also lives in `../../gaia-review/SKILL.md`. This skill points at it; do not duplicate the tables here.

### Run inference

```bash
gaia run infer <pkg>             # writes .gaia/beliefs.json
gaia run infer <pkg> --depth 1   # joint cross-package inference (direct deps)
gaia run infer <pkg> --depth -1  # joint cross-package inference (all transitive deps)
```

### Interpret BP results

Read the table in `../../_shared/bp-interpretation.md`. Do not duplicate the interpretation table here — that reference is the single canonical copy. The shape of the loop:

```
gaia run infer → .gaia/beliefs.json → interpret per ../../_shared/bp-interpretation.md
   ↓
   structural issues  → back to Pass 1-5 (revise graph)
   prior issues       → revise priors.py (revisit ../../gaia-review/SKILL.md guide)
   otherwise          → proceed to ANALYSIS.md
```

If results are clearly wrong (a well-supported conclusion has belief < 0.3, or a contradict relation does not pick a side), go back and check:

1. **Structural issue?** (→ revisit Pass 1-5.) Missing premises, wrong relation verb, missing alternative for an `infer`, evidence double-counting.
2. **Parameter issue?** (→ revisit `priors.py`.) Priors too low / high, `--p-e-given-h` miscalibrated, π(Alt) reflecting computational correctness instead of explanatory power.

## Generate the GitHub presentation

After the prior-assignment tail produces beliefs you trust, hand off to `../../gaia-publish/SKILL.md`:

```bash
gaia run render <pkg> --target github   # .github-output/ README + narrative outline
gaia run render <pkg> --target docs     # per-module Mermaid graphs in docs/detailed-reasoning.md
gaia run render <pkg> --target obsidian # gaia-wiki/ skeleton (hands off to ../../gaia-obsidian-wiki/SKILL.md)
```

`../../gaia-publish/SKILL.md` carries the README narrative discipline (per-conclusion evidence assessment, Weak Points framed around internal nodes, Evidence Gaps by theme). `../../gaia-obsidian-wiki/SKILL.md` carries the rich-vault discipline (claim pages with full derivations, section pages as narrative chapters).

## `ANALYSIS.md` — critical analysis deliverable

After BP results stabilise, produce a **critical analysis** of the source. This is the analytical payoff of formalization — by building the knowledge graph, you now understand the argument's structure well enough to identify its strengths and weaknesses.

`ANALYSIS.md` lives in the package root and is a **required deliverable** — do not skip it. The required sections:

### 1. Package statistics

Knowledge graph counts (claims by role, relations by verb, structural-verb counts), verb-type distribution, claim role classification, figure reference coverage, BP result summary.

### 2. Summary

One paragraph on the argument's overall structure and strength.

### 3. Weak points (table)

Internal nodes with low belief. **Internal nodes, not exported conclusions** — exported conclusions go in the README's Reasoning Structure section (`../../gaia-publish/SKILL.md`); `ANALYSIS.md` Weak Points is for the load-bearing intermediate nodes whose fragility threatens the whole chain.

Columns: claim, belief, issue. Include all derived claims with belief < 0.8 and any `infer`-alternative claims with belief > 0.25.

Vulnerability signals to capture in the "issue" column:

| Signal | What it means |
|--------|---------------|
| Derived conclusion with low belief (< 0.5) | Weak premise support or fragile reasoning chain |
| Long reasoning chain (4+ hops from leaf to conclusion) | Multiplicative effect — small uncertainties compound |
| `infer` alternative π(Alt) ≈ π(H) | Alternative is equally plausible — evidence does not distinguish |
| Leaf claim with low prior and many downstream dependents | Single weak foundation supporting many conclusions |
| `derive` warrant with very low prior (< 0.3) | Reviewer flagged this step as unreliable |
| Claim marked as `note` that could be questioned | Hidden assumption not subject to BP updating |

### 4. Evidence gaps (tables, grouped by theme)

Group by theme: **experimental**, **computational**, **theoretical**. Within each, identify where additional evidence would most strengthen the argument. For each gap: which conclusions improve if filled. Prioritise by impact.

- **Unsupported leaf claims:** claims with no reasoning support that the source takes as given — what evidence could back them up?
- **Weak `infer` alternatives:** where the alternative nearly matches the hypothesis in explanatory power — what new observation could break the tie?
- **Missing comparisons:** theoretical predictions without experimental validation — what experiment could test them?
- **Single-observation generalisations:** laws supported by only one observation — what additional observations would strengthen the `derive`?

### 5. Contradictions

(a) Explicit `contradict(...)` relations modelled and how BP resolved them (which side won). (b) Internal tensions in the source that were not modelled as formal contradictions but are worth flagging.

### 6. Confidence assessment

Tier the exported claims into confidence levels (very high / high / moderate / tentative) with belief ranges.

The critical analysis transforms a qualitative reading of the source into a quantitative structural assessment. Every knowledge package should ship with one.
