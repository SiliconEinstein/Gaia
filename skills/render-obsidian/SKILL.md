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

**Goal:** A reader who reads sections 01 through 06 in order should understand the paper's complete argument without ever opening the original paper. Each section is a self-contained chapter of a "textbook rewrite" of the paper.

1. **Title** — Rewrite skeleton title into a descriptive narrative title in user's language (e.g., "从第一性原理计算库仑赝势", "为什么 DFPT 能给出正确的声子耦合"). Keep number prefix.

2. **Overview** — 2-3 paragraphs telling the section's story:
   - What scientific question does this section answer?
   - Why is this question important for the overall argument?
   - What is the key insight or result?
   - How does it build on previous sections and enable the next?

3. **Per-section Mermaid** — Keep as-is.

4. **Claims list** — This is the heart of the section. For each claim (in topo order), write a **narrative paragraph** (not a bullet point) that:
   - Explains what this claim says in plain language
   - Gives the key quantitative result (numbers, equations)
   - Explains why this result matters for the section's argument
   - Transitions naturally to the next claim

   The claims should flow as a connected story. Example (bad vs good):

   **BAD** (isolated bullet points):
   ```
   ### [[adiabatic_approx|#02 绝热近似]]
   > 传统金属中 ωD/EF ~ 0.005。
   Prior: 0.95 → Belief: 0.71
   ```

   **GOOD** (narrative flow):
   ```
   ### [[adiabatic_approx|#02 绝热近似]]

   整个下折叠理论的基础是绝热近似——在传统金属中，Debye 频率
   与 Fermi 能之比 $\omega_D/E_F \sim 0.005$，声子的能标远小于
   电子的能标。这一巨大的能标分离使得 Migdal 定理成立：高阶
   电声顶角修正被压低至 $O(\omega_D/E_F)$，从而保证了 BSE
   积分核的可分离性（详见 [[downfolded_bse|#43 下折叠 BSE]]）。

   这一前提的 belief 从先验 0.95 下降到后验 0.71，反映了下折叠
   链上的不确定性积累——虽然绝热近似本身很可靠，但它作为多个
   推导步骤的共同前提，其不确定性被放大了。
   ```

   The good version tells a story: what the claim says → why it matters → what the belief change means.

#### Weak Points section

**Goal:** A reader should understand WHERE the argument is weakest, WHY it's weak, and WHAT could fix it. This is a critical assessment, not a data dump.

The skeleton provides a table of the 10 lowest-belief claims. Agent should rewrite into a structured analysis:

1. **Executive summary** (1 paragraph) — The single most important takeaway. What is the weakest link in the entire reasoning chain? If you had to bet on which claim will fail, which one and why?

2. **Structural analysis** — Group weak points by their position in the reasoning graph:
   - **Foundation weaknesses** — Are any leaf premises (holes) controversial? If a widely-accepted fact turns out to be wrong, what collapses?
   - **Bottleneck weaknesses** — Are there single claims that many conclusions depend on? A low-belief bottleneck is more dangerous than a low-belief leaf.
   - **Propagation effects** — Does the reasoning graph amplify uncertainty? (e.g., "the downfolded BSE has belief 0.33 not because it's intrinsically unreliable, but because it depends on cross-term suppression which has belief 0.50, and the uncertainty propagates through 3 derivation steps")

3. **For each major weak point** (top 3-5), write a full paragraph:
   - What the claim says and where it sits in the reasoning chain
   - WHY the belief is low — trace the reasoning graph backwards to find the root cause
   - What the reviewer's justification says about the uncertainty
   - What competing explanation or alternative approach exists
   - What specific evidence or experiment would resolve the uncertainty
   - What downstream conclusions would be affected if this claim fails

4. **Comparison with the paper's own assessment** — Does the paper acknowledge these weaknesses? Does the reasoning graph reveal weaknesses the paper doesn't discuss?

#### Open Questions section

**Goal:** A reader should know exactly what work remains to be done, prioritized by impact. This is a research roadmap derived from the reasoning graph.

The skeleton lists holes and questions. Agent should rewrite into:

1. **Overview** (1-2 paragraphs) — The big picture: what would make this knowledge package "complete"? What's the most impactful single improvement?

2. **Open questions from the paper** — If the IR has `type: question` nodes, explain each:
   - What the question asks
   - Why it matters for the overall argument
   - What the paper suggests (if anything) as an approach
   - What the reasoning graph says about its impact (which conclusions depend on it?)

3. **Evidence gaps** (grouped by theme):

   **Experimental gaps:**
   - What measurements are missing or imprecise?
   - Which claims rely on the weakest experimental evidence?
   - What experiments would most reduce uncertainty?

   **Computational gaps:**
   - What calculations are approximate that could be made exact?
   - What parameters have the largest error bars?
   - What computational advances would help?

   **Theoretical gaps:**
   - What derivations rely on uncontrolled approximations?
   - Where does the theory break down (validity limits)?
   - What extensions would broaden applicability?

4. **Impact analysis** — For each gap, trace forward through the reasoning graph:
   - If this hole were filled with higher confidence, which conclusions would improve?
   - Rank the holes by "information value": how much would filling this hole reduce overall uncertainty?

5. **Suggested next steps** — Prioritized list of 3-5 actionable research directions, each with:
   - What to do
   - Why it's high-impact (which conclusions it would strengthen)
   - Estimated difficulty/feasibility

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
