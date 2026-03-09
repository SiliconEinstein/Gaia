# Gaia 理论基础

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-09 |
| 关联文档 | [inference-theory.md](inference-theory.md) — 推理引擎数学细节, [language/design-rationale.md](language/design-rationale.md) — Lean 类比与 CLI 语义 |

---

## 1. 总论：Gaia 是什么

**两个总定义：**

1. **Gaia 是基于 plausible reasoning 的形式化语言。**
2. **Large Knowledge Model = 自然科学的系统的形式化。**

Gaia 不是数据库、不是编程语言、不是传统知识图谱。它是一套形式系统，让人类和 LLM 能够把科学知识——命题、证据、推理链——写成结构化的、可计算合理度的表达式。

Gaia 由三个组成部分构成：

```
Language  →  CLI (Robot)  →  Cloud (LKM)
    ↓                  ↓               ↓
形式化知识          本地推理          全局知识模型
YAML 表达式         BP 计算           跨 package 集成
```

- **Language** 是语法层：Gaia Language 定义了如何用 YAML 表达命题、推理链、模块依赖
- **CLI** 是推理层：`gaia build` 编译因子图、运行 BP，严格按概率规则计算每个命题的合理度
- **Cloud** 是集成层：多个知识 package 发布后合并为 Large Knowledge Model，跨 package BP 统一信念

**核心思想：** 这三层的理论根基是同一个——E.T. Jaynes 的概率论纲领。Gaia 就是 Jaynes 的 "Robot" 的形式化语言实现。

---

## 2. Jaynes 的纲领：概率即逻辑

Gaia 的认识论根基是 E.T. Jaynes 的 *Probability Theory: The Logic of Science* (2003)。Jaynes 的理论不仅决定了 BP 算法的选择，更从根本上定义了 Gaia 是什么。

### 2.1 核心论点：概率不是频率，是理性推理的唯一合法形式

频率学派将 P(A) 定义为"无限次重复实验中 A 出现的比例"。这无法回答"火星上曾经有生命的概率是多少？"——没有重复实验可做。

Jaynes 的定义：**P(A|X) = 给定信息 X 时，命题 A 的合理程度 (plausibility)**。每个概率都是条件概率。改变信息，概率就改变——这不是主观偏好，而是逻辑必然。

### 2.2 Cox 定理：推导（而非假设）概率论

Jaynes 不假设概率公理，而是从三条关于"合理推理"的基本要求**推导**出概率论的全部规则：

1. **实数表示**：plausibility 可以用实数排序
2. **常识对应**：支持 A 的证据出现 → A 的 plausibility 连续、单调增加
3. **一致性**：
   - (a) 同一结论从不同路径推得，答案必须相同
   - (b) 不能忽略已有信息
   - (c) 相同信息 → 相同结论

Richard Cox (1946) 证明：**满足这三条的唯一系统同构于概率论。** 任何其他系统要么等价于概率论，要么自相矛盾。

### 2.3 三大规则

由 Cox 定理推导出的三大规则：

- **乘法规则**：P(AB|X) = P(A|BX) · P(B|X) — 联合合理度的分解
- **加法规则**：P(A|X) + P(¬A|X) = 1 — 命题与其否定互补
- **Bayes 定理**：P(H|DX) = P(D|HX) · P(H|X) / P(D|X) — 证据更新

Jaynes 强调：这些不是"方法"或"学派"，是**逻辑定理**。

### 2.4 最大熵原则 (MaxEnt)

当信息不完整时，应选择**在满足已知约束的前提下熵最大的分布**——最诚实的选择，只编码已知信息，不偷偷添加未知信息。

对 Gaia 的直接影响：

| 场景 | MaxEnt 选择 | Gaia 实现 |
|------|------------|----------|
| 节点无额外信息 | P(x=1) = P(x=0) = 0.5 | Node.prior 默认值 |
| 因子中前提不全为真 | 对结论无约束 | potential = 1（均匀） |
| 没有入边的孤立节点 | belief = prior | BP 不修改无因子节点 |

### 2.5 Cromwell 规则

对经验命题**永远不要赋予概率 0 或 1**。如果 P(H|X) = 0，那无论多强的证据都无法改变你的信念——这是教条主义。

对 Gaia：Node.prior 应始终在 (0, 1) 开区间内。prior = 1.0 的节点在 BP 中不可被任何证据削弱——仅用于定义性真理（如"真空环境"），不用于经验命题。

---

## 3. 从强逻辑到弱逻辑：推理形式的概率化映射

