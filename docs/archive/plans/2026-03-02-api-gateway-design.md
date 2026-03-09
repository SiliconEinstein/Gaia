# API Gateway 模块详细设计

> **Status:** COMPLETED

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.3 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/plans/2026-03-02-commit-engine-design.md`, `docs/plans/2026-03-02-search-engine-design.md`, `docs/plans/2026-03-02-storage-layer-design.md` |
| 目标 | 定义 API Gateway 的路由结构和端点设计 |
| 变更记录 | v1.0: 初始设计; v1.1: Node 模型变更——text→content, confidence→prior, 新增 title/metadata 字段 (端点无 raw node 字段引用，无需额外修改); v1.2: HyperEdge.reasoning 改为 list = []; v1.3: Node 移除 notations/assumptions (改用 extra)，content 类型改为 str\|dict\|list，type 改为 str；Node/HyperEdge 新增 extra: dict |

---

## 1. 设计原则

- **纯路由层**：Gateway 不包含业务逻辑，只做请求转发和序列化
- **统一命名**：API 路径用 `/nodes` 和 `/hyperedges`（与数据模型 `Node` / `HyperEdge` 一致）
- **Layer 1 先行**：本文档覆盖 Layer 1 (Knowledge Graph API)，Layer 2 (Research API) 待后续设计

---

## 2. 目录结构

```
services/gateway/
├── __init__.py
├── app.py               # FastAPI app 创建 + 生命周期管理
├── routes/
│   ├── __init__.py
│   ├── commits.py       # /commits 相关端点
│   ├── read.py          # /nodes, /hyperedges 相关端点
│   └── search.py        # /search 相关端点
└── deps.py              # 依赖注入 (StorageManager, CommitEngine, SearchEngine)
```

---

## 3. 端点列表

### 3.1 写入 — Commit 工作流 (5 个端点)

| 方法 | 路径 | 转发到 | 说明 |
|------|------|--------|------|
| POST | `/commits` | `CommitEngine.submit` | 提交 + 轻量检查 |
| GET | `/commits/{id}` | `CommitEngine.get_commit` | 查询 commit 状态 |
| POST | `/commits/{id}/review` | `CommitEngine.review` | LLM 审核 |
| POST | `/commits/{id}/merge` | `CommitEngine.merge` | 入图 + 触发 BP |
| POST | `/commits/batch` | 批量 `CommitEngine.submit` | 批量提交 |

### 3.2 读取 — 精确查询 (3 个端点)

| 方法 | 路径 | 转发到 | 说明 |
|------|------|--------|------|
| GET | `/nodes/{id}` | `storage.lance.load_node` | 读取节点详情 |
| GET | `/hyperedges/{id}` | `storage.graph.get_hyperedge` | 读取超边详情 |
| GET | `/nodes/{id}/subgraph` | `storage.graph.get_subgraph` + `storage.lance.load_nodes_bulk` | 读取节点的 N-hop 子图 |

### 3.3 搜索 (2 个端点)

| 方法 | 路径 | 转发到 | 说明 |
|------|------|--------|------|
| POST | `/search/nodes` | `SearchEngine.search_nodes` | 三路召回搜节点 |
| POST | `/search/hyperedges` | `SearchEngine.search_edges` | 三路召回搜超边 |

**总计 10 个端点。**

---

## 4. 端点详细设计

### 4.1 POST /commits

```python
# services/gateway/routes/commits.py
@router.post("/commits")
async def submit_commit(
    request: CommitRequest,
    engine: CommitEngine = Depends(get_commit_engine),
) -> CommitResponse:
    return await engine.submit(request)
```

**请求体**：
```python
class CommitRequest(BaseModel):
    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]
```

**响应**：
```python
class CommitResponse(BaseModel):
    commit_id: str
    status: str                     # "pending_review"
    check_results: CheckResults     # 去重候选、候选矛盾
```

### 4.2 GET /commits/{id}

```python
@router.get("/commits/{commit_id}")
async def get_commit(
    commit_id: str,
    engine: CommitEngine = Depends(get_commit_engine),
) -> Commit:
    return await engine.get_commit(commit_id)
```

### 4.3 POST /commits/{id}/review

```python
@router.post("/commits/{commit_id}/review")
async def review_commit(
    commit_id: str,
    depth: str = "standard",
    engine: CommitEngine = Depends(get_commit_engine),
) -> ReviewResponse:
    return await engine.review(commit_id, depth=depth)
```

### 4.4 POST /commits/{id}/merge

```python
@router.post("/commits/{commit_id}/merge")
async def merge_commit(
    commit_id: str,
    force: bool = False,
    engine: CommitEngine = Depends(get_commit_engine),
) -> MergeResponse:
    return await engine.merge(commit_id, force=force)
```

### 4.5 POST /commits/batch

```python
@router.post("/commits/batch")
async def batch_submit(
    request: BatchCommitRequest,
    engine: CommitEngine = Depends(get_commit_engine),
) -> BatchCommitResponse:
    ...
