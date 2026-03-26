# 置信传播

> **Status:** Target design
>
> **上游依赖：**
> - [01-plausible-reasoning.md](01-plausible-reasoning.md) — Jaynes 框架、弱三段论 C1-C4
> - [01a-jaynes-maxent-grounding.md](01a-jaynes-maxent-grounding.md) — 从约束到 posterior 的 MaxEnt / Min-KL 落地
> - [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) — 因子图、逻辑算子
> - [03-coarse-reasoning.md](03-coarse-reasoning.md) — 粗推理算子

本文档定义因子图上的置信传播（Belief Propagation, BP）算法。BP 是因子图上的通用消息传递算法，与具体的势函数选择无关。

---

## 1. Sum-Product 消息传递

因子图由变量节点（命题）和因子节点（逻辑约束）组成（参见 [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) §1）。BP 通过在变量节点和因子节点之间传递消息来计算每个变量的边缘后验信念。

消息是二维向量 `[p(x=0), p(x=1)]`，始终归一化使得和为 1。

### 1.1 算法

```
Initialize: all messages = [0.5, 0.5] (uniform, MaxEnt)
            priors = {var_id: [1-prior, prior]}

Repeat (up to max_iterations):

  1. Variable → factor messages (exclude-self rule):
     msg(v → f) = π(v) · ∏_{f' ≠ f} msg(f' → v)
     Then normalize.

  2. Factor → variable messages (marginalize):
     msg(f → v) = ∑_{x_other} ψ(x_v, x_other) · ∏_{v' ≠ v} msg(v' → f)
     Then normalize.

  3. Damp and normalize:
     μ^(t+1) = α · μ^(new) + (1-α) · μ^(t)
     Default α = 0.5.

  4. Compute beliefs:
     b(v) = normalize( π(v) · ∏_f msg(f → v) )
     Output belief = b(v)[1], i.e., p(x=1).

  5. Check convergence:
     If max|new_belief - old_belief| < threshold: stop.
```

### 1.2 消息公式详解

**Variable → factor 消息：** 变量 v 向因子 f 发送的消息是 v 的先验 π(v) 乘以**除 f 之外**所有连接因子发来消息的逐元素乘积：

```
msg(v → f)[x] = π(v)[x] · ∏_{f' ∈ ne(v) \ {f}} msg(f' → v)[x]
```

其中 ne(v) 是 v 的所有相邻因子节点。这条消息汇总了"从 f 以外的其他因子收到的关于 v 的全部信息"。

**Factor → variable 消息：** 因子 f 向变量 v 发送的消息是对因子势函数在其他变量上做边缘化：

```
msg(f → v)[x_v] = ∑_{x_{ne(f)\{v}}} ψ_f(x_v, x_{ne(f)\{v}}) · ∏_{v' ∈ ne(f) \ {v}} msg(v' → f)[x_{v'}]
```

其中 ne(f) 是 f 的所有相邻变量节点。这条消息汇总了"因子 f 根据其势函数和其他输入变量的信念，对 v 应取何值的意见"。

**信念计算：** 每个变量的后验信念正比于先验乘以所有连接因子消息的乘积：

```
b(v) ∝ π(v) · ∏_{f ∈ ne(v)} msg(f → v)
```

这是 Bayes 定理在因子图上的直接表达：后验 ∝ 先验 × 似然。

### 1.3 自由参数

信念计算公式 b(v) ∝ π(v) · ∏ msg(f→v) 中，消息由势函数 ψ 驱动。因此系统的自由参数取决于因子图的类型：

- **细因子图**（所有因子都是逻辑算子，p=1）：势函数由真值表唯一确定（参见 [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) §1.4），节点先验 π 是**唯一的自由参数类**。
- **粗因子图**（包含粗推理算子，p<1）：势函数携带参数 p（参见 [03-coarse-reasoning.md](03-coarse-reasoning.md) §2），p 作为**第二自由参数类**加入系统。

### 1.4 同步调度

所有新消息都从旧消息计算，然后同时交换。因子的排序不影响结果。同步调度保证了更新的确定性——给定相同的初始条件，产生相同的消息序列。

### 1.5 排除自身规则（Exclude-Self Rule）

变量 v 向因子 f 发送消息时，必须排除 f 自身发来的消息。这防止了循环自增强：如果 v 把 f 的消息包含进去再发回给 f，f 会"听到自己的回声"，导致信念无根据地膨胀。排除自身规则确保每条消息只传递"来自其他路径的独立信息"。

### 1.6 与 Jaynes 规则的对应关系

