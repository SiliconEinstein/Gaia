# Local 与 Global 推理

> **Status:** Current canonical

`BeliefPropagation` 类同时用于 local、joint 和 global 推理。本文档描述三者共享的部分、差异，以及各模式的配置方式。

## Local 推理（`gaia infer`）

**范围**：单个包。

Local 推理运行在 **LocalCanonicalGraph** 上，使用 **LocalParameterization** 覆盖层作为概率来源。

- **图**：来自 `gaia build` 的 `graph_ir/local_canonical_graph.json`。
- **参数化**：作者生成的 `LocalParameterization` 覆盖层，包含节点先验概率和 factor 条件概率。
- **输出**：信念预览，位于 `.gaia/infer/` 下。这些仅供预览，不在发布时提交。
- **目的**：让作者在发布前查看 BP 如何评估其推理结构。结论的低信念值可能表示前提缺失或推理薄弱。

当 `--depth 0`（默认）时，local 推理不查询或修改全局图。外部节点的先验来自 `dep_beliefs/` 中的扁平信念值（由 `gaia add` 下载），不包含依赖包的推理结构。

### 联合跨包推理（`gaia infer --depth N`）

当指定 `--depth N`（N>0 或 N=-1 表示无限递归），推理从单包局部模式升级为**联合跨包推理**。这是 local 和 global 之间的中间模式——仍在 CLI 端运行，但跨越多个包。

**机制**：

1. 通过 `load_dependency_compiled_graphs()` 从已安装的 `-gaia` 依赖包中加载已编译的 IR（`ir.json`），按 `depth` 控制递归深度（1=仅直接依赖，2+=递归，-1=全部传递依赖）。
2. 分别对本地包和各依赖包调用 `lower_local_graph()` 生成独立的 FactorGraph。
3. 通过 `merge_factor_graphs()` 将所有 FactorGraph 合并为一个联合图：
   - 共享 QID 的节点合并为单个 variable（按所有权决定先验优先级）。
   - **先验优先级**：每个包对自己拥有的节点（QID 前缀匹配 `{namespace}:{package}::`）具有先验权威性。依赖包的节点使用依赖包设定的先验，本地包的节点使用本地先验。
   - 所有 factor 以带前缀的 ID 共存（`dep_{name}_...` / `local_...`），避免 ID 冲突。
4. 在合并后的联合图上运行 `InferenceEngine`（与单包推理使用完全相同的 BP/JT 算法）。

**与 `--depth 0` 的区别**：

| 方面 | `--depth 0` | `--depth N` (N!=0) |
|---|---|---|
| 外部节点处理 | `dep_beliefs/` 中的扁平信念值注入为先验 | 依赖包的完整因子图参与联合推理 |
| 推理结构 | 仅本地包的 factor | 本地 + 依赖包的所有 factor |
| 信息流 | 单向（上游信念 → 本地先验） | 双向（本地证据可通过 BP 消息传递影响依赖节点的后验） |
| 适用场景 | 快速预览、无依赖的包 | 跨包推理链（如 A 包的结论是 B 包的前提） |

**注意事项**：

- 联合推理不修改依赖包的任何文件，输出仍写入本地包的 `.gaia/beliefs.json`。
- 依赖包必须已编译（存在 `.gaia/ir.json`）。
- 合并后的图规模随依赖数量增长，可能影响推理性能。

## Global 推理（服务器 BP）

**范围**：所有已摄入的包。

Global 推理运行在 LKM 维护的 **persistent FactorGraph** 上，使用 **PriorRecord / FactorParamRecord** 作为概率来源。

- **图**：由所有已 integrate 包组装而成的 global FactorGraph。
- **参数化**：独立的参数化层（PriorRecord、FactorParamRecord），按 resolution_policy 解析为具体值。
- **输出**：BeliefSnapshot，包含所有 variable 的后验信念值。
- **目的**：在所有包的全部可用证据基础上，产生系统对每个命题可信度的最佳估计。

