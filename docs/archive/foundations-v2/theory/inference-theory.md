# 推理引擎理论

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-16 |
| 状态 | Target design for the next BP / Graph IR theory revision |
| 关联文档 | [theoretical-foundation.md](theoretical-foundation.md) — Jaynes 纲领与 Gaia 定位, [../bp-on-graph-ir.md](../bp-on-graph-ir.md) — BP 在 Graph IR 上的运行 |

---

本文档定义 Gaia 推理引擎 **v2.0 目标模型** 的理论参考。组织顺序为：先从 Jaynes 第一性原理推导设计约束（§1），再给出满足这些约束的统一势函数模型（§2），然后分析推理方向的格论性质（§3），定义五种 factor 类型（§4），最后描述信念传播算法的计算细节（§5）。

当前 `main` 上已实现/已成文的本地 BP 语义仍以 [../bp-on-graph-ir.md](../bp-on-graph-ir.md) 为准；本文档描述的是下一轮 BP / Graph IR 理论收敛后的目标设计，因此其中关于 noisy-AND + leak、constraint factor 去 gate 的内容不应被理解为当前运行时已经完成同步。

关于 Jaynes 的认识论纲领和 Gaia 的整体定位，参见 [theoretical-foundation.md](theoretical-foundation.md)。

---

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

具体验证（π₁=0.9, π₂=0.8, p=0.9）在 §2.2 给出。

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

---

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

### 2.2 Noisy-AND + Leak：推理 factor 的势函数

#### 作者提供的信息

在 Gaia 的创作模型中，作者对一条推理链提供的信息是：

- 各前提 P₁, ..., Pₙ 的 prior：π₁, ..., πₙ
- 条件概率 P(C=1 | P₁=1 ∧ ... ∧ Pₙ=1) = p

在这个 **v2.0 目标理论模型** 中，作者为一条 reasoning factor 显式提供的是前提 prior 和条件概率 `p`。结论 C 的支持主要由这些量决定。

这不等于“当前 runtime 不再为结论维护 prior”。当前 `main` 的本地 BP overlay 仍要求为每个 belief-bearing node 提供 prior；这里讨论的是目标理论里的 factor 语义，而不是当前参数化工件的最小字段集合。

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

### 2.3 约束 factor 的势函数

Contradiction 和 equivalence 是**关系**（Relation），表达命题之间的结构性约束。当前 `main` 上成文的 BP / Graph IR 语义仍使用 gate 设计；本节定义的是 v2.0 目标模型，其中关系节点不再被当作只读 gate。

Gate 语义违反了 Jaynes 的核心原则：**所有命题的可信度都应随证据更新。** 如果 A 和 B 都有压倒性证据为真，而有人声称它们矛盾，合理的推理应该质疑矛盾本身——而非永远以固定强度压制 A 和 B。

在该目标模型中，关系节点作为普通 factor 参与者。

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

---

## 3. 蕴含格中的 Abstraction 与 Induction

这一节从格论 (lattice theory) 的角度阐明 Gaia 两种核心推理操作的数学本质，以及为什么 abstraction 保真而 induction 不保真。

### 3.1 蕴含格 (Lindenbaum-Tarski Algebra)

所有命题按蕴含强度可以排成一个格 (lattice)。定义偏序：

```
P ≤ Q  当且仅当  P ⊨ Q  (P 蕴含 Q，即 P 比 Q 更强)
```

在这个格中：

- **向上** = 越来越弱（信息越来越少）
- **向下** = 越来越强（声称越来越多）
- **最小上界 (LUB / join)** = 析取 A ∨ B — 最弱的、被 A 和 B 各自蕴含的命题
- **最大下界 (GLB / meet)** = 合取 A ∧ B — 最强的、蕴含 A 和 B 各自的命题

```
            弱 (上方)
               ↑
        ... C_abs ...        ← abstraction 的结果
           A ∨ B             ← 析取 = LUB (最紧上界)
          /     \
         A       B           ← 原始命题
          \     /
           A ∧ B             ← 合取 = GLB (最紧下界)
        ... C_ind ...        ← induction 的结果
               ↓
            强 (下方)
```

### 3.2 Abstraction 与析取 (OR)

Gaia 的 abstraction 操作：给定命题 A 和 B，找到 C 满足 A ⊨ C 且 B ⊨ C（C 是它们共同的、更弱的概括）。

