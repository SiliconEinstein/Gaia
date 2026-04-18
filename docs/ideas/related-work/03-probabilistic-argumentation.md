# 3. 概率论证框架

> 状态：研究调研（2026-04-03）
>
> 本章覆盖论证理论（argumentation theory）与概率论证（probabilistic argumentation）领域的核心系统，分析其与 Gaia 的关系。Gaia 将科学命题通过类型化 DSL 声明，编译为 factor graph，运行 belief propagation 推理——这一 pipeline 与论证框架有深刻的结构对应，但也有根本性的差异。

---

## 3.1 Dung 抽象论证框架（1995）

### 框架定义

Phan Minh Dung 在 1995 年的经典论文 *On the Acceptability of Arguments and its Fundamental Role in Nonmonotonic Reasoning, Logic Programming and n-Person Games* 中提出了抽象论证框架（Abstract Argumentation Framework, AF）。其定义极其简洁：

**AF = ⟨Args, Attacks⟩**

- **Args**：一个有限的论证集合。每个论证是一个抽象节点——Dung 的框架刻意不关心论证的内部结构。
- **Attacks**：一个有向关系 Attacks ⊆ Args × Args。若 (A, B) ∈ Attacks，则说论证 A 攻击论证 B。

整个框架可以理解为一张有向图：节点是论证，边是攻击关系。

### 四种扩展语义

给定一个论证框架 ⟨Args, Attacks⟩，核心问题是：哪些论证应当被"接受"？Dung 定义了四种扩展语义（extension semantics），每种给出不同的"可接受论证集合"。

**基本概念——无冲突集与可接受集：**

- 一个集合 S ⊆ Args 是**无冲突的（conflict-free）**，当且仅当 S 中没有任何论证攻击 S 中的另一个论证。
- 一个论证 A 被集合 S **防御（defend）**，当且仅当对每个攻击 A 的论证 B，S 中存在某个论证 C 攻击 B。
- 一个无冲突集 S 是**可接受的（admissible）**，当且仅当 S 防御其所有成员。

在此基础上，四种扩展语义为：

**1. Grounded 扩展（基础扩展）**

Grounded 扩展是最小的完备扩展——它只包含那些"无论如何都应该被接受"的论证。具体来说，它是防御函数 F(S) = {A ∈ Args : S 防御 A} 的最小不动点。

**例子：** 假设有三个论证 A、B、C，其中 B 攻击 A，C 攻击 B，没有其他攻击。Grounded 扩展是 {C, A}——C 没有被攻击所以被接受，C 防御了 A（因为 C 攻击了 B），所以 A 也被接受。

**2. Preferred 扩展（偏好扩展）**

Preferred 扩展是极大的（就集合包含关系而言）可接受集。一个论证框架可以有多个 preferred 扩展。

**例子：** A 和 B 互相攻击，C 没有被攻击。Preferred 扩展有两个：{A, C} 和 {B, C}。这反映了"A 和 B 之间的争论没有定论"的直觉。

**3. Stable 扩展（稳定扩展）**

无冲突集 S 是 stable 扩展，当且仅当 S 攻击了所有不在 S 中的论证。Stable 扩展比 preferred 扩展更严格——它要求集合"主动攻击"外部的每个论证。Stable 扩展可能不存在（例如三个论证形成一个攻击环 A→B→C→A）。

**4. Complete 扩展（完备扩展）**

无冲突集 S 是 complete 扩展，当且仅当 S 恰好包含它所防御的所有论证（即 S 是 F 的不动点）。Grounded 扩展是最小的 complete 扩展；每个 preferred 扩展都是 complete 扩展。

### 怀疑接受与轻信接受

- **轻信接受（credulous acceptance）：** 论证 A 被轻信接受，当且仅当存在某个扩展包含 A。
- **怀疑接受（skeptical acceptance）：** 论证 A 被怀疑接受，当且仅当所有扩展都包含 A。

### 与 Gaia 的结构对应

Gaia 的 contradiction 算子（`⊗`）和 retraction 机制与 Dung 的攻击关系有直接的结构对应：

