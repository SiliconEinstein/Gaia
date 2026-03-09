# 推理引擎理论

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-09 |
| 关联文档 | [theoretical-foundation.md](theoretical-foundation.md) — Jaynes 纲领与 Gaia 定位, [../language/design-rationale.md](../language/design-rationale.md) — CLI 架构与 Lean 类比 |

---

本文档是 Gaia 推理引擎的完整理论参考。关于 Jaynes 的认识论纲领和 Gaia 的整体定位，参见 [theoretical-foundation.md](theoretical-foundation.md)。

---

## 1. 因子图与信念传播

### 1.1 什么是因子图

因子图 (factor graph) 是一种二部图，包含两种节点：

- **变量节点 (variable node)**：表示一个未知量，带有先验分布
- **因子节点 (factor node)**：表示变量之间的约束或关联

Gaia 的推理超图**天然就是一个因子图**：

```
变量节点 = Node (命题)
  ├── 先验值 = Node.prior
  └── 后验值 = Node.belief (BP 计算结果)

因子节点 = HyperEdge (超边)
  ├── 连接 = premises[] (输入变量) + conclusions[] (输出变量)
  └── 势函数 = HyperEdge.probability
```

具体映射（以一条 paper-extract 边为例）：

```
Node 1: "材料A有X性质" (prior=0.8)
Node 2: "材料B有Y性质" (prior=0.7)
    │                                    变量节点
    └── premises ──┐
                   ▼
              ■ Factor (edge_id=1, prob=0.9)    因子节点
                   │
    ┌─ conclusions ┘
    ▼
Node 3: "合金AB具有Z性质" (prior=1.0)         变量节点
```

这个映射在 `libs/inference/factor_graph.py` 中实现：Node 列表 → 变量，HyperEdge 列表 → 因子。

### 1.2 信念传播 (BP) 的直觉

信念传播就是在因子图上反复传递消息，更新每个节点的"信念"。

核心公式的直觉：

```
前提可信度 × 推理可靠性 = 结论可信度

beliefs[1] × beliefs[2] × edge.probability = factor_message
     0.8    ×    0.7     ×      0.9        =    0.504

"前提1我信80%，前提2我信70%，推理过程可靠性90%，
 所以结论我信50.4%"
```

一轮迭代遍历所有超边，计算每条边对 conclusions 节点的消息，更新 belief。

### 1.3 为什么需要 "Loopy"

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

### 1.4 为什么需要 Damping (阻尼)

有环时，如果每轮直接用新值替换旧值，容易振荡：

```
无阻尼：
  第1轮: belief = 0.504
  第2轮: belief = 0.832  ← 跳上去
  第3轮: belief = 0.291  ← 跳下来
  第4轮: belief = 0.877  ← 又跳上去
  ...不收敛
```

阻尼的做法是新旧值加权混合：

```python
beliefs[h] = damping * new_belief + (1 - damping) * old_belief
```

默认 `damping=0.5`，每次只更新一半：

```
有阻尼 (damping=0.5):
  第1轮: belief = 0.5 × 0.504 + 0.5 × 1.0   = 0.752
  第2轮: belief = 0.5 × 0.xxx + 0.5 × 0.752  = 0.6xx
  第3轮: ...逐渐稳定
```

`damping=1.0` 表示完全用新值（无阻尼），`damping=0.0` 表示完全不更新。

### 1.5 完整 BP 流程（Sum-Product 算法）

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

关键改进（相对于旧实现）：
- **双向消息**：var→factor + factor→var，backward 抑制自然涌现
- **Exclude-self rule**：避免循环放大
- **同步更新**：所有新消息从旧消息计算，然后一次性替换（因子顺序无关）
- **2-vector 归一化**：消息始终求和为 1，长链不衰减

### 1.6 与 Jaynes 的对应关系

Jaynes 本人没有讨论因子图和 BP（这是 Pearl 等人后来的工作），但联系是直接的：

| Jaynes 概念 | Factor Graph / BP 对应 |
|---|---|
| 乘法规则 P(AB\|X) = P(A\|BX)·P(B\|X) | 联合分布的因子分解 ∏ fₐ(xₐ) |
| 加法规则 ΣP = 1 | marginalization（对变量求和） |
| Bayes 更新 | 消息传递：var→factor 和 factor→var |
| 一致性公理 IIIa | BP 收敛后的 beliefs 满足局部一致性 |
| MaxEnt | Bethe 自由能（loopy BP 近似最小化的目标） |
| 证据可交换性 | 同步 schedule：所有消息同时计算，顺序无关 |

