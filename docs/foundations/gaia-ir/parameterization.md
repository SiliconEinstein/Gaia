# Parameterization — 参数定义

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

Parameterization 是 GlobalCanonicalGraph 上的概率参数层。它由一组**原子记录**构成——每条记录是一个 Knowledge 的 prior 或一个 Strategy 的 conditional probabilities。不同 review 来源（不同模型、不同策略）产出不同的记录，BP 运行前按 resolution policy 组装成完整参数集。

Gaia IR 结构定义见 [gaia-ir.md](gaia-ir.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

## 存储层：原子记录

数据库中存储的是独立的参数记录，每条记录携带来源信息：

```
PriorRecord:
    gcn_id:             str              # 全局 claim Knowledge ID
    value:              float            # ∈ (ε, 1-ε)
    source_id:          str              # 哪个 ParameterizationSource 产出的
    created_at:         str              # ISO 8601

StrategyParamRecord:
    strategy_id:            str              # 全局 Strategy ID (gcs_ 前缀)
    conditional_probabilities: list[float]   # None(通用): 2^K; infer(noisy-AND): [q]; soft_implication: [p₁, p₂]
    source_id:              str              # 哪个 ParameterizationSource 产出的
    created_at:             str              # ISO 8601

ParameterizationSource:
    source_id:          str              # 唯一 ID
    model:              str              # "gpt-5-mini" | "claude-opus" | ...
    policy:             str | None       # "conservative" | "aggressive" | 自定义策略名
    config:             dict | None      # threshold, prompt version 等具体配置
    created_at:         str              # ISO 8601
```

**关键规则：**

- **PriorRecord 只对 Claim**：只有 `type=claim` 的 Knowledge 有记录。Setting/Question/Template 不参与 BP。
- **所有形态的 Strategy 都有 conditional_probabilities**（折叠模式下的 ↝ 参数），因此所有推理类 Strategy 都需要 StrategyParamRecord。
- **FormalStrategy（9 种命名策略）展开时**，参数化通过中间 Knowledge 的 PriorRecord 实现；折叠时仍使用 conditional_probabilities。
- **Operator 是纯确定性的（ψ ∈ {0, 1}），不需要参数记录。**
- **一个 Knowledge/Strategy 可以有多条记录**（来自不同 source），BP 运行时选择用哪条。
- **Cromwell's rule**：所有值钳制到 `[ε, 1-ε]`，ε = 1e-3。

## BP 运行时：Resolution Policy

BP 运行前，按 resolution policy 从原子记录中为每个 Knowledge/Strategy 选择一个值，组装成完整参数集：

| policy | 说明 |
|--------|------|
| **latest** | 每个 Knowledge/Strategy 取最新的记录（按 `created_at`） |
| **source:\<source_id\>** | 指定使用某个 ParameterizationSource 的记录 |

组装过程是**现算的**，不持久化。组装时使用 `prior_cutoff` 时间戳过滤记录——只取该时间点之前的记录，确保结果可重现（见 [belief-state.md](belief-state.md)）。

### 多分辨率 BP 编译路径

BP 编译接受 `expand_set`（需要展开的 Strategy ID 集合），根据 Strategy 形态和展开决策选择路径：

- **Strategy 未在 expand_set 中 → 折叠**：使用 StrategyParamRecord.conditional_probabilities 编译为 ↝
- **CompositeStrategy 在 expand_set 中 → 展开**：递归编译 sub_strategies
- **FormalStrategy 在 expand_set 中 → 展开**：BP 在 Operator 层运行（参数在中间 Knowledge 的 PriorRecord）

### 完整性检查

BP 引擎在运行前验证组装结果的完整性：

- GlobalCanonicalGraph 中每个 `type=claim` 的 Knowledge 都必须有对应的 PriorRecord
- 所有推理类 Strategy 都必须有 StrategyParamRecord（折叠参数）
- FormalStrategy 的 FormalExpr 展开的中间 Knowledge（如果是 claim）也必须有 PriorRecord（仅在展开模式下需要）

否则拒绝运行。

## Prior 来源

每个 global claim Knowledge 的 prior 由 review 赋值。不存在聚合逻辑——canonicalization 对 premise Knowledge 直接复用已有 global Knowledge（prior 不变），对 conclusion Knowledge 创建新的 global Knowledge（prior 由 review 独立赋值）。

## Strategy probability 来源

- `None`（通用）：完整 CPT（2^K 参数），默认 MaxEnt 0.5，由 review 赋值
- `infer`（noisy-AND）：单参数 [q]，由 review 赋值，反映推理本身的可信度
- `soft_implication`：[p₁, p₂]，由 review 赋值
- `independent_evidence`：[q]，声明 premises 之间独立支持关系（conclusion=None），确认后编译为 Operator
- `contradiction`：[q]，声明两个 premises 矛盾（conclusion=None），确认后编译为 Operator
- `toolcall` / `proof`：可根据计算的可复现性打分（具体策略后续定义）
- Canonicalization 确认的 equivalence Operator 是独立结构关系（顶层 operators），不需要 StrategyParamRecord

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `StrategyParamRecord`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell 钳制
