# Parameterization — 参数定义

> **Status:** Current v0.5 contract
>
> **Protected Contract Layer** — 本目录定义 CLI 和 LKM 之间的结构契约。变更需要独立 PR 并经负责人审查批准。

Parameterization 是 Gaia IR 上的 **claim prior** 层。它只保存对
`type=claim` Knowledge 的外生先验判断；每条记录带有来源信息，多个
source 可以给同一个 claim 写入不同 prior，推理运行前再由
`ResolutionPolicy` 选择 winner。

Strategy 的条件概率参数不再有独立的 `StrategyParamRecord` 层。v0.5 的
实际 IR contract 是：

- `infer` / `noisy_and` 的 `conditional_probabilities` 保存在
  `Strategy` 自身；
- `associate` 的 `p_a_given_b` / `p_b_given_a` 保存在 `Strategy` 自身；
- `FormalStrategy` 不携带独立 strategy-level 概率参数，其行为由
  `FormalExpr`、接口 claim 的 prior，以及确定性 `Operator` 结构导出。

Gaia IR 结构定义见 [02-gaia-ir.md](02-gaia-ir.md)。推理输出见
[../bp/belief-state.md](../bp/belief-state.md)。backend-facing lowering
如何消费这些 inline strategy 参数，见 [07-lowering.md](07-lowering.md)。

## 存储层：原子记录

数据库中存储独立的 claim prior 记录，每条记录携带来源信息：

```text
PriorRecord:
    knowledge_id:       str              # claim Knowledge QID
    value:              float            # ∈ [ε, 1-ε]
    source_id:          str              # 哪个 ParameterizationSource 产出的
    justification:      str
    created_at:         str              # ISO 8601

ParameterizationSource:
    source_id:          str              # 唯一 ID
    model:              str              # "user" | "gpt-5-mini" | ...
    policy:             str | None       # "user_priors" | "continuous_inference" | ...
    config:             dict | None      # threshold, prompt version 等具体配置
    created_at:         str              # ISO 8601
```

**关键规则：**

- **PriorRecord 只对 claim**：只有 `type=claim` 的 Knowledge 有记录。
  Setting 和 question 不携带概率。
- **helper claim 仍按 claim 处理**：public interface helper claim 可以像
  普通 claim 一样拥有 prior；结构型 private/helper result claim 由
  Operator 确定，禁止携带独立 PriorRecord。
- **Strategy 参数是 inline IR 字段**：不要在 parameterization 层为
  Strategy 另建记录。
- **Operator 是纯确定性的**：真值表完全确定，不需要参数记录。
- **一个 claim 可以有多条 PriorRecord**：来自不同 source，resolution
  时选择 winner，同时保留 losers 供 audit。
- **Cromwell's rule**：所有值钳制到 `[ε, 1-ε]`，ε = `1e-3`。

## Resolution Policy

推理运行前，按 resolution policy 从同一 claim 的多条 PriorRecord 中选择
winner。组装过程是现算的，不持久化为新的 source of truth。`prior_cutoff`
可以把 records 过滤到某个时间点之前，从而复现历史快照。

| policy | 说明 |
|--------|------|
| `explicit_priority`（默认） | 按 `priority_order` 模式列表中第一个匹配的 source 选；同 source 内 recency tiebreaker。模式支持 trailing wildcard（`reviewer_*`）和 catch-all（`*`） |
| `latest` | 每个 claim 取最新记录，source-agnostic |
| `source:<source_id>` | 只使用某个 source 的记录，同 source 内 recency tiebreaker |

### 默认 priority_order

`ResolutionPolicy` 的默认策略 `explicit_priority` 配合下列默认
`priority_order`（定义在 `gaia.ir.DEFAULT_PRIORITY_ORDER`）：

```python
DEFAULT_PRIORITY_ORDER = (
    "calibration_*",          # 1. 历史校准（未来 feature）
    "user_priors",            # 2. 作者用 register_prior() 默认 source
    "reviewer_*",             # 3. 人工 reviewer 估计
    "continuous_inference",   # 4. 连续参数推断引擎
    "evidence_factor_*",      # 5. EvidenceFactor 派生（未来）
    "agent_*",                # 6. LLM agent 自动建议
    "claim_inline",           # 7. claim(prior=X) 内联 shortcut
    "*",                      # 8. catch-all
)
```

核心原则：

1. 明确审议大于便利 shortcut：显式 `register_prior()` 默认
   `user_priors`，优先于 `claim(prior=X)` 产生的 `claim_inline`。
2. 作者意图通常大于引擎产出；retrospective calibration 是例外，因为它
   可能纳入作者写作时没有的真实 outcome evidence。

作者可以在 `priors.py` 中导出自定义 `RESOLUTION_POLICY`：

```python
from gaia.ir import ResolutionPolicy

RESOLUTION_POLICY = ResolutionPolicy(
    strategy="explicit_priority",
    priority_order=["calibration_2026q2", "user_priors", "continuous_inference", "*"],
)
```

## 作者面 API

Prior 是 Bayesian 推理唯一的非数据输入，承载作者的主观判断、领域知识和
不确定性立场。Gaia v0.5+ 提供两个作者面入口：

### `register_prior` — 规范入口

```python
from gaia.lang import register_prior

register_prior(
    claim_obj,
    value=0.7,
    justification="literature consensus from Doll-Hill 1956 + replications",
    source_id="user_priors",
)
```