析取 A ∨ B 也满足这个条件：A ⊨ (A ∨ B) 且 B ⊨ (A ∨ B)。区别在于：

| | 析取 (A ∨ B) | Abstraction |
|---|---|---|
| **定义** | 逻辑连接词 | 推理操作 |
| **在格中的位置** | 最小上界 (最紧) | 通常在 LUB 之上 (更松) |
| **结果** | "A 或 B" (精确但啰嗦) | 语义概括 (自然但更弱) |

以超导为例：

```
A: "MgB₂ 在 T<39K 时超导"
B: "MgB₂ 在 H<Hc 时超导"

A ∨ B: "MgB₂ 在 T<39K 时超导，或在 H<Hc 时超导"    ← 精确，最紧上界
C_abs: "MgB₂ 存在超导态"                              ← 更弱，但语义上更有意义

蕴含链：A ⊨ (A ∨ B) ⊨ C_abs
```

**关键性质：** 两者都是上界，因此从 A（或 B）出发到达它们都是保真的。不管 C 在 A ∨ B 之上多远，只要 A ⊨ C，那么 A 真时 C 一定真。

### 3.3 Induction 与合取 (AND)

Gaia 的 induction 操作：给定命题 A 和 B，找到 C 满足 C ⊨ A 且 C ⊨ B（C 是它们共同的、更强的概括）。

合取 A ∧ B 也满足这个条件：(A ∧ B) ⊨ A 且 (A ∧ B) ⊨ B。区别在于：

| | 合取 (A ∧ B) | Induction |
|---|---|---|
| **定义** | 逻辑连接词 | 推理操作 |
| **在格中的位置** | 最大下界 (最紧) | 通常在 GLB 之下 (更松) |
| **结果** | "A 且 B" (只说了已知的) | 泛化概括 (声称超出证据) |

以金属膨胀为例：

```
A: "铁加热膨胀"
B: "铜加热膨胀"

A ∧ B: "铁加热膨胀，且铜加热膨胀"    ← 精确，最紧下界，只说了铁和铜
C_ind: "金属加热膨胀"                 ← 更强！声称了金、银、铝、锌……

蕴含链：C_ind ⊨ (A ∧ B) ⊨ A
```

**关键性质：** C_ind 比 A ∧ B 更强（在格中更低），这意味着 (A ∧ B) ⊭ C_ind。从 A、B 出发无法保真地到达 C_ind。

### 3.4 根本性的不对称

这是本节最核心的 insight：

```
向上 (弱化)：可以无限远离 A ∨ B，每一步都保真
               A ⊨ (A∨B) ⊨ C₁ ⊨ C₂ ⊨ ...  ✓ 全部保真

向下 (强化)：A ∧ B 是保真的极限，再往下一步就不保真了
               ... C₂ ⊨ C₁ ⊨ (A∧B) ⊨ A
                   ✗       ✗     ✓ 只有最后一步保真
```

原因很简单：

- **弱化** = 丢掉信息。真命题蕴含的任何更弱命题必然为真。丢信息永远安全。
- **强化** = 添加信息。添加的信息可能是错的。A ∧ B 是"零添加"的极限（只重述已知事实），再往下就是在声称证据没有支持的东西。

这就是哲学中**归纳问题 (problem of induction)** 的格论表述：归纳是唯一能产生 genuinely new knowledge 的推理形式，但它的代价是不保真。

### 3.5 对 Gaia 设计的直接推论

这个不对称性直接决定了 Gaia 的概率设计：

| 操作 | 格中方向 | 保真性 | probability 约束 | 理由 |
|------|---------|--------|-----------------|------|
| **Abstraction** | 向上 (弱化) | 保真 | 可以 = 1.0 | 结论已被前提蕴含 |
| **Induction** | 向下 (强化) | 不保真 | 必须 < 1.0 | 结论超出了证据范围 |
| **合取引入** | 到 GLB (不动) | 保真 | = 1.0 | 但不产生新知识，Gaia 中不需要专门边类型 |

格论决定了 probability 的**取值约束**（abstraction 可以 = 1.0，induction 必须 < 1.0）。§2 的 noisy-AND + leak 模型决定了势函数的**结构形式**（前提为假时 potential = ε 而非 1.0）。两者互补：格论约束 p 的值域，noisy-AND + leak 约束 φ 在各状态组合下的形状。

### 3.6 四种操作的完整对称