| Dung AF | Gaia |
|---------|------|
| 论证节点 | Knowledge（claim 类型） |
| 攻击边 (A, B) | contradiction 算子：`⊗(A, B) → helper_claim`，约束 ¬(A=1 ∧ B=1) |
| 扩展（可接受论证集） | BP 收敛后 belief > 阈值的 claim 集合 |

当两个 claim A 和 B 之间存在 contradiction 算子时，Gaia 的 BP 引擎会通过概率传播自动压低其中一个 claim 的 belief——这在效果上类似于 Dung 框架中攻击关系导致被攻击论证不被接受。但机制完全不同：Dung 通过集合论运算选择扩展，Gaia 通过连续值的消息传递迭代收敛。

### 核心局限：二值性

Dung 框架的根本局限在于其**二值性**——每个论证要么被接受，要么被拒绝，没有中间状态。这在科学推理中是不充分的。

考虑以下场景：一位材料科学家提出 claim C₁ = "Material X 在 90K 以下表现出超导性"，另一位研究者提出 claim C₂ = "Material X 在 90K 以下的电阻降低是测量误差"。在 Dung 框架中，C₁ 和 C₂ 互相攻击，框架给出两个 preferred 扩展 {C₁} 和 {C₂}——告诉我们"这两个说法不能同时成立"。但科学家真正需要的是：**在当前证据下，C₁ 的可信度是多少？** 也许基于四个独立实验室的复现数据，C₁ 的后验概率应该是 0.87，而 C₂ 的后验概率应该是 0.13。Dung 框架无法给出这样的定量判断。

这正是 Gaia 引入概率语义的根本原因。在 Gaia 中，上述场景会被建模为：

```
C₁ (prior=0.5)  ──⊗──  C₂ (prior=0.5)
                   │
              helper_claim
```

加上四组独立实验数据作为 abduction 支持 C₁，BP 运行后 C₁ 的 belief 自然上升到 0.87 左右，C₂ 被压低到 0.13——这是从 Jaynes 概率框架出发的连续值推理结果。

---

## 3.2 Toulmin 论证模型（1958）

### 六个组件

Stephen Toulmin 在 1958 年的 *The Uses of Argument* 中提出了一种结构化论证模型，将一个完整的论证分解为六个组件：

1. **Claim（主张）：** 论证者试图证成的断言。例如："该化合物在常温下是稳定的。"
2. **Data（证据/数据）：** 支撑主张的事实基础。例如："XRD 衍射实验显示该化合物在 300K 下保持晶体结构不变。"
3. **Warrant（推理许可/推理依据）：** 从 data 到 claim 的推理桥梁——解释为什么这些数据能支持这个主张。例如："晶体结构在给定温度下不变，意味着该化合物在该温度下是热力学稳定的。"
4. **Backing（后盾）：** 为 warrant 本身提供支撑的更基础的知识。例如："根据热力学第二定律和 Gibbs 自由能分析，晶格稳定性意味着化学稳定性。"
5. **Qualifier（限定词）：** 表达主张成立的确信程度。例如："大概率（probably）"、"推测性地（presumably）"、"如果没有反例（ceteris paribus）"。
6. **Rebuttal（反驳条件）：** 列出可能使主张不成立的例外情况。例如："除非该化合物在 300K 下存在亚稳态相，XRD 无法区分。"

### 与 Gaia 概念的对应

Toulmin 模型的六个组件与 Gaia 的概念体系有清晰的映射关系：

