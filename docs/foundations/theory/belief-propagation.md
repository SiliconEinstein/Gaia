# Belief Propagation — 推理超图上的概率推理

> **Status:** Target design — foundation baseline
>
> 本文档定义如何在推理超图上定义概率并计算信念。
> 关于推理超图的结构（知识对象、算子类型、因子图形式），参见 [reasoning-hypergraph.md](reasoning-hypergraph.md)。
> 关于为什么用概率来描述科学推理（Jaynes 框架），参见 [plausible-reasoning.md](plausible-reasoning.md)。
> 本文档不定义具体的编写语言语法或 Graph IR 字段布局。

## 1. Jaynes 规则与建模缺口

Jaynes 理论（参见 [plausible-reasoning.md](plausible-reasoning.md)）给出了概率推理的**规则** — 乘法规则、加法规则、Bayes 定理。这些规则是推理的微积分：它告诉你如何从已知概率计算未知概率。

但规则本身不构成一个可计算的系统。类比：牛顿给你 F=ma，但你还需要具体的力学定律（F=-kx 弹簧，F=GMm/r² 万有引力）才能解具体问题。Jaynes 的规则是 F=ma，我们还需要"力学定律"。

### 1.1 Jaynes 确定了什么

对于一条推理链 P₁ ∧ P₂ → C，Jaynes 的规则确定了：

- **前提全真时**：P(C=1 | P₁=1, P₂=1) = p（由作者给定）
- **反向更新**：Bayes 定理唯一地决定了 P(P₁ | C) 如何从 P(C | P₁) 计算
- **多因子合并**：乘法规则决定了多条推理链的影响如何组合

### 1.2 Jaynes 没有确定什么

关键缺口：**前提为假时，结论怎么办？**

```
P(C=1 | P₁=0) = ?
```

Jaynes 的规则对此没有唯一答案 — 这是一个**建模选择**。不同的选择导致不同的系统行为：

- **沉默**：P(C | P₁=0) = prior(C) — 前提倒了，结论不受影响，回到先验
- **主动压低**：P(C | P₁=0) = ε — 前提倒了，结论被强力压低

哪个是对的？Polya/Jaynes 的弱三段论 4（参见 [plausible-reasoning.md](plausible-reasoning.md) §1.3-1.4）给出了判据：

| 约束 | 来源 | 需求 |
|------|------|------|
| C1 | 三段论 1 (modus ponens) | 前提真 → 结论信念上升 |
| C2 | 三段论 2 (弱确认) | 结论真 → 前提信念上升 |
| C3 | 三段论 3 (modus tollens) | 结论假 → 前提信念下降 |
| C4 | 三段论 4 (弱否认) | **前提假 → 结论信念下降** |

C1–C3 在任何使用 Jaynes 规则的系统中自动满足。**C4 要求"主动压低"，排除了"沉默"。** 这就是建模缺口的约束：Jaynes 的规则不唯一确定模型，但弱三段论缩小了选择空间。

## 2. Noisy-AND + Leak：填补缺口的模型

推理超图中的前提是联合必要条件 — 所有前提必须同时成立，结论才获得支撑（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §4.1）。这一合取结构直接决定了概率模型的形式。

### 2.1 作者提供的信息

在 Gaia 中，作者对一条推理链提供的信息是：

- 各前提 P₁, ..., Pₙ 的先验：π₁, ..., πₙ
- 条件概率 P(C=1 | P₁=1 ∧ ... ∧ Pₙ=1) = p

这只定义了"前提全真"这一种情况。对于 n 个二值前提 + 1 个结论，完整的条件概率表（CPT）需要 2ⁿ 个参数。作者只给了 1 个。

### 2.2 Noisy-AND + Leak 如何唯一确定模型

合取语义对应概率图模型文献中的 **noisy-AND** 模型（Independence of Causal Influence 族的标准成员，与 noisy-OR 对偶；Pearl 1988, Henrion 1989）。

**Leak probability** ε 编码"前提不全为真时，结论仍然成立的极小背景概率"。默认值 ε = Cromwell 下界（10⁻³）。

一旦选定 noisy-AND + leak，整个模型由 (p, ε) **唯一确定**，没有额外自由度：

```
前提全真, 结论真  →  p        (作者给定)
前提全真, 结论假  →  1-p      (加法规则：必然)
前提不全真, 结论真  →  ε      (leak：极小背景概率)
前提不全真, 结论假  →  1-ε    (加法规则：必然)
```

