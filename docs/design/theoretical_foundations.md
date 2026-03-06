# Gaia 理论基础

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.2 |
| 日期 | 2026-03-04 |
| 关联文档 | [related_work.md](related_work.md) — 与已有系统的对比, [knowledge_package_system.md](knowledge_package_system.md) — Cargo/Julia 类比 |

---

## 1. 推理超图的本质

Gaia 是一个 **推理超图 (Reasoning Hypergraph)**。理解它的关键在于三个层次：它是什么、它不是什么、以及它如何推理。

### 1.1 两层结构

Gaia 将逻辑复杂度分为两层：

```
┌─────────────────────────────────────────────────────┐
│  节点内容层 (Content Layer)                           │
│  ─────────────────────────────                       │
│  每个节点是一个命题 (proposition)，内容可以包含         │
│  任意逻辑：析取(∨)、否定(¬)、全称量词(∀)、            │
│  因果声明、整个因果模型、数学公式……                    │
│                                                      │
│  处理者：人 + LLM (commit review pipeline)            │
│  对推理引擎：不透明 (opaque)                          │
├─────────────────────────────────────────────────────┤
│  图结构层 (Graph Structure Layer)                     │
│  ─────────────────────────────                       │
│  超边连接命题，只表达：                                │
│    tail₁ ∧ tail₂ ∧ ... ∧ tailₙ → head₁ ∧ ... ∧ headₘ │
│  每条边附带概率 (probability) 和类型 (type)            │
│                                                      │
│  处理者：BP 算法 (自动计算)                            │
│  设计原则：保持简单，才能亿级扩展                       │
└─────────────────────────────────────────────────────┘
```

这个分层是有意为之的设计选择：

- **图结构层刻意简单**——只有"合取蕴含合取"加概率，因为这是要在十亿节点上自动计算的部分
- **逻辑的丰富性留在节点内容里**——析取、否定、因果关系等都可以作为命题的 content 存在，由人和 LLM 理解

### 1.2 命题级 vs 实体级

传统知识图谱的节点是 **实体 (entity)**——"爱因斯坦"、"乌尔姆"这样的世界中的事物。

Gaia 的节点是 **命题 (proposition)**——"爱因斯坦出生于乌尔姆"这样的关于世界的主张。每个命题有真假程度 (belief ∈ [0,1])，而非简单的存在与否。

这个区别决定了一切下游设计：

| 维度 | 实体级 (传统 KG) | 命题级 (Gaia) |
|------|----------------|--------------|
| 节点 | 事物 | 主张 |
| 边 | 关系 (bornIn) | 推理 (前提→结论) |
| 不确定性 | 无 (存储即为真) | prior, belief, probability |
| 矛盾 | 错误 | 一等公民 |
| 溯源 | 可选的元数据 | 核心结构 (reasoning chain) |

---

## 2. 因子图与信念传播

### 2.1 什么是因子图

因子图 (factor graph) 是一种二部图，包含两种节点：

- **变量节点 (variable node)**：表示一个未知量，带有先验分布
- **因子节点 (factor node)**：表示变量之间的约束或关联

Gaia 的推理超图 **天然就是一个因子图**：

```
变量节点 = Node (命题)
  ├── 先验值 = Node.prior
  └── 后验值 = Node.belief (BP 计算结果)

因子节点 = HyperEdge (超边)
  ├── 连接 = tail[] (输入变量) + head[] (输出变量)
  └── 势函数 = HyperEdge.probability
```

具体映射（以一条 paper-extract 边为例）：

```
Node 1: "材料A有X性质" (prior=0.8)
Node 2: "材料B有Y性质" (prior=0.7)
    │                                    变量节点
    └──── tail ────┐
                   ▼
              ■ Factor (edge_id=1, prob=0.9)    因子节点
                   │
    ┌──── head ────┘
    ▼
Node 3: "合金AB具有Z性质" (prior=1.0)         变量节点
```

