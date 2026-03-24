# Factor 节点

> **Status:** Current canonical

本文档是 FactorNode 的唯一定义——Gaia factor graph 中的约束节点。Potential 函数（计算语义）见 [../bp/potentials.md](../bp/potentials.md)。

## FactorNode Schema

Graph IR 中每个 factor 都具有以下结构：

```
FactorNode:
    factor_id:    str              # f_{sha256[:16]} from (kind, module, name)
    type:         str              # reasoning | instantiation | mutex_constraint | equiv_constraint | retraction
    premises:     list[str]        # knowledge node IDs -- strong dependency, creates BP edges
    contexts:     list[str]        # knowledge node IDs -- weak dependency, no BP edges
    conclusion:   str | None       # single output knowledge node
    source_ref:   SourceRef | None # trace to authoring source
    metadata:     dict | None
```

Factor 身份是确定性的：`f_{sha256[:16]}` 由 chain ID 或源构造计算得出。相同的推理链接在重复构建时总是获得相同的 factor ID。

Factor 在三个身份层（raw、local canonical、global canonical）之间共享——仅节点 ID 命名空间不同。当 factor 在规范化过程中从 local 提升到 global 范围时，premise/context/conclusion ID 从 `lcn_` 命名空间重写为 `gcn_` 命名空间。

## Factor 类型

### reasoning

由以下声明生成：`#claim(from: ...)` 或 `#action(from: ...)`（通过 ChainExpr）。

- **Premises**：`from:` 中列出的 knowledge 节点。
- **Contexts**：间接依赖（在 v4 表层中尚不可表达）。
- **Conclusion**：被支持的 claim 或 action。
- **覆盖范围**：deduction（高 p）、induction（中等 p）、abstraction（相同 potential 形状，过渡性的）。
- **粒度**：每个 ChainExpr 一个 factor，而非每步一个。中间步骤是 chain 的内部细节。

### instantiation

由以下操作生成：schema 节点（参数化 knowledge）展开为 ground 实例。

- **Premises**：`[schema_node]` —— 全称/参数化命题。
- **Contexts**：`[]`
- **Conclusion**：ground 实例节点。
- **二元性**：每个 instantiation factor 恰好连接一个 schema 和一个 instance。部分实例化通过中间节点链式传递。

### mutex_constraint

由以下声明生成：`#relation(type: "contradiction", between: (<A>, <B>))`。

- **Premises**：`[R, A, B]`，其中 R 是 relation 节点，A 和 B 是被约束的 claim 节点。
- **Conclusion**：R（在当前运行时中充当只读门控；目标设计使 R 成为完全参与者）。

### equiv_constraint

由以下声明生成：`#relation(type: "equivalence", between: (<A>, <B>))`。

- **Premises**：`[R, A, B]`，其中 R 是 relation 节点，A 和 B 是被等价的 claim 节点。
- **Conclusion**：R（在当前运行时中充当只读门控；目标设计使 R 成为完全参与者）。
- **N 元**：分解为共享同一 relation 节点 R 的成对 factor。

### retraction

由以下操作生成：`type: "retraction"` 的 chain。

- **Premises**：反对结论的证据节点。
- **Conclusion**：被撤回的 claim。

## 编译规则

| 源构造 | Knowledge 节点 | Factor 节点 |
|---|---|---|
| `#claim` / `#setting` / `#question` / `#action`（无 `from:`） | 一个 knowledge 节点 | 无 |
| `#claim(from: ...)` / `#action(from: ...)` | 一个 knowledge 节点 | 一个 reasoning factor |
| `#relation(type: "contradiction", between: ...)` | 一个 contradiction 节点 | 一个 mutex_constraint factor |
| `#relation(type: "equivalence", between: ...)` | 一个 equivalence 节点 | 一个 equiv_constraint factor |
| Schema 展开 | Instance 节点 | 每对一个 instantiation factor |

## Context 与 Premise 的区别

- **Premise**（`premises` 字段）：承载性依赖。前提为假会削弱结论的有效性。会创建 BP 边——BP 沿这些连接发送和接收消息。
- **Context**（`contexts` 字段）：弱/背景依赖。不创建 BP 边。被参数化覆盖层在分配 factor 概率时使用。

> v4 目前仅有 `from:`（premise）。一个独立的 `under:` context 角色已计划但尚未实现。

## 存储模型说明

存储模型（`libs/storage/models.py`）使用略有不同的枚举值来表示 factor 类型。存储中的 `FactorNode` 类型枚举使用 `infer` 而非 `reasoning`，并列出：`infer | instantiation | abstraction | contradiction | equivalence`。Graph IR 规范使用 `reasoning | instantiation | mutex_constraint | equiv_constraint | retraction`。两者正在趋同；存储模型反映当前实现，而 Graph IR 反映目标 schema。

## 源代码

- `libs/graph_ir/models.py` -- Graph IR `FactorNode`
- `libs/storage/models.py` -- 存储 `FactorNode`
- [../bp/potentials.md](../bp/potentials.md) -- 每种 factor 类型的 potential 函数