经典逻辑的推理形式在 Jaynes 框架下各自对应概率公式。这个映射揭示了 Gaia 的设计逻辑：图结构层的每种边类型都有严格的概率论对应。

### 3.1 三段论 (Modus Ponens) → 条件概率 / Bayes 更新

经典逻辑：

```
A → B,  A  ⊢  B        （确定性，保真）
```

Jaynes 概率化：

```
P(B|AX) = edge.probability
P(A|X)  = Node_A.belief
P(B|X)  = P(B|AX) · P(A|X) + P(B|¬AX) · P(¬A|X)
```

前提不再是"真/假"，而是"多大程度上可信"。推理也不再保真，而是"多大程度上可靠"。这就是 Gaia 的 **deduction / paper-extract 边**的语义：前提的 belief 乘以边的 probability，得到结论的消息。

### 3.2 链式推理 (Syllogism) → Chain Rule / 因子分解

经典逻辑：

```
A → B,  B → C  ⊢  A → C   （三段论链式推理）
```

Jaynes 概率化：

```
P(ABC|X) = P(A|X) · P(B|AX) · P(C|ABX)   （chain rule）
```

联合分布按条件链式分解。在因子图上，这对应多个因子的级联：每个因子是一条超边，消息沿链路传播。长链推理的可信度自然衰减——这不是 bug，是 Jaynes 规则的直接推论。

### 3.3 归纳 (Induction) → 不保真的强化推理

经典逻辑中归纳不是有效推理。Jaynes 给了它严格的概率语义：

```
观察"铁加热膨胀"和"铜加热膨胀" → 归纳"金属加热膨胀"
```

归纳的结论**超出了证据范围**——从两种金属推广到所有金属。这在蕴含格中是向下（强化）方向的跳跃，因此 probability 必须 < 1.0。

**设计推论：** Gaia 的 induction 边的 probability 不可为 1.0——这不是任意约束，是格论+概率论的必然结果（详见 [inference-theory.md](inference-theory.md) §2）。

### 3.4 抽象 (Abstraction) → 保真的弱化推理

```
"MgB₂ 在 T<39K 时超导" → 抽象 → "MgB₂ 存在超导态"
```

抽象的结论**弱于前提**——从具体条件到一般存在性。蕴含格中向上（弱化）方向是保真的：真命题蕴含的更弱命题必然为真。

**设计推论：** Gaia 的 abstraction 边的 probability 可以 = 1.0。

### 3.5 映射总览

| 经典推理形式 | Jaynes 对应 | Gaia 边类型 | probability 约束 |
|------------|-----------|-----------|----------------|
| 三段论 (modus ponens) | 条件概率 / Bayes | deduction, paper-extract | ∈ (0, 1] |
| 链式推理 (syllogism) | chain rule / 因子分解 | 多条边的级联 | 每条边独立 |
| 归纳 (induction) | 不保真强化 | induction | 必须 < 1.0 |
| 抽象 (abstraction) | 保真弱化 | abstraction | 可以 = 1.0 |
| 矛盾 | 证据冲突 | contradiction | 惩罚性 potential |

> **注**：完整的 BP 算法细节和因子势函数设计参见 [inference-theory.md](inference-theory.md)。

---

## 4. 矛盾作为第一公民

这是 Gaia 区别于传统知识图谱的最根本特征，值得独立成章。

### 4.1 Jaynes 的核心洞察

发现矛盾 = 学到新信息。

当我们发现命题 A 和命题 B 矛盾时，Jaynes 说的是：我们学到了 P(A∧B|I) ≈ 0——**它们不能同时为真**。这不是"A 不太可能"或"B 不太可能"，而是一条新的约束。

### 4.2 与经典逻辑的根本分歧

经典逻辑中矛盾触发**爆炸原理 (ex falso quodlibet)**——从假推出一切，系统崩溃。

Jaynes 中矛盾是**证据冲突**——不同证据指向不同方向，Bayes 定理自动分配惩罚。系统不会崩溃，只会调整信念。

```
经典逻辑：  A ∧ ¬A  →  ⊥  →  任意命题    （系统崩溃）
Jaynes：    P(A∧B|I) ≈ 0  →  posterior odds 自动调整  （系统学习）
```

### 4.3 "Weaker evidence yields first"

这是理论推导的结果，不是设计选择：

```
posterior odds = prior odds × LR₁ × LR₂ × ...
```

