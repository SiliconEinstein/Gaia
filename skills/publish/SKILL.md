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

## Step 2: Read Inputs

Read these files to understand the package:

```bash
cat .github-output/narrative-outline.md  # Your writing backbone
cat .github-output/manifest.json         # Exported conclusions list
cat .gaia/reviews/*/beliefs.json         # BP results
ls src/<package>/*.py                    # DSL source code
```

Also read `.github-output/README.md` to see the auto-generated skeleton you'll extend.

## Step 3: Write README

Copy the skeleton and fill the placeholders:

```bash
cp .github-output/README.md README.md
```

The final README structure:

### Title + Badges (auto-generated, keep as-is)

Replace `<!-- badges:start --><!-- badges:end -->` with badges linking to Pages and Wiki if they exist.

### Summary (YOU WRITE)

Add `## Summary` after badges, before the Overview section. One paragraph (3-5 sentences):
- What the source material investigates and why it matters
- Core innovation or methodology
- Key results — name exported conclusions with belief values

**Bad:** "This package contains 42 claims organized into 6 modules..."
**Good:** "This paper develops a parameter-free framework for predicting superconducting Tc by computing the Coulomb pseudopotential from first principles. The predicted values for Al (belief 0.93), Zn (0.93), and Li (0.96) closely match experiment..."

### MI + Mermaid graph (auto-generated, keep as-is)

### Reasoning Structure (YOU WRITE)

Add `## Reasoning Structure` after the Mermaid graph. Create ONE `###` subsection per group in `narrative-outline.md`.

For each subsection, write 4-8 sentences of prose:
- What question does this group of claims address?
- What are the key premises and their confidence (prior → belief)?
- How does the reasoning connect them to the conclusion?
- What did BP reveal — which beliefs shifted most and why?
- Inline MI for key edges: "this derivation provides 0.30 bits"
- If a claim has `metadata.figure`, embed: `![Caption](docs/public/assets/path)`

**Bad:** "This section contains adiabatic_approx (prior 0.95, belief 0.90) and cross_term_suppressed (prior 0.90, belief 0.69). They support downfolded_bse."

**Good:** "The downfolding derivation starts from the adiabatic separation of energy scales (0.95 → 0.90) and the suppression of cross-channel terms (0.90 → 0.69). Together they yield the downfolded BSE (belief 0.76), providing 0.10 bits of information. The moderate belief reflects the cross-term estimate's reliance on a plasmon-pole argument..."

### Key Findings table (auto-generated, keep as-is)

### Weak Points (YOU WRITE)

Replace `<!-- content:start --><!-- content:end -->` with `## Weak Points` (3-4 items).

For each weak claim, explain the MECHANISM:
- Long derivation chain → multiplicative belief erosion
- Contradiction draining probability from both sides
- Low MI edge → premises barely reduce uncertainty
- High prior dropping to low belief → downstream constraints pulling it down

**Bad:** "mu_vdiagmc_values has belief 0.50."
**Good:** "μ* from vDiagMC (belief 0.50) is the weakest exported conclusion. It depends on two computational premises via a noisy-AND (0.09 bits), and participates in a contradiction with the RPA prediction, which drains probability from both sides."

### Evidence Gaps (YOU WRITE)

Add `## Evidence Gaps` (2-3 items). For each: what evidence is missing, and which claims it would strengthen.

## Step 4: Push to GitHub

```bash
git add README.md
git commit -m "docs: update README via /gaia:publish"
git push origin main
```

If wiki/ and docs/ from `.github-output/` should also be pushed:

```bash
cp -r .github-output/wiki .
cp -r .github-output/docs .
git add wiki/ docs/
git commit -m "docs: add wiki pages and GitHub Pages template"
git push origin main
```

## Quality Checklist

Before pushing, verify:
- [ ] All `exported_conclusions` from manifest mentioned in Summary
- [ ] No `<!-- ... -->` placeholder comments remain in README
- [ ] Reasoning Structure has one subsection per narrative-outline group
- [ ] Each subsection tells a story — no claim-listing
- [ ] Figures from `metadata.figure` embedded where relevant
- [ ] Weak Points explain WHY (mechanism), not just belief values
- [ ] Evidence Gaps name specific missing evidence and affected claims

## Ralph Loop Integration

For iterative refinement:

```
/ralph-loop "Read .github-output/narrative-outline.md and manifest.json.
Write README.md: Summary, Reasoning Structure (one subsection per outline
group), Weak Points with mechanisms, Evidence Gaps. Push to GitHub.
Output <promise>PUBLISH COMPLETE</promise> when quality checklist passes."
--max-iterations 5
```