这个映射在 `services/inference_engine/factor_graph.py` 的 `from_subgraph()` 方法中实现：Node 列表 → 变量，HyperEdge 列表 → 因子。

### 2.2 信念传播 (BP) 的直觉

信念传播就是在因子图上反复传递消息，更新每个节点的"信念"。

核心公式的直觉：

```
前提可信度 × 推理可靠性 = 结论可信度

beliefs[1] × beliefs[2] × edge.probability = factor_message
     0.8    ×    0.7     ×      0.9        =    0.504

"前提1我信80%，前提2我信70%，推理过程可靠性90%，
 所以结论我信50.4%"
```

一轮迭代遍历所有超边，计算每条边对 head 节点的消息，更新 belief。

### 2.3 为什么需要"Loopy"

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

### 2.4 为什么需要 Damping (阻尼)

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

### 2.5 完整 BP 流程

```
初始化: 每个节点 belief = prior
         │
         ▼
    ┌─── 循环 (最多 max_iterations 轮) ───┐
    │                                      │
    │  遍历每条超边:                        │
    │    factor_msg = ∏(tail beliefs) × prob│
    │    对每个 head 节点:                  │
    │      new = prior × factor_msg         │
    │      belief = damping×new             │
    │             + (1-damping)×old         │
    │                                      │
    │  检查收敛:                            │
    │    max(|new - old|) < threshold?      │
    │    是 → 停止                          │
    │    否 → 继续下一轮                    │
    └──────────────────────────────────────┘
         │
         ▼
输出: 每个节点的后验 belief ∈ [0, 1]
```

### 2.6 Pre-grounded：为什么没有 Grounding 瓶颈

Markov Logic Networks (MLN) 存储的是 **通用规则**：

```
∀x: Metal(x) ∧ Heated(x) → Expands(x)     权重=2.1
```

推理时需要对每个具体金属实例化 (grounding)——铁、铜、铝……N 个常量 × k 个变量产生 O(N^k) 个基底子句。这是 MLN 在大规模知识库上不可行的根本原因。

Gaia 不存通用规则。每条超边已经是一个具体的、grounded 的推理步骤：

```
HyperEdge(tail=[节点"铁被加热"], head=[节点"铁膨胀了"], probability=0.95)
```

知识贡献者在提交时就指定了"这些具体前提通过这个具体推理得到这些具体结论"。系统不需要枚举所有可能的实例化。

代价是 Gaia 无法直接表达"对所有金属都成立"——只能靠积累足够多的具体实例，然后通过 BP 传播信念。

---

## 3. 与因果图的关系

### 3.1 不同层面的图

因果图 (Causal Graph, Pearl) 和 Gaia 的推理超图容易混淆，因为它们都是"有向图 + 概率"。但它们建模的对象处于不同层面：

```
Gaia (认识论层):   "我们有多少证据支持 '吸烟导致肺癌' 这个说法？"
                         ↑ 关于知识的推理
因果图 (本体论层):  "吸烟是否导致肺癌？如果干预吸烟行为，肺癌概率如何变化？"
                         ↑ 关于世界的推理
```

| 维度 | 因果图 | Gaia |
|------|-------|------|
| 建模对象 | 世界的因果机制 | 我们对世界的认识 |
| 节点含义 | 变量 (吸烟量、肺癌状态) | 命题 ("吸烟导致肺癌") |
| 边的含义 | X 导致 Y | 证据 A 支持命题 B |
| 核心问题 | "如果改变 X，Y 会怎样？" | "给定这些证据，我该多相信 Y？" |
| 推理方式 | do-calculus, 反事实推理 | 信念传播 |

### 3.2 因果图可以是 Gaia 节点的内容

一个因果模型（甚至一整个因果图）可以作为 Gaia 中一个节点的 content：

