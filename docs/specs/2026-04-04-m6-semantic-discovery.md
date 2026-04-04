# M6 — Semantic Discovery Spec

> **Status:** Draft
> **Date:** 2026-04-04
> **Supersedes:** `2026-03-31-m6-curation.md`（scope 缩减，只保留 embedding + clustering）

## 概述

M6 专注于**语义聚类发现**：对 global FactorGraph 中所有 public variable nodes 生成 embedding，通过 FAISS 向量相似度搜索找到语义相似的 variable 组（cluster），输出结构化的聚类结果。

**M6 只做发现，不做判断。** 聚类结果交给下游 spec（Relation Analysis）来用 LLM 分析 cluster 内 variable 之间的具体关系（subsumption / equivalence / contradiction / unrelated），并生成 Gaia Lang package 提交 proposal。

**不在 M6 scope 内的：**
- Binding / Equivalence / Contradiction 的具体判断 → 后续 Relation Analysis spec
- ConflictDetection（BP 诊断信号）→ 后续 spec
- StructuralAudit（孤立节点、悬空因子）→ 后续 spec
- Curation 包的生成和提交 → 后续 spec

M6 依赖 M2（存储层）+ M5（integrate 完成后的 global graph）。

## 上游参考

- `propositional_logic_analysis/clustering/`：FAISS 聚类 + embedding 参考实现
- `propositional_logic_analysis/clustering/prompts/join_symmetric.md`：关系分类 prompt（下游 spec 参考）

---

## 数据流

```
┌──────────────┐     gcn_ids needing    ┌──────────────┐
│   LanceDB    │     embedding          │  Embedding   │
│              │ ─────────────────────► │    API       │
│ global vars  │                        │  (dashscope) │
│ local vars   │     content text       │              │
│ (content)    │ ─────────────────────► │              │
└──────────────┘                        └──────┬───────┘
                                               │ vectors
                                               ▼
                                        ┌──────────────┐
                                        │  ByteHouse   │
                                        │              │
                                        │ node_        │
                                        │  embeddings  │
                                        └──────┬───────┘
                                               │ load all
                                               │ embeddings
                                               ▼
                                        ┌──────────────┐
                                        │    FAISS     │
                                        │  clustering  │
                                        │              │
                                        │ IndexFlatIP  │
                                        │ + UnionFind  │
                                        └──────┬───────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │   Clusters   │
                                        │              │
                                        │ [{gcn_ids},  │
                                        │  {gcn_ids},  │
                                        │  ...]        │
                                        └──────────────┘
```

---

## 三个系统的职责

| 系统 | 存什么 | M6 中的查询 |
|------|--------|------------|
| **LanceDB** | LKM 结构化数据 | 获取 public global variable 列表 + content（通过 representative_lcn 回查 local） |
| **ByteHouse** | `node_embeddings` 表 | 存取 embedding 向量 |
| **FAISS** | 内存索引（不持久化） | ANN search + Union-Find 聚类 |

---

## Step 1: Embedding 生成与存储

**触发时机：** integrate 完成后，对新增的 global variable nodes 生成 embedding。

**流程：**

1. 从 LanceDB 获取所有 `visibility="public"` 的 global variable gcn_ids
2. 从 ByteHouse 查已有 embedding 的 gcn_ids，取差集得到 pending
3. 对 pending gcn_ids，从 LanceDB 回查 content（通过 `representative_lcn` → `local_variable_nodes.content`）
4. 调用 embedding API 生成 512 维向量
5. 批量写入 ByteHouse `node_embeddings` 表

**Embedding API：**
- URL: `https://openapi.dp.tech/openapi/v1/test/vectorize`
- Auth: `accessKey` header（env: `ACCESS_KEY`）
- Request: `{"text": "...", "provider": "dashscope"}`
- Response: `{"data": {"vector": [float * 512]}}`
- 维度: 512

**并发控制（参考 propositional_logic_analysis）：**
- `asyncio.gather()` + `Semaphore(N)`
- 专用 writer 线程做 ByteHouse 批量写入，避免阻塞 embedding 计算
- 失败重试（3 次 + exponential backoff）

**ByteHouse 表结构：**

```sql
CREATE TABLE paper_data.node_embeddings (
    gcn_id        String,
    content       String,
    node_type     String,      -- "claim" | "question" | "setting" | "action"
    embedding     Array(Float32),
    source_id     String,      -- embedding model identifier
    created_at    DateTime DEFAULT now()
) ENGINE = HaUniqueMergeTree(...)
ORDER BY gcn_id
UNIQUE KEY gcn_id
SETTINGS index_granularity = 128
```

---

## Step 2: FAISS 聚类

**参考实现：** `propositional_logic_analysis/clustering/src/faiss_clusterer.py`

**算法：**

