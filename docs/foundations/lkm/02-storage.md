# 存储模型

> **Status:** Target design

## 概述

LKM 的存储围绕 **Local / Global 对偶 FactorGraph** 组织。Local FactorGraph 保留 ingest 后的完整内容（文本、推理步骤），Global FactorGraph 只保留图结构和参数化信息，不存文本内容。两者通过 CanonicalBinding 桥接。

概率参数和推理结果分别存储在独立的参数化层和信念快照中。BP 内部使用的 int 索引是实现细节，不构成独立的"运行时 FactorGraph"。

## Local / Global FactorGraph

### 为什么分两层

- BP 只需要图结构和参数，不需要文本
- Content 的 source of truth 在 local，global 只是结构索引
- 避免 merge 时的内容同步问题（curation binding 时只需更新指针和 local_members）
- 与上游 Gaia IR canonicalization 设计对齐（`05-canonicalization.md §7`）

### Content 访问路径

`global_variable_nodes[gcn_id].representative_lcn` → `local_variable_nodes[local_id].content`，两次主键查询。

### Local Variable Nodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | QID 格式：`{namespace}:{package_name}::{label}` |
| `type` | str | `claim` / `setting` / `question` |
| `visibility` | str | `public`（作者显式声明）/ `private`（lowering FormalStrategy 产生的中间节点） |
| `content` | str | 命题的自然语言描述 |
| `content_hash` | str | `SHA-256(type + content + sorted(parameters))`，不含 package_id（跨包稳定） |
| `parameters` | list | 全称命题的参数列表（如 `[{name: "x", type: "material"}]`） |
| `metadata` | dict | 可选元数据：文献引用 (refs)、schema 分类等 |

### Global Variable Nodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | gcn_id，全局唯一 |
| `type` | str | `claim` / `setting` / `question` |
| `visibility` | str | `public` / `private` |
| `content_hash` | str | SHA-256，仅用于 dedup 索引 |
| `parameters` | list | 全称命题的参数列表 |
| `metadata` | dict | 可选元数据 |
| `representative_lcn` | dict | 代表性 local node：`{package_id, local_id}` |
| `local_members` | list | 所有映射到此 global node 的 local node：`[{package_id, local_id}, ...]` |

Global variable node **不存 content**——content 通过 `representative_lcn` 指向 local 层获取。

**Visibility 规则（对齐 [Gaia IR helper claims](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/04-helper-claims.md)）：**

- `public`：可有独立 PriorRecord，参与 canonicalization，暴露给查询
- `private`：禁止独立 PriorRecord，不参与 canonicalization，不暴露给普通查询。Prior policy 遵循上游 Gaia IR 定义

### Local Factor Nodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | local factor 唯一标识 |
| `factor_type` | str | `strategy` / `operator` |
| `subtype` | str | 见下表 |
| `premises` | list[str] | Premise variable QIDs |
| `conclusion` | str | Conclusion variable QID |
| `steps` | list[dict] | 推理步骤：`[{reasoning: ...}]` |
| `source_package` | str | 来源包标识 |

### Global Factor Nodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | global factor 唯一标识 |
| `factor_type` | str | `strategy` / `operator` |
| `subtype` | str | 见下表 |
| `premises` | list[str] | Premise variable gcn_ids |
| `conclusion` | str | Conclusion variable gcn_id |
| `source_package` | str | 最初创建此 factor 的来源标识 |

Global factor node **不存 steps**——steps 通过 local factor 获取。

**factor_type + subtype 严格对齐 [Gaia IR](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/02-gaia-ir.md)：**

| factor_type | subtype | 势函数 | 需要 FactorParamRecord |
|-------------|---------|--------|----------------------|
| `strategy` | `infer` | 概率性，premises false → silent | 是 |
| `strategy` | `noisy_and` | 概率性，premises false → leak ε | 是 |
| `operator` | `implication` | 确定性 | 否 |
| `operator` | `equivalence` | 确定性 | 否 |
| `operator` | `contradiction` | 确定性 | 否 |
| `operator` | `complement` | 确定性 | 否 |
| `operator` | `conjunction` | 确定性 | 否 |
| `operator` | `disjunction` | 确定性 | 否 |
| `operator` | `instantiation` | 确定性 | 否 |

势函数详见 [势函数](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/bp/potentials.md)。

CompositeStrategy 不出现在 FactorGraph 中——lowering 时已展开为 leaf strategies。FormalStrategy 不出现——lowering 时展开为 operators + 中间 variables。

**Factor 精确匹配**：当两个 factor 具有相同的 premises + conclusion + factor_type + subtype 时，视为同一 factor（合并，各自保留 FactorParamRecord）。factor_type 或 subtype 不同则为独立 factor。

## CanonicalBinding

CanonicalBinding 记录 local node 到 global node 的身份映射（many local → one global）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `local_id` | str | QID |
| `global_id` | str | gcn_id |
| `package_id` | str | 来源包标识 |
| `version` | str | 包版本 |
| `decision` | str | `match_existing` / `create_new` / `equivalent_candidate` |
| `reason` | str | 决策原因（如 `content_hash exact match`、`cosine similarity 0.95`） |

多个 local node 绑定同一 global node 时，`global_variable_nodes[gcn_id].local_members` 增长，`representative_lcn` 指向其中一个代表。

按 `local_id` 和 `global_id` 双向索引。

## 参数化层

概率参数独立于 FactorGraph 结构存储，对齐 [Gaia IR 参数化契约](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/06-parameterization.md)。

### PriorRecord

| 字段 | 类型 | 说明 |
|------|------|------|
| `variable_id` | str | 关联的 global variable node gcn_id |
| `value` | float | 先验概率 |
| `source_id` | str | 参数来源标识 |
| `created_at` | datetime | 创建时间 |

