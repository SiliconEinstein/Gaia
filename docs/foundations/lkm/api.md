# API

> **Status:** Current canonical

本文档描述 Gaia 网关服务（`services/gateway/`）暴露的 HTTP API。这是内部网关 API，不是正式的公开契约。所有端点均可能变更。

## 服务器

网关是一个 FastAPI 应用。路由定义在 `services/gateway/routes/packages.py` 中。依赖注入通过 `services/gateway/deps.py` 中的全局 `Dependencies` 单例管理，在启动时用 `StorageManager` 初始化。

## 端点

### 包摄取

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `POST` | `/packages/ingest` | 摄取完整的包（package + modules + knowledge + chains + probabilities + beliefs + embeddings） | Stable |

请求体（IngestRequest）：
```json
{
  "package": { ... },
  "modules": [ ... ],
  "knowledge": [ ... ],
  "chains": [ ... ],
  "probabilities": [],
  "beliefs": [],
  "embeddings": []
}
```

响应（IngestResponse）：`{ package_id, status, knowledge_count, chain_count }`。

摄取端点执行三写入原子性操作：Content store（数据源）、Graph store（拓扑）和 Vector store（embeddings）。

### 包读取

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `GET` | `/packages` | 列出所有包（分页） | Stable |
| `GET` | `/packages/{package_id}` | 获取单个包 | Stable |

### Knowledge 读取

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `GET` | `/knowledge` | 列出 knowledge 条目（分页，可选 `type_filter`） | Stable |
| `GET` | `/knowledge/{knowledge_id}` | 获取单个 knowledge 条目 | Stable |
| `GET` | `/knowledge/{knowledge_id}/versions` | 获取某个 knowledge 条目的所有版本 | Stable |
| `GET` | `/knowledge/{knowledge_id}/beliefs` | 获取某个 knowledge 条目的信念历史 | Stable |

### Module 读取

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `GET` | `/modules` | 列出所有模块（可选 `package_id` 过滤） | Stable |
| `GET` | `/modules/{module_id}` | 获取单个模块 | Stable |
| `GET` | `/modules/{module_id}/chains` | 获取模块的 chain | Stable |

### Chain 读取

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `GET` | `/chains` | 列出 chain（分页，可选 `module_id` 过滤） | Stable |
| `GET` | `/chains/{chain_id}` | 获取单个 chain | Stable |
| `GET` | `/chains/{chain_id}/probabilities` | 获取 chain 的概率历史 | Stable |

### 图

| Method | Path | 描述 | 状态 |
|---|---|---|---|
| `GET` | `/graph` | 获取 knowledge 节点和 chain 边，用于 DAG 可视化（可选 `package_id` 过滤） | Stable |

## 认证

未实现认证。网关仅供内部/开发使用。

## 错误处理

- `404` -- 资源未找到（package、knowledge、module、chain）。
- `503` -- 存储未初始化（启动失败或缺少配置）。

## 尚未实现

以下功能在目标服务器架构（`docs/archive/foundations-v2/server/architecture.md`）中有描述，但尚未作为 HTTP 端点暴露：

- **搜索 API**（`QueryService`）-- 面向 agent 的全文和向量搜索。实验性。
- **Review 提交** -- 同行评审引擎集成。目标架构。
- **全局 BP 触发** -- 运行全局 BP。目标架构。
- **策展端点** -- 聚类、冲突发现、图维护。目标架构。

## 源码

- `services/gateway/routes/packages.py` -- 路由定义
- `services/gateway/deps.py` -- 依赖注入
- `services/gateway/app.py` -- FastAPI 应用工厂
