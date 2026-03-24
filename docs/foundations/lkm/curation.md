# 策展引擎

> **Status:** Current canonical -- target evolution noted

策展引擎对全局知识图谱执行离线维护：去重节点、发现抽象、检测矛盾以及清理结构问题。它位于 `libs/curation/`，编排逻辑在 `scripts/pipeline/run_curation_db.py`。

## 6 步 Pipeline

策展 pipeline 作为批处理 pipeline 的第 6 阶段运行。它从数据库读取全局节点和 factor，通过六个步骤处理，然后将结果写回。

### 1. 聚类

`libs/curation/clustering.py` -- 使用 embedding 相似度（通过 `DPEmbeddingModel`）对相似节点进行分组。排除 schema 节点和已连接的节点对。阈值：0.85。

### 2. 去重

`libs/curation/dedup.py` -- 通过内容哈希识别完全重复。返回包含目标 ID 和证据的合并建议。

### 3. 抽象

`libs/curation/abstraction.py` -- 使用 LLM（`AbstractionAgent`）分析聚类并提出 schema（抽象）节点。创建新的 `kind: "schema"` GlobalCanonicalNode，并用 `instantiation` factor 将其与实例节点关联。还检测聚类中的矛盾候选。

### 4. 冲突检测

`libs/curation/conflict.py` -- 使用 BP 诊断的两级冲突检测：
- **第 1 级**（`detect_conflicts_level1`）：分析收敛诊断中的振荡和残差信号。
- **第 2 级**（`detect_conflicts_level2`）：对标记的节点执行扰动探测。

BP 诊断详情参见 [../bp/inference.md](../bp/inference.md)。

### 5. 结构审计

`libs/curation/structure.py` -- 检查全局图的结构问题：孤立节点、悬空 factor 引用、环路及其他异常。返回包含错误、警告和信息项的报告。

### 6. 清理

`libs/curation/cleanup.py` -- 根据所有建议和冲突候选生成清理计划，将其分类为自动批准、需要审查或丢弃。执行已批准的操作（合并、删除），并记录审计日志。

## 辅助模块

| 模块 | 用途 |
|------|------|
| `models.py` | 数据模型：`SimilarityCluster`、`MergeSuggestion`、`ConflictCandidate`、`CleanupPlan` |
| `similarity.py` | 两两相似度计算 |
| `operations.py` | 对节点/factor 图的合并和删除操作 |
| `audit.py` | `AuditLog`，用于追踪所有策展决策 |
| `reviewer.py` | 基于 LLM 的合并/抽象建议审查 |
| `scheduler.py` | `run_curation()` 入口点，从 `__init__.py` 导出 |
| `prompts/` | 用于抽象和审查的 LLM 提示模板 |

## 编排

`scripts/pipeline/run_curation_db.py` 是独立的编排器：

1. 通过 StorageManager 连接存储（LanceDB + 可选的 graph 后端）
2. 加载所有 GlobalCanonicalNode 和 factor
3. 顺序运行 6 个步骤，累积建议和冲突候选
4. 计算差异（增加/移除的节点和 factor）
5. 写回结果：删除移除的节点/factor，upsert 剩余/新增的节点
6. 保存 JSON 报告，包含每步的耗时、计数和详情

CLI 参数：`--db-path`、`--graph-backend`、`--report-path`、`--llm-model`。

## 代码路径

| 组件 | 文件 |
|------|------|
| 聚类 | `libs/curation/clustering.py` |
| 去重 | `libs/curation/dedup.py` |
| 抽象 agent | `libs/curation/abstraction.py` |
| 冲突检测 | `libs/curation/conflict.py` |
| 结构审计 | `libs/curation/structure.py` |
| 清理执行 | `libs/curation/cleanup.py` |
| 数据库编排器 | `scripts/pipeline/run_curation_db.py` |
| Embedding 模型 | `libs/embedding.py:DPEmbeddingModel` |

## 当前状态

作为数据库原生批处理脚本运行。抽象步骤使用真实 LLM 调用（通过 litellm），聚类使用真实 embedding。已在约 5 篇论文的图上测试。策展结果写回存储。

## 目标状态

- 将编排迁移到服务端 CurationService，作为包摄入后的定时后台任务运行。
- 添加增量策展（仅处理新摄入的包，而非整个图）。
- 通过 API 暴露策展报告，供前端可视化。
