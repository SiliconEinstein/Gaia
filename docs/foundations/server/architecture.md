# Gaia Server Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-09 |
| 状态 | **Draft — 目标架构设计，非当前实现描述** |
| 关联文档 | [../product-scope.md](../product-scope.md), [../domain-model.md](../domain-model.md), [../system-overview.md](../system-overview.md) |

> **注意：** 本文档定义的是 server 端的**目标架构**，用于指导后续重构。当前 `main` 上的 server 仍然使用 `/commits/*`、`/jobs/*` 等旧 API，基于 Node/HyperEdge 模型。本文档中的 API 路由（`/packages`、`/bp/*` 等）和数据模型（closure/chain/module/package）是重构后的目标状态。

---

## 1. Server 定位

Gaia 是 CLI-first, Server-enhanced。Server 是一个可选的 **registry 和计算后端**，类似 Julia General Registry / crates.io。

Server 提供四个增强服务：

| 服务 | 说明 |
|------|------|
| Knowledge integration | 把 packages 合并到全局 LKM |
| Global search | 跨 package 的 vector + BM25 + topology 搜索 |
| LLM Review Engine | 自动审查推理链质量 |
| Large-scale BP | 全局图上的信念传播 |

Server **不修改 package**——它是 package 的只读消费者。

---

## 2. 总体架构

三层分层架构：Transport → Domain Services → Storage。

```
┌─────────────────────────────────────────────────────┐
│  Transport Layer                                     │
│  ┌──────────────┐  ┌──────────────────┐              │
│  │ HTTP Routes   │  │ Webhook Handler  │              │
│  │ (FastAPI)     │  │ (GitHub events)  │              │
│  └──────┬───────┘  └────────┬─────────┘              │
│         └────────┬──────────┘                        │
│                  ▼                                    │
│         PackageRequest (统一表示)                      │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Domain Services Layer                               │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │ IngestionService                             │     │
│  │                                              │     │
│  │ submit(pkg) → validate → review → integrate  │     │
│  │                                              │     │
│  │ 拥有 package 生命周期状态机                    │     │
│  │ 内部组合 Validator + ReviewEngine + Integrator│     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                  │
│  │ BPService     │  │ QueryService │                  │
│  │               │  │              │                  │
│  │ run_global()  │  │ search()     │                  │
│  │ run_subgraph()│  │ read_node()  │                  │
│  │               │  │ read_edge()  │                  │
│  └──────────────┘  │ subgraph()   │                  │
│                     └──────────────┘                  │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Storage Layer                                       │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │ StorageManager                            │        │
│  │                                           │        │
│  │ 统一读写接口，封装三个后端的协调           │        │
│  └──────────────────────────────────────────┘        │
│       │            │            │                     │
│  ┌────▼───┐  ┌─────▼────┐  ┌───▼────────┐           │
│  │ Neo4j   │  │ LanceDB   │  │ VectorStore│           │
│  │ (graph) │  │ (content) │  │ (embed)    │           │
│  └────────┘  └──────────┘  └────────────┘           │
└─────────────────────────────────────────────────────┘
```

依赖方向严格向下：Transport → Domain → Storage。每层只依赖下一层。

---

## 3. Storage Layer

### 3.1 设计原则

StorageManager 是所有存储操作的**唯一门面**。Domain services 不直接接触 Neo4j / LanceDB / VectorStore。

### 3.2 数据归属

每个后端是特定数据的 source of truth，不是彼此的副本：

| 后端 | Source of truth for | 提供的查询能力 |
|------|-------------------|---------------|
| **Neo4j** | 图拓扑（节点间的超边关系、tail/head 连接） | 邻居遍历、子图提取、边类型过滤 |
| **LanceDB** | 节点/边的内容与元数据（content, prior, keywords, reasoning...） | BM25 全文搜索、元数据过滤、按 ID 读取 |
| **VectorStore** | Embedding 向量 | top-k 相似度搜索 |

### 3.3 StorageManager 接口

```python
class StorageManager:
    # ── 写入（package 入库，三写由此层保证一致性）──
    async def ingest_package(self, package: PackageData) -> IngestResult

    # ── 单实体读取 ──
    async def get_node(self, node_id: str) -> Node | None
    async def get_edge(self, edge_id: str) -> HyperEdge | None

    # ── 图查询（委托 Neo4j）──
    async def get_neighbors(self, node_id: str, direction: str,
                            edge_types: list[str] | None,
                            max_hops: int) -> Subgraph
    async def get_subgraph(self, node_id: str, max_nodes: int) -> Subgraph

    # ── 搜索查询（各后端独立）──
    async def search_vector(self, embedding: list[float], top_k: int) -> list[ScoredNode]
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredNode]
    async def search_topology(self, seed_ids: list[str], hops: int) -> list[ScoredNode]
```

### 3.4 三写一致性与降级模式

Package 入库是 server 唯一的写入路径。不存在单独写某个后端的场景。

写入行为取决于后端在 **提交时** 的可用状态：

**后端在提交前已知不可用（降级模式）：**

