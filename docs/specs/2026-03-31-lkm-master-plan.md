# LKM 构建主计划

> **Status:** Approved
> **Date:** 2026-03-31

## 零、设计原则

**遇到细节拿不准时，先查上游文档，不要自己发明。**

LKM 的数据模型和 canonicalization 语义在上游已有完整设计，具体参考顺序：

1. `Gaia/docs/foundations/gaia-ir/`（首要参考：identity、canonicalization、lowering、parameterization）
2. `Gaia/docs/foundations/ecosystem/`（registry 治理、curation package 流程）
3. `Gaia/docs/foundations/bp/`（BP 算法、势函数）
4. 上述文档没有答案时，再与用户讨论，不要擅自假设

---

## 一、整体架构

```
数据源
  ├── Gaia IR 包（社区作者 → Registry）         Pipeline A
  └── 论文 XML（arXiv / PubMed）                Pipeline B
                    ↓
            Ingest（per package，同步）
            lower / extract → Local FactorGraph
                    ↓
            Integrate（per package，同步）
            content_hash dedup → CanonicalBinding → Global FactorGraph
                    ↓
  ┌─────────────────────────────────────────────┐
  │  Local FactorGraph        Global FactorGraph │
  │  (content + steps)        (structure only)   │
  │  local_variable_nodes     global_variable_nodes│
  │  local_factor_nodes       global_factor_nodes  │
  │        │                         │            │
  │        └──── CanonicalBinding ───┘            │
  │              (local QID → gcn_id)             │
  │                  + PriorRecord                │
  │                  + FactorParamRecord          │
  │                  + ParameterizationSource     │
  └─────────────────────────────────────────────┘
                    ↓ （异步）
            Curation Discovery
            embedding 相似度 + 冲突检测 → 提案报告
                    ↓ （异步）
            Global BP
            loopy BP → BeliefSnapshot
                    ↓
            HTTP API（FastAPI）
            读取端：variable/factor 查询、belief、子图、BM25 搜索
```

---

## 二、Local / Global FactorGraph 的对偶关系

**核心设计决定**：两套完全对偶的 FactorGraph，global 不存文本内容。

```
Local FactorGraph                    Global FactorGraph
─────────────────                    ──────────────────
local_variable_nodes                 global_variable_nodes
  id: QID                              id: gcn_id
  content: "YBCO 在 90K 超导"          content: (不存)
  content_hash: SHA-256(...)           content_hash: SHA-256(...)  ← 仅用于 dedup 索引
  parameters: [...]                    parameters: [...]
  type, visibility                     type, visibility
                                       representative_lcn: {pkg, local_id}
                                       local_members: [{pkg, local_id}, ...]

local_factor_nodes                   global_factor_nodes
  id: local_fac_id                     id: global_fac_id
  premises: [QID, ...]                 premises: [gcn_id, ...]
  conclusion: QID                      conclusion: gcn_id
  steps: [{reasoning: ...}]            steps: (不存)
  factor_type, subtype                 factor_type, subtype
```

**为什么 global 不存 content/steps**：
- BP 只需要图结构和参数，不需要文本
- content 的 source of truth 在 local，global 只是结构索引
- 避免 merge 时的内容同步问题（curation binding 时只需更新指针和 local_members）
- 与上游 Gaia IR canonicalization 设计对齐（`05-canonicalization.md §7`）

**content 访问路径**：`global_variable_nodes[gcn_id].representative_lcn` → `local_variable_nodes[local_id].content`，两次主键查询。

---

## 三、Canonicalization 的两种关系

**CanonicalBinding**（身份映射，many local → one global）：

```
canonical_bindings:
  local_id:   "reg:galileo::ybco_90k"   ← QID
  global_id:  "gcn_abc123"              ← gcn_id
  package_id: "galileo_v1"
  version:    "1.0.0"
  decision:   "match_existing" | "create_new" | "equivalent_candidate"
  reason:     "content_hash exact match" | "cosine similarity 0.95" | ...
```

多个 local node 绑定同一 global node 时，`global_variable_nodes[gcn_id].local_members` 增长，`representative_lcn` 指向其中一个代表。

**Equivalence factor**（两个独立 global node 被声明等价）：

```
global_factor_nodes:
  factor_type: "operator"
  subtype:     "equivalence"
  premises:    ["gcn_abc123"]
  conclusion:  "gcn_def456"
```

