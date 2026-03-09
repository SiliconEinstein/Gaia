# libs/storage 模块详细设计

> **Status:** COMPLETED

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.4 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/lkm_system_design/phase1_billion_scale.md` (v1.2, §4 存储层) |
| 目标 | 定义 `libs/storage` 模块的目录结构、接口清单和设计决策 |
| 变更记录 | v1.0: 初始设计; v1.1: 统一命名 (Node/HyperEdge)，get_subgraph 加 edge_types; v1.2: Node 增加 title/metadata 字段，text→content，confidence→prior; v1.3: HyperEdge.reasoning 改为 list = []; v1.4: Node 移除 notations/assumptions (改用 extra)，content 类型改为 str\|dict\|list，type 改为 str；Node/HyperEdge 新增 extra: dict |

---

## 1. 设计原则

- **基本逻辑单元是节点 (Node) 和超边 (HyperEdge)**——存储层不涉及论文等上游概念
- **命名约定**：对外接口和数据模型统一用 `Node`（= 命题）和 `HyperEdge`（= 推理超边）。Neo4j 内部用 `:Proposition` 和 `:Hyperedge` 标签是实现细节，不暴露给上层
- **三层存储**：LanceDB（节点内容+metadata+belief）、Neo4j（图拓扑）、ByteHouse/LanceDB（向量检索）
- **无 Redis**：BP 消息在推理引擎进程内存完成，belief 值写回 LanceDB
- **StorageManager 是容器，不是门面**：不做组合业务逻辑，上层服务直接调用各 store
- **接口最小化**：只暴露真正需要的原子操作，组合逻辑由上层负责

---

## 2. 目录结构

```
libs/storage/
├── __init__.py              # 导出 StorageManager, StorageConfig
├── config.py                # StorageConfig — 部署模式与连接配置
├── manager.py               # StorageManager — 容器 + 生命周期管理
├── lance_store.py           # LanceStore — 节点内容 + metadata + belief
├── neo4j_store.py           # Neo4jGraphStore — 图拓扑 (Cypher)
├── vector_search/
│   ├── __init__.py          # 工厂: create_vector_client(config)
│   ├── base.py              # VectorSearchClient ABC
│   ├── bytehouse_client.py  # ByteHouseVectorClient (生产环境)
│   └── lancedb_client.py    # LanceDBVectorClient (本地 fallback)
├── id_generator.py          # IDGenerator — ID 分配
├── migration.py             # 原型 JSON/SQLite → 新存储迁移工具
└── compat.py                # GraphStoreCompat — 兼容原型 GraphStore 接口
```

---

## 3. 配置

```python
# libs/storage/config.py
from pydantic import BaseModel
from typing import Literal

class StorageConfig(BaseModel):
    deployment_mode: Literal["production", "local"] = "local"

    # LanceDB
    lancedb_path: str = "/data/lancedb/lkm"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "lkm"

    # ByteHouse (production only)
    bytehouse_host: str | None = None
    bytehouse_port: int = 19000
    bytehouse_database: str = "lkm"
    bytehouse_api_key: str | None = None

    # Local fallback
    local_vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"
```

通过 `deployment_mode` 决定向量检索走 ByteHouse 还是 LanceDB。Neo4j 和 LanceDB 在两种模式下接口一致，无需切换（生产用 Neo4j Enterprise，本地用 Neo4j Community，同一 Cypher 接口）。

---

## 4. 接口设计

### 4.1 LanceStore — 节点主存储 (7 个方法)

存储节点内容、元数据和 belief 值。不存 embedding（由 VectorSearchClient 负责）。

```python
# libs/storage/lance_store.py
class LanceStore:
    """LanceDB：节点文本 + metadata + belief"""

    def __init__(self, db_path: str): ...
    async def close(self) -> None: ...

    # ── 节点 CRUD ──
    async def save_nodes(self, nodes: list[Node]) -> list[int]:
        """批量写入节点，返回分配的 ID 列表"""

    async def load_node(self, node_id: int) -> Node | None:
        """按 ID 读取单个节点"""

    async def load_nodes_bulk(self, node_ids: list[int]) -> list[Node]:
        """批量读取节点"""

    async def update_node(self, node_id: int, **fields) -> None:
        """更新节点字段（如 status, prior 等）"""

    # ── Belief 读写（BP 引擎计算后写回）──
    async def update_beliefs(self, beliefs: dict[int, float]) -> None:
        """批量更新 belief 值: {node_id: belief_value}"""

    async def get_beliefs_bulk(self, node_ids: list[int]) -> dict[int, float]:
        """批量读取 belief 值"""

    # ── 全文搜索 ──
    async def fts_search(
        self, query: str, k: int = 100
    ) -> list[tuple[int, float]]:
        """BM25 全文搜索，返回 [(node_id, score), ...]"""