**BP 算法就是 Jaynes 的 Robot 在因子图上的高效实现。** 在树结构图上 BP 精确实现 Jaynes 的规则；在有环图上 BP 是近似实现（loopy BP），但仍然遵循相同的局部规则。

---

## 2. 蕴含格中的 Abstraction 与 Induction

这一节从格论 (lattice theory) 的角度阐明 Gaia 两种核心推理操作的数学本质，以及为什么 abstraction 保真而 induction 不保真。

### 2.1 蕴含格 (Lindenbaum-Tarski Algebra)

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

### 2.2 Abstraction 与析取 (OR)

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

### 2.3 Induction 与合取 (AND)

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

### 2.4 根本性的不对称

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

### 2.5 对 Gaia 设计的直接推论

这个不对称性直接决定了 Gaia 的概率设计：

| 操作 | 格中方向 | 保真性 | probability 约束 | 理由 |
|------|---------|--------|-----------------|------|
| **Abstraction** | 向上 (弱化) | 保真 | 可以 = 1.0 | 结论已被前提蕴含 |
| **Induction** | 向下 (强化) | 不保真 | 必须 < 1.0 | 结论超出了证据范围 |
| **合取引入** | 到 GLB (不动) | 保真 | = 1.0 | 但不产生新知识，Gaia 中不需要专门边类型 |

### 2.6 四种操作的完整对称

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

## 3. 边类型的语义

### 3.1 当前边类型体系

> **注意：** `join` 和 `meet` 已分别重命名为 `abstraction` 和 `induction`（Issue #25），以准确反映第 2 节分析的格论语义。

| 类型 | 语义 | 格中方向 | BP 中的行为 |
|------|------|---------|------------|
| `paper-extract` | 从论文提取的推理链：前提 → 结论 | — | 正向支持 |
| `abstraction` (原 join) | 提取共同弱化命题（保真） | 向上 | 正向支持（prob 可 = 1.0） |
| `induction` (原 meet) | 归纳泛化为更强命题（不保真） | 向下 | 正向支持（prob 必须 < 1.0） |
| `contradiction` | 两个命题相互矛盾 | — | **反向抑制**：A↑ 则 B↓ |
| `retraction` | 撤回一条已有的推理链 | — | **排除**：不参与传播 |

### 3.2 Contradiction 的语义

Contradiction 表示"前提不能同时为真"。按照 Jaynes 的理论，发现矛盾等价于学到新信息 P(A∧B|I) ≈ 0（详见 [theoretical-foundation.md](theoretical-foundation.md) §4）。

**Factor potential 设计：**

矛盾 factor 必须**惩罚 all-premises-true 配置**，而非像 deduction 那样鼓励它：

```
Deduction:     all premises=1, conclusion=1 → p       (高，鼓励)
Contradiction: all premises=1, conclusion=1 → 1-p     (低，惩罚)
               all premises=1, conclusion=0 → ε≈0     (conjunction 成立却否认矛盾，更不可能)
               else → 1                       (无约束)
```

这产生的 backward message 会**强力抑制前提**——prior 越弱的前提被削弱越多（Jaynes 的 "weaker evidence yields first"），无需依赖下游的 retraction edge：

```
Node A: "材料X稳定" (belief=0.8, 有多条边支持)
Node B: "材料X不稳定" (belief=0.5, 证据较弱)
    ↔ [contradiction, prob=0.95]

BP backward message:
  A 的强 belief 通过 contradiction 边抑制 B → B 的 belief 大幅下降
  B 的弱 belief 对 A 的抑制较小 → A 的 belief 略微下降
  最终 A >> B，自动遵循 "weaker evidence yields first"
```

实现位于 `libs/inference/bp.py` 的 `_evaluate_potential()` 函数。

### 3.3 Retraction 的语义

Retraction 表示"一条推理链不再有效"。学术场景：论文被撤稿。

```
之前：
  Edge 10 (paper-extract): [Node 1, Node 2] → [Node 3], prob=0.9
  Node 3 的 belief 较高，因为有 Edge 10 的支持

撤回后：
  Edge 20 (retraction): 撤回 Edge 10
  Edge 10 不再参与 BP
  Node 3 失去这条证据支持，belief 下降
```

Contradiction 是"两方对峙，各有证据"；Retraction 是"一方认错退出，证据作废"。