契约：

- `claim_obj` 必须是现有 `Claim` 实例；
- `value` 必须落在 `[CROMWELL_EPS, 1 - CROMWELL_EPS]`；
- `justification` 必须非空；
- `source_id` 默认 `"user_priors"`；
- 多次调用同一 claim 会 append 多条记录，resolution 时仲裁。

编译时，winning record 会写入 `metadata["prior"]`,
`metadata["prior_justification"]`, `metadata["prior_source_id"]`；所有候选
record 保留在 `metadata["prior_records"]` 供 audit / diagnostics 使用。

### `claim(prior=X)` — 低优先级便利 shortcut

```python
my_claim = claim("Subject p smokes daily.", prior=0.3)
```

等价于注册一条 `source_id="claim_inline"` 的 prior record。inline shortcut
在默认 `priority_order` 中低于 `user_priors`，适合作为草稿先验；经过审议的
prior 应写成 `register_prior(...)`。

### `priors.py` 文件约定

`priors.py` 在 `gaia compile` / `gaia infer` 时被自动 import，触发其中的
`register_prior` 调用作为 side effect。文件可以同时导出可选的
`RESOLUTION_POLICY`。

```python
from gaia.lang import register_prior

from . import daily_observation

register_prior(
    daily_observation,
    0.90,
    justification="empirical background in air",
)
```

不再支持 `PRIORS = {claim: (value, justification)}` dict 格式；检测到该
dict 会报 migration error。不要为了表达“中立”而注册 `0.5` prior；如果
一个独立模型假设暂时没有外部信息来源，应保持 unset，由 MaxEnt 给出中立
起点。

## 诊断

`gaia inquiry review` 在多源场景下额外发出两类 diagnostic：

| Diagnostic | Severity | 触发条件 |
|-----------|----------|---------|
| `prior_dissent` | warning | 同一 claim 有多条 PriorRecord 且 `max(values) - min(values) > PRIOR_DISSENT_THRESHOLD` |
| `prior_overridden` | info | ResolutionPolicy 选中一条 record 并覆盖其他候选 |

`gaia check --hole` 在显示已覆盖的独立 claim 时也会展示所有 source：

```text
- daily_observation  prior=0.9 (source: user_priors)
                       ↪ also: 0.85 (source: continuous_inference, overridden)
- aristotle_model    no external prior (MaxEnt)
- some_predicate     prior=0.27 (source: continuous_inference)
```

## 与 Strategy 参数的关系

Parameterization 只管 claim prior；Strategy 概率参数留在 IR 的 Strategy
字段上：

| Strategy type | 参数位置 | 说明 |
|---------------|----------|------|
| `infer` | `Strategy.conditional_probabilities` | 完整 CPT，长度为 `2^k`；compiler 可按 MaxEnt 填默认 0.5 |
| `noisy_and` | `Strategy.conditional_probabilities` | 兼容路径，单参数 p |
| `associate` | `Strategy.p_a_given_b`, `Strategy.p_b_given_a` | 对称关联的两个条件概率 |
| `support` / `deduction` 等 FormalStrategy | 无独立 strategy 参数 | 行为由 FormalExpr + interface claim prior + Operator 结构导出 |

这意味着 `.gaia/ir.json` 的 source of truth 是 `Strategy` inline 字段，而不是
额外的 strategy parameter record。若未来引入 first-class EvidenceFactor 或
校准层，应作为新的明确 contract 设计，而不是复活半接线的 sidecar 参数层。

## 完整性检查

本地 `gaia infer` 和发布 / LKM 摄入应区分：

- 本地 preview 允许独立 claim 缺少外部 PriorRecord；这些自由变量按
  MaxEnt 进入推理，用于帮助作者发现还没有覆盖的输入。
- `gaia check --gate` / 发布流程可以要求更严格的完整性：structural
  holes、unformalized dependencies、unaccepted review warrants 或低 posterior
  都可以阻断发布质量 gate。
- Strategy 结论 claim 的 belief 由对应 Strategy / BP 推导，不要求独立
  prior。
- 结构型 helper claim 和 FormalExpr private node 禁止携带独立 PriorRecord。
- 如果某个 public interface helper 被设计成普通独立 claim，它应按普通
  claim 处理；但 relation/decompose/infer 生成的 helper 通常是 review target
  或结构变量，不应获得外部 prior。

## 源代码

- `gaia/ir/parameterization.py` — `PriorRecord`, `ResolutionPolicy`,
  `ParameterizationSource`, `DEFAULT_PRIORITY_ORDER`, `default_resolution_policy`
- `gaia/ir/strategy.py` — `Strategy`, `StrategyType`（inline strategy probability fields）
- `gaia/lang/dsl/register_prior.py` — `register_prior()` 作者面 API、resolution 步骤、metadata schema 常量
- `gaia/lang/dsl/knowledge.py` — `claim(prior=X)` shortcut
- `gaia/cli/_packages.py` — `apply_package_priors()` CLI 步骤
- `gaia/lang/compiler/compile.py` — `compile_package_artifact()` 入口处的 idempotent resolution 兜底
- `gaia/inquiry/diagnostics.py` — `detect_prior_dissent()`, `detect_prior_overridden()`
- `gaia/cli/commands/check.py` — `_append_covered_prior_details` 的多源输出格式
