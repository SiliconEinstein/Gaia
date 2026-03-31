# Parameterization — 参数定义

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Parameterization 是 Gaia IR 上的概率参数层。它由一组**原子记录**构成——每条记录是一个 Knowledge 的先验概率，或一个**需要外部概率参数的 Strategy** 的条件概率。不同 review 来源（不同模型、不同策略）产出不同的记录，推理运行前按 resolution policy 组装成完整参数集。

Gaia IR 结构定义见 [02-gaia-ir.md](02-gaia-ir.md)。推理输出见 [../bp/belief-state.md](../bp/belief-state.md)。三者的关系见 [01-overview.md](01-overview.md)。

backend-facing lowering 如何消费这些参数，见 [07-lowering.md](07-lowering.md)。

本文件只定义 **global parameterization contract**。若某些 local-only backend 需要临时 local 参数输入，那属于 backend-private / ephemeral workflow，不属于这里的持久化记录模型。

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
- **helper claim 仍按 claim 处理，但当前默认只指结构型 result claim**：这类 helper claim 默认由 Operator 确定，不额外引入自由 prior。
- **只有参数化 Strategy 才有 conditional_probabilities**：目前包括 `infer`、`noisy_and`。
- **直接 FormalStrategy** 不携带独立的 StrategyParamRecord：其有效条件行为由 FormalExpr、相关显式 claim 的 PriorRecord，以及确定性 Operator 共同导出。
- **Operator 是纯确定性的（真值表完全确定），不需要参数记录。**
- **一个 Knowledge/Strategy 可以有多条记录**（来自不同 source），推理运行时选择用哪条。
- **Cromwell's rule**：所有值钳制到 `[ε, 1-ε]`，ε = 1e-3。

**三层语义：**

1. **持久化输入层**：这里只存 review 明确给出的外部参数，即 `StrategyParamRecord`
2. **结构推导层**：直接 FormalStrategy 的行为由 `FormalExpr` + 相关显式 claim prior 决定；结构型 helper claim 由 Operator 确定
3. **运行时 assembled / compiled 层**：系统可以为任意 Strategy 生成一份等效的 `conditional_probabilities` 视图，但这份视图不是新的持久化 source of truth

## 参数模型

`conditional_probabilities` 作为**持久化输入字段**，只对需要外部概率参数的 Strategy 定义：

| type | conditional_probabilities | 说明 |
|------|--------------------------|------|
| **`infer`** | `[p₁, p₂, ..., p_{2^k}]`（2^k 个） | 完整条件概率表，每种前提真值组合一个参数。默认 MaxEnt 0.5 |
| **`noisy_and`** | `[p]`（1 个） | P(conclusion=true \| all premises=true) = p。前提不全真时 leak=ε |
| **`toolcall`**（deferred） | — | 未引入 |
| **`proof`**（deferred） | — | 未引入 |

## Resolution Policy

推理运行前，按 resolution policy 从原子记录中为每个 Knowledge/Strategy 选择一个值，组装成完整参数集：

| policy | 说明 |
|--------|------|
| **latest** | 每个 Knowledge/Strategy 取最新的记录（按 `created_at`） |
| **source:\<source_id\>** | 指定使用某个 ParameterizationSource 的记录 |

组装过程是**现算的**，不持久化。组装时使用 `prior_cutoff` 时间戳过滤记录——只取该时间点之前的记录，确保结果可重现（见 [../bp/belief-state.md](../bp/belief-state.md)）。

## 多分辨率支持

Strategy 的三种形态（基本 Strategy、CompositeStrategy、FormalStrategy）支持多分辨率推理。Parameterization 层为此提供两类持久化输入，并允许在运行时生成等效视图：

- **外部策略参数**：StrategyParamRecord.conditional_probabilities——仅参数化 Strategy 有，用于 `infer` / `noisy_and` 等 leaf probabilistic strategies。
- **显式 claim 先验**：相关显式中间 claim 与其他不确定 claim 的 PriorRecord——直接 FormalStrategy 的有效条件行为由这些 prior 与内部 skeleton 导出。

纯结构型 helper claim 即使显式存在于图中，也默认不作为新的独立参数入口；它们的值由对应 Operator 决定。

运行时 compiled 层可以进一步为每个 Strategy 生成一份等效 `conditional_probabilities`：

- 对参数化 Strategy：直接读取 StrategyParamRecord
- 对直接 FormalStrategy：对其私有内部变量做 marginalization，从 `FormalExpr` + interface-claim `PriorRecord` 导出

**Marginalization 的数学定义：** 对 FormalStrategy 的私有中间变量做变量消去（variable elimination）——在联合分布中对内部变量求和，得到仅关于接口变量（premises、conclusion）的等效条件概率 P(conclusion | premises)。

以 `FormalStrategy(type=deduction, premises=[A₁, A₂], conclusion=C)` 为例，其内部结构是：