```

**Node 数据模型**（status 只有 `active | deleted`，不做节点合并）：

```python
class Node(BaseModel):
    id: int
    type: str                                # paper-extract | abstraction | deduction | conjecture | ...
    subtype: str | None = None
    title: str | None = None
    content: str | dict | list
    keywords: list[str] = []
    prior: float = 1.0                   # BP 先验输入
    belief: float | None = None          # BP 引擎写回
    status: Literal["active", "deleted"] = "active"
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None
```

### 4.2 Neo4jGraphStore — 图拓扑 (5 个方法)

存储节点（只存 ID）和超边（建模为 Reasoning 节点 + :TAIL/:HEAD 关系）。`create_hyperedge` 内部自动 `MERGE` 节点，无需单独创建。

**命名说明**：接口方法用 `hyperedge`（对外术语）。Neo4j 内部 `:Proposition` / `:Hyperedge` 标签是实现细节。

```python
# libs/storage/neo4j_store.py
class Neo4jGraphStore:
    """Neo4j 图拓扑：节点 + 超边（Reasoning 节点 + :TAIL/:HEAD 关系）"""

    def __init__(self, driver: neo4j.AsyncDriver, database: str): ...
    async def initialize_schema(self) -> None: ...   # CREATE CONSTRAINT/INDEX
    async def close(self) -> None: ...

    # ── 超边写入 ──
    async def create_hyperedge(self, edge: HyperEdge) -> int:
        """创建一条超边。内部自动 MERGE tail/head 节点"""

    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        """批量创建超边"""

    async def update_hyperedge(self, edge_id: int, **fields) -> None:
        """更新超边属性（probability, verified 等）"""

    # ── 超边读取 ──
    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        """按 ID 读取超边详情（含 tail/head 列表）"""

    # ── 图遍历 ──
    async def get_subgraph(
        self, node_ids: list[int], hops: int = 1,
        edge_types: list[str] | None = None,
    ) -> tuple[set[int], set[int]]:
        """从指定节点出发，获取 N-hop 邻域。
        返回 (node_ids, hyperedge_ids)。
        知识图 1-hop = Neo4j 2-hop（节点→超边→节点）。
        edge_types: 过滤超边类型，None=全部，["abstraction"]=只沿 Abstraction 边遍历。
        上层按需用 get_hyperedge 补全超边详情。"""
```

**HyperEdge 数据模型**：

```python
class HyperEdge(BaseModel):
    id: int
    type: str                              # paper-extract | abstraction | induction | contradiction | retraction
    subtype: str | None = None
    tail: list[int]                        # 前提 node IDs
    head: list[int]                        # 结论 node IDs
    probability: float | None = None
    verified: bool = False
    reasoning: list = []
    metadata: dict = {}
    extra: dict = {}
    created_at: datetime | None = None