```python
Node(
    id=42,
    type="paper-extract",
    content={
        "causal_model": {
            "edges": [
                {"from": "吸烟", "to": "肺癌"},
                {"from": "基因", "to": "吸烟倾向"},
                {"from": "基因", "to": "肺癌"}
            ]
        },
        "claim": "论文A提出的吸烟-肺癌因果模型（含混淆变量）"
    },
    prior=0.85
)
```

然后 Gaia 的超边在这些节点之间建立推理关系：

```
Node 42: "论文A的因果模型（含混淆变量基因）"    belief=0.85
Node 43: "论文B的因果模型（不含混淆变量）"      belief=0.6
    ↔ [contradiction: 两个因果模型矛盾]

Node 44: "论文C的新实验排除了基因混淆"          belief=0.9
Node 42 + Node 44:
    → [abstraction] → Node 45: "修正后的因果模型"       belief=?  ← BP 计算
```

Gaia 不做因果推断，但它管理 **关于因果模型的知识演化**——哪些模型被提出了、它们之间有什么矛盾、新证据如何影响我们对各个模型的信任度。

### 3.3 两者是正交的

因果推断回答"世界怎么运作"；Gaia 回答"我们的认识有多可靠"。两者互补而非包含：

```
                    世界建模 (本体论)
                         │
              因果图      │
              (Pearl)    │
                         │
  ──────────────────────────────────────
                         │
              Gaia       │
              (LKM)      │
                         │
                    知识建模 (认识论)
```

---

## 4. 在逻辑体系中的位置

### 4.1 不是一阶逻辑

一阶逻辑 (FOL) 有变量和量词：

```
∀x (Metal(x) ∧ Heated(x) → Expands(x))
```

Gaia 里没有量词。每个节点是具体的、已实例化的命题——"铁在加热时膨胀"，而非"对所有金属"。BP 也不看节点内容，只看图的拓扑和概率。

### 4.2 不是命题逻辑

虽然 Gaia 操作的对象是命题，但它不满足经典命题逻辑的关键特征：

| 特征 | 命题逻辑 | Gaia |
|------|---------|------|
| 真值 | 二元 (true/false) | 连续 [0, 1] |
| 推理 | 演绎规则 (modus ponens) | 消息传递 (BP) |
| 矛盾 | 爆炸原理 (p ∧ ¬p → 任何) | 矛盾共存，belief 竞争 |
| 单调性 | 单调 (加前提不推翻结论) | 非单调 (新证据可降低 belief) |

### 4.3 接近 Horn 逻辑 + 概率

如果将 Gaia 的概率强制为 {0, 1}，每条超边退化为：

```
tail₁ ∧ tail₂ ∧ ... ∧ tailₙ → head₁ ∧ head₂ ∧ ... ∧ headₘ
```

这是 **Horn 子句 (Horn Clause)**——合取蕴含合取，是 Prolog/Datalog 的基础。比完整命题逻辑弱（没有析取 ∨ 和否定 ¬），但正因为弱，推理是多项式时间且不会爆炸。

```
完整命题逻辑 (∨, ¬, →)
    ⊃
  Horn 逻辑 / Datalog (∧ → ∧)     ← Gaia 的图结构层在这里
    ⊃
  事实数据库 (只有事实)
```

加上连续概率后，Gaia 成为 **概率化的 Horn 逻辑**，在 Datalog 的基本模式上叠加了 [0,1] 值域和信念传播。

### 4.4 析取和否定藏在节点里

图结构层没有 ∨ 和 ¬，但这不意味着 Gaia 不能表达它们——它们藏在节点的 content 里：

```python
Node(content="材料X在高温下稳定，或存在相变临界温度")  # 内含 ∨
Node(content="排除基因因素后，吸烟仍导致肺癌")        # 内含 ¬ 和 →
Node(content="对所有稀土元素，掺杂可提升超导温度")      # 内含 ∀
```

BP 把这些都视为不透明的原子。节点内部的逻辑复杂度由人和 LLM 在 commit review 时把关，不需要推理引擎理解。

