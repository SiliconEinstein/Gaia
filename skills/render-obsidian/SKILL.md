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

- **Claims** = atomic content units, numbered by topological order. Each carries full derivation + prior justification.
- **Sections** = narrative chapters following the paper's arc. Agent rewrites titles. Last two sections are Weak Points and Open Questions.
- **Wikilinks** use labels, filenames use titles, `aliases` bridges them.

## Pipeline

```
Step 1: gaia compile + gaia infer
Step 2: gaia render --target obsidian → skeleton
Step 3: Read inputs (IR, beliefs, DSL, artifacts/)
Step 4: Rewrite every page
Step 5: Cross-reference audit
```

## Step 3: Read Inputs

```bash
cat .gaia/ir.json
cat .gaia/beliefs.json
cat src/<package>/*.py
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
5. **Review** — From `beliefs.json` and `priors.py`:
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

**Page structure (from top to bottom):**

1. **Title** — Descriptive narrative title in user's language. Keep number prefix.

2. **Overview** (10%) — 2-3 paragraphs setting up the section's question, approach, and key result.

3. **Per-section Mermaid** — Keep as-is.

4. **Claims narrative** (70% of the page — THIS IS THE MAIN BODY) — For EVERY claim in topo order, write a `###` heading + 1-3 paragraphs. This is NOT optional. Every claim listed in the skeleton MUST appear with its narrative.

   **CRITICAL: This section is the bulk of the page. Do NOT skip it.** The skeleton has `### [[label|#XX title]]` entries — the agent must expand EACH ONE into a full narrative paragraph.

   For each claim:
   - `### [[label|#XX title]]` heading (keep the wikilink)
   - What this claim says in plain language, with key numbers and equations
   - Why this result matters for the section's argument
   - How it connects to the previous and next claims (logical flow)
   - If exported (★): **highlight as a key conclusion** with a callout block
   - Belief analysis: what does the prior→belief change reveal?

   **Exported conclusions should be highlighted:**
   ```
   ### [[downfolded_bse|#43 下折叠 BSE]] ★

   > [!IMPORTANT] 核心结论
   > 完整的动量-频率 BSE 可以严格化简为仅依赖频率的一维积分方程，
   > 误差仅 0.2%。

   这是本章最重要的结果...
   ```

5. **Chapter summary** (10%) — 本章建立了什么，为下一章准备了什么。

**Full section page example (showing the required structure):**

```markdown
# 03 - 从微观推导下折叠 Bethe-Salpeter 方程

## 概述

(2-3 paragraphs: question, approach, key result)

(Mermaid graph)

## 推理链

### [[pair_propagator_decomposition|#18 配对传播子分解]]

配对传播子 $GG$ 可以精确分解为低能相干部分 $\Pi_{\mathrm{BCS}}$
和高能非相干余项 $\phi$。这不是一个近似——而是一个数学恒等式。
相干部分携带 Cooper 对数 $\ln(\omega_c/T)$，定义了低能配对通道。

论文选择在双电子通道（而非传统的粒子-空穴通道）引入能量尺度
分离，这是一个关键创新——传统方案会导致低能区域库仑相互作用
失去屏蔽。这一选择为下面的交叉项压制论证奠定了基础。

### [[cross_term_suppressed|#19 交叉项压制]]

有了配对传播子分解，关键问题是：库仑和声子通道的交叉项是否
会破坏可分离性？论文利用等离子体极子模型给出了严格的上界估计：
交叉项被压制在 $O(\omega_c^2/\omega_p^2) \leq 1\%$。

这是整条推理链中最脆弱的一环——belief 仅 0.50，反映了 1% 这个
边界条件的不确定性。如果交叉项实际上更大，整个下折叠理论的
精度保证就会失效。

### [[downfolded_bse|#43 下折叠 BSE]] ★

> [!IMPORTANT] 核心结论
> 频率-only 下折叠 BSE：$\Lambda_\omega = \eta_\omega + \pi T
> \sum (\lambda - \mu_{\omega_c}) z^{ph}_{\omega'}/|\omega'| \Lambda_{\omega'}$

结合配对传播子分解和交叉项压制，完整 BSE 化简为仅含频率的
一维积分方程。$\mu^*$ 和 $\lambda$ 获得了精确的微观定义...

(... more claims ...)

## 本章小结

本章从微观出发严格推导了下折叠 BSE，为 $\mu^*$ 和 $\lambda$
提供了精确定义。这为第四章通过 vDiagMC 计算 $\mu^*$ 和第五章
验证 DFPT $\lambda$ 的可靠性奠定了理论基础。
```

**DO NOT** write a section page with only the overview and Mermaid — the claims narrative is the main content that readers come here to read.

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
