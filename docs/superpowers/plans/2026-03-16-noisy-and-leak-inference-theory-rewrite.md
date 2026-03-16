# Inference-Theory.md Rewrite Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `docs/foundations/theory/inference-theory.md` into a **v2.0 target-design** theory reference: lead with Jaynes first principles, introduce the noisy-AND + leak unified factor model, remove gate semantics for contradiction/equivalence at the theory level, and relocate BP algorithm details to a later section.

**Architecture:** Full document restructure from "BP basics → lattice → edge types" to "Jaynes first principles → unified factor model → lattice → factor types → BP algorithm". The document remains a single Markdown file. Content is a mix of new theoretical sections (§1, §2) and relocated/adapted existing sections (§3, §5). Because `bp-on-graph-ir.md` remains the current runtime/BP reference until a follow-up PR lands, this rewrite must explicitly present itself as target theory rather than already-shipped runtime semantics.

**Tech Stack:** Markdown, ruff (for any format checks), git

**Spec:** `docs/superpowers/specs/2026-03-16-noisy-and-leak-unified-factor-design.md`

---

## Chunk 1: Document scaffold and §1 Jaynes first principles

### Task 1: Create document scaffold with all section headers

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md`

This task replaces the entire file with the new structure. All sections start as placeholders (with `TODO` markers) so the document shape is established before content is filled in.

- [ ] **Step 1: Write scaffold**

Replace the full content of `docs/foundations/theory/inference-theory.md` with:

```markdown
# 推理引擎理论

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-16 |
| 关联文档 | [theoretical-foundation.md](theoretical-foundation.md) — Jaynes 纲领与 Gaia 定位, [../bp-on-graph-ir.md](../bp-on-graph-ir.md) — BP 在 Graph IR 上的运行 |

---

本文档是 Gaia 推理引擎的完整理论参考。组织顺序为：先从 Jaynes 第一性原理推导设计约束（§1），再给出满足这些约束的统一势函数模型（§2），然后分析推理方向的格论性质（§3），定义五种 factor 类型（§4），最后描述信念传播算法的计算细节（§5）。

关于 Jaynes 的认识论纲领和 Gaia 的整体定位，参见 [theoretical-foundation.md](theoretical-foundation.md)。

---

## 1. Jaynes 第一性原理

TODO

## 2. 统一势函数模型

TODO

## 3. 蕴含格中的 Abstraction 与 Induction

TODO

## 4. 五种 Factor 类型

TODO

## 5. 信念传播算法

TODO

## 6. 已知局限与演进方向

TODO

## 7. 逻辑编程技术启发

TODO

## 附录 A：术语对照

TODO

## 附录 B：与相关系统的概率机制对比

TODO
```

- [ ] **Step 2: Commit scaffold**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: scaffold restructured inference-theory.md (v2.0)"
```

---

### Task 2: Write §1 Jaynes 第一性原理

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace `## 1.` TODO block

§1 has three subsections. This is entirely new content derived from the design spec's theoretical analysis.

- [ ] **Step 1: Write §1.1 Cox 定理与三条规则**

Replace the `## 1.` TODO with the full §1. Start with §1.1:

```markdown
## 1. Jaynes 第一性原理

本节从 Cox 定理出发，推导出任何合规推理引擎必须满足的设计约束。这些约束直接决定了 §2 中势函数的形式。

### 1.1 Cox 定理与三条规则

Cox (1946) 证明：任何满足以下三个公理的合理推理系统，必须同构于概率论。

1. **实数表示**：命题的可信度用实数表示
2. **常识一致性**：如果 A 蕴含 B，B 的可信度上升 → A 的可信度也应上升
3. **唯一性**：等价的推理路径给出相同的结果

由此**推导出**（不是假设）三条规则：

- **乘法规则**: P(AB|X) = P(A|BX)·P(B|X)
- **加法规则**: P(A|X) + P(¬A|X) = 1
- **贝叶斯定理**: P(H|DX) = P(D|HX)·P(H|X) / P(D|X)

概率论不是众多推理方案中的一种——它是唯一满足一致性的方案。完整论证参见 [theoretical-foundation.md](theoretical-foundation.md) §2。
```

