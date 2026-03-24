# Belief Propagation — 推理超图的结构与算法

> **Status:** Target design — foundation baseline
>
> 本文档定义推理超图（因子图）的数学结构和 Belief Propagation 算法。
> 关于科学推理的认识论基础（为什么用概率、Jaynes 框架），参见 [plausible-reasoning.md](plausible-reasoning.md)。
> 本文档不定义具体的编写语言语法或 Graph IR 字段布局。

## 1. 推理超图的结构

### 1.1 因子图

科学推理中的命题和推理链接形成一个网络。这个网络有精确的数学结构：**因子图（factor graph）** — 一种二部图，包含两种节点：

- **变量节点（variable node）**：代表命题。每个变量有一个先验分布和一个由推理引擎计算的后验信念值。对于二值变量：状态为真（1）或假（0）。
- **因子节点（factor node）**：代表命题之间的约束或推理链接。每个因子连接一组变量子集，通过势函数（potential function）编码它们之间的交互。

```
变量节点 = 命题（携带信念值）
  prior  → 初始合理性，∈ (ε, 1-ε)
  belief → 由 BP 计算的后验合理性

因子节点 = 推理链接（连接多个命题的超边）
  连接一组变量子集
  势函数编码约束语义
```

### 1.2 为什么是超图而非普通图

一个推理步骤通常有**多个前提**共同支撑一个结论：

```
前提₁ ∧ 前提₂ ∧ ... ∧ 前提ₙ → 结论
```

这不是两两之间的关系（普通边），而是多个变量之间的联合约束（超边）。因子节点就是这样的超边 — 它同时连接所有前提和结论。

### 1.3 联合概率的因子分解

所有变量的联合概率分解为因子的乘积：

```
P(x₁, ..., xₙ | I) ∝ ∏ⱼ φⱼ(xⱼ) · ∏ₐ ψₐ(x_Sₐ)
```

其中 φⱼ 是变量 j 的先验（一元因子），ψₐ 是因子 a 在其连接变量子集 Sₐ 上的势函数。势函数不是概率 — 它们无需归一化，仅比值有意义。

这就是 Jaynes 乘法规则的图结构化表达：联合合理性是所有局部约束的乘积。

### 1.4 概率化的 Horn 子句

如果将因子图中的概率强制为 {0, 1}，每条超边退化为：

```
前提₁ ∧ 前提₂ ∧ ... ∧ 前提ₙ → 结论
```

这是 **Horn 子句（Horn Clause）** — 合取蕴含，是 Prolog/Datalog 的基础。比完整命题逻辑弱（没有析取 ∨ 和否定 ¬），但正因为弱，推理是多项式时间的。

加上连续概率后，推理超图成为**概率化的 Horn 逻辑** — 在 Datalog 的基本模式上叠加 [0, 1] 值域和信念传播。

### 1.5 弱三段论作为势函数的设计需求

Polya/Jaynes 的四个弱三段论（参见 [plausible-reasoning.md](plausible-reasoning.md) §1.3-1.4）对因子图上的势函数提出了约束 — 任何正确的势函数设计都必须满足：

| 三段论 | 需求 |
|--------|------|
| 强 (modus ponens) | 前提信念高时，因子到结论的消息推高结论信念 |
| 弱 1 (确认) | 结论信念高时，因子到前提的消息推高前提信念 |
| 弱 2 (tollens) | 结论信念低时，因子到前提的消息压低前提信念 |
| 弱 3 (否认) | 前提信念低时，因子到结论的消息应压低结论信念 |

弱三段论 3 是最关键的设计约束：如果势函数在前提为假时保持沉默（potential = 1.0），该需求不被满足 — 结论将停留在先验值而非被压低。满足此需求的势函数需要一个"泄漏"机制（如 noisy-AND + leak），使得前提为假时因子主动发送抑制性消息。

这四个需求不是设计选择，是 Jaynes 理论的数学推论。满足这些需求的具体势函数方案见 §3。

