# Graph IR 概述

> **Status:** Current canonical

## 目的

Graph IR（中间表示）是介于 Gaia Language 与 belief propagation 之间的结构化 factor graph。它是 CLI（本地编写工具）与 LKM（全局知识引擎）之间的**契约**。

Gaia Language 是作者编写的表层形式。Graph IR 是 BP 进行推理所依赖的机器可读结构形式。BP 运行在 Graph IR 加参数化覆盖层之上——而非直接运行在语言表层上。

Graph IR 是一个**一等提交产物**。在 `gaia publish` 期间，包会同时提交其 raw graph 和 local canonical graph。

## 三层身份体系

Graph IR 定义了三个身份层，每层代表知识身份解析的不同阶段：

### 1. RawGraph（确定性的，来自 `gaia build`）

Raw graph 是编译 Typst 源码后的直接确定性输出。Raw 节点是内容寻址的：相同的源码总是产生相同的 raw graph。在这一层仅合并字节完全相同的内容。

输出产物：`graph_ir/raw_graph.json`

### 2. LocalCanonicalGraph（包级语义合并）

一个 agent skill 在包范围内将 raw 节点划分为语义等价组。每个 raw 节点恰好映射到一个 local canonical 节点。单例映射（一个 raw 节点对应一个 canonical 节点）是合法的，也是在没有 agent 审查的情况下 `gaia build` 的默认行为。

输出产物：`graph_ir/local_canonical_graph.json` + `graph_ir/canonicalization_log.json`

### 3. GlobalCanonicalGraph（注册中心分配，审查后生效）

Global canonical 节点由审查/注册层在发布后分配，不在本地编写。身份信息通过 CanonicalBinding 记录来链接 local canonical 节点与其全局对应节点。

> **愿景设计**：完整的全局规范化（含反驳循环）是目标架构。当前实现使用简化的 embedding 相似度匹配（在发布时执行）。

节点 schema 的各层定义见 [knowledge-nodes.md](knowledge-nodes.md)。

## 规范化 JSON 与图哈希

Local canonical graph 具有确定性的 JSON 序列化。`local_graph_hash`（规范化 JSON 的 SHA-256 哈希）用作完整性校验——审查引擎从源码重新编译 raw graph 并验证其是否与提交的哈希匹配。

此哈希还用于将参数化覆盖层绑定到特定的图版本（见 [parameterization.md](parameterization.md)）。

## 构建时生成规则

编译器将 Gaia Language 表层构造翻译为 knowledge 节点和 factor 节点：

| 源构造 | Knowledge 节点 | Factor 节点 |
|---|---|---|
| `#claim` / `#setting` / `#question` / `#action`（无 `from:`） | 一个 knowledge 节点 | 无 |
| `#claim(from: ...)` / `#action(from: ...)` | 一个 knowledge 节点 | 一个 reasoning factor |
| `#relation(type: "contradiction", between: ...)` | 一个 contradiction 节点 | 一个 mutex_constraint factor |
| `#relation(type: "equivalence", between: ...)` | 一个 equivalence 节点 | 一个 equiv_constraint factor |
| Schema 展开（参数化节点） | Instance 节点 | 每对 schema-instance 一个 instantiation factor |

Knowledge 节点 schema 见 [knowledge-nodes.md](knowledge-nodes.md)。Factor 节点 schema 和类型定义见 [factor-nodes.md](factor-nodes.md)。

## Factor 节点

Factor 在三个身份层之间共享——仅节点 ID 命名空间不同。每个 factor 编码了 knowledge 节点之间的一个推理链接或结构约束。Factor 结构在 [factor-nodes.md](factor-nodes.md) 中统一定义；计算语义（potential 函数）在 [../bp/potentials.md](../bp/potentials.md) 中定义。

## 参数化

Graph IR 有意将结构与参数分离。先验概率和条件概率存在于通过哈希引用图的覆盖层对象中，而非内联在图中。见 [parameterization.md](parameterization.md)。

## 规范化

跨身份层映射节点（从 raw 到 local canonical 到 global canonical）的过程在 [canonicalization.md](canonicalization.md) 中描述。

## 源代码

- `libs/graph_ir/models.py` -- `RawGraph`, `LocalCanonicalGraph`, `FactorNode`
- `libs/graph_ir/typst_compiler.py` -- `compile_v4_to_raw_graph()`
- `libs/graph_ir/build_utils.py` -- `build_singleton_local_graph()`
- `libs/graph_ir/adapter.py` -- 从 local canonical graph 构建 `FactorGraph`
- `libs/storage/models.py` -- `FactorNode`, `CanonicalBinding`, `GlobalCanonicalNode`
