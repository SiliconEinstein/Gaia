# Belief Propagation — 推理超图的结构与算法

> **Status:** Target design — foundation baseline
>
> 本文档定义推理超图（因子图）的数学结构和 Belief Propagation 算法。
> 关于科学推理的认识论基础（为什么用概率、Jaynes 框架），参见 [plausible-reasoning.md](plausible-reasoning.md)。
> 本文档不定义具体的编写语言语法、Graph IR 字段布局或特定的因子势函数公式。

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

这四个需求不是设计选择，是 Jaynes 理论的数学推论。具体的势函数方案（如何满足这些需求）属于实现层面。

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

## 3. Loopy BP 与收敛性

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

## 4. 构造性操作 vs BP 算子

以下区分是强制性的：

### 4.1 图构造/研究操作

这些操作创建或提议新的知识结构：

- 抽象（abstraction）
- 泛化（generalization）
- 隐含前提发现（hidden premise discovery）
- 独立证据审计（independent evidence audit）

它们**不是**自动的 BP 边类型。它们属于审查/策展流程——其结果可能最终产生新的 BP 因子，但操作本身不直接参与信念传播。

### 4.2 BP 算子族

这些算子决定了图被接受后信念更新如何传播：

- entailment（蕴含）
- induction（归纳）
- abduction（溯因）
- equivalent（等价）
- contradict（矛盾）

每种算子对应不同的势函数。Jaynes 式弱三段论是这些 BP 算子上的合约，不是新的语言声明。

算子类型的完整语义定义见 [scientific-ontology.md](scientific-ontology.md) §6。

## 5. 什么进入 BP

### 5.1 承载 BP 的对象

以下对象在审查/接受后可以进入 BP：

- Claim（封闭断言——唯一的 BP 承载类别，包括其结构特化：Observation、Measurement 等）
- 通过 Template 从 Setting/Question 实例化而来的 Claim
- 已接受的 equivalent / contradict 关系

### 5.2 非 BP 对象

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