| Toulmin 组件 | Gaia 对应 | 说明 |
|-------------|-----------|------|
| **Claim** | `Knowledge(type=claim)` | 直接对应。Gaia 的 claim 是携带概率的科学断言。 |
| **Data** | `Knowledge(type=setting)` 或 `claim` 充当 `background` | Toulmin 的 data 在 Gaia 中可以是 setting（背景信息）或充当推理策略的 background 前提。当数据本身也有不确定性时，它就是 claim。 |
| **Warrant** | `Strategy(type=deduction/abduction/induction/analogy/...)` | 这是最关键的对应。Toulmin 的 warrant 回答"为什么从 data 可以得到 claim"——在 Gaia 中，这正是推理策略的角色。Gaia 将 warrant 精细化为九种命名推理策略（演绎、溯因、归纳、类比等），每种有不同的因子图展开结构。 |
| **Backing** | Strategy 的 `justification` 字段或 `metadata` | 为推理策略本身提供基础支撑。在 Gaia IR 的 strategy 中可通过 background 或 refs 字段记录。 |
| **Qualifier** | 后验概率 P(claim=1 \| evidence) | 这是 Gaia 相对于 Toulmin 的质变。Toulmin 的 qualifier 是定性词汇（"probably"、"presumably"），Gaia 将其量化为 [0,1] 区间上的连续后验概率，通过 BP 算法从整张因子图的结构自动推导得出。 |
| **Rebuttal** | contradiction 算子 `⊗` + retraction 策略 | Toulmin 的 rebuttal 列出主张可能失败的条件。Gaia 通过 contradiction 算子将两个不兼容的 claim 连接起来，通过 BP 的概率传播自动量化 rebuttal 对主张置信度的影响。 |

### Gaia 作为"带量化语义的计算化 Toulmin"

从结构角度看，Gaia 可以被理解为 **Toulmin 模型的计算化、量化扩展**：

- Toulmin 提供了论证的**解剖学**——告诉我们一个好的论证应该有哪些组成部分；
- Gaia 提供了论证的**生理学**——告诉我们这些组成部分如何通过概率传播产生定量的置信度更新。

具体来说，Gaia 对 Toulmin 的三个关键超越是：

1. **Warrant 的类型化：** Toulmin 的 warrant 是自由文本，Gaia 将其精细化为九种命名推理策略，每种对应特定的因子图展开模板和 Bayesian 推导。不同的 warrant 类型在 Gaia 中产生不同的概率更新行为。
2. **Qualifier 的量化：** "probably" 在 Toulmin 中是模糊的自然语言词汇；在 Gaia 中，qualifier 被替换为精确的后验概率——例如 0.73——它是 BP 算法在给定先验、推理策略参数和全部证据后自动计算的结果。
3. **Rebuttal 的形式化：** Toulmin 的 rebuttal 是人工列举的例外条件；在 Gaia 中，rebuttal 通过 contradiction 算子和替代解释节点（AltExp）被编码进因子图结构，其对主张置信度的影响由 BP 自动计算。

**例子：** 一位化学家主张"Catalyst A 在 500K 下的转化率超过 90%"（Toulmin claim / Gaia claim）。支撑数据是"三次独立实验测量到转化率分别为 91%、93%、89%"（Toulmin data / Gaia setting + claim）。推理依据是"多次独立实验结果一致支持该断言"（Toulmin warrant / Gaia induction 策略）。在 Toulmin 框架下，我们只能说这个 claim "probably" 成立；在 Gaia 中，BP 基于归纳策略的 noisy-AND 展开结构和三组观测数据的先验，自动计算出后验概率 0.91。

---

## 3.3 ASPIC+（Modgil & Prakken, 2014）

### 完整架构

ASPIC+ 是当前最成熟的**结构化论证框架（structured argumentation framework）**，由 Sanjay Modgil 和 Henry Prakken 在 2014 年的综合论文中系统化提出。它试图在 Dung 的抽象层和具体论证实践之间架设桥梁。

ASPIC+ 的完整架构包含以下层次：

**知识库（Knowledge Base）**由两部分组成：
- **公理前提（axiom premises, Kn）：** 不可质疑的确定性知识。
- **普通前提（ordinary premises, Kp）：** 可被质疑的假设性知识。

**推理规则** 分为两类：
- **严格规则（strict rules, Rs）：** 若前提成立则结论必然成立。形式为 `A₁, ..., Aₙ → C`。例如：{鸟(x)} → {有翅膀(x)}。
- **可废止规则（defeasible rules, Rd）：** 前提成立时结论**通常**成立，但可能有例外。形式为 `A₁, ..., Aₙ ⇒ C`。例如：{鸟(x)} ⇒ {会飞(x)}。

**论证构造：** 论证通过链式应用规则从知识库中的前提出发逐步构建。一个论证 A 有以下属性：
- `Prem(A)`：A 所依赖的前提集合
- `Conc(A)`：A 的结论
- `Sub(A)`：A 的所有子论证
- `DefRules(A)`：A 中使用的可废止规则集合
- `TopRule(A)`：A 的最后一步规则

