# Parameterization — 参数定义

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

Parameterization 是 Gaia IR 的下游概率参数层。它不改变 persistent Graph IR 的对象边界，而是为**当前将被运行时使用的对象**提供数值。

在当前收缩后的 v2 里，参数记录挂载在两类对象上：

- `PriorRecord` 挂在 **GlobalCanonicalKnowledgeStore** 的 canonical claim（`gcn_`）上
- `StrategyParamRecord` 挂在 **local Strategy 引用**上，例如 `LocalStrategyRef(package_id, version, strategy_id)`

也就是说：

- claim 的 prior 是全局共享的
- Strategy 的 conditional probabilities 仍然跟着 local graph 中的那条 Strategy

这与 Gaia IR 的边界保持一致：

- global 层只统一命题身份
- local 层保留完整推理结构
- runtime 真正要跑时，再从 selected local graphs 派生出可计算视图

Gaia IR 结构定义见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md)。BeliefState 见 [belief-state.md](belief-state.md)。整体关系见 [overview.md](overview.md)。

## 存储层：原子记录

数据库中存储的是独立的参数记录，每条记录携带来源信息：

```
PriorRecord:
    gcn_id:             str              # canonical claim ID（gcn_ 前缀）
    value:              float            # ∈ (ε, 1-ε)
    source_id:          str              # 哪个 ParameterizationSource 产出的
    created_at:         str              # ISO 8601

LocalStrategyRef:
    package_id:         str
    version:            str
    strategy_id:        str              # local Strategy ID（lcs_ 前缀）

StrategyParamRecord:
    strategy_ref:                   LocalStrategyRef
    conditional_probabilities:      list[float]
    source_id:                      str
    created_at:                     str

ParameterizationSource:
    source_id:          str              # 唯一 ID
    model:              str              # "gpt-5-mini" | "claude-opus" | ...
    policy:             str | None       # "conservative" | "aggressive" | 自定义策略名
    config:             dict | None      # threshold, prompt version 等具体配置
    created_at:         str              # ISO 8601
```

`StrategyParamRecord` 指向的是**某条 local Strategy**，不是某个 persistent global strategy。server curation 若提交的是特殊来源的 local/curation package，也使用同样的 `LocalStrategyRef` 方案。

## 关键规则

- **PriorRecord 只对 canonical claim 生效**：只有 `type=claim` 的 `gcn_` 有 prior。`setting` 与 `question` 不参与概率推理。
- **StrategyParamRecord 只对 local Strategy 生效**：它描述的是某条 local 推理在折叠模式下的条件概率。
- **Operator 没有参数记录**：Operator 是确定性结构约束。
- **一个 claim / Strategy 可以有多条记录**：来自不同 `source_id` 的 review、模型或校准流程。
- **Cromwell's rule**：所有概率值钳制到 `[ε, 1-ε]`，其中 `ε = 1e-3`。

## 参数语义

### PriorRecord

PriorRecord 表示某个 canonical claim 的基础可信度。它作用在 `gcn_` 上，因此不同 local package 中映射到同一 `gcn_` 的 claim 共享同一个 prior 空间。

这正是 claim canonicalization 的意义：

- 如果一个 local claim 命中已有 `gcn_`，它复用同一条 canonical prior 轴
- 如果没有命中，就创建新的 `gcn_`，后续由 review 为其补充 PriorRecord

### StrategyParamRecord

StrategyParamRecord 表示某条 local Strategy 在**折叠模式**下的条件概率参数。

它不试图把 Strategy 提升为 persistent global 对象，而是保持：

- 结构留在 local graph
- 参数也继续挂在该 local Strategy 上
- runtime projection 只负责把这条 local Strategy 的 endpoints 映射到对应的 `gcn_`

因此，`StrategyParamRecord` 的作用对象始终是：

- 某条具体的 local Strategy
- 某个具体的 package/version

## 不同 Strategy 类型的参数

Strategy 的参数化模型由 `type` 决定：