当 contradiction factor 惩罚 all-tails-true 时，backward message 流向所有前提。**prior 越弱的前提被削弱越多**——因为它的 prior odds 更小，乘以同一个惩罚性 likelihood ratio 后衰减更大。

```
Node A: "材料X稳定" (belief=0.8, 多条边支持)
Node B: "材料X不稳定" (belief=0.5, 证据较弱)
    ↔ [contradiction, prob=0.95]

BP backward message:
  A 的强 belief → 通过 contradiction 抑制 B → B 大幅下降
  B 的弱 belief → 对 A 的抑制较小 → A 略微下降
  最终 A >> B，自动遵循 "weaker evidence yields first"
```

### 4.4 矛盾在 Gaia 中的地位

传统知识图谱**害怕矛盾**——矛盾是数据质量问题，需要清洗。

Gaia **拥抱矛盾**——矛盾是知识进步的引擎。科学本身就是通过矛盾前进的：新实验反驳旧假说、不同理论产生冲突预测、新证据推翻已有结论。

`contradiction` 是 Gaia 的一等公民边类型，不是异常处理机制：

- 它有独立的 factor potential 语义（惩罚 all-tails-true，与 deduction 相反）
- 它的 backward message 自动抑制弱前提，无需人工介入
- 它与 retraction 互补：contradiction 是"两方对峙"，retraction 是"一方认错退出"

**设计推论：** contradiction factor potential 惩罚 all-tails-true 配置（与 deduction 相反），backward message 自动抑制弱前提——这是 Jaynes 规则的直接实现（详见 [inference-theory.md](inference-theory.md) §3）。

---

## 5. Jaynes's Robot 与 Gaia

### 5.1 Robot 隐喻

Jaynes 用一个思想实验贯穿全书：设计一个 **robot**，它必须：

- 接收命题和证据，输出合理度
- 严格遵循概率规则（Cox 定理推导出的三大规则）
- 无直觉、无偏见——只跟着逻辑走
- 满足一致性——同一问题不同问法必须得到相同答案

**Gaia 就是这个 Robot 的实现。**

### 5.2 对应表

| Jaynes Robot 特征 | Gaia 对应 |
|---|---|
| 接收命题 | Node（命题节点，content 是主张） |
| 接收证据 | HyperEdge（推理关系，带 probability） |
| 输出合理度 | Node.belief（后验信念，∈ [0,1]） |
| 无偏见 | BP 不读节点 content，只看结构和概率 |
| 一致性 | 同步消息传递 + 收敛保证：因子顺序不影响结果 |
| 证据可交换 | 乘法规则的对称性：P(AB|X) = P(BA|X) |

### 5.3 两层架构的理论根基

Robot 隐喻解释了 Gaia 的两层架构（§6.1）：

- **图结构层** = Robot 的推理引擎——严格遵循概率规则，自动计算
- **内容层** = Robot 的输入——命题的语义由人和 LLM 把关，Robot 不需要"理解"

这个分层不是工程权衡，是 Jaynes 理论的直接推论：Robot 只需要知道"命题的合理度"和"证据的可靠性"，不需要理解命题说了什么。BP 的不透明性正是 Robot 的忠实实现。

### 5.4 LLM 的角色

在 Jaynes 框架中，LLM 不是推理者，是**翻译者**：

```
自然语言知识  →  LLM 形式化  →  Gaia Language  →  BP 推理  →  beliefs
    ↑                                              ↑
  人类理解                                      Robot 规则
```

LLM 负责把自然语言知识翻译成 Gaia Language（命题 + 推理链 + 概率标注）。Robot (BP) 负责推理——严格按 Jaynes 规则计算合理度。

一个幻觉频发的 LLM 可以产生"精彩"但错误的推理——BP 不在乎，因为它只看结构和概率，不读文字。这就是 Gaia 从 Lean 借鉴的**构造/验证分离**原则：构造过程（LLM）可以犯错，验证过程（BP + Review）独立把关（详见 [language/design-rationale.md](language/design-rationale.md)）。

---

## 6. 推理超图的本质

### 6.1 两层结构

Gaia 将逻辑复杂度分为两层：