**三种攻击方式：**
- **Undermining（前提攻击）：** 论证 A 的结论否定论证 B 的某个普通前提。
- **Rebutting（结论攻击）：** 论证 A 的结论否定论证 B 中某条可废止规则的结论。
- **Undercutting（规则攻击）：** 论证 A 的结论否定论证 B 中某条可废止规则的适用性（不攻击结论本身，而是攻击推理过程）。

构建出论证和攻击关系后，ASPIC+ 将结果映射回 Dung 的抽象论证框架，使用 Dung 的扩展语义来确定哪些论证被接受。

### 推理规则类型与 Gaia 策略的对应

ASPIC+ 的规则分类与 Gaia 的推理策略有精确的结构对应：

| ASPIC+ 规则 | Gaia 策略 | 说明 |
|------------|-----------|------|
| 严格规则 `A₁,...,Aₙ → C` | `Strategy(type=deduction)`：前提全真时结论必真 | 对应 Gaia 中 p₁=1 的软蕴含——实质上退化为严格蕴含。微观结构为 ∧ + → |
| 可废止规则 `A₁,...,Aₙ ⇒ C` | `Strategy(type=induction/abduction/analogy/...)`：前提支持但不保证结论 | 对应 Gaia 中 p₁<1 的软蕴含 ↝，通过 noisy-AND 展开 |

Gaia 的关键扩展在于：ASPIC+ 的可废止规则是**同质的**——所有可废止规则都用 `⇒` 表示，框架不关心"以什么方式"可废止。Gaia 将可废止推理细分为溯因、归纳、类比、概率估计、范式推理等多种**命名策略**，每种有不同的因子图展开结构和概率参数。

### 偏好排序 vs. 概率

ASPIC+ 使用**偏好排序（preference ordering）**来解决论证之间的冲突：给规则和前提赋予一个偏序关系（如"规则 r₁ 比 r₂ 更可靠"），然后通过提升原则（lifting principle）将规则的偏好提升为论证的偏好。如果攻击论证优于被攻击论证，则攻击成功（"defeats"）；否则攻击被阻挡。

Gaia 的概率语义提供了一种更精细的冲突解决机制。偏好排序是离散的、序数的（只能说 A 比 B 好，不能说好多少）；概率是连续的、基数的（可以说 A 的可信度是 0.82，B 的可信度是 0.31）。

### 关键对比：同一论证在 ASPIC+ 与 Gaia 下的评估

**场景：** 两位研究者对一种新材料 M 的性质存在分歧。

- 研究者 α 提出 claim C₁ = "M 在 200K 下超导"，基于一组电阻率测量数据 D₁，使用归纳推理。
- 研究者 β 提出 claim C₂ = "M 在 200K 下不超导，电阻率下降是由于杂质效应"，基于理论计算 D₂，使用演绎推理。

**在 ASPIC+ 中的评估：**

研究者 α 构建论证 A₁：D₁ ⇒ C₁（可废止规则：测量数据归纳支持超导性）。研究者 β 构建论证 A₂：D₂ → ¬C₁（严格规则：理论计算排除超导性，同时 ¬C₁ rebut C₁）。

如果偏好排序设为"严格规则优于可废止规则"，则 A₂ defeat A₁，C₁ 不被接受，C₂ 被接受。最终结果是**二值的**：C₁ 被拒绝。

**在 Gaia 中的评估：**

同一场景被编码为因子图：

```
D₁_obs₁ (prior=0.95) ──┐                      D₂_calc (prior=0.80)
D₁_obs₂ (prior=0.95) ──┤ induction策略         │
D₁_obs₃ (prior=0.90) ──┘    ↝                  │ deduction策略
                         C₁ (prior=0.5) ──⊗── C₂ (prior=0.5)
                                         │
                                    helper_claim
```

BP 运行后，假设归纳策略的替代解释先验较低（各 AltExpᵢ ≈ 0.15），三组观测数据联合提供强支持，但 C₂ 的演绎支持也很强。最终 C₁ 的后验可能收敛到 **0.68**，C₂ 收敛到 **0.32**。

