# LKM API 设计 v3

> **Status:** ACTIVE (current API spec)

| 文档属性 | 值 |
|---------|---|
| 版本 | 3.0 |
| 日期 | 2026-03-03 |
| 状态 | 草稿 |
| 前置文档 | `docs/plans/2026-03-02-lkm-api-design-v2.md` (v2.4, 已被本文档取代) |
| 变更记录 | v3.0: review 重构为异步 pipeline (embedding→NN search→CC/CP abstraction→verify→BP)；所有 API 新增 batch 异步模式；重新定义 Gaia 仓库 scope——内部集成 embedding/abstraction/verify/BP 算子 |

---

## 1. 设计原则

### 1.1 超边是原子单元 (继承 v2)

LKM 是知识库（Large Knowledge Model）。所有知识以**超边**（hyperedge）的形式存在：

```
超边 = {tail: [前提命题...], head: [结论命题...], type, reasoning}
```

- 命题不独立存在，命题永远是超边的一部分
- 论文提取：`[论文上下文] ──paper-extract──→ [命题]`
- Agent 推导：`[已有命题A, B] ──induction/deduction──→ [新命题C]`
- 没有思维链的命题不允许进入图

### 1.2 超边类型 (继承 v2)

| 类型 | 说明 |
|------|------|
| `paper-extract` | 从论文中提取的推理链 |
| `abstraction` | 发现已有命题之间的关系（等价、包含、部分重叠） |
| `induction` | 从已有关系推导新知识（子类型见下） |
| `contradiction` | 发现矛盾 |
| `retraction` | 撤回已有知识 |

**Induction 子类型**：

| 子类型 | 说明 |
|--------|------|
| `reasoning` | 逻辑推理 |
| `deduction` | 严格演绎 |
| `conjecture` | 合理猜测（附 probability） |
| `contradiction` | 发现矛盾 |

### 1.3 Git-like 写入模型 (v3 更新)

写入操作统一为 commit → review → merge 三步，**review 为异步长链路 pipeline**：

```
Git                    LKM
────                   ────
git push + create PR   POST /commits               提交变更 + 轻量检查（同步）
CI pipeline            POST /commits/{id}/review    提交异步 review job
                       GET  /commits/{id}/review    查看 review 进度
                       → Embedding → NN Search      自动计算向量 + 搜索近邻
                         → CC/CP Abstraction → Verify 发现关系 + 验证推理
                         → BP                       信念传播
code review result     GET  /commits/{id}/review/result  获取审核结果
merge PR               POST /commits/{id}/merge     入图（同步）
```

### 1.4 单条同步 / 批量异步

| 模式 | 行为 |
|------|------|
| 单条请求 | 同步返回结果（review 除外，review 始终异步） |
| 批量请求 | 全部异步执行，返回 job_id，通过 Job API 查询 |

### 1.5 Review Pipeline 内部算子化

Review 不再是单次 LLM 调用，而是**多步 pipeline**，每步为独立可复用算子：

```
① Embedding       为新节点生成向量
      │
② NN Search       每个新节点搜索 20 个最近邻
      │
      ├────────────────────────┐
      ▼ (parallel)             ▼ (parallel)
③a CC Abstraction          ③b CP Abstraction
  conclusion↔conclusion     conclusion↔premise
      │                        │
  Abstraction Tree Verify  Abstraction Tree Verify
      │                        │
  Refine                   Refine
      │                        │
  Verify Again             Verify Again
      │                        │
      └───────────┬────────────┘
                  ▼
④ Belief Propagation
      │
⑤ Return verified trees + review result
```

### 1.6 两层 API 架构 (继承 v2)

```
┌──────────────────────────────────────────────────────┐
│  Layer 2: Research API  (上层 — 面向研究问题)           │
│  novelty / reliability / contradiction / provenance   │
│  （需求清单见第 8 节，详细设计待后续文档）               │
├──────────────────────────────────────────────────────┤
│  Layer 1: Knowledge Graph API  (底层 — 面向图操作)      │
│  commits / review pipeline / nodes / edges / search   │
│  （本文档详细设计的主体）                                │
└──────────────────────────────────────────────────────┘
                        │
                   共享存储层
           LanceDB (local/TOS) + Neo4j + ByteHouse (未来)
```

### 1.7 Gaia 仓库 Scope

**Gaia 负责**：

