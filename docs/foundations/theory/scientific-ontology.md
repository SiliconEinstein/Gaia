# 科学本体论

> **Status:** Target design — foundation baseline
>
> 本文档定义 Gaia 的科学对象模型，供后续基础文档复用。

## 1. 目的

本文档在语言和 BP 细节分化之前，回答四个基本问题：

1. Gaia 中存在哪些科学对象？
2. 哪些对象具有真值、可以参与 BP？
3. 哪些操作是确定性蕴含，哪些是概率性支持？
4. 哪些区分属于编写语言层面，哪些仅属于审查/策展层面？

本文档对本体论和建模边界具有规范性。

本文档**不**定义：

- 编写语言的具体语法
- Graph IR 的字段布局
- 因子势函数的公式
- 服务器 API 合约

## 2. 第一原则

Gaia 不是孤立地形式化抽象逻辑。它形式化的是**具有证据溯源、适用条件、不确定性和可修正性的科学断言**。

核心边界：

- **只有封闭的、具有真值的科学断言参与 BP**
- **开放模板、发现工作流和研究任务不直接参与 BP**

## 3. 科学推理的独特之处

与形式演绎逻辑相比，科学推理有五个额外层次：

1. **世界接口**：前提来自观测、测量、实验和文献——而非来自公理。
2. **不确定性**：我们很少证明一个命题为真；我们评估的是在当前证据下它的可信程度。
3. **适用条件**：科学定律几乎总是附带体系限制、理想化条件和背景假设。
4. **可废止性（defeasibility）**：新证据可以削弱旧结论。矛盾不是系统故障，而是知识更新信号。
5. **开放式发现**：溯因推理、归纳推理和隐含前提的发现都超出纯演绎逻辑的范畴。

## 4. 对象类别

### 4.1 Template（模板）

Template 是一个开放的命题模式或谓词形式。

示例：

- `falls_at_rate(x, medium)`
- `critical_temperature(material, pressure)`
- `P(x) -> Q(x)`

Template 类似于谓词或开放公式。它**不是**封闭命题，不直接携带真值信念。

Template **不**进入 BP。

### 4.2 ClosedClaim（封闭断言）

ClosedClaim 是一个封闭的、具有真值的科学断言。

示例：

- "在月球真空中，羽毛和锤子以相同速率下落。"
- "该样本在 90 K 以下表现出超导性。"

ClosedClaim 是默认的 BP 承载断言类别。

### 4.3 ObservationClaim（观测断言）

ObservationClaim 是一种 ClosedClaim，其主要权威性来自观测而非推导。

示例：

- 报告的实验结果
- 测量到的天文信号
- 被解读为命题的仪器读数

ObservationClaim 仍然是 claim，而非独立的逻辑物种。其区分对审查、溯源和默认先验有意义。

### 4.4 MeasurementClaim（测量断言）

MeasurementClaim 是一种以观测为中心的断言，绑定了量值、单位、校准和不确定性结构。

示例：

- "转变温度为 92 ± 1 K。"
- "测量的红移为 z = 0.5。"

MeasurementClaim 是 ObservationClaim 的特化。它仍然具有真值，但通常携带更严格的定量元数据要求。

### 4.5 HypothesisClaim（假说断言）

HypothesisClaim 是作为解释性或预测性候选项提出的断言，而非已确立的定律或直接观测。

示例：

- 对异常现象的暗物质解释
- 对矛盾模式的隐变量解释

HypothesisClaim 像其他封闭断言一样进入 BP，但其认识论地位是不同的。

### 4.6 LawClaim（定律断言）

LawClaim 是一个封闭的、一般性的科学断言，其内容包含明确的适用范围、领域和体系。

示例：

- "对于真空中靠近地球的刚体，加速度与质量无关。"
- "对于稀薄态下的理想气体，PV = nRT。"

LawClaim 不是裸模板。它是一个**封闭**命题，通常带有明确的量化或领域限制。

LawClaim 可以参与 BP。

### 4.7 PredictionClaim（预测断言）

PredictionClaim 是在特定假设下由模型、定律或假说推导出的断言。

示例：

- "在绑体装置下，复合体必须下落更快。"
- "给定模型 M 和参数 θ，光谱应在 λ 处达到峰值。"

它仍然是 ClosedClaim，但其溯源和评估策略不同于直接观测。

### 4.8 RegimeAssumption（体系假设）

RegimeAssumption 是一个背景条件、理想化假设或适用性约束，表示某个推理步骤或定律在其之下成立。

示例：

- 真空
- 非相对论体系
- 可忽略空气阻力
- 近地近似

RegimeAssumption 具有真值且可被质疑。

### 4.9 AbstractClaim（抽象断言）

AbstractClaim 是从多个更具体的断言中提取出的新的、更弱的封闭断言。

必要性质：

- 每个成员断言都蕴含该 AbstractClaim

这是一个向上的、保真的操作。AbstractClaim 是断言，不是模板。

### 4.10 GeneralizationCandidate（泛化候选）

GeneralizationCandidate 是从多个具体案例归纳出的更强、更广的候选定律或解释模式。

必要性质：

- 成员断言支持它，但**不**单独蕴含它

这是一个非演绎对象。它可能后续被提升为 LawClaim，但它不等价于 AbstractClaim。

### 4.11 Question（问题）