这个 0.68 远比 ASPIC+ 的"拒绝"有用——它告诉科学家：当前证据对超导性有中等偏强的支持，但仍需进一步实验来消解不确定性。这正是科学推理的真实需求。

---

## 3.4 概率论证框架（Li, Oren & Norman, 2012; Hunter & Thimm, 2017）

### Li, Oren & Norman（2012）：概率化的扩展

Hengfei Li、Nir Oren 和 Timothy Norman 在 2012 年提出了 **Probabilistic Argumentation Framework (PAF)**，将概率引入 Dung 的抽象论证框架。核心想法是：

- 每个论证有一个独立的存在概率 P(A)——表示该论证能被成功构建的概率。
- 每条攻击关系也可能有概率——表示攻击成功的概率。
- 一个论证的**接受概率**定义为：它属于某个扩展的概率，即对所有可能的"论证子集实现"求和。

形式化地说，给定一个概率论证框架 ⟨Args, Attacks, P⟩，每个论证 A 的接受概率为：

> P_accept(A) = Σ_{S ⊆ Args} P(S) · 𝟙[A ∈ Extension(AF_S)]

其中 P(S) 是论证子集 S 被实现的概率，AF_S 是由 S 诱导的子框架。

### Hunter & Thimm（2017）：认知概率方法

Anthony Hunter 和 Matthias Thimm 提出了一种不同的概率化路径——**认知方法（epistemic approach）**。在他们的框架中：

- 概率不表示论证的"存在性"，而表示一个理性主体对论证"可接受性"的**信念度**。
- 一个概率函数 P 为 2^Args 上的分布，表示主体认为哪些论证集合是可接受的。
- 约束：P 必须与 Dung 的扩展语义一致——即 P 只在合法扩展上赋予非零概率。

这种方法比 Li et al. 的方法更贴近认识论（epistemology），因为它直接建模**信念**而非论证的物理存在。

### 计算复杂度问题

两种概率论证框架都面临严重的**计算扩展性问题**。核心瓶颈在于枚举扩展：

- 确定一个论证是否属于某个 preferred 扩展是 NP-complete 的。
- 确定一个论证是否被怀疑接受（属于所有 preferred 扩展）是 Π₂^P-complete 的。
- 计算接受概率需要对所有可能的论证子集求和，每个子集又需要计算扩展。

对于 n 个论证的框架，最坏情况下需要枚举 O(2^n) 个子集，每个子集上的扩展计算本身就是 NP-hard 的。

### Gaia 的 BP 方法为何更好地伸缩

Gaia 完全绕过了扩展枚举问题。其推理机制是 loopy BP（循环置信传播）：

- **每次迭代的时间复杂度**是 O(|E| · 2^k)，其中 |E| 是因子图的边数，k 是最大因子度数（在 Gaia 中通常 k ≤ 5，因为 conjunction 将多前提分解）。
- **迭代次数**通常在 10-50 次内收敛（配合 damping 参数 0.3-0.5）。
- 因此总复杂度是**多项式级别的**（对于有界因子度数的图，是线性于边数的）。

**具体伸缩性对比：**

考虑一个包含 100 个科学 claim 和 200 条推理关系的知识网络：

- **PAF 方法：** 需要枚举扩展。在 100 个节点的图上，preferred 扩展的数量可能是指数级的。即使使用剪枝优化，对于密集攻击图，计算一个论证的接受概率可能需要数分钟甚至更长。
- **Gaia BP 方法：** 100 个变量节点 + ~200 个因子节点的因子图，loopy BP 在现代硬件上的运行时间大约在 1-10 毫秒量级。即使图规模增长到 10,000 个节点，BP 仍可在秒级完成。

这种伸缩性差异不是常数因子的区别，而是**复杂度类**的区别——PAF 是指数级的（在最坏情况下），BP 是多项式级的。

### 哲学差异

更深层的差异在于推理范式：

- PAF 的概率化仍然锚定在 Dung 的扩展语义上——概率是"属于某个扩展"的概率。这意味着最终的语义仍然是集合论的，概率只是对集合论结果的加权。
- Gaia 的概率是 Jaynes 意义上的**信念度**——它不经过"扩展"这个中间概念，而是直接通过 BP 将因子图上的局部约束聚合为每个变量的边际后验。Gaia 的置信度是 BP 在整张图上推理的自然结果，而非对某种组合结构的概率化包装。

