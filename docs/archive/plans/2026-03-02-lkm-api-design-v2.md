# LKM API 设计 v2.2

> **Status:** SUPERSEDED by `2026-03-03-lkm-api-design-v3.md`

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.4 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/plans/2026-03-02-lkm-api-design.md` (v1, 已被本文档取代) |
| 相关文档 | `docs/plans/2026-03-02-phase1-module-architecture-design.md` |
| 变更记录 | v2.0: 初始设计; v2.1: 移除 resolve 步骤和 merge_propositions 操作，统一命名 (/nodes, /hyperedges, /search/nodes, /search/hyperedges)，存储层更新为 Neo4j+LanceDB+ByteHouse; v2.2: Node 模型更新——新增 title/metadata，text→content，confidence→prior; v2.3: HyperEdge.reasoning 改为 list = []; v2.4: Node 移除 notations/assumptions (改用 extra)，content 类型改为 str\|dict\|list，type 改为 str；Node/HyperEdge 新增 extra: dict |

---

## 1. 设计原则

### 1.1 超边是原子单元

LKM 是知识库（Large Knowledge Model），不是推理引擎。所有知识以**超边**（hyperedge）的形式存在：

```
超边 = {tail: [前提命题...], head: [结论命题...], type, reasoning}
```

- 命题不独立存在，命题永远是超边的一部分
- 论文提取：`[论文上下文] ──paper-extract──→ [命题]`
- Agent 推导：`[已有命题A, B] ──induction/deduction──→ [新命题C]`
- 没有思维链的命题不允许进入图

### 1.2 超边类型

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

### 1.3 Git-like 写入模型

写入操作统一为 commit → review → merge 三步：

```
Git                    LKM
────                   ────
git push + create PR   POST /commits          提交变更（新增或修改）
CI (lint, typecheck)   → 自动轻量检查          去重、结构校验、召回候选
request review         POST /commits/{id}/review  LLM 深度审核
code review            → LLM 验证推理链         质量评估、逻辑一致性、重合检测
merge PR               POST /commits/{id}/merge   入图 + BP 更新
```

**重合处理**：当 review 检测到提交的命题与已有命题语义等价时，merge 拒绝入图，要求提交者修改后重新提交。

### 1.4 推理由外部 Agent 负责

LKM 的职责边界：

```
LKM（知识库）                      External Agent（研究代理）
┌─────────────────────┐           ┌─────────────────────┐
│ 存储                 │           │ 推理                 │
│ 检索                 │  ◄─ API ─►│ 推导新命题 (induction) │
│ 评估（质检/矛盾检测） │           │ 提出猜想             │
│ 维护（去重/合并/BP）  │           │ 设计实验             │
└─────────────────────┘           └─────────────────────┘
```

### 1.5 两层 API 架构

```
┌──────────────────────────────────────────────────────┐
│  Layer 2: Research API  (上层 — 面向研究问题)           │
│  novelty / reliability / contradiction / provenance   │
│  面向人类研究者和审稿人                                 │
│  内部编排: 多路召回 + 子图提取 + BP + LLM              │
│  （本文档记录需求，详细设计待后续文档）                    │
├──────────────────────────────────────────────────────┤
│  Layer 1: Knowledge Graph API  (底层 — 面向图操作)      │
│  commits / nodes / edges / search                     │
│  面向 Research Agent 和 Knowledge Curator              │
│  （本文档详细设计的主体）                                │
└──────────────────────────────────────────────────────┘
                        │
                   共享存储层
           LanceDB + Neo4j + ByteHouse