| BP 操作 | Jaynes 规则 |
|---|---|
| 联合 = 势与先验的乘积 | 乘法规则 |
| 消息归一化 [p(0) + p(1) = 1] | 加法规则 |
| belief = 先验 × 因子到变量消息的乘积 | Bayes 定理（后验正比于先验 × 似然） |
| 变量到因子消息（排除自身） | 排除当前因子的背景信息 P(H\|X) |
| 因子到变量消息（边缘化） | 对其他变量边缘化后的似然 P(D\|HX) |

在树结构图上，BP 精确计算边缘后验。在有环图上，BP 是一种变分近似。

## 2. 消息传递语义

§1 定义了通用的 BP 算法。本节展示 BP 在我们的具体算子上产生什么行为。

### 2.1 逻辑算子上的消息传递

逻辑算子（蕴含、合取、析取、否定）的势函数完全由真值表确定：一致状态 ψ=1，不一致状态 ψ=0（参见 [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) §2）。这些 0/1 势函数使 BP 消息传递产生确定性逻辑行为。

以蕴含 A→C 为例。蕴含的势函数为：

| A | C | ψ |
|---|---|---|
| 1 | 1 | 1 |
| 1 | 0 | 0 |
| 0 | 1 | 1 |
| 0 | 0 | 1 |

**正向消息（A→C）：** 因子向 C 发送的消息由对 A 的边缘化产生：

```
msg(f→C)[c] = ∑_a ψ(a,c) · msg(A→f)[a]
```

设 msg(A→f) = [q, 1-q]，其中 q = P(A=0)，则：

```
msg(f→C)[C=1] = ψ(0,1)·q + ψ(1,1)·(1-q) = 1·q + 1·(1-q) = 1
msg(f→C)[C=0] = ψ(0,0)·q + ψ(1,0)·(1-q) = 1·q + 0·(1-q) = q
```

归一化后：msg(f→C) ∝ [1, q]。当 A 有高信念时（q 小，即 P(A=0) 小），C=0 的消息权重接近 0，C=1 被强烈偏好。直觉：ψ(1,1)/ψ(1,0) = 1/0——一旦 A=1 确定，C=1 是唯一一致的状态。

**反向消息（C→A）：** 因子向 A 发送的消息由对 C 的边缘化产生：

```
msg(f→A)[a] = ∑_c ψ(a,c) · msg(C→f)[c]
```

设 msg(C→f) = [r, 1-r]，其中 r = P(C=0)，则：

```
msg(f→A)[A=1] = ψ(1,0)·r + ψ(1,1)·(1-r) = 0·r + 1·(1-r) = 1-r
msg(f→A)[A=0] = ψ(0,0)·r + ψ(0,1)·(1-r) = 1·r + 1·(1-r) = 1
```

归一化后：msg(f→A) ∝ [1, 1-r]。当 C 的信念较低时（r 大，即 P(C=0) 大），A=1 的消息权重下降。这正是 **modus tollens** 行为：结论为假使前提更不可信。

### 2.2 粗推理算子上的消息传递

粗推理算子连接前提 M 和结论 C，携带参数 p，势函数中 ψ(1,0) = f(p)（参见 [03-coarse-reasoning.md](03-coarse-reasoning.md) §2）：

| M | C | ψ |
|---|---|---|
| 1 | 1 | 1 |
| 1 | 0 | f(p) |
| 0 | 1 | 1 |
| 0 | 0 | 1 |

**正向消息（M→C）：** 设 msg(M→f) = [q, 1-q]，则：

```
msg(f→C)[C=1] = 1·q + 1·(1-q) = 1
msg(f→C)[C=0] = 1·q + f(p)·(1-q)
```

归一化后：msg(f→C) ∝ [1, q + f(p)·(1-q)]。

当 M 有高信念时（q 小），msg(f→C)[C=0] ≈ f(p)。p 越大，f(p) 越小，C=0 越被抑制，C 越被支持。这就是粗推理的正向支持：前提成立时，结论获得与 p 成正比的支持强度。

**反向消息（C→M）：** 设 msg(C→f) = [r, 1-r]，则：

```
msg(f→M)[M=1] = f(p)·r + 1·(1-r) = 1 - r·(1 - f(p))
msg(f→M)[M=0] = 1·r + 1·(1-r) = 1
```

归一化后：msg(f→M) ∝ [1, 1 - r·(1-f(p))]。

