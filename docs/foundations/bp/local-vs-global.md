# Local 与 Global 推理

> **Status:** Current canonical

`BeliefPropagation` 类同时用于 local 和 global 推理。本文档描述两者共享的部分、差异，以及各模式的配置方式。

## Local 推理（`gaia infer`）

**范围**：单个包。

Local 推理运行在 **LocalCanonicalGraph** 上，使用 **LocalParameterization** 覆盖层作为概率来源。

- **图**：来自 `gaia build` 的 `graph_ir/local_canonical_graph.json`。
- **参数化**：作者生成的 `LocalParameterization` 覆盖层，包含节点先验概率和 factor 条件概率。
- **输出**：信念预览，位于 `.gaia/infer/` 下。这些仅供预览，不在发布时提交。
- **目的**：让作者在发布前查看 BP 如何评估其推理结构。结论的低信念值可能表示前提缺失或推理薄弱。

Local 推理不查询或修改全局图。它完全是包内局部的。

## Global 推理（服务器 BP）

**范围**：所有已摄入的包。

Global 推理运行在 LKM 维护的 **persistent FactorGraph** 上，使用 **PriorRecord / FactorParamRecord** 作为概率来源。

- **图**：由所有已 integrate 包组装而成的 global FactorGraph。
- **参数化**：独立的参数化层（PriorRecord、FactorParamRecord），按 resolution_policy 解析为具体值。
- **输出**：BeliefSnapshot，包含所有 variable 的后验信念值。
- **目的**：在所有包的全部可用证据基础上，产生系统对每个命题可信度的最佳估计。

Global 推理的 FactorGraph 是持久化的——integrate 时写入存储，BP 直接从中读取。详见 [dp-gaia LKM 文档](https://github.com/SiliconEinstein/dp-gaia/tree/main/docs/foundations/lkm/)。

## 共享部分

| 方面 | 是否共享？ |
|---|---|
| 算法 | 是——相同的 `BeliefPropagation` 类 |
| 消息调度 | 是——同步 sum-product |
| Factor potential | 是——所有 factor 类型使用相同的 potential 函数 |
| Damping、收敛、Cromwell's rule | 是——相同的参数 |
| 诊断 | 是——`belief_history`、`direction_changes` 在两种模式下均可用 |

## 差异部分

| 方面 | Local | Global |
|---|---|---|
| **图范围** | 单个包的 local FactorGraph | 所有包的 global FactorGraph |
| **ID 命名空间** | Knowledge QID（`{ns}:{pkg}::{label}`） | global variable/factor ID |
| **参数化来源** | `LocalParameterization`（作者生成的覆盖层） | PriorRecord / FactorParamRecord（按 resolution_policy 解析） |
| **跨包证据** | 无（隔离的） | 有（共享的 schema 节点、已规范化的 claim） |
| **持久性** | 临时预览 | 持久化 FactorGraph + BeliefSnapshot |
| **触发方式** | `gaia infer` CLI 命令 | Curation 完成后（集成或策展后） |

## 参数化来源详情

### Local

`LocalParameterization` 覆盖层以 Knowledge QID 为键存储节点先验概率，以 `factor_id` 为键存储 factor 参数。它通过 `graph_hash` 引用 local canonical graph。覆盖层在本地生成（由 agent skill 或手动），不在发布时提交。

### Global

参数存储在独立的参数化层：PriorRecord（per variable）和 FactorParamRecord（per factor），各带 source_id 和 created_at。一个 variable/factor 可有多条参数记录（来自不同 reviewer/来源）。BP 运行时按 resolution_policy + prior_cutoff 从中选择具体值。结果写入 BeliefSnapshot（不覆盖参数记录）。详见 [dp-gaia 02-storage.md](https://github.com/SiliconEinstein/dp-gaia/blob/main/docs/foundations/lkm/02-storage.md)。

## 相关文档

- [../gaia-ir/06-parameterization.md](../gaia-ir/06-parameterization.md) -- 覆盖层 schema 和完整性校验
- [inference.md](inference.md) -- BP 如何在 Gaia IR 上运行（算法细节）
- [potentials.md](potentials.md) -- factor potential 函数

## 源代码

- `libs/inference/bp.py` -- `BeliefPropagation`（共享类）
- `libs/graph_ir/adapter.py` -- 从 local 或 global graph 构建 `FactorGraph`
- `libs/graph_ir/models.py` -- `LocalParameterization`