| 能力 | 说明 |
|------|------|
| Commit + Review + Merge | 写入流程，review 内含完整推理 pipeline |
| 内部算子 | embedding, nn_search, abstraction, verify, refine, bp |
| 搜索与读取 | 多路搜索、精确读取、子图查询 |
| 存储层 | LanceDB (三模式) + Neo4j + Vector Index |
| 异步 Job 管理 | review pipeline 和所有 batch 操作的 job 调度 |

**Gaia 不负责**：

| 不做 | 说明 |
|------|------|
| OCR / PDF 解析 | 外部服务 |
| 论文结构化提取 | 外部 pipeline，产出 nodes + edges 后调用 Gaia API |

### 1.8 Metadata 约定

Node 和 HyperEdge 的 `metadata` 字段需遵循以下约定，以支持按论文过滤等功能：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `paper_id` | string | 论文唯一标识 | `"arxiv:2301.12345"` |
| `location` | string | 论文内的位置标识 | `"10.1021ja800073m_2008_J.__1"` |
| `premise_id` | string | 命题在论文内的编号 | `"1"` |

> **注**：`paper_id` 是 search filter 中 `paper_id` 过滤条件的数据来源。提交 commit 时，外部 pipeline 应在 metadata 中填入 `paper_id`。

---

## 2. API 总览

### 2.1 完整 API 列表

| API | 方法 | 模式 | 功能 |
|-----|------|------|------|
| **写入** | | | |
| `/commits` | POST | 同步 | 提交变更 + 轻量检查 |
| `/commits/{id}` | GET | 同步 | 查看 commit 状态 |
| `/commits/{id}/review` | POST | 异步 | 提交 review job |
| `/commits/{id}/review` | GET | 同步 | 查看 review 进度 |
| `/commits/{id}/review` | DELETE | 同步 | 取消 review job |
| `/commits/{id}/review/result` | GET | 同步 | 获取 review 结果 |
| `/commits/{id}/merge` | POST | 同步 | 入图 |
| **批量写入** | | | |
| `/commits/batch` | POST | 异步 | 批量提交 + 自动 review + merge |
| `/commits/batch/{batch_id}` | GET | 同步 | 查看批量进度 |
| `/commits/batch/{batch_id}` | DELETE | 同步 | 取消批量 job |
| **精确读取** | | | |
| `/nodes/{id}` | GET | 同步 | 读取节点 |
| `/hyperedges/{id}` | GET | 同步 | 读取超边 |
| `/nodes/{id}/subgraph` | GET | 同步 | 节点邻居子图 |
| **批量读取** | | | |
| `/nodes/batch` | POST | 异步 | 批量读取节点 |
| `/hyperedges/batch` | POST | 异步 | 批量读取超边 |
| `/nodes/subgraph/batch` | POST | 异步 | 批量子图查询 |
| **检索** | | | |
| `/search/nodes` | POST | 同步 | 搜索节点 |
| `/search/hyperedges` | POST | 同步 | 搜索超边 |
| **批量检索** | | | |
| `/search/nodes/batch` | POST | 异步 | 批量搜索节点 |
| `/search/hyperedges/batch` | POST | 异步 | 批量搜索超边 |
| **Job 管理 (通用)** | | | |
| `/jobs/{job_id}` | GET | 同步 | 查看 job 状态 |
| `/jobs/{job_id}` | DELETE | 同步 | 取消 job |
| `/jobs/{job_id}/result` | GET | 同步 | 获取 job 结果 |

### 2.2 vs v2 变更摘要

| 变更 | 说明 |
|------|------|
| review 重构为异步 pipeline | 不再是单次 LLM 调用，包含 embedding/search/abstraction/verify/BP |
| review API 扩展 | 新增 GET (status), DELETE (cancel), GET /result |
| 所有 API 新增 batch 模式 | batch 请求异步执行，通过 Job API 查询 |
| 通用 Job 管理 API | `/jobs/{job_id}` 统一管理所有异步任务 |
| Gaia 内部集成算子 | embedding, abstraction, verify, bp 不再依赖外部 |
| search 不再要求外部传入 embedding | Gaia 内部生成 embedding |

---

## 3. 写入 API 详细设计

### 3.1 Commit 生命周期

