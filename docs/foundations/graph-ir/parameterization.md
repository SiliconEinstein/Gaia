# Parameterization — 参数定义

> **Status:** Target design

Parameterization 是 GlobalCanonicalGraph 上的概率参数层。它由一组**原子记录**构成——每条记录是一个节点的 prior 或一个 factor 的 probability。不同 review 来源（不同模型、不同策略）产出不同的记录，BP 运行前按 resolution policy 组装成完整参数集。

Graph IR 结构定义见 [graph-ir.md](graph-ir.md)。BP 输出见 [belief-state.md](belief-state.md)。三者的关系见 [overview.md](overview.md)。

## 存储层：原子记录

数据库中存储的是独立的参数记录，每条记录携带来源信息：

```
PriorRecord:
    gcn_id:             str              # 全局 claim 节点 ID
    value:              float            # ∈ (ε, 1-ε)
    source_id:          str              # 哪个 ParameterizationSource 产出的
    created_at:         str              # ISO 8601

FactorParamRecord:
    factor_id:          str              # 全局 factor ID
    probability:        float            # ∈ (ε, 1-ε)
    source_id:          str              # 哪个 ParameterizationSource 产出的
    created_at:         str              # ISO 8601

ParameterizationSource:
    source_id:          str              # 唯一 ID
    model:              str              # "gpt-5-mini" | "claude-opus" | ...
    policy:             str | None       # "conservative" | "aggressive" | 自定义策略名
    config:             dict | None      # threshold, prompt version 等具体配置
    created_at:         str              # ISO 8601
```

**关键规则：**

- **PriorRecord 只对 Claim**：只有 `type=claim` 的节点有记录。Setting/Question/Template 不参与 BP。
- **FactorParamRecord 覆盖所有 category**：infer、toolcall、proof 都有 probability。
- **一个节点/factor 可以有多条记录**（来自不同 source），BP 运行时选择用哪条。
- **Cromwell's rule**：所有值钳制到 `[ε, 1-ε]`，ε = 1e-3。

## BP 运行时：Resolution Policy

BP 运行前，按 resolution policy 从原子记录中为每个节点/factor 选择一个值，组装成完整参数集：

| policy | 说明 |
|--------|------|
| **latest** | 每个节点/factor 取最新的记录（按 `created_at`） |
| **source:\<source_id\>** | 指定使用某个 ParameterizationSource 的记录 |

组装过程是**现算的**，不持久化。组装时使用 `prior_cutoff` 时间戳过滤记录——只取该时间点之前的记录，确保结果可重现（见 [belief-state.md](belief-state.md)）。BP 引擎在运行前验证组装结果的完整性：GlobalCanonicalGraph 中每个 claim 节点和每个 factor 都必须有对应的值，否则拒绝运行。

## Prior 来源

每个 global claim 节点的 prior 由 review 赋值。不存在聚合逻辑——canonicalization 对 premise 节点直接复用已有 global 节点（prior 不变），对 conclusion 节点创建新的 global 节点（prior 由 review 独立赋值）。

## Factor probability 来源

- `infer`：概率由 review 赋值，反映推理的可信度
- `toolcall`：可根据计算的可复现性打分（具体策略后续定义）
- `proof`：有效证明可设为 1.0（具体策略后续定义）
- Canonicalization 产生的 equivalent candidate factor 使用 placeholder probability，对应的新 global claim 节点也有 placeholder prior。两者均由后续 review 确定最终值

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `FactorParams`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell 钳制
