# 本地存储

> **Status:** Current canonical

本文档描述 CLI 在本地开发和 `gaia publish --local` 中使用的嵌入式存储配置。服务器端存储架构参见 [dp-gaia](https://github.com/SiliconEinstein/dp-gaia) 仓库。

## 嵌入式后端

CLI 使用嵌入式（进程内）存储后端：

| 后端 | 实现 | 用途 |
|---------|---------------|---------|
| **LanceDB embedded** | `LanceContentStore`（使用本地路径） | 内容持久化、BM25 全文搜索 |
| **Kuzu embedded** | `KuzuGraphStore` | 图拓扑，用于遍历查询 |
| **LanceDB Vector** | `LanceVectorStore`（同一 LanceDB 连接） | 向量相似性搜索 |

LanceDB 和 Kuzu 均作为嵌入式数据库运行——无需单独的服务器进程。

## 配置

| 设置项 | 来源 | 默认值 |
|---------|--------|---------|
| `GAIA_LANCEDB_PATH` | 环境变量或 `--db-path` | `./data/lancedb/gaia` |
| `graph_backend` | `StorageConfig` | `"kuzu"`（嵌入式） |

LanceDB 路径控制所有内容、向量和 Kuzu 图数据的本地存储位置。

## `gaia publish --local` 三写入

本地发布时，CLI 通过 `StorageManager` 运行完整的三写入协议：

```
1. Write package with status="preparing"  (invisible to reads)
2. Write to ContentStore:  package, modules, knowledge, chains, factors
3. Write to GraphStore:    topology (knowledge -> chain relationships)
4. Write to VectorStore:   embeddings
5. Flip status to "merged"  (visible to reads)
```

失败时，数据保持 "preparing" 状态——对读取者不可见，可以安全重试。

## 通过 BM25 进行 `gaia search`

`gaia search` 查询本地 LanceDB 内容存储：

- **主要方式**：通过 LanceDB 内置 FTS 索引的 BM25 全文搜索。
- **回退方式**：针对 CJK/未分词文本的 SQL `LIKE` 过滤。
- **直接查找**：`--id <knowledge_id>` 获取特定知识项及其来自 `belief_history` 的最新置信值。

## 代码路径

| 组件 | 文件 |
|-----------|------|
| 存储配置 | `libs/storage/config.py:StorageConfig` |
| 存储管理器 | `libs/storage/manager.py:StorageManager` |
| 内容存储 | `libs/storage/lance_content_store.py:LanceContentStore` |
| 图存储（Kuzu） | `libs/storage/kuzu_graph_store.py:KuzuGraphStore` |
| 向量存储 | `libs/storage/lance_vector_store.py:LanceVectorStore` |
| CLI 发布命令 | `cli/main.py` |
| 管线发布 | `libs/pipeline.py:pipeline_publish()` |

## 当前状态

本地存储使用嵌入式 LanceDB 和 Kuzu 正常工作。`publish --local` 路径执行完整的三写入协议。BM25 搜索功能正常。图后端是可选的——系统可优雅降级为仅内容模式。