这是图结构变更，由 curation 产出，走 registry 审查后通过正常 ingest 路径进入 global graph。

**参考**：`Gaia/docs/foundations/gaia-ir/05-canonicalization.md §2`（Binding vs Equivalence 的判断逻辑）

---

## 四、模块拆分与执行顺序

```
Phase 1（基础）                                          ✅ Done
  [M1] LKM 数据模型（Pydantic models）
  [M2] Storage layer（LanceDB + Neo4j + StorageManager）
    └── 依赖 M1

Phase 2（Ingest）                                         ✅ Done
  [M3] Pipeline A：Gaia IR lowering
    └── 依赖 M1
  [M4] Pipeline B：XML extraction
    └── 依赖 M1
  [M5] Integrate（dedup + CanonicalBinding + 写入）
    └── 依赖 M1 + M2 + M3/M4
  [—] Batch import pipeline + Neo4j graph store

Phase 3（语义发现）                                       ← Next
  [M6] Semantic Discovery（embedding + FAISS clustering）
    └── 依赖 M2 + M5
  [M6b] Relation Analysis（LLM group 分析 + package 生成）
    └── 依赖 M6

Phase 4（推理）
  [M7] Global BP
    └── 依赖 M2 + M5
  [M6c] Graph Health（conflict detection + structural audit）
    └── 依赖 M6 + M7

Phase 5（对外）
  [M8] HTTP API
    └── 依赖 M2 + M5（M6/M7 可选）
```

---

## 五、各模块详情

---

### M1 — LKM 数据模型

**设计文档**：`docs/foundations/lkm/02-storage.md`

**职责**：定义 LKM 自有的 Pydantic v2 models。与上游 `gaia.gaia_ir.*` 完全独立——gaia.gaia_ir 是 ingest 时的输入格式，不是 LKM 内部格式。

**核心 models**：

| 类名 | 层 | 说明 |
|------|----|------|
| `LocalVariableNode` | local | id=QID, type, visibility, content, content_hash, parameters, metadata |
| `LocalFactorNode` | local | id, factor_type, subtype, premises(QID), conclusion(QID), steps, source_package |
| `GlobalVariableNode` | global | id=gcn_id, type, visibility, content_hash, parameters, metadata, representative_lcn, local_members |
| `GlobalFactorNode` | global | id, factor_type, subtype, premises(gcn_id), conclusion(gcn_id), source_package |
| `CanonicalBinding` | 桥接 | local_id(QID), global_id(gcn_id), package_id, version, decision, reason |
| `PriorRecord` | 参数化层 | variable_id(gcn_id), value, source_id, created_at |
| `FactorParamRecord` | 参数化层 | factor_id(global), conditional_probabilities, source_id, created_at |
| `ParameterizationSource` | 参数化层 | source_id, source_class, model, policy, created_at |
| `BeliefSnapshot` | 推理输出 | snapshot_id, timestamp, graph_hash, resolution_policy, prior_cutoff, beliefs, converged, iterations, max_residual |

**关键设计决定**：
- `content_hash = SHA-256(type + content + sorted(parameters))`，不含 package_id（跨包稳定）
- `factor_type` ∈ `{strategy, operator}`，`subtype` 严格对齐 Gaia IR（`02-gaia-ir.md`）
- `ParameterizationSource.source_class` ∈ `{official, heuristic, provisional}`，优先级不可逆
- `visibility` ∈ `{public, private}`，private node 不参与 canonicalization，无 PriorRecord

**上游参考**：
- `Gaia/docs/foundations/gaia-ir/02-gaia-ir.md`：factor_type/subtype taxonomy 的权威来源
- `Gaia/docs/foundations/gaia-ir/03-identity-and-hashing.md`：content_hash 计算规则
- `Gaia/docs/foundations/gaia-ir/05-canonicalization.md §5`：CanonicalBinding 字段定义
- `Gaia/docs/foundations/gaia-ir/06-parameterization.md`：PriorRecord/FactorParamRecord schema

**旧代码参考**：
- `Gaia/archive:gaia/models/parameterization.py`：PriorRecord/FactorParamRecord/ParameterizationSource 结构参考（source_class 层级逻辑可复用）
- `Gaia/archive:gaia/models/binding.py`：CanonicalBinding 结构参考，但字段已更新

---

### M2 — Storage Layer

**设计文档**：`docs/foundations/lkm/02-storage.md`