- [ ] **Step 2: Write §1.2 四个三段论**

Append §1.2 after §1.1. This is the core new derivation. Use a unified example (P₁∧P₂ → C) with concrete numbers (π₁=0.9, π₂=0.8, p=0.9, ε=0.001).

```markdown
### 1.2 四个三段论

Jaynes 在 *Probability Theory* 第一章从三条规则推导了四个量化三段论。给定推理关系 P₁∧P₂ → C（条件概率 p）：

**三段论 1 — Modus Ponens（前提真 → 结论更可信）：**

前提全部成立时，结论的可信度由条件概率决定：

```
P(C=1 | P₁=1, P₂=1) = p
```

**三段论 2 — 弱确认（结论真 → 前提更可信）：**

由贝叶斯定理，结论为真时，前提的可信度上升：

```
P(P₁=1 | C=1) = P(C=1 | P₁=1) · π₁ / P(C=1)
```

其中 P(C=1 | P₁=1) 对 P₂ 边缘化：P(C=1 | P₁=1) = p·π₂ + P(C=1|P₁=1,P₂=0)·(1-π₂)。

这个值大于 π₁ 当且仅当 P(C=1|P₁=1) > P(C=1)——即知道 P₁ 为真使结论更可能，这在正向支持的推理中总是成立。

**三段论 3 — Modus Tollens（结论假 → 前提更不可信）：**

```
P(P₁=1 | C=0) = P(C=0 | P₁=1) · π₁ / P(C=0)
```

结论为假时前提被削弱。这是 Modus Ponens 的概率化逆否命题。

**三段论 4 — 弱否定（前提假 → 结论更不可信）：**

```
P(C=1 | P₁=0) = ?
```

这个值取决于 **factor 如何编码 P(C | P₁=0)**。这是关键：前三个三段论对任何合理的 factor 都成立，但第四个三段论的成立需要 factor 在前提为假时主动压低结论——而非沉默。

具体验证（π₁=0.9, π₂=0.8, p=0.9）将在 §2.2 给出。
```

- [ ] **Step 3: Write §1.3 对推理引擎的要求**

```markdown
### 1.3 对推理引擎的要求

从四个三段论推导出推理引擎的设计约束：

| 约束 | 来源 | 要求 |
|------|------|------|
| C1 | 三段论 1 | 前提全真时，factor 必须以概率 p 支持结论 |
| C2 | 三段论 2 | 结论为真时，backward 消息必须提升前提 |
| C3 | 三段论 3 | 结论为假时，backward 消息必须压低前提 |
| C4 | 三段论 4 | 前提为假时，factor 必须压低结论——**不能沉默** |

C1–C3 在任何使用乘法/加法规则的消息传递系统中自动满足。**C4 是对 factor potential 形式的额外约束**——它禁止在前提为假时将 potential 设为均匀值（如 1.0），因为均匀 potential 使 factor 沉默，结论回到 prior 而非下降。

§2 将给出满足全部四条约束的势函数设计。
```

- [ ] **Step 4: Commit §1**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: write §1 Jaynes first principles and four syllogisms"
```

---

## Chunk 2: §2 unified factor potential model

### Task 3: Write §2 统一势函数模型

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace `## 2.` TODO block

This is the most important new section. Four subsections.

- [ ] **Step 1: Write §2.1 从条件概率到 Factor Potential**

Replace the `## 2.` TODO:

```markdown
## 2. 统一势函数模型

### 2.1 从条件概率到 Factor Potential

Factor potential（势函数）是一个函数，输入变量的状态组合，输出一个非负权重，表示该组合在此关系下的兼容程度。

联合概率由所有 factor potential 的乘积和所有 prior 的乘积决定：

```
P(x₁, ..., xₙ | I) ∝ ∏ⱼ φⱼ(xⱼ) · ∏ₐ ψₐ(xSₐ)
```

其中 φⱼ 是变量 j 的 prior（一元 factor），ψₐ 是 factor a 的势函数（连接变量子集 Sₐ）。

关键性质：

- **Potential 不是概率**——不需要归一化。只有比值有意义。
- **Potential = 1.0 意味着沉默**——对变量的两个状态给出相同权重，factor 不施加任何影响。
- **多个 factor 的影响通过乘积合并**——归一化由 BP 的消息传递自动保证。
```

