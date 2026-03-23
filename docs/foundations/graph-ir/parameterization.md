# 参数化

> **Status:** Current canonical

Graph IR 有意将结构与参数分离。Factor graph 拓扑（节点和边）是确定性的且可审计的。先验概率、条件概率和信念值存在于通过哈希引用图的独立覆盖层对象中。

## 原则

结构是编写并提交的。参数是推导出来的，且与运行时相关。

- **结构**（Graph IR）：由源码确定性产生，在发布时提交，可由审查引擎重新验证。
- **参数**（覆盖层）：本地推导用于预览，或由注册中心管理用于全局推理。不在发布时提交。

这种分离意味着相同的结构图可以使用不同的概率输入进行推理——作者的本地预览、审查者的独立评估，以及注册中心的全局状态。

## LocalParameterization 覆盖层

```
LocalParameterization:
    graph_hash:         str                          # SHA-256 of the canonical JSON
    node_priors:        dict[str, float]             # keyed by local_canonical_id
    factor_parameters:  dict[str, FactorParams]      # keyed by factor_id

FactorParams:
    conditional_probability: float                   # reasoning factors only
```

`graph_hash` 将此覆盖层绑定到 local canonical graph 的特定版本。如果图发生变化（例如，重新运行 `gaia build` 后），覆盖层将失效，必须重新生成。

### 键解析

- `node_priors` 以 `local_canonical_id` 为键。允许使用完整 ID 或无歧义前缀。
- `factor_parameters` 以 `factor_id` 为键。允许使用完整 ID 或无歧义前缀。

### 完整性要求

有效的覆盖层必须提供：
- 活跃 local graph 中每个承载信念的节点的先验概率
- 该图中每个 reasoning/abstraction factor 的 `conditional_probability`

缺少条目会使覆盖层无效。BP 不会回退到隐式默认值。

### Cromwell's rule

当覆盖层被加载时，所有先验概率和条件概率被钳制到 `[epsilon, 1 - epsilon]`，其中 `epsilon = 1e-3`。这可防止 BP 期间出现退化的零配分函数状态。

### 不提交

Local parameterization 覆盖层**不**在 `gaia publish` 期间提交。它仅用于作者通过 `gaia infer` 进行本地预览推理。审查引擎会做出独立的概率判断。

## GlobalInferenceState

```
GlobalInferenceState:
    graph_hash:         str                          # hash of the global canonical graph
    node_priors:        dict[str, float]             # keyed by full global_canonical_id
    factor_parameters:  dict[str, FactorParams]      # keyed by factor_id
    node_beliefs:       dict[str, float]             # keyed by full global_canonical_id
    updated_at:         str                          # ISO timestamp
```

`GlobalInferenceState` 由注册中心管理，而非由包作者编写。它可能从已批准的审查报告判断中种子初始化，但审查报告本身不是 BP 输入产物。注册中心/运行时代码在 BP 运行前将这些判断归一化到当前全局图状态中。

### 范围差异

| | LocalParameterization | GlobalInferenceState |
|---|---|---|
| **范围** | 单个包 | 所有已摄入的包 |
| **图** | Local canonical graph | Global canonical graph |
| **ID 命名空间** | `local_canonical_id` | `global_canonical_id` |
| **管理者** | 作者（本地工具） | 注册中心（服务器） |
| **是否提交** | 否 | 不适用（仅限服务器端） |
| **是否包含信念值** | 否（信念值是 `gaia infer` 的输出） | 是（在 BP 运行间持久化） |

## 图哈希完整性

图哈希充当版本锁：

1. `gaia build` 产生具有确定性规范化 JSON 序列化的 `local_canonical_graph.json`。
2. 计算 `local_graph_hash = SHA-256(canonical JSON)`。
3. `LocalParameterization.graph_hash` 必须与当前图哈希匹配。
4. 审查期间，审查引擎从源码重新编译 raw graph 并验证哈希与提交的图匹配。

这确保了参数化是为正在审查的确切图生成的，且提交的图在编译后未被篡改。

## 源代码

- `libs/graph_ir/models.py` -- `LocalParameterization`, `FactorParams`
- `libs/inference/factor_graph.py` -- `CROMWELL_EPS`, Cromwell 钳制
- `docs/foundations/bp/local-vs-global.md` -- local 和 global 推理如何使用这些覆盖层