**职责**：LanceDB 表 schema、读写操作、Neo4j/Kuzu 拓扑层、StorageManager facade。

**LanceDB 表**（10 张，local + global 分离）：

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

**关键实现要点**：
- PyArrow schema：复杂结构（list、dict）序列化为 JSON 字符串列
- `run_in_executor()` 包装所有 LanceDB 同步调用（LanceDB 是同步库）
- **写入协议**（对齐 `02-storage.md §写入协议`）：`preparing` → 全量写入 → `merged`；失败保持 `preparing`，对读端不可见
- 批量写入：`table.add(rows)` 一次写多行，不在循环里逐条写
- `content_hash` 列建索引，用于 integrate 时 O(1) dedup 查找
- `canonical_bindings` 按 `local_id` 和 `global_id` 双向索引

**Neo4j/Kuzu（可选拓扑层）**：
- 只存 gcn_id 节点 + global factor 关系，不重复存 content
- `write_factors()` 用 `UNWIND` 批量写，不能逐条（已知旧版性能瓶颈）
- 无 Neo4j 时优雅降级，content store 仍可全量查询

**旧代码参考**：
- `Gaia/archive:gaia/libs/storage/lance.py`：async 包装模式、PyArrow schema 定义、表初始化、row 序列化反序列化骨架——**可大量复用结构，但 schema 字段按新 models 重写**
- `Gaia/archive:gaia/libs/storage/manager.py`：StorageManager facade 模式直接复用
- `Gaia/archive:gaia/libs/storage/neo4j.py`：AsyncGraphDatabase driver 用法参考
- `Gaia/archive:gaia/libs/storage/config.py`：StorageConfig 结构参考

**测试**：integration tests 必须使用真实 LanceDB（`tmp_path` fixture，自动清理），禁止 mock DB。

---

### M3 — Pipeline A：Gaia IR Lowering

**设计文档**：`docs/foundations/lkm/03-lifecycle.md §Pipeline A`；`Gaia/docs/foundations/gaia-ir/07-lowering.md`

**职责**：将上游 `gaia.gaia_ir.LocalCanonicalGraph` lower 为 LKM 的 `(local_variable_nodes, local_factor_nodes)`。确定性，相同输入永远产出相同结果。

**Lowering 规则**（严格对齐 `07-lowering.md`）：

| 输入（Gaia IR） | 输出（LKM） |
|----------------|------------|
| Knowledge (claim/setting/question) | `visibility=public` LocalVariableNode，id=QID |
| FormalStrategy 展开的中间节点 | `visibility=private` LocalVariableNode |
| Leaf Strategy (infer/noisy_and) | `factor_type=strategy` LocalFactorNode |
| Operator (equivalence/contradiction/…) | `factor_type=operator` LocalFactorNode |
| CompositeStrategy | 展开为 leaf strategies，不出现在输出 |
| FormalStrategy | 展开为 operators + private variable nodes |

- Validated review reports → PriorRecord + FactorParamRecord（`source_class=official`）
- 上游 `gaia.gaia_ir.*` 只读，不修改

**上游参考**：
- `Gaia/docs/foundations/gaia-ir/07-lowering.md`：lowering 契约权威来源
- `Gaia/docs/foundations/gaia-ir/04-helper-claims.md`：private variable 的 visibility 规则

**旧代码参考**：
- `Gaia/archive:gaia/core/canonicalize.py`：local node 遍历结构参考，但旧版 lowering 和 canonicalize 混在一起，新版需要严格分离

---

### M4 — Pipeline B：XML Extraction

**设计文档**：`docs/foundations/lkm/03-lifecycle.md §Pipeline B`

**职责**：从论文 XML（arXiv / PubMed）rule-based 确定性提取 → `(local_variable_nodes, local_factor_nodes)`。不涉及 ML。

**提取规则**：
- 论文命题（claims）→ `visibility=public` LocalVariableNode，`type=claim`
- 显式推理关系 → `factor_type=strategy` LocalFactorNode
- 论文引用关系 → `factor_type=operator` LocalFactorNode（subtype=implication）
- 参数估计：PriorRecord + FactorParamRecord（`source_class=heuristic`，基于期刊等级、引用数等元数据）
- Local variable id = `paper:{metadata_id}::{content_hash[:8]}`（确定性 pseudo-QID）