```

**本文档聚焦 Layer 1 的完整设计。Layer 2 的需求清单见第 8 节。**

---

## 2. API 总览

### 2.1 完整 API 列表

| API | 方法 | 功能 | 成本 |
|-----|------|------|------|
| **写入（commit → review → merge）** | | | |
| `/commits` | POST | 提交变更 + 轻量检查 | 低 |
| `/commits/{id}` | GET | 查看 commit 状态和 review 结果 | 低 |
| `/commits/{id}/review` | POST | LLM 深度审核（含重合检测） | 高 |
| `/commits/{id}/merge` | POST | 入图 + 触发 BP 更新 | 中 |
| `/commits/batch` | POST | 批量提交多个 commit | 中 |
| **精确读取** | | | |
| `/nodes/{id}` | GET | 读取节点详情 | 低 |
| `/hyperedges/{id}` | GET | 读取超边详情 | 低 |
| `/nodes/{id}/subgraph` | GET | 读取节点的邻居子图 | 低 |
| **检索** | | | |
| `/search/nodes` | POST | 找相似节点（支持多种 filter） | 低 |
| `/search/hyperedges` | POST | 找相似超边 | 低 |

### 2.2 vs v1 API 变更摘要

| 变更 | 说明 | 来源 |
|------|------|------|
| 新增 `POST /commits/batch` | 批量提交多个 commit | 思想实验：Paper Ingest Agent |
| search API filters 扩展 | 新增过滤条件 | 思想实验：Reviewer |
| merge 响应新增 `index_status` | 告知索引更新状态 | 思想实验：Research Agent |
| 统一命名 | `/propositions` → `/nodes`，`/edges` → `/hyperedges`，`/search/reasoning` → `/search/hyperedges` | 命名规范统一 |
| 简化写入流程 | 移除 resolve 步骤，merge 遇到重合直接拒绝 | 简化设计 |
| 移除 `merge_propositions` | 不再需要命题合并操作 | 简化设计 |

---

## 3. 写入 API 详细设计

### 3.1 Commit 生命周期

```
                         ┌────────────────────┐
    POST /commits ──────►│  pending_review     │
                         └────────┬───────────┘
                                  │
                   POST /commits/{id}/review
                                  │
                         ┌────────▼───────────┐
                    ┌────│  reviewed           │────┐
                    │    └────────────────────┘    │
                    │                              │
          verdict:  │                    verdict:  │
            pass    │                   has_overlap │
                    │                              │
                    │                     ┌────────▼──────┐
                    │                     │   rejected     │
                    │                     │  (需修改后重新  │
                    │                     │   提交新commit) │
                    │                     └───────────────┘
                    │
             POST /commits/{id}/merge
                    │
           ┌────────▼───────────┐
           │     merged          │
           └────────────────────┘
