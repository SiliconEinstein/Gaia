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

Rewrite into a complete article about this claim:

1. **Title**: Keep or translate the `# heading`
2. **Content**: Replace the terse blockquote with 2-3 paragraphs fully explaining the claim — what it states, what evidence supports it, what method produced it. Include specific numbers, equations, experimental conditions.
3. **Derivation**: Rewrite in prose. Don't just list premises — explain the logical chain: WHY each premise supports this conclusion. Keep wikilinks but wrap them in explanatory sentences.
4. **Supports**: Rewrite as prose — what downstream conclusions depend on this claim and why.
5. **Context**: Add 2-3 paragraphs explaining the claim's scientific context from `artifacts/`. Include figures with `![[filename]]`.
6. **Significance**: 1-2 paragraphs on why this matters for the overall argument.
7. **Caveats**: Note limitations, alternative explanations, sources of uncertainty.

Target: 500-800 words per conclusion page.

#### Evidence pages (`evidence/*.md`)

Rewrite into a source documentation page:

1. **Content**: Expand the terse blockquote into a full description of the evidence.
2. **Source**: Where does this evidence come from? Specific experiment, dataset, calculation, or literature. Method, precision, known limitations.
3. **Supports**: Which conclusions depend on this evidence and why.
4. **Figures**: Embed relevant figures from `artifacts/images/`.

Target: 200-400 words per evidence page.

#### Module pages (`modules/*.md`)

Rewrite into a chapter-level overview:

1. **Overview**: 2-3 paragraphs — what scientific question this module addresses, what approach is taken, key results. Write as a review paper section introduction.
2. **Transition**: How this module connects to adjacent modules.
3. **Claims section**: For each claim listed:
   - Exported claims (with `[[link]] ★`): expand the one-line description into 2-3 sentences.
   - Inlined claims: rewrite the content and derivation info into readable prose. Don't just say "Derived via X from Y" — explain the reasoning.

Target: 400-800 words per module page.

#### Strategy pages (`reasoning/*.md`)

Rewrite into a reasoning explanation:

1. **Overview**: What type of reasoning is this and what does it establish?
2. **Premises → Conclusion**: For each premise, explain WHY it supports the conclusion. Include the mathematical or physical argument.
3. **Strength assessment**: How strong is this reasoning? What could weaken it?

Target: 300-500 words per strategy page.

#### Overview page (`overview.md`)

1. **Citation**: Add proper bibliographic reference to original work.
2. **Abstract**: 3-4 paragraphs summarizing the entire package — central question, methodology, key quantitative results, limitations.
3. **Reasoning graph**: Keep the Mermaid diagram as-is.

Target: 300-500 words.

#### `_index.md`

Add a package description (3-5 sentences) with the most striking quantitative results. Keep all statistics tables and navigation as-is.

#### Meta pages (`meta/*.md`)

- `beliefs.md`: Add a brief introduction explaining what the table shows.
- `holes.md`: Add a brief introduction explaining what leaf premises are and why they matter.

### Quality bar

**Every page must include:**
- Specific numerical values (with units, error bars where available)
- Key equations in LaTeX where they clarify the argument
- Cross-references via wikilinks to related pages
- At least one figure embed from `artifacts/images/` if relevant figures exist

**BAD — thin rewrite:**
```
## 背景
铝的 r_s = 2.07，预测 T_c = 0.96 K，接近实验值 1.2 K。
```

**GOOD — rich rewrite:**
```
## 背景

铝是超导理论的基准测试材料。Wigner-Seitz 半径 $r_s = 2.07$，
带质量 $m_b = 1.05$，处于弱耦合区间。声子吸引（$\lambda = 0.44$，
来自 DFPT 计算，$\omega_{\log} = 320$ K）与 Coulomb 排斥
（$\mu^* = 0.13$，来自 [[mu_vdiagmc_values]] 在 $r_s = 2.07$
处的值经 BTS 重正化）之间的竞争仅留下很小的净配对相互作用。

唯象方法预测 $T_c = 1.9$ K，比实验值 1.2 K 高估 58%——根本
原因是传统取值 $\mu^* \approx 0.10$ 低估了 Coulomb 排斥。
第一性原理值 $\mu^* = 0.13$ 恰好增大了足够的排斥，将 $T_c$
降低到 0.96 K，偏差在 20% 以内。

![[8_0.jpg]]
*图 4：vDiagMC 计算的 $\mu_{E_F}(r_s)$（圆圈带误差棒），
与静态 RPA（虚线）、动态 RPA（点线）和 Morel-Anderson 常数
（点划线）的对比。改编自 Cai et al., arXiv:2512.19382。*
```

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
