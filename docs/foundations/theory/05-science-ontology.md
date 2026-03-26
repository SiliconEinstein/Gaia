# 科学知识本体论

> **Status:** Target design
>
> 本文档定义 Gaia 中的科学对象分类：知识类型、关系类型、推理策略。
>
> **上游依赖：**
> - [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md) — 四种逻辑原语算子（蕴含、合取、析取、否定）及派生算子（等价、矛盾）
> - [03-coarse-reasoning.md](03-coarse-reasoning.md) — 粗推理算子、粗/细因子图
>
> **下游：**
> - [06-science-formalization.md](06-science-formalization.md) — 科学推理的因子图映射方法论
>
> **Graph IR 实现：**
> - [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md) — FactorNode schema, reasoning_type enum
>
> **Gaia Lang 映射：**
> - [../gaia-lang/knowledge-types.md](../gaia-lang/knowledge-types.md) — DSL 中的知识类型定义

## 1. 知识类型

Gaia 中有四种知识对象类型。**Claim 是唯一携带 probability 并参与 BP 的类型。**

### 1.1 Claim（断言）

可判真的命题。携带先验概率 π，参与信念传播（BP）。

Claim 是 Gaia 推理系统的核心承载对象——只有 Claim 拥有 belief 值，只有 Claim 之间的关系参与 BP 消息传递。所有其他类型要参与概率推理，必须通过 Template 实例化为 Claim。

示例：
- "在月球真空中，羽毛和锤子以相同速率下落。"
- "该样本在 90 K 以下表现出超导性。"

### 1.2 Setting（背景设定）

上下文假设。不携带先验，不参与 BP。

Setting 为研究提供背景信息——研究现状、动机、已知的未解决挑战、近似方法或理论框架。Setting 可以作为推理的结构性前提参与图结构（提供上下文），但不产生或接收 BP 消息。

示例：
- 某个领域的研究现状
- 一组实验的动机和出发点

### 1.3 Question（问题）

开放探究。不携带先验，不参与 BP。

Question 表达待研究的方向或未解决的科学问题。它可以作为推理的驱动性前提参与图结构，但不参与信念传播。

示例：
- 未解决的科学问题
- 后续调查目标

### 1.4 Template（模板）

含自由变量的命题模式。v1 暂不暴露。

Template 的核心作用是**桥梁**——将 Setting 或 Question 包装成 Claim，使其获得概率语义并参与 BP。

示例：
- `falls_at_rate(x, medium)`
- `"{method} can be applied in this {context}"`

Template 到 Claim 的实例化是 entailment 的特例（确定性），可跳过 review 直接升格为 permanent。

### 1.5 知识类型总结

| 类型 | 携带先验 π | 参与 BP | 说明 |
|------|-----------|---------|------|
| **Claim** | 是 | 是 | 可判真的命题，唯一的 BP 承载对象 |
| **Setting** | 否 | 否 | 上下文假设，可作结构性前提 |
| **Question** | 否 | 否 | 开放探究，驱动方向 |
| **Template** | 否 | 否 | 命题模式，通过实例化桥接到 Claim（v1 暂不暴露） |

## 2. 关系类型

三种结构性关系类型。每种由逻辑原语算子组合而成（定义见 [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md)）。

### 2.1 等价（Equivalence）

A↔B：A 和 B 的真值应保持一致。

**逻辑分解：** 等价 = 蕴含(A→B) + 蕴含(B→A)。

BP 行为：双向消息传递——A 的 belief 变化直接影响 B，反之亦然。

### 2.2 矛盾（Contradiction）

¬(A∧B)：A 和 B 不应同时为真。

**逻辑分解：** 矛盾 = 否定(A, ¬A) + 蕴含(B→¬A)。其中 ¬A 是编译器生成的辅助变量节点。

BP 行为：B 的 belief 升高 → 蕴含反向消息提升 ¬A → 否定约束压低 A。实现 explaining away。

### 2.3 否定（Negation）

A⊕B：A 和 B 真值互补。原语算子 ¬（二元约束，非一元 NOT）。

否定是矛盾和归谬推理的基础。因子图中否定是一个二元因子，连接命题及其否定形式。

**一致状态：** (1,0), (0,1)。**不一致状态：** (1,1), (0,0)。

