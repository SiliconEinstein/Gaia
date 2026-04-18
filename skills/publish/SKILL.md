---
name: publish
description: "Generate and publish README for a Gaia knowledge package — compile skeleton, fill narrative, push to GitHub."
---

# Publish

Generate a complete README for a Gaia knowledge package and push it to the GitHub repo.

## Full Pipeline

```
gaia render . --target github    # Step 1: generate skeleton + narrative outline
/gaia:publish                    # Step 2: this skill fills narrative + pushes
```

## Step 1: Generate Skeleton

Run in the package directory (requires `gaia compile` and `gaia infer` to have been run first):

```bash
gaia render . --target github
```

This produces `.github-output/` containing:
- `README.md` — skeleton with Mermaid reasoning graph, MI annotation, conclusions table, and placeholders
- `narrative-outline.md` — auto-generated writing backbone (sections grouped by graph connectivity)
- `manifest.json` — checklist of exported conclusions and placeholders

**Important:** Only copy the skeleton to `README.md` the FIRST time. On subsequent runs, read the new `.github-output/` data (beliefs, outline) but do NOT overwrite the existing README — update it in place.

## Step 2: Read Inputs

Primary inputs (drive the narrative):
```bash
cat .github-output/narrative-outline.md  # Writing backbone from graph structure
cat .github-output/manifest.json         # Exported conclusions list
cat .gaia/beliefs.json         # BP results
cat .github-output/docs/public/data/graph.json  # Figure metadata + graph data
ls src/<package>/*.py                    # DSL source code (claims, strategies, reasons)
```

Optional — read `artifacts/` (original paper, figures) for factual grounding (equations, experimental numbers, figure context). But be careful: the README is an **analysis driven by the reasoning graph**, not a paper summary. The graph may assign low belief to claims the paper presents confidently, or reveal structural weaknesses the paper glosses over. Trust the graph's assessment over the paper's rhetoric.

## Step 3: Write README

### Bibliographic Header

The README must start with a proper citation of the original source material. Read `pyproject.toml` for the description, and the DSL source's module docstring or `artifacts/` for full bibliographic details.

```markdown
# Package Title

> **Original work:** [Author1, Author2, et al.] "[Paper Title]." *Journal Name* Volume, Pages (Year). [DOI/arXiv link]

[badges]

> [!NOTE]
> This README is an AI-generated analysis based on a [Gaia](https://github.com/SiliconEinstein/Gaia) reasoning graph formalization of the original work. Belief values reflect the graph's probabilistic assessment of each claim's support, not the original authors' confidence. See [ANALYSIS.md](ANALYSIS.md) for detailed verification results.
```

The agent should find authors, title, journal from the package's `pyproject.toml` description, module docstrings, or `artifacts/paper.md`. This citation is used for figure attributions later.

### Badges

Replace `<!-- badges:start --><!-- badges:end -->` with links to Pages and Wiki if they exist.

### Summary (YOU WRITE)

One paragraph (3-5 sentences) readable by any scientist:
- What the source material investigates and why it matters
- Core innovation or methodology
- Key results with concrete numbers from the paper (e.g. "predicts Tc(Al) = 0.96 K vs experimental 1.2 K")
- Belief values may be cited parenthetically for the most important conclusions, but the summary should make sense without them

### MI callout + Mermaid graph (auto-generated, keep as-is)

The skeleton includes a `[!TIP]` callout with the total mutual information and a Mermaid reasoning graph. Keep both as generated.

### Reasoning Structure (YOU WRITE)

Add `## Reasoning Structure` after the Mermaid graph. This is the heart of the README — a **per-conclusion evidence assessment**. For each exported conclusion, analyze how well the evidence supports it.

**Audience:** A researcher in the paper's field who has NOT read the original paper. After reading this section, they should understand what each conclusion claims, how it was derived, how strong the evidence is, and what risks remain.

**Ordering:** Follow `narrative-outline.md` — this orders conclusions by the paper's logical arc (from foundational results to final predictions), NOT by belief value. The narrative flow should mirror the paper's argument: theory → computation → validation → predictions.

**For each conclusion, write:**

1. **Heading**: Rewrite the claim title into a descriptive sentence that a non-specialist can understand, plus belief value. Don't use the raw label — write a meaningful title.
   - BAD: `### Downfolded BSE (belief: 0.33)`
   - GOOD: `### The full Bethe-Salpeter equation reduces to a solvable frequency-only form (belief: 0.33)`

2. **What it says** (1 paragraph): Explain the scientific result in enough detail that a reader unfamiliar with the paper can understand it. Include:
   - The key quantitative result (numbers, equations)
   - What problem this solves and why it matters
   - How it was obtained (method, key approximations)
   - Comparison with prior approaches (if applicable)
   - Read `artifacts/` for specific details — don't write generic descriptions

3. **Evidence chains** (2-4 bullet points): Each evidence chain supporting this conclusion:
   - Name the chain descriptively
   - Trace the key nodes and give the weakest link's belief
   - Explain WHY the weakest link is weak (not just the number)

4. **Figures**: Embed relevant figures from `artifacts/images/` with descriptive captions

5. **Verdict** (1-2 sentences): Is this conclusion well-supported? What's the main risk?

**Example:**