- [ ] **Step 2: Write §2.2 Noisy-AND + Leak**

```markdown
### 2.2 Noisy-AND + Leak：推理 factor 的势函数

#### 作者提供的信息

在 Gaia 的创作模型中，作者对一条推理链提供的信息是：

- 各前提 P₁, ..., Pₙ 的 prior：π₁, ..., πₙ
- 条件概率 P(C=1 | P₁=1 ∧ ... ∧ Pₙ=1) = p

**结论 C 没有独立的 prior。** C 的可信度完全由前提和条件概率决定。

#### 旧模型的问题

旧的势函数在前提不全为真时设 potential = 1.0（沉默）：

```
φ_old(P₁,...,Pₙ, C):
  all Pᵢ=1, C=1  →  p
  all Pᵢ=1, C=0  →  1-p
  any Pᵢ=0, C=1  →  1.0     ← 沉默
  any Pᵢ=0, C=0  →  1.0     ← 沉默
```

这等价于 P(C|前提不全为真) = prior(C)。如果 C 的 prior 是 0.5（MaxEnt 默认值），则前提倒了，C 仍然是 0.5——违反约束 C4（§1.3），即第四三段论失败。

#### Noisy-AND + Leak 势函数

Gaia 的推理链是 **noisy-AND** 语义：所有前提必须同时成立，结论才以概率 p 成立。这是概率图模型文献中 canonical models（Independence of Causal Influence）族的标准成员，与 noisy-OR 对偶。

**Leak probability**（Henrion 1989）编码"前提不全为真时，结论仍然成立的背景概率"。对 Gaia 的推理链，前提是结论的近似必要条件，因此 leak 应极小。默认值 ε = Cromwell 下界（10⁻³）。

```
φ(P₁,...,Pₙ, C):
  all Pᵢ=1, C=1  →  p        (前提全真，支持结论)
  all Pᵢ=1, C=0  →  1-p      (前提全真，不支持结论)
  any Pᵢ=0, C=1  →  ε        (前提不全真，结论仍为真 → 极不兼容)
  any Pᵢ=0, C=0  →  1-ε      (前提不全真，结论为假 → 兼容)
```

#### 四三段论验证

取 π₁=0.9, π₂=0.8, p=0.9, ε=0.001：

**C 的边缘概率**（乘法规则 + 加法规则）：

```
P(C=1) = p · π₁π₂ + ε · (1 - π₁π₂)
       = 0.9 × 0.72 + 0.001 × 0.28
       = 0.648
```

**三段论 1** — P(C=1 | P₁=1, P₂=1) = p = 0.9 ✓

**三段论 2** — P(P₁=1 | C=1)：

```
P(C=1 | P₁=1) = p·π₂ + ε·(1-π₂) = 0.9×0.8 + 0.001×0.2 = 0.7202
P(P₁=1 | C=1) = 0.7202 × 0.9 / 0.648 = 0.9997 > 0.9 ✓
```

**三段论 3** — P(P₁=1 | C=0)：

```
P(C=0 | P₁=1) = (1-p)·π₂ + (1-ε)·(1-π₂) = 0.1×0.8 + 0.999×0.2 = 0.2798
P(C=0) = 1 - 0.648 = 0.352
P(P₁=1 | C=0) = 0.2798 × 0.9 / 0.352 = 0.716 < 0.9 ✓
```

**三段论 4** — P(C=1 | P₁=0)：

```
P(C=1 | P₁=0) = ε = 0.001 ✓
```

前提为假时，结论从 0.648 跌到 0.001。旧模型下只会跌到 0.5。

#### 与 PGM 文献的关系

Noisy-AND 是 noisy-OR（Pearl 1988, Henrion 1989）的对偶形式。Noisy-OR 用于析取因果模型（任意一个原因可导致结果），noisy-AND 用于合取因果模型（所有条件都必须满足）。Leak probability 是两者共享的标准参数，编码未建模原因的背景概率。

完整 CPT 需要 2ⁿ 个参数（n 个前提），noisy-AND + leak 只需要 2 个：p 和 ε。这与 Gaia 的创作模型完全匹配——作者只需指定一个条件概率。
```

