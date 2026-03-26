# 本地推理

> **Status:** Current canonical

本文档描述 `gaia infer` 如何在单个包上运行本地置信传播。BP 算法和因子势函数的定义参见 [BP 层](../bp/inference.md)。

## 概览

`gaia infer` 提供本地置信预览——它在包的局部规范图上使用本地导出的参数化运行 BP。范围严格限制在单个包内；不查询或修改全局图。

## `gaia infer` 的工作原理

该命令链接三个管线函数：

1. **Build**（`pipeline_build()`）—— 重建包，产出 `LocalCanonicalGraph`。
2. **Review**（`pipeline_review(build, mock=True)`）—— 通过 `MockReviewClient` 导出先验和因子参数，产出包含 `node_priors` 和 `factor_params` 的 `ReviewOutput`。
3. **Infer**（`pipeline_infer(build, review)`）—— 将图适配为因子图，运行 BP，输出置信值。

## 适配层

参见 `libs/graph_ir/adapter.py`。

适配器通过以下方式从 Gaia IR 构建 `FactorGraph`：

1. 将每个 `LocalCanonicalNode` ID 映射为整数变量 ID。
2. 从 `LocalParameterization`（或 `ReviewOutput.node_priors`）设置先验。
3. 将每个 `FactorNode` 映射为包含 `premises`、`conclusions`、`probability` 和 `edge_type` 的因子字典。
4. 应用 Cromwell 规则：所有先验和因子概率限制在 `[epsilon, 1 - epsilon]` 范围内。

结果是一个可供 BP 引擎使用的 `FactorGraph`。

## 参数

| 参数 | 默认值 | 描述 |
|-----------|---------|-------------|
| `damping` | 0.5 | 混合因子；1.0 = 完全替换，0.0 = 保持旧值 |
| `max_iterations` | 50 | 迭代次数上限 |
| `convergence_threshold` | 1e-6 | 最大置信变化低于此值时停止 |

这些是默认的 BP 参数。CLI 目前不将它们暴露为命令行参数。

## 输出

结果保存到 `.gaia/infer/infer_result.json`，包含：

- 每节点置信值（后验概率）
- 收敛诊断信息（运行迭代次数、是否收敛、停止时的最大变化）
- 用于冲突检测的置信历史轨迹

## 跨层引用

- **BP 算法**（消息传递、收敛、诊断）：参见 [../bp/inference.md](../bp/inference.md)
- **因子势函数**（每种因子类型如何约束置信值）：参见 [../bp/potentials.md](../bp/potentials.md)
- **本地与全局 BP**（相同算法，不同范围）：参见 [../bp/local-vs-global.md](../bp/local-vs-global.md)
- **参数化模型**（结构与概率的分离）：参见 [../gaia-ir/parameterization.md](../gaia-ir/parameterization.md)

## 代码路径

| 组件 | 文件 |
|-----------|------|
| 管线推理函数 | `libs/pipeline.py:pipeline_infer()` |
| Gaia IR 适配器 | `libs/graph_ir/adapter.py` |
| 因子图 | `libs/inference/factor_graph.py` |
| BP 算法 | `libs/inference/bp.py:BeliefPropagation` |
| CLI 命令 | `cli/main.py`（`infer` 命令） |
| 模拟审查客户端 | `cli/llm_client.py:MockReviewClient` |

## 当前状态

本地推理功能完备。CLI 始终使用 `MockReviewClient`（确定性先验：`setting = 1.0`，其他 = `0.5`；因子条件概率 = `0.85`）。真正的 LLM 审查仅通过管线脚本可用。