```
                    保真 (deductive)         不保真 (inductive)
                   ──────────────────    ──────────────────────
向上 (弱化)     │  Abstraction           │  (不存在：弱化不可能
                │  A,B → C (C 更弱)      │   不保真，因为真命题
                │  prob 可以 = 1.0        │   蕴含一切更弱命题)
                │                         │
向下 (强化)     │  合取引入               │  Induction
                │  A,B → A∧B (精确下界)  │  A,B → C (C 更强)
                │  prob = 1.0 但平凡      │  prob 必须 < 1.0
```

右上角为空不是偶然——弱化在逻辑上不可能不保真（如果你只是丢掉信息，不可能出错）。左下角存在但平凡——合取引入保真但不产生洞见。

Gaia 真正有意义的两种操作占据了对角线：**abstraction (保真弱化)** 和 **induction (不保真强化)**，它们分别是知识浓缩和知识创造的引擎。

---

## 4. 四类 BP Operator Family 与当前 lowering

本节只讨论 **BP operator family**，不讨论所有图构造操作。

这一区分必须明确：

- `abstraction`、`generalization`、`hidden premise discovery` 首先是**图构造 / 研究操作**
- BP 关心的是这些操作在被接受后，最终降低成什么 **operator family**

因此，Graph IR / storage 中出现的结构名和 BP family 并不总是一一对应。

### 4.1 Operator Family 总表

| Family | 语义 | 保真性 | probability 约束 | antecedent=false 时的正确行为 | 当前 / 目标 lowering |
|---|---|---|---|---|---|
| `reasoning_support` | 普通前提→结论支持 | 不一定保真 | `p ∈ (0,1]`；deductive 可接近 1，abductive 通常 < 1 | **应压低结论**（noisy-AND + leak） | 当前主要由 `infer` 承载 |
| `deterministic_entailment` | 真值保留的蕴含 | 保真 | 概念上 = 1.0（runtime 仍受 Cromwell clamp） | **通常沉默**，不推出结论为假 | 当前稳定子类是 `instantiation`；accepted abstraction/member entailment 也应落这里 |
| `inductive_support` | 从实例到更强候选规律的支持 | 不保真 | **必须 < 1.0** | 通常弱影响或沉默，不应按 noisy-AND 必要条件语义处理 | 未来 family，当前 local runtime 尚未稳定成型 |
| `constraint` | 兼容性约束（矛盾 / 等价） | 非 antecedent→consequent 关系 | 不适用；由兼容核决定 | 不适用；使用专门约束势函数 | 当前 / 目标都由 `contradiction` / `equivalence` 承载 |

### 4.2 更新律矩阵

Jaynes 的四个三段论在系统里应被理解为 **operator contract**，而不是新的语言关键字。

| Family | 前提真→结论↑ | 结论真→前提↑ | 结论假→前提↓ | 前提假→结论↓ |
|---|:---:|:---:|:---:|:---:|
| `reasoning_support` | ✓ | ✓ | ✓ | ✓ |
| `deterministic_entailment` | ✓ | ✓ | ✓ | 通常否；应沉默 |
| `inductive_support` | ✓ | ✓ | 弱 / 部分成立 | 通常否；不应强行压低 |
| `constraint` | 不适用 | 不适用 | 不适用 | 不适用 |

最后一列最容易被误用：

- 对 `reasoning_support`，前提是结论的近似必要条件，所以 antecedent=false 应压低结论
- 对 `deterministic_entailment`，`not A` 一般不推出 `not B`，所以 antecedent=false 应沉默
- 对 `inductive_support`，从案例到规律的支持不是必要条件结构，不能机械套用 noisy-AND 的第四条

### 4.3 `reasoning_support`

`reasoning_support` 是作者最常写、也是本地 BP 最常见的 operator family。

它的典型结构是：

```
premises:   [P₁, P₂, ..., Pₙ]
conclusion: C
parameter:  p
```

其 canonical 势函数是 §2.2 的 **noisy-AND + leak**：

| 前提全真？ | 结论值 | Potential |
|-----------|--------|-----------|
| 是 | 1 | p |
| 是 | 0 | 1-p |
| 否 | 1 | ε |
| 否 | 0 | 1-ε |

这个 family 覆盖的是“给定这些前提，结论应该更可信”的一般支持结构。

说明：

- `deductive` 是它的高置信模式，不是独立 family
- `abductive` 更适合被看作它的作者语义 mode，而不是底层独立 kernel family
- 当前代码里一些历史名如 `retraction`、`abstraction` 若仍以 infer-like factor 出现，应被视为 transitional lowering，而不是新的 ontology family