```

### 3.2 POST /commits — 提交变更

提交一个或多个操作，系统自动执行轻量检查。

**请求**：

```json
{
  "message": "Add YH10 superconductivity findings from arxiv:2301.xxx",
  "operations": [
    {
      "op": "add_edge",
      "tail": [
        {"title": "DFT 预测 fcc YH10 相稳定", "content": "DFT 计算预测 fcc YH10 相稳定", "keywords": "...", "extra": {}},
        {"title": "声子谱无虚频", "content": "声子谱无虚频", "keywords": "...", "extra": {}}
      ],
      "head": [
        {"title": "YH10 高压超导 Tc≈303K", "content": "YH10 在 400GPa 下 Tc≈303K", "keywords": "...", "extra": {"notations": "T_c \\approx 303\\,K"}}
      ],
      "type": "paper-extract",
      "reasoning": ["基于 DFT 和 Eliashberg 方程的理论预测"],
      "source": {"paper_id": "arxiv:2301.12345", "section": "3.2"}
    },
    {
      "op": "modify_edge",
      "edge_id": 456,
      "changes": {
        "status": "retracted",
        "reason": "原始数据有误"
      }
    },
    {
      "op": "modify_node",
      "node_id": 789,
      "changes": {
        "content": "修正后的命题文本",
        "extra": {"notations": "修正后的符号"}
      }
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

**轻量检查（自动执行，不涉及 LLM）**：

| 检查项 | 说明 |
|--------|------|
| 结构校验 | tail/head 非空（contradiction 除外）、type 合法 |
| 命题去重 | 多路召回检查每个命题是否已有等价（embedding + BM25 + 图拓扑） |
| 候选矛盾 | 召回与新命题高度相似但可能矛盾的已有命题 |
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
        "structural_valid": true,
        "dedup": {
          "tail": [
            {"content": "DFT 计算预测...", "matched_node_id": null, "is_new": true},
            {"content": "声子谱无虚频", "matched_node_id": 102, "is_new": false, "similarity": 0.97}
          ],
          "head": [
            {"content": "YH10 在 400GPa...", "matched_node_id": null, "is_new": true}
          ]
        },
        "candidate_contradictions": [
          {"node_id": 269, "content": "YH10 在实验中未能合成", "similarity": 0.82}
        ]
      },
      {
        "index": 1,
        "op": "modify_edge",
        "edge_exists": true,
        "current_status": "active",
        "impact_preview": {"affected_downstream_nodes": 12}
      },
    ]
  }
}
```

### 3.3 POST /commits/{id}/review — LLM 深度审核

触发 LLM 对 commit 中的变更进行深度审核，**包括重合检测**。

**请求**：

```json
{
  "depth": "standard"
}
```

| depth | 说明 | 成本 |
|-------|------|------|
| `standard` | 验证推理链逻辑、评估质量、检测重合 | 1-2 次 LLM 调用/操作 |
| `thorough` | + 交叉验证、检查前提可靠性、评估新颖度 | 3-5 次 LLM 调用/操作 |

**LLM 审核内容（每条 add_edge 操作）**：

| 审核项 | 说明 |
|--------|------|
| 推理有效性 | 前提是否真的能推出结论？ |
| 逻辑一致性 | 与已有知识是否一致？候选矛盾是否为真矛盾？ |
| 质量评分 | tightness (1-5), substantiveness (1-5) |
| 新颖度 | 结论相对于已有知识有多新 |
| **重合检测** | 轻量检查中的候选去重，LLM 判断是否真正语义等价 |

**响应（通过 GET /commits/{id} 查询）**：

当所有操作通过、无重合：

```json
{
  "commit_id": "abc123",
  "status": "reviewed",
  "review_results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "verdict": "pass",
        "quality": {
          "reasoning_valid": true,
          "tightness": 4,
          "substantiveness": 3,
          "novelty": 0.72
        },
        "contradictions_confirmed": [
          {
            "node_id": 269,
            "is_real_contradiction": true,
            "reason": "理论预测 vs 实验结果，论文 269 报告 YH10 未能在 410GPa 下合成"
          }
        ],
        "overlaps": [],
        "belief_preview": {
          "head_nodes_belief": 0.65,
          "explanation": "有一篇实验论文矛盾，belief 未达到高置信"
        }
      }
    ],
    "overall_verdict": "pass"
  }
}
```

当检测到重合（merge 将拒绝，需修改后重新提交）：

```json
{
  "commit_id": "abc123",
  "status": "reviewed",
  "review_results": {
    "operations": [
      {
        "index": 0,
        "op": "add_edge",
        "verdict": "has_overlap",
        "quality": {
          "reasoning_valid": true,
          "tightness": 4,
          "substantiveness": 3,
          "novelty": 0.72
        },
        "overlaps": [
          {
            "position": "tail[1]",
            "submitted_content": "声子谱无虚频",
            "matched_node_id": 102,
            "matched_content": "fcc YH10 的声子谱计算显示无虚频模",
            "llm_judgment": "semantically_equivalent",
            "prior": 0.95
          },
          {
            "position": "head[0]",
            "submitted_content": "YH10 在 400GPa 下 Tc≈303K",
            "matched_node_id": 5010,
            "matched_content": "YH10 超导临界温度约 303K (400GPa)",
            "llm_judgment": "semantically_equivalent",
            "prior": 0.91
          }
        ],
        "belief_preview": {
          "head_nodes_belief": 0.65,
          "explanation": "有一篇实验论文矛盾，belief 未达到高置信"
        }
      }
    ],
    "overall_verdict": "has_overlap"
  }
}
```

### 3.4 POST /commits/{id}/merge — 入图

将已通过 review 的 commit 应用到图中。

**前置条件**：commit status 必须为 `reviewed`（verdict=pass，无未解决的重合）。如果存在重合（verdict=has_overlap），merge 拒绝执行，提交者需修改后重新提交新 commit。

**请求**：

```json
{
  "force": false
}
```

| 参数 | 说明 |
|------|------|
| `force: false` | 默认：review 必须 pass（无重合） |
| `force: true` | 跳过 verdict 检查（例如：矛盾本身也是有价值的知识） |

**处理**：

1. 对每条 add_edge：创建新节点、创建超边、更新邻接索引
2. 对每条 modify_edge / modify_node：更新节点/边的状态
3. 触发局部 BP 更新（受影响节点重新计算 belief）
4. 异步更新向量索引和 BM25 索引

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
      },
      {
        "index": 1,
        "op": "modify_edge",
        "edge_id": 456,
        "previous_status": "active",
        "new_status": "retracted"
      }
    ],
    "belief_updates": {
      "5002": 0.65,
      "269": 0.71,
      "102": 0.88
    },
    "bp_iterations": 8,
    "bp_converged": true,
    "index_status": "pending"
  }
}
```