| 状态 | 行为 |
|------|------|
| Neo4j 不可用 | 入库只写 LanceDB + Vector，图查询返回空，拓扑搜索跳过 |
| VectorStore 不可用 | 入库只写 LanceDB + Neo4j，向量搜索跳过 |
| LanceDB 不可用 | **系统不可用**（核心 source of truth） |

**后端在写入过程中失败（mid-flight failure → 回滚）：**

```
ingest_package(pkg):
    1. LanceDB.write(nodes, edges)     ← 内容先落盘（source of truth）
    2. Neo4j.write(topology)           ← 图拓扑
    3. VectorStore.write(embeddings)   ← 向量索引

    Mid-flight 失败策略：
    - 步骤 2 失败 → 删除步骤 1 写入的记录，返回错误
    - 步骤 3 失败 → 删除步骤 1、2 写入的记录，返回错误
```

关键区别：降级模式是**启动时已知**的能力缺失，允许部分写入；mid-flight failure 是**运行时意外**，必须回滚以保证一致性。

---

## 4. Domain Services Layer

### 4.1 IngestionService

管理 package 从提交到入库的完整生命周期。

#### 状态机

```
submitted → validating → validated → reviewing → reviewed
                ↓                                    ↓
             invalid                          ┌─────┴─────┐
             (rejected)                   approved     rejected
                                             ↓
                                        integrating
                                             ↓
                                          merged
```

#### 接口

```python
class IngestionService:
    def __init__(self, validator: Validator,
                 review_engine: ReviewEngine,
                 storage: StorageManager):
        ...

    async def submit(self, request: PackageRequest) -> SubmissionResult
    async def get_status(self, submission_id: str) -> SubmissionStatus
```

`submit()` 是异步的——立即返回 `submission_id`，客户端通过 `get_status()` 轮询进度。这适配 webhook 场景（GitHub 期望快速响应），direct publish 也用同样模式保持一致。

#### 内部组件

| 组件 | 职责 | 输入 → 输出 |
|------|------|------------|
| **Validator** | schema 校验、引用完整性、prior 范围检查、边类型约束 | PackageData → ValidationResult |
| **ReviewEngine** | LLM 审查推理链质量 | PackageData → ReviewReport |
| **Integrator** | 把 package 映射到全局图结构，调用 StorageManager 写入 | PackageData → IngestResult |

#### Validator 职责

1. Schema 合法性（package.yaml + module YAML 结构）
2. 引用完整性（chain 中的 premise 引用都指向存在的 declaration）
3. Prior ∈ (0, 1)（Cromwell 规则，setting type 允许 1.0）
4. 边类型约束（induction 的 probability 必须 < 1.0）
5. Export 的 closure_id 存在于某个 module 中

#### ReviewEngine 职责

对每个 module 的每条 chain：

1. 推理步骤是否逻辑连贯
2. 结论是否被前提支持
3. 推理类型是否正确标注（deduction vs induction vs abstraction）
4. 输出 per-chain 评分 + 总体 accept/reject 建议

### 4.2 BPService

```python
class BPService:
    def __init__(self, storage: StorageManager):
        ...

    async def run_global(self) -> BPResult
    async def run_subgraph(self, node_ids: list[str]) -> BPResult
    async def schedule_update(self) -> None
```

- 复用 `libs/inference/` 的 CPU 实现（FactorGraph + BeliefPropagation）
- `run_global()` 从 storage 加载全局图，运行 BP，把更新后的 beliefs 写回 storage
- `schedule_update()` 由 IngestionService 在入库完成后异步调用，支持 debounce（多个 package 短时间内入库只跑一次 BP）

### 4.3 QueryService

```python
class QueryService:
    def __init__(self, storage: StorageManager):
        ...

    async def get_node(self, node_id: str) -> Node | None
    async def get_edge(self, edge_id: str) -> HyperEdge | None
    async def get_subgraph(self, node_id: str, direction: str,
                           max_nodes: int) -> Subgraph
    async def search(self, text: str, top_k: int) -> list[ScoredNode]
```

`search()` 内部执行三路并行召回 + 归一化 + 加权融合 + 去重 + top-k 过滤。

搜索的具体策略（权重、召回路径）在后续设计中细化，当前优先级较低。

---

## 5. Transport Layer

### 5.1 统一请求表示

两条路径（HTTP direct / GitHub webhook）最终都构造同一个 `PackageRequest`：

```python
@dataclass
class PackageRequest:
    source: Literal["webhook", "direct"]
    package_files: dict[str, str]   # filename → YAML content
    metadata: RequestMetadata

@dataclass
class RequestMetadata:
    submitter: str
    submitted_at: datetime
    # webhook 专有
    repo_url: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
```

### 5.2 HTTP Routes

```
POST   /packages              # direct publish
GET    /packages/{id}/status   # 查询提交状态

GET    /nodes/{id}
GET    /edges/{id}
GET    /nodes/{id}/subgraph

POST   /search

POST   /bp/run                 # 手动触发全局 BP
GET    /bp/status
```

路由实现只做 transport 转换，不含业务逻辑：

