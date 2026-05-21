---
name: gaia-publish
description: |
  Use after `gaia run render <pkg> --target github` to fill the README skeleton
  with a per-conclusion evidence-assessment narrative, write Weak Points and
  Evidence Gaps sections framed around internal nodes, then push README +
  ANALYSIS.md + docs/detailed-reasoning.md to GitHub. Agent-side prose
  discipline anchored on a single render verb.
---

# gaia-publish

## Intent

Convert a compiled-and-inferred Gaia knowledge package into a polished GitHub README. The CLI dependency is a single verb — `gaia run render --target github` — that emits a skeleton plus structured input data. Everything that gives the README its value (the per-conclusion narrative, the Weak Points framing, the Evidence Gaps grouping, the jargon-free voice) is agent-side writing discipline. This skill carries that discipline.

The output is a `README.md` at the package root that any scientist in the source's field can read end-to-end without prior exposure to Gaia. Belief values appear parenthetically as quantitative summaries of the reasoning graph's verdict, never as the subject of a sentence and never explained in DSL terms.

## CLI invocations

Prerequisites: the package has been compiled (`gaia build compile <pkg>`) and inferred (`gaia run infer <pkg>`). Both must be fresh — `gaia run render --target github` will refuse stale inputs.

```bash
# Generate the GitHub-target render: README skeleton + narrative outline + manifest + graph data
gaia run render <pkg> --target github

# Per-module Mermaid reasoning graphs for the docs/ companion page
gaia run render <pkg> --target docs
```

The `--target github` run writes `.github-output/` containing:

- `README.md` — skeleton with bibliographic-header placeholders, Mermaid reasoning graph, Key Findings table, placeholder comments where narrative goes.
- `narrative-outline.md` — auto-generated writing backbone, sections grouped by graph connectivity in the source's logical arc.
- `manifest.json` — exported-conclusions checklist + placeholder map.
- `docs/public/data/graph.json` — figure metadata + node/edge data backing the Mermaid graph.

The `--target docs` run writes `docs/detailed-reasoning.md` with per-module reasoning graphs and full claim details.

Input reads (no gaia verb needed — plain shell):

```bash
cat .github-output/narrative-outline.md     # writing backbone
cat .github-output/manifest.json            # exported conclusions
cat .gaia/beliefs.json                      # BP results
cat .github-output/docs/public/data/graph.json  # figure metadata + graph
ls src/<package>/*.py                       # DSL source for grounding
ls artifacts/                               # source paper, figures, references
```

The README is an analysis of the reasoning graph, not a paper summary. The graph may assign low belief to claims the source presents confidently, or surface structural weaknesses the source glosses over. Trust the graph's assessment over the source's rhetoric — and explain the divergence when it exists.

Finally, vanilla git for the push:

```bash
git add README.md ANALYSIS.md docs/detailed-reasoning.md
git commit -m "docs: update README from gaia run render"
git push origin main
```

## Methodology

### First-time vs. update

The first time you publish a package, copy `.github-output/README.md` to the package root as `README.md` and proceed with section-by-section narrative writing. The skeleton is your starting canvas.

On every subsequent run, the workflow inverts: `gaia run render --target github` regenerates fresh `.github-output/` data (new beliefs, new outline, new graph), but you do **not** overwrite the existing `README.md`. Instead, read the new outputs as input data and update `README.md` in place — preserving any user-curated outer wrappers (custom intro paragraphs, audience-specific framing, project-specific section ordering). Sections that the agent owns (Reasoning Structure verdicts, Weak Points, Evidence Gaps) get rewritten against the new beliefs; bibliographic header and human-authored framing stay.

If the graph's structure changes substantively (new exported conclusions, removed sections), check that `narrative-outline.md` still matches the README's section ordering before rewriting individual sections.

### Bibliographic header

The README opens with a proper citation of the original source material. Pull authors, title, journal, year, DOI from `pyproject.toml` `description`, from the DSL source module docstrings, or from `artifacts/paper.md` / `artifacts/references.json`.

Shape:

```markdown
# Package Title

> **Original work:** [Author1, Author2, et al.] "[Source Title]." *Journal/Venue* Volume, Pages (Year). [DOI/arXiv link]

<!-- badges:start -->
<!-- badges:end -->

> [!NOTE]
> This README is an AI-generated analysis based on a [Gaia](https://github.com/SiliconEinstein/Gaia)
> reasoning graph formalization of the original work. Belief values reflect the graph's
> probabilistic assessment of each claim's support, not the original authors' confidence.
> See [ANALYSIS.md](ANALYSIS.md) for detailed verification results.
```

Replace the `<!-- badges:start --><!-- badges:end -->` pair with links to CI, docs, the wiki output, and GitHub Pages if any of those exist for the repo. Keep the AI-generated-analysis disclaimer verbatim — it sets the right expectation for readers and is the canonical pointer to `ANALYSIS.md` (produced upstream by `gaia-formalize-fine`).

The bibliographic header is also the canonical attribution source for figure captions later in the document. Pin author + year here so every figure embed can refer back to it consistently.

