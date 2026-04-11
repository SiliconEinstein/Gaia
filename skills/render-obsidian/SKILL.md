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

**Core principle:** Each wiki page is a self-contained knowledge document. After reading a page, the reader should understand the claim, its evidence, and its role in the argument **without needing to read the original source**. The wiki replaces reading the paper, not summarizes it.

### Quality standard: thin vs rich

**BAD (thin)** — the agent's default tendency:
```markdown
## Context
Aluminum has r_s = 2.07 and the ab initio prediction is 0.96 K,
close to the experimental value of 1.2 K.
```

**GOOD (rich)** — what the reader actually needs:
```markdown
## Context
Aluminum is the benchmark test for any superconductivity theory. With
Wigner-Seitz radius $r_s = 2.07$ and band mass $m_b = 1.05$, it sits
in the weak-coupling regime where the competition between phonon
attraction ($\lambda = 0.44$ from DFPT, using $\omega_{\log} = 320$ K)
and Coulomb repulsion ($\mu^* = 0.13$ from vDiagMC at $r_s = 2.07$
with BTS renormalization) leaves a small net pairing interaction.

The phenomenological prediction of $T_c = 1.9$ K overshoots the
experimental $T_c = 1.2$ K by 58%, primarily because the conventional
$\mu^* \approx 0.10$ underestimates Coulomb repulsion. The ab initio
value $\mu^* = 0.13$ increases the repulsion just enough to bring
$T_c$ down to 0.96 K — within 20% of experiment. The remaining
discrepancy likely reflects the UEG-to-material mapping approximation
and band structure effects beyond the free-electron model.

![[8_0.jpg]]
*Fig. 4: Dimensionless bare Coulomb pseudopotential $\mu_{E_F}(r_s)$
from vDiagMC (circles with error bars), compared with static RPA
(dashed), dynamic RPA (dotted), and Morel-Anderson constant (dash-dot).
Adapted from Cai et al., arXiv:2512.19382.*
```

The difference: the rich version includes all the numbers ($r_s$, $m_b$, $\lambda$, $\omega_{\log}$, $\mu^*$), explains the mechanism (why the prediction differs from phenomenology), embeds figures, and gives the reader enough context to evaluate the claim independently.

### Claim pages (`conclusions/*.md`)

Add after the existing skeleton content:

**Context** (3-5 paragraphs, ~300-500 words):
- **Paragraph 1**: What is this claim about? Set the scientific context — what question is being answered, what method is used, what physical regime.
- **Paragraph 2**: The specific data and results. Include ALL relevant numbers: material parameters, computed values with error bars, comparisons with experiment and prior theory. Reproduce key equations if they clarify the argument.
- **Paragraph 3**: How the result was obtained — what computation, what approximations, what input data. The reader should be able to trace the derivation.
- **Paragraph 4 (if applicable)**: Caveats, limitations, comparison with alternative approaches.
- Embed relevant figures from `artifacts/images/` with captions and attribution.

**Significance** (1-2 paragraphs): Why this claim matters for the package's overall argument. What breaks if this claim is wrong? What does it enable downstream?

```markdown
> [!NOTE]
> Context expanded from [Author et al.], Section X, pp. Y-Z.
> See `artifacts/paper.md` for full details.
```

### Module pages (`modules/*.md`)

Add at the top (after frontmatter, before Claims):

**Overview** (2-3 paragraphs, ~200-400 words): What scientific question this module addresses, what approach is taken, and what the key results are. Write as you would a section introduction in a review paper — the reader should understand the module's contribution after reading just the overview.

**Transition** (2-3 sentences): How this module builds on the previous one and what it enables for the next. Name the specific concepts that flow between modules.

### Evidence pages (`evidence/*.md`)

**Source** (1-2 paragraphs): Where this evidence comes from — specific experiment, dataset, calculation, or literature reference. Include: who measured/computed it, what method, what precision, and any known limitations. Cite from `artifacts/` if available.

### Strategy pages (`reasoning/*.md`)

Expand the Reasoning section into **Explanation** (2-3 paragraphs): For each premise → conclusion link, explain the scientific logic of WHY the premise supports the conclusion. Include the mathematical or physical argument, not just "A implies B." The reader should understand the chain of reasoning as clearly as if they read the relevant section of the paper.

### Overview page (`overview.md`)

**Abstract** (2-3 paragraphs, ~200-300 words): A self-contained summary of the entire knowledge package. What is the central question? What new methodology is introduced? What are the key quantitative results? What are the limitations? A domain expert should be able to decide whether to explore further based on this abstract alone.

### `_index.md`

**Package Description** (3-5 sentences): What this package formalizes, what the source material is, and what the main findings are. Include the most striking quantitative result.

## Narrative Guidelines

**Audience:** A domain expert who hasn't read the original source material but understands the field. They should be able to evaluate the claims based solely on the wiki pages.

**Voice:** Scientific, precise, but readable. Third-person. Write as you would for a review article or an extended encyclopedia entry.

**Content depth:** Every page should include:
- Specific numerical values (with units and error bars where available)
- Key equations (in LaTeX) where they clarify the argument
- Comparison with alternative approaches or prior results
- Figure embeds from `artifacts/images/` with descriptive captions

**DO:**
- Read `artifacts/` thoroughly — find the section corresponding to each claim and extract concrete details
- Ground every claim in specific data (not "good agreement" but "0.874 K vs 0.875 K, 0.1% error")
- Embed figures with `![[filename]]` and write informative captions
- Cross-reference other pages via wikilinks: `[[label]]`
- Use Obsidian callouts: `> [!NOTE]` for source citations, `> [!WARNING]` for caveats

**DO NOT:**
- Write thin summaries that could apply to any paper in the field
- Use Gaia jargon (noisy_and, abduction, factor graph, BP, NAND)
- Describe graph structure ("this claim derives from two premises via...")
- Modify frontmatter or existing wikilink sections
- Remove any skeleton content — only add
- Leave a page without at least one specific number or equation

### Handling Missing Information

| Missing | Action | Annotation |
|---------|--------|------------|
| Terse claim content (< 20 words) | Expand from `artifacts/` — read the relevant section and write a full explanation | `> [!NOTE] Content expanded from source` |
| Strategy has no `reason` field | Reconstruct the scientific argument from premises + source material | `> [!NOTE] Reasoning reconstructed from source` |
| No beliefs (infer not run) | Write structural description only | `> [!WARNING] Beliefs not available — run gaia infer` |
| No `artifacts/` directory | Write from IR content only, note the gap prominently | `> [!WARNING] Original source not available — narrative is based on IR content only` |

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
