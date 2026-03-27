# Gaia IR 概述

> **Status:** Target design — 以 `theory/01`-`theory/05` 为语义边界
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

## 目的

Gaia IR 是 Gaia 在 **theory Layer 2** 上的命题网络表示。它回答的是：

- 图里有哪些对象？
- 哪些对象是可判真的 claim？
- 哪些关系是严格逻辑关系？
- 哪些推理步骤仍然是尚未完全形式化的 coarse strategy / weakpoint？

Gaia IR **不**回答：

- 如何编译成因子图
- 如何给某条边挑选 noisy-AND / CPT 参数模型
- 如何运行 BP 或其他推理算法

这些属于 downstream 计算层。

## 一、Gaia IR 的三个对象

Gaia IR 由三种对象组成：

```text
Knowledge   +   Operator   +   Strategy
节点            严格关系        粗推理声明
```

| 对象 | 作用 | theory 对齐点 |
|------|------|---------------|
| **Knowledge** | 表示命题、背景或问题 | `04-reasoning-strategies.md` 的知识类型 |
| **Operator** | 表示 claim 之间的严格关系 | `03-propositional-operators.md` 的严格算子 |
| **Strategy** | 表示尚未充分展开的推理步骤 | `03` 的 ↝ 与 `04` 的命名推理策略 |

### Knowledge

Knowledge 有三种类型：

| type | 是否真值对象 | 说明 |
|------|-------------|------|
| **claim** | 是 | 科学断言，唯一会在 downstream 获得 prior / belief |
| **setting** | 否 | 背景设定、适用语境 |
| **question** | 否 | 待研究问题 |

`template` 不再是 Gaia IR 一等类型。全称命题直接作为 `claim(parameters != [])` 表达。

### Operator

Operator 是 claim 之间的**确定性逻辑约束**。当前核心类型包括：

- `entailment`
- `equivalence`
- `contradiction`
- `negation`
- `conjunction`
- `disjunction`

这些对象定义命题网络的严格结构，不携带自由概率参数。

### Strategy

Strategy 是**粗推理声明**。它说明某些 claim 通过某种 reasoning pattern 支撑另一个 claim，但尚未完全还原成显式 claim + strict operator 子网络。

`Strategy.type` 是语义分类，不是运行时参数模型。典型类型包括：

- `soft_implication`
- `deduction`
- `abduction`
- `induction`
- `analogy`
- `extrapolation`
- `reductio`
- `elimination`
- `mathematical_induction`
- `case_analysis`

## 二、粗命题网络与细命题网络

Gaia IR 允许图停留在不同形式化层级，但**同一条推理步骤在同一张活跃图里应只选择一个分辨率表达**。

### 粗命题网络

当某条推理还没有被完全分析时，用 Strategy 诚实记录 weakpoint：

```json
{
  "scope": "local",
  "knowledges": [
    {"id": "lcn_obs1", "type": "claim", "content": "Obs1"},
    {"id": "lcn_obs2", "type": "claim", "content": "Obs2"},
    {"id": "lcn_law", "type": "claim", "content": "Law"}
  ],
  "strategies": [
    {
      "strategy_id": "lcs_1",
      "type": "induction",
      "premises": ["lcn_obs1", "lcn_obs2"],
      "conclusion": "lcn_law"
    }
  ],
  "operators": []
}
```

### 细命题网络

当同一条推理被进一步形式化时，应把中间命题写成显式 claim，再用 Operator 连接：

```json
{
  "scope": "local",
  "knowledges": [
    {"id": "lcn_law", "type": "claim", "content": "Law"},
    {"id": "lcn_inst1", "type": "claim", "content": "Instance1"},
    {"id": "lcn_obs1", "type": "claim", "content": "Obs1"},
    {"id": "lcn_inst2", "type": "claim", "content": "Instance2"},
    {"id": "lcn_obs2", "type": "claim", "content": "Obs2"}
  ],
  "strategies": [],
  "operators": [
    {
      "operator_id": "lco_1",
      "operator": "entailment",
      "variables": ["lcn_law", "lcn_inst1"],
      "conclusion": "lcn_inst1"
    },
    {
      "operator_id": "lco_2",
      "operator": "equivalence",
      "variables": ["lcn_inst1", "lcn_obs1"],
      "conclusion": null
    },
    {
      "operator_id": "lco_3",
      "operator": "entailment",
      "variables": ["lcn_law", "lcn_inst2"],
      "conclusion": "lcn_inst2"
    },
    {
      "operator_id": "lco_4",
      "operator": "equivalence",
      "variables": ["lcn_inst2", "lcn_obs2"],
      "conclusion": null
    }
  ]
}
```

