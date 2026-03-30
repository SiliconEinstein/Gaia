# Parameterization — 参数定义

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Parameterization 是 Gaia IR 上的概率参数层。它由一组**原子记录**构成——每条记录是一个 Knowledge 的先验概率，或一个**需要外部概率参数的 Strategy** 的条件概率。不同 review 来源（不同模型、不同策略）产出不同的记录，推理运行前按 resolution policy 组装成完整参数集。

Gaia IR 结构定义见 [gaia-ir.md](gaia-ir.md)。推理输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

## 存储层：原子记录

数据库中存储独立的参数记录，每条记录携带来源信息：

```
PriorRecord:
    gcn_id:             str              # 全局 claim Knowledge ID
    value:              float            # ∈ (ε, 1-ε)
    source_id:          str              # 哪个 ParameterizationSource 产出的
    created_at:         str              # ISO 8601

StrategyParamRecord:
    strategy_id:                str          # 全局 Strategy ID (gcs_ 前缀，仅对参数化 Strategy)
    conditional_probabilities:  list[float]  # 参数数量由 type 决定（见下表）
    source_id:                  str          # 哪个 ParameterizationSource 产出的
    created_at:                 str          # ISO 8601

ParameterizationSource:
    source_id:          str              # 唯一 ID
    model:              str              # "gpt-5-mini" | "claude-opus" | ...
    policy:             str | None       # "conservative" | "aggressive" | 自定义策略名
    config:             dict | None      # threshold, prompt version 等具体配置
    created_at:         str              # ISO 8601
```

**关键规则：**

- **PriorRecord 只对 claim**：只有 `type=claim` 的 Knowledge 有记录。Setting 和 question 不携带概率。
- **只有参数化 Strategy 才有 conditional_probabilities**：目前包括 `infer`、`noisy_and`，以及未来若定义参数模型的 `toolcall` / `proof`。
- **直接 FormalStrategy** 不携带独立的 StrategyParamRecord：其有效条件行为由 FormalExpr 和中间 Knowledge 的 PriorRecord 导出。
- **Operator 是纯确定性的（真值表完全确定），不需要参数记录。**
- **一个 Knowledge/Strategy 可以有多条记录**（来自不同 source），推理运行时选择用哪条。
- **Cromwell's rule**：所有值钳制到 `[ε, 1-ε]`，ε = 1e-3。

## 参数模型

`conditional_probabilities` 只对需要外部概率参数的 Strategy 定义：

| type | conditional_probabilities | 说明 |
|------|--------------------------|------|
| **`infer`** | `[p₁, p₂, ..., p_{2^k}]`（2^k 个） | 完整条件概率表，每种前提真值组合一个参数。默认 MaxEnt 0.5 |
| **`noisy_and`** | `[p]`（1 个） | P(conclusion=true \| all premises=true) = p。前提不全真时 leak=ε |
| **`toolcall`** | 另行定义 | 可根据计算的可复现性打分 |
| **`proof`** | 另行定义 | 有效证明可设为 1.0 - ε |

## Resolution Policy

推理运行前，按 resolution policy 从原子记录中为每个 Knowledge/Strategy 选择一个值，组装成完整参数集：

| policy | 说明 |
|--------|------|
| **latest** | 每个 Knowledge/Strategy 取最新的记录（按 `created_at`） |
| **source:\<source_id\>** | 指定使用某个 ParameterizationSource 的记录 |

组装过程是**现算的**，不持久化。组装时使用 `prior_cutoff` 时间戳过滤记录——只取该时间点之前的记录，确保结果可重现（见 [belief-state.md](belief-state.md)）。

## 多分辨率支持

Strategy 的三种形态（基本 Strategy、CompositeStrategy、FormalStrategy）支持多分辨率推理。Parameterization 层为此提供两类信息：

- **外部策略参数**：StrategyParamRecord.conditional_probabilities——仅参数化 Strategy 有，用于 `infer` / `noisy_and` 等 leaf probabilistic strategies。
- **显式 claim 先验**：FormalExpr 中间 Knowledge 的 PriorRecord——直接 FormalStrategy 的有效条件行为由这些 prior 与内部 skeleton 导出。

哪些 Strategy 展开、哪些折叠，由推理引擎的 `expand_set` 决定。对直接 FormalStrategy，如果运行时需要折叠视图，应由其内部结构现算出等效行为，而不是读取独立的 StrategyParamRecord。具体的推理算法见 [bp/](../bp/) 层。

## 完整性检查

推理运行前验证组装结果的完整性：

- 全局图中每个 `type=claim` 的 Knowledge 都必须有对应的 PriorRecord
- 每个参数化 Strategy 都必须有 StrategyParamRecord
- 每个直接 FormalStrategy 的中间 Knowledge（如果是 claim）都必须有 PriorRecord

否则拒绝运行。

## Prior 来源

每个 global claim Knowledge 的 prior 由 review 赋值。不存在聚合逻辑——canonicalization 对 premise Knowledge 直接复用已有 global Knowledge（prior 不变），对 conclusion Knowledge 创建新的 global Knowledge（prior 由 review 独立赋值）。

## Strategy 条件概率来源

| type | 条件概率来源 |
|------|-------------|
| `infer` | Review 赋值。完整 CPT（2^k 参数），默认 MaxEnt 0.5 |
| `noisy_and` | Review 赋值。单参数 p，反映推理本身的可信度 |
| 直接 FormalStrategy（`deduction` 至 `case_analysis`） | 不单独赋 strategy 参数；其有效条件行为由 FormalExpr + 中间 Knowledge 的 PriorRecord 导出 |
| `toolcall` / `proof` | 可根据可复现性/验证结果打分（具体策略后续定义） |

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `StrategyParamRecord`
- `gaia/libs/models/parameterization.py` -- `PriorRecord`, `FactorParamRecord`, `ResolutionPolicy`