```
┌─────────────────────────────────────────────────────┐
│  节点内容层 (Content Layer)                           │
│  ─────────────────────────                           │
│  每个节点是一个命题 (proposition)，内容可以包含         │
│  任意逻辑：析取(∨)、否定(¬)、全称量词(∀)、            │
│  因果声明、整个因果模型、数学公式……                    │
│                                                      │
│  处理者：人 + LLM (commit review pipeline)            │
│  对推理引擎：不透明 (opaque)                          │
├─────────────────────────────────────────────────────┤
│  图结构层 (Graph Structure Layer)                     │
│  ─────────────────────────                           │
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

### 6.2 命题级 vs 实体级

传统知识图谱的节点是**实体 (entity)**——"爱因斯坦"、"乌尔姆"这样的世界中的事物。Gaia 的节点是**命题 (proposition)**——"爱因斯坦出生于乌尔姆"这样的关于世界的主张。每个命题有真假程度 (belief ∈ [0,1])，而非简单的存在与否。

| 维度 | 实体级 (传统 KG) | 命题级 (Gaia) |
|------|----------------|--------------|
| 节点 | 事物 | 主张 |
| 边 | 关系 (bornIn) | 推理 (前提→结论) |
| 不确定性 | 无 (存储即为真) | prior, belief, probability |
| 矛盾 | 错误 | 一等公民 |
| 溯源 | 可选的元数据 | 核心结构 (reasoning chain) |

### 6.3 概率化的 Horn Clause

如果将 Gaia 的概率强制为 {0, 1}，每条超边退化为：

```
tail₁ ∧ tail₂ ∧ ... ∧ tailₙ → head₁ ∧ head₂ ∧ ... ∧ headₘ
```

这是 **Horn 子句 (Horn Clause)**——合取蕴含合取，是 Prolog/Datalog 的基础。比完整命题逻辑弱（没有析取 ∨ 和否定 ¬），但正因为弱，推理是多项式时间且不会爆炸。

加上连续概率后，Gaia 成为**概率化的 Horn 逻辑**——在 Datalog 的基本模式上叠加 [0,1] 值域和信念传播。

### 6.4 析取和否定藏在节点里

图结构层没有 ∨ 和 ¬，但这不意味着 Gaia 不能表达它们——它们藏在节点的 content 里：

```python
Node(content="材料X在高温下稳定，或存在相变临界温度")  # 内含 ∨
Node(content="排除基因因素后，吸烟仍导致肺癌")        # 内含 ¬ 和 →
Node(content="对所有稀土元素，掺杂可提升超导温度")      # 内含 ∀
```

BP 把这些都视为不透明的原子。**图结构保持简单（可计算），逻辑丰富性放在内容层（由人/LLM 处理）。**

### 6.5 Pre-grounded：无 Grounding 瓶颈

Markov Logic Networks (MLN) 存储通用规则（`∀x: Metal(x) ∧ Heated(x) → Expands(x)`），推理时需要对每个具体金属实例化——O(N^k) 个基底子句。

Gaia 不存通用规则。每条超边已经是具体的、grounded 的推理步骤。知识贡献者在提交时就指定了具体前提和结论。代价是无法直接表达"对所有金属都成立"——只能靠积累具体实例，通过 BP 传播信念。

---

## 7. 在形式系统谱系中的位置

### 7.1 不是一阶逻辑，不是命题逻辑

Gaia 不是一阶逻辑（没有量词和变量）；也不是经典命题逻辑：

| 特征 | 命题逻辑 | Gaia |
|------|---------|------|
| 真值 | 二元 (true/false) | 连续 [0, 1] |
| 推理 | 演绎规则 (modus ponens) | 消息传递 (BP) |
| 矛盾 | 爆炸原理 | 矛盾共存，belief 竞争 |
| 单调性 | 单调 (加前提不推翻结论) | 非单调 (新证据可降低 belief) |

### 7.2 三传统交叉

Gaia 是三个传统的交叉点：

```
         Lean
      (architecture)
          / \
         /   \
        / Gaia \
       /________\
      /          \
  概率图模型      非单调逻辑
  (semantics)    (knowledge model)