Global 推理的 FactorGraph 是持久化的——integrate 时写入存储，BP 直接从中读取。详见 [gaia-lkm LKM 文档](https://github.com/SiliconEinstein/gaia-lkm/tree/main/docs/foundations/lkm/)。

## 共享部分

| 方面 | 是否共享？ |
|---|---|
| 算法 | 是——相同的 `BeliefPropagation` 类 |
| 消息调度 | 是——同步 sum-product |
| Factor potential | 是——所有 factor 类型使用相同的 potential 函数 |
| Damping、收敛、Cromwell's rule | 是——相同的参数 |
| 诊断 | 是——`belief_history`、`direction_changes` 在所有模式下均可用 |

## 差异部分

| 方面 | Local (`--depth 0`) | Joint (`--depth N`, N!=0) | Global |
|---|---|---|---|
| **图范围** | 单个包的 local FactorGraph | 本地包 + 依赖包的合并 FactorGraph | 所有包的 global FactorGraph |
| **ID 命名空间** | Knowledge QID（`{ns}:{pkg}::{label}`） | Knowledge QID（多个包共存） | global variable/factor ID |
| **参数化来源** | metadata prior + `dep_beliefs/` 扁平注入 | metadata prior（各包对自有节点具有权威性） | PriorRecord / FactorParamRecord（按 resolution_policy 解析） |
| **跨包证据** | 仅上游信念值（单向） | 完整因子图（双向 BP 消息传递） | 有（共享的 schema 节点、已规范化的 claim） |
| **持久性** | 临时预览 | 临时预览 | 持久化 FactorGraph + BeliefSnapshot |
| **触发方式** | `gaia infer` CLI 命令 | `gaia infer --depth N` CLI 命令 | Curation 完成后（集成或策展后） |

## 参数化来源详情

### Local（`--depth 0`）

节点先验来自 Knowledge metadata 中的 `prior` 字段（由 `priors.py` 和编译时 DSL `reason+prior` 对设定）。lowering 层直接读取 `metadata["prior"]`。外部节点（QID 前缀不匹配本地包的节点）的先验来自 `dep_beliefs/` 目录中上游包发布的信念值。

### Joint（`--depth N`, N!=0）

各包的先验仍来自各自 Knowledge metadata 的 `prior` 字段。`merge_factor_graphs()` 按所有权规则决定先验优先级：每个包对以自己 QID 前缀开头的节点具有权威性。不需要 `dep_beliefs/` — 依赖包的完整因子图直接参与推理。

### Global

参数存储在独立的参数化层：PriorRecord（per variable）和 FactorParamRecord（per factor），各带 source_id 和 created_at。一个 variable/factor 可有多条参数记录（来自不同 reviewer/来源）。BP 运行时按 resolution_policy + prior_cutoff 从中选择具体值。结果写入 BeliefSnapshot（不覆盖参数记录）。详见 [gaia-lkm 02-storage.md](https://github.com/SiliconEinstein/gaia-lkm/blob/main/docs/foundations/lkm/02-storage.md)。

## 相关文档

- [../gaia-ir/06-parameterization.md](../gaia-ir/06-parameterization.md) -- 覆盖层 schema 和完整性校验
- [inference.md](inference.md) -- BP 如何在 Gaia IR 上运行（算法细节）
- [potentials.md](potentials.md) -- factor potential 函数

## 源代码

- `libs/inference/bp.py` -- `BeliefPropagation`（共享类）
- `libs/graph_ir/adapter.py` -- 从 local 或 global graph 构建 `FactorGraph`
- `libs/graph_ir/models.py` -- `LocalParameterization`
- `gaia/bp/lowering.py` -- `lower_local_graph()`、`merge_factor_graphs()`（联合跨包合并）
- `gaia/cli/commands/infer.py` -- `gaia infer` 命令（`--depth` 参数）
- `gaia/cli/_packages.py` -- `load_dependency_compiled_graphs()`、`collect_foreign_node_priors()`