---

## 3.5 Epistemic Graphs（Hunter & Polberg, 2018）

### 概述

Epistemic Graphs 是 Anthony Hunter 和 Sylwia Polberg 在 2018 年提出的框架，也是现有论证理论中**哲学上最接近 Gaia 的系统**。它值得更详细的分析。

### 架构

Epistemic Graph 的核心定义为 **EG = ⟨Args, Edges, ε⟩**：

- **Args：** 论证（或命题）节点集合。
- **Edges ⊆ Args × Args × {+, −}：** 有向影响边，标记为正（支持）或负（攻击）。这比 Dung 框架更丰富——Dung 只有攻击边，Epistemic Graphs 同时有支持和攻击。
- **ε：** 认知约束集合。每个约束形如 "若 A 的信念度 ≥ 0.7，则 B 的信念度 ≥ 0.5" 这样的不等式条件。

每个论证节点 A 被赋予一个信念度 b(A) ∈ [0,1]，表示一个理性主体对 A 为真的确信程度。

### 约束满足方法

Epistemic Graphs 的推理机制是**约束满足**：给定一组认知约束 ε，系统寻找满足所有约束的概率分布。

具体来说：
1. 为每个论证节点 A 定义一个二值随机变量 X_A ∈ {0, 1}。
2. 认知约束定义了一组关于 P(X_A = 1) 的不等式。
3. 系统在满足所有约束的概率分布集合上找到信念度的上下界。

例如，约束"若 P(X_A=1) ≥ 0.8 则 P(X_B=1) ≥ 0.6"表达了"对 A 的高信念应该导致对 B 的至少中等信念"。

### autoepigraph.py

Hunter 和 Polberg 提供了一个小型 Python 实现 autoepigraph.py，它可以：
- 解析 Epistemic Graph 的定义（节点、边、约束）
- 通过线性规划求解满足约束的概率分布
- 输出每个节点的信念度区间

这是一个概念验证实现，代码规模在数百行量级。

### 与 Gaia 的详细对比

Epistemic Graphs 在哲学动机上与 Gaia 高度一致——两者都在论证结构上叠加概率信念度。以下是按八个维度展开的详细对比：

| 维度 | Epistemic Graphs | Gaia |
|------|-----------------|------|
| **知识表示** | 抽象论证节点 + 正/负影响边 + 认知约束 | 类型化 Knowledge 节点（claim/setting/question）+ Operator（6种确定性逻辑关系）+ Strategy（9种命名推理策略）|
| **推理机制** | 约束满足：在约束相容的概率分布空间中求解信念度界限 | Belief propagation：因子图上的 sum-product 消息传递，迭代收敛到近似边际后验 |
| **推理类型** | 未区分——所有影响边都是同质的正/负影响 | 九种命名策略：演绎、溯因、归纳、类比、概率估计、范式推理、强化、矛盾、撤回。每种有不同的因子图展开模板 |
| **工程化程度** | 概念验证级（autoepigraph.py，数百行） | 完整工程系统：Typst DSL、编译器、IR 层、BP 引擎、存储（LanceDB + 图数据库）、FastAPI 网关、review 管线 |
| **可伸缩性** | 线性规划，变量数等于约束数，适用于中小规模（数十个节点） | Loopy BP，对有界度数图线性于边数；已在数百到数千节点上验证 |
| **不确定性建模** | 信念度区间 [lower, upper]——约束满足给出范围而非点值 | 点估计后验概率——BP 给出每个变量的边际 belief；配合参数化层（priors.py）记录不确定性的结构来源 |
| **领域定位** | 通用论证理论，无特定领域 | 面向科学知识形式化——知识类型、推理策略、包模型都为科学论文和研究优化 |
| **表达力** | 可表达任意概率约束（高表达力），但结构是扁平的——没有推理策略类型 | 推理策略类型化（每种策略有不同的概率语义），但约束结构由策略的展开模板决定——不能任意指定 |
| **包与版本模型** | 无——每个 Epistemic Graph 是独立的 | 完整的包模型（Package → Module → Knowledge + Chain），QID 身份系统，content hash 去重，版本控制 |
| **审查机制** | 无 | 参数化层（priors.py）：每条推理链附带 reason+prior 配对，审查结论影响先验和策略参数 |