Question 是一个探究制品，不是具有真值的命题。

示例：

- 未解决的科学问题
- 后续调查目标

Question 不直接进入 BP。

## 5. 算子族

### 5.1 reasoning_support（推理支持）

reasoning_support 是前提与结论之间的概率性支持关系。

它涵盖普通推理链接，如：

- 演绎式支持
- 溯因式支持
- 归纳式支持

其具体的更新规则由推理理论文档定义，不在本文档中。

### 5.2 entailment（蕴含）

entailment 是封闭断言之间的确定性保真关系。

如果 A 蕴含 B，则：

- A 支持 B
- ¬A **不**一般意味着 ¬B

这个族是许多抽象式边的正确语义归属。

### 5.3 instantiation（实例化）

instantiation 从更一般的定律或模式断言推导出一个具体的封闭断言。

示例：

- 从全称定律到案例特定的实例
- 从模式断言到具体的绑定案例

instantiation 在结构上不同于一般蕴含，但其 BP 内核可能最终复用确定性蕴含语义。

### 5.4 inductive_support（归纳支持）

inductive_support 是从具体案例到更广假说或候选定律的概率性支持。

它不保真。它必须与 entailment 区分开来。

### 5.5 contradiction / equivalence（矛盾/等价）

这些是具有真值的断言之间的约束关系。

- **contradiction**（矛盾）：相关断言不应同时为真
- **equivalence**（等价）：相关断言应在真值上一致

它们可能作为关系承载变量和约束因子参与 BP。

## 6. 构造性操作 vs BP 算子

以下区分是强制性的：

### 6.1 图构造/研究操作

这些操作创建或提议新的知识结构：

- 抽象（abstraction）
- 泛化（generalization）
- 隐含前提发现（hidden premise discovery）
- 独立证据审计（independent evidence audit）

它们**不是**自动的 BP 边类型。

### 6.2 BP 算子族

这些算子决定了图被接受后信念更新如何传播：

- reasoning_support
- entailment
- instantiation
- inductive_support
- contradiction
- equivalence

Jaynes 式弱三段论是这些 BP 算子上的合约，不是新的语言声明。

## 7. 什么进入 BP

### 7.1 承载 BP 的对象

以下对象在审查/接受后可以进入 BP：

- ClosedClaim
- ObservationClaim
- MeasurementClaim
- HypothesisClaim
- LawClaim
- PredictionClaim
- RegimeAssumption
- 已接受的 contradiction / equivalence 关系

### 7.2 非 BP 对象

以下对象**不**直接进入 BP：

- Template
- Question
- 接受前的 GeneralizationCandidate
- 审查发现
- 策展建议
- 循环审计制品
- 独立证据审计报告

## 8. 命题，而非实体

传统知识图谱存储**实体**（爱因斯坦、乌尔姆），通过**关系**（出生于）连接。Gaia 存储**命题**（"爱因斯坦出生于乌尔姆"），通过**推理链接**（前提支持结论）连接。

| 维度 | 实体级（传统知识图谱） | 命题级（Gaia） |
|------|----------------------|---------------|
| 节点 | 世界中的事物 | 关于世界的断言 |
| 边 | 关系（出生于） | 推理步骤（前提 → 结论） |
| 不确定性 | 无（存储 = 为真） | 先验、信念、概率 |
| 矛盾 | 数据质量问题 | 一等公民 |
| 溯源 | 可选元数据 | 核心结构（推理链） |

## 9. 可废止性

科学信念随新证据而变化。这通过三种机制形式化：

- **通过 BP 的信念更新**：当新因子（推理链接）被添加到图中时，BP 重新计算所有信念。一个先前高信念的断言可能被新的矛盾证据降低。
- **矛盾（contradiction）**：明确声明两个断言不应同时为真的关系。BP 自动削弱支持较少的断言。
- **撤回（retraction）**：明确声明先前反对某断言的证据被撤回。被撤回证据的影响被反转。

可废止性不是缺陷或特殊情况——它是区分科学推理与演绎证明的核心特征。在 Gaia 中，非单调性（新前提可以降低旧结论的信念）被内建于推理引擎中。

## 10. 审查/策展边界

本体论不将审查制品混入知识内容。

- 策展发现的潜在矛盾**尚不是**已接受图中的矛盾断言
- 佐证/独立证据发现**不是**语言关系或 BP 因子
- 泛化候选**尚不是**定律

这些制品在被相应工作流接受之前，仍然是审查/策展制品。

## 11. 对后续文档的约束

后续文档应遵循以下规则：

1. plausible-reasoning.md 应解释科学推理为何需要这一本体论
2. 编写语言规范应仅暴露面向作者的子集
3. Graph IR 应定义已接受本体论对象的结构表示
4. 推理理论应仅在承载 BP 的子集上定义 BP 算子合约
5. 审查/策展文档应定义非 BP 制品如何被提议、审计和可能被接受

## 12. 当前方向

在当前基础重置中，Gaia 应优先：

- 小的编写语言
- 更丰富的科学本体论
- 已接受的图结构与研究/策展制品之间的清晰分离
- 在已接受的封闭断言上运行 loopy BP，而非在模板或工作流对象上

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Cox, R.T. "Probability, Frequency and Reasonable Expectation" (1946)
- Polya, G. *Mathematics and Plausible Reasoning* (1954)