## 3. 推理策略

七种推理策略，每种是一个**从粗因子图到细因子图的展开模板**。

粗因子图中，作者用粗推理算子（p<1）表达推理骨架。推理策略定义如何将这些粗算子展开为逻辑原语组合（所有因子 p=1）+ 中间命题，形成细因子图。关于粗/细因子图的定义和粗推理算子的语义，参见 [03-coarse-reasoning.md](03-coarse-reasoning.md)。

### 3.1 Deduction（演绎）

**类型：** 确定性。

**语义：** 三段论演绎，modus ponens。作者声明此步为确定性推导——前提成立则结论必然成立。

**粗因子图：** M→C（粗推理）

**细因子图：** M→C (p=1, 蕴含)

Deduction 是**唯一直接产生 p=1 因子的策略**。编译器将粗推理因子直接升级为蕴含。

**注意：** Modus tollens 不作为独立策略。它由蕴含因子的**反向 BP 消息**自动实现（C1 弱三段论：结论为假时，前提的可信度降低）。无需专门的展开模板。

### 3.2 Abduction（溯因）

**类型：** 不确定。

**语义：** 从观测到最佳解释的推理——观察到现象，推断最可能的假说。

**粗因子图：** []→H（无显式前提，H 为假说）

**细因子图展开：**
- 蕴含 H→O'（假说蕴含预测观测 O'，编译器生成）
- 等价 O'≡O（预测观测与实际观测等价）

**BP 路径：** O（实际观测）belief 高 → 等价传递到 O' → 蕴含因子的反向消息提升 H 的 belief。多个竞争假说的 explaining away 由 BP 自然产生。

**参数：**
- `hypothesis`：假说（claim label）
- `observation`：观测（claim label）
- `body`：溯因推理的论证文本

### 3.3 Induction（归纳）

**类型：** 不确定。

**语义：** 从多个具体实例归纳出一般规律。

**粗因子图：** [A₁..Aₙ]→B（A₁ 到 Aₙ 为实例，B 为一般规律）

**细因子图展开：**
- 蕴含 B→A₁ (p=1)
- 蕴含 B→A₂ (p=1)
- ...
- 蕴含 B→Aₙ (p=1)

布线方向：一般规律 B 蕴含每个实例 Aᵢ（如果 B 为真，每个实例必然为真）。这与认识论方向（从实例推向规律）相反，但 BP 通过反向消息自然实现归纳推理。

**BP 路径：** 多个 Aᵢ 具有高 belief → 各蕴含因子的反向消息联合提升 B 的 belief。某个 Aₖ 的 belief 降低（反例）时，对应的反向消息减弱对 B 的支撑——系统自动处理反例。

**参数：**
- `law`：一般规律（claim label）
- `instances`：实例元组（label tuple）

### 3.4 Analogy（类比）

**类型：** 不确定。

**语义：** 将源域中已建立的结构规律迁移到目标域。核心不是连续性，而是一个显式的桥梁主张。

**粗因子图：** [source]→target

**细因子图展开：**
- 蕴含 [source, analogy_claim]→target (p=1)

其中 `analogy_claim` 是编译器自动生成的辅助命题，声明源域与目标域在相关结构上可对应。类比中的不确定性不在蕴含本身，而在 `analogy_claim` 是否成立。

**BP 路径：** source belief 高 + analogy_claim belief 高 → 蕴含前向消息支撑 target。如果 analogy_claim 的 belief 降低（桥梁主张被质疑），target 的支撑自动减弱。

**参数：**
- `source`：源域规律（claim label）
- `target`：目标域结论（claim label）
- `body`：类比论证文本

### 3.5 Extrapolation（外推）

**类型：** 不确定。

**语义：** 与类比结构相同，语义区别在于外推是范围延伸（同一参数空间内做极限外推），而类比是系统迁移（不同域之间的结构对应）。

**粗因子图：** [source]→target

**细因子图展开：**
- 蕴含 [source, extrap_claim]→target (p=1)

其中 `extrap_claim` 是编译器自动生成的辅助命题，声明从已知范围到目标范围的延伸是合理的。

**BP 路径：** 与类比相同。source belief 高 + extrap_claim belief 高 → target 获得支撑。