---

## 4. 已知局限与演进方向

### 4.1 已解决的局限

以下问题在 sum-product loopy BP 重写中已解决：

1. ~~边类型未区分~~：现已实现类型感知 factor potential（deduction、retraction、contradiction 各有独立语义）
2. ~~多因子消息顺序覆盖~~：现使用 2-vector 消息 + 乘法聚合，多条入边的消息正确合并
3. ~~无反向传播~~：现有完整的 var→factor 和 factor→var 双向消息，backward 抑制自然涌现
4. ~~因子顺序影响结果~~：现使用同步 schedule，所有消息从旧值计算后同时更新
5. ~~Contradiction 无独立语义~~：现使用 Jaynes 惩罚性 potential（§3.2），contradiction 自带强力 backward inhibition

### 4.2 当前局限

1. **纯拓扑推理**：BP 完全不看节点内容，无法利用语义相似性

### 4.3 可能的演进方向

| 方向 | 说明 | 优先级 |
|------|------|--------|
| GPU 加速 BP | 用 PGMax (JAX) 替代自研 NumPy 实现 | 中 |
| 嵌入辅助 BP | 用 embedding 相似度调节消息权重 | 低 |
| 局部精确推理 | 树结构子图用精确 BP，环结构用 Loopy BP | 低 |

### 4.4 不打算改变的设计选择

- **节点内容对 BP 不透明**：语义理解交给 LLM，不交给推理引擎
- **图结构只有合取→合取**：保持简单，不引入析取/否定到图结构层
- **Pre-grounded**：不存通用规则，只存具体实例
- **非单调推理**：新证据可以降低已有 belief，这是特性不是 bug

---

## 5. 逻辑编程技术启发

Horn clause 研究领域（逻辑编程、Datalog）的成熟技术对 Gaia 有直接价值：

| 技术 | 来源 | 在 Gaia 中的应用方向 |
|------|------|---------------------|
| **Seminaïve evaluation** | Datalog | 每轮 BP 只传播上一轮变化的消息，避免重复计算 |
| **Magic sets optimization** | Datalog | 优化后向链查询——只计算与查询相关的子图，而非全图 BP |
| **Tabling / memoization** | Prolog (XSB) | 缓存已推导的中间结果 |
| **Stratification** | Datalog with negation | 分层处理 contradiction edge——先处理无矛盾子图，再处理矛盾 |
| **Incremental view maintenance** | Differential Dataflow | 增量 BP——只重算受影响的节点，而非全图重跑 |

其中 seminaïve evaluation 尤其值得关注：当前 BP 实现每轮遍历所有超边，但大部分节点的 belief 在每轮变化很小。Datalog 的 seminaïve 策略（只看上一轮有变化的事实）直接对应"只传播上一轮 belief 变化超过阈值的节点"。

### 5.1 不动点计算与收敛性

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

| 术语 | Gaia 中的对应 | 代码位置 |
|------|-------------|---------|
| Variable (变量) | Node | `libs/models.py:Node` |
| Prior (先验) | Node.prior | `libs/models.py` |
| Belief (后验信念) | Node.belief | `libs/models.py` |
| Factor (因子) | HyperEdge | `libs/models.py:HyperEdge` |
| Factor potential (因子势函数) | HyperEdge.probability | `libs/models.py` |
| Factor graph (因子图) | FactorGraph | `libs/inference/factor_graph.py` |
| Factor potential (详细) | `_evaluate_potential()` | `libs/inference/bp.py` |
| Message passing (消息传递) | BP iteration | `libs/inference/bp.py` |
| Damping (阻尼) | BeliefPropagation._damping | `libs/inference/bp.py` |
| Convergence (收敛) | max_change < threshold | `libs/inference/bp.py` |

## 附录 B：与相关系统的概率机制对比

| 系统 | 概率机制 | 推理方式 | 扩展性瓶颈 |
|------|---------|---------|-----------|
| **MLN** | 一阶公式 + 权重 → MRF | Gibbs / BP | Grounding: O(N^k) |
| **PSL** | 连续 [0,1] + Hinge-loss MRF | 凸优化 | 仍需 grounding |
| **DeepDive** | 候选事实 + 因子图 | Gibbs sampling | 批处理 |
| **贝叶斯网络** | 条件概率表 | 精确 BP / 变分 | DAG 限制 |
| **Gaia** | 超图即因子图，prior + probability | Loopy BP (damped) | 无 grounding |
