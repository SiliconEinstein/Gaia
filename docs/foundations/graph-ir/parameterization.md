# Parameterization — 参数定义

> **Status:** Target design

Parameterization 作用在 **GlobalCanonicalGraph** 上，编码每个全局节点和算子的概率值。它通过 `graph_hash` 绑定到特定版本的全局图。

Graph IR 结构定义见 [graph-ir.md](graph-ir.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

## Schema

```
Parameterization:
    graph_hash:         str                            # 绑定到 GlobalCanonicalGraph 的哈希

    # ── 节点参数 ──
    node_priors:        dict[str, Prior]               # 以 gcn_ ID 为键
                                                       # 只有 type=claim 的节点有 entry

    # ── 算子参数 ──
    factor_params:      dict[str, FactorParams]        # 以 factor_id 为键
                                                       # 所有 category 都有 entry

Prior:
    value:              float                          # ∈ (ε, 1-ε)
    source:             str                            # "review" | "aggregated"
    sources:            list[PriorSource] | None       # 聚合时记录各来源

FactorParams:
    probability:        float                          # ∈ (ε, 1-ε)
    source:             str                            # "review" | "toolcall_reproducibility" | ...

PriorSource:
    package:            str
    local_id:           str
    value:              float
    source:             str                            # "author" | "review"
```

## node_priors：只对 Claim

只有 `type=claim` 的 knowledge 节点有 prior。Setting、Question、Template 不出现在 `node_priors` 中——它们不参与 BP，没有 probability 的概念。

一个 global 节点可能由多个 local 节点映射而来，各自有不同的 prior。`Prior.sources` 记录各来源，`Prior.value` 是聚合后的结果。聚合方法（取最大值、均值、贝叶斯更新等）是可配置的实现细节。

## factor_params：所有 category 都有

**所有 factor（infer、toolcall、proof）都有 probability 接口。** 这是统一的设计：

- `infer`：概率由 review 赋值，反映推理的可信度
- `toolcall`：可根据计算的可复现性打分（具体策略后续定义）
- `proof`：有效证明可设为 1.0（具体策略后续定义）

Probability 存储在参数化覆盖层中，不内联在 FactorNode 结构里。这样同一个 factor 结构可以有不同 reviewer 给出的不同 probability。

## 完整性要求

有效的 Parameterization 必须提供：
- GlobalCanonicalGraph 中每个 `type=claim` 节点的 prior
- GlobalCanonicalGraph 中每个 factor 的 probability

缺少条目会使覆盖层无效。BP 不回退到隐式默认值。

## Cromwell's rule

所有 prior 和 probability 被钳制到 `[ε, 1-ε]`，其中 `ε = 1e-3`。这防止 BP 中出现退化的零配分函数状态。

## 图哈希完整性

`graph_hash` 充当版本锁：Parameterization 必须绑定到它所参数化的 GlobalCanonicalGraph 的确切版本。当全局图发生变化（新包摄入、curation 修改），Parameterization 需要更新。

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `FactorParams`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell 钳制
