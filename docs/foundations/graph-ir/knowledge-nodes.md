# Knowledge 节点

> **Status:** Current canonical

本文档定义了 Graph IR 三个身份层中每层的 knowledge 节点 schema。Knowledge 节点是 Gaia factor graph 中的 variable node（变量节点）——它们表示具有可量化不确定性的命题。

Factor 节点（连接 knowledge 节点的约束节点）见 [factor-nodes.md](factor-nodes.md)。不同 knowledge 类型的 BP 行为见 [../cli/gaia-lang/knowledge-types.md](../cli/gaia-lang/knowledge-types.md)。

## 1. RawKnowledgeNode（来自 `gaia build`）

```
RawKnowledgeNode:
    raw_node_id:    str              # sha256(knowledge_type + content + sorted(parameters))
    knowledge_type: str              # claim | setting | question | action | contradiction | equivalence
    content:        str
    parameters:     list[Parameter]  # empty = ground, non-empty = schema (universally quantified)
    source_refs:    list[SourceRef]
```

Raw 节点是确定性的且内容寻址的：相同的源码总是产生相同的 `raw_node_id`。在这一层仅合并字节完全相同的内容。

**身份规则**：`raw_node_id = sha256(knowledge_type + content + sorted(parameters))`。这意味着具有相同类型、内容和参数的两个声明将共享同一个 raw 节点 ID，即使它们出现在包内不同的源文件中。

**Schema 与 ground**：具有非空 `parameters` 的节点是 schema（全称量化命题）。具有空 `parameters` 的节点是 ground（具体）命题。Schema 节点在展开为 ground 实例时可能生成 instantiation factor。

输出产物：`graph_ir/raw_graph.json`

## 2. LocalCanonicalNode（包级语义合并）

```
LocalCanonicalNode:
    local_canonical_id:     str
    knowledge_type:         str
    representative_content: str
    parameters:             list[Parameter]
    member_raw_node_ids:    list[str]   # one or more raw nodes merged
```

一个 agent skill 在包范围内将 raw 节点划分为语义等价组。每个 raw 节点恰好映射到一个 local canonical 节点。单例映射（一个 raw 节点对应一个 canonical 节点）是合法的，也是在没有 agent 辅助聚类的情况下的默认行为。

**代表性内容**：当多个 raw 节点合并为一个 local canonical 节点时，会选择其中一个作为代表。当前选择策略是首次遇到的节点；更智能的选择策略是一个潜在改进方向。

输出产物：`graph_ir/local_canonical_graph.json` + `graph_ir/canonicalization_log.json`

## 3. GlobalCanonicalNode（注册中心分配，审查后生效）

```
GlobalCanonicalNode:
    global_canonical_id: str                  # registry-assigned, opaque (e.g., gcn_<sha256[:16]>)
    knowledge_type:      str                  # claim, question, etc.
    kind:                str | None            # sub-classification
    representative_content: str               # content from the first contributing node
    parameters:          list[Parameter]       # for schema nodes
    member_local_nodes:  list[LocalCanonicalRef]  # all local nodes bound to this
    provenance:          list[PackageRef]      # which packages contributed
    metadata:            dict | None           # includes source_knowledge_names for ext: resolution
```

Global canonical 节点由审查/注册层在发布后分配，不在本地编写。身份信息通过 CanonicalBinding 记录来存储。

**跨包解析**：`source_knowledge_names` 元数据字段支持 `ext:package.name` 跨包引用的解析。当后续包引用先前包中的节点时，规范化引擎可通过此字段找到对应的全局节点。

> **愿景设计**：完整的全局规范化（含反驳循环）是目标架构。当前实现使用简化的 embedding 相似度匹配（在发布时执行）。

## 4. CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:  str
    global_canonical_id: str
    package_id:          str
    match_type:          str    # "match_existing" | "create_new"
```

每条绑定记录了全局规范化过程中做出的决策：一个 local 节点是被匹配到现有的全局节点，还是导致创建了一个新的全局节点。绑定在审查批准后最终确定。

## 输出产物

| 阶段 | 产物 | 内容 |
|---|---|---|
| `gaia build` | `graph_ir/raw_graph.json` | 所有 `RawKnowledgeNode` + `FactorNode` |
| `gaia build` | `graph_ir/local_canonical_graph.json` | 所有 `LocalCanonicalNode` + `FactorNode`（重新映射 key） |
| `gaia build` | `graph_ir/canonicalization_log.json` | Raw 到 local 的映射决策 |
| 审查/集成 | `CanonicalBinding` 记录 | Local 到 global 的映射决策 |

## 源代码

- `libs/graph_ir/models.py` -- `RawKnowledgeNode`, `LocalCanonicalNode`, `FactorNode`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
