# 知识类型

> **Status:** Current canonical

Gaia 有四种知识对象的**声明类型**和两种结构约束的**关系类型**。每种类型对应一个 Typst 表面函数。

## 声明类型

### Claim (`#claim`)

可判真的科学断言，是主要的推理类型。

- **含义**：可以为真或假的命题，具有可量化的不确定性。
- **默认先验**：作者指定，在 (epsilon, 1 - epsilon) 范围内。无固定默认值；推理前必须参数化。
- **通过 `kind:` 指定子类型**：`"observation"`、`"hypothesis"`、`"law"`、`"prediction"` 等。`kind` 记录证据类型和科学角色，但不改变结构拓扑。
- **表面语法**：`#claim(kind: "observation", from: (<premise>,))[content][proof]`

### Setting (`#setting`)

上下文假设、背景条件或范围限制，在包内无需证明。

- **含义**：在本地无需理由即被接受。可被其他包的矛盾所质疑。
- **默认先验**：通常较高（作者认为是已知的），但仍在 (epsilon, 1 - epsilon) 范围内。
- **表面语法**：`#setting[content] <label>`

### Question (`#question`)

开放的科学探究，不是可判真的断言。

- **含义**：为包提供动机，但不对世界做任何断言。
- **默认先验**：不适用。Question 不参与参数化。
- **表面语法**：`#question[content] <label>`

### Action (`#action`)

程序性步骤或计算任务。与 `#claim` 共享参数签名。

- **含义**：声明要执行的程序。在科学意义上默认不是可判真的命题。
- **默认先验**：默认推理不适用。运行时特定的降级可能会赋予先验值。
- **表面语法**：`#action(kind: "python", from: (<dep>,))[content][proof]`

## 关系类型

关系通过 `#relation(type:, between:)` 声明，作为现有节点之间的结构约束。

### Contradiction (`#relation(type: "contradiction")`)

- **含义**：两个被引用的节点互斥——它们不应同时为真。
- **V1 范围**：适用于 claim、setting 和其他关系节点。不适用于 question 或裸 action。

### Equivalence (`#relation(type: "equivalence")`)

- **含义**：两个被引用的节点表达相同的命题。
- **V1 范围**：保持类型一致。对于 question 和 action，等价关系仅在具有相同根类型和相同 `kind` 的节点之间有效。

## 总结表

| 类型 | Typst 函数 | 可判真？ | `from:` | `between:` |
|---|---|---|---|---|
| Claim | `#claim` | 是 | 可选 | 否 |
| Setting | `#setting` | 是 | 否 | 否 |
| Question | `#question` | 否 | 否 | 否 |
| Action | `#action` | 否（默认） | 可选 | 否 |
| Contradiction | `#relation(type: "contradiction")` | 是 | 否 | 必需 |
| Equivalence | `#relation(type: "equivalence")` | 是 | 否 | 必需 |

## 证明状态分类

包中的每个知识节点可以根据其证明状态进行分类——即它在包的推理结构中被支持的程度：

| 证明状态 | 含义 |
|---|---|
| **Theorem** | 至少有一条推理链，其所有前提在包内已解析 |
| **Assumption** | 在包内无需证明即被接受（setting，或无 `from:` 的 claim） |
| **Hole** | 被作为前提引用但从未声明——推理中的缺口 |
| **Conjecture** | 有推理链，但至少一个前提未解析（依赖于 hole） |

运行 `gaia build --proof-state` 可生成证明状态报告。分析实现参见 `libs/lang/proof_state.py`。

## 跨层引用

- **BP 行为**：参见 [../bp/potentials.md](../bp/potentials.md)
- **Graph IR 映射**（声明如何转变为变量节点和因子节点）：参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md) 和 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)

## 源码

- `libs/storage/models.py` —— `Knowledge.type` 枚举：`claim | question | setting | action | contradiction | equivalence`
- `docs/foundations/theory/reasoning-hypergraph.md` —— 本体论分类