这是 Gaia 表达力的来源：**图结构保持简单（可计算），逻辑丰富性放在内容层（由人/LLM 处理）**。

---

## 5. 蕴含格中的 Abstraction 与 Induction

这一节从格论 (lattice theory) 的角度阐明 Gaia 两种核心推理操作的数学本质，以及为什么 abstraction 保真而 induction 不保真。这是 Gaia 概率设计的理论根基。

### 5.1 蕴含格 (Lindenbaum-Tarski Algebra)

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

### 5.2 Abstraction 与析取 (OR)

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

### 5.3 Induction 与合取 (AND)

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

### 5.4 根本性的不对称

这是本文档最核心的 insight：

```
向上 (弱化)：可以无限远离 A ∨ B，每一步都保真
               A ⊨ (A∨B) ⊨ C₁ ⊨ C₂ ⊨ ...  ✓ 全部保真

向下 (强化)：A ∧ B 是保真的极限，再往下一步就不保真了
               ... C₂ ⊨ C₁ ⊨ (A∧B) ⊨ A
                   ✗       ✗     ✓ 只有最后一步保真
```

原因很简单：

- **弱化** = 丢掉信息。真命题蕴含的任何更弱命题必然为真。丢信息永远安全。
- **强化** = 添加信息。添加的信息可能是错的。A ∧ B 是"零添加"的极限（它只重述已知的事实），再往下就是在声称证据没有支持的东西。

这就是哲学中 **归纳问题 (problem of induction)** 的格论表述：归纳是唯一能产生 genuinely new knowledge 的推理形式，但它的代价是不保真。

### 5.5 对 Gaia 设计的直接推论

这个不对称性直接决定了 Gaia 的概率设计：

| 操作 | 格中方向 | 保真性 | probability 约束 | 理由 |
|------|---------|--------|-----------------|------|
| **Abstraction** | 向上 (弱化) | 保真 | 可以 = 1.0 | 结论已被前提蕴含 |
| **Induction** | 向下 (强化) | 不保真 | 必须 < 1.0 | 结论超出了证据范围 |
| **合取引入** | 到 GLB (不动) | 保真 | = 1.0 | 但不产生新知识，Gaia 中不需要专门边类型 |

这也解释了为什么 Gaia 不需要合取引入 (conjunction introduction) 作为独立的边类型：A ∧ B 只是把两个已知事实"粘"在一起，不产生任何新的认识。Abstraction 和 induction 之所以有价值，恰恰因为它们超越了合取/析取的"精确但无趣"——前者以保真为代价提取语义精华，后者以冒险为代价产生新知识。

### 5.6 四种操作的完整对称

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

## 6. 边类型的语义

### 6.1 当前边类型体系

> **注意：** `join` 和 `meet` 已分别重命名为 `abstraction` 和 `induction`（Issue #25），以准确反映第 5 节分析的格论语义。下表使用新名称。

| 类型 | 语义 | 格中方向 | BP 中应有的行为 |
|------|------|---------|---------------|
| `paper-extract` | 从论文提取的推理链：前提 → 结论 | — | 正向支持 |
| `abstraction` (原 join) | 提取共同弱化命题（保真） | 向上 | 正向支持（prob 可 = 1.0） |
| `induction` (原 meet) | 归纳泛化为更强命题（不保真） | 向下 | 正向支持（prob 必须 < 1.0） |
| `contradiction` | 两个命题相互矛盾 | — | **反向抑制**：A↑ 则 B↓ |
| `retraction` | 撤回一条已有的推理链 | — | **排除**：不参与传播 |

### 6.2 Contradiction 的语义

Contradiction 表示"两个命题不能同时为真"。在 BP 中应该产生竞争效应：

```
Node A: "材料X稳定" (belief=0.8, 有多条边支持)
Node B: "材料X不稳定" (belief=0.5, 证据较弱)
    ↔ [contradiction, prob=0.95]

BP 应该：
  A 的强 belief 通过 contradiction 边抑制 B → B 的 belief 下降
  B 的弱 belief 对 A 的抑制较小 → A 的 belief 略微下降
  最终 A >> B，而非两者都高
```