- [ ] **Step 3: Write §2.3 约束 factor 的势函数**

```markdown
### 2.3 约束 factor 的势函数

Contradiction 和 equivalence 是**关系**（Relation），表达命题之间的结构性约束。旧设计使用 gate 语义——关系节点的 belief 只读，BP 不向其发送消息。

Gate 语义违反了 Jaynes 的核心原则：**所有命题的可信度都应随证据更新。** 如果 A 和 B 都有压倒性证据为真，而有人声称它们矛盾，合理的推理应该质疑矛盾本身——而非永远以固定强度压制 A 和 B。

新设计将关系节点作为普通 factor 参与者。

#### Contradiction（互斥约束）

语义：C_contra ∧ A₁ ∧ ... ∧ Aₙ → ⊥（矛盾成立且所有命题都为真是不可能的）。

```
φ_contradiction(C_contra, A₁, ..., Aₙ):
  C_contra=1, all Aᵢ=1   →  ε      (矛盾成立且都真 → 几乎不可能)
  其他所有组合              →  1      (无约束)
```

三个方向的消息自然涌现：

1. **C_contra 可信 + B 可信 → A 被压低**（保持旧行为）
2. **弱证据先让步**（保持：prior odds 低的变量在 odds 空间被同一似然比影响更大）
3. **A 和 B 都很强 → C_contra 被压低**（新能力：质疑矛盾本身）

推导 factor 给 C_contra 的消息似然比：

```
LR(C_contra) = msg(C_contra=1) / msg(C_contra=0)
             ≈ 1 - b_A · b_B
```

当 b_A 和 b_B 都接近 1 时，LR 接近 0，C_contra 被强力压低。

#### Equivalence（等价约束）

语义：C_equiv 为真时，A 和 B 应具有相同的真值。

```
φ_equivalence(C_equiv, A, B):
  C_equiv=1, A=B    →  1-ε    (等价成立 + 一致 → 高兼容)
  C_equiv=1, A≠B    →  ε      (等价成立 + 不一致 → 低兼容)
  C_equiv=0, 任意    →  1      (不等价 → 无约束)
```

对于 n-ary equivalence（3+ 成员），分解为 pairwise 约束：equiv(A, B, C) → factors for (C_equiv, A, B), (C_equiv, A, C), (C_equiv, B, C)。每个 pairwise factor 都包含 C_equiv 作为参与者。

效果：
- A 和 B 一致时，C_equiv 被推高（证据确认等价）
- A 和 B 分歧时，C_equiv 被压低（系统质疑等价关系）

#### 为什么 gate 语义不再需要

旧设计引入 gate 的理由是担心 feedback loop：关系节点影响约束强度 → 约束改变命题 belief → 命题 belief 改变关系节点 → 振荡。

这个担忧在 loopy BP + damping 下不成立。BP 在有环图上通过 damping 收敛到稳定的均衡点（§5.3）。关系节点参与 BP 产生的环与任何其他环没有本质区别。

gate 语义的代价是：阻止了双向信息流，使系统无法质疑关系本身。这比 feedback loop 风险更严重——它违反了 Jaynes 的一致性要求。
```

- [ ] **Step 4: Write §2.4 合规性验证**