### Summary paragraph

One paragraph, 3-5 sentences, that any scientist in the field can read cold. Required elements:

- **What** the source material investigates and why it matters.
- **How** — the core innovation or methodology, in plain prose.
- **Key numbers** from the source itself (e.g. "predicts Tc(Al) = 0.96 K vs experimental 1.2 K"), not graph quantities.
- **Optional belief** value parenthetically for the single most consequential conclusion, only if it adds information.

The summary must make sense without any belief values. Do not name internal claims by their DSL labels. Do not mention reasoning graphs, beliefs, or inference in the summary itself — that framing lives in the disclaimer.

### Reasoning Structure section (per-conclusion writing)

Add `## Reasoning Structure` after the auto-generated Mermaid graph + MI callout (both of which the skeleton renders; leave them as-is). This section is the heart of the README — a per-conclusion evidence assessment for every exported conclusion in `manifest.json`.

**Audience.** A researcher in the source's field who has not read the original work. After this section, they should understand what each conclusion claims, how it was derived, how strong the evidence is, and what risks remain.

**Ordering.** Follow `narrative-outline.md`, which orders conclusions along the source's logical arc (foundational results → derived consequences → final predictions). **Do not** sort by belief value — that produces an order that's incoherent as a narrative and buries early-chain results.

**For each conclusion, write four parts:**

1. **Descriptive title.** Rewrite the raw label into a sentence a non-specialist understands, plus the belief value in parentheses. Never use the label directly.
   - Bad: `### Downfolded BSE (belief: 0.33)`
   - Good: `### The full Bethe-Salpeter equation reduces to a solvable frequency-only form (belief: 0.33)`

2. **What it says** (one paragraph). Explain the scientific result in enough detail for a reader unfamiliar with the source to follow it. Include the key quantitative result (numbers, equations); what problem this solves and why it matters; how it was obtained (method, key approximations); and comparison with prior approaches where relevant. Read `artifacts/` for specifics — do not write generic descriptions.

3. **Evidence chains** (2-4 bullets). For each major chain supporting this conclusion:
   - Name the chain descriptively (one phrase capturing what the chain establishes).
   - Trace the key intermediate claims and call out the chain's weakest link with its belief.
   - Explain **why** the weakest link is weak — not just the number, but the underlying assumption, approximation, or evidentiary gap.

4. **Figures.** Embed relevant figures from `artifacts/images/` with descriptive italic captions and attribution back to the source authors (use the bibliographic header for the canonical attribution string).

5. **Verdict** (1-2 sentences). Is this conclusion well-supported? What's the main residual risk? When the verdict's belief is unusually low or unusually high, point at `../_shared/bp-interpretation.md` mentally for how to phrase the takeaway — but write the sentence as scientific critique, not graph analysis.

**Worked example** (after vocab pass):

```markdown
### The full Bethe-Salpeter equation reduces to a solvable frequency-only form (belief: 0.33)

The central theoretical achievement of this work is a rigorous downfolding of
the complete momentum-frequency Bethe-Salpeter equation into a one-dimensional
integral equation depending only on Matsubara frequency:
$K(\omega,\omega') = \lambda(\omega,\omega') - \mu_{\omega_c}(\omega,\omega')$.
This is accomplished by decomposing the pair propagator into coherent and
incoherent parts (an exact mathematical identity), then showing that
cross-channel mixing between Coulomb and phonon sectors is suppressed at
$O(\omega_c^2/\omega_p^2) \leq 1\%$. The resulting equation gives
$\mu^\ast$ and $\lambda$ precise microscopic definitions for the first time,
replacing the phenomenological parameters used since the 1960s. Numerical
validation against the full BSE on a toy model with aluminum-like parameters
shows 0.2% agreement in predicted $T_c$.

**Evidence chains:**

- **Cross-term suppression** (weakest link, belief 0.50): The entire downfolding
  rests on cross-channel terms being ~1%. The estimate uses a plasmon-pole model
  that may overstate the suppression for low-density metals or 2D systems.
- **Toy-model validation** (belief 0.76): Full vs downfolded equation agree to
  0.2% in predicted $T_c$, but the validation uses RPA for the electron vertex —
  not the exact vertex function.

![Fig. 3 | Diagrammatic structure of the equation](artifacts/images/4_2.jpg)
*The equation with decomposed pair propagator. Adapted from Cai et al.*

> This is the theoretical foundation for everything downstream. The low belief
> (0.33) reflects uncertainty propagation from the cross-term suppression
> assumption — if cross terms are larger than 1%, the entire framework needs
> revision.
```

### Weak Points section

`## Weak Points` lives after the Key Findings table (which the skeleton emits and you keep as-is). Focus on **internal nodes** — intermediate or hole claims with low belief — **not** exported conclusions. Exported conclusions are already covered in Reasoning Structure; surfacing them again here is duplication. Internal weakness is what the reasoning graph uniquely sees that the source's narrative does not.

Shape:

