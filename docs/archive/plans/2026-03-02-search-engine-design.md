# Search Engine 模块详细设计

> **Status:** COMPLETED

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.4 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/plans/2026-03-02-storage-layer-design.md` |
| 目标 | 定义 Search Engine 模块的结构、接口和召回策略 |
| 变更记录 | v1.0: 初始设计; v1.1: 统一命名 (Node/HyperEdge), API 路径 /search/nodes, /search/hyperedges; v1.2: Node 模型变更——text→content, confidence→prior, 新增 title/metadata 字段 (ScoredNode 内嵌 Node，无需额外修改); v1.3: HyperEdge.reasoning 改为 list = []; v1.4: Node 移除 notations/assumptions (改用 extra)，content 类型改为 str\|dict\|list，type 改为 str；Node/HyperEdge 新增 extra: dict |

---

## 1. 设计原则

- **两个搜索入口**：`search_nodes`（搜节点）和 `search_edges`（搜超边）
- **三路召回**：向量搜索 + BM25 + Abstraction 树遍历，合并去重排序
- **search_edges 基于 search_nodes**：先搜节点，再展开到关联超边
- **调用方可选择召回路径**：按需启用/禁用某路召回
- **`/search/subgraph` 推迟到 Layer 2 Research API**：通用图模式匹配在十亿级开销大，改为提供预定义模式查询

---

## 2. 三路召回策略

| 路径 | 实现 | 找什么 | 适合场景 |
|------|------|--------|---------|
| **vector** | `storage.vector.search` | 语义相似节点 | 换了说法但意思一样 |
| **bm25** | `storage.lance.fts_search` | 关键词匹配 | 包含相同术语但 embedding 不相似 |
| **topology** | `storage.graph.get_subgraph(edge_types=["abstraction"])` | Abstraction 树上的相关节点 | 文本不同但知识结构相关 |

**合并策略**：三路结果取并集，按分数归一化后加权排序，去重返回 top-k。

```
vector (top-100)  ──┐
bm25 (top-100)    ──┼──► 合并去重 → 归一化加权排序 → top-k
topology (N-hop)  ──┘
```

---

## 3. 目录结构

```
services/search-engine/
├── __init__.py
├── engine.py            # SearchEngine — 主入口
├── recall/
│   ├── __init__.py
│   ├── vector.py        # VectorRecall — 向量搜索路径
│   ├── bm25.py          # BM25Recall — 全文搜索路径
│   └── topology.py      # TopologyRecall — Abstraction 树遍历路径
└── merger.py            # ResultMerger — 多路结果合并去重排序
```

---

## 4. 接口设计

### 4.1 SearchEngine — 对外入口 (2 个方法)

```python
# services/search-engine/engine.py
class SearchEngine:
    """多路召回搜索引擎"""

    def __init__(self, storage: StorageManager): ...

    async def search_nodes(
        self,
        query: str,
        embedding: list[float],
        k: int = 50,
        filters: NodeFilters | None = None,
        paths: list[Literal["vector", "bm25", "topology"]] | None = None,
    ) -> list[ScoredNode]:
        """搜索节点：三路召回 → 合并去重 → 排序
        paths=None 时启用全部三路。
        """

    async def search_edges(
        self,
        query: str,
        embedding: list[float],
        k: int = 50,
        filters: EdgeFilters | None = None,
        paths: list[Literal["vector", "bm25", "topology"]] | None = None,
    ) -> list[ScoredHyperEdge]:
        """搜索超边：search_nodes → 展开到关联超边 → 排序"""
```

### 4.2 过滤条件

```python
class NodeFilters(BaseModel):
    type: list[str] | None = None           # ["paper-extract", "abstraction", ...]
    status: list[str] = ["active"]          # 默认只搜 active
    min_belief: float | None = None         # 最低置信度
    keywords: list[str] | None = None       # 关键词过滤

class EdgeFilters(BaseModel):
    type: list[str] | None = None           # ["induction", "abstraction", "contradiction", ...]
    verified: bool | None = None            # 是否已验证