**旧代码参考**：
- `propositional_logic_analysis/clustering/src/xml_extractor.py`：lxml 解析骨架、premises/conclusion 提取逻辑。**注意**：旧代码针对自定义 XML schema（`<assumption>/<premises>/<conclusion>` 标签），实际 arXiv XML 结构不同，需适配真实 schema
- `propositional_logic_analysis/clustering/src/utils/xml_utils.py`：XML 工具函数

---

### M5 — Integrate

**设计文档**：`docs/foundations/lkm/03-lifecycle.md §Integrate`

**职责**：将 local FactorGraph 合并入 global FactorGraph，写入 CanonicalBinding。同步，per-package。

**流程**：

1. **Variable integrate（content_hash dedup，仅 public）**：
   - 查 `global_variable_nodes WHERE content_hash = X`（走索引，O(1)）
   - 命中 → 写 CanonicalBinding（`decision=match_existing`），更新 `local_members`
   - 未命中 → 新建 GlobalVariableNode，写 CanonicalBinding（`decision=create_new`）
   - `visibility=private` 的节点直接分配新 gcn_id，不走 hash 查找

2. **Factor integrate（精确结构匹配）**：
   - 用 CanonicalBinding 将 local QIDs 映射为 gcn_ids
   - 查 `global_factor_nodes WHERE premises=? AND conclusion=? AND factor_type=? AND subtype=?`
   - 命中 → 复用 global factor，追加 FactorParamRecord
   - 未命中 → 新建 GlobalFactorNode

3. **跨包引用解析**：
   - premises/conclusion 中的非本包 QID → 查 CanonicalBinding 或 global_variable_nodes
   - 未命中 → factor 丢弃，记入 `unresolved_cross_refs`（对齐 `05-canonicalization.md §6.4`）

**上游参考**：
- `Gaia/docs/foundations/gaia-ir/05-canonicalization.md §3-6`：匹配策略、factor lifting 规则权威来源
- `Gaia/docs/foundations/gaia-ir/03-identity-and-hashing.md §3`：content_hash 用途边界

**旧代码参考**：
- `Gaia/archive:gaia/core/canonicalize.py`：node classification、factor lifting 结构参考
- **注意**：旧版全量加载 global nodes 进内存（`get_knowledge_nodes(prefix="gcn_")`）——**新实现必须走 indexed lookup，不允许全表扫描**

---

### M6 — Semantic Discovery（Embedding + Clustering）

**Spec**：`docs/specs/2026-04-04-m6-semantic-discovery.md`

**职责**：对 global variable nodes 生成 embedding，通过 FAISS 向量相似度聚类，输出语义相似的 variable 组。**只做发现，不做关系判断。**

**关键技术决策**：
- Embedding 存 ByteHouse `node_embeddings` 表（不存 LanceDB）
- 搜索用 FAISS 内存索引（IndexFlatIP + Union-Find）
- Embedding API：`https://openapi.dp.tech/openapi/v1/test/vectorize`（dashscope，512 维）

---

### M6b — Relation Analysis（LLM 关系分析 + Package 生成）

**Spec**：`docs/specs/2026-04-04-relation-analysis.md`

**职责**：对 M6 输出的每个 cluster 做 group-level LLM 关系分析（不是 pairwise），根据关系类型生成 Gaia Lang package 作为 relation proposal。

**四种 group 关系类型**：
- **Partial Overlap** → 新建 join node，每个结论 subsume join
- **Equivalence** → 新建 common conclusion，equivalence operators
- **Contradiction** → contradiction operators + 可选 join
- **Unrelated** → 丢弃

**上游参考**：
- `propositional_logic_analysis/clustering/prompts/join_symmetric.md`：prompt 写法参考
- `Gaia/docs/foundations/gaia-ir/05-canonicalization.md §2`：Binding vs Equivalence 语义

---

### M6c — Graph Health（Conflict Detection + Structural Audit）

**Spec**：`docs/specs/2026-04-04-m6c-graph-health.md`（placeholder）

**职责**：图健康检查。依赖 M7（conflict detection 需要 BP 诊断数据）。
- Conflict Detection：BP 振荡/高残差信号
- Structural Audit：孤立节点、悬空因子、未解析引用

---

### M7 — Global BP

**设计文档**：`docs/foundations/lkm/05-global-inference.md`

**职责**：从参数化层按 resolution_policy 解析参数，在 global FactorGraph 上运行 loopy BP，结果写入 BeliefSnapshot。

