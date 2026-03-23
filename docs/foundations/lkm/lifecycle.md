# LKM 生命周期

> **Status:** Current canonical

本文档描述包发布后的服务端生命周期。关于本地 CLI 生命周期（从 init 到 publish），参见 [../cli/lifecycle.md](../cli/lifecycle.md)。

## 概述

包通过 `gaia publish` 发布后，LKM 生命周期接管：

```
validate  ->  canonicalize  ->  review  ->  [rebuttal cycle]  ->  integrate  ->  curate  ->  global BP
```

## 各阶段

### 验证（Validate）

Review 引擎从提交的源码重新编译 raw graph。与提交的 `raw_graph.json` 的任何不一致都是阻断性发现。

- **输入**：提交的包源码 + 提交的 `raw_graph.json`。
- **输出**：通过/失败。不一致时提交被拒绝。
- **作用**：确定性重编译，用于完整性验证。

### 规范化（Canonicalize，全局）

规范化引擎将每个 `LocalCanonicalNode` 映射到 `GlobalCanonicalNode`：

- **输入**：`LocalCanonicalGraph` + 当前全局图。
- **输出**：`CanonicalBinding` 记录 + 新建/更新的 `GlobalCanonicalNode`。
- **作用**：对每个本地节点进行 embedding，在全局图中搜索匹配项。对每个本地节点：匹配到现有全局节点或创建新节点。

详见 [global-canonicalization.md](global-canonicalization.md)。

### 评审（Review）

独立的同行评审评估推理质量、重复检测、缺失引用和冲突识别。

- **输入**：包源码 + raw graph + local canonical graph。
- **输出**：`ReviewOutput`，包含 `node_priors`、`factor_params` 和逐 chain 评估。
- **作用**：产生概率判断，用于 BP 参数化。

详见 [review-pipeline.md](review-pipeline.md)。

### 反驳周期（Rebuttal Cycle）

如果存在阻断性发现，作者可以接受修订或撰写反驳。该周期最多重复 5 轮。5 轮后仍未解决则升级为人工评审（`under_debate`）。

> **远期目标**：完整的 review -> rebuttal -> editor 周期是目标架构。当前实现在发布时使用简化的自动规范化。

### 集成（Integrate）

已批准的包被合并到全局图中：

- **输入**：`CanonicalBinding` 记录 + `ReviewOutput` + 全局 factor。
- **输出**：更新的全局图，刷新的 `GlobalInferenceState`。
- **作用**：最终确定绑定，创建/更新 `GlobalCanonicalNode` 条目，写入全局 `FactorNode` 记录（将 premises/conclusion 重映射到 `global_canonical_id`），从 review 输出刷新推理状态，将包标记为 `merged`。

### 策展（Curate）

由策展引擎执行的离线图维护：

- 相似度聚类（发现近似重复的全局节点）
- 去重（合并完全重复项）
- 抽象发现（提议 schema 节点）
- 矛盾发现（检测跨包冲突）
- 结构审计（图健康检查）
- 清理（执行已批准的合并/删除操作）

详见 [curation.md](curation.md)，了解完整的 6 步流水线。

### 全局 BP（Global BP）

BP 引擎在全局规范图上运行 sum-product BP，使用注册表管理的 `GlobalInferenceState`。与本地 BP 算法相同，但范围和参数化来源不同。

- **输入**：全局规范图 + `GlobalInferenceState`。
- **输出**：更新的 `GlobalInferenceState.node_beliefs` + `BeliefSnapshot` 历史。
- **触发**：在集成或策展完成后。

详见 [global-inference.md](global-inference.md)。BP 算法参见 [../bp/inference.md](../bp/inference.md)。

## 各阶段产物

| 阶段 | 关键产物 |
|---|---|
| 验证 | 通过/失败（不一致时阻断） |
| 规范化 | `CanonicalBinding` 记录，新建/更新的 `GlobalCanonicalNode` |
| 评审 | 同行评审报告（发现 + 概率判断） |
| 集成 | 最终确定的绑定，更新的全局图，刷新的 `GlobalInferenceState` |
| 策展 | 聚类结果，冲突报告，清理操作 |
| 全局 BP | 更新的 `GlobalInferenceState`（节点信念值），`BeliefSnapshot` 历史 |

## 来源

- `libs/global_graph/canonicalize.py` -- 全局规范化
- `libs/pipeline.py` -- review 流水线
- `libs/curation/` -- 策展引擎
- `libs/inference/bp.py` -- BP 引擎
- `libs/storage/manager.py` -- 存储集成