### 1.6 系统永远有解

推理超图的一个深层性质：**系统永远有解**。

在因子图上运行信念传播，总能给出一组信念值。不存在"不可满足"或"无解"的概念。不完整的信息产生不确定的信念（接近 0.5），矛盾的信息产生竞争的信念（弱者被压低），但系统永远不会崩溃。

这与基于 SAT 求解的系统形成对比 — SAT 可以返回"无解"。概率推理没有"无解"，只有"不确定"。这正是科学推理的本质：我们永远处于不完整信息下，但总能给出当前最合理的信念。

## 2. Sum-Product 消息传递

消息是二维向量 `[p(x=0), p(x=1)]`，始终归一化使得和为 1。

### 算法

```
Initialize: all messages = [0.5, 0.5] (uniform, MaxEnt)
            priors = {var_id: [1-prior, prior]}

Repeat (up to max_iterations):

  1. Compute all variable -> factor messages (exclude-self rule):
     msg(v -> f) = prior(v) * prod_{f' != f} msg(f' -> v)
     Then normalize.

  2. Compute all factor -> variable messages (marginalize):
     msg(f -> v) = sum_{other vars} potential(assignment) * prod_{v' != v} msg(v' -> f)
     Then normalize.

  3. Damp and normalize:
     msg = alpha * new_msg + (1 - alpha) * old_msg
     Default alpha = 0.5.

  4. Compute beliefs:
     b(v) = normalize(prior(v) * prod_f msg(f -> v))
     Output belief = b(v)[1], i.e., p(x=1).

  5. Check convergence:
     If max |new_belief - old_belief| < threshold: stop.
```

关键设计要点：

- **双向消息**：变量到因子和因子到变量。反向抑制（modus tollens）自然产生。
- **排除自身规则（exclude-self rule）**：当变量 v 向因子 f 发送消息时，排除 f 自身的传入消息。这防止了循环自增强。
- **同步调度**：所有新消息都从旧消息计算，然后同时交换。因子排序不影响结果。
- **二维向量归一化**：消息始终和为 1，防止长链中的数值衰减。

### 与 Jaynes 规则的对应关系

| BP 操作 | Jaynes 规则 |
|---|---|
| 联合 = 势与先验的乘积 | 乘法规则 |
| 消息归一化 [p(0) + p(1) = 1] | 加法规则 |
| belief = 先验 × 因子到变量消息的乘积 | Bayes 定理（后验正比于先验 × 似然） |
| 变量到因子消息（排除自身） | 排除当前因子的背景信息 P(H\|X) |
| 因子到变量消息（边缘化） | 对其他变量边缘化后的似然 P(D\|HX) |

在树结构图上，BP 是精确的。在有环图上，它是一种近似。

## 3. 势函数模型

§1.5 给出了势函数必须满足的四条设计约束。本节给出满足这些约束的具体势函数设计。

### 3.1 从条件概率到势函数

势函数（potential function）是一个函数，输入变量的状态组合，输出一个非负权重，表示该组合在此关系下的兼容程度。

关键性质：

- **势函数不是概率** — 不需要归一化，仅比值有意义。
- **势函数 = 1.0 意味着沉默** — 对变量的两个状态给出相同权重，因子不施加任何影响。
- **多个因子的影响通过乘积合并** — 归一化由 BP 的消息传递自动保证。

### 3.2 Noisy-AND + Leak：推理因子的势函数

#### 作者提供的信息

在 Gaia 的创作模型中，作者对一条推理链提供的信息是：

- 各前提 P₁, ..., Pₙ 的先验：π₁, ..., πₙ
- 条件概率 P(C=1 | P₁=1 ∧ ... ∧ Pₙ=1) = p

#### 朴素模型的问题

朴素的势函数在前提不全为真时设 potential = 1.0（沉默）：

```
φ_naive(P₁,...,Pₙ, C):
  all Pᵢ=1, C=1  →  p
  all Pᵢ=1, C=0  →  1-p
  any Pᵢ=0, C=1  →  1.0     ← 沉默
  any Pᵢ=0, C=0  →  1.0     ← 沉默
```