**实现要点**：
- 参数分层选取：`official > heuristic > provisional`（同层按 `latest` 或 `source:<id>`）
- 调用上游 `gaia.bp.BeliefPropagation`（只读，不修改上游）
- 构建 `gaia.bp.FactorGraph`（int 索引的运行时图）是实现细节，不是存储模型
- BeliefSnapshot 记录 `graph_hash + resolution_policy + prior_cutoff` 保证可复现
- `visibility=private` 的 variable 参与 BP 计算，但不暴露在 BeliefSnapshot 查询结果里

**上游参考**：
- `Gaia/docs/foundations/bp/potentials.md`：各 factor subtype 的势函数定义
- `Gaia/docs/foundations/gaia-ir/06-parameterization.md`：resolution_policy 语义

**旧代码参考**：
- `Gaia/archive:gaia/core/global_bp.py`：参数解析 + `gaia.bp` 调用接口，可直接参考，但参数化层 schema 已变更需更新

---

### M8 — HTTP API

**设计文档**：`docs/foundations/lkm/06-api.md`

**职责**：FastAPI 应用，暴露读取端 + ingest 触发端点。

**端点分组**：

| 分组 | 端点 | 功能 |
|------|------|------|
| Ingest | `POST /packages/ingest` | 触发 Pipeline A（接收 Gaia IR package） |
| Variables | `GET /variables/{id}` | 查询 variable node（含 content via representative_lcn）|
| Variables | `GET /variables` | 列表 + BM25 搜索 |
| Factors | `GET /factors/{id}` | 查询 factor node（含 steps via local lookup）|
| Graph | `GET /graph/subgraph` | N 跳子图查询 |
| Beliefs | `GET /beliefs/snapshots` | BeliefSnapshot 历史 |
| Admin | `POST /curation/run` | 手动触发 curation discovery |
| Admin | `POST /bp/run` | 手动触发 global BP |

**注意**：`GET /variables/{id}` 返回 content 时需 join `local_variable_nodes`（通过 `representative_lcn`）；`GET /factors/{id}` 返回 steps 时同理。

**旧代码参考**：
- `Gaia/archive:gaia/lkm/services/routes/`：FastAPI router 结构参考
- `Gaia/archive:gaia/lkm/services/app.py`：app 创建 + lifespan 模式参考
- `Gaia/archive:gaia/lkm/services/deps.py`：StorageManager 依赖注入参考

---

## 六、各模块对应 Spec 文件

| 模块 | Spec 文件 | 状态 |
|------|----------|------|
| M1 数据模型 | （内嵌于 master plan） | ✅ Done |
| M2 Storage layer | `2026-04-01-m2-lkm-storage.md` | ✅ Done |
| M3 Pipeline A (Lowering) | （内嵌于 master plan） | ✅ Done |
| M4 Pipeline B (XML) | （内嵌于 master plan） | ✅ Done |
| M5 Integrate | （内嵌于 master plan） | ✅ Done |
| — Batch Import Hardening | `2026-04-03-import-pipeline-hardening.md` | ✅ Done |
| M6 Semantic Discovery | `2026-04-04-m6-semantic-discovery.md` | **Next** |
| M6b Relation Analysis | `2026-04-04-relation-analysis.md` | Spec written |
| M6c Graph Health | `2026-04-04-m6c-graph-health.md` | Placeholder |
| M7 Global BP | 待创建 | Not started |
| M8 HTTP API | 待创建 | Partial |

---

## 七、全局约束

- **设计参考优先级**：上游 Gaia IR / ecosystem 文档 > 旧代码 > 自行推断；有疑问先问
- **测试**：涉及 DB 的模块必须有 integration test，使用真实 LanceDB（`tmp_path` fixture），禁止 mock DB
- **性能**：content_hash 查找必须走索引；DB 写入必须批量（`table.add(rows)`）；禁止在循环里逐条写
- **依赖方向**：`gaia_lkm` → `gaia`（只读），不能反向，不能 monkey-patch 上游
- **并发**：LanceDB 用 `run_in_executor()` 包装；Neo4j 用 `UNWIND` 批量写
- **source_class 优先级**：official 参数永远不被 heuristic/provisional 覆盖，不可逆
- **global graph 不存文本**：content 和 steps 只在 local 层，global 层通过 representative_lcn 索引