### 4.4 `deterministic_entailment`

`deterministic_entailment` 表达真值保留的蕴含。

最稳定的子类是 `instantiation`：

```
premises:   [V_schema]
conclusion: V_instance
```

其关键语义是：

- `schema=true` 强约束 `instance=true`
- `instance=false` 反向削弱 `schema`
- `schema=false` 时通常沉默，而不是推出 `instance=false`

这也是 accepted abstraction/member entailment 的正确家族：如果多个更具体命题都蕴含一个更弱命题，那么成员到抽象命题的连接应落在 `deterministic_entailment`，而不是复用 ordinary reasoning kernel。

### 4.5 `inductive_support`

`inductive_support` 表达从多个具体实例到更强 generalization candidate 的支持。

它与 `reasoning_support` 的差异不在于“都有一个 p”，而在于其认识论方向：

- `reasoning_support` 通常是给定前提支持结论
- `inductive_support` 是从具体案例支持一个**超出案例范围**的更强命题

因此：

- `p` 必须严格小于 1.0
- 它不应被当作必要条件结构
- antecedent=false 时通常不应像 noisy-AND 那样强力压低 generalization

当前 Gaia 中，真正稳定的 `inductive_support` 还没有完整落成统一 local runtime family；它更多仍处在 curation / investigation 的候选结构层。

### 4.6 `constraint`

`constraint` family 包含：

- `contradiction`
- `equivalence`

它们不是 antecedent→consequent operator，而是兼容性核：

- `contradiction`：关系成立时，不兼容 all-true 配置
- `equivalence`：关系成立时，奖励一致、惩罚分歧

这里最重要的理论要求不是四条三段论，而是：

- 约束应能双向影响被约束命题
- 在 target design 中，关系节点本身也应可被证据质疑

### 4.7 当前 structural factor names 与 operator family 的映射

| 当前结构名 | 应归入的 BP family | 备注 |
|---|---|---|
| `infer` | `reasoning_support` | 当前最主要 lowering |
| `abstraction` | transitional；通常应落到 `deterministic_entailment` 或 graph-construction result | 名称上仍带历史混淆 |
| `instantiation` | `deterministic_entailment` | 语义最稳定 |
| `contradiction` | `constraint` | 当前 / 目标都保留 |
| `equivalence` | `constraint` | 当前 runtime 仍有同步中的过渡痕迹 |

这张表的目的不是重新命名现有 schema，而是防止把结构名、语言名、BP family 名混成一个层级。

---

## 5. 信念传播算法

### 5.1 因子图

因子图 (factor graph) 是一种二部图，包含两种节点：

- **变量节点 (variable node)**：表示一个未知量，带有先验分布
- **因子节点 (factor node)**：表示变量之间的约束或关联

Gaia 的推理超图**天然就是一个因子图**：

```
变量节点 = Knowledge (命题)
  ├── 先验值 = prior
  └── 后验值 = belief (BP 计算结果)

因子节点 = Factor (推理关系或约束)
  ├── 连接 = premises[] + conclusion (或 participants[])
  └── 势函数 = §4 定义的各类型 potential
```

直觉：信念传播就是在因子图上反复传递消息，更新每个节点的"信念"。

```
前提可信度 × 推理可靠性 = 结论可信度

beliefs[1] × beliefs[2] × edge.probability = factor_message
     0.8    ×    0.7     ×      0.9        =    0.504

"前提1我信80%，前提2我信70%，推理过程可靠性90%，
 所以结论我信50.4%"
```

### 5.2 Sum-Product 消息传递

消息为 2-vector `[p(x=0), p(x=1)]`，始终归一化。

```
初始化: 所有消息 = [0.5, 0.5]（均匀，MaxEnt）
        priors = {var_id: [1-prior, prior]}
         │
         ▼
    ┌─── 循环 (最多 max_iterations 轮) ────────────────┐
    │                                                    │
    │  1. 计算所有 var→factor 消息 (exclude-self rule):  │
    │     msg(v→f) = prior(v) × ∏ msg(f'→v), f'≠f      │
    │                                                    │
    │  2. 计算所有 factor→var 消息 (marginalize):        │
    │     msg(f→v) = Σ_{其他变量} φ(assignment) × ∏ msg  │
    │                                                    │
    │  3. Damping + 归一化:                              │
    │     msg = α × new + (1-α) × old, 然后归一化        │
    │                                                    │
    │  4. 计算 beliefs:                                  │
    │     b(v) = normalize(prior(v) × ∏ msg(f→v))       │
    │                                                    │
    │  5. 检查收敛:                                      │
    │     max(|new_belief - old_belief|) < threshold?    │
    │     是 → 停止                                      │
    │     否 → 继续下一轮                                │
    └────────────────────────────────────────────────────┘
         │
         ▼
输出: 每个节点的后验 belief = b(v)[1] ∈ [0, 1]
```

