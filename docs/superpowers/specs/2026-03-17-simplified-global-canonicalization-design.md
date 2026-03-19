# Simplified Global Canonicalization Design

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-17 |
| 状态 | Draft |
| 关联文档 | [../../foundations/graph-ir.md](../../foundations/graph-ir.md) §4.3-4.5, §7.4, [2026-03-17-curation-service-design.md](2026-03-17-curation-service-design.md) |

---

## 1. 动机

Graph IR §7.4 定义了完整的 global canonicalization 流程（6 步，含 rebuttal cycle 和 probability judgments）。完整 review engine 暂不实现。

但 publish 时必须做 global canonicalization——否则新 package 的节点在全局图里是孤立的，跨 package 的 factor 连不上，global BP 无法运行。

本设计是 graph-ir.md §7.4 的**最小子集**：只做 identity assignment（local node → global node 映射），跳过 rebuttal cycle、probability judgments、non-identity findings。Curation service 后续负责修正错误的自动匹配。

## 2. 简化版 vs 完整版

| 步骤 | 完整版 (graph-ir.md §7.4) | 简化版 |
|------|--------------------------|--------|
| 1. Embed each LocalCanonicalNode | ✓ | ✓ |
| 2. Search global graph for matches | ✓ | ✓ |
| 3. Choose: match_existing or create_new | ✓（agent 判断） | ✓（自动阈值） |
| 4. Probability judgments | ✓（reviewer 评估） | ✗（用作者 prior） |
| 5. Rebuttal cycle | ✓ | ✗ |
| 6. Record CanonicalBinding + update global graph | ✓ | ✓ |

## 3. 流程

```
gaia publish 提交 4 个 artifacts
        │
        ▼
  ┌─────────────────────────────────┐
  │ Step 1: Embed                   │
  │  对每个 LocalCanonicalNode      │
  │  生成 embedding                 │
  └───────────┬─────────────────────┘
              │
              ▼
  ┌─────────────────────────────────┐
  │ Step 2: Search                  │
  │  对每个 local node，在 global   │
  │  graph 中搜索 top-k 最相似的    │
  │  GlobalCanonicalNode            │
  │  (vector + BM25 双路召回)       │
  └───────────┬─────────────────────┘
              │
              ▼
  ┌─────────────────────────────────┐
  │ Step 3: Match Decision          │
  │  对每个 local node:             │
  │                                 │
  │  best_match = top-1 candidate   │
  │                                 │
  │  if similarity > MATCH_THRESHOLD│
  │     AND type + kind 一致:       │
  │    → match_existing             │
  │  else:                          │
  │    → create_new                 │
  └───────────┬─────────────────────┘
              │
              ▼
  ┌─────────────────────────────────┐
  │ Step 4: Record & Update         │
  │                                 │
  │  match_existing:                │
  │    → 创建 CanonicalBinding      │
  │    → 更新 GlobalCanonicalNode   │
  │      的 member_local_nodes      │
  │      和 provenance              │
  │                                 │
  │  create_new:                    │
  │    → 创建新 GlobalCanonicalNode │
  │    → 创建 CanonicalBinding      │
  │                                 │
  │  两种情况都:                     │
  │    → 初始化 GlobalInferenceState│
  │      node_priors (用作者 prior)  │
  │    → 重定向 global factor 引用   │
  └───────────┬─────────────────────┘
              │
              ▼
  ┌─────────────────────────────────┐
  │ Step 5: Factor Integration      │
  │                                 │
  │  把 local graph 的 factor 提升  │
  │  到 global graph:               │
  │  - premises/conclusion 的       │
  │    local_canonical_id 替换为    │
  │    global_canonical_id          │
  │  - 跨 package 引用:            │
  │    如果 between 的节点在 global │
  │    graph 中已有对应，连上       │
  │    否则标记为 unresolved        │
  └─────────────────────────────────┘
```

## 4. Match Decision 规则

### 4.1 相似度阈值

```
MATCH_THRESHOLD = 0.90    # 高阈值，宁可 create_new 也不误合并
```

宁可多创建一些 GlobalCanonicalNode（后续 curation 合并），也不要错误地把不同的命题合并到一起（难以回滚）。

### 4.2 类型约束

匹配必须满足：
- `knowledge_type` 完全一致
- 对 `question` 和 `action`，`kind` 也必须一致
- `contradiction` 和 `equivalence` 不做跨 package 匹配（它们是 package-local 的关系声明）

### 4.3 匹配 vs 创建

| 条件 | 决策 |
|------|------|
| similarity >= 0.90 且类型一致 | `match_existing` |
| similarity < 0.90 | `create_new` |
| 类型不一致 | `create_new` |
| global graph 为空（首个 package） | 全部 `create_new` |

## 5. Parameterization 初始化

简化版不做独立的 probability judgment。GlobalInferenceState 的初始值来自作者：

- `node_priors[gcn_id]` = 作者在 local_parameterization 中给的 prior
- `factor_parameters[factor_id]` = 作者给的 conditional_probability

当多个 package 的 local node 映射到同一个 GlobalCanonicalNode 时，prior 取**加权平均**（权重 = package 的 member 数量）。

后续 curation reviewer 或完整 review engine 可以覆写这些值。

## 6. 数据模型

直接复用 graph-ir.md 定义的结构，不新增类型：

- `GlobalCanonicalNode` (graph-ir.md §4.3)
- `CanonicalBinding` (graph-ir.md §4.4)
- `GlobalInferenceState` (graph-ir.md §4.5)

新增存储：

```
global_graph/
  global_canonical_nodes.json     # list[GlobalCanonicalNode]
  canonical_bindings.json         # list[CanonicalBinding]
  global_factors.json             # list[FactorNode] (global_canonical_id refs)
  global_inference_state.json     # GlobalInferenceState
```

V1 用 JSON 文件存储。后续迁移到 LanceDB + Neo4j。

## 7. 与 Curation Service 的协作

| 简化版 Review | Curation |
|--------------|----------|
| 高阈值匹配，宁可多 create_new | 发现遗漏的合并（similarity 0.7-0.9 区间） |
| 不做 non-identity findings | 发现矛盾、等价、抽象关系 |
| 用作者 prior | — |
| 实时执行 | 定时修正 |

设计上 review 保守、curation 补充。两者共用 `libs/curation/similarity.py` 的 `find_similar()` 函数。

## 8. 接口

```python
class SimplifiedReviewEngine:
    def __init__(self, storage: StorageManager):
        ...

    async def canonicalize_package(
        self,
        local_graph: LocalCanonicalGraph,
        local_parameterization: LocalParameterization,
    ) -> CanonicalizationResult:
        """Map local nodes to global graph. Creates CanonicalBindings."""
        ...

@dataclass
class CanonicalizationResult:
    bindings: list[CanonicalBinding]
    new_global_nodes: list[GlobalCanonicalNode]
    matched_global_nodes: list[str]          # gcn_ids that got new members
    unresolved_cross_refs: list[str]         # factor refs that couldn't be resolved
```

## 9. 不在此次范围

- Rebuttal cycle
- Independent probability judgments（reviewer 校准 prior）
- Non-identity findings（refines, contradicts, missing_ref）
- LLM-based semantic matching（V1 用 embedding cosine）
- 完整 review report 生成