- 当 C 有高信念时（r 小），msg(f→M)[M=1] ≈ 1，M 获得部分支持——弱溯因。
- 当 C 的信念较低时（r 大），msg(f→M)[M=1] 下降，M 被抑制——modus tollens 行为。

与逻辑蕴含的对比：逻辑蕴含中 ψ(1,0) = 0，反向抑制是绝对的（C=0 时 A=1 完全被禁止）。粗推理中 ψ(1,0) = f(p) > 0，反向抑制是部分的——强度由 p 控制。

### 2.3 弱三段论的实现

[01-plausible-reasoning.md](01-plausible-reasoning.md) §1.3 定义了四条弱三段论准则 C1-C4。[03-coarse-reasoning.md](03-coarse-reasoning.md) §3 论证了粗推理算子的势函数满足这些准则。本节从 BP 消息传递的角度展示 C1-C4 如何自然涌现。

**C1（前提真 → 结论信念上升）：** §2.2 的正向消息分析表明，当 M 信念高时，因子向 C 传递强支持消息。这是 BP 正向消息传播的直接结果。

**C2（结论真 → 前提信念上升）：** §2.2 的反向消息分析表明，当 C 信念高时，msg(f→M)[M=1] 接近 1，M 获得支持。这是 Bayes 定理的自然结果：结论为真提升了对前提的后验信念。

**C3（结论假 → 前提信念下降）：** §2.2 的反向消息分析表明，当 C 信念低（r 大）时，msg(f→M)[M=1] 下降。这就是 modus tollens——结论为假削弱前提。

**C4（前提假 → 结论变弱）：** 当 M 信念低时，正向消息中 M=1 的权重低，因子对 C 的支持减弱，C 回落到其先验水平。结论失去这条推理路径的支持。

四条准则不需要特殊设计——它们是 BP 在满足约束的势函数上运行的自然结果。在逻辑算子（p=1）上同样成立（参见 §2.1 的正向/反向消息分析），只是效果更强烈（0/1 势函数产生确定性传播）。

## 3. 收敛性

### 3.1 Loopy BP

在树结构因子图上，BP 在有限步内精确收敛到真实的边缘后验。但现实世界的因子图通常包含环（多条推理路径汇聚到同一命题）。**Loopy BP** 在有环图上迭代运行消息传递直到信念稳定——不保证收敛，但在实践中通常有效。

### 3.2 阻尼（Damping）

阻尼防止有环图上的振荡：

```
μ^(t+1) = α · μ^(new) + (1-α) · μ^(t)
```

当 α = 0.5（默认值）时，每次更新向新值移动一半。阻尼以收敛速度换取稳定性。α 越小越稳定但越慢。

### 3.3 Bethe 自由能

Loopy BP 的不动点对应 **Bethe 自由能**的驻点——这是真实自由能的变分近似。在稀疏图上（每个节点的连接度不太高），Bethe 近似通常较好。这为 loopy BP 提供了理论依据：即使不保证收敛，收敛时的结果也有明确的变分意义。

### 3.4 收敛判据

实践中的收敛判据：

```
max_v |b^(t+1)(v) - b^(t)(v)| < threshold
```

当所有变量的信念变化幅度都小于阈值时，算法终止。

### 3.5 系统永远有解

在因子图上运行 BP，总能给出一组信念值。不存在"不可满足"或"无解"的概念。不完整的信息产生不确定的信念（接近 0.5），矛盾的信息产生竞争的信念（弱者被压低），但系统永远不会崩溃。这与基于 SAT 求解的系统形成对比——概率推理没有"无解"，只有"不确定"。

---

## 跨层引用

- **上游（theory 层）**：[01-plausible-reasoning.md](01-plausible-reasoning.md) — Jaynes 框架、Cox 定理、弱三段论 C1-C4；[02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) — 因子图结构、四种逻辑算子及其势函数；[03-coarse-reasoning.md](03-coarse-reasoning.md) — 粗推理算子定义、参数 p 的含义
- **BP 层**：[../bp/potentials.md](../bp/potentials.md) — f(p) 的具体函数形式；[../bp/inference.md](../bp/inference.md) — BP 推理的工程实现细节
- **源码**：`libs/inference/bp.py`（BP 算法实现）、`libs/inference/factor_graph.py`（因子图数据结构）

## 参考文献

- Kschischang, Frey, Loeliger. "Factor Graphs and the Sum-Product Algorithm" (2001)
- Yedidia, Freeman, Weiss. "Understanding Belief Propagation and its Generalizations" (2003)
- Pearl, J. *Probabilistic Reasoning in Intelligent Systems* (1988)
