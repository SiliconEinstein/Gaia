---
name: render-obsidian
description: "Use when user wants a browsable Obsidian wiki from a Gaia knowledge package — generates skeleton, rewrites all pages as rich knowledge documents from IR and original sources, audits cross-references."
---

# Render Obsidian Wiki

Generate a rich, browsable Obsidian vault (`gaia-wiki/`) from a Gaia knowledge package. The agent drives the full pipeline: skeleton generation, full rewrite into human-readable knowledge documents, and cross-reference audit.

## Full Pipeline

```
/gaia:render-obsidian
  ↓
Step 1: gaia compile + gaia infer (if review exists)
Step 2: gaia render --target obsidian → gaia-wiki/ skeleton
Step 3: Read inputs (IR, beliefs, artifacts/, DSL source)
Step 4: Rewrite every page as a complete knowledge document
Step 5: Cross-reference audit
Step 6: Report
```

## Step 1: Ensure Compile + Infer

```bash
gaia compile .
ls reviews/ && gaia infer .   # run inference if review exists
```

## Step 2: Generate Skeleton

```bash
gaia render . --target obsidian
```

This produces `gaia-wiki/` with YAML frontmatter, wikilinks, and Mermaid graphs on every page. The skeleton provides **structure only** — all prose content will be rewritten by the agent.

## Step 3: Read Inputs

Read thoroughly before writing:

```bash
cat .gaia/ir.json                          # Full IR
cat .gaia/reviews/*/beliefs.json           # BP results
cat .gaia/reviews/*/parameterization.json  # Priors + strategy params
cat src/<package>/*.py                     # DSL source (claims, reasons, strategies)
ls artifacts/                              # Original paper, figures, data
```

Read the original source material in `artifacts/` cover-to-cover. The agent must understand the paper's argument, data, and figures before writing any page.

## Step 4: Rewrite Every Page

**Core principle:** The skeleton is scaffolding, not content. The agent rewrites every page into a complete, self-contained knowledge document. After reading a page, the reader should understand the topic **without needing the original source**.

**Language:** Follow the user's language. If the user speaks Chinese, write all prose in Chinese. Frontmatter keys, wikilinks `[[label]]`, and Mermaid diagrams stay in English (they are structural identifiers).

### What to preserve vs rewrite

| Element | Action |
|---------|--------|
| YAML frontmatter | **Preserve exactly** — never modify |
| Wikilinks `[[label]]` | **Preserve exactly** — never change targets |
| Mermaid diagrams | **Preserve exactly** |
| `.obsidian/graph.json` | **Preserve exactly** |
| Section headings (`## Derivation`, etc.) | **Translate** to user's language |
| Claim content blockquotes (`> ...`) | **Rewrite** — expand terse claims into full explanations |
| `> [!REASONING]` callouts | **Rewrite** — translate and expand the reasoning |
| Premise/conclusion lists | **Rewrite** — keep wikilinks but add explanatory text |
| Everything else | **Write from scratch** |

### Per-page rewrite guide

#### Conclusion pages (`conclusions/*.md`)

Rewrite into a complete article about this claim.

**Completeness standard:** The page is a faithful, readable reproduction of everything the original paper says about this topic — including appendix material. Don't summarize or compress; rewrite for readability while preserving all derivations, equations, data, and arguments. If the paper devotes 3 pages to the derivation, the wiki page should reproduce those 3 pages worth of content in a more readable form.

**Section ordering (top to bottom):**

1. **Title**: Translate the `# heading`
2. **Content**: Replace the terse blockquote with a full explanation of the claim. Include ALL relevant numbers, equations, experimental conditions.
3. **Background** (新增, 放在推导之前): The complete scientific context for this claim. What problem does it address? What is known from prior work? What gap exists? Embed relevant figures from `artifacts/images/`. This section sets up the reader to understand the derivation that follows.
4. **Derivation** (核心, 最详尽的部分): Reproduce the paper's full argument for this claim — not a summary but a readable rewrite of the original derivation. Include:
   - All key equations with explanation of each step
   - Physical reasoning behind each mathematical step
   - Approximations made and why they are justified
   - Numerical validations cited in the paper
   - Appendix material that supports this derivation
   - Keep wikilinks to premises but embed them in explanatory prose
5. **Supports**: What downstream conclusions depend on this claim.
6. **Significance**: Why this matters. What breaks if wrong?
7. **Caveats**: Limitations, alternative explanations, uncertainty sources.

#### Evidence pages (`evidence/*.md`)

Rewrite into a complete source documentation page. Evidence pages are leaf nodes — they represent facts the paper takes as given or demonstrates directly.

1. **Content**: Full statement of the evidence with all quantitative details, equations, and conditions.
2. **Background**: Scientific context — why this evidence matters, what it establishes, how it was obtained. Reproduce the paper's full discussion of this point including any appendix material.
3. **Source**: Experimental method, measurement conditions, precision, error bars, known limitations. Embed relevant figures and data tables from the paper.
4. **Supports**: Which conclusions depend on this evidence — explain the logical connection, not just list names.

#### Module pages (`modules/*.md`)

Rewrite into a comprehensive chapter that mirrors the corresponding section of the paper.

1. **Overview**: What scientific question this module addresses, what approach is taken, and the key results. Write as a section of a review paper.
2. **Transition**: How this module builds on previous modules and enables subsequent ones.
3. **Claims section**: For each claim, reproduce the paper's full treatment:
   - Exported claims: substantive summary with all key numbers, equations, and the reasoning chain.
   - Inlined claims: rewrite the paper's content for this claim in full — equations, derivations, data, physical reasoning. Don't compress a 2-paragraph paper discussion into one sentence.

