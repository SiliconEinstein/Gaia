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

One paragraph (3-5 sentences):
- What the source material investigates and why it matters
- Core innovation or methodology
- Key results — name exported conclusions with belief values

### MI + Mermaid graph (auto-generated, keep as-is)

### Reasoning Structure (YOU WRITE)

Add `## Reasoning Structure` after the Mermaid graph. Create ONE `###` subsection per group in `narrative-outline.md`.

**Section titles:** The outline's group names come from the most prominent claim and may be too long or awkward. Rewrite them as concise, readable section titles that describe what the group is about. Example: outline says "Noise-free reverse trajectories often improve success" → rewrite as "Method Validation and Benchmarks".

For each subsection, write 4-8 sentences of prose:
- What question does this group of claims address?
- Key premises and their confidence (prior → belief)
- How the reasoning connects them to conclusions
- What BP revealed — which beliefs shifted most and why
- Inline MI for key edges: "this derivation provides 0.30 bits"

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

3-4 structurally vulnerable claims. For each, explain the MECHANISM:
- Long derivation chain → multiplicative belief erosion
- Contradiction draining probability from both sides
- Low MI edge → premises barely reduce uncertainty
- High prior dropping to low belief → constraints pulling it down

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
- [ ] All exported conclusions from manifest mentioned in Summary
- [ ] Reasoning Structure has one subsection per outline group
- [ ] All subsections tell stories, no claim-listing
- [ ] Figures embedded with captions and attribution
- [ ] Weak Points explain mechanisms
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
