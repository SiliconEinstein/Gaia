# 参数化

> **Status:** Target design — 基于结构/参数/信念三层分离原则重新设计

Graph IR 将**结构、参数、信念**严格分离为三个独立对象。

## 原则

```
Graph IR（结构）          ← 编译时确定，review 不改变
    ×
Parameterization（参数）  ← review 产出，可多版本
    →
BeliefState（信念）       ← BP 计算结果
```

- **结构**（Graph IR）：由源码确定性产生，在发布时提交，可由审查引擎重新验证。
- **参数**（Parameterization）：由 review 推导，不在发布时提交。同一结构图可以有不同参数化。
- **信念**（BeliefState）：由 BP 计算，绑定到特定的结构+参数组合。

三者通过 `graph_hash` 和 `parameterization_hash` 绑定，可独立版本化。

## Parameterization

```
Parameterization:
    graph_hash:         str                            # 绑定到哪个图结构
    scope:              str                            # "local" | "global"

    # ── 节点参数 ──
    node_priors:        dict[str, Prior]               # 以 knowledge node ID 为键
                                                       # 只有 type=claim 的节点有 entry

    # ── 算子参数 ──
    factor_params:      dict[str, FactorParams]        # 以 factor_id 为键
                                                       # 所有 category 都有 entry

Prior:
    value:              float                          # ∈ (ε, 1-ε)
    source:             str                            # "author" | "review" | "aggregated"

FactorParams:
    probability:        float                          # ∈ (ε, 1-ε)
    source:             str                            # "author" | "review" | "toolcall_reproducibility" | ...
```

### node_priors：只对 Claim

只有 `type=claim` 的 knowledge 节点有 prior。Setting、Question、Template 不出现在 `node_priors` 中——它们不参与 BP，没有 probability 的概念。

### factor_params：所有 category 都有

**所有 factor（infer、toolcall、proof）都有 probability 接口。** 这是统一的设计：

- `infer`：概率由 review 赋值，反映推理的可信度
- `toolcall`：可根据计算的可复现性打分（具体策略后续定义）
- `proof`：有效证明可设为 1.0（具体策略后续定义）

Probability 存储在参数化覆盖层中，不内联在 FactorNode 结构里。这样同一个 factor 结构可以有不同 reviewer 给出的不同 probability。

### 完整性要求

有效的 Parameterization 必须提供：
- 每个 `type=claim` 节点的 prior
- 每个 factor 的 probability

缺少条目会使覆盖层无效。BP 不回退到隐式默认值。

### Cromwell's rule

所有 prior 和 probability 被钳制到 `[ε, 1-ε]`，其中 `ε = 1e-3`。这防止 BP 中出现退化的零配分函数状态。

### 不提交

Local parameterization **不**在 `gaia publish` 期间提交。它仅用于作者通过 `gaia infer` 进行本地预览。审查引擎做出独立的概率判断。

## BeliefState

```
BeliefState:
    graph_hash:              str         # 绑定到哪个图结构
    parameterization_hash:   str         # 绑定到哪个参数化
    bp_run_id:               str         # 唯一运行 ID
    scope:                   str         # "local" | "global"

    # ── 信念 ──
    beliefs:                 dict[str, float]   # 以 knowledge node ID 为键
                                                 # 只有 type=claim 的节点有 belief

    # ── 诊断 ──
    converged:               bool
    iterations:              int
    max_residual:            float
```

BeliefState 是 BP 的**纯输出**。它通过 `graph_hash + parameterization_hash` 双重绑定到产生它的结构和参数。同一个参数化可以有多次 BP 运行（例如不同调度策略）。

## Global Parameterization

Global 参数化与 local 使用相同的 `Parameterization` schema，但有一个额外问题：一个 global 节点可能由多个 local 节点映射而来，各自有不同的 prior。

```
GlobalParameterization extends Parameterization:
    node_priors: dict[gcn_id, AggregatedPrior]

AggregatedPrior:
    value:       float                         # 聚合后的 prior
    method:      str                           # "max" | "mean" | "bayesian_update" | ...
    sources:     list[PriorSource]             # 各来源的 prior

PriorSource:
    package:     str
    local_id:    str
    value:       float
    source:      str                           # "author" | "review"
```

聚合策略是 global parameterization 的职责。具体聚合方法（取最大值、均值、贝叶斯更新等）是可配置的实现细节。

## 范围差异

| | Local | Global |
|---|---|---|
| **范围** | 单个包 | 所有已摄入的包 |
| **图** | LocalCanonicalGraph | GlobalCanonicalGraph |
| **ID 命名空间** | `lcn_` | `gcn_` |
| **管理者** | 作者（本地工具） | 注册中心（服务器） |
| **Prior 来源** | 单一 review | 聚合多个来源 |
| **是否提交** | 否 | 不适用（服务器端） |

## 图哈希完整性

图哈希充当版本锁：

1. `gaia build` 产生具有确定性序列化的 `local_canonical_graph.json`
2. 计算 `local_graph_hash = SHA-256(canonical JSON)`
3. `Parameterization.graph_hash` 必须与当前图哈希匹配
4. 审查期间，审查引擎从源码重新编译并验证哈希匹配

这确保参数化是为正在审查的确切图生成的。

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `FactorParams`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell 钳制