```
                         ┌────────────────────┐
    POST /commits ──────►│  pending_review     │
    (同步，秒回)          └────────┬───────────┘
                                  │
                   POST /commits/{id}/review (异步 job)
                                  │
                         ┌────────▼───────────┐
                         │  reviewing          │ ← 新状态: pipeline 执行中
                         │  (异步 pipeline)     │
                         └────────┬───────────┘
                                  │
                      Pipeline 完成 (自动更新)
                                  │
                    ┌─────────────┼─────────────┐
                    ▼                            ▼
           ┌────────────────┐          ┌────────────────┐
           │  reviewed       │          │  rejected       │
           │  (verdict:pass) │          │  (verdict:fail  │
           └───────┬────────┘          │   或 has_overlap)│
                   │                    └────────────────┘
        POST /commits/{id}/merge
              (同步)
                   │
          ┌────────▼───────────┐
          │     merged          │
          └────────────────────┘
```

### 3.2 POST /commits — 提交变更 (同步)

提交一个或多个操作，系统自动执行轻量检查。

**请求**：

```json
{
  "message": "Add YH10 superconductivity findings from arxiv:2301.xxx",
  "operations": [
    {
      "op": "add_edge",
      "tail": [
        {"title": "DFT 预测 fcc YH10 相稳定", "content": "...", "keywords": [], "extra": {}},
        {"title": "声子谱无虚频", "content": "...", "keywords": [], "extra": {}}
      ],
      "head": [
        {"title": "YH10 高压超导 Tc≈303K", "content": "...", "keywords": [], "extra": {}}
      ],
      "type": "paper-extract",
      "reasoning": [{"title": "DFT+Eliashberg", "content": "基于 DFT 和 Eliashberg 方程的理论预测"}]
    },
    {
      "op": "modify_edge",
      "edge_id": 456,
      "changes": {"status": "retracted", "reason": "原始数据有误"}
    },
    {
      "op": "modify_node",
      "node_id": 789,
      "changes": {"content": "修正后的命题文本"}
    }
  ]
}
```

**支持的操作类型**：

| op | 说明 | 必填字段 |
|----|------|---------|
| `add_edge` | 新增超边（含新/旧命题） | tail, head, type, reasoning |
| `modify_edge` | 修改已有超边 | edge_id, changes |
| `modify_node` | 修改已有节点 | node_id, changes |

**轻量检查（同步，不涉及 LLM）**：

| 检查项 | 说明 |
|--------|------|
| 结构校验 | tail/head 非空、type 合法 |
| 引用校验 | modify 操作引用的 edge_id / node_id 是否存在 |

**响应**：

```json
{
  "commit_id": "abc123",
  "status": "pending_review",
  "check_results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "structural_valid": true
      },
      {
        "index": 1,
        "op": "modify_edge",
        "edge_exists": true
      }
    ]
  }
}
```

### 3.3 POST /commits/{id}/review — 提交 Review Job (异步)

触发异步 review pipeline。返回 job_id，通过 Job API 查询进度。

**请求**：

```json
{
  "depth": "standard"
}
```

| depth | 说明 |
|-------|------|
| `standard` | 完整 pipeline: embedding → NN search → CC/CP abstraction → verify → BP |
| `quick` | 仅 embedding → NN search → 基础去重检测 (跳过 abstraction/verify/BP) |

**响应**：

```json
{
  "job_id": "job_review_abc123",
  "status": "running",
  "pipeline_steps": [
    {"step": "embedding", "status": "pending"},
    {"step": "nn_search", "status": "pending"},
    {"step": "cc_abstraction", "status": "pending"},
    {"step": "cp_abstraction", "status": "pending"},
    {"step": "verify", "status": "pending"},
    {"step": "bp", "status": "pending"}
  ]
}
```

### 3.4 GET /commits/{id}/review — 查看 Review 进度

**响应**：

```json
{
  "job_id": "job_review_abc123",
  "status": "running",
  "progress": {
    "current_step": "cc_abstraction",
    "steps_completed": 2,
    "steps_total": 6
  },
  "pipeline_steps": [
    {"step": "embedding", "status": "completed", "duration_ms": 1200},
    {"step": "nn_search", "status": "completed", "duration_ms": 800},
    {"step": "cc_abstraction", "status": "running"},
    {"step": "cp_abstraction", "status": "running"},
    {"step": "verify", "status": "pending"},
    {"step": "bp", "status": "pending"}
  ]
}
```

### 3.5 DELETE /commits/{id}/review — 取消 Review Job

**响应**：

```json
{
  "job_id": "job_review_abc123",
  "status": "cancelled"
}
```

### 3.6 GET /commits/{id}/review/result — 获取 Review 结果