```

```python
class BatchCommitRequest(BaseModel):
    commits: list[CommitRequest]
    auto_review: bool = True
    review_depth: str = "standard"

class BatchCommitResponse(BaseModel):
    batch_id: str
    total_commits: int
    status: str                     # "processing"
```

### 4.6 GET /nodes/{id}

```python
# services/gateway/routes/read.py
@router.get("/nodes/{node_id}")
async def get_node(
    node_id: int,
    storage: StorageManager = Depends(get_storage),
) -> Node:
    node = await storage.lance.load_node(node_id)
    if not node:
        raise HTTPException(404)
    return node
```

### 4.7 GET /hyperedges/{id}

```python
@router.get("/hyperedges/{edge_id}")
async def get_edge(
    edge_id: int,
    storage: StorageManager = Depends(get_storage),
) -> HyperEdge:
    edge = await storage.graph.get_hyperedge(edge_id)
    if not edge:
        raise HTTPException(404)
    return edge
```

### 4.8 GET /nodes/{id}/subgraph

```python
@router.get("/nodes/{node_id}/subgraph")
async def get_node_subgraph(
    node_id: int,
    hops: int = 1,
    edge_types: str | None = None,      # 逗号分隔: "abstraction,induction"
    storage: StorageManager = Depends(get_storage),
) -> SubgraphResponse:
    types = edge_types.split(",") if edge_types else None
    node_ids, edge_ids = await storage.graph.get_subgraph(
        [node_id], hops=hops, edge_types=types,
    )
    nodes = await storage.lance.load_nodes_bulk(list(node_ids))
    edges = [await storage.graph.get_hyperedge(eid) for eid in edge_ids]
    return SubgraphResponse(nodes=nodes, edges=edges)
```

```python
class SubgraphResponse(BaseModel):
    nodes: list[Node]
    edges: list[HyperEdge]
```

### 4.9 POST /search/nodes

```python
# services/gateway/routes/search.py
@router.post("/search/nodes")
async def search_nodes(
    request: SearchNodesRequest,
    search: SearchEngine = Depends(get_search_engine),
) -> list[ScoredNode]:
    return await search.search_nodes(
        query=request.query,
        embedding=request.embedding,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
```

```python
class SearchNodesRequest(BaseModel):
    query: str
    embedding: list[float]              # 1024d, 调用方自行计算
    k: int = 50
    filters: NodeFilters | None = None
    paths: list[str] | None = None      # ["vector", "bm25", "topology"]
```

### 4.10 POST /search/hyperedges

```python
@router.post("/search/hyperedges")
async def search_edges(
    request: SearchEdgesRequest,
    search: SearchEngine = Depends(get_search_engine),
) -> list[ScoredHyperEdge]:
    return await search.search_edges(
        query=request.query,
        embedding=request.embedding,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
```

```python
class SearchEdgesRequest(BaseModel):
    query: str
    embedding: list[float]
    k: int = 50
    filters: EdgeFilters | None = None
    paths: list[str] | None = None
```

---

## 5. 依赖注入

```python
# services/gateway/deps.py
from libs.storage import StorageManager, StorageConfig

_storage: StorageManager | None = None
_commit_engine: CommitEngine | None = None
_search_engine: SearchEngine | None = None

async def get_storage() -> StorageManager:
    return _storage

async def get_commit_engine() -> CommitEngine:
    return _commit_engine

async def get_search_engine() -> SearchEngine:
    return _search_engine
```

```python
# services/gateway/app.py
from fastapi import FastAPI

def create_app(config: StorageConfig) -> FastAPI:
    app = FastAPI(title="LKM API", version="1.0")

    @app.on_event("startup")
    async def startup():
        global _storage, _commit_engine, _search_engine
        _storage = StorageManager(config)
        _commit_engine = CommitEngine(_storage, llm_client)
        _search_engine = SearchEngine(_storage)

    @app.on_event("shutdown")
    async def shutdown():
        await _storage.close()

    app.include_router(commits.router, prefix="/commits", tags=["commits"])
    app.include_router(read.router, tags=["read"])
    app.include_router(search.router, prefix="/search", tags=["search"])

    return app
```

---

## 6. 接口总览

| 类别 | 端点 | 方法 | 转发到 |
|------|------|------|--------|
| **写入** | `/commits` | POST | CommitEngine.submit |
| | `/commits/{id}` | GET | CommitEngine.get_commit |
| | `/commits/{id}/review` | POST | CommitEngine.review |
| | `/commits/{id}/merge` | POST | CommitEngine.merge |
| | `/commits/batch` | POST | 批量处理 |
| **读取** | `/nodes/{id}` | GET | LanceStore.load_node |
| | `/hyperedges/{id}` | GET | Neo4jGraphStore.get_hyperedge |
| | `/nodes/{id}/subgraph` | GET | get_subgraph + load_nodes_bulk |
| **搜索** | `/search/nodes` | POST | SearchEngine.search_nodes |
| | `/search/hyperedges` | POST | SearchEngine.search_edges |

**总计 10 个端点。**