这等价于 P(C | 前提不全为真) = prior(C)。如果 C 的先验是 0.5（MaxEnt 默认值），则前提为假时 C 仍然是 0.5 — 违反 §1.5 的约束 C4（弱三段论 3 失败）。

#### Noisy-AND + Leak

Gaia 的推理链是 **noisy-AND** 语义：所有前提必须同时成立，结论才以概率 p 成立。这是概率图模型文献中 canonical models（Independence of Causal Influence）族的标准成员，与 noisy-OR 对偶。

**Leak probability**（Henrion 1989）编码"前提不全为真时，结论仍然成立的背景概率"。对 Gaia 的推理链，前提是结论的近似必要条件，因此 leak 应极小。默认值 ε = Cromwell 下界（10⁻³）。

```
φ(P₁,...,Pₙ, C):
  all Pᵢ=1, C=1  →  p        (前提全真，支持结论)
  all Pᵢ=1, C=0  →  1-p      (前提全真，不支持结论)
  any Pᵢ=0, C=1  →  ε        (前提不全真，结论仍为真 → 极不兼容)
  any Pᵢ=0, C=0  →  1-ε      (前提不全真，结论为假 → 兼容)
```

完整 CPT 需要 2ⁿ 个参数（n 个前提），noisy-AND + leak 只需要 2 个：p 和 ε。这与 Gaia 的创作模型完全匹配 — 作者只需指定一个条件概率。

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

前提为假时，结论从 0.648 跌到 0.001。朴素模型下只会回到先验值 0.5。这就是 leak 的核心作用：前提为假时因子不再沉默，而是主动压低结论。

#### 与 PGM 文献的关系

Noisy-AND 是 noisy-OR（Pearl 1988, Henrion 1989）的对偶形式。Noisy-OR 用于析取因果模型（任意一个原因可导致结果），noisy-AND 用于合取因果模型（所有条件都必须满足）。Leak probability 是两者共享的标准参数，编码未建模原因的背景概率。

### 3.3 约束因子的势函数

Contradiction 和 equivalence 不是前提→结论的推理，而是命题之间的结构性约束。它们需要专门的势函数。

#### Contradiction（互斥约束）

语义：C_contra ∧ A₁ ∧ ... ∧ Aₙ → ⊥（矛盾成立且所有命题都为真是不可能的）。

```
φ_contradiction(C_contra, A₁, ..., Aₙ):
  C_contra=1, all Aᵢ=1   →  ε      (矛盾成立且都真 → 几乎不可能)
  其他所有组合              →  1      (无约束)
```

三个方向的消息自然涌现：

1. **C_contra 可信 + B 可信 → A 被压低**
2. **弱证据先让步**（prior odds 低的变量在 odds 空间被同一似然比影响更大）
3. **A 和 B 都很强 → C_contra 被压低**（系统质疑矛盾本身）

第 3 点是关键：如果 A 和 B 都有压倒性证据为真，合理的推理应该质疑矛盾声明本身 — 这正是 Jaynes 一致性要求的体现。

#### Equivalence（等价约束）

语义：C_equiv 为真时，A 和 B 应具有相同的真值。

```
φ_equivalence(C_equiv, A, B):
  C_equiv=1, A=B    →  1-ε    (等价成立 + 一致 → 高兼容)
  C_equiv=1, A≠B    →  ε      (等价成立 + 不一致 → 低兼容)
  C_equiv=0, 任意    →  1      (不等价 → 无约束)
```

效果：A 和 B 一致时，C_equiv 被推高（证据确认等价）；A 和 B 分歧时，C_equiv 被压低（系统质疑等价关系）。

### 3.4 各算子类型的合规性验证

五种推理算子（参见 [scientific-ontology.md](scientific-ontology.md) §6）对 §1.5 四条约束的满足情况：