**`index_status`**：

| 值 | 说明 |
|----|------|
| `pending` | 索引更新已提交，尚未完成。精确读取（GET by ID）立即可用，搜索可能暂时找不到新命题 |
| `indexed` | 索引已更新，搜索可发现新命题 |

精确读取（GET /nodes/{id}）保证强一致——merge 后立即可读。搜索为最终一致，通常秒级完成。

### 3.5 GET /commits/{id} — 查看状态

```json
{
  "commit_id": "abc123",
  "status": "pending_review | reviewed | merged | rejected",
  "message": "Add YH10 superconductivity findings...",
  "created_at": "2026-03-02T10:30:00Z",
  "check_results": { "..." },
  "review_results": { "..." },
  "merge_results": { "..." }
}
```

### 3.6 POST /commits/batch — 批量提交

批量提交多个 commit，异步处理。

**请求**：

```json
{
  "commits": [
    {
      "message": "arxiv:2301.12345 - YH10 超导研究",
      "operations": [
        {"op": "add_edge", "type": "paper-extract", "...": "..."},
        {"op": "add_edge", "type": "paper-extract", "...": "..."}
      ]
    },
    {
      "message": "arxiv:2301.67890 - LaH10 高压实验",
      "operations": [
        {"op": "add_edge", "type": "paper-extract", "...": "..."}
      ]
    }
  ],
  "auto_review": true,
  "review_depth": "standard"
}
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `auto_review` | 是否自动触发 review | `true` |
| `review_depth` | review 深度 | `"standard"` |

**说明**：

- batch 内部有自己的批量优化实现，不一定分解为逐条单 commit 调用
- 批量优化包括：跨 commit 去重、批量 LLM review、单次 BP 触发、单次索引重建
- 每个 commit 独立追踪状态（pass / merged / rejected）

**响应**：

```json
{
  "batch_id": "batch_001",
  "total_commits": 2,
  "status": "processing",
  "poll_url": "/commits/batch/batch_001"
}
```

### 3.7 GET /commits/batch/{batch_id} — 批量进度查询

```json
{
  "batch_id": "batch_001",
  "status": "processing | completed | partial",
  "total_commits": 100,
  "progress": {
    "pending_review": 3,
    "reviewed": 0,
    "merged": 82,
    "rejected": 15
  },
  "commits": [
    {"commit_id": "abc123", "message": "arxiv:2301.12345...", "status": "merged"},
    {"commit_id": "abc124", "message": "arxiv:2301.67890...", "status": "rejected"},
    "..."
  ]
}
```

---

## 4. 精确读取 API 详细设计

### 4.1 GET /nodes/{id}

```json
{
  "id": 251,
  "title": "YH10 高压超导 Tc≈303K",
  "content": "fcc YH10 相在 400GPa 下超导，Tc≈303K",
  "keywords": ["YH10", "超导", "高压氢化物"],
  "type": "paper-extract",
  "status": "active",
  "belief": 0.65,
  "metadata": {},
  "extra": {"notations": "T_c \\approx 303\\,K"},
  "created_at": "2026-03-01T..."
}
```

### 4.2 GET /hyperedges/{id}

```json
{
  "id": 1234,
  "type": "paper-extract",
  "subtype": null,
  "tail": [102, 5001],
  "head": [5002],
  "reasoning": ["基于 DFT 和 Eliashberg 方程的理论预测"],
  "probability": null,
  "verified": true,
  "quality": {
    "tightness": 4,
    "substantiveness": 3
  },
  "source": {"paper_id": "arxiv:2301.12345", "section": "3.2"},
  "status": "active",
  "created_at": "2026-03-01T...",
  "commit_id": "abc123"
}
```

### 4.3 GET /nodes/{id}/subgraph

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
    {"id": 251, "title": "...", "content": "...", "belief": 0.65, "type": "paper-extract"},
    {"id": 269, "title": "...", "content": "...", "belief": 0.71, "type": "paper-extract"}
  ],
  "edges": [
    {"id": 1234, "type": "paper-extract", "tail": [102, 5001], "head": [251]},
    {"id": 1567, "type": "contradiction", "tail": [251, 269], "head": []}
  ]
}
```

