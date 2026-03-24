# Graph IR 概述

> **Status:** Target design — 基于 [reasoning-hypergraph.md](../theory/reasoning-hypergraph.md) 重新设计

## 目的

Graph IR（中间表示）是 Gaia 推理超图的结构化因子图表示。它是 CLI（本地编写工具）与 LKM（全局知识引擎）之间的**共享数据契约**。

- **Gaia Language** 是作者编写的表层形式。
- **Graph IR** 是推理引擎依赖的机器可读结构。
- **Parameterization** 是独立于结构的概率叠加层。

三者分离：Graph IR 只编码**什么连接什么**，不编码**多可信**。概率由 Parameterization 提供，信念由 BP 计算。

Graph IR 是一个**一等提交产物**。在 `gaia publish` 期间，包会提交其 local canonical graph。

## 两层身份体系

Graph IR 定义两个身份层，代表知识身份解析的两个阶段：

### 1. LocalCanonicalGraph（包级，来自 `gaia build`）

编译 Typst 源码后的确定性输出。每个节点有内容寻址的 `local_canonical_id`（SHA-256）。

**内容的唯一存储位置。** 所有知识内容（`content` 字段）存储在 local canonical 节点上。Global 层不重复存储内容，只引用 local 层。

输出产物：`graph_ir/local_canonical_graph.json`

### 2. GlobalCanonicalGraph（跨包，注册中心分配）

Global canonical 节点由 LKM 在发布后分配。每个 global 节点通过引用一个 **representative local canonical 节点**来获取内容，而非自身存储内容副本。这避免了跨包的长文本重复。

身份映射通过 CanonicalBinding 记录存储。

节点 schema 见 [knowledge-nodes.md](knowledge-nodes.md)。

## 规范化 JSON 与图哈希

Local canonical graph 具有确定性的 JSON 序列化。`local_graph_hash`（规范化 JSON 的 SHA-256）用于：

1. **完整性校验**：审查引擎从源码重新编译并验证哈希匹配
2. **版本绑定**：参数化覆盖层通过哈希绑定到特定图版本（见 [parameterization.md](parameterization.md)）

## 构建时生成规则

编译器将 Gaia Language 表层构造翻译为 knowledge 节点和 factor 节点：

| 源构造 | Knowledge 节点 | Factor 节点 |
|---|---|---|
| `#claim` / `#setting` / `#question`（无 `from:`） | 一个 knowledge 节点 | 无 |
| `#claim(from: ...)` | 一个 knowledge 节点 | 一个 factor（`category=infer, stage=initial`） |
| `#action(from: ...)` | 一个 claim knowledge 节点 | 一个 factor（`category=toolcall`） |
| `#relation(type: "contradiction", between: ...)` | 无 | 一个 factor（`reasoning_type=contradict`） |
| `#relation(type: "equivalence", between: ...)` | 无 | 一个 factor（`reasoning_type=equivalent`） |
| Template 实例化 | 一个 claim 节点 | 一个 factor（`reasoning_type=entailment`, probability=1.0） |

**说明：**

- `#action` 在 Gaia Language 中保留为语法糖，但在 Graph IR 层不产生独立的 knowledge 类型。它编译为一个 `type=claim` 的 knowledge 节点 + 一个 `category=toolcall` 的 factor。
- `#relation` 不再产生中间 relation knowledge 节点。contradiction 和 equivalence 直接编码为双向 factor，连接相关的 knowledge 节点。
- Template 实例化是 entailment 的特例，probability=1.0，可跳过 review 直接升格为 permanent。

Knowledge 节点 schema 见 [knowledge-nodes.md](knowledge-nodes.md)。Factor 节点 schema 见 [factor-nodes.md](factor-nodes.md)。

## Factor 节点

Factor 在两个身份层之间共享——仅节点 ID 命名空间不同。当 factor 从 local 提升到 global 时，premise/context/conclusion ID 从 `lcn_` 重写为 `gcn_`。

Factor 结构在 [factor-nodes.md](factor-nodes.md) 中统一定义。

## 参数化

Graph IR 将**结构与参数严格分离**。先验概率和 factor 概率存在于通过哈希引用图的独立覆盖层中。同一结构图可以使用不同的概率参数进行推理。见 [parameterization.md](parameterization.md)。

## 规范化

跨身份层映射节点（从 local canonical 到 global canonical）的过程在 [canonicalization.md](canonicalization.md) 中描述。所有知识类型（claim、setting、question、template）均参与全局规范化。

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalGraph`, `FactorNode`
- `libs/graph_ir/typst_compiler.py` -- `compile_v4_to_raw_graph()`
- `libs/graph_ir/build_utils.py` -- `build_singleton_local_graph()`
- `libs/graph_ir/adapter.py` -- 从 local canonical graph 构建 `FactorGraph`
- `libs/storage/models.py` -- `FactorNode`, `CanonicalBinding`, `GlobalCanonicalNode`