```

| 来源 | Gaia 借鉴的内容 |
|---|---|
| **Lean** | 架构：proof state、tactic 框架、构造/验证分离、交互模式、export 格式 |
| **概率图模型** (因子图, BP) | 语义：连续 belief、消息传递、近似推理 |
| **非单调逻辑** (AGM, Belief Revision) | 知识模型：retraction、contradiction、defeasible reasoning |

但 Gaia 不是"概率化的 Lean"——Lean 的依赖类型论过重、知识是单调的、验证是确定性的。详见 [language/design-rationale.md](language/design-rationale.md)。

### 7.3 与因果图的关系

因果图 (Pearl) 和 Gaia 建模的对象处于不同层面：

```
Gaia (认识论层):   "我们有多少证据支持 '吸烟导致肺癌' 这个说法？"
因果图 (本体论层):  "吸烟是否导致肺癌？如果干预吸烟行为，肺癌概率如何变化？"
```

| 维度 | 因果图 | Gaia |
|------|-------|------|
| 建模对象 | 世界的因果机制 | 我们对世界的认识 |
| 节点含义 | 变量 (吸烟量) | 命题 ("吸烟导致肺癌") |
| 边的含义 | X 导致 Y | 证据 A 支持命题 B |
| 核心问题 | "如果改变 X，Y 会怎样？" | "给定这些证据，我该多相信 Y？" |

两者正交互补：因果图可以作为 Gaia 节点的 content（一个因果模型就是一个命题），Gaia 管理**关于因果模型的知识演化**。

### 7.4 与 MLN/PSL 的对比

| 维度 | MLN/PSL | Gaia |
|------|---------|------|
| 概率类型 | 统计概率 (statistical) | 认识论概率 (epistemic, Jaynes) |
| 规则 | 通用一阶公式 | Pre-grounded 具体实例 |
| Grounding | O(N^k) | 无 |
| 推理 | Gibbs / 凸优化 | Loopy BP |
| 矛盾 | 约束冲突 | 一等公民，自动 belief 调整 |

最根本的差异：MLN 的概率是"这个公式在数据库中有多少比例的基底为真"（统计频率）；Gaia 的概率是"给定这些证据，这个命题有多可信"（Jaynes 的 plausibility）。

---

## 8. 从 Gaia Language 到 Large Knowledge Model

### 8.1 Horn Clause 的三层体现

Gaia 的 Horn clause 本质在三个层次上展开：

```
┌─────────────────────────────────────────────────────────────────┐
│  Cloud 层 (LKM 集成)                                            │
│                                                                  │
│  全局 belief 一致 :- package₁ 已集成, package₂ 已集成, ...      │
│                                                                  │
│  ← 服务端 BP 在所有已发布的 package 上运行                       │
│  ← 跨 package 的 contradiction / retraction 在此层处理          │
├─────────────────────────────────────────────────────────────────┤
│  Module 层 (语言模块系统)                                        │
│                                                                  │
│  module 可用 :- import₁ 已解析, import₂ 已解析                  │
│                                                                  │
│  ← ref 引用 = import，export = 模块接口                         │
│  ← 类似 Haskell/OCaml 模块系统，不是包管理器                     │
├─────────────────────────────────────────────────────────────────┤
│  Chain 层 (推理)                                                 │
│                                                                  │
│  结论可信 :- 前提₁ 成立, 前提₂ 成立, 前提₃ 成立                  │
│                                                                  │
│  ← Gaia 的核心层                                                 │
│  ← 概率化的 Horn clause，BP 在这一层运行                         │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 模块系统的组织语义

Gaia 的 ref/export 形成的模块依赖图是 Horn clause 的组织层——不是版本管理或接口匹配，而是知识组织和推理组合：

| 维度 | 包管理器 (Cargo/npm) | PL 模块系统 (Haskell) | Gaia Language |
|------|---------------------|----------------------|--------------|
| 核心单元 | 可独立发布的包 | 编译单元 / 模块 | 知识模块 (module YAML) |
| 依赖语义 | 硬接口（类型必须匹配） | 类型检查 | 软引用（命题 + belief） |
| 冲突处理 | SAT 求解 / 版本排他 | 类型错误 | BP + contradiction |

关键差异：Cargo 需要 SAT solver 因为**代码有硬接口**。Gaia 不需要，因为**知识引用是软的**——命题不可变，belief 是连续值，矛盾由 BP 自然处理。

### 8.3 自然科学的形式化 → LKM

整个链条：

```
自然语言论文 → LLM 形式化 → Gaia Language module → gaia build → 知识 package
    → publish → Cloud 集成 → 跨 package BP → Large Knowledge Model
```

LKM 不是一个预先设计的产品——它是自然科学被系统形式化为 Gaia 后的**自然涌现**。当足够多的知识模块被发布并集成后，跨 package 的 BP 自动产生全局一致的 belief 网络。这就是 Large Knowledge Model。

### 8.4 系统永远有解

Horn clause 系统的一个深层性质：**Gaia 永远有解。** 节点不可变 + 概率连续 = BP 总能给出一组 belief 值，只是精度不同。没有"构建失败"或"不可满足"的概念——这与 SAT-based 系统形成根本对比。不完整的知识产生不确定的 belief，但不会使系统崩溃。
