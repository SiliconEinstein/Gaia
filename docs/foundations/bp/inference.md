# Gaia IR 上的 BP 推理

> **Status:** Current canonical

本文档描述 belief propagation 如何在 Gaia IR 上运行。纯 BP 算法（sum-product 消息传递、damping、收敛）见 [../theory/07-belief-propagation.md](../theory/07-belief-propagation.md)。Factor potential 函数见 [potentials.md](potentials.md)。Local 与 global 推理的区别见 [local-vs-global.md](local-vs-global.md)。backend-facing lowering 边界见 [../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)。

## FactorGraph

### 概念

FactorGraph 是 variable node（变量节点）和 factor node（因子节点）之间的二部图。它是 BP 算法操作的数据结构，由 Gaia IR 经过 [lowering](../gaia-ir/07-lowering.md) 产生。

FactorGraph 是一个**概念**，不绑定特定的存储或运行方式：
- CLI 本地推理时，FactorGraph 在内存中临时构建
- LKM 全局推理时，FactorGraph 持久化在存储中，BP 引擎从中读取

### 结构

- **Variable nodes**：每个 knowledge 节点成为一个二值变量，携带先验信念 `p(x=1)`。
- **Factor nodes**：每个包含 `variables`、`conclusion`、`factor_type`，以及参数化因子的 `p1`/`p2`（SOFT_ENTAILMENT）或 `cpt`（CONDITIONAL）。

### 实现

**v1（Graph IR 管线）**：`libs/inference/factor_graph.py`，使用 int 索引、`premises`/`conclusions`/`edge_type` 字符串。供 `scripts/pipeline/run_local_bp.py` 等包内 BP 使用。

**v2（理论对齐 BP 引擎）**：`gaia/bp/factor_graph.py`，使用字符串 ID、八种 `FactorType`（六种确定性 + SOFT_ENTAILMENT + CONDITIONAL）、`variables` + `conclusion` 结构。势函数见 [potentials.md](potentials.md)。包含 loopy BP、Junction Tree、GBP、exact brute-force、`InferenceEngine` 自动选择。

### 从 Gaia IR 构建

- **Graph IR → v1**：适配器 `libs/graph_ir/adapter.py`，将 Knowledge QID 映射为整数 ID。
- **Gaia IR（`LocalCanonicalGraph`）→ v2**：`gaia.bp.lowering.lower_local_graph()`，契约见 [../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)。Operator → 确定性因子；`noisy_and` → CONJUNCTION + SOFT_ENTAILMENT；`infer` → CONDITIONAL 或可选 degraded ∧+↝；FormalStrategy → expand（内部 Operator 逐一 lower）或 fold（NotImplementedError，待设计）。

### Cromwell's rule

所有先验概率和 factor 概率被钳制到 `[epsilon, 1 - epsilon]`，其中 `epsilon = 1e-3`（见 `factor_graph.py:CROMWELL_EPS`）。这可防止 BP 期间出现退化的零配分函数状态，零概率会阻断所有后续证据更新。

## 消息计算

消息是 2 维向量 `[p(x=0), p(x=1)]`，始终归一化使总和为 1。这是 `Msg` 类型（NumPy `NDArray[float64]`，形状 `(2,)`）。

### 同步调度

每次迭代：

1. **Variable-to-factor 消息**：对每条 `(variable, factor)` 边，消息是该变量的先验乘以所有传入的 factor-to-var 消息的乘积（排除当前 factor——排除自身规则）。

2. **Factor-to-variable 消息**：对每条 `(factor, variable)` 边，遍历其他变量的所有 2^(n-1) 种赋值，以 factor potential 和传入的 var-to-factor 消息加权进行边际化。

3. **Damping 和归一化**：新消息通过 `damping * new + (1 - damping) * old` 与旧消息混合，然后归一化。

4. **计算信念值**：每个变量的信念值是其先验乘以所有传入 factor-to-var 消息的乘积，再归一化。

5. **检查收敛**：如果任何信念值的最大绝对变化低于阈值，则停止。

### Conclusion 先验与约束激活

所有 Operator 统一为 CONDITIONAL 三元因子。Relation operator（equivalence / contradiction / complement）的 conclusion 使用 $\pi = 1-\varepsilon$（断言"关系成立"），约束自然激活，不需要 gate_var 或其他门控机制。Directed operator（conjunction / disjunction / implication）的 conclusion 使用 $\pi = 0.5$（计算输出），belief 由 variables 决定。详见 [formal-strategy-lowering.md §2](formal-strategy-lowering.md)。

## 参数

| 参数 | 默认值 | 描述 |
|---|---|---|
| `damping` | 0.5 | 消息更新的混合因子。1.0 = 完全替换，0.0 = 保持旧值。 |
| `max_iterations` | 50 | 消息传递轮次的上限。 |
| `convergence_threshold` | 1e-6 | 当最大信念变化低于此值时停止。 |

## 诊断

`run_with_diagnostics()` 返回一个 `BPDiagnostics` 对象，包含：

- **`iterations_run`**：执行了多少次迭代。
- **`converged`**：是否达到收敛阈值。
- **`max_change_at_stop`**：最终迭代中的最大信念变化。
- **`belief_history: dict[int, list[float]]`**：每个变量跨迭代的信念轨迹。用于可视化和调试。
- **`direction_changes: dict[int, int]`**：每个变量信念增量的符号反转次数。高计数表示振荡，这是冲突检测的信号——该变量从图的不同部分接收到矛盾证据。

## Schema/Ground 交互

### 本地包 BP

在单个包内，schema 和 ground 节点通过二元 instantiation factor 交互：

```
V_schema
    |-- F_inst_1: premises=[V_schema], conclusion=V_ground_1
    |-- F_inst_2: premises=[V_schema], conclusion=V_ground_2
```

BP 同时计算所有 local canonical 节点的信念值。正向消息从 schema 流向 instance（演绎支持）。反向消息从 instance 流向 schema（归纳证据）。Instantiation potential 函数见 [potentials.md](potentials.md)。

### 全局图 BP

包发布后，来自不同包的 schema 节点可能共享一个 global canonical 节点。一个包的 ground 实例的证据通过共享的 schema 间接支持其他包的 ground 实例：

```
Package A:  F_inst_a: premises=[V_schema], conclusion=V_ground_a
Package B:  F_inst_b: premises=[V_schema], conclusion=V_ground_b
                               ^ shared schema node
```

这是通过共享抽象知识实现的跨包证据传播。

## 源代码

- `libs/inference/bp.py` -- `BeliefPropagation`, `run_with_diagnostics()`
- `libs/inference/factor_graph.py` -- `FactorGraph`, `CROMWELL_EPS`
- `libs/graph_ir/adapter.py` -- 从 Gaia IR 构建 `FactorGraph`
