# 全局推断

> **Status:** Current canonical

本文档描述在 global canonical graph 上进行的服务端 belief propagation。BP 算法详情参见 [BP 层](../bp/inference.md)。Factor potential 定义参见 [potentials](../bp/potentials.md)。

## 概述

全局推断运行与本地推断相同的 sum-product loopy BP 算法，但作用域不同：

| 方面 | 本地 BP（`gaia infer`） | 全局 BP（服务端） |
|------|------------------------|-------------------|
| **图** | LocalCanonicalGraph（单个包） | Global canonical graph（所有包） |
| **参数化** | LocalParameterization / ReviewOutput | GlobalInferenceState |
| **触发** | `gaia infer` CLI 命令 | 集成或策展之后 |
| **输出** | 本地信念预览（`.gaia/infer/`） | 更新 `GlobalInferenceState.node_beliefs` |

算法、消息调度和 factor potential 完全相同。参见 [../bp/local-vs-global.md](../bp/local-vs-global.md) 了解对比。

## GlobalInferenceState 作为参数化来源

GlobalInferenceState 是注册中心管理的单例，存储全局图的所有运行时参数：

- **`node_priors`** -- `dict[str, float]`，以 `global_canonical_id` 为键。由所有已集成包的审查输出聚合而成。
- **`factor_parameters`** -- `dict[str, FactorParams]`，以 `factor_id` 为键。每个包含 `conditional_probability`。
- **`node_beliefs`** -- `dict[str, float]`，以 `global_canonical_id` 为键。每次 BP 运行后更新。
- **`graph_hash`** -- 完整性校验，将状态绑定到特定的图结构。

概率与结构严格分离：Gaia IR 只存储结构；GlobalInferenceState 存储所有运行时参数。参见 [../gaia-ir/parameterization.md](../gaia-ir/parameterization.md)。

## 全局 BP 何时运行

全局 BP 在以下情况后触发：

1. **集成** -- 新包被合并到全局图，添加新的节点和 factor。
2. **策展** -- 策展引擎修改了图（合并重复项、添加抽象 factor、移除过期条目）。

在这两种情况下，图结构都已改变，信念需要重新计算。

## 执行流程

1. 从存储加载 global canonical graph（所有 GlobalCanonicalNode 和全局 FactorNode）。
2. 使用 `GlobalInferenceState.node_priors` 和 `factor_parameters` 从全局节点和 factor 构建 FactorGraph。
3. 使用标准参数运行 BeliefPropagation（damping=0.5、max_iterations=50、threshold=1e-6）。
4. 将更新的信念写入 `GlobalInferenceState.node_beliefs`。
5. 可选地写入 BeliefSnapshot 历史记录。

## 代码路径

| 组件 | 文件 |
|------|------|
| 全局 BP 脚本 | `scripts/pipeline/run_global_bp_db.py` |
| BP 算法 | `libs/inference/bp.py:BeliefPropagation` |
| Factor graph | `libs/inference/factor_graph.py:FactorGraph` |
| Global inference state | `libs/storage/models.py:GlobalInferenceState` |
| Storage manager | `libs/storage/manager.py:StorageManager` |

## 当前状态

全局 BP 作为批处理 pipeline 脚本（`run_global_bp_db.py`）可用。它通过 StorageManager 从 LanceDB 读写。用于本地推断的同一个 BeliefPropagation 类被无修改地复用。

## 目标状态

- 将全局 BP 作为服务端 BPService 暴露，在集成后异步触发。
- 添加增量 BP（仅在受新集成包影响的子图上重新运行）。
