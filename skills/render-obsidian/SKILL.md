---
name: render-obsidian
description: "Use when user wants a browsable Obsidian wiki from a Gaia knowledge package — generates skeleton, rewrites all pages as rich knowledge documents, audits cross-references."
---

# Render Obsidian Wiki

Generate a rich Obsidian vault (`gaia-wiki/`) from a Gaia knowledge package.

## Vault Architecture

```
gaia-wiki/
├── claims/
│   ├── holes/              Leaf premises — reasoning chain endpoints
│   ├── intermediate/       Derived but not exported
│   ├── conclusions/        Exported claims ★ + questions
│   └── context/            Settings, background, structural
├── sections/               Narrative chapters (DSL module order)
│   ├── 01 - Introduction.md
│   ├── ...
│   ├── 07 - Weak Points.md
│   └── 08 - Open Questions.md
├── meta/                   beliefs table, holes list
├── _index.md               Claim Index + Sections + Reading Path
├── overview.md             Simplified Mermaid
└── .obsidian/
```

- **Claims** = atomic content units, numbered by topological order. Each carries full derivation + review justification.
- **Sections** = narrative chapters following the paper's arc. Agent rewrites titles. Last two sections are Weak Points and Open Questions.
- **Wikilinks** use labels, filenames use titles, `aliases` bridges them.

## Pipeline

```
Step 1: gaia compile + gaia infer
Step 2: gaia render --target obsidian → skeleton
Step 3: Read inputs (IR, beliefs, parameterization, DSL, review sidecar, artifacts/)
Step 4: Rewrite every page
Step 5: Cross-reference audit
```

## Step 3: Read Inputs

```bash
cat .gaia/ir.json
cat .gaia/reviews/*/beliefs.json
cat .gaia/reviews/*/parameterization.json  # includes justification per prior
cat src/<package>/*.py
cat src/<package>/reviews/*.py             # review sidecar source
ls artifacts/
```

Read `artifacts/` cover-to-cover before writing any page.

## Step 4: Rewrite Every Page

**Core principle:** Faithful reproduction. Each page replaces reading the paper for its topic.

**Language:** Follow user's preference. Frontmatter/wikilinks/Mermaid stay English.

---

### Claim pages (`claims/{holes,intermediate,conclusions,context}/*.md`)

Each claim is a self-contained article. `#XX` number = position in reasoning chain.

**Section ordering:**

1. **Title** — Descriptive in user's language. Keep `#XX` prefix.
2. **Content** — Full explanation, all numbers/equations/conditions.
3. **Background** — Scientific context from `artifacts/`. What problem? Prior work? Gap? Embed figures with `![[file]]` + italic caption.
4. **Derivation** — Reproduce the paper's FULL argument:
   - All equations with step-by-step explanation
   - Physical reasoning behind each step
   - Why each approximation is justified
   - Numerical validations from the paper
   - Appendix material
   - Use `[[label|#XX label]]` for cross-references
5. **Review** — From `parameterization.json`:
   - `**Prior**: 0.95`
   - `**Justification**: omega_D/E_F ~ 0.005; Migdal theorem validated.`
   - `**Belief**: 0.71`
6. **Supports** — Downstream claims.
7. **Significance** — Why it matters. What breaks if wrong?
8. **Caveats** — Limitations, alternative explanations, uncertainties.

**Depth by claim type:**

| Type | Depth |
|------|-------|
| **Conclusions** (★) | Most detailed — full derivation chain, multiple paragraphs per section |
| **Holes** | Focus on source provenance — where does this evidence come from? Method, precision, limitations |
| **Intermediate** | Full derivation of this step in the chain |
| **Context** | Brief — what it establishes and why it's assumed |

---

### Section pages (`sections/*.md`)

Sections are **narrative chapters** that tell the paper's story. Claims within each section are sorted by topological order (evidence → derivation → conclusion).

1. **Title** — Rewrite skeleton title into a descriptive narrative title in user's language (e.g., "Computing μ* from First Principles", "Why DFPT Gets the Phonon Coupling Right"). Keep number prefix.
2. **Overview** — 2-3 paragraphs telling the section's story: what scientific question, what approach, what key insight, how it connects to the overall argument. Write as a review paper section.
3. **Per-section Mermaid** — Keep as-is.
4. **Claims list** — For each claim, write 2-3 sentences of narrative summary with key numbers, linking to the full claim page. Don't duplicate derivations. The narrative should flow — each claim summary connects to the next, telling a coherent story.

#### Weak Points section

The skeleton lists the 10 lowest-belief claims. Agent should rewrite into:

1. **Overview** — What are the weakest links in the reasoning and why they matter.
2. **For each weak claim** — Don't just cite the low belief. Explain:
   - WHY the belief is low (what the BP propagation reveals about structural weakness)
   - What assumption is most vulnerable
   - What evidence would strengthen it
   - What competing explanation hasn't been ruled out
3. **Systemic risks** — Are there patterns? (e.g., "all downfolding claims have low belief because they depend on cross-term suppression at 1%")

#### Open Questions section

The skeleton lists holes and questions. Agent should rewrite into:

1. **Overview** — What are the most important gaps and future directions.
2. **For each category of hole** — Group by theme (experimental, computational, theoretical). For each:
   - What additional evidence would help
   - Which conclusions would be most affected
   - Feasibility of obtaining this evidence
3. **Future extensions** — What the paper suggests as next steps. What the reasoning graph suggests as most impactful improvements.

---

### Overview, _index, meta

- **Overview** — Citation + abstract + simplified Mermaid graph.
- **_index** — Package description + statistics + Claim Index table (with numbers) + Sections table + Reading Path.
- **Meta** — `beliefs.md`: intro + full belief table. `holes.md`: intro + leaf premises table.

---

### Quality standard

**Faithful reproduction, not summarization.** If the paper devotes 3 pages to a derivation, reproduce them in readable form. Include appendix material.

**Every page must include:**
- All relevant numerical values (units, error bars)
- Key equations with step-by-step explanation
- Derivation steps from the paper (including appendix)
- Figure embeds with italic captions
- Cross-references with claim numbers `[[label|#XX label]]`
- Review justification where available

**Figure embeds** — every `![[file]]` must have italic caption:
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
- Duplicate full derivations in section pages
- List weak points without explaining WHY they're weak