| 算子类型 | C1 (前提真→支持) | C2 (结论真→前提↑) | C3 (结论假→前提↓) | C4 (前提假→结论↓) | 势函数 |
|---------|:---:|:---:|:---:|:---:|------|
| entailment | ✓ | ✓ | ✓ | 通常沉默 | noisy-AND + leak 或 p≈1.0 |
| induction | ✓ | ✓ | ✓ | ✓ | noisy-AND + leak, p < 1.0 |
| abduction | ✓ | ✓ | ✓ | ✓ | noisy-AND + leak |
| equivalent | ✓ | ✓ | ✓ | ✓ (质疑关系) | 约束势函数 |
| contradict | ✓ | ✓ | ✓ | ✓ (质疑关系) | 约束势函数 |

**entailment 的 C4 为什么通常沉默是正确的：** 对于 instantiation（从全称到实例），¬∀x.P(x) ⊬ ¬P(a) — 全称命题为假不代表每个实例都假。单个反例强力否证全称（C3），但全称为假对实例无约束（C4）。这是 Popper/Jaynes 对归纳的标准观点。

## 4. Loopy BP 与收敛性

现实世界的因子图常包含环。loopy BP 通过迭代消息传递直到信念稳定来处理这种情况。

**阻尼（damping）** 防止在有环图上的振荡：

```
msg_new = alpha * computed_msg + (1 - alpha) * msg_old
```

当 alpha = 0.5（默认值）时，每次更新向新值移动一半。阻尼以收敛速度换取稳定性。

loopy BP 最小化 **Bethe 自由能**，这是真实自由能的变分近似。在稀疏图上，这种近似通常较好。系统始终产生一组信念 — 不存在"不可满足"的状态。不完整的信息产生不确定的信念，而非系统失败。

**Cromwell 规则**在两处强制执行：

1. **在构造时**：所有先验和条件概率都钳制在 [ε, 1-ε]，其中 ε = 10⁻³。
2. **在势函数中**：泄漏参数本身就是 Cromwell 下界，确保没有状态组合具有零势。

这防止了零概率阻断所有未来证据的退化更新。

## 5. 构造性操作 vs BP 算子

以下区分是强制性的：

### 5.1 图构造/研究操作

这些操作创建或提议新的知识结构：

- 抽象（abstraction）
- 泛化（generalization）
- 隐含前提发现（hidden premise discovery）
- 独立证据审计（independent evidence audit）

它们**不是**自动的 BP 边类型。它们属于审查/策展流程——其结果可能最终产生新的 BP 因子，但操作本身不直接参与信念传播。

### 5.2 BP 算子族

这些算子决定了图被接受后信念更新如何传播：

- entailment（蕴含）
- induction（归纳）
- abduction（溯因）
- equivalent（等价）
- contradict（矛盾）

每种算子对应不同的势函数。Jaynes 式弱三段论是这些 BP 算子上的合约，不是新的语言声明。

算子类型的完整语义定义见 [scientific-ontology.md](scientific-ontology.md) §6。

## 6. 什么进入 BP

### 6.1 承载 BP 的对象

以下对象在审查/接受后可以进入 BP：

- Claim（封闭断言——唯一的 BP 承载类别，包括其结构特化：Observation、Measurement 等）
- 通过 Template 从 Setting/Question 实例化而来的 Claim
- 已接受的 equivalent / contradict 关系

### 6.2 非 BP 对象

以下对象**不**直接进入 BP：

- Template
- Setting
- Question
- infer 阶段的推理链接（尚未经过审查确认具体类型）
- candidate 阶段的推理链接（尚未经过充分验证）
- 审查发现
- 策展建议
- 循环审计制品
- 独立证据审计报告

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Pearl, J. *Probabilistic Reasoning in Intelligent Systems* (1988)
- Yedidia, Freeman, Weiss. "Understanding Belief Propagation and its Generalizations" (2003)
- Henrion, M. "Some Practical Issues in Constructing Belief Networks" (1989)