仅在 review job 完成后可用。

**响应 (通过, 无重合)**：

```json
{
  "job_id": "job_review_abc123",
  "status": "completed",
  "review_results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "verdict": "pass",
        "embedding_generated": true,
        "nn_candidates": [
          {"node_id": 102, "similarity": 0.97, "content": "fcc YH10 的声子谱..."}
        ],
        "quality": {
          "reasoning_valid": true,
          "tightness": 4,
          "substantiveness": 3,
          "novelty": 0.72
        },
        "abstraction_trees": {
          "cc": [
            {
              "source_node": 5002,
              "target_node": 251,
              "relation": "partial_overlap",
              "verified": true,
              "edge_id_created": null
            }
          ],
          "cp": []
        },
        "contradictions_confirmed": [
          {
            "node_id": 269,
            "is_real_contradiction": true,
            "reason": "理论预测 vs 实验结果"
          }
        ],
        "overlaps": []
      }
    ],
    "overall_verdict": "pass",
    "bp_results": {
      "belief_updates": {
        "5002": 0.65,
        "269": 0.71,
        "102": 0.88
      },
      "iterations": 8,
      "converged": true,
      "affected_nodes": 12,
      "explanation": "有一篇实验论文矛盾，head node belief 未达到高置信"
    }
  }
}
```

**响应 (有重合，merge 将拒绝)**：

```json
{
  "review_results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "verdict": "has_overlap",
        "overlaps": [
          {
            "position": "tail[1]",
            "submitted_content": "声子谱无虚频",
            "matched_node_id": 102,
            "matched_content": "fcc YH10 的声子谱计算显示无虚频模",
            "judgment": "semantically_equivalent",
            "similarity": 0.97
          }
        ]
      }
    ],
    "overall_verdict": "has_overlap"
  }
}
```

### 3.7 POST /commits/{id}/merge — 入图 (同步)

将已通过 review 的 commit 应用到图中。

**前置条件**：commit status 必须为 `reviewed` (verdict=pass)。

**请求**：

```json
{
  "force": false
}
```

| 参数 | 说明 |
|------|------|
| `force: false` | 默认：review 必须 pass |
| `force: true` | 跳过 verdict 检查 |

**处理**：

1. 对每条 `add_edge`：创建新节点 → 创建超边 → 写入 LanceDB + Neo4j
2. 对每条 `modify_edge` / `modify_node`：更新对应存储
3. 将 review pipeline 中已计算的 embedding 写入向量索引
4. 将 review pipeline 中 abstraction/verify 产生的新边写入存储
5. 将 review pipeline 中 BP 计算的 belief 值写入 LanceDB

> **注**：belief 计算在 review pipeline 中完成，merge 只负责将结果持久化。belief_updates 在 review result 中返回给调用者。

**响应**：

```json
{
  "commit_id": "abc123",
  "status": "merged",
  "results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "edge_id": 1234,
        "tail_node_ids": [102, 5001],
        "head_node_ids": [5002],
        "nodes_created": [5001, 5002],
        "nodes_reused": [102]
      }
    ],
    "abstraction_edges_created": [1235, 1236],
    "beliefs_persisted": true,
    "index_status": "indexed"
  }
}
```

### 3.8 POST /commits/batch — 批量提交 (异步)

批量提交多个 commit，异步执行 commit → review → merge 全流程。

**请求**：

