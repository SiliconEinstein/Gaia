# API

> **Status:** Target design

本文档描述 LKM 的目标 HTTP API 设计。基于 Local / Global 对偶 FactorGraph 架构，使用 variable / factor 术语。

## 服务器

FastAPI 应用。依赖注入通过 `StorageManager` 单例管理，在启动时初始化。

## 端点

### Ingest

| Method | Path | 描述 |
|---|---|---|
| `POST` | `/packages/ingest` | 触发 Pipeline A（接收 Gaia IR package），执行 lower → integrate 全流程 |

请求体：Gaia IR package（`LocalCanonicalGraph` + validated review reports）。

响应：`{ package_id, status, variable_count, factor_count }`。

摄取端点按 [写入协议](02-storage.md) 执行：local FactorGraph → CanonicalBinding → global FactorGraph → 参数化层 → graph store → vector store。

### Variables

| Method | Path | 描述 |
|---|---|---|
| `GET` | `/variables` | 列出 variable nodes（分页 + BM25 搜索） |
| `GET` | `/variables/{id}` | 查询单个 variable node |

`GET /variables/{id}` 返回 global variable node 信息。content 通过 `representative_lcn` join `local_variable_nodes` 获取。

查询参数：
- `q`：BM25 全文搜索（匹配 local variable 的 content）
- `type`：按 type 过滤（`claim` / `setting` / `question`）
- `visibility`：按 visibility 过滤（默认仅 `public`）
- `limit` / `offset`：分页

### Factors

| Method | Path | 描述 |
|---|---|---|
| `GET` | `/factors/{id}` | 查询单个 factor node |

返回 global factor node 信息。steps 通过 local factor lookup 获取。

### Graph

| Method | Path | 描述 |
|---|---|---|
| `GET` | `/graph/subgraph` | N 跳子图查询 |

查询参数：
- `node_id`：起始 gcn_id
- `hops`：跳数（默认 1）
- `direction`：`upstream` / `downstream` / `both`

返回子图内的 variable nodes + factor nodes + edges。

### Beliefs

| Method | Path | 描述 |
|---|---|---|
| `GET` | `/beliefs/snapshots` | BeliefSnapshot 列表 |
| `GET` | `/beliefs/snapshots/{snapshot_id}` | 单个 BeliefSnapshot |
| `GET` | `/beliefs/variables/{id}` | 某个 variable 的 belief 历史 |

### Admin

| Method | Path | 描述 |
|---|---|---|
| `POST` | `/curation/run` | 手动触发 curation discovery |
| `POST` | `/bp/run` | 手动触发 global BP |

## 认证

未实现认证。仅供内部/开发使用。

## 错误处理

- `404` -- 资源未找到（variable、factor、snapshot）。
- `503` -- 存储未初始化（启动失败或缺少配置）。