```markdown
### 2.4 各 factor 类型的合规性验证

五种 factor 类型对 §1.3 四条约束的满足情况：

| Factor 类型 | C1 (前提真→支持) | C2 (结论真→前提↑) | C3 (结论假→前提↓) | C4 (前提假→结论↓) | 变更 |
|------------|:---:|:---:|:---:|:---:|------|
| Reasoning | ✓ | ✓ | ✓ | ✓ | **noisy-AND + leak** |
| Instantiation | ✓ | ✓ (弱) | ✓ | ✓ (正确无约束) | 不变 |
| Retraction | ✓ | ✓ | ✓ | ✓ (正确沉默) | 不变 |
| Contradiction | ✓ | ✓ | ✓ | ✓ (质疑关系) | **去 gate** |
| Equivalence | ✓ | ✓ | ✓ | ✓ (质疑关系) | **去 gate** |

**Instantiation 的 C4 为什么正确：** Schema=0 时 potential=1.0 是正确的。¬∀x.P(x) ⊬ ¬P(a)——全称命题为假不代表每个实例都假。单个反例强力否证全称（C3），但全称为假对实例无约束（C4）。这是 Popper/Jaynes 对归纳的标准观点。

**Retraction 的 C4 为什么正确：** 撤回证据 E 不成立时 potential=1.0 是正确的。E 是反对 C 的一条论据，E 不成立意味着这条论据消失——C 由其他 factor 决定。"没有找到反对的理由"≠"找到了支持的理由"。
```

- [ ] **Step 5: Commit §2**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: write §2 unified factor potential model (noisy-AND + leak)"
```

---

## Chunk 3: §3 lattice theory (adapted) and §4 factor types

### Task 4: Write §3 蕴含格（adapted from old §2）

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace `## 3.` TODO block

Copy old §2 (lines 175-307) almost verbatim. Only changes: renumber from §2.x to §3.x, and add a bridging paragraph at the end of §3.5 (old §2.5).

- [ ] **Step 1: Copy old §2 content as new §3, renumber subsections**

Replace the `## 3.` TODO with the old §2 content (§2.1–§2.6), changing all `### 2.x` to `### 3.x`. Keep all content, diagrams, and tables intact.

- [ ] **Step 2: Add bridging paragraph at end of §3.5**

After the existing table in §3.5 (old §2.5), append:

```markdown
格论决定了 probability 的**取值约束**（abstraction 可以 = 1.0，induction 必须 < 1.0）。§2 的 noisy-AND + leak 模型决定了势函数的**结构形式**（前提为假时 potential = ε 而非 1.0）。两者互补：格论约束 p 的值域，noisy-AND + leak 约束 φ 在各状态组合下的形状。
```

- [ ] **Step 3: Commit §3**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: adapt §3 lattice theory from old §2, add factor model bridge"
```

---

### Task 5: Write §4 五种 Factor 类型

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace `## 4.` TODO block

This section gives concrete definitions for each factor type using a uniform format: structure, potential table, Jaynes compliance, design rationale.

- [ ] **Step 1: Write §4.1 Reasoning**

Replace the `## 4.` TODO with:

```markdown
## 4. 五种 Factor 类型

每种 factor 使用统一格式：结构、势函数表、Jaynes 合规性、设计理由。

### 4.1 Reasoning Factor

**结构：** 连接前提知识节点到单个结论知识节点，附带条件概率。

```
premises:   [P₁, P₂, ..., Pₙ]    (直接依赖)
conclusion: C                      (结论)
parameter:  conditional_probability = p
```

**势函数（noisy-AND + leak）：**

| 前提全真？ | 结论值 | Potential |
|-----------|--------|-----------|
| 是 | 1 | p |
| 是 | 0 | 1-p |
| 否 | 1 | ε (leak) |
| 否 | 0 | 1-ε |

其中 ε = Cromwell 下界（默认 10⁻³）。

**Subtypes：**

| Subtype | 势函数差异 | probability 约束 |
|---------|-----------|-----------------|
| deduction | 标准（上表） | 可以 = 1.0 |
| induction | 标准（上表） | 必须 < 1.0（§3 格论约束） |
| abstraction | 标准（上表） | 可以 = 1.0 |
| retraction | 反转（见下） | — |

**Retraction 的反转势函数：**

Retraction 表示"撤回证据 E 成立时，结论 C 被削弱"：

| E (前提) | C (结论) | Potential |
|----------|---------|-----------|
| 1 | 1 | 1-p (削弱) |
| 1 | 0 | p |
| 0 | 1 | 1.0 (沉默) |
| 0 | 0 | 1.0 (沉默) |

Retraction 的 E=0 行保持 1.0 是正确的（§2.4）：撤回证据不成立时，这条反对论据消失，C 由其他 factor 决定。这与 reasoning factor 不同——reasoning 的前提是结论存在的根据（前提倒 → 结论失去基础），retraction 的前提是反对结论的论据（论据消失 → 结论不受影响）。

**合规性：** 满足 C1–C4（§2.4）。
```

