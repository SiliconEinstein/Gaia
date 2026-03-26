# 知识类型

> **Status:** Target design — 对齐 theory/ 和 gaia-ir/ 基准
>
> 基于 [2026-03-25-gaia-lang-alignment-design.md](../../specs/2026-03-25-gaia-lang-alignment-design.md) 更新。

Gaia 有三种知识对象的**声明类型**。每种类型对应一个 Typst 表面函数。

关系类型（contradiction、equivalence）不是知识类型——它们编译为 FactorNode（`reasoning_type: contradict | equivalent`）。参见 [spec.md](spec.md) 中的 `#relation` 语法。

## 声明类型

### Claim (`#claim`)

可判真的科学断言，是推理超图中唯一参与 BP 的知识类型。

- **含义**：可以为真或假的命题，具有可量化的不确定性。
- **参与 BP**：是。Claim 是唯一默认携带 probability（prior + belief）的类型。
- **默认先验**：作者指定，在 (epsilon, 1 - epsilon) 范围内。无固定默认值；推理前必须参数化。
- **通过 `kind:` 指定子类型**：`"observation"`、`"hypothesis"`、`"law"`、`"prediction"` 等。`kind` 编译为 `KnowledgeNode.metadata: {schema: <kind>}`，记录证据类型和科学角色，但不改变结构拓扑。
- **表面语法**：`#claim(kind: "observation", from: (<premise>,))[content][proof]`

### Setting (`#setting`)

上下文假设、背景条件或范围限制，在包内无需证明。

- **含义**：为理解研究提供上下文的背景信息或动机性叙述。可被其他包的矛盾所质疑。
- **参与 BP**：否。Setting 不携带 probability（无 prior、无 belief），不参与 BP 消息传递。参见 [04-reasoning-strategies.md §1.2](../theory/04-reasoning-strategies.md) 和 [gaia-ir.md §1.2](../gaia-ir/gaia-ir.md)。
- **结构依赖**：Setting 可以被 claim 通过 `from:` 引用为前提。Setting 出现在编译后 FactorNode 的 `premises` 列表中，但按 [gaia-ir §2.5 BP 参与规则](../gaia-ir/gaia-ir.md)，non-claim premise 不参与 BP 消息传递——不发送消息、不接收消息、不影响 belief 计算。Review 在分配 factor probability 时应考虑 setting 前提的内容。
- **表面语法**：`#setting[content] <label>`

### Question (`#question`)

开放的科学探究，不是可判真的断言。

- **含义**：为包提供动机，但不对世界做任何断言。
- **参与 BP**：否。Question 不携带 probability，不参与参数化。
- **表面语法**：`#question[content] <label>`

## 总结表

| 类型 | Typst 函数 | 参与 BP | 携带 prior | `from:` | `kind:` |
|------|-----------|---------|-----------|---------|---------|
| Claim | `#claim` | 是 | 是 | 可选 | 可选 |
| Setting | `#setting` | 否 | 否 | 否 | 否 |
| Question | `#question` | 否 | 否 | 否 | 否 |

> Gaia-ir 还定义了 `template` 类型（含自由变量的命题模式），但 gaia-lang v1 暂不暴露。参见 [gaia-ir.md §1.2](../gaia-ir/gaia-ir.md)。

## ∧ + ↝ 语义

`from:` 创建的粗因子，其多个前提遵循**合取 + 似然蕴含**语义（联合必要条件）：所有前提必须同时成立，结论才获得支撑。任何一个前提失败，整条推理链断裂。参见 [03-propositional-operators.md](../theory/03-propositional-operators.md)。

论证策略（`#abduction`、`#induction` 等）生成的**细命题网络**由 entailment + equivalence + contradiction 因子组合而成，所有因子 p=1——推理效果通过 BP 消息传递协作实现。参见 [05-formalization-methodology.md §2.4](../theory/05-formalization-methodology.md)。

## 证明状态分类

包中的每个知识节点可以根据其证明状态进行分类——即它在包的推理结构中被支持的程度：

| 证明状态 | 含义 |
|---|---|
| **Theorem** | 至少有一条推理链，其所有前提在包内已解析 |
| **Assumption** | 在包内无需证明即被接受（setting，或无 `from:` 的 claim） |
| **Hole** | 被作为前提引用但从未声明——推理中的缺口 |
| **Conjecture** | 有推理链，但至少一个前提未解析（依赖于 hole） |

运行 `gaia build --proof-state` 可生成证明状态报告。分析实现参见 `libs/lang/proof_state.py`。

> **注意：** 当前证明状态分类在知识类型变更（移除 action、contradiction、equivalence）和新增论证策略后可能需要重新审视。具体调整延迟到实现阶段。参见设计文档 §2.4。

## 跨层引用

- **Theory 层**：[04-reasoning-strategies.md](../theory/04-reasoning-strategies.md)（知识类型定义）、[03-propositional-operators.md](../theory/03-propositional-operators.md)（∧ + ↝ 语义、粗/细命题网络）、[05-formalization-methodology.md](../theory/05-formalization-methodology.md)（形式化工作流 §2.4）
- **Gaia IR 层**：[gaia-ir.md](../gaia-ir/gaia-ir.md)（KnowledgeNode schema §1、FactorNode schema §2、BP 参与规则 §2.5）
- **BP 层**：[potentials.md](../bp/potentials.md)（势函数设计）

## 源码

- `libs/storage/models.py` —— `Knowledge.type` 枚举（实现中待对齐为 `claim | setting | question`）
- `docs/foundations/theory/04-reasoning-strategies.md` —— 本体论分类