### 6.3 Retraction 的语义

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

## 7. Horn Clause：知识系统与依赖系统的共同逻辑基础

§4.3 指出 Gaia 的图结构层是概率化的 Horn 逻辑。这个观察有一个关键推论：**软件包管理器（Cargo、Julia Pkg）的依赖系统在逻辑上也是 Horn clause 系统**。而引入 Knowledge Package 概念后（见 [knowledge_package_system.md](knowledge_package_system.md)），Gaia 实际上是一个**双层 Horn clause 系统**——在 edge 层和 package 层各有一套，两层之间存在派生关系。

### 7.1 Horn Clause 的标准形式

```
H :- B₁, B₂, ..., Bₙ
（如果 B₁ 且 B₂ 且 ... 且 Bₙ，则 H）
```

核心数据结构：多个输入 → 一个输出的有向超边。

### 7.2 Gaia 的双层 Horn Clause

Cargo 只有一层 Horn clause（包级依赖）。Gaia 有两层：

```
┌─────────────────────────────────────────────────────────────────┐
│  Package 层 (依赖管理)                                           │
│                                                                  │
│  KP_A 可用 :- KP_B ≥1.0 已解析, KP_C ≥2.0 已解析               │
│                                                                  │
│  ← 这一层和 Cargo 直接同构                                       │
│  ← Gaia.toml / Gaia.lock 就是这一层的声明与锁定                  │
├─────────────────────────────────────────────────────────────────┤
│  Edge 层 (推理)                                                  │
│                                                                  │
│  结论可信 :- 前提₁ 成立, 前提₂ 成立, 前提₃ 成立                  │
│                                                                  │
│  ← 这一层是 Gaia 独有的                                          │
│  ← 概率化的 Horn clause，BP 在这一层运行                         │
└─────────────────────────────────────────────────────────────────┘
```

**两层之间的派生关系：**

```
Edge 层:  KP_A 内的某条推理边引用了 KP_B 导出的节点作为前提
              ↓ 派生出
Package 层: KP_A depends on KP_B
```

Package 层的依赖不是人手动声明的（虽然也可以），而是从 edge 层的跨包引用**自动推导**出来的。这就像 Cargo 中的依赖不是凭空声明的，而是因为代码中 `use` 了另一个 crate 的 API。

### 7.3 四方对照

| 系统 | Horn Clause 实例 | 层次 | 语义 |
|------|-----------------|------|------|
| **Prolog/Datalog** | `ancestor(X,Z) :- parent(X,Y), ancestor(Y,Z)` | 单层 | 逻辑推理 |
| **Cargo** | `P 可构建 :- dep_A 已满足, dep_B 已满足` | 单层 (包) | 依赖满足 |
| **Gaia (package 层)** | `KP_A 可用 :- KP_B ≥1.0 已解析, KP_C ≥2.0 已解析` | 外层 | 依赖满足 |
| **Gaia (edge 层)** | `结论可信 :- 前提₁ 成立, 前提₂ 成立` | 内层 | 知识推理 |

Cargo 和 Gaia 的 package 层是**直接同构**的——都是 `包 :- 依赖₁, 依赖₂, ...`。这就是为什么 Cargo 的几乎所有包管理机制（Gaia.toml、Gaia.lock、semver、registry 协议、CLI）都可以直接复用。

Gaia 的 edge 层是 Cargo 完全没有的——Cargo 的包内部是源代码（不透明的），Gaia 的包内部是推理超图（结构化的）。这就是为什么 Gaia 需要 BP、contradiction、retraction 等 Cargo 不需要的机制。

### 7.4 操作语义的同构与分层

操作在两层上分别对应：

**Package 层（Gaia ≈ Cargo）：**