1. 从 ByteHouse 批量加载 embedding（按 `node_type` 分组，只处理同类型）
2. 构建 FAISS `IndexFlatIP`（内积 = 归一化向量上的 cosine similarity）
3. 对每个 variable 做 k-NN search（`k` 默认 100）
4. Union-Find 合并：similarity > `threshold` 的 pair 合并到同一组
5. 提取连通分量 = 语义聚类

**过滤约束（参考 propositional_logic_analysis）：**
- **仅同类型比较**：claim 只和 claim 聚，question 只和 question 聚
- **`exclude_same_factor`**：同一个 factor 的 premise 和 conclusion 不互聚（需从 Neo4j 查拓扑）
- **`max_cluster_size`**：单个 cluster 上限（默认 20），防止 mega-cluster
- **排除已知 binding**：已有 CanonicalBinding 的 pair 跳过（已经在 integrate 阶段处理过）

**Union-Find 选择理由（vs k-means / DBSCAN）：**
- 不需要预设聚类数
- 自然处理传递性（A 近 B、B 近 C → ABC 同组）
- 和 propositional_logic_analysis 的方法一致

---

## 输出

```python
@dataclass
class SemanticCluster:
    cluster_id: str                   # 自动生成
    node_type: str                    # "claim" | "question" | ...
    gcn_ids: list[str]                # cluster 内的 global variable ids
    centroid_gcn_id: str              # 离质心最近的 variable（cluster 代表）
    avg_similarity: float             # cluster 内平均 pairwise 相似度
    min_similarity: float             # cluster 内最小 pairwise 相似度

@dataclass
class ClusteringResult:
    clusters: list[SemanticCluster]
    stats: ClusteringStats
    timestamp: datetime

@dataclass
class ClusteringStats:
    total_variables_scanned: int      # 参与聚类的 variable 总数
    total_embeddings_computed: int    # 本次新计算的 embedding 数
    total_clusters: int
    cluster_size_distribution: dict[int, int]  # size → count
    elapsed_seconds: float
```

---

## 实现文件结构

```
gaia/lkm/core/
    discovery.py             # run_semantic_discovery() 主函数
    _embedding.py            # embedding 生成 + ByteHouse 读写
    _clustering.py           # FAISS 聚类 + Union-Find

gaia/lkm/models/
    discovery.py             # SemanticCluster, ClusteringResult, ClusteringStats

gaia/lkm/storage/
    bytehouse_store.py       # ByteHouseEmbeddingStore: CRUD + 批量加载
```

---

## 配置参数

```python
@dataclass
class DiscoveryConfig:
    # Embedding
    embedding_api_url: str = "https://openapi.dp.tech/openapi/v1/test/vectorize"
    embedding_provider: str = "dashscope"
    embedding_dim: int = 512
    embedding_concurrency: int = 24  # semaphore limit for async API calls

    # Clustering
    similarity_threshold: float = 0.85
    faiss_k: int = 100              # k-NN search top-k
    max_cluster_size: int = 20
    exclude_same_factor: bool = True

    # FAISS index type
    faiss_index_type: str = "flat"  # "flat" (exact) or "ivf" (approximate)
```

---

## 关键约束

1. **M6 只做聚类发现，不做关系判断** — 不判断 binding/equivalence/contradiction
2. **仅 public variable 参与**：private variable 不参与
3. **相同 type 才聚类**：claim 只和 claim 聚
4. **Embedding 存 ByteHouse**：不存 LanceDB
5. **增量计算**：只对新增 variable 生成 embedding，不重算已有的
6. **FAISS 在内存中运行**：不持久化索引，每次运行重建

---

## 测试要求

### 单元测试

- `test_embedding_api_call`：content → embedding 向量，维度 512
- `test_incremental_embedding`：只对新增 variable 计算 embedding
- `test_clustering_similar_pairs`：相似 variable pair 在同一 cluster
- `test_clustering_dissimilar_separate`：不相似的 variable 在不同 cluster
- `test_type_filter`：不同 type 不聚类
- `test_private_excluded`：private variable 不参与
- `test_max_cluster_size`：单个 cluster 不超过上限
- `test_exclude_same_factor`：同 factor 的节点不互聚

### 集成测试

- `test_full_discovery_pipeline`：从 fixture 数据跑完整发现流程
- `test_idempotent_discovery`：跑两次结果一致（同样的 embedding + 同样的阈值）

---

## 下游消费者（后续 Relation Analysis spec）

M6 输出的 `ClusteringResult` 交给下游处理：

1. 对每个 cluster，加载各 variable 的 content
2. 用 LLM 做 pairwise 关系分类（参考 `join_symmetric.md` 的四种关系）：
   - **Subsumption**（蕴含）：A entails B → 建立层级
   - **Partial Overlap**（部分重叠）→ 创建 join/abstract node
   - **Contradiction**（矛盾）→ 标记冲突
   - **Unrelated**（无关）→ 跳过（clustering 误匹配）
3. 生成 Gaia Lang package，以 relation proposal 的形式提交到 registry

这部分不在 M6 scope 内，将在独立 spec 中定义。