```python
@router.post("/packages")
async def submit_package(files: UploadFiles, deps: Deps):
    request = PackageRequest(
        source="direct",
        package_files=parse_uploads(files),
        metadata=RequestMetadata(submitter=current_user(), ...)
    )
    result = await deps.ingestion.submit(request)
    return result
```

### 5.3 Webhook Handler

```python
@router.post("/webhooks/github")
async def github_webhook(request: Request, deps: Deps):
    event = verify_and_parse(request)  # 验证 webhook secret

    if event.action not in ("opened", "synchronize"):
        return {"status": "ignored"}

    package_files = await fetch_package_from_pr(event)

    request = PackageRequest(
        source="webhook",
        package_files=package_files,
        metadata=RequestMetadata(
            submitter=event.sender,
            repo_url=event.repo_url,
            pr_number=event.pr_number,
            commit_sha=event.head_sha,
        )
    )

    submission = await deps.ingestion.submit(request)

    # 立即回复 GitHub 一个 pending comment
    await post_pending_comment(event, submission.id)
```

`submit()` 立即返回 `submission_id`（非阻塞）。Review 完成后通过回调投递结果：

```python
# IngestionService 内部，review 完成时的回调
async def _on_review_complete(self, submission_id: str, result: ReviewResult):
    ...
    await self._result_adapter.deliver(submission_id, result)
```

```python
# ResultAdapter 根据来源投递结果
class ResultAdapter:
    async def deliver(self, submission_id: str, result: SubmissionResult):
        request = self._get_request(submission_id)
        if request.source == "webhook":
            await self.github.post_pr_comment(
                repo=request.metadata.repo_url,
                pr=request.metadata.pr_number,
                body=format_review_comment(result),
            )
        # direct publish: 客户端通过 GET /packages/{id}/status 轮询
```

### 5.4 结果投递流程

| 路径 | 提交响应 | 结果投递 |
|------|---------|---------|
| Direct (HTTP) | 立即返回 `submission_id` | 客户端轮询 `GET /packages/{id}/status` |
| Webhook | 立即回复 GitHub 200 + pending comment | Review 完成后回调写 PR comment |

### 5.5 Application Bootstrap

系统组装从 gateway 中剥离，独立为 bootstrap 模块：

```python
# server/bootstrap.py
def create_dependencies() -> Dependencies:
    # Storage
    neo4j = Neo4jClient(settings.neo4j_url)
    lance = LanceDB(settings.lancedb_path)
    vector = VectorStore(settings.vector_config)
    storage = StorageManager(neo4j, lance, vector)

    # Domain Services
    validator = Validator()
    review_engine = ReviewEngine(llm_client=create_llm_client())
    ingestion = IngestionService(validator, review_engine, storage)
    bp = BPService(storage)
    query = QueryService(storage)

    return Dependencies(ingestion, bp, query)

# server/app.py
def create_app() -> FastAPI:
    app = FastAPI()
    deps = create_dependencies()
    app.include_router(package_routes(deps))
    app.include_router(query_routes(deps))
    app.include_router(webhook_routes(deps))
    return app
```

---

## 6. 模块优先级

| 模块 | 优先级 | 说明 |
|------|--------|------|
| Storage Layer | 高 | 一切的基础 |
| IngestionService (Validator + ReviewEngine + Integrator) | 高 | 核心写入路径 |
| QueryService (读取 + 搜索) | 中 | 搜索策略后续细化 |
| BPService | 中 | 先复用 libs/inference/ CPU 实现 |
| Transport Layer | 高 | HTTP routes + webhook handler |

---

## 7. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 架构风格 | 分层服务 | 契合 registry 本质，规模适当，不需要 event bus 或微服务复杂性 |
| 存储选型 | Neo4j + LanceDB + VectorStore（不变） | 现有选型满足需求 |
| 三写一致性 | LanceDB 优先写入，失败回滚 | LanceDB 是 source of truth |
| submit 模式 | 异步（返回 id + 轮询） | 适配 webhook 快速响应需求 |
| webhook + direct 统一 | 共享 PackageRequest + IngestionService | 底层完全一致，只有 transport 差异 |
| BP | 复用 libs/inference/ CPU 实现 | 现阶段够用，GPU 加速后续再做 |
| 搜索 | 后续细化 | 架构预留三路召回接口，策略优先级低 |
| 系统组装 | 独立 bootstrap 模块 | 解决 deps.py 做太多事的问题 |

---

## 8. 与 Foundation Reset Plan 的关系

本文档是目标架构设计，为 foundation-reset-plan 中以下阶段提供方向：

- Phase 4 (storage-schema): §3 给出了存储层职责和接口的目标设计，详细 schema 见 `server/storage-schema.md`
- Phase 5 (module-boundaries): §2-5 给出了模块划分和依赖方向的目标设计
- Phase 6 (api-contract): §5.2 给出了目标 API 路由（非当前 API 描述）

以下仍需独立完成：

- Phase 3 (graph-spec): 图的形式化定义（节点/超边字段、遍历语义）
- 搜索策略详细设计
- GPU BP 架构设计
