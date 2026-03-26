# 服务端存储

> **Status:** Current canonical

本文档描述服务端存储架构。关于 CLI 使用的本地（嵌入式）存储，参见 [../cli/local-storage.md](../cli/local-storage.md)。

## 三后端架构

存储层使用三个互补的后端，均由 `StorageManager`（`libs/storage/manager.py`）管理：

| 后端 | 类 | 用途 | 是否必需？ |
|---------|-------|---------|-----------|
| **LanceDB Content** | `LanceContentStore` | 所有实体持久化，BM25 全文搜索 | 是（数据源） |
| **Neo4j / Kuzu Graph** | `Neo4jGraphStore` / `KuzuGraphStore` | 图拓扑，用于遍历查询 | 可选 |
| **LanceDB Vector** | `LanceVectorStore` | Embedding 相似度搜索 | 可选 |

Content store 始终必需，作为数据源。Graph store 和 Vector store 是可选的——系统在缺少它们时优雅降级。

### 后端选择

通过 `StorageConfig`（`libs/storage/config.py`）配置：

- **LanceDB**：本地路径或远程 S3/TOS URI。远程模式使用 `storage_options` 配合 TOS 访问密钥。
- **Graph 后端**：`"kuzu"`（嵌入式，本地默认）、`"neo4j"`（服务端）或 `"none"`。
- **Vector store**：始终与 Content store 一起创建（相同 LanceDB 连接，独立表）。

## StorageManager

`StorageManager` 是统一门面。领域服务仅与此类交互，不直接访问各个 store。

核心职责：

- **初始化**：实例化并连接所有已配置的 store。
- **三写入原子性**：协调多 store 写入，带有可见性门控。
- **读取委派**：将读取请求传递给相应的 store，对图查询进行可见性过滤。
- **优雅降级**：当可选 store 不可用时返回空结果。

## 三写入原子性

参见 `libs/storage/manager.py:StorageManager.ingest_package()`。

包摄取遵循五步协议：

```
1. Write package with status="preparing"  (invisible to reads)
2. Write to ContentStore:  package, modules, knowledge, chains, factors, submission_artifact
3. Write to GraphStore:    topology (knowledge -> chain relationships), factor topology
4. Write to VectorStore:   embeddings
5. Flip status to "merged"  (visible to reads)
```

失败时，数据保持 "preparing" 状态——对读取者不可见，可安全重试。Content store 始终最先写入，作为数据源。

## LanceDB 表 Schema

所有表在 `libs/storage/lance_content_store.py` 中以 PyArrow schema 定义：

### 核心实体表

| 表 | 键 | 用途 |
|-------|-----|---------|
| `packages` | `(package_id, version)` | 包元数据、状态、模块列表 |
| `modules` | `module_id` | 模块元数据、chain_ids、export_ids |
| `knowledge` | `(knowledge_id, version)` | 带版本的命题，包含 type、content、prior、keywords |
| `chains` | `chain_id` | 推理链，包含带类型的 steps（premises -> conclusion） |

### 推理表

| 表 | 键 | 用途 |
|-------|-----|---------|
| `probabilities` | `(chain_id, step_index)` | 来自各来源的步骤可靠性分数 |
| `belief_history` | `(knowledge_id, version, bp_run_id)` | BP 结果的历史快照 |

### Gaia IR 表

| 表 | 键 | 用途 |
|-------|-----|---------|
| `factors` | `factor_id` | Gaia IR 编译产生的持久化 factor |
| `canonical_bindings` | `(package, version, local_canonical_id)` | 本地到全局节点的映射 |
| `global_canonical_nodes` | `global_canonical_id` | 跨包去重的知识标识 |
| `global_inference_state` | singleton `_id` | 注册表管理的全局 BP 状态（先验、信念、factor 参数） |

### 资源表

| 表 | 键 | 用途 |
|-------|-----|---------|
| `resources` | `resource_id` | 资源元数据（图片、代码、数据集） |
| `resource_attachments` | `(resource_id, target_id)` | 到 knowledge/chains/modules 的多对多链接 |
| `submission_artifacts` | `(package_name, commit_hash)` | 不可变快照，用于审计 |

## Graph Store 拓扑

Graph store（Neo4j 或 Kuzu）维护用于遍历查询的拓扑：

- Knowledge 节点以复合键 `knowledge_id@version` 标识
- 来自 chain 的 `:PREMISE` 和 `:CONCLUSION` 关系
- Factor 拓扑链接
- GlobalCanonicalNode 拓扑和绑定

Graph store 始终从属于 Content store。它在三写入协议中被填充，可从 Content store 数据重建。

## 服务端 vs 本地存储

| 方面 | 服务端 | 本地（CLI） |
|--------|--------|-------------|
| **LanceDB** | 远程 S3/TOS URI 或本地路径 | 本地路径（`GAIA_LANCEDB_PATH`） |
| **Graph 后端** | Neo4j（生产）或 Kuzu | Kuzu（嵌入式） |
| **Vector store** | 启用 | 启用 |
| **访问方式** | 通过 FastAPI 网关 | 直接通过 `StorageManager` |
| **并发** | 多读单写 | 单用户 |

## 代码路径

| 组件 | 文件 |
|-----------|------|
| 存储管理器 | `libs/storage/manager.py:StorageManager` |
| 存储配置 | `libs/storage/config.py:StorageConfig` |
| Content store | `libs/storage/lance_content_store.py:LanceContentStore` |
| Graph store (Neo4j) | `libs/storage/neo4j_graph_store.py:Neo4jGraphStore` |
| Graph store (Kuzu) | `libs/storage/kuzu_graph_store.py:KuzuGraphStore` |
| Vector store | `libs/storage/lance_vector_store.py:LanceVectorStore` |
| 数据模型 | `libs/storage/models.py` |

## 当前状态

存储层已在生产环境中运行，使用远程 LanceDB（S3/TOS）和 Neo4j。本地开发使用嵌入式 LanceDB，可选使用 Kuzu。BM25 全文搜索通过 LanceDB 内置的 FTS 索引提供。三写入协议在 CLI 发布路径和服务端摄取流水线中均被使用。

## 目标状态

存储层已稳定，无计划中的重大 schema 变更。`global_inference_state` 表最近新增，随着推理流水线成熟可能会有少量字段增补。
