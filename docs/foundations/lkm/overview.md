# LKM 概述

> **Status:** Current canonical

Large Knowledge Model (LKM) 是一个计算注册中心——不仅仅是存储，而是一个主动验证、规范化、审查、集成、策展和推断全局知识图谱的系统。**LKM 从不接触 Gaia Lang——它完全在 Gaia IR 上运作。**

## 架构

LKM 有两个方面：

### 写入端（包生命周期）

当一个包被发布时，它进入服务端生命周期：

```
validate  ->  canonicalize  ->  review  ->  [rebuttal]  ->  integrate  ->  curate  ->  global BP
```

每个阶段在各自的文档中有详细说明：
- [review-pipeline.md](review-pipeline.md) -- 同行评审与概率赋值
- [global-canonicalization.md](global-canonicalization.md) -- 本地到全局的节点映射
- [curation.md](curation.md) -- 离线图维护
- [global-inference.md](global-inference.md) -- 服务端 belief propagation
- [pipeline.md](pipeline.md) -- 批量编排
- [lifecycle.md](lifecycle.md) -- 完整的逐阶段分解

### 读取端（查询服务）

LKM 通过 HTTP API 端点暴露已发布的知识：

- 包和模块浏览
- 带版本历史的知识条目检索
- 推理链和概率历史
- 用于 DAG 可视化的图拓扑
- BM25 全文搜索（计划中：向量相似性搜索）

端点详情见 [api.md](api.md)。

## 实现

LKM 实现为 FastAPI 网关（`services/gateway/`）：

- **应用工厂**：`services/gateway/app.py` 导出 `create_app(dependencies=None)`。
- **依赖注入**：`services/gateway/deps.py` 持有一个 `Dependencies` 类，包含 StorageManager 单例。测试通过 `create_app(dependencies=...)` 注入自定义依赖。
- **启动**：加载 `.env`，从 `StorageConfig` 初始化 StorageManager，连接 content/graph/vector 存储。
- **CORS**：允许 `localhost:5173` 用于前端开发服务器。

运行方式：

```bash
GAIA_LANCEDB_PATH=./data/lancedb/gaia \
  uvicorn services.gateway.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

## 分层架构

```
Entry Points
  Server  (services/gateway/)    -- FastAPI HTTP API
  Pipeline scripts  (scripts/)   -- batch orchestration

         | call

Engines
  Canonicalization  (libs/global_graph/) -- local -> global node mapping
  Review Pipeline  (services/review_pipeline/) -- review scoring
  Curation  (services/curation/)         -- offline graph maintenance
  BP Engine  (libs/inference/)           -- sum-product loopy BP

         | use

Storage
  LanceDB  (libs/storage/lance_content_store.py)  -- content + FTS + metadata
  Neo4j/Kuzu  (libs/storage/)  -- graph topology
  LanceDB Vector  (libs/storage/lance_vector_store.py)  -- embedding similarity
```

依赖严格向下流动。`libs/` 没有服务层依赖。CLI 和服务端是共享同一 `libs/` 层的独立产品表面。

## 端到端数据流（服务端）

```
5. Global Canonicalization
   libs/global_graph/canonicalize.py  ->  map local nodes to global nodes
       |  produces CanonicalBindings + GlobalCanonicalNodes + global factors
6. Persist (StorageManager three-write)
   libs/storage/manager.py  ->  content -> graph -> vector
       |
7. Curation (offline)
   services/curation/  ->  similarity clustering, contradiction discovery
       |
8. Global BP (server)
   Same libs/inference/ engine on the global canonical graph
```

步骤 1-4（编写、构建、本地 BP）在本地通过 CLI 完成。参见 [../cli/lifecycle.md](../cli/lifecycle.md)。

## 关键设计决策

- **Gaia IR 作为接口边界。** LKM 接收 Gaia IR（原始图、本地规范图）——从不接收 Typst 源码。这将编写 DSL 与注册中心解耦。
- **结构与参数分离。** Gaia IR 存储结构关系。先验、信念和 factor 参数存储在 GlobalInferenceState 中。参见 [../gaia-ir/parameterization.md](../gaia-ir/parameterization.md)。
- **三次写入原子性。** 包摄入写入 content（真实来源）、graph（拓扑）和 vector（embedding），带可见性门控。参见 [storage.md](storage.md)。
- **优雅降级。** Graph 和 vector 存储是可选的。系统仅凭 content 存储即可运行。

## 代码路径

| 组件 | 文件 |
|------|------|
| App factory | `services/gateway/app.py` |
| Dependencies | `services/gateway/deps.py` |
| Routes | `services/gateway/routes/packages.py` |
| Storage manager | `libs/storage/manager.py` |
| Storage config | `libs/storage/config.py` |
| Global canonicalization | `libs/global_graph/canonicalize.py` |
| BP engine | `libs/inference/bp.py` |

## 当前状态

服务端是一个以读为主的 API，拥有单个批量写入端点（`/packages/ingest`）。`localhost:5173` 上的前端消费这些端点用于 DAG 可视化和知识浏览。服务端的审查、策展和全局 BP 可通过 pipeline 脚本使用，但尚未作为 HTTP 触发的服务。

## 目标状态

- **写入端**：添加服务端 ReviewService（摄入时进行 LLM 审查）和 CurationService（后台图维护）。
- **读取端**：将读取路由拆分为独立的 router 以便独立扩展。
- 将 `gaia publish --server` 连接到 `POST /packages/ingest`。