| 操作 | Cargo | Gaia (package 层) |
|------|-------|-------------------|
| 前向链 | 所有依赖满足 → 包可构建 | 所有依赖已解析 → 包可用 |
| 后向链 | 要构建 P，需先解析依赖 | 要使用 KP_A，需先解析其依赖 |
| 拓扑排序 | 构建顺序 (build plan) | 包安装/解析顺序 |
| 一致性检查 | 版本是否可解析 | 版本是否可解析 |
| 增量维护 | 依赖更新 → 重编译受影响的包 | 依赖更新 → 重传播受影响的包 |
| 溯源 | `cargo tree` | `gaia tree` |

**Edge 层（Gaia 独有）：**

| 操作 | Gaia (edge 层) |
|------|----------------|
| 前向链 | 所有前提可信 → 结论可信 |
| 后向链 | 要验证结论，追溯前提链 |
| 拓扑排序 | BP 传播顺序 |
| 一致性检查 | 信念是否收敛 |
| 增量维护 | belief 变化 → 重传播受影响的节点 |
| 溯源 | reasoning chain |

### 7.5 Gaia 不需要 SAT Resolver

前一版分析认为 Gaia 的 package 层和 Cargo 一样需要 SAT solver（PubGrub）来解析版本约束。**这是错误的。** 仔细分析后发现，Cargo 需要 SAT 的根本原因在 Gaia 中不存在。

#### 7.5.1 Cargo 为什么需要 SAT

Cargo 需要 SAT 是因为**代码有硬接口**：

```rust
// crate B v1.0
pub fn process(x: u32) -> String { ... }

// crate B v2.0 — 改了签名
pub fn process(x: String) -> Result<String> { ... }
```

crate A 调用了 `B::process(42)`。v1.0 和 v2.0 的 `process` 签名不兼容，同一编译单元里只能有一个版本。当多个 crate 对 B 的版本要求冲突时（钻石依赖），必须用 SAT 求解找一组全局兼容的版本，否则编译失败。

**SAT 的必要性 = 版本排他性 + 接口硬约束。**

#### 7.5.2 Gaia 为什么不需要 SAT

Gaia 的节点是**不可变的**（content-addressed）。一旦提交，`node_42` 的内容和 hash 永远不变。当 KP_B 从 v1.0 升到 v2.0 时：

```
KP_B v1.0: 导出 node_42 "X材料在300K超导" (belief=0.8)
KP_B v2.0: node_42 仍然存在（不可变），
           新增 node_99 "实验修正：X材料超导温度为280K"
           新增 retraction edge 撤回部分旧推理
```

KP_A 引用了 KP_B 的 node_42 作为前提。KP_B 升级后：

| 场景 | Cargo | Gaia |
|------|-------|------|
| 依赖升级改了接口 | 调用方**编译失败** | 节点不可变，引用**永远不断** |
| 钻石依赖冲突 | B 和 C 要求 D 的不兼容版本 → SAT | B 和 C 引用 D 的不同结论 → **BP 自然处理** |
| 两个版本共存 | 同一编译单元不行 → 排他选择 | 天然可以共存 → contradiction edge + BP 裁决 |
| "构建失败" | 版本不可满足 → 硬错误 | belief 降低 → **软降级** |

**节点不可变**消除了接口断裂问题。**BP**消除了版本排他性需求。SAT 的两个前提都不成立。

#### 7.5.3 Gaia 在 package 层需要什么

不是 SAT solver，而是一个**轻量的 registry lookup + 偏好排序 + staleness 检测**：

1. **名称解析**：`depends on KP_B >=1.0` → 从 registry 找到可用版本列表
2. **偏好排序**：优先用最新版（通常包含最新证据，belief 最准确）
3. **Staleness 检测**：标记引用了已被 retract/supersede 的节点的边，提示用户 `gaia outdated`
4. **建议性警告**：KP_B v2.0 有新证据可能影响你的推理，是否要 `gaia update`

这更接近 `pip install` 的简单版本匹配，而不是 PubGrub 的 CDCL 回溯搜索。