### Gaia 从 Epistemic Graphs 继承的哲学基础

Gaia 与 Epistemic Graphs 共享以下哲学立场：

1. **论证节点应该有连续的信念度**，而不是二值的"接受/拒绝"。
2. **攻击和支持都应该是一等公民**——不能只有攻击（如 Dung），因为科学推理中支持关系至少和攻击关系一样重要。
3. **信念度应该通过结构约束相互影响**——一个节点的信念度变化应该传播到相关节点。

### Gaia 超越 Epistemic Graphs 的地方

1. **推理策略类型化：** Epistemic Graphs 的正/负影响边是同质的——一条"+"边既可能是演绎支持也可能是归纳支持，框架不区分。Gaia 的九种命名推理策略各自有不同的概率语义（不同的因子图展开模板和参数），这意味着"为什么支持"在 Gaia 中是一等公民。

2. **因子图编译：** Epistemic Graphs 直接在约束上运算；Gaia 将推理结构**编译**为标准因子图——一个成熟的概率图模型中间表示。这使得 Gaia 可以利用概率图模型领域数十年的算法研究（BP、Junction Tree、GBP、variational methods）。

3. **可伸缩 BP 推理：** 约束满足在变量数增长时面临 LP 规模膨胀问题；BP 是 O(|E|) 每迭代，实践中收敛快。

4. **包模型与工程系统：** Epistemic Graphs 是一个独立的数学对象；Gaia 有完整的生命周期——作者用 Typst DSL 编写、编译到 IR、注册到 registry、review 后集成到 LKM 的全局知识图。

5. **参数化层（priors.py）：** Gaia 为每条推理链附带 inline 的 reason+prior 配对（验证研究设计、数据完整性、推理有效性等维度），审查结论可以调整先验和策略参数。这在 Epistemic Graphs 中没有对应。

6. **科学领域特化：** Gaia 的知识类型（claim/setting/question）、推理策略（演绎/溯因/归纳/类比/...）、包模型（对应科学论文）都是为科学知识形式化设计的。Epistemic Graphs 是领域无关的通用框架。

---

## 3.6 Carneades 论证模型（Gordon, Prakken & Walton, 2007）

### 证明标准

Thomas Gordon、Henry Prakken 和 Douglas Walton 在 2007 年提出的 Carneades 论证模型引入了一个独特的概念——**证明标准（proof standard）**。不同的 claim 可以有不同的证明标准，标准决定了"多少证据才足以接受该 claim"。

Carneades 定义了五种证明标准，按严格程度递增排列：

1. **Scintilla of evidence（微量证据）：** 只要存在至少一个支持论证且该论证没有被彻底击败，claim 就被接受。这是最低标准——"有一丁点证据就行"。
   - **例子：** 在初步科学假设阶段，只要有一组实验数据暗示某种效应存在，就值得进一步研究。

2. **Preponderance of evidence（优势证据）：** 支持的论证在数量和质量上整体超过反对的论证。
   - **例子：** 在流行病学研究中，如果大多数研究支持某种因果关系而少数不支持，可以初步接受该因果关系。

3. **Clear and convincing evidence（明确且令人信服的证据）：** 支持论证明显强于反对论证，中间不存在严重的未解决质疑。
   - **例子：** 在新药审批中，III 期临床试验数据必须明确展示药效优于安慰剂。

4. **Beyond reasonable doubt（排除合理怀疑）：** 几乎不存在合理的替代解释。
   - **例子：** 宣布发现新粒子（如 Higgs boson）需要 5σ 统计显著性。

5. **Dialectical validity（辩证有效性）：** 所有反对论证都被成功反驳，支持论证形成完整无缺的论证链。
   - **例子：** 数学证明——每一步都必须严格正确，不能有跳跃或遗漏。

### 听众（Audiences）