- [ ] **Step 2: Write §4.2 Instantiation**

```markdown
### 4.2 Instantiation Factor

**结构：** 二元 factor，连接一个 schema 节点（全称命题）到一个 ground 节点（实例）。

```
premises:   [V_schema]             (∀x.P(x))
conclusion: V_instance             (P(a))
```

**势函数（确定性蕴含）：**

| Schema | Instance | Potential |
|--------|----------|-----------|
| 1 (∀x.P(x) 成立) | 1 (P(a) 成立) | 1.0 |
| 1 (∀x.P(x) 成立) | 0 (P(a) 不成立) | ε (矛盾：全称为真但实例为假) |
| 0 (∀x.P(x) 不成立) | 1 (P(a) 成立) | 1.0 (实例可独立成立) |
| 0 (∀x.P(x) 不成立) | 0 (P(a) 不成立) | 1.0 |

无参数化的 conditional_probability——这是确定性逻辑蕴含。

**归纳强化：** 多个实例通过 BP 消息聚合，在共享的 schema 节点上产生归纳效应：

```
V_schema ─── F_inst_1 ─── V_ground_1 (belief=0.9)
         ─── F_inst_2 ─── V_ground_2 (belief=0.85)
         ─── F_inst_3 ─── V_ground_3 (belief=0.1)   ← 反例
```

- 多个高 belief 实例：backward 消息弱支持 schema（正例不能证明全称，但多个正例累积提供弱归纳证据）
- 一个低 belief 实例：backward 消息强力压低 schema（反例否证全称）
- Schema belief 下降 → forward 消息削弱所有实例（全称被质疑 → 所有实例失去全称支持）

**合规性：** 满足 C1–C4（§2.4）。Schema=0 时 potential=1.0 是正确的：¬∀x.P(x) ⊬ ¬P(a)。
```

- [ ] **Step 3: Write §4.3 Contradiction**

```markdown
### 4.3 Contradiction Factor

**结构：** 三变量（或多变量）约束 factor，连接矛盾关系节点和被约束的命题节点。

```
participants: [C_contra, A₁, A₂, ..., Aₙ]
```

C_contra 是矛盾关系节点（Knowledge type="contradiction"），**作为普通参与者**参与 BP——不是 gate。

**势函数（互斥约束）：**

| C_contra | 所有 Aᵢ | Potential |
|----------|---------|-----------|
| 1 | 全部 = 1 | ε (矛盾成立且都真 → 几乎不可能) |
| 其他任意组合 | — | 1 (无约束) |

**三个方向的效果：**

```
C_contra(0.8), A(0.9), B(0.6)
    ↓
BP 收敛后：
  B 大幅下降（弱证据先让步，odds 空间乘法）
  A 小幅下降
  C_contra 基本不变（A·B 乘积已不大）

如果 A 和 B 都收到新证据，升到 0.95：
  C_contra 被大幅压低（LR ≈ 1 - 0.95×0.95 ≈ 0.10）
  系统结论：矛盾关系可能不成立
```

**Jaynes 的解释：** 发现矛盾 = 学到新信息 P(A∧B|I) ≈ 0。这不是系统错误，而是证据冲突。BP 自动处理：弱证据先让步（从 odds 乘法自然涌现），强反证可质疑矛盾本身（从双向消息自然涌现）。

**合规性：** 满足 C1–C4（§2.4）。
```