#### 7.5.4 修正后的分道扬镳图

```
                    Horn Clause (共同基础)
                    单调、布尔、多项式
                   /                      \
              Cargo                      Gaia
                |                          |
          依赖 = 硬接口调用            依赖 = 软知识引用
          (类型必须匹配)              (节点不可变，引用永不断)
                |                          |
          冲突 = 编译错误              冲突 = belief 竞争
          (编译前必须解决)            (BP 实时处理)
                |                          |
          → SAT/PubGrub               → 不需要 SAT
            (CDCL 回溯)                BP 即是 resolver
```

Cargo 和 Gaia 从 Horn clause 出发，但分道扬镳的原因不是"一个在 package 层一个在 edge 层"，而是**依赖的语义本质不同**：硬接口调用 vs 软知识引用。这个差异同时贯穿 package 层和 edge 层。

### 7.6 为什么 Gaia 仍然可以借鉴 Cargo

虽然 Gaia 不需要 Cargo 的核心算法（SAT），但 Cargo 中**基于 Horn clause 拓扑结构**的设计仍然可以复用：

| 可复用（拓扑结构层面） | 不可复用（约束语义层面） |
|----------------------|------------------------|
| 包的命名与版本号 (semver) | SAT/PubGrub 版本约束解析 |
| Gaia.toml / Gaia.lock 格式 | 版本排他性（Gaia 允许多版本共存） |
| Registry 协议（发布、下载、搜索） | "编译"的含义（独立编译 vs 全局 BP） |
| CLI 子命令结构 (`init`, `add`, `publish`) | 冲突处理（编译错误 vs belief 竞争） |
| 依赖树可视化 (`gaia tree`) | 增量更新策略（重编译 vs 增量 BP） |

判断标准：**如果一个特性只依赖"命名包之间的有向引用图"（Horn clause 拓扑），就可以复用；如果它依赖"引用是排他的/破坏性的"（硬约束语义），就不可以。**

详细的逐项对照见 [knowledge_package_system.md](knowledge_package_system.md)。

### 7.7 来自逻辑编程的技术启发

既然 Gaia 和 Cargo 共享 Horn clause 基础，那么 Horn clause 研究领域（逻辑编程、Datalog）的成熟技术可能对 Gaia 也有价值：

| 技术 | 来源 | 在 Gaia 中的潜在应用 |
|------|------|---------------------|
| **Magic sets optimization** | Datalog | 优化后向链查询——只计算与查询相关的子图，而非全图 BP |
| **Tabling / memoization** | Prolog (XSB) | 缓存已推导的中间结果；Gaia 的 BeliefSnapshot 本质上就是 tabling |
| **Stratification** | Datalog with negation | 分层处理 contradiction edge——先处理无矛盾子图，再处理矛盾 |
| **Incremental view maintenance** | Datalog (Differential Dataflow) | 增量 BP——只重算受影响的节点，而非全图重跑 |
| **Seminaïve evaluation** | Datalog | 每轮 BP 只传播上一轮变化的消息，避免重复计算 |

其中 seminaïve evaluation 尤其值得关注：当前 BP 实现每轮遍历所有超边，但大部分节点的 belief 在每轮变化很小。Datalog 的 seminaïve 策略（只看上一轮有变化的事实）直接对应"只传播上一轮 belief 变化超过阈值的节点"。

### 7.8 抽象代数视角

从更抽象的层面看，Horn clause 系统是一个**半格 (semilattice)**上的不动点计算：

```
操作器 T: 状态空间 → 状态空间
    T(当前所有已知事实) = 当前所有已知事实 ∪ 新推导出的事实
```

对比 Cargo 和 Gaia 的不动点计算：

```
Cargo:   T_sat(已解析的包集合) = 已解析的包集合 ∪ 新可解析的包
         布尔值域，可能无解（不可满足的依赖），需要 CDCL 回溯

Gaia:    T_bp(当前 belief 向量) = 当前 belief 向量 ⊕ BP 消息更新
         连续值域，总有解（belief 总会稳定在某个值），需要 damping
```