ε 又是 Cromwell 下界（系统常数），所以**作者只需给 p，一切就唯一确定了**。2ⁿ 个参数的空间被压缩到 1 个。

### 2.3 为什么沉默模型是错的

对比朴素的"沉默"模型：

```
前提不全真, 结论真  →  1.0     ← 沉默（不施加影响）
前提不全真, 结论假  →  1.0     ← 沉默
```

这等价于 P(C | 前提不全真) = prior(C)。如果 C 的先验是 0.5（MaxEnt），则前提为假时 C 仍然是 0.5 — 违反 C4。

### 2.4 四三段论验证

取 π₁=0.9, π₂=0.8, p=0.9, ε=0.001：

**C 的边缘概率**（乘法规则 + 加法规则）：

```
P(C=1) = p · π₁π₂ + ε · (1 - π₁π₂)
       = 0.9 × 0.72 + 0.001 × 0.28
       = 0.648
```

**C1** — P(C=1 | P₁=1, P₂=1) = p = 0.9 ✓

**C2** — P(P₁=1 | C=1)：

```
P(C=1 | P₁=1) = p·π₂ + ε·(1-π₂) = 0.7202
P(P₁=1 | C=1) = 0.7202 × 0.9 / 0.648 = 0.9997 > 0.9 ✓
```

**C3** — P(P₁=1 | C=0)：

```
P(C=0 | P₁=1) = (1-p)·π₂ + (1-ε)·(1-π₂) = 0.2798
P(P₁=1 | C=0) = 0.2798 × 0.9 / 0.352 = 0.716 < 0.9 ✓
```

**C4** — P(C=1 | P₁=0) = ε = 0.001 ✓

前提为假时，结论从 0.648 跌到 0.001。沉默模型下只会回到先验值 0.5。

### 2.5 约束算子的模型

Contradiction 和 equivalence 不是前提→结论的推理，而是命题之间的结构性约束（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §7.3）。它们有各自的固定模型：

**Contradiction**（互斥约束）— 矛盾成立且所有命题都为真几乎不可能：

```
C_contra=1, all Aᵢ=1   →  ε
其他所有组合              →  1
```

如果 A 和 B 都有压倒性证据为真，系统会质疑矛盾声明本身 — 这正是 Jaynes 一致性要求的体现。

**Equivalence**（等价约束）— 等价成立时，真值应一致：

```
C_equiv=1, A=B    →  1-ε
C_equiv=1, A≠B    →  ε
C_equiv=0, 任意    →  1
```

约束算子的模型也由 ε（Cromwell 下界）唯一确定，无额外参数。

### 2.6 合规性总结

五种推理算子（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §7）对四条约束的满足情况：

| 算子类型 | C1 | C2 | C3 | C4 | 自由参数 |
|---------|:---:|:---:|:---:|:---:|------|
| entailment | ✓ | ✓ | ✓ | 通常沉默 | p（≈1.0） |
| induction | ✓ | ✓ | ✓ | ✓ | p（< 1.0） |
| abduction | ✓ | ✓ | ✓ | ✓ | p |
| equivalent | ✓ | ✓ | ✓ | ✓ (质疑关系) | 无（仅 ε） |
| contradict | ✓ | ✓ | ✓ | ✓ (质疑关系) | 无（仅 ε） |

**entailment 的 C4 为什么通常沉默是正确的：** 对于 instantiation（从全称到实例），¬∀x.P(x) ⊬ ¬P(a) — 全称命题为假不代表每个实例都假。这是 Popper/Jaynes 对归纳的标准观点。

## 3. Sum-Product 消息传递

§2 定义了每个因子节点的局部模型。本节描述如何在整个因子图（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §5）上，通过消息传递从局部模型计算全局信念。

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

**系统永远有解**：在因子图上运行 BP，总能给出一组信念值。不存在"不可满足"或"无解"的概念。不完整的信息产生不确定的信念（接近 0.5），矛盾的信息产生竞争的信念（弱者被压低），但系统永远不会崩溃。这与基于 SAT 求解的系统形成对比 — 概率推理没有"无解"，只有"不确定"。

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Pearl, J. *Probabilistic Reasoning in Intelligent Systems* (1988)
- Yedidia, Freeman, Weiss. "Understanding Belief Propagation and its Generalizations" (2003)
- Henrion, M. "Some Practical Issues in Constructing Belief Networks" (1989)