这里的关键不是“给 BP 一个可折叠/可展开的 AST”，而是：**细命题网络中的每个承重对象都必须是显式 claim。**

如果某条路径已经被细化成显式子网络，就不应再把对应 coarse strategy 作为另一条独立证据同时激活，否则会重复计数。细化是 graph rewrite / graph replacement，不是 IR 内置的 dual-resolution runtime。

## 三、显式 claim 规则

Gaia IR 不允许隐式中间命题：

- 任何被 `Operator` 或 `Strategy` 引用的 claim，都必须出现在顶层 `knowledges`
- prediction、instance、bridge claim、continuity claim 等必须写成 self-contained claim
- 不能依赖“服务器展开 strategy 时临时创建一个看不见的 claim”

这点直接对齐 [05-formalization-methodology.md](../theory/05-formalization-methodology.md)。

## 四、Background 的边界

`background` 只承载 `setting` / `question`，不承载 claim。

原因很简单：只要一个对象有真值、可被支持或反驳、会影响结论是否成立，它就应该进入 proposition network 成为显式 claim，而不是被藏进 `background`。

例如全称命题实例化中的变量绑定，应该写进结构化 `metadata.binding`，同时把实例化结果写成显式封闭 claim；而不是把 `"x = YBCO"` 作为一个假的图节点去承担推理语义。

## 五、Canonicalization 原则

规范化按**命题身份**进行，而不是按“它在 local 图里是 premise 还是 conclusion”进行。

三种情况必须分开：

1. local 与已有 global 是**同一命题**：直接 CanonicalBinding
2. 两者不是同一命题，但 reviewer 认为它们**等价**：保留为两个 global claim，再加 `equivalence`
3. 没有匹配：创建新 global claim

因此，`equivalence` 是命题层关系，不是为了解决“结论节点不能 merge”而引入的技术补丁。

## 六、Local / Global 两层

Gaia IR 仍然有 local / global 两层：

| 层 | 范围 | 作用 |
|----|------|------|
| **LocalCanonicalGraph** | 单个包内 | 存储正文 content、local strategy steps、作者局部结构 |
| **GlobalCanonicalGraph** | 跨包 | 统一命题身份，承载全局 proposition network |

Global 层通常通过 `representative_lcn` 引用 local content，但如果 review / LKM 在 global 层新增 claim，它也必须作为**显式 Knowledge** 写入图中，而不是作为隐式展开副产物存在。

## 七、下游对象

Gaia IR 之外还有两个 downstream 对象：

```text
Gaia IR          ->   Parameterization          ->   BeliefState
命题网络结构          参数层 / 输入记录               推理输出
```

它们的边界应该这样理解：

- **Gaia IR**：theory 层的结构 contract
- **Parameterization**：给 claim 和 coarse strategy 附加参数的下游层
- **BeliefState**：任一推理引擎产出的后验结果

Parameterization 和 BeliefState 可以只作用于 global graph，但它们都**不是** Gaia IR 语义的一部分。Gaia IR 不应反向依赖某个具体推理引擎的实现选择。

## 八、进一步阅读

- 详细 schema： [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md)
- theory 边界： [03-propositional-operators.md](../theory/03-propositional-operators.md), [04-reasoning-strategies.md](../theory/04-reasoning-strategies.md), [05-formalization-methodology.md](../theory/05-formalization-methodology.md)
- downstream docs： [parameterization.md](parameterization.md), [belief-state.md](belief-state.md)
