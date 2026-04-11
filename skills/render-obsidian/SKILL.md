---
name: render-obsidian
description: "Use when user wants a browsable Obsidian wiki from a Gaia knowledge package — generates skeleton, fills narrative from IR and original sources, audits cross-references."
---

# Render Obsidian Wiki

Generate a rich, browsable Obsidian vault (`gaia-wiki/`) from a Gaia knowledge package. The agent drives the full pipeline: skeleton generation, narrative filling, and cross-reference audit.

## Full Pipeline

```
/gaia:render-obsidian
  ↓
Step 1: gaia compile + gaia infer (if review exists)
Step 2: gaia render --target obsidian → gaia-wiki/ skeleton
Step 3: Read inputs (IR, beliefs, artifacts/)
Step 4: Fill narrative per page (agent writes directly)
Step 5: Cross-reference audit
Step 6: Report
```

## Step 1: Ensure Compile + Infer

Run in the package directory:

```bash
gaia compile .
```

If a review sidecar exists, also run inference:

```bash
ls reviews/          # check for review sidecars
gaia infer .         # run if review exists
```

If compile or infer fails, stop and report the error.

## Step 2: Generate Skeleton

```bash
gaia render . --target obsidian
```

This produces `gaia-wiki/` containing:
- `_index.md` — master navigation with statistics
- `overview.md` — Mermaid reasoning graph
- `conclusions/{label}.md` — one page per exported claim / question
- `evidence/{label}.md` — one page per leaf premise
- `modules/{module}.md` — one page per module (non-exported claims inlined)
- `reasoning/{strategy}.md` — one page per complex strategy
- `meta/beliefs.md` — belief table (if infer was run)
- `meta/holes.md` — leaf premises summary
- `.obsidian/graph.json` — graph view color config

All pages have YAML frontmatter and wikilinks. The skeleton is browsable but thin.

## Step 3: Read Inputs

Read these files to prepare for narrative filling:

```bash
cat .gaia/ir.json                          # Full IR (knowledges, strategies, operators)
cat .gaia/reviews/*/beliefs.json           # BP results (if available)
cat .gaia/reviews/*/parameterization.json  # Review priors + strategy params
ls src/<package>/*.py                      # DSL source (claims, strategies, reasons)
ls artifacts/                              # Original paper, figures, data
```

Build a mental model of:
- The package's overall argument (what is it trying to establish?)
- The reasoning chains (which premises support which conclusions?)
- The evidence quality (where are beliefs strong vs weak?)
- The original source material (what context does the paper provide?)

## Step 4: Fill Narrative Per Page

For each page in `gaia-wiki/`, enrich the skeleton with narrative content. **Do NOT modify frontmatter or wikilinks** — only add prose sections.

### Claim pages (`conclusions/*.md`)

Add these sections after the existing skeleton content:

**Context** (2-3 paragraphs): Explain the claim in the context of the original work. Include relevant data, experimental conditions, and figures from `artifacts/`. Write for a domain expert who hasn't read the paper.

```markdown
## Context

The authors tested RFdiffusion-designed binders against five protein targets
of therapeutic interest...

> [!NOTE]
> Context expanded from Watson et al. 2023, Extended Data Fig. 5.
> See `artifacts/paper.pdf` pp. 8-10.
```

**Significance** (1 paragraph): Why this claim matters for the package's overall argument. How does it connect to the exported conclusions?

If `artifacts/` has relevant figures, embed them:
```markdown
![[figure-4-binder-results.png]]
```

### Module pages (`modules/*.md`)

Add at the top (after frontmatter, before Claims):

**Overview** (1-2 paragraphs): What this module covers and how it fits in the larger argument.

**Transition** (1-2 sentences): How this module connects to previous and next modules in the argument arc.

### Evidence pages (`evidence/*.md`)

Add:

**Source** (1 paragraph): Where this evidence comes from — specific experiment, dataset, observation, or literature reference. Cite from `artifacts/` if available.

### Strategy pages (`reasoning/*.md`)

Expand the existing Reasoning section:

**Explanation** (1-2 paragraphs): For each premise → conclusion link, explain WHY the premise supports the conclusion. Don't just list the premises — tell the reasoning story.

### Overview page (`overview.md`)

Add:

**Abstract** (1-2 paragraphs): Summarize the entire knowledge package. What question does it address, what does it conclude, and how confident is the reasoning?

### `_index.md`

Add after the existing navigation:

**Package Description** (2-3 sentences): Brief description from `pyproject.toml` or module docstrings.

## Narrative Guidelines

**Audience:** A domain expert who hasn't read the original source material but understands the field.

**Voice:** Scientific, precise, but readable. Third-person. Cite specific numbers from the paper.

**DO:**
- Ground claims in concrete data (numbers, experiments, comparisons)
- Cite figures from `artifacts/` with `![[filename]]` syntax
- Use Obsidian callouts for annotation:
  - `> [!NOTE]` — context expanded from source
  - `> [!WARNING]` — information unavailable or uncertain
  - `> [!REASONING]` — expanded reasoning explanation
- Reference other pages via wikilinks: `[[label]]`

**DO NOT:**
- Use Gaia jargon (noisy_and, abduction, factor graph, BP, NAND)
- Describe graph structure ("this claim derives from two premises via...")
- Modify frontmatter or existing wikilink sections
- Remove any skeleton content — only add

### Handling Missing Information

| Missing | Action | Annotation |
|---------|--------|------------|
| Terse claim content (< 20 words) | Expand from `artifacts/` | `> [!NOTE] Content expanded from source` |
| Strategy has no `reason` field | Reconstruct from premises + source | `> [!NOTE] Reasoning reconstructed from source` |
| No beliefs (infer not run) | Write structural description only | `> [!WARNING] Beliefs not available` |
| No `artifacts/` directory | Write from IR content only | `> [!WARNING] Original source not available` |

## Step 5: Cross-Reference Audit

After filling all pages, verify:

```bash
# Check for broken wikilinks
grep -roh '\[\[[^]]*\]\]' gaia-wiki/ | sort -u | while read link; do
  name=$(echo "$link" | sed 's/\[\[//;s/\]\]//')
  if ! find gaia-wiki -name "${name}.md" | grep -q .; then
    echo "BROKEN: $link"
  fi
done
```

Fix any broken wikilinks. Update `_index.md` statistics if page count changed.

## Step 6: Report

Summarize what was done:

```
Obsidian wiki generated at gaia-wiki/
- X pages total (Y conclusions, Z evidence, W modules)
- Narrative filled for N pages
- Figures embedded: M
- Broken wikilinks: 0
```

Suggest opening in Obsidian:
```
Open in Obsidian: File → Open Vault → select gaia-wiki/
Graph view will show the reasoning structure color-coded by node type.
```