```

**Neo4j 内部 Cypher 建模**（实现细节）：

> **注意**：`reasoning` 字段是 `list` 类型，Neo4j 中存储为 JSON 字符串（`json.dumps`），读取时用 `json.loads` 解析。

```cypher
-- Neo4j 标签: :Proposition (对应 Node), :Hyperedge (对应 HyperEdge)
-- 创建 Induction 超边（多个前提 → 一个结论）
MERGE (a:Proposition {id: $tail_0})
MERGE (b:Proposition {id: $tail_1})
MERGE (c:Proposition {id: $head_0})
CREATE (e:Hyperedge:Induction {id: $eid, probability: $prob, verified: false})
CREATE (a)-[:TAIL]->(e), (b)-[:TAIL]->(e), (e)-[:HEAD]->(c)

-- get_subgraph: 3-hop 邻域 (edge_types=None, 全部类型)
MATCH path = (start:Proposition)-[:TAIL|HEAD*1..6]-(node)
WHERE start.id IN $node_ids AND node:Proposition

-- get_subgraph: 沿 Abstraction 树遍历 (edge_types=["abstraction"])
MATCH path = (start:Proposition)-[:TAIL|HEAD*1..6]-(node)
WHERE start.id IN $node_ids AND node:Proposition
  AND ALL(n IN [x IN nodes(path) WHERE x:Hyperedge] WHERE n.type IN $edge_types)
```

### 4.3 VectorSearchClient — 向量检索抽象 (3 个方法)

通过 ABC + 工厂模式，生产环境用 ByteHouse，本地用 LanceDB DiskANN。

```python
# libs/storage/vector_search/base.py
from abc import ABC, abstractmethod

class VectorSearchClient(ABC):
    """向量检索统一接口"""

    @abstractmethod
    async def insert_batch(
        self, node_ids: list[int], embeddings: list[list[float]]
    ) -> None:
        """批量写入 embedding"""

    @abstractmethod
    async def search(
        self, query: list[float], k: int = 50
    ) -> list[tuple[int, float]]:
        """单条向量搜索，返回 [(node_id, distance), ...]"""

    @abstractmethod
    async def search_batch(
        self, queries: list[list[float]], k: int = 50
    ) -> list[list[tuple[int, float]]]:
        """批量向量搜索"""
```

```python
# libs/storage/vector_search/__init__.py
from .base import VectorSearchClient
from ..config import StorageConfig

def create_vector_client(config: StorageConfig) -> VectorSearchClient:
    if config.deployment_mode == "production":
        from .bytehouse_client import ByteHouseVectorClient
        return ByteHouseVectorClient(
            host=config.bytehouse_host,
            port=config.bytehouse_port,
            database=config.bytehouse_database,
            api_key=config.bytehouse_api_key,
        )
    else:
        from .lancedb_client import LanceDBVectorClient
        return LanceDBVectorClient(
            db_path=config.lancedb_path,
            index_type=config.local_vector_index_type,
        )
```

### 4.4 StorageManager — 容器 + 生命周期

不做组合业务逻辑。上层服务通过 `manager.lance` / `manager.graph` / `manager.vector` 直接调用各 store。

```python
# libs/storage/manager.py
class StorageManager:
    """从一份配置创建三个 store，统一管理连接生命周期"""

    lance: LanceStore
    graph: Neo4jGraphStore
    vector: VectorSearchClient
    ids: IDGenerator

    def __init__(self, config: StorageConfig):
        self.lance = LanceStore(config.lancedb_path)
        self.graph = Neo4jGraphStore(
            driver=neo4j.AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password),
            ),
            database=config.neo4j_database,
        )
        self.vector = create_vector_client(config)
        self.ids = IDGenerator(...)

    async def close(self) -> None:
        """关闭所有连接"""
        await self.lance.close()
        await self.graph.close()
```

### 4.5 IDGenerator — ID 分配

```python
# libs/storage/id_generator.py
class IDGenerator:
    """分布式唯一 ID 分配"""

    async def alloc_node_id(self) -> int: ...
    async def alloc_hyperedge_id(self) -> int: ...
    async def alloc_node_ids_bulk(self, count: int) -> list[int]: ...
    async def alloc_hyperedge_ids_bulk(self, count: int) -> list[int]: ...