关键设计：
- **双向消息**：var→factor + factor→var，backward 抑制自然涌现
- **Exclude-self rule**：避免循环放大
- **同步更新**：所有新消息从旧消息计算，然后一次性替换（因子顺序无关）
- **2-vector 归一化**：消息始终求和为 1，长链不衰减

### 5.3 Loopy BP 与 Damping

如果因子图是一棵树（没有环），BP 一轮就能精确收敛。

但真实的知识图谱几乎一定有环：

```
Node A: "高温超导存在"
    ↓ [edge 1]
Node B: "材料X是高温超导体"
    ↓ [edge 2]
Node C: "材料X的晶体结构支持超导"
    ↓ [edge 3]
Node A: "高温超导存在" ← 回到了 A，形成环
```

有环时，消息会循环传播。Loopy BP 的做法是：不管有没有环，直接迭代传递消息，跑多轮直到信念值稳定。理论上不保证收敛，但在实践中对大多数图效果很好。

**Damping（阻尼）** 防止有环图上的振荡：

```python
msg_new = damping * computed_msg + (1 - damping) * msg_old
```

默认 `damping=0.5`，每次只更新一半。`damping=1.0` 表示完全用新值（无阻尼），`damping=0.0` 表示完全不更新。

### 5.4 Cromwell's Rule

永远不对经验命题赋予 P=0 或 P=1（Cromwell's Rule）。如果 P(H)=0，则无论多少证据都无法更新 belief（贝叶斯定理的分子为零）。

Gaia 在两处执行 Cromwell's Rule：

1. **构建时**：所有 prior 和 conditional_probability 被 clamp 到 [ε, 1-ε]，ε = 10⁻³
2. **势函数中**：noisy-AND + leak 的 leak 参数 ε 本身就是 Cromwell 下界，确保没有状态组合的 potential 为零

实现位于 `libs/inference/factor_graph.py` 的 `_cromwell_clamp()` 函数。

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

---

## 6. 已知局限与演进方向

### 6.1 已解决的局限

以下问题在 sum-product loopy BP 重写中已解决：

1. ~~边类型未区分~~：现已实现类型感知 factor potential（deduction、retraction、contradiction 各有独立语义）
2. ~~多因子消息顺序覆盖~~：现使用 2-vector 消息 + 乘法聚合，多条入边的消息正确合并
3. ~~无反向传播~~：现有完整的 var→factor 和 factor→var 双向消息，backward 抑制自然涌现
4. ~~因子顺序影响结果~~：现使用同步 schedule，所有消息从旧值计算后同时更新
5. ~~Contradiction 无独立语义~~：现使用 Jaynes 惩罚性 potential（§4.3），contradiction 自带强力 backward inhibition
6. ~~Gate 语义阻止双向信息流~~：现已统一为普通 factor 参与者，关系节点的 belief 可被证据更新（§2.3）

### 6.2 当前局限

1. **纯拓扑推理**：BP 完全不看节点内容，无法利用语义相似性

### 6.3 可能的演进方向

| 方向 | 说明 | 优先级 |
|------|------|--------|
| GPU 加速 BP | 用 PGMax (JAX) 替代自研 NumPy 实现 | 中 |
| 嵌入辅助 BP | 用 embedding 相似度调节消息权重 | 低 |
| 局部精确推理 | 树结构子图用精确 BP，环结构用 Loopy BP | 低 |

### 6.4 不打算改变的设计选择

- **节点内容对 BP 不透明**：语义理解交给 LLM，不交给推理引擎
- **图结构只有合取→合取**：保持简单，不引入析取/否定到图结构层
- **Pre-grounded**：不存通用规则，只存具体实例
- **非单调推理**：新证据可以降低已有 belief，这是特性不是 bug

---

## 7. 逻辑编程技术启发

Horn clause 研究领域（逻辑编程、Datalog）的成熟技术对 Gaia 有直接价值：