---

## 5. 检索 API 详细设计

### 5.1 POST /search/nodes — 找相似节点

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

**支持的 filters**：

| filter | 类型 | 说明 |
|--------|------|------|
| `status` | string | 节点状态：`active` / `deleted` |
| `type` | string[] | 节点来源类型 |
| `min_belief` | float | 最低 belief 阈值 |
| `paper_id` | string | 按论文 ID 过滤（查看某篇论文的所有命题） |
| `min_quality` | int | 最低质量评分（tightness） |
| `edge_type` | string[] | 按关联超边类型过滤 |

**处理**：多路召回（ByteHouse/LanceDB 向量搜索 + BM25 + 图拓扑），合并去重，按相关度排序。

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
      "source": "ann",
      "type": "paper-extract"
    },
    {
      "node_id": 300,
      "title": "LaH10 高压超导 Tc≈250K",
      "content": "LaH10 在 170GPa 下 Tc≈250K",
      "similarity": 0.84,
      "belief": 0.92,
      "source": "bm25",
      "type": "paper-extract"
    }
  ],
  "total": 20,
  "recall_sources": {"ann": 12, "bm25": 6, "topo": 2}
}
```

### 5.2 POST /search/hyperedges — 找相似超边

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

**处理**：对超边的 reasoning 文本做多路召回，也可以基于 tail/head 命题的 embedding 做联合检索。

**响应**：

```json
{
  "results": [
    {
      "edge_id": 1234,
      "type": "paper-extract",
      "reasoning": ["基于 DFT 和 Eliashberg 方程的理论预测"],
      "tail_summary": ["DFT 计算", "晶格动力学"],
      "head_summary": ["YH10 Tc≈303K"],
      "similarity": 0.87,
      "quality": {"tightness": 4, "substantiveness": 3},
      "source_paper": "arxiv:2301.12345"
    }
  ]
}
```

> **注**：`/search/subgraph`（子图模式搜索）已推迟到 Layer 2 Research API，不在 Layer 1 中提供。

---

## 6. 典型使用场景

### 6.1 Research Agent 推导新知识

```
1. POST /search/nodes               → 了解已有知识
   {text: "YH10 高压超导"}

2. (Agent 自己推理)

3. POST /commits                    → 提交推导结果
   {operations: [{op: "add_edge", type: "deduction", ...}]}
   ← 秒回：轻量检查结果（候选去重、候选矛盾）

4. POST /commits/{id}/review        → LLM 深度审核
   ← 审核推理链质量 + 重合检测

5. GET /commits/{id}                → 查看审核结果
   ├─ 如果 verdict: pass            → 直接 merge
   └─ 如果 verdict: has_overlap     → 修改后重新提交新 commit

6. POST /commits/{id}/merge         → 入图
   ← belief_updates, index_status: "pending"
   精确读取立即可用；搜索最终一致
```

### 6.2 批量论文注入

```
1. 外部系统将论文解析为超边

2. POST /commits/batch               → 批量提交
   {commits: [
     {message: "arxiv:2301.12345", operations: [...]},
     {message: "arxiv:2301.67890", operations: [...]},
     ...
   ], auto_review: true}
   ← batch_id