```

---

## 5. 接口总览

| Store | 方法 | 说明 |
|-------|------|------|
| **LanceStore** | `save_nodes` | 批量写入节点 |
| | `load_node` | 单条读取 |
| | `load_nodes_bulk` | 批量读取 |
| | `update_node` | 更新节点字段 |
| | `update_beliefs` | BP 结果批量写回 |
| | `get_beliefs_bulk` | 批量读取 belief |
| | `fts_search` | BM25 全文搜索 |
| **Neo4jGraphStore** | `create_hyperedge` | 创建超边（自动 MERGE 节点）|
| | `create_hyperedges_bulk` | 批量创建超边 |
| | `update_hyperedge` | 更新超边属性 |
| | `get_hyperedge` | 读取超边详情 |
| | `get_subgraph` | N-hop 邻域遍历（可按超边类型过滤）|
| **VectorSearchClient** | `insert_batch` | 批量写入 embedding |
| | `search` | 单条向量搜索 |
| | `search_batch` | 批量向量搜索 |
| **StorageManager** | `close` | 关闭所有连接 |
| **IDGenerator** | `alloc_node_id` | 分配单个节点 ID |
| | `alloc_hyperedge_id` | 分配单个超边 ID |
| | `alloc_node_ids_bulk` | 批量分配节点 ID |
| | `alloc_hyperedge_ids_bulk` | 批量分配超边 ID |

**总计 20 个公开方法**，每个职责单一。

---

## 6. 与 v1.1 模块架构的变更对照

| v1.1 (旧) | v1.2 (新) | 变更原因 |
|-----------|-----------|---------|
| `graph_store.py` (DuckDB) | `neo4j_store.py` (Neo4j) | Neo4j 原生图遍历，5-hop 毫秒级 |
| `belief_store.py` (Redis) | **删除** | BP 消息在引擎进程内存，belief 写回 LanceDB |
| LanceStore 含 embedding + ANN | LanceStore **不含** embedding | 向量检索独立到 VectorSearchClient |
| 无向量抽象层 | `vector_search/` 子包 | ByteHouse (生产) + LanceDB (本地) 可切换 |
| StorageManager 含组合方法 | StorageManager 仅容器 | 组合逻辑由上层业务决定 |
| `mark_merged()` | **删除** | 新架构不做节点合并 |
| Node status: active/merged/deleted | active/deleted | 无 merged 状态 |
| `save_contradiction` / `load_contradictions` | **删除** | 矛盾检测是上层逻辑 |
| `find_unverified_edges` / `get_edges_by_type` | **删除** | Pipeline 业务查询，非存储层职责 |
| 4 个图遍历方法 | 1 个 `get_subgraph` | 统一为单一遍历接口 |

---

## 7. 上层调用示例

### Commit Engine merge 操作

```python
async def merge_commit(manager: StorageManager, commit: Commit):
    # 1. 分配 ID
    node_ids = await manager.ids.alloc_node_ids_bulk(len(commit.new_nodes))
    edge_ids = await manager.ids.alloc_hyperedge_ids_bulk(len(commit.new_edges))

    # 2. 写 LanceDB（节点内容 + metadata）
    await manager.lance.save_nodes(commit.new_nodes)

    # 3. 写 Neo4j（图拓扑）
    await manager.graph.create_hyperedges_bulk(commit.new_edges)

    # 4. 写 VectorSearch（embedding）
    await manager.vector.insert_batch(node_ids, commit.embeddings)

    # 5. 触发局部 BP（上层逻辑）
    ...
```

### 查询节点子图

```python
async def get_node_detail(manager: StorageManager, node_id: int):
    # 1. 取节点详情
    node = await manager.lance.load_node(node_id)

    # 2. 取 1-hop 邻域
    neighbor_ids, edge_ids = await manager.graph.get_subgraph([node_id], hops=1)

    # 3. 补全超边详情（按需）
    edges = [await manager.graph.get_hyperedge(eid) for eid in edge_ids]

    # 4. 补全邻居节点详情（按需）
    neighbors = await manager.lance.load_nodes_bulk(list(neighbor_ids))

    return node, edges, neighbors
```