一个 variable 可有多条 PriorRecord（来自不同 reviewer/模型）。仅 `visibility: "public"` 的 variable 可有 PriorRecord。

### FactorParamRecord

| 字段 | 类型 | 说明 |
|------|------|------|
| `factor_id` | str | 关联的 global factor node ID |
| `conditional_probabilities` | list[float] | 条件概率（数量取决于 subtype） |
| `source_id` | str | 参数来源标识 |
| `created_at` | datetime | 创建时间 |

一个 factor 可有多条 FactorParamRecord（来自不同包对同一推理关系的评估）。仅 `factor_type: "strategy"` 的 factor 需要 FactorParamRecord。

### ParameterizationSource

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_id` | str | 唯一标识 |
| `source_class` | str | 信任层级：`official` / `heuristic` / `provisional` |
| `model` | str | 产生参数的模型/方法（如 reviewer ID、LLM model name） |
| `policy` | str | 参数赋值策略 |
| `created_at` | datetime | 创建时间 |

**Source class 层级**（对齐 [上游 ecosystem 的参数治理](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/04-registry-operations.md)）：

| source_class | 来源 | 信任优先级 |
|---|---|---|
| `official` | 通过 registry 验证的 validated review reports | 最高 |
| `heuristic` | XML 提取规则估计 | 中 |
| `provisional` | mock / 自动化 review | 最低 |

Resolution policy 按 source_class 分层：同一 variable/factor 有多条参数记录时，高信任层级的记录优先。同层内按 `latest` 或 `source:<id>` 选择。`official` 参数永远不被 `heuristic` 覆盖，不可逆。

## 推理输出层

### BeliefSnapshot

每次 BP 运行后保存一份快照：

| 字段 | 类型 | 说明 |
|------|------|------|
| `snapshot_id` | str | 快照标识 |
| `timestamp` | datetime | 运行时间 |
| `graph_hash` | str | 运行时的图结构哈希 |
| `resolution_policy` | str | 本次运行使用的参数选择策略 |
| `prior_cutoff` | datetime | 本次运行使用的参数截止时间 |
| `beliefs` | dict[str, float] | gcn_id → belief 值 |
| `converged` | bool | BP 是否收敛 |
| `iterations` | int | 迭代次数 |
| `max_residual` | float | 最终最大残差 |

`resolution_policy` + `prior_cutoff` + `graph_hash` 三者共同保证 BP 结果可复现。

## 不存储的内容

| 不存 | 原因 |
|------|------|
| Gaia IR（LocalCanonicalGraph） | 传输格式，lower 后不保留 |
| Gaia Lang 源码 | CLI 职责，LKM 不接触 |
| GlobalInferenceState（单例） | 参数在参数化层，belief 在快照层 |

## 存储后端

| 后端 | 用途 | 是否必需 |
|------|------|---------|
| **LanceDB** | Local/Global FactorGraph + CanonicalBinding + 参数化层 + 快照持久化，BM25 全文搜索 | 是 |
| **Graph DB (Neo4j / Kuzu)** | 图拓扑遍历查询（仅 global 层 gcn_id 节点 + global factor 关系） | 可选 |
| **Vector Index** | Embedding 相似度搜索（curation 用） | 可选 |

Content store（LanceDB）始终是数据源。Graph store 和 vector store 是可选的加速层——缺少时系统优雅降级。Graph store 可从 content store 重建。

### LanceDB 表

| 表名 | 层 | 内容 |
|------|----|----|
| `local_variable_nodes` | local | LocalVariableNode，含 content |
| `local_factor_nodes` | local | LocalFactorNode，含 steps |
| `global_variable_nodes` | global | GlobalVariableNode，无 content |
| `global_factor_nodes` | global | GlobalFactorNode，无 steps |
| `canonical_bindings` | 桥接 | QID → gcn_id 映射 + decision |
| `prior_records` | 参数化 | PriorRecord（按 gcn_id 索引） |
| `factor_param_records` | 参数化 | FactorParamRecord（按 global factor_id 索引） |
| `param_sources` | 参数化 | ParameterizationSource |
| `belief_snapshots` | 推理输出 | BeliefSnapshot |
| `node_embeddings` | curation | local variable node embedding 向量 |

### 后端选择

通过 `StorageConfig` 配置：

- **LanceDB**：本地路径或远程 S3/TOS URI
- **Graph 后端**：`"kuzu"`（嵌入式，开发默认）、`"neo4j"`（生产）或 `"none"`
- **Vector store**：与 content store 共用 LanceDB 连接，独立表

### 实现要点

- PyArrow schema：复杂结构（list、dict）序列化为 JSON 字符串列
- `run_in_executor()` 包装所有 LanceDB 同步调用（LanceDB 是同步库）
- 批量写入：`table.add(rows)` 一次写多行，不在循环里逐条写
- `content_hash` 列建索引，用于 integrate 时 O(1) dedup 查找
- `canonical_bindings` 按 `local_id` 和 `global_id` 双向索引
- Neo4j/Kuzu `write_factors()` 用 `UNWIND` 批量写，不能逐条

## 写入协议

包 ingest 时的写入遵循先写后可见的协议：

1. 写入 local FactorGraph（状态 `preparing`，对读取不可见）
2. 写入 CanonicalBinding
3. 写入 global FactorGraph：新 variable nodes + factor nodes（含 integrate 时的确定性去重）
4. 写入参数化层：PriorRecord + FactorParamRecord
5. 写入 graph store：拓扑关系（如已配置）
6. 写入 vector store：embeddings（如已配置）
7. 标记状态为 `merged`（对读取可见）

失败时数据保持 `preparing` 状态——对读取不可见，可安全重试。
