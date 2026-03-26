# 信念传播：因子图上的近似推理

> **Derivation chain position:** Layer 3 — Computational Methods
> Factor Graphs → **[this document]**
>
> 本文档定义信念传播（Belief Propagation）作为因子图上的近似推理算法。
> BP 是一种计算方法——不是 Jaynes 理论本身。
> 在树结构图上，BP 给出精确结果。在含环图上，BP 是近似的（Bethe 自由能）。
> 依赖 `06-factor-graphs.md` 的因子图定义和势函数。

> **Status:** Target design
>
> **上游依赖：**
> - [01-plausible-reasoning.md](01-plausible-reasoning.md) — Jaynes 框架、弱三段论
> - [02-maxent-grounding.md](02-maxent-grounding.md) — 从约束到 posterior 的 MaxEnt / Min-KL 落地
> - [06-factor-graphs.md](06-factor-graphs.md) — 因子图、算子势函数

本文档定义因子图上的置信传播（Belief Propagation, BP）算法。BP 是因子图上的通用消息传递算法，与具体的势函数选择无关。BP 不是 Jaynes 理论的一部分——它是一种计算方法，用于在因子图上近似计算边缘后验。在树结构图上，BP 给出精确的边缘后验；在含环图上，BP 是一种变分近似，最小化 Bethe 自由能。

这里要先区分两个层次：

- [03-propositional-operators.md](03-propositional-operators.md) 中的 `↝` 是精确 Jaynes 语义下的 coarse summary。
- [06-factor-graphs.md](06-factor-graphs.md) 中的 ↝ 因子是对这个 summary 的**编译实现**。

因此，本节讨论的是：**BP 如何在这组编译后的局部因子上近似边缘化一个联合分布。**

---

## 1. Sum-Product 消息传递

因子图由变量节点（命题）和因子节点（逻辑约束）组成（参见 [06-factor-graphs.md](06-factor-graphs.md) §1）。BP 通过在变量节点和因子节点之间传递消息来计算每个变量的边缘后验信念。

消息是二维向量 `[p(x=0), p(x=1)]`，始终归一化使得和为 1。

### 1.1 算法

