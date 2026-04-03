# 全局推理

> **Status:** Target design

## 概述

全局推理在 global FactorGraph 上运行 loopy belief propagation (BP)，计算所有 variable nodes 的后验信念。它在 curation 完成后触发，是 write side 的最后一步。

## 与本地推理的关系

本地推理（`gaia infer`）和全局推理使用完全相同的 BP 算法和势函数。区别仅在于作用域和参数来源：

| 方面 | 本地 BP | 全局 BP |
|------|---------|---------|
| **图** | Local FactorGraph（单包） | Global FactorGraph（所有包 + 论文） |
| **参数** | ReviewOutput 产生的 PriorRecord / FactorParamRecord | 全局参数化层中的所有 PriorRecord / FactorParamRecord |
| **参数解析** | 直接使用（单来源） | 按 resolution_policy 从多来源中选择 |
| **触发** | `gaia infer` CLI 命令 | Curation 完成后 |
| **输出** | 本地信念预览 | BeliefSnapshot（持久化） |

算法、消息调度、势函数、Cromwell's rule 完全一致。详见 [推理](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/bp/inference.md)、[势函数](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/bp/potentials.md)、[局部与全局](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/bp/local-vs-global.md)。

## 执行流程

1. **加载 FactorGraph**：从存储读取所有 variable nodes 和 factor nodes
2. **解析参数**：按 `resolution_policy` + `prior_cutoff` 从 PriorRecord / FactorParamRecord 中选择具体的 prior 和 conditional probability 值
3. **构建 BP 运行时**：将 FactorGraph + 解析后的参数传入 BP 引擎（内部转换为 int 索引是实现细节）
4. **运行 BP**：damping=0.5, max_iterations=50, threshold=1e-6
5. **保存 BeliefSnapshot**：包含 beliefs、resolution_policy、prior_cutoff、graph_hash、convergence_info

### Resolution Policy

当一个 variable/factor 有多条 PriorRecord / FactorParamRecord 时，resolution_policy 决定使用哪个值：

- `latest`：使用 `created_at` 最新的记录
- `source:<id>`：使用指定来源的记录

Resolution policy 和 prior_cutoff 记录在 BeliefSnapshot 中，保证 BP 结果可复现：给定相同的 graph_hash + resolution_policy + prior_cutoff，产出相同的 beliefs。

## 何时运行

全局 BP 在以下情况后触发：

1. **Curation 完成** — 图中的重复和冲突已处理
2. **手动触发** — 通过 API 或 CLI

**不**在每次 integrate 后立即运行。原因：
- Integrate 后的确定性去重已消除精确重复，但语义重复仍存在
- 等 curation 处理完语义重复再跑，避免 double counting
- 批量 ingest 场景下（灌入大量论文），逐包跑 BP 无意义

## 未来演进

- **增量 BP**：只在受新 integrate/curation 影响的子图上重新运行，而非全图
- **粗粒化 BP**：将子图折叠为单个 factor，在不同粒度上运行 BP。需要单独设计
- **算法演进**：如果从 BP 切换到 MCMC 等其他推理方法，全局推理的实现需要重新设计
