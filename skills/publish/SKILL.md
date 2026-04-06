---
name: publish
description: "Fill narrative content into GitHub presentation skeleton — summaries, figures, translations, critical analysis."
---

# Publish

## 1. Overview

This skill runs AFTER `gaia compile . --github` has generated `.github-output/`. The compiler produces a deterministic skeleton (wiki pages, README with placeholders, React Pages template, graph.json). This skill fills LLM-generated narrative content into that skeleton.

Can run standalone or via Ralph Loop for iterative refinement with Chrome DevTools rendering checks.

## 2. Read Manifest

Read `.github-output/manifest.json` first. It is your checklist.

```bash
cat .github-output/manifest.json
```

Extract and track:
- `readme_placeholders` -- each must be filled in README.md
- `pages_sections` -- each must get a narrative in `docs/public/data/sections/`
- `assets` -- available figures for embedding
- `exported_conclusions` -- every one must appear in the README narrative

## 3. Fill README NARRATIVE_SUMMARY

**Inputs:** DSL source (`src/<package>/*.py`) + beliefs (`.gaia/reviews/*/beliefs.json`)

Write ONE paragraph (3-5 sentences):
1. What the source material investigates
2. Key findings -- name each exported conclusion explicitly
3. Overall confidence level from BP results

Replace `<!-- NARRATIVE_SUMMARY: ... -->` in `.github-output/README.md` with the paragraph.

**Bad:** "This package contains 42 claims organized into 5 modules..."
**Good:** "This package formalizes Eliashberg theory for conventional superconductors, demonstrating that predicted Tc values for aluminum (0.93 posterior) and lithium (0.87 posterior) align with experimental measurements..."

## 4. Fill README FIGURES

Scan `graph.json` nodes for `metadata.figure` fields. Select 1-3 figures:
1. Prefer figures attached to exported conclusions
2. Then figures on high-belief claims
3. Skip figures on low-belief or orphaned claims

Embed as markdown images in `.github-output/README.md`:
```markdown
![Caption describing the figure](docs/public/assets/filename.png)
```

Replace `<!-- FIGURES: ... -->` with the embedded images.

## 5. Fill Pages Section Narratives

For each `docs/public/data/sections/*.md`:
1. Find the corresponding module in DSL source
2. Read the module's claims, strategies, and beliefs
3. Write 4-8 sentences that tell the STORY of the reasoning

Cover:
- What question does this module address?
- What are the key premises?
- How does the reasoning flow from premises to conclusion?
- What did BP reveal -- surprises, confirmations, belief shifts?

**CRITICAL:** Do NOT list claims. Tell the narrative. A reader should understand the argument flow without seeing the knowledge graph.

**Bad:** "This module contains claim_a (prior 0.9), claim_b (prior 0.8), and claim_c derived by deduction."
**Good:** "The method module asks whether Eliashberg theory can predict Tc from first principles. Starting from the established phonon spectrum and electron-phonon coupling constants, a deductive chain derives the gap equation solution. BP confirms the derivation with high confidence (0.91), though the McMillan approximation introduces a small systematic uncertainty..."

## 6. Generate Chinese Translations

For each `sections/*.md`, create `sections/*-zh.md` with Chinese translation.
For each `wiki/*.md` (except Home.md), create `wiki/*-zh.md`.

Quality requirements:
- Natural Chinese, not machine-literal translation
- Technical terms keep English in parentheses on first use: "超导转变温度 (Tc)"
- Match the narrative structure of the English version

## 7. Critical Analysis

Add two subsections in README after Key Figures:

**Weak Points** (2-4 items):
- Structurally vulnerable claims: low belief, long reasoning chains, weak abductions
- Each point: 1-2 sentences with specific claim name and belief value

**Evidence Gaps** (2-3 items):
- Where additional evidence would most strengthen the argument
- Each point: what evidence is needed and which claims it would affect

## 8. Quality Checklist

Verify before declaring done:
- [ ] All `exported_conclusions` from manifest appear in README narrative
- [ ] All `readme_placeholders` filled -- no `<!-- ... -->` comments remain
- [ ] All `pages_sections` have narrative content (not empty or placeholder)
- [ ] Figures with `metadata.figure` embedded in README or Pages sections
- [ ] Chinese translations exist for all sections and wiki pages
- [ ] No claim-listing -- all narratives tell stories

## 9. Ralph Loop Integration

Ready-to-use prompt for iterative refinement:

```
/ralph-loop "Read .github-output/manifest.json. Fill all placeholders
in README.md and docs/public/data/sections/. Read the Python DSL source
code and beliefs.json. Write narrative summaries, embed figures, generate
Chinese translations. Check docs/ rendering with Chrome DevTools.
Output <promise>PUBLISH COMPLETE</promise> when all placeholders filled
and pages render correctly." --max-iterations 10
```