```
conjunction([A₁, A₂], conclusion=M)    ← M=1 iff A₁=1 ∧ A₂=1
implication([M], conclusion=C)          ← M=1 时 C 必须=1
```

M 是私有中间变量。要导出等效条件概率 P(C | A₁, A₂)，对 M 做变量消去：

```
P(C=1 | A₁, A₂) = Σ_m P(C=1 | M=m) × P(M=m | A₁, A₂)
```

由于两个 Operator 都是确定性的（P(M=1 | A₁=1, A₂=1)=1，其余=0；P(C=1 | M=1)=1），结果是：当 A₁=1 ∧ A₂=1 时 P(C=1)=1，否则 P(C=1)=0。这就是纯演绎的确定性语义。

对含不确定性的命名策略（如 abduction），不确定性也应落在**接口 claim** 上，而不是私有内部节点上。例如 abduction 中承载自由度的是 public interface claim `AlternativeExplanationForObs`；内部的 `disjunction_result` / `equivalence_result` 仍是纯结构型 helper claim。marginalization 只是把这些私有 helper 节点安全消去，而不会为 private node 发明新的 prior。

这是精确的数学操作，属于 IR 的概率语义定义；具体推理后端可以用精确或近似算法实现（见 [bp/](../bp/) 层）。

由于 FormalExpr 内部节点是严格私有的（禁止外部引用，见 [04-helper-claims.md §3](04-helper-claims.md#3-formalexpr-内部-claim-的封装)），FormalStrategy **总是可以被折叠的**——所有内部变量都可以安全消去。

哪些 Strategy 折叠、哪些展开，由推理引擎的 `expand_set` 决定。对直接 FormalStrategy，折叠视图应由其内部结构现算出等效行为，而不是读取独立的 StrategyParamRecord。

## 完整性检查

推理运行前验证组装结果的完整性：

- 全局图中每个承载外生不确定性的 `type=claim` Knowledge 都必须有对应的 PriorRecord
- 每个参数化 Strategy 都必须有 StrategyParamRecord
- 每个直接 FormalStrategy 所依赖的相关 interface claim 都必须有 PriorRecord；这包括 formalization 自动补齐的 public interface claim（如 abduction 的 `AlternativeExplanationForObs`）

结构型 helper claim **禁止**携带独立 PriorRecord——它们的分布完全由 Operator 确定性约束决定，没有自由度（详细解释见 [04-helper-claims.md §6](04-helper-claims.md#6-与-parameterization-的关系)）。

**Operator 不属于 parameterization 的范围。** Operator 纯确定性，不携带任何概率参数。Parameterization 只管两类输入：claim 的 PriorRecord 和参数化 Strategy 的 StrategyParamRecord。每种 Operator 的行为完全由其真值表定义（见 [02-gaia-ir.md §2.2](02-gaia-ir.md#22-算子类型与真值表)），例如 conjunction 的约束是 `M=1 iff 所有输入=1`，implication 的约束是 `A=1 时 B 必须=1`——这些都是确定性关系，不需要额外的概率参数。

否则拒绝运行。

> **Open question：CompositeStrategy 折叠时的参数来源。** 当前 contract 只定义了参数化 leaf Strategy（读 StrategyParamRecord）和 FormalStrategy（从 FormalExpr + claim prior 导出）的折叠路径。CompositeStrategy 折叠为单个单元时的条件概率来源尚未定义——是需要显式 StrategyParamRecord，还是从 sub_strategies 自动 marginalize，或禁止折叠？待后续设计明确。

## Prior 来源

每个 global claim Knowledge 的 prior 由 review 赋值。不存在聚合逻辑——canonicalization 对 premise Knowledge 直接复用已有 global Knowledge（prior 不变），对 conclusion Knowledge 创建新的 global Knowledge（prior 由 review 独立赋值）。

## Strategy 条件概率来源

| type | 条件概率来源 |
|------|-------------|
| `infer` | Review 赋值。完整 CPT（2^k 参数），默认 MaxEnt 0.5 |
| `noisy_and` | Review 赋值。单参数 p，反映推理本身的可信度 |
| 直接 FormalStrategy（`deduction` 至 `case_analysis`） | 不单独赋持久化 strategy 参数；其有效条件行为由 FormalExpr + 相关 interface claim 的 PriorRecord 导出。纯结构型 helper claim 作为 Operator 结果，不默认引入独立 prior；若 formalization 自动补齐了 public interface claim，则它与其他 premise/conclusion claim 一样需要参数化 |
| `toolcall` / `proof`（deferred） | 未引入 |

## 源代码

- `gaia/gaia_ir/parameterization.py` -- `PriorRecord`, `StrategyParamRecord`, `ResolutionPolicy`, `ParameterizationSource`
- `gaia/gaia_ir/strategy.py` -- `Strategy`, `StrategyType`（type 决定参数模型）