```json
{
  "commits": [
    {
      "message": "arxiv:2301.12345 - YH10 超导研究",
      "operations": [{"op": "add_edge", "...": "..."}]
    },
    {
      "message": "arxiv:2301.67890 - LaH10 高压实验",
      "operations": [{"op": "add_edge", "...": "..."}]
    }
  ],
  "auto_review": true,
  "auto_merge": true,
  "review_depth": "standard"
}
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `auto_review` | 自动触发 review | `true` |
| `auto_merge` | review 通过后自动 merge | `true` |
| `review_depth` | review 深度 | `"standard"` |

**响应**：

```json
{
  "job_id": "job_batch_001",
  "total_commits": 2,
  "status": "running"
}
```

### 3.9 GET /commits/batch/{batch_id} — 批量进度查询

```json
{
  "job_id": "job_batch_001",
  "status": "running",
  "total_commits": 100,
  "progress": {
    "pending_review": 3,
    "reviewing": 12,
    "reviewed": 0,
    "merged": 82,
    "rejected": 3
  },
  "commits": [
    {"commit_id": "abc123", "message": "arxiv:2301.12345...", "status": "merged"},
    {"commit_id": "abc124", "message": "arxiv:2301.67890...", "status": "rejected"}
  ]
}
```

---

## 4. 精确读取 API 详细设计

### 4.1 GET /nodes/{id} (同步)

```json
{
  "id": 251,
  "type": "paper-extract",
  "subtype": "premise",
  "title": "YH10 高压超导 Tc≈303K",
  "content": "fcc YH10 相在 400GPa 下超导，Tc≈303K",
  "keywords": ["YH10", "超导", "高压氢化物"],
  "prior": 1.0,
  "belief": 0.65,
  "status": "active",
  "metadata": {},
  "extra": {"notations": "T_c \\approx 303\\,K"},
  "created_at": "2026-03-01T..."
}
```

### 4.2 GET /hyperedges/{id} (同步)

```json
{
  "id": 1234,
  "type": "paper-extract",
  "subtype": null,
  "tail": [102, 5001],
  "head": [5002],
  "reasoning": [{"title": "DFT+Eliashberg", "content": "基于 DFT 和 Eliashberg 方程的理论预测"}],
  "probability": null,
  "verified": true,
  "metadata": {},
  "extra": {},
  "created_at": "2026-03-01T..."
}
```

### 4.3 GET /nodes/{id}/subgraph (同步)

**参数**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `hops` | 跳数 | 3 |
| `direction` | `upstream` \| `downstream` \| `both` | `both` |
| `max_nodes` | 最大节点数 | 500 |
| `edge_types` | 过滤超边类型 | 全部 |

**响应**：

```json
{
  "center_node_id": 251,
  "nodes": [
    {"id": 251, "title": "...", "content": "...", "belief": 0.65, "type": "paper-extract"}
  ],
  "edges": [
    {"id": 1234, "type": "paper-extract", "tail": [102, 5001], "head": [251]}
  ]
}
```

### 4.4 批量读取 (异步)

#### POST /nodes/batch

**请求**：

```json
{
  "node_ids": [251, 269, 300, 5001, 5002]
}
```

**响应**：

```json
{
  "job_id": "job_read_nodes_001",
  "status": "running"
}
```

通过 `GET /jobs/{job_id}/result` 获取结果。

#### POST /hyperedges/batch

**请求**：

```json
{
  "edge_ids": [1234, 1235, 1567]
}
```

#### POST /nodes/subgraph/batch

**请求**：

```json
{
  "queries": [
    {"node_id": 251, "hops": 3, "direction": "both"},
    {"node_id": 269, "hops": 2, "direction": "upstream"}
  ]
}
```

---

## 5. 检索 API 详细设计

### 5.1 POST /search/nodes (同步)

**请求**：

```json
{
  "text": "高压下氢化物的超导转变温度",
  "top_k": 20,
  "filters": {
    "status": "active",
    "type": ["paper-extract", "deduction"],
    "min_belief": 0.5,
    "paper_id": "arxiv:2301.12345",
    "min_quality": 3
  }
}
```

> **v3 变化**：不再需要调用者传入 `embedding`，Gaia 内部生成。

**支持的 filters**：

| filter | 类型 | 说明 |
|--------|------|------|
| `status` | string | 节点状态 |
| `type` | string[] | 节点类型 |
| `min_belief` | float | 最低 belief 阈值 |
| `paper_id` | string | 按论文 ID 过滤 |
| `min_quality` | int | 最低质量评分 |
| `edge_type` | string[] | 按关联超边类型过滤 |
| `keywords` | string[] | 关键词过滤 |

**处理**：text → 内部 embedding → 多路召回 (vector + BM25 + topology) → 融合排序。

**响应**：

```json
{
  "results": [
    {
      "node_id": 251,
      "title": "YH10 高压超导 Tc≈303K",
      "content": "fcc YH10 相在 400GPa 下超导，Tc≈303K",
      "similarity": 0.89,
      "belief": 0.65,
      "source": "vector",
      "type": "paper-extract"
    }
  ],
  "total": 20,
  "recall_sources": {"vector": 12, "bm25": 6, "topology": 2}
}
```

### 5.2 POST /search/hyperedges (同步)

**请求**：

```json
{
  "text": "DFT 理论预测氢化物超导温度",
  "top_k": 10,
  "filters": {
    "edge_type": ["paper-extract", "deduction"],
    "min_quality": 3
  }
}
```

**响应**：

```json
{
  "results": [
    {
      "edge_id": 1234,
      "type": "paper-extract",
      "reasoning": [{"title": "DFT+Eliashberg", "content": "..."}],
      "tail_summary": ["DFT 计算", "晶格动力学"],
      "head_summary": ["YH10 Tc≈303K"],
      "similarity": 0.87
    }
  ]
}
```

### 5.3 批量检索 (异步)

#### POST /search/nodes/batch

**请求**：

```json
{
  "queries": [
    {"text": "高压氢化物超导", "top_k": 20},
    {"text": "铜氧化物配对机制", "top_k": 10},
    {"text": "拓扑超导体", "top_k": 15}
  ],
  "filters": {
    "status": "active"
  }
}
```

**响应**：

```json
{
  "job_id": "job_search_batch_001",
  "status": "running"
}
```

#### POST /search/hyperedges/batch

同上模式。

---

## 6. Job 管理 API

所有异步操作（review、batch 操作）共享统一的 Job 管理接口。

### 6.1 GET /jobs/{job_id} — 查看 Job 状态

```json
{
  "job_id": "job_review_abc123",
  "type": "review",
  "status": "running",
  "created_at": "2026-03-03T10:00:00Z",
  "updated_at": "2026-03-03T10:00:05Z",
  "progress": {
    "current_step": "cc_abstraction",
    "steps_completed": 2,
    "steps_total": 6
  }
}
```

**Job 状态**：

| status | 说明 |
|--------|------|
| `pending` | 等待执行 |
| `running` | 执行中 |
| `completed` | 执行完成 |
| `failed` | 执行失败 |
| `cancelled` | 已取消 |

### 6.2 DELETE /jobs/{job_id} — 取消 Job

```json
{
  "job_id": "job_review_abc123",
  "status": "cancelled"
}
```

### 6.3 GET /jobs/{job_id}/result — 获取 Job 结果

仅在 status=completed 时可用。结果格式取决于 job type。

---

## 7. Review Pipeline 算子设计

每个算子为独立模块，可单独测试、替换、组合。

### 7.1 算子列表

| 算子 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `EmbeddingOperator` | node content (text) | embedding vector (float[]) | 调用 embedding model |
| `NNSearchOperator` | embedding vector | list of (node_id, similarity) | 搜索 k 个最近邻 |
| `CCAbstractionOperator` | conclusion nodes + NN candidates | abstraction trees | conclusion↔conclusion 关系发现 |
| `CPAbstractionOperator` | conclusion nodes + NN candidates | abstraction trees | conclusion↔premise 关系发现 |
| `AbstractionTreeVerifyOperator` | abstraction trees | verified trees | 验证 abstraction tree 的有效性 |
| `RefineOperator` | verified trees | refined trees | 精炼 abstraction tree |
| `VerifyAgainOperator` | refined trees | final verified trees | 二次验证 |
| `BPOperator` | affected node ids + graph | belief updates | 局部信念传播 |

### 7.2 算子接口

每个算子实现统一接口：

```python
class Operator(ABC):
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行算子逻辑，读取并更新 context。"""
        ...

    async def cancel(self) -> None:
        """取消正在执行的操作。"""
        ...
```

### 7.3 Pipeline 编排

Pipeline 根据 commit 中的**操作类型**自动选择算子子集：

| 操作类型 | 执行的算子 | 说明 |
|---------|-----------|------|
| `add_edge` | 全部 (①→②→③→④→⑤) | 新节点需要 embedding、abstraction 发现、verify、BP |
| `modify_node` (content 变更) | ① Embedding → ② NN Search → ⑤ BP | 内容变更需重新计算 embedding 和影响评估 |
| `modify_node` (非 content) | ⑤ BP | 仅影响评估 |
| `modify_edge` (retraction) | ⑤ BP | 撤回影响评估，计算下游节点 belief 变化 |
| `modify_edge` (其他) | ⑤ BP | 仅影响评估 |

一个 commit 包含混合操作时，取所有操作所需算子的**并集**。

```python
# add_edge 操作: 完整 pipeline
pipeline_full = Pipeline(steps=[
    EmbeddingOperator(model=embedding_model),
    NNSearchOperator(k=20),
    ParallelStep(
        CCAbstractionOperator(),
        CPAbstractionOperator(),
    ),
    AbstractionTreeVerifyOperator(),
    RefineOperator(),
    VerifyAgainOperator(),
    BPOperator(),
])

# modify 操作: 仅 BP 影响评估
pipeline_modify = Pipeline(steps=[
    BPOperator(),
])
```

---

## 8. 典型使用场景

### 8.1 Research Agent 推导新知识

```
1. POST /search/nodes                    → 了解已有知识 (同步)
   {text: "YH10 高压超导"}

2. (Agent 自己推理，产出新的超边)

3. POST /commits                         → 提交推导结果 (同步，秒回)
   {operations: [{op: "add_edge", type: "deduction", ...}]}
   ← commit_id, status: "pending_review"

4. POST /commits/{id}/review             → 提交 review job (异步)
   {depth: "standard"}
   ← job_id, status: "running"

5. GET /commits/{id}/review              → 轮询 review 进度
   ← pipeline_steps: embedding ✓, nn_search ✓, cc_abstraction running...

6. GET /commits/{id}/review/result       → 获取审核结果
   ├─ verdict: pass              → 继续 merge
   ├─ verdict: has_overlap       → 修改后重新提交新 commit
   └─ verdict: rejected          → 推理链不合格

7. POST /commits/{id}/merge              → 入图 (同步)
   ← abstraction_edges_created, beliefs_persisted, index_status
   (belief_updates 已在 step 6 review result 中返回)
```

### 8.2 批量论文注入 (Paper Ingest Agent)

```
1. 外部系统将论文解析为超边

2. POST /commits/batch                   → 批量提交 (异步)
   {commits: [
     {message: "arxiv:2301.12345", operations: [...]},
     {message: "arxiv:2301.67890", operations: [...]},
     ...100 篇论文
   ], auto_review: true, auto_merge: true}
   ← job_id: "job_batch_001"

3. GET /commits/batch/{batch_id}         → 轮询进度
   ← 82 merged, 15 reviewing, 3 rejected

4. 对 rejected 的 commit:
   修改后 POST /commits → review → merge (逐条处理)
```

### 8.3 撤回已有知识

```
1. POST /commits                         → 提交撤回操作 (同步)
   {operations: [{
     op: "modify_edge",
     edge_id: 456,
     changes: {status: "retracted", reason: "论文撤稿"}
   }]}

2. POST /commits/{id}/review             → review (异步)
   ← pipeline 评估影响范围，受影响节点 BP 重算

3. GET /commits/{id}/review/result       → 查看影响分析
   ← affected_downstream_nodes: 12, belief_updates preview

4. POST /commits/{id}/merge              → 入图 (同步)
   ← review 中计算的 BP 结果持久化，受影响节点 belief 降低
```

### 8.4 批量撤回某篇论文的所有命题

```
1. POST /search/nodes                    → 按论文查询所有节点 (同步)
   {filters: {paper_id: "arxiv:retracted-paper"}}
   ← 返回该论文的所有节点

2. POST /search/hyperedges               → 查找关联超边 (同步)
   {filters: {edge_type: ["paper-extract"]}}

3. POST /commits                         → 批量撤回 (同步)
   {operations: [
     {op: "modify_edge", edge_id: 101, changes: {status: "retracted"}},
     {op: "modify_edge", edge_id: 102, changes: {status: "retracted"}},
     ...
   ]}

4. POST /commits/{id}/review → merge     → 异步 review + 同步 merge
```

### 8.5 文献综述 (Human Researcher)

```
1. POST /search/nodes                    → 搜索相关命题 (同步)
   {text: "铜氧化物高温超导机理", top_k: 50}

2. POST /search/hyperedges               → 搜索推理链 (同步)
   {text: "超导配对机制的理论解释", top_k: 20}

3. GET /nodes/{id}/subgraph              → 探索某个命题的上下游 (同步)
   ?hops=3&direction=both

4. (如果需要批量探索多个命题)
   POST /nodes/subgraph/batch            → 批量子图查询 (异步)
   {queries: [
     {node_id: 251, hops: 3},
     {node_id: 300, hops: 3},
     ...
   ]}
   ← job_id → GET /jobs/{job_id}/result
```

### 8.6 检查"我的想法新不新"

```
1. POST /search/nodes                    → 搜索相似命题 (同步)
   {text: "我的新想法...", top_k: 5}
   ← top-1 similarity < 0.5 → 很新颖
   ← top-1 similarity > 0.9 → 已有人提出

2. (可选) 提交到知识图谱验证
   POST /commits → review
   ← review result 中的 novelty 评分给出量化新颖度
```

---

## 9. 用户角色与 API 覆盖矩阵

### 9.1 角色定义 (继承 v2)

| 角色 | 谁 | 与 LKM 的关系 |
|------|-----|---------------|
| **Research Agent** | 自动化 AI Agent | 检索知识 → 推理 → 提交新发现 |
| **Paper Ingest Agent** | 自动化 Agent | 批量注入论文到知识图谱 |
| **Human Researcher** | 人类科学家 | 查询、浏览、验证假设、写综述 |
| **Reviewer** | 人类/AI 审稿人 | 评估论文/命题的质量 |
| **Knowledge Curator** | 人类/AI 维护者 | 纠错、撤回、标注 |
| **System Admin** | 运维人员 | 监控、Job 管理 |

### 9.2 覆盖矩阵

| 操作 | 角色 | API | 状态 |
|------|------|-----|------|
| 搜索已有知识 | Agent, Researcher | `POST /search/nodes` | ✅ |
| 批量搜索 | Agent | `POST /search/nodes/batch` | ✅ 新增 |
| 搜索超边 | Agent, Researcher | `POST /search/hyperedges` | ✅ |
| 查看节点详情 | 所有 | `GET /nodes/{id}` | ✅ |
| 批量读取节点 | Agent | `POST /nodes/batch` | ✅ 新增 |
| 查看超边详情 | 所有 | `GET /hyperedges/{id}` | ✅ |
| 查看节点邻居 | 所有 | `GET /nodes/{id}/subgraph` | ✅ |
| 提交新超边 | Agent | `POST /commits` | ✅ |
| 异步 review | Agent | `POST /commits/{id}/review` | ✅ 重构 |
| 查看 review 进度 | Agent | `GET /commits/{id}/review` | ✅ 新增 |
| 取消 review | Agent | `DELETE /commits/{id}/review` | ✅ 新增 |
| 入图 | Agent | `POST /commits/{id}/merge` | ✅ |
| 批量提交 | Ingest Agent | `POST /commits/batch` | ✅ |
| 撤回知识 | Curator | `POST /commits` (modify_edge) | ✅ |
| 管理 Job | Admin | `GET/DELETE /jobs/{job_id}` | ✅ 新增 |
| 新颖度评估 | Researcher | Layer 2 API | ⏳ 待设计 |
| 可信度 + 证据链 | Researcher | Layer 2 API | ⏳ 待设计 |
| 矛盾分析 | Researcher | Layer 2 API | ⏳ 待设计 |

---

## 10. Layer 2 Research API 需求清单 (继承 v2)

| 端点 | 功能 | 内部编排 |
|------|------|---------|
| `POST /research/novelty` | 新颖度评分 | 多路召回 + BP + score 聚合 |
| `POST /research/reliability` | 可信度评分 | 子图提取 + BP + 证据分类 |
| `POST /research/contradictions` | 矛盾列表 | 子图过滤 + BP |
| `GET /research/provenance/{id}` | 论文溯源树 | 递归上游追溯 |
| `POST /research/overview` | 领域知识结构 | 多路召回 + 聚类 + 子图合并 |
| `POST /research/compare` | 证据强度比较 | 双方子图 + BP + LLM |
| `POST /review/paper` | 论文审阅报告 | 命题遍历 + novelty + reliability |

---

## 附录 A：vs v2 变更总结

| 项目 | v2 | v3 |
|------|-----|-----|
| review | 单次 LLM 调用 (同步) | 多步 pipeline (异步 job) |
| review 内容 | LLM 审核推理链 + 重合检测 | embedding → NN search → CC/CP abstraction → verify → BP |
| embedding | 调用者外部提供 | Gaia 内部生成 |
| abstraction/verify | 不在 Gaia 内 | Gaia 内部算子 |
| BP 触发 | merge 时同步 | review pipeline 内完成，belief_updates 作为 review result 返回，merge 仅持久化 |
| batch API | 仅 /commits/batch | 所有 API 都支持 batch |
| batch 模式 | 异步 | 异步，统一 Job 管理 |
| Job 管理 | 无 | 通用 /jobs API |
| commit 轻量检查 | 去重 + 矛盾候选 + 引用校验 | 结构校验 + 引用校验 (去重移入 review pipeline) |
| search 输入 | text + embedding | 仅 text (内部生成 embedding) |