#### Strategy pages (`reasoning/*.md`)

Rewrite into a complete reasoning explanation that reproduces the paper's argument in full:

1. **Overview**: What type of reasoning, what it establishes, and in which section of the paper.
2. **Premises → Conclusion**: Reproduce the paper's complete argument — all equations, derivation steps, physical reasoning, and numerical evidence. This is not a summary but a readable rewrite of the original proof/argument.
3. **Strength assessment**: How strong is this reasoning? What assumptions does it depend on? What could weaken it?

#### Overview page (`overview.md`)

1. **Citation**: Proper bibliographic reference to original work.
2. **Abstract**: A comprehensive summary of the entire package — central question, methodology, key quantitative results, limitations. The reader should be able to decide whether to explore further.
3. **Reasoning graph**: Keep the Mermaid diagram as-is.

Target: 300-500 words.

#### `_index.md`

Add a package description (3-5 sentences) with the most striking quantitative results. Keep all statistics tables and navigation as-is.

#### Meta pages (`meta/*.md`)

- `beliefs.md`: Add a brief introduction explaining what the table shows.
- `holes.md`: Add a brief introduction explaining what leaf premises are and why they matter.

### Quality bar

**The standard is faithful reproduction, not summarization.** The wiki page should contain the same depth as the paper's treatment of the topic. If the paper devotes 2 pages to a derivation, reproduce those 2 pages in readable form — don't compress to 2 sentences. Appendix material that supports the topic should be included.

**Think of it as:** rewriting the paper into a wiki, not summarizing it into a wiki.

**Every page must include:**
- ALL relevant numerical values from the original source (with units, error bars)
- ALL key equations with step-by-step explanation
- ALL derivation steps the paper provides (including appendix material)
- Cross-references via wikilinks to related pages
- Figure embeds from `artifacts/images/` for every figure relevant to the topic

**BAD — derivation as summary:**
```
## 推导

将第一性原理工作流应用于铝（[[ab_initio_workflow]]），
代入材料参数，得到 T_c = 0.96 K。
```

**GOOD — derivation reproduces the paper's argument:**
```
## 推导

铝的超导转变温度由下折叠 Eliashberg 方程（[[downfolded_bse]]）
结合第一性原理输入参数预测。

**库仑赝势的确定：** 铝的 Wigner-Seitz 半径 $r_s = 2.07$，
带质量 $m_b = 1.05$。从 vDiagMC 参数化
（[[mu_vdiagmc_values]]）查表得 $\mu_{E_F}(2.07) = 0.56$。
通过 BTS 重正化关系

$$\mu^*(\omega_D) = \frac{\mu_{E_F}}{1 + \mu_{E_F} \ln(E_F/\omega_D)}$$

取 $E_F = 11.7$ eV，$\omega_D = 36$ meV（对应 Debye 温度
$\Theta_D = 428$ K），对数因子 $\ln(E_F/\omega_D) = 5.78$，
得到 $\mu^* = 0.56/(1+0.56 \times 5.78) = 0.13$。

**电声耦合：** DFPT 计算（[[dfpt_reliable_for_simple_metals]]）
给出 $\lambda = 0.44$，$\omega_{\log} = 320$ K。Allen-Dynes
公式的有效耦合为 $g = \lambda - \mu^*(1+0.62\lambda) =
0.44 - 0.13 \times 1.27 = 0.275$。

**$T_c$ 求解：** 将 $\mu^* = 0.13$, $\lambda = 0.44$,
$\omega_{\log} = 320$ K 代入 PCF 外推得到
$T_c^{\text{EFT}} = 0.96$ K，与实验值 $T_c^{\text{exp}} = 1.2$ K
偏差 20%。相比之下，唯象取值 $\mu^* \approx 0.10$ 给出
$T_c = 1.9$ K，偏差 58%。

![[14_0.jpg]]
*图 6：铝的 $T_c$ 随压力变化。实心圆为第一性原理预测，
空心圆为实验数据。改编自 Cai et al., arXiv:2512.19382。*
```

The good version reproduces the actual calculation steps, intermediate values, and equations — the reader can follow the derivation without opening the paper.

### DO NOT

- Leave any page with only skeleton English content
- Write thin summaries — every page should be a substantive knowledge document
- Use Gaia jargon (noisy_and, abduction, factor graph, BP, NAND)
- Describe graph structure ("this claim derives from two premises via...")
- Modify frontmatter or wikilink targets
- Skip evidence pages — they are important for completeness

### Handling missing information

| Missing | Action | Annotation |
|---------|--------|------------|
| Terse claim (< 20 words) | Read `artifacts/`, find relevant section, write full explanation | `> [!NOTE] 内容根据原文扩展` |
| No `reason` in strategy | Reconstruct from premises + source | `> [!NOTE] 推理根据原文重构` |
| No beliefs | Write structural description, note gap | `> [!WARNING] 未运行推断` |
| No `artifacts/` | Write from IR only, note prominently | `> [!WARNING] 原始文献不可用` |

## Step 5: Cross-Reference Audit

```bash
grep -roh '\[\[[^]]*\]\]' gaia-wiki/ | sort -u | while read link; do
  name=$(echo "$link" | sed 's/\[\[//;s/\]\]//' | sed 's/#.*//' | sed 's/|.*//')
  if ! find gaia-wiki -name "${name}.md" | grep -q .; then
    echo "BROKEN: $link"
  fi
done
```

## Step 6: Report

```
Obsidian wiki: gaia-wiki/
- X pages total (Y conclusions, Z evidence, W modules)
- All pages rewritten in [language]
- Figures embedded: M
- Broken wikilinks: 0

Open in Obsidian: File → Open Vault → select gaia-wiki/
```