- `infer`：完整条件概率表（CPT），参数个数是 `2^k`
- `noisy_and`：单参数 `[p]`
- 命名策略（`deduction` / `abduction` / `induction` / `analogy` / `extrapolation` / ...）：
  - 如果 runtime 将其**折叠**为一条 coarse support edge，则仍通过 `conditional_probabilities` 提供参数
  - 如果 runtime 将其**展开**为子策略或 Operator 结构，则由展开后的结构参与计算

这意味着：

- Parameterization 记录的是“当前 runtime 如何消费这条 local Strategy”所需的参数
- 它不是 Graph IR 本体层对 Strategy 的重新建模

## 运行时：Resolution Policy 与 Projection Policy

运行前，需要同时确定两类策略：

1. **Projection policy**：本次运行选择哪些 local package / curation package
2. **Resolution policy**：从原子参数记录中选择哪些 PriorRecord / StrategyParamRecord

典型 resolution policy：

| policy | 说明 |
|--------|------|
| **latest** | 每个对象取最新的记录（按 `created_at`） |
| **source:\<source_id\>** | 指定使用某个 ParameterizationSource 的记录 |

运行时组装步骤：

1. 选择要参与本次运行的 local packages
2. 读取其中的 local `Knowledge / Strategy / Operator`
3. 用 `CanonicalBinding` 将其中的 `lcn_` 映射到 `gcn_`
4. 为涉及的 `gcn_` 选择 PriorRecord
5. 为将以折叠模式运行的 local Strategy 选择 StrategyParamRecord
6. 根据 `expand_set` 决定哪些 Strategy 展开、哪些保持折叠
7. 编译出临时 runtime projection 并运行 BP 或其他下游算法

这个 runtime projection 是：

- derived
- rebuildable
- implementation-facing

而不是 protected Graph IR contract 的 persistent 对象。

## 多分辨率运行

当前 BP 路径接受 `expand_set`（需要展开的 local Strategy 引用集合），根据 Strategy 形态和展开决策选择路径：

- **local Strategy 不在 expand_set 中 → 折叠**
  使用该 local Strategy 对应的 `StrategyParamRecord.conditional_probabilities`

- **CompositeStrategy 在 expand_set 中 → 展开**
  递归进入子策略

- **FormalStrategy 在 expand_set 中 → 展开**
  进入 `formal_expr` 中的 Operator 结构

是否展开是 runtime 决策，而不是 persistent global contract 的结构属性。

## 完整性检查

完整性检查针对的是**当前 runtime projection**，而不是整个仓库里所有对象。

运行前至少需要满足：

- 当前 projection 中每个参与推理的 canonical claim（`gcn_`）都有可用的 PriorRecord
- 当前 projection 中每个将以折叠模式运行的 local Strategy 都有可用的 StrategyParamRecord
- Operator 不需要参数记录

如果某条 FormalStrategy 被完全展开，则是否还需要其折叠参数，取决于本次 runtime 是否真的要把它当作一条 coarse support edge 使用。

## Prior 与 Strategy 参数的来源

### Prior 来源

每个 canonical claim 的 prior 由 review、research 或其他 calibration 流程赋值。Gaia IR 本身不定义聚合逻辑，只定义记录格式与引用对象。

### Strategy 参数来源

- `infer`：完整 CPT，由 review 赋值；旧 `soft implication` 可视为其单前提/低维特例
- `noisy_and`：单参数 `[p]`，由 review 赋值
- 命名策略：折叠时仍可使用 `conditional_probabilities`，展开时由内部结构参与运行
- 特殊来源的 curation package：与普通 local package 一样，通过 `LocalStrategyRef` 取参

## 与 global core 的关系

当前方案下，Parameterization 不要求以下 persistent global 对象：

- 不需要 persistent global Strategy
- 不需要 persistent global Operator set

它只依赖：

- `gcn_` canonical claim
- `CanonicalBinding`
- local Strategy 的稳定引用

这使得 Graph IR core 保持轻量，而 runtime 仍然可以通过 projection 获得完整的可计算结构。

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `StrategyParamRecord`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, runtime 编译