### 3.6 Reductio（归谬）

**类型：** 依赖否定。

**语义：** 假设 P 成立，推导出矛盾，从而得出 ¬P。经典的反证法。

**粗因子图：** contradict(P, R)

**细因子图展开：**
- 蕴含 P→Q (p=1)（从 P 推出 Q）
- 矛盾 contradict(Q, R)（Q 与已知 R 矛盾）
- 否定 negation(P, ¬P)（P 和 ¬P 真值互补）

**BP 路径：** R belief 高 → contradict 压低 Q → 蕴含反向消息压低 P → negation 约束提升 ¬P。

**依赖：** 需要 negation reasoning_type（当前 Graph IR 尚未定义，参见 §3.8）。

### 3.7 Elimination（排除）

**类型：** 依赖否定。

**语义：** 排除所有备选假说，幸存者为结论。要求备选集是穷尽的。

**粗因子图：** [E₁, E₂]→H₃（E₁, E₂ 为排除证据，H₃ 为幸存假说）

**细因子图展开：**
- 矛盾 contradict(H₁, E₁)（假说 H₁ 被证据 E₁ 排除）
- 矛盾 contradict(H₂, E₂)（假说 H₂ 被证据 E₂ 排除）
- 否定 negation(H₁, ¬H₁)
- 否定 negation(H₂, ¬H₂)
- 蕴含 [¬H₁, ¬H₂]→H₃ (p=1)（穷尽性蕴含：所有备选被排除，幸存者成立）

**BP 路径：** Eᵢ belief 高 → contradict 压低 Hᵢ → negation 提升 ¬Hᵢ → 穷尽性蕴含前向消息提升 H₃。

**依赖：** 需要 negation reasoning_type（当前 Graph IR 尚未定义，参见 §3.8）。

### 3.8 推理策略总结

| 策略 | 类型 | 粗因子图 | 细因子图展开 |
|------|------|---------|-------------|
| **Deduction（演绎）** | 确定性 | M→C（粗推理） | M→C (p=1, 蕴含) |
| **Abduction（溯因）** | 不确定 | []→H | 蕴含 H→O' + 等价 O'≡O |
| **Induction（归纳）** | 不确定 | [A₁..Aₙ]→B | 蕴含 B→A₁, B→A₂, ... B→Aₙ (各 p=1) |
| **Analogy（类比）** | 不确定 | [source]→target | 蕴含 [source, analogy_claim]→target (p=1) |
| **Extrapolation（外推）** | 不确定 | [source]→target | 蕴含 [source, extrap_claim]→target (p=1) |
| **Reductio（归谬）** | 依赖否定 | contradict(P, R) | 蕴含 P→Q + 矛盾 contradict(Q,R) + 否定 negation(P,¬P) |
| **Elimination（排除）** | 依赖否定 | [E₁,E₂]→H₃ | 矛盾 + 否定 + 穷尽性蕴含 |

### 3.9 与 Graph IR reasoning_type 的关系

当前 Graph IR（[../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)）定义了五种 `reasoning_type`：

| reasoning_type | 语义 |
|---------------|------|
| `entailment` | 蕴含 |
| `induction` | 归纳 |
| `abduction` | 溯因 |
| `equivalent` | 等价 |
| `contradict` | 矛盾 |

**策略与 reasoning_type 的关系：** 推理策略是 theory 层的概念，描述粗→细展开模板。展开后产生的因子使用 Graph IR 层的 reasoning_type。

**策略使用的 reasoning_type：**

| 策略 | 使用的 reasoning_type |
|------|---------------------|
| Deduction | `entailment` |
| Abduction | `entailment` + `equivalent` |
| Induction | `entailment` |
| Analogy | `entailment` |
| Extrapolation | `entailment` |
| Reductio | `entailment` + `contradict` + **negation**（待定义） |
| Elimination | `contradict` + **negation**（待定义） + `entailment` |

**缺口：** Reductio 和 Elimination 策略需要 `negation` reasoning_type（否定算子 A⊕B），当前 Graph IR 尚未定义。这是已知的设计缺口——在 Graph IR 层新增 `negation` reasoning_type 需要独立 PR（受保护层变更流程）。在此之前，这两种策略无法完整实现。