在纯 Horn clause（布尔、单调）下，T 保证在有限步内收敛到唯一最小不动点（Knaster-Tarski 定理）。

两者以不同方式打破了这个保证：
- **Cargo**：加入版本约束后，可能没有不动点（不可满足的依赖），需要回溯搜索 → SAT
- **Gaia**：加入概率和矛盾后，不动点可能不唯一（Loopy BP 不保证收敛到全局最优），需要 damping 近似 → 但总有一个近似解

这解释了一个深层差异：Cargo 可以"失败"（无解），Gaia 不会"失败"——它总是能给出一组 belief 值，只是准确度不同。**节点不可变 + 概率连续 = 系统永远有解。** 这是 Gaia 不需要 SAT 的代数层面的解释。

---

## 8. 已知局限与未来方向

### 8.1 当前 BP 实现的局限

1. **边类型未区分**：所有边都按正向支持处理，contradiction 不抑制，retraction 不排除（已提 Issue #23, #24）
2. **多因子消息顺序覆盖**：多条边指向同一节点时，最后更新的边影响最大，而非聚合所有消息
3. **纯拓扑推理**：BP 完全不看节点内容，无法利用语义相似性

### 8.2 可能的演进方向

| 方向 | 说明 | 优先级 |
|------|------|--------|
| 类型感知 BP | contradiction 抑制, retraction 排除 | 高 (Issue #24) |
| 消息聚合 | 多条入边的消息先聚合再更新 belief | 高 |
| GPU 加速 BP | 用 PGMax (JAX) 替代自研 NumPy 实现 | 中 |
| 嵌入辅助 BP | 用 embedding 相似度调节消息权重 | 低 |
| 局部精确推理 | 树结构子图用精确 BP，环结构用 Loopy BP | 低 |

### 8.3 不打算改变的设计选择

- **节点内容对 BP 不透明**：语义理解交给 LLM，不交给推理引擎
- **图结构只有合取→合取**：保持简单，不引入析取/否定到图结构层
- **Pre-grounded**：不存通用规则，只存具体实例
- **非单调推理**：新证据可以降低已有 belief，这是特性不是 bug

---

## 附录 A：术语对照

| 术语 | Gaia 中的对应 | 代码位置 |
|------|-------------|---------|
| Variable (变量) | Node | `libs/models.py:Node` |
| Prior (先验) | Node.prior | `libs/models.py:14` |
| Belief (后验信念) | Node.belief | `libs/models.py:16` |
| Factor (因子) | HyperEdge | `libs/models.py:HyperEdge` |
| Factor potential (因子势函数) | HyperEdge.probability | `libs/models.py:34` |
| Factor graph (因子图) | FactorGraph | `services/inference_engine/factor_graph.py` |
| Message passing (消息传递) | BP iteration | `services/inference_engine/bp.py:68-100` |
| Damping (阻尼) | BeliefPropagation._damping | `services/inference_engine/bp.py:41` |
| Convergence (收敛) | max_change < threshold | `services/inference_engine/bp.py:98-100` |

## 附录 B：与相关系统的概率机制对比

| 系统 | 概率机制 | 推理方式 | 扩展性瓶颈 |
|------|---------|---------|-----------|
| **MLN** | 一阶公式 + 权重 → MRF | Gibbs / BP | Grounding: O(N^k) |
| **PSL** | 连续 [0,1] + Hinge-loss MRF | 凸优化 | 仍需 grounding |
| **DeepDive** | 候选事实 + 因子图 | Gibbs sampling | 批处理 |
| **贝叶斯网络** | 条件概率表 | 精确 BP / 变分 | DAG 限制 |
| **Gaia** | 超图即因子图，prior + probability | Loopy BP (damped) | 无 grounding |

详细对比见 [related_work.md](related_work.md)。