```

### 4.3 返回类型

```python
class ScoredNode(BaseModel):
    node: Node
    score: float                            # 归一化后的综合分数
    sources: list[str]                      # 来自哪些召回路径 ["vector", "bm25", "topology"]

class ScoredHyperEdge(BaseModel):
    edge: HyperEdge
    score: float
    sources: list[str]
```

### 4.4 召回组件 (各 1 个方法)

```python
# services/search-engine/recall/vector.py
class VectorRecall:
    """向量搜索路径"""
    def __init__(self, vector_client: VectorSearchClient): ...
    async def recall(self, embedding: list[float], k: int = 100) -> list[tuple[int, float]]:
        """返回 [(node_id, distance), ...]"""


# services/search-engine/recall/bm25.py
class BM25Recall:
    """全文搜索路径"""
    def __init__(self, lance_store: LanceStore): ...
    async def recall(self, query: str, k: int = 100) -> list[tuple[int, float]]:
        """返回 [(node_id, bm25_score), ...]"""


# services/search-engine/recall/topology.py
class TopologyRecall:
    """Abstraction 树遍历路径"""
    def __init__(self, graph_store: Neo4jGraphStore): ...
    async def recall(self, seed_node_ids: list[int], hops: int = 3) -> list[tuple[int, float]]:
        """从种子节点沿 Abstraction 树遍历，返回 [(node_id, hop_distance), ...]
        seed_node_ids 来自 vector/bm25 的 top 结果。"""
```

### 4.5 ResultMerger (1 个方法)

```python
# services/search-engine/merger.py
class ResultMerger:
    """合并多路召回结果"""
    async def merge(
        self,
        results: dict[str, list[tuple[int, float]]],
        k: int = 50,
    ) -> list[tuple[int, float, list[str]]]:
        """输入: {"vector": [(id, score)...], "bm25": [...], "topology": [...]}
        输出: [(node_id, merged_score, sources), ...] 排序后 top-k
        归一化各路分数到 [0,1]，加权求和，去重。"""
```

---

## 5. 数据流

### search_nodes 流程

```
输入: query + embedding + filters + paths

1. 并行启动 vector + bm25:
   ├── VectorRecall.recall(embedding, k=100)
   └── BM25Recall.recall(query, k=100)

2. 取 vector top-10 作为种子 → TopologyRecall.recall(seed_ids, hops=3)

3. ResultMerger.merge(三路结果, k)

4. 按 node_ids 批量加载节点详情:
   storage.lance.load_nodes_bulk(node_ids)

5. 应用 filters (type, status, min_belief, keywords)

6. 返回 list[ScoredNode]
```

### search_edges 流程

```
1. search_nodes(query, embedding, k, ...) → 得到节点列表

2. 对匹配节点，获取关联超边:
   storage.graph.get_subgraph(node_ids, hops=1) → edge_ids

3. 批量加载超边详情:
   [storage.graph.get_hyperedge(eid) for eid in edge_ids]

4. 应用 EdgeFilters

5. 按节点匹配分数排序超边，返回 list[ScoredHyperEdge]
```

---

## 6. 接口总览

| 组件 | 方法 | 说明 |
|------|------|------|
| **SearchEngine** | `search_nodes` | 三路召回搜节点 |
| | `search_edges` | 先搜节点再展开到超边 |
| **VectorRecall** | `recall` | 向量搜索 |
| **BM25Recall** | `recall` | 全文搜索 |
| **TopologyRecall** | `recall` | Abstraction 树遍历 |
| **ResultMerger** | `merge` | 多路结果合并去重排序 |

**总计 6 个公开方法。**

---

## 7. 调用方

| 调用方 | 使用的方法 | 场景 |
|--------|-----------|------|
| **API Gateway** | `search_nodes` | `POST /search/nodes` |
| **API Gateway** | `search_edges` | `POST /search/hyperedges` |
| **Commit Engine (DedupChecker)** | `search_nodes` | submit 时去重召回 |
| **Build Pipeline (外部)** | `search_nodes` | 候选对发现 |