Carneades 引入了**听众（audience）**概念。不同的听众对论证赋予不同的权重——同一个论证，法官可能认为它很有力，而科学家可能认为它证据不足。形式上，一个 audience 是一个函数，为每个论证赋予一个权重值。

这与 Gaia 的**参数化层（priors.py）**有弱平行关系。在 Gaia 中，priors.py 记录审查者对推理链的结构化评估（以 reason+prior 配对形式），审查结论可以调整先验和策略参数。不同审查者可能给出不同的评估——这在功能上类似于 Carneades 中不同听众赋予不同权重。

但两者有重要差异：

- Carneades 的听众权重直接决定论证是否满足证明标准——这是一个**判定（decision）**。
- Gaia 的 review 评估影响的是先验和参数——这些参数再通过 BP 传播产生后验。review 不直接判定 claim 是否成立，而是通过调整输入参数间接影响 BP 的输出。判定留给了概率推理本身。

### 证明标准 vs. 连续后验概率

Carneades 的证明标准本质上是**定性阈值**——它们把连续的证据强度离散化为几个档位。这与 Gaia 的连续后验概率形成对比：

| 特性 | Carneades 证明标准 | Gaia 后验概率 |
|------|-------------------|-------------|
| 值域 | 5 个离散等级 | [0, 1] 连续实数 |
| 语义 | "够不够"——满足/不满足某个标准 | "多可信"——连续信念度 |
| 领域适应 | 通过选择不同标准来适应不同领域 | 通过设置不同先验和策略参数来适应不同领域 |
| 计算方式 | 论证权重的定性比较 | BP 在因子图上的消息传递 |
| 信息量 | 低——只知道是否达标 | 高——知道精确的可信度 |

**例子：** 一项材料的超导性 claim 在 Carneades 中可能被评为"满足 clear and convincing evidence 标准"或"仅满足 preponderance 标准"。在 Gaia 中，同一 claim 的后验概率可能是 0.82——它同时蕴含了"这个 claim 很可能为真"（相当于满足 clear and convincing 标准）以及"还有约 18% 的不确定性"这两层信息。

更关键的是，Gaia 的连续后验概率允许**渐进更新**。当新证据到来时，0.82 可以平滑地更新为 0.87 或 0.74——而不需要在离散的证明标准等级之间跳跃。在科学研究中，证据的积累本来就是渐进的，连续概率比离散阈值更自然地捕捉了这种渐进性。

---

## 3.7 本章总结：从论证到概率推理

纵观整个论证理论领域，可以看到一条清晰的演化路径：

1. **Dung (1995)**：纯抽象、纯定性——论证是节点，攻击是边，语义是扩展。
2. **Toulmin (1958)**：结构化但仍定性——论证有内部结构（data/warrant/backing），但 qualifier 是模糊词汇。
3. **ASPIC+ (2014)**：结构化且有规则类型——区分严格/可废止规则，但仍无概率。
4. **PAF (2012) / Hunter & Thimm (2017)**：概率化——在 Dung 的扩展上叠加概率，但计算复杂度成为瓶颈。
5. **Epistemic Graphs (2018)**：信念度 + 约束满足——哲学上最接近连续概率推理，但缺乏工程系统。
6. **Carneades (2007)**：证明标准——试图在定性和定量之间取折中，引入离散阈值。

**Gaia 在这条路径上的位置**可以概括为：

> Gaia 将 Epistemic Graphs 的哲学直觉（信念度 + 影响传播）与 ASPIC+ 的结构洞察（命名推理类型）结合，通过 Jaynes 概率框架给出严格的量化语义，编译到成熟的因子图中间表示，运行可伸缩的 BP 推理，并包裹在面向科学知识的完整工程系统中（DSL → 编译 → IR → 推理 → 审查 → 发布）。

论证理论为 Gaia 提供了结构灵感——特别是"论证有类型化的内部结构"（Toulmin/ASPIC+）和"论证节点应有连续信念度"（Epistemic Graphs）这两个核心洞察。但 Gaia 的计算语义来自概率图模型而非论证理论——它不依赖扩展语义，不使用证明标准，而是通过因子图 + BP 实现端到端的概率推理。这种组合在现有文献中没有直接先例。