```markdown
### The full Bethe-Salpeter equation reduces to a solvable frequency-only form (belief: 0.33)

The central theoretical achievement of this work is a rigorous
"downfolding" of the complete momentum-frequency Bethe-Salpeter
equation into a one-dimensional integral equation depending only
on Matsubara frequency: $K(\omega,\omega') = \lambda(\omega,\omega')
- \mu_{\omega_c}(\omega,\omega')$. This is accomplished by
decomposing the pair propagator into coherent and incoherent parts
(an exact mathematical identity), then showing that cross-channel
mixing between Coulomb and phonon sectors is suppressed at
$O(\omega_c^2/\omega_p^2) \leq 1\%$. The resulting equation gives
$\mu^\ast$ and $\lambda$ precise microscopic definitions for the
first time — replacing the phenomenological parameters used since
the 1960s. Numerical validation against the full BSE on a toy model
with aluminum-like parameters shows 0.2% agreement in predicted $T_c$.

**Evidence support:**
- **Cross-term suppression** (weakest link, belief 0.50): The entire
  downfolding rests on cross-channel terms being ~1%. The estimate
  uses a plasmon-pole model that may overstate the suppression for
  low-density metals or 2D systems.
- **Toy model validation** (belief 0.76): Full vs downfolded BSE
  agree at 0.2%, but this uses RPA for the electron vertex — not
  the exact vertex function.

![Fig. 3 | Diagrammatic structure of the BSE](artifacts/images/4_2.jpg)
*The BSE with decomposed pair propagator. Adapted from Cai et al.*

> This is the theoretical foundation for everything downstream.
> The low belief (0.33) reflects uncertainty propagation from the
> cross-term suppression assumption — if cross terms are larger
> than 1%, the entire framework needs revision.
```

The good version explains the science in detail, gives context (why this matters, what existed before), includes the specific mathematical result, and makes the verdict meaningful.

**What NOT to do:**
- Do not write a narrative essay — write per-conclusion assessments
- Do not use Gaia jargon (noisy_and, abduction, factor, BP, NAND)
- Do not describe graph structure — describe evidence strength
- Do not lead with belief values — lead with the science

### Key Findings table (auto-generated, keep as-is)

### Weak Points (YOU WRITE)

**Focus: internal nodes with low belief — NOT the conclusions themselves** (those are covered in Reasoning Structure). Discuss intermediate claims and premises where the argument is structurally weak.

<details open>
<summary>Weak Points Analysis</summary>

Write 3-5 weak points, each as a full paragraph:

1. **Executive summary** (1 sentence): The single weakest internal link.

2. **For each weak point** — an intermediate or hole claim with low belief:
   - What the claim says and WHERE it sits in the reasoning chain
   - WHY the belief is low — trace backwards to the root cause
   - What downstream conclusions are affected (trace forward)
   - What assumption is most vulnerable
   - What specific evidence or experiment would resolve it

3. **Structural patterns**: Are there bottleneck nodes that many conclusions depend on? Does uncertainty amplify through the chain?

Cite belief values parenthetically. Frame as scientific critique, not graph analysis.

</details>

### Evidence Gaps (YOU WRITE)

<details>
<summary>Evidence Gaps & Future Work</summary>

Group by theme:

**Experimental gaps:**
- What measurements are missing or imprecise?
- What experiments would most reduce uncertainty?

**Computational gaps:**
- What calculations are approximate that could be exact?
- What parameters have the largest error bars?

**Theoretical gaps:**
- What derivations rely on uncontrolled approximations?
- Where does the theory break down?

For each gap, name which conclusions would improve if it were filled. Prioritize by impact.

</details>

### Link to ANALYSIS.md

If the package has an `ANALYSIS.md` (generated during formalization Pass 5/6), add a final section linking to it:

```markdown
## Detailed Analysis

For structural integrity verification (Pass 5), standalone readability checks (Pass 6),
and complete package statistics, see [ANALYSIS.md](ANALYSIS.md).
```

## Step 4: Preview Before Pushing

Before pushing, verify the README renders correctly:

```bash
# Quick check: search for unfilled placeholders
grep -n "<!-- " README.md

# Preview in terminal (if glow is installed)
glow README.md

# Or open in browser
open README.md  # macOS
```

Verify:
- [ ] No `<!-- ... -->` placeholder comments remain
- [ ] All exported conclusions from manifest mentioned in Summary or Reasoning Structure
- [ ] Reasoning Structure reads as a scientific narrative — a domain expert can understand it without knowing what Gaia is
- [ ] No Gaia jargon in prose (no "noisy_and", "abduction", "factor graph", "BP", "NAND constraint")
- [ ] Belief values appear only parenthetically, never as the subject of a sentence
- [ ] Figures embedded with captions and attribution
- [ ] Weak Points are scientific critiques, not graph-structure descriptions
- [ ] Bibliographic header present

## Step 5: Generate Per-Module Graphs

```bash
gaia render . --target docs
```

This writes `docs/detailed-reasoning.md` with per-module Mermaid reasoning graphs and full claim details. Add a `[!NOTE]` callout in the README after the overview Mermaid graph:

```markdown
> [!NOTE]
> **[Per-module reasoning graphs with full claim details →](docs/detailed-reasoning.md)**
>
> 6 Mermaid diagrams (one per section) with every claim, strategy, and belief value.
```

## Step 6: Push to GitHub

```bash
git add README.md ANALYSIS.md docs/detailed-reasoning.md
git commit -m "docs: update README via /gaia:publish"
git push origin main
```

Optionally also push wiki and Pages template:

```bash
cp -r .github-output/wiki .
cp -r .github-output/docs .
git add wiki/ docs/
git commit -m "docs: add wiki pages and GitHub Pages template"
git push origin main
```
