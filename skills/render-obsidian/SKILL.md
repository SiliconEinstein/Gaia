---
name: render-obsidian
description: "Use when user wants a browsable Obsidian wiki from a Gaia knowledge package — generates skeleton, rewrites all pages as rich knowledge documents from IR and original sources, audits cross-references."
---

# Render Obsidian Wiki

Generate a rich, browsable Obsidian vault (`gaia-wiki/`) from a Gaia knowledge package.

## Vault Architecture

```
gaia-wiki/
├── claims/                 One page per claim, numbered by topological order
│   ├── 01 - BCS Theory.md              (layer 0, leaf)
│   ├── ...
│   └── 59 - Tc Prediction.md ★         (highest layer, conclusion)
├── modules/                Chapter narrative, numbered by paper order
│   ├── 01 - Introduction.md
│   └── ...06 - Results.md
├── meta/                   beliefs table, holes list
├── _index.md               Master index with numbered claim table
├── overview.md             Simplified Mermaid graph
└── .obsidian/
```

- **Claims** = atomic content units. Numbered by topological order (small=leaves, large=conclusions). Each has full derivation/reasoning.
- **Modules** = reading chapters. Narrative organized by claim numbers, linking to claim pages. No full derivation duplication.
- **Wikilinks** use labels (`[[tc_al_predicted]]`). Filenames use titles. `aliases` in frontmatter bridges them.

## Pipeline

```
Step 1: gaia compile + gaia infer (if review exists)
Step 2: gaia render --target obsidian → skeleton
Step 3: Read inputs (IR, beliefs, artifacts/, DSL source, review sidecar)
Step 4: Rewrite every page
Step 5: Cross-reference audit
Step 6: Report
```

## Step 3: Read Inputs

```bash
cat .gaia/ir.json                          # Full IR
cat .gaia/reviews/*/beliefs.json           # BP results
cat .gaia/reviews/*/parameterization.json  # Priors + strategy params
cat src/<package>/*.py                     # DSL source
cat src/<package>/reviews/*.py             # Review sidecars (justifications!)
ls artifacts/                              # Original paper, figures
```

Read `artifacts/` cover-to-cover. Read review sidecar for `justification` fields — these explain WHY each prior was chosen.

## Step 4: Rewrite Every Page

**Core principle:** Faithful reproduction. The reader should understand the topic without the original source.

**Language:** Follow user's language. Frontmatter/wikilinks/Mermaid stay English.

### Claim pages (`claims/*.md`)

Self-contained articles. The `#XX` number shows position in reasoning chain.

**Section ordering:**

1. **Title**: Descriptive in user's language. Keep `#XX` prefix.
2. **Content**: Full explanation with all numbers, equations, conditions.
3. **Background**: Scientific context, problem, prior work, gap. Embed figures with `![[file]]` + italic caption.
4. **Derivation** (核心): Reproduce paper's full argument — all equations, step-by-step, approximations justified, appendix material included. Use `[[label|#XX label]]` for cross-references.
5. **Review**: Prior + justification from review sidecar. Posterior belief.
6. **Supports**: Downstream claims depending on this one.
7. **Significance**: Why it matters.
8. **Caveats**: Limitations, alternatives.

### Module pages (`modules/*.md`)

Narrative chapters linking to claim pages.

1. **Overview**: Scientific question, approach, key results (review paper style).
2. **Transition**: Connection to previous/next modules.
3. **Per-module Mermaid**: Keep as-is.
4. **Claims list**: For each claim, 2-3 sentence summary + `[[label|#XX title]]` link. Don't duplicate derivations.

### Overview, _index, meta

- **Overview**: Citation + abstract + Mermaid graph
- **_index**: Package description + statistics + Claim Index table + Reading Path
- **Meta**: Chinese introductions + tables

### Quality bar

**Faithful reproduction, not summarization.** Rewrite the paper into a wiki.

Every page: all numbers, all equations, all derivation steps, figure embeds with captions, cross-references with claim numbers.

### Figure embeds

Every `![[filename]]` MUST have italic caption:
```
![[8_0.jpg]]
*图 4：vDiagMC 计算的 μ_EF(r_s)。改编自 Cai et al.*
```

### DO NOT

- Leave skeleton English content
- Write thin summaries
- Use Gaia jargon (noisy_and, abduction, factor graph, BP)
- Modify frontmatter or wikilink targets
- Embed images without captions
- Duplicate full derivations in module pages

## Step 5: Cross-Reference Audit

Wikilinks use labels, resolved via aliases:
```bash
all=$(grep -rh "^aliases:" gaia-wiki/ --include="*.md" | sed 's/aliases: \[//;s/\]//')
echo "$all" $(find gaia-wiki -name "*.md" -exec basename {} .md \;) | tr ' ' '\n' | sort -u > /tmp/targets
grep -roh '\[\[[^]!]*\]\]' gaia-wiki/ --include="*.md" | sed 's/\[\[//;s/\]\]/;s/#.*//;s/|.*//' | sort -u | while read n; do grep -qx "$n" /tmp/targets || echo "BROKEN: [[$n]]"; done
```

## Step 6: Report

```
Obsidian wiki: gaia-wiki/
- X claim pages (01-XX), Y module pages (01-YY)
- All rewritten in [language]
- Figures: M, Broken links: 0
```