3. GET /commits/batch/{batch_id}      → 轮询进度
   ← 82 merged, 15 rejected, 3 reviewing

4. 对 rejected 的 commit（有重合）：
   修改后重新 POST /commits           → 提交修正后的新 commit
   POST /commits/{id}/review → merge
```

### 6.3 撤回已有知识

```
1. POST /commits
   {operations: [{
     op: "modify_edge",
     edge_id: 456,
     changes: {status: "retracted", reason: "论文撤稿"}
   }]}

2. POST /commits/{id}/review
   ← 影响分析：12 个下游节点受影响

3. POST /commits/{id}/merge
   ← BP 重新计算，受影响节点 belief 降低
```

### 6.4 批量撤回某篇论文的所有命题

```
1. POST /search/nodes                 → 按论文查询所有节点
   {filters: {paper_id: "arxiv:retracted-paper"}}
   ← 返回该论文的所有节点及其关联超边

2. POST /commits                      → 批量撤回
   {operations: [
     {op: "modify_edge", edge_id: 101, changes: {status: "retracted", reason: "论文撤稿"}},
     {op: "modify_edge", edge_id: 102, changes: {status: "retracted", reason: "论文撤稿"}},
     ...
   ]}

3. POST /commits/{id}/review → merge
```

### 6.5 文献综述

```
1. POST /search/nodes
   {text: "铜氧化物高温超导机理"}

2. POST /search/hyperedges
   {text: "超导配对机制的理论解释"}

3. 对感兴趣的节点：
   GET /nodes/{id}/subgraph?hops=3
   → 来源追溯与影响分析
```

### 6.6 检查"我的想法新不新"

```
1. POST /search/nodes
   {text: "我的新想法..."}
   ← 如果 top-1 similarity < 0.5 → 很新颖
   ← 如果 top-1 similarity > 0.9 → 已有人提出
