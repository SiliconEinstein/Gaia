---
name: publish
description: "Generate and publish README for a Gaia knowledge package — compile skeleton, fill narrative, push to GitHub."
---

# Publish

Generate a complete README for a Gaia knowledge package and push it to the GitHub repo.

## Full Pipeline

```
gaia compile . --github          # Step 1: generate skeleton + narrative outline
/gaia:publish                    # Step 2: this skill fills narrative + pushes
```

## Step 1: Generate Skeleton

Run in the package directory:

```bash
gaia compile . --github
```

This produces `.github-output/` containing:
- `README.md` — skeleton with Mermaid reasoning graph, MI annotation, conclusions table, and placeholders
- `narrative-outline.md` — auto-generated writing backbone (sections grouped by graph connectivity)
- `manifest.json` — checklist of exported conclusions and placeholders

**Important:** Only copy the skeleton to `README.md` the FIRST time. On subsequent runs, read the new `.github-output/` data (beliefs, outline) but do NOT overwrite the existing README — update it in place.

## Step 2: Read Inputs

```bash
cat .github-output/narrative-outline.md  # Your writing backbone
cat .github-output/manifest.json         # Exported conclusions list
cat .gaia/reviews/*/beliefs.json         # BP results
cat .github-output/docs/public/data/graph.json  # Check metadata.figure for images
ls src/<package>/*.py                    # DSL source code
```

## Step 3: Write README

### Bibliographic Header

The README must start with a proper citation of the original source material. Read `pyproject.toml` for the description, and the DSL source's module docstring or `artifacts/` for full bibliographic details.

```markdown
# Package Title

> **Original work:** [Author1, Author2, et al.] "[Paper Title]." *Journal Name* Volume, Pages (Year). [DOI/arXiv link]

[badges]
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

### MI + Mermaid graph (auto-generated, keep as-is)

### Reasoning Structure (YOU WRITE)

Add `## Reasoning Structure` after the Mermaid graph. This is the heart of the README — a standalone scientific narrative that a domain expert can read without knowing what Gaia, belief propagation, or factor graphs are.

**Audience:** A researcher in the paper's field. They understand the science but have not read this specific paper. They should come away understanding what the paper argues, why the argument is convincing, and where it is weak.

**Organizing principle:** Follow the paper's intellectual arc, not the factor graph topology. Use `narrative-outline.md` as a starting point for grouping, but reorganize freely — merge small groups, split large ones, reorder to match the paper's logical flow. Typical arc: motivation/problem → method → validation → results → implications.

**Section titles:** Concise, descriptive. Example: outline says "Noise-free reverse trajectories often improve success" → rewrite as "Benchmarking Against Prior Methods".

For each subsection, write 4-8 sentences of prose that:
- Explain the scientific question and why it matters
- Walk through the key evidence and reasoning **in the paper's own terms** (equations, experimental results, comparisons)
- Note where the argument is strongest or weakest, citing specific numbers from the paper
- Parenthetically cite belief values as supporting quantification, e.g. "...validated by the 0.2% agreement between full and downfolded BSE calculations (belief 0.76)"

**What NOT to do:**
- Do not organize around "premises → conclusion" or "strategy type"
- Do not lead with "(prior → belief)" annotations — they are parenthetical support, not the story
- Do not use Gaia-specific terms: "noisy_and", "abduction", "factor", "BP", "NAND constraint", "information gain bits" in the prose
- Do not describe the graph structure ("this claim is derived from two premises via...")
- Do not list claims — tell a story that connects them

The Mermaid graph and conclusions table already provide the technical Gaia view. The prose should complement them by telling the **scientific** story that the graph encodes.

### Embedding Figures

Check `graph.json` nodes for `metadata.figure` and `metadata.caption`. For each figure:
1. Embed it in the Reasoning Structure subsection where that claim appears
2. Use the original caption from `metadata.caption`
3. Add attribution: "Adapted from [Author et al., Year]" referencing the bibliographic header

```markdown
![Fig. 1 | Protein design using RFdiffusion. Diffusion models trained to recover 
corrupted structures via iterative denoising.](docs/public/assets/images/fig1.jpg)
*Adapted from Watson et al., Nature 2023.*
```

If `metadata.caption` is absent, write a descriptive caption based on the claim content.

### Key Findings table (auto-generated, keep as-is)

### Weak Points (YOU WRITE)

3-4 places where the paper's argument is weakest, written as a scientist would critique it:
- What is the weakest link in the reasoning, and why?
- What assumption is most likely to fail, and what would break?
- Where does the paper extrapolate beyond its evidence?
- What competing explanation has not been fully ruled out?

Cite belief values parenthetically as quantitative support for your critique, e.g. "The cross-term suppression assumption is the most vulnerable foundation (belief drops from prior 0.90 to 0.69 under downstream constraints)." Do not frame weak points in terms of graph structure — frame them in terms of scientific reasoning.

### Evidence Gaps (YOU WRITE)

2-3 places where additional evidence would help. Name specific missing evidence and which claims it would strengthen.

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

## Step 5: Push to GitHub

```bash
git add README.md
git commit -m "docs: update README via /gaia:publish"
git push origin main
```

Optionally also push wiki and docs:

```bash
cp -r .github-output/wiki .
cp -r .github-output/docs .
git add wiki/ docs/
git commit -m "docs: add wiki pages and GitHub Pages template"
git push origin main
```

## Ralph Loop Integration

For iterative refinement:

```
/ralph-loop "Read .github-output/narrative-outline.md and manifest.json.
Write README.md following /gaia:publish skill structure: bibliographic header,
summary, reasoning structure (rewrite outline group names as readable titles),
embed figures with captions and attribution, weak points with mechanisms,
evidence gaps. Preview and verify before pushing.
Output <promise>PUBLISH COMPLETE</promise> when quality checklist passes."
--max-iterations 5
```