```markdown
## Weak Points

<details open>
<summary>Weak Points Analysis</summary>

[Executive summary — one sentence naming the single weakest internal link.]

[3-5 weak points, each a full paragraph; see structure below.]

[Closing paragraph on structural patterns.]

</details>
```

For each weak point — an intermediate or hole claim with low belief — write a paragraph covering:

- **Location in the chain.** What the claim says, and where it sits relative to other claims (which conclusions depend on it, which premises feed into it).
- **Root cause.** Trace backwards from the low belief: which premise prior is too low, which warrant is weak, which `contradict` is firing.
- **Downstream impact.** Trace forwards: which exported conclusions inherit this weakness, and how much it pulls them down.
- **Vulnerable assumption.** Name the single most fragile assumption — the one whose revision would most change the belief.
- **Resolving experiment or computation.** What specific work would resolve the weakness? Be concrete (a measurement, a derivation, a tighter bound).

Closing paragraph identifies **structural patterns**: are there bottleneck nodes that many conclusions depend on? Does uncertainty amplify through long derivation chains? Is one weakly-grounded assumption shared by multiple chains?

Cite belief values parenthetically. Frame as scientific critique, not graph analysis — readers should understand what's weak about the science, not what's weak about the graph.

### Evidence Gaps section

`## Evidence Gaps` follows Weak Points. Group gaps by theme so readers can scan for the kind of work that would advance the field:

```markdown
## Evidence Gaps

<details>
<summary>Evidence Gaps & Future Work</summary>

### Experimental gaps
- [Each gap as a bullet; name which conclusions improve if filled.]

### Computational gaps
- [...]

### Theoretical gaps
- [...]

</details>
```

For each gap, name **which conclusions improve** if it is filled — this is what turns the section from a wish-list into a research roadmap. Prioritise within each theme by impact (largest belief change for the most conclusions first).

Themes:

- **Experimental gaps.** Missing or imprecise measurements; experiments that would most reduce uncertainty.
- **Computational gaps.** Approximations that could be made exact; parameters with the largest error bars.
- **Theoretical gaps.** Derivations relying on uncontrolled approximations; regimes where the theory breaks down.

Some gaps cross themes (a missing measurement that motivates a tighter derivation). Group by the dominant theme and cross-reference in prose.

### Link to ANALYSIS.md

If the package has an `ANALYSIS.md` (produced upstream by `gaia-formalize-fine`'s Pass 5/6 + prior-assignment tail), close the README with:

```markdown
## Detailed Analysis

For structural integrity verification, standalone readability checks, and complete
package statistics, see [ANALYSIS.md](ANALYSIS.md).
```

### Preview checklist

Before pushing, verify the README is reader-ready:

```bash
# Placeholder scan
grep -n "<!-- " README.md

# Terminal preview (if glow is installed)
glow README.md
```

Run through the checklist:

- [ ] No `<!-- ... -->` placeholder comments remain.
- [ ] Every exported conclusion from `manifest.json` appears in Summary or Reasoning Structure.
- [ ] Reasoning Structure reads as scientific narrative — a domain expert can follow it without knowing what Gaia is.
- [ ] **No Gaia jargon in user-visible prose** — no `noisy_and`, `BP`, `factor graph`, `NAND`, `abduction`, no DSL function names. Reasoning Structure is the science; the disclaimer carries the framing.
- [ ] Belief values appear **only parenthetically** — never as the subject of a sentence, never as a lead.
- [ ] Figures embedded with italic captions and attribution to the source authors.
- [ ] Weak Points are framed as scientific critique, not graph-structure descriptions.
- [ ] Bibliographic header present and complete.

### GitHub push

Commit and push the README plus its companion documents:

```bash
git add README.md ANALYSIS.md docs/detailed-reasoning.md
git commit -m "docs: update README from gaia run render"
git push origin main
```

Optionally, the GitHub-target render also stages a wiki tree and a Pages template under `.github-output/`. To publish those:

```bash
cp -r .github-output/wiki .
cp -r .github-output/docs .
git add wiki/ docs/
git commit -m "docs: refresh wiki and Pages template from gaia run render"
git push origin main
```

The wiki tree and Pages template are alternative output channels; for a richer browsable form of the same package, see `../gaia-obsidian-wiki/SKILL.md`.

## BP-interpretation pointer

When writing verdict sentences in Reasoning Structure and the root-cause sentences in Weak Points, the question is always "what does this belief value mean about the science?" For the canonical mapping from belief patterns (independent premise behaviour, derived-conclusion behaviour, contradict/exclusive resolution, abnormal patterns and their common fixes), see `../_shared/bp-interpretation.md`. Do not paraphrase that table inline — point at it and write the verdict in the source's own scientific vocabulary.

## Cross-refs

- `../_shared/bp-interpretation.md` — belief-result interpretation reference; consult when phrasing verdicts and root-cause sentences.
- `../gaia-formalize-fine/SKILL.md` — upstream skill that produces the knowledge package and `ANALYSIS.md`; the README's Detailed Analysis section links into it.
- `../gaia-obsidian-wiki/SKILL.md` — alternate output channel; richer browsable vault for the same package, when README polish is not the goal.