```

---

## 7. 用户角色与 API 覆盖矩阵

本章记录思想实验的验证结果：每个角色的典型操作是否被 API 覆盖。

### 7.1 角色定义

| 角色 | 谁 | 与 LKM 的关系 |
|------|-----|---------------|
| **Research Agent** | 自动化 AI Agent | 检索知识 → 推理 → 提交新发现 |
| **Paper Ingest Agent** | 自动化 Agent | 批量注入论文到知识图谱 |
| **Human Researcher** | 人类科学家 | 查询、浏览、验证假设、写综述 |
| **Reviewer** | 人类/AI 审稿人 | 评估论文/命题的质量、新颖性、一致性 |
| **Knowledge Curator** | 人类/AI 维护者 | 纠错、合并重复、撤回、标注 |
| **System Admin** | 运维人员 | 监控、索引重建、Pipeline 状态 |

### 7.2 覆盖矩阵

| 操作 | 角色 | Layer 1 API | 状态 |
|------|------|-------------|------|
| 搜索已有知识 | Agent, Researcher | `/search/nodes` | ✅ |
| 搜索超边 | Agent, Researcher | `/search/hyperedges` | ✅ |
| 查看节点详情 | 所有 | `/nodes/{id}` | ✅ |
| 查看超边详情 | 所有 | `/hyperedges/{id}` | ✅ |
| 查看节点邻居 | 所有 | `/nodes/{id}/subgraph` | ✅ |
| 提交新超边 | Agent | `/commits` | ✅ |
| 批量提交 | Ingest Agent | `/commits/batch` | ✅ |
| 撤回知识 | Curator | `/commits` (modify_edge) | ✅ |
| 按属性查超边 | Curator | `/search/hyperedges` + filters | ✅ |
| 新颖度评估 | Researcher, Reviewer | 需 Layer 2 API | ⏳ 待设计 |
| 可信度 + 证据链 | Researcher, Reviewer | 需 Layer 2 API | ⏳ 待设计 |
| 矛盾分析 | Researcher, Reviewer | 需 Layer 2 API | ⏳ 待设计 |
| 命题溯源 | Researcher | 需 Layer 2 API | ⏳ 待设计 |
| 论文审阅报告 | Reviewer | 需 Layer 2 API | ⏳ 待设计 |
| 领域知识概览 | Researcher | 需 Layer 2 API | ⏳ 待设计 |
| 系统监控 | Admin | 需运维 API | ⏳ 待设计 |
| 索引管理 | Admin | 需运维 API | ⏳ 待设计 |

---

## 8. Layer 2 Research API 需求清单

以下端点在 gateway 设计文档中已有雏形，但尚未完成详细 API 设计。记录需求，待后续文档展开。

| 端点 | 功能 | 内部编排 |
|------|------|---------|
| `POST /research/novelty` | 输入命题文本，返回新颖度评分 + 相似命题 + 证据 | 多路召回 + BP + score 聚合 |
| `POST /research/reliability` | 输入命题 ID，返回可信度评分 + 证据分解 | 子图提取 + BP + 证据分类 |
| `POST /research/contradictions` | 输入命题 ID，返回矛盾列表 + 双方证据对比 | 子图过滤 + BP |
| `GET /research/provenance/{id}` | 输入命题 ID，返回论文溯源树 | 递归上游追溯 |
| `POST /research/overview` | 输入主题文本，返回领域知识结构 | 多路召回 + 聚类 + 子图合并 |
| `POST /research/compare` | 输入两个命题 ID，比较证据强度 | 双方子图 + BP + LLM 分析 |
| `POST /review/paper` | 输入论文 ID，流式返回审阅报告 | 命题遍历 + novelty + reliability + LLM 生成 |

---

## 附录 A：思想实验记录

本 API 设计基于对 6 个用户角色的系统性思想实验，逐步验证 v1 API 是否满足各角色的实际使用场景。以下记录实验中发现的关键问题及其解决方式。

### A.1 Research Agent

**场景**：Agent 探索"高压氢化物超导"领域，推导新知识。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 去重交互缺失 | commit 轻量检查发现相似命题，但 Agent 无法表达"复用已有" | review 阶段 LLM 判断真实重合 → merge 拒绝，要求修改后重新提交 |
| 写入后搜索一致性 | merge 后搜索可能找不到新命题 | 接受最终一致 + index_status 字段 + 精确读取保证强一致 |
| 缺少 novelty 端点 | Agent 需要自己判断新颖度阈值 | 归入 Layer 2 Research API |

### A.2 Paper Ingest Agent

**场景**：批量注入 100 篇论文。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 无批量 API | 需串行调用 100 次 /commits | 新增 /commits/batch |
| batch 与单条的关系 | batch 内部不一定要分解为逐条 commit 调用 | batch 有自己的批量优化实现，外部语义一致 |

### A.3 Human Researcher

**场景**：研究者用 LKM 辅助超导研究。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 搜索结果缺乏结构 | 返回扁平列表，无法看到知识全景 | 归入 Layer 2 (overview) |
| belief 缺乏可解释性 | 0.78 是什么意思？缺少证据分解 | 归入 Layer 2 (reliability) |
| 缺少命题溯源 | 无法直接查"来自哪篇论文" | 归入 Layer 2 (provenance) |
| 缺少矛盾对比 | 需多步操作才能对比两个矛盾观点 | 归入 Layer 2 (contradictions, compare) |

### A.4 Reviewer

**场景**：审稿人评估论文质量。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 无法按论文查命题 | 不知道论文产出了哪些命题 | search API 增加 paper_id filter |
| 论文级评估需要编排 | 需逐个命题检查新颖度、矛盾 | 归入 Layer 2 (review/paper) |

### A.5 Knowledge Curator

**场景**：维护图谱质量。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 重复命题处理 | 发现重复命题后如何处理 | 通过 modify_node 标记删除或通过 add_edge 引用已有节点 |
| 无法按属性查超边 | 找低质量边需要过滤查询 | search API filters 扩展 |
| 缺少图谱统计 | 无法查看总量、健康度 | 后续加 GET /stats |

### A.6 System Admin

**场景**：监控和维护系统。

| 发现 | 问题 | 解决方式 |
|------|------|---------|
| 运维 API 缺失 | Pipeline 进度、索引重建、BP 状态均无 API | 运维 API 待后续设计，非本文档范围 |