```
Initialize: all messages = [0.5, 0.5] (uniform, neutral)
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

这里的 `[0.5, 0.5]` 只是一个**中性初始化**，不应与 [02-maxent-grounding.md](02-maxent-grounding.md) 中的 MaxEnt posterior 混淆。真正的 posterior 由整张图的联合分布和边缘化规则决定，而不是由初始消息直接给出。

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

这在结构上对应于 `posterior ∝ prior × likelihood`。在树图上，这个对应给出精确的边缘后验；在含环图上，它只是 BP 的局部近似更新形式。

### 1.3 自由参数

信念计算公式 b(v) ∝ π(v) · ∏ msg(f→v) 中，消息由势函数 ψ 驱动。因此系统的自由参数取决于因子图的类型：

- **细因子图**（所有因子都是确定性算子）：势函数由真值表唯一确定（参见 [06-factor-graphs.md](06-factor-graphs.md) §3），节点先验 π 是**唯一的自由参数类**。
- **粗因子图**（包含 ↝（软蕴含）算子）：势函数携带参数 (p₁, p₂)（参见 [06-factor-graphs.md](06-factor-graphs.md) §3.7），(p₁, p₂) 作为**第二自由参数类**加入系统。

### 1.4 同步调度

所有新消息都从旧消息计算，然后同时交换。因子的排序不影响结果。同步调度保证了更新的确定性——给定相同的初始条件，产生相同的消息序列。

### 1.5 排除自身规则（Exclude-Self Rule）

变量 v 向因子 f 发送消息时，必须排除 f 自身发来的消息。这防止了循环自增强：如果 v 把 f 的消息包含进去再发回给 f，f 会"听到自己的回声"，导致信念无根据地膨胀。排除自身规则确保每条消息只传递"来自其他路径的独立信息"。

### 1.6 与 Jaynes 规则的对应关系

本表展示 BP 操作与 Jaynes 规则的**结构对应**。它们说明 BP 为什么能够近似实现 Jaynes 式 posterior 计算。
这种对应在树结构图上是精确的；在含环图上，BP 只是 Bethe 近似下的局部消息传递，不应被误解为 Jaynes 规则本身。

| BP 操作 | Jaynes 规则 |
|---|---|
| 联合 = 势与先验的乘积 | 乘法规则给出的未归一化 posterior 结构 |
| 消息归一化 [p(0) + p(1) = 1] | 加法规则 |
| belief = 先验 × 因子到变量消息的乘积 | 后验 ∝ 先验 × 似然 的局部实现 |
| 变量到因子消息（排除自身） | 排除当前因子后的背景信息汇总 |
| 因子到变量消息（边缘化） | 对其他变量边缘化后的局部 likelihood |

在树结构图上，BP 精确计算边缘后验。在有环图上，BP 是一种变分近似。

### 1.7 证据如何进入 BP

为了与 [02-maxent-grounding.md](02-maxent-grounding.md) 中的 Jaynes 更新语义保持一致，证据必须作为**额外的局部 likelihood** 进入，而不是通过修改消息公式进入。

- **硬证据** `X=x*`：给变量 `X` 添加一个 unary delta factor，或等价地直接 clamp 该变量

```text
λ_E(X) = 1[X = x*]
```

- **软证据**：给变量或局部子集添加相应的 likelihood factor

```text
λ_E(x_S) ∝ P(E | x_S)
```

然后新的后验是：

```text
P(x | E, I) ∝ P(x | I) · λ_E(x)
```

BP 只是在这个更新后的联合分布上近似边缘化。  
也就是说：

- **条件化 / Min-KL 选择原则** 属于 Jaynes 理论层
- **消息传递** 属于计算层

## 2. 消息传递语义

§1 定义了通用的 BP 算法。本节展示 BP 在我们的具体算子上产生什么行为。

### 2.1 逻辑算子上的消息传递

逻辑算子（蕴含、合取、析取、否定）的势函数完全由真值表确定：一致状态 ψ=1，不一致状态 ψ=0（参见 [06-factor-graphs.md](06-factor-graphs.md) §2）。这些 0/1 势函数使 BP 消息传递产生确定性逻辑行为。

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

归一化后：msg(f→C) ∝ [q, 1]。当 A 有高信念时（q 小，即 P(A=0) 小），C=0 的消息权重接近 0，C=1 被强烈偏好。直觉：ψ(1,1)/ψ(1,0) = 1/0——一旦 A=1 确定，C=1 是唯一一致的状态。

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

### 2.2 ↝（软蕴含）算子上的消息传递

↝（软蕴含）算子连接前提 M 和结论 C，携带参数 (p₁, p₂)（势函数定义见 [06-factor-graphs.md](06-factor-graphs.md) §3.7，参数语义见 [03-propositional-operators.md](03-propositional-operators.md) §4）：

| M | C | ψ |
|---|---|---|
| 1 | 1 | p₁ |
| 1 | 0 | 1−p₁ |
| 0 | 0 | p₂ |
| 0 | 1 | 1−p₂ |

其中 p₁ = 近似充分性，p₂ = 局部必要性。按 [03-propositional-operators.md](03-propositional-operators.md) §4 的口径，它们首先是未展开子结构在接口 `(M,C)` 上的有效条件统计；到本层被编译成一个局部、按行归一化的因子后，在孤立极限下与对应的条件通道一致。

按照 [03-propositional-operators.md](03-propositional-operators.md) §4 的定义，↝ 还要求：

```text
p₁ + p₂ > 1
```

即 `P_eff(C=1|M=1) > P_eff(C=1|M=0)`。因此这里分析的 ↝ 始终是**正支持通道**；若某条边表现为负支持，应在理论层改写为 `M ↝ ¬C`。

同时要注意：在整张粗因子图里，真实的全局后验条件概率由所有相邻因子共同决定，因此这里的 `(p₁,p₂)` 不应被机械理解为最终整图上的 `P(C|M)`；它们是局部支持因子的参数。

**正向消息（M→C）：** 设 msg(M→f) = [q, 1-q]（q = P(M=0)），则：

```
msg(f→C)[C=1] = ψ(0,1)·q + ψ(1,1)·(1-q) = (1−p₂)·q + p₁·(1-q)
msg(f→C)[C=0] = ψ(0,0)·q + ψ(1,0)·(1-q) = p₂·q + (1−p₁)·(1-q)
```

归一化后，消息向量按 `[C=0, C=1]` 排列：

- 当 M 有高信念时（q 小），`msg(f→C) ≈ [1−p₁, p₁]`。p₁ 越大，C=1 越被偏好——这就是软蕴含的正向支持。
- 当 M 信念低时（q 大），`msg(f→C) ≈ [p₂, 1−p₂]`。当 p₂ = 0.5 时消息接近均匀——前提为假时不提供信息（MaxEnt 无信息值）；当 p₂ > 0.5 时 C=0 被偏好——前提缺席使结论倾向为假。

**反向消息（C→M）：** 设 msg(C→f) = [r, 1-r]（r = P(C=0)），则：

```
msg(f→M)[M=1] = ψ(1,0)·r + ψ(1,1)·(1-r) = (1−p₁)·r + p₁·(1-r)
msg(f→M)[M=0] = ψ(0,0)·r + ψ(0,1)·(1-r) = p₂·r + (1−p₂)·(1-r)
```

归一化后，消息向量按 `[M=0, M=1]` 排列：

- 当 C 有高信念时（r 小），`msg(f→M) ≈ [1−p₂, p₁]`。当 p₁ + p₂ > 1 时 M=1 的权重高于 M=0——弱溯因：结论为真提升前提的信念。
- 当 C 信念低时（r 大），`msg(f→M) ≈ [p₂, 1−p₁]`。由于 ↝ 满足 `p₁ + p₂ > 1`，此时 M=1 的权重低于 M=0——modus tollens：结论为假削弱前提。

与逻辑蕴含的对比：逻辑蕴含中 ψ(1,0) = 0（对应 p₁ = 1），反向抑制是绝对的（C=0 时 M=1 完全被禁止）。↝（软蕴含）中 p₁ < 1 使 ψ(1,0) = 1−p₁ > 0，反向抑制是部分的——强度由 p₁ 控制。

### 2.3 弱三段论的实现

[01-plausible-reasoning.md](01-plausible-reasoning.md) §1.3–1.4 定义了四种三段论——强三段论（modus ponens）和三条弱三段论。本节从 BP 消息传递的角度展示它们如何在 ↝ 的势函数上自然涌现。

**强三段论（前提真 → 结论信念上升）：** §2.2 的正向消息分析表明，当 M 信念高时（q 小），`msg(f→C) ≈ [1−p₁, p₁]`，p₁ 越大 C=1 越被偏好。这是 BP 正向消息传播的直接结果。

**弱三段论 1（结论真 → 前提信念上升）：** §2.2 的反向消息分析表明，当 C 信念高时（r 小），`msg(f→M) ≈ [1−p₂, p₁]`。当 p₁ + p₂ > 1 时 M=1 获得比 M=0 更高的权重——溯因。这是 Bayes 定理的自然结果：结论为真提升了对前提的后验信念。

**弱三段论 2（结论假 → 前提信念下降）：** §2.2 的反向消息分析表明，当 C 信念低时（r 大），`msg(f→M) ≈ [p₂, 1−p₁]`。由于 `p₁ + p₂ > 1`，M=1 获得的权重低于 M=0——modus tollens：结论为假削弱前提。

**弱三段论 3（前提假 → 结论变弱）：** 当 M 信念低时（q 大），`msg(f→C) ≈ [p₂, 1−p₂]`。当 p₂ = 0.5 时消息接近均匀——前提缺席时不提供信息，C 回落到先验水平。当 p₂ > 0.5 时 C=0 被偏好——结论失去支持。

四条准则不需要特殊设计——它们是 BP 在 ↝ 的势函数上运行的自然结果。在确定性算子（p₁ = 1）上同样成立（参见 §2.1），只是效果更强烈（ψ(1,0) = 0 产生确定性传播）。

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

### 3.5 失败模式与边界

BP 不是"永远有解"的魔法过程，它仍然受上游模型和图结构的约束：

- 如果上游给出的硬约束彼此不相容，使可行集为空，那么 Jaynes 意义下就不存在合法 posterior；这不是 BP 可以修复的问题。
- 如果联合分布定义良好，但图中有环，loopy BP 可能振荡、不收敛，或收敛到偏差较大的近似。
- 与 SAT 不同的是，软证据之间的张力通常表现为 competing messages 和较高不确定性，而不是立刻出现二值的“无解”。

因此，BP 的正确定位是：

> **在可行的概率模型上近似边缘化。**

它很好地处理不完整信息和相互竞争的软支撑，但并不消除上游约束不相容或近似算法不收敛这两类根本问题。

---

## 跨层引用

- **上游（theory 层）**：[01-plausible-reasoning.md](01-plausible-reasoning.md) — Jaynes 框架、Cox 定理、弱三段论；[06-factor-graphs.md](06-factor-graphs.md) — 因子图结构、算子势函数；[03-propositional-operators.md](03-propositional-operators.md) §4 — ↝（软蕴含）算子定义、参数 (p₁, p₂) 的含义
- **BP 层**：[../bp/potentials.md](../bp/potentials.md) — f(p) 的具体函数形式；[../bp/inference.md](../bp/inference.md) — BP 推理的工程实现细节
- **源码**：`libs/inference/bp.py`（BP 算法实现）、`libs/inference/factor_graph.py`（因子图数据结构）

## 参考文献

- Kschischang, Frey, Loeliger. "Factor Graphs and the Sum-Product Algorithm" (2001)
- Yedidia, Freeman, Weiss. "Understanding Belief Propagation and its Generalizations" (2003)
- Pearl, J. *Probabilistic Reasoning in Intelligent Systems* (1988)
