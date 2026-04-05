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

### 关系型算子的消息传递（Contradiction / Equivalence / Complement）

关系型算子（CONTRADICTION、EQUIVALENCE、COMPLEMENT）在 BP 中通过 **helper claim（三元因子的 conclusion）** 参与消息传递，而非直接约束两个变量的二元因子。这是 v2 架构与 v1 的关键区别。

#### 三元因子结构

IR 层的 `Operator(operator="contradiction", variables=[A, B], conclusion=H)` 在 lowering 后变成一个三元确定性因子，连接 A、B、H 三个变量节点。H 是 helper claim，语义为 `H = NOT(A AND B)`。

```
A ──┐
    ├── CONTRADICTION factor ψ(A,B,H) ── H (helper claim)
B ──┘
```

BP 在每次迭代中对该因子计算三条消息（与其他所有因子类型走完全相同的 `_compute_f2v` 逻辑，无特殊分支）：

- **f→A 消息**：遍历 B×H 的 4 种赋值，用 `contradiction_potential(A,B,H)` 加权，边际化得到关于 A 的消息。
- **f→B 消息**：遍历 A×H 的 4 种赋值，同理。
- **f→H 消息**：遍历 A×B 的 4 种赋值，得到关于 H 的消息。

#### Helper claim 的先验

Lowering 为关系型算子的 conclusion（helper H）设置接近 1.0 的先验（`1 - CROMWELL_EPS ≈ 0.999`），表示"约束默认成立"。这使得：

- **A 和 B 都为高信念时**：H 的信念被压向 0（因为 `ψ(1,1,1) = LOW`），factor→A 和 factor→B 的消息开始抑制它们同时为真。
- **A 和 B 不同时为真时**：H 保持高信念，约束处于活跃但无冲突状态。

#### v1 gate_var 与 v2 全参与的对比

| 方面 | v1（gate_var） | v2（当前实现） |
|------|--------------|-------------|
| H 的角色 | 只读门控变量，只提供信息不接收消息 | **全参与 BP 变量**，双向收发消息 |
| 反馈回路 | 被 gate_var 机制阻断 | 允许，由 damping + Cromwell 保证稳定性 |
| H 的信念更新 | 固定不变 | 随迭代更新，反映约束满足程度 |
| 振荡检测 | 不适用（H 不更新） | H 的 `direction_changes` 是 curation 冲突检测信号 |

#### 振荡行为

当图中存在张力（如 A→B 的软蕴含支持 B 为高，同时 contradiction(A,B,H) 要求 A 和 B 不同时为真），helper 变量 H 会在迭代中出现 belief 方向反转（`direction_changes > 0`）。在 v2 中，主变量（A、B）通常单调收敛，张力被 helper 变量吸收——这是 `BPDiagnostics.direction_changes` 的主要信号来源，被下游 curation 冲突检测消费（见 `docs/specs/2026-03-31-m6-curation.md` §Conflict Detection）。

#### Equivalence 和 Complement 的处理

与 Contradiction 完全同构，仅势函数真值表不同：

| 因子类型 | H 的语义 | H=1 当 | H=0 当 |
|---------|---------|--------|--------|
| CONTRADICTION | NOT(A AND B) | A 和 B 不同时为真 | A=1 且 B=1 |
| EQUIVALENCE | (A == B) | A 和 B 同真或同假 | A≠B |
| COMPLEMENT | (A XOR B) | A 和 B 恰好一真一假 | A=B |

三者在 BP 迭代中的消息传递路径完全一致——都是三元确定性因子，通过 `evaluate_potential` 统一调度。

## 参数

| 参数 | 默认值 | 描述 |
|---|---|---|
| `damping` | 0.5 | 消息更新的混合因子。1.0 = 完全替换，0.0 = 保持旧值。 |
| `max_iterations` | 50 | 消息传递轮次的上限。 |
| `convergence_threshold` | 1e-6 | 当最大信念变化低于此值时停止。 |

## 诊断

v2 中 `BeliefPropagation.run()` **始终**返回 `BPResult`（包含 beliefs + diagnostics），无需单独调用 `run_with_diagnostics()`。`BPDiagnostics` 字段：

- **`iterations_run`**：执行的完整迭代轮数。
- **`converged`**：是否因 max belief change < threshold 而提前终止。若为 `False`，表示达到 `max_iterations` 上限未收敛。
- **`max_change_at_stop`**：最终迭代中的最大信念变化。
- **`belief_history: dict[str, list[float]]`**：每个变量跨迭代的信念轨迹（iter_0 = 先验）。用于可视化、调试和振荡检测。
- **`direction_changes: dict[str, int]`**：每个变量信念增量的符号反转次数（BP 运行结束时自动由 `compute_direction_changes()` 填充）。高计数表示振荡——该变量从图的不同部分接收到矛盾证据。这是 curation 冲突检测的一级信号（`m6-curation.md` §Conflict Detection: `signal="oscillation"`）。
- **`treewidth`**：由 JT 引擎设置（-1 表示未计算或不适用）。

`BPDiagnostics.belief_table()` 可格式化输出跨迭代的信念历史表格，用于调试。

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

## 推理引擎（InferenceEngine）

v2 提供统一的 `InferenceEngine`，根据图的 treewidth 自动选择最优算法：

| 条件 | 算法 | 精确性 | 复杂度 |
|------|------|--------|--------|
| treewidth ≤ 15 | Junction Tree (JT) | 精确 | O(n · 2^w) |
| 15 < treewidth ≤ 30 | Generalized BP (GBP) | 近似（region 内精确） | O(regions · 2^w_region) |
| treewidth > 30 | Loopy BP | 近似（Bethe 自由能） | O(iterations · n · max_factor_size) |

也可通过 `method="jt"/"gbp"/"bp"/"exact"` 强制指定。`method="exact"` 使用暴力枚举（仅限 ≤ 26 变量）。

## 源代码

### v2（当前，理论对齐）

- `gaia/bp/bp.py` — `BeliefPropagation`（loopy BP）, `BPDiagnostics`, `BPResult`
- `gaia/bp/factor_graph.py` — `FactorGraph`, `FactorType`, `Factor`, `CROMWELL_EPS`
- `gaia/bp/potentials.py` — 八种 FactorType 的势函数 + `evaluate_potential` 统一调度
- `gaia/bp/exact.py` — `exact_inference`（暴力枚举，用于验证）
- `gaia/bp/junction_tree.py` — `JunctionTreeInference`（精确，O(n·2^w)）
- `gaia/bp/gbp.py` — `GeneralizedBeliefPropagation`（region 分解）
- `gaia/bp/engine.py` — `InferenceEngine`（自动选择）
- `gaia/bp/lowering.py` — `lower_local_graph`（Gaia IR → FactorGraph）

### v1（归档，Graph IR 管线）

- `libs/inference/bp.py` — 旧 BP（int ID, gate_var 机制）
- `libs/inference/factor_graph.py` — 旧 FactorGraph
- `libs/graph_ir/adapter.py` — 旧 Graph IR 适配器