- [ ] **Step 4: Write §4.4 Equivalence**

```markdown
### 4.4 Equivalence Factor

**结构：** 三变量约束 factor，连接等价关系节点和被等价的命题节点。

```
participants: [C_equiv, A, B]
```

C_equiv 是等价关系节点（Knowledge type="equivalence"），**作为普通参与者**参与 BP——不是 gate。

**势函数（等价约束）：**

| C_equiv | A, B 关系 | Potential |
|---------|----------|-----------|
| 1 | A = B (一致) | 1-ε |
| 1 | A ≠ B (不一致) | ε |
| 0 | 任意 | 1 (无约束) |

n-ary equivalence（3+ 成员）分解为 pairwise：equiv(A, B, C) → factors for (C_equiv, A, B), (C_equiv, A, C), (C_equiv, B, C)。

**效果：**

- 等价成立 + A 可信 → B 被提升（证据桥接）
- 等价成立 + A 和 B 一致 → C_equiv 被推高（确认等价）
- 等价成立 + A 和 B 分歧 → C_equiv 被压低（质疑等价关系）

**合规性：** 满足 C1–C4（§2.4）。
```

- [ ] **Step 5: Commit §4**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: write §4 five factor types with unified format"
```

---

## Chunk 4: §5 BP algorithm (relocated), §6-§7, appendices, final review

### Task 6: Write §5 信念传播算法（relocated from old §1）

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace `## 5.` TODO block

Relocate old §1.1, §1.3, §1.4, §1.5 content here with minor adaptations. Add §5.4 Cromwell's Rule (collected from scattered mentions) and §5.5 BP-Jaynes correspondence (adapted from old §1.6).

- [ ] **Step 1: Write §5.1–§5.3 (relocated from old §1)**

Replace the `## 5.` TODO. Adapt old §1.1 (什么是因子图), §1.3 (Loopy), §1.4 (Damping), §1.5 (Sum-Product) as §5.1–§5.3. The content of §1.2 (BP 的直觉) can be folded into §5.1 as an introductory paragraph. Remove the old "关键改进" list (it was relative to a previous implementation — no longer relevant in a theory document versioned at 2.0).

Key adaptations:
- §5.1: combine old §1.1 + §1.2 into a concise "what is a factor graph + intuition" section
- §5.2: old §1.5 (the full sum-product flow diagram) verbatim
- §5.3: merge old §1.3 + §1.4 into one subsection

- [ ] **Step 2: Write §5.4 Cromwell's Rule**

```markdown
### 5.4 Cromwell's Rule

永远不对经验命题赋予 P=0 或 P=1（Cromwell's Rule）。如果 P(H)=0，则无论多少证据都无法更新 belief（贝叶斯定理的分子为零）。

Gaia 在两处执行 Cromwell's Rule：

1. **构建时**：所有 prior 和 conditional_probability 被 clamp 到 [ε, 1-ε]，ε = 10⁻³
2. **势函数中**：noisy-AND + leak 的 leak 参数 ε 本身就是 Cromwell 下界，确保没有状态组合的 potential 为零

实现位于 `libs/inference/factor_graph.py` 的 `_cromwell_clamp()` 函数。
```

- [ ] **Step 3: Write §5.5 BP 与 Jaynes 的闭环对应**

Adapted from old §1.6 table, enriched with the syllogism mapping:

```markdown
### 5.5 BP 与 Jaynes 的闭环对应

BP 的每一步操作都对应 Jaynes 的一条规则：

| BP 操作 | Jaynes 规则 | 说明 |
|---------|------------|------|
| 联合分布 = ∏ factor potential × ∏ prior | 乘法规则 | 因子分解 |
| 消息归一化 [p(0)+p(1)=1] | 加法规则 | 2-vector 始终求和为 1 |
| belief = prior × ∏ factor→var messages | 贝叶斯定理 | posterior ∝ prior × likelihood |
| var→factor 消息 (exclude-self) | 先验（排除当前 factor 的贡献） | P(H\|X) 中的"背景信息" |
| factor→var 消息 (marginalize) | 似然函数 | P(D\|HX) 对其他变量边缘化 |
| Bethe 自由能 | MaxEnt 近似 | loopy BP 近似最小化的目标 |
| 同步 schedule | 证据可交换性 | 消息顺序不影响结果 |

**在树结构图上，BP 精确实现 Jaynes 的规则。在有环图上，BP 通过 Bethe 自由能近似实现——这是计算上的必然，且在稀疏知识图谱上近似质量通常很好。**
```

- [ ] **Step 4: Commit §5**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: write §5 BP algorithm (relocated from old §1, added Cromwell and Jaynes correspondence)"
```

---

### Task 7: Write §6, §7, and appendices

**Files:**
- Modify: `docs/foundations/theory/inference-theory.md` — replace remaining TODO blocks

- [ ] **Step 1: Write §6 (adapted from old §4)**

Replace `## 6.` TODO. Copy old §4 content (已知局限与演进方向). Changes:
- §6.1 "已解决的局限" add item 6: `~~Gate 语义阻止双向信息流~~：现已统一为普通 factor 参与者，关系节点的 belief 可被证据更新`
- §6.2–§6.4: keep as-is from old §4.2–§4.4

- [ ] **Step 2: Write §7 (verbatim from old §5)**

Replace `## 7.` TODO with old §5 content (逻辑编程技术启发 + §5.1 不动点计算) verbatim.

- [ ] **Step 3: Write Appendix A (updated terminology)**

Replace `## 附录 A` TODO. Copy old appendix A and add new entries:

| 术语 | Gaia 中的对应 | 代码位置 |
|------|-------------|---------|
| Noisy-AND | Reasoning factor 的势函数模型 | `libs/inference/bp.py:_evaluate_potential()` |
| Leak probability (ε) | Cromwell 下界，前提为假时的 potential | `libs/inference/factor_graph.py:_cromwell_clamp()` |
| Gate (已移除) | 旧设计中关系节点的只读机制，已统一为普通参与者 | — |

- [ ] **Step 4: Write Appendix B (verbatim from old)**

Replace `## 附录 B` TODO with old Appendix B content verbatim.

- [ ] **Step 5: Commit §6, §7, appendices**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: write §6-§7 and appendices, complete inference-theory.md v2.0 restructure"
```

---

### Task 8: Final review, lint, and format check

**Files:**
- Review: `docs/foundations/theory/inference-theory.md`

- [ ] **Step 1: Run ruff format check**

```bash
ruff check docs/foundations/theory/inference-theory.md 2>/dev/null; echo "ruff does not check .md files, skip"
```

- [ ] **Step 2: Verify no broken internal links**

Check that all `[text](link)` references in the document point to existing files:
- `theoretical-foundation.md` — exists in same directory
- `../bp-on-graph-ir.md` — exists in parent directory

```bash
ls docs/foundations/theory/theoretical-foundation.md docs/foundations/bp-on-graph-ir.md
```

Expected: both files listed, no errors.

- [ ] **Step 3: Verify document structure**

Grep for section headers to confirm correct numbering:

```bash
grep -E "^##" docs/foundations/theory/inference-theory.md
```

Expected output should show:
```
## 1. Jaynes 第一性原理
## 2. 统一势函数模型
## 3. 蕴含格中的 Abstraction 与 Induction
## 4. 五种 Factor 类型
## 5. 信念传播算法
## 6. 已知局限与演进方向
## 7. 逻辑编程技术启发
## 附录 A：术语对照
## 附录 B：与相关系统的概率机制对比
```

- [ ] **Step 4: Verify no TODO markers remain**

```bash
grep -n "TODO" docs/foundations/theory/inference-theory.md
```

Expected: no output (all TODOs replaced).

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add docs/foundations/theory/inference-theory.md
git commit -m "docs: final review fixes for inference-theory.md v2.0"
```

Only run this if changes were made in steps 1-4.