| 技术 | 来源 | 在 Gaia 中的应用方向 |
|------|------|---------------------|
| **Seminaïve evaluation** | Datalog | 每轮 BP 只传播上一轮变化的消息，避免重复计算 |
| **Magic sets optimization** | Datalog | 优化后向链查询——只计算与查询相关的子图，而非全图 BP |
| **Tabling / memoization** | Prolog (XSB) | 缓存已推导的中间结果 |
| **Stratification** | Datalog with negation | 分层处理 contradiction edge——先处理无矛盾子图，再处理矛盾 |
| **Incremental view maintenance** | Differential Dataflow | 增量 BP——只重算受影响的节点，而非全图重跑 |

其中 seminaïve evaluation 尤其值得关注：当前 BP 实现每轮遍历所有超边，但大部分节点的 belief 在每轮变化很小。Datalog 的 seminaïve 策略（只看上一轮有变化的事实）直接对应"只传播上一轮 belief 变化超过阈值的节点"。

### 7.1 不动点计算与收敛性

从抽象代数视角看，Horn clause 系统是一个**半格 (semilattice)** 上的不动点计算：

```
操作器 T: 状态空间 → 状态空间
    T(当前所有已知事实) = 当前所有已知事实 ∪ 新推导出的事实
```

在纯 Horn clause（布尔、单调）下，T 保证在有限步内收敛到唯一最小不动点（Knaster-Tarski 定理）。

Gaia 在两个维度上扩展了这个保证：

- **概率化**：值域从 {0, 1} 扩展到 [0, 1]，需要 damping 保证收敛
- **非单调**：contradiction 和 retraction 打破单调性，不动点可能不唯一

但 Gaia 的一个深层性质是：**系统永远有解。** 节点不可变 + 概率连续 = BP 总能给出一组 belief 值，只是精度不同。

---

## 附录 A：术语对照

| 术语 | Gaia 中的对应 | v2.0 / 当前文档锚点 |
|------|-------------|---------------------|
| Variable (变量) | belief-bearing knowledge node / local canonical node | `docs/foundations/graph-ir.md`, `libs/graph_ir/models.py` |
| Prior (先验) | local/global parameterization 中的 node prior | `docs/foundations/bp-on-graph-ir.md` §2, `libs/graph_ir/models.py:LocalParameterization` |
| Belief (后验信念) | BP 收敛后的 node belief | 本文 §5, `libs/inference/bp.py`, `libs/storage/models.py:BeliefSnapshot` |
| Factor (因子) | local factor node / runtime factor graph factor | `docs/foundations/graph-ir.md`, `libs/graph_ir/models.py:FactorNode`, `libs/inference/factor_graph.py` |
| Factor potential (势函数) | factor compatibility function | 本文 §2, `libs/inference/bp.py:_evaluate_potential()` |
| Noisy-AND | reasoning factor 的 v2.0 目标势函数模型 | 本文 §2.2 |
| Leak probability (ε) | 前提不全为真时的背景兼容度 | 本文 §2.2, `libs/inference/factor_graph.py:_cromwell_clamp()` |
| Factor graph (因子图) | runtime bipartite BP graph | 本文 §5.1, `libs/inference/factor_graph.py` |
| Message passing (消息传递) | BP iteration | 本文 §5.2, `libs/inference/bp.py` |
| Damping (阻尼) | loopy BP stabilization | 本文 §5.3, `libs/inference/bp.py` |
| Convergence (收敛) | max_change < threshold | 本文 §5.3, `libs/inference/bp.py` |
| Gate | 当前 runtime 中关系节点的只读机制；v2.0 目标模型移除此语义 | `docs/foundations/bp-on-graph-ir.md` §4 |

## 附录 B：与相关系统的概率机制对比

| 系统 | 概率机制 | 推理方式 | 扩展性瓶颈 |
|------|---------|---------|-----------|
| **MLN** | 一阶公式 + 权重 → MRF | Gibbs / BP | Grounding: O(N^k) |
| **PSL** | 连续 [0,1] + Hinge-loss MRF | 凸优化 | 仍需 grounding |
| **DeepDive** | 候选事实 + 因子图 | Gibbs sampling | 批处理 |
| **贝叶斯网络** | 条件概率表 | 精确 BP / 变分 | DAG 限制 |
| **Gaia** | 超图即因子图，noisy-AND + leak | Loopy BP (damped) | 无 grounding |
