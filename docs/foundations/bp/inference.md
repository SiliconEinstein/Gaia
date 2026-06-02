# Gaia IR 上的 BP 推理

> **Status:** Current canonical (v0.5 + BP refactor 2026-05-13)

本文档描述 belief propagation 如何在 Gaia IR 上运行。纯 BP 算法（sum-product 消息传递、damping、收敛）见 [../theory/07-belief-propagation.md](../theory/07-belief-propagation.md)。Factor potential 函数见 [potentials.md](potentials.md)。Local 与 global 推理的区别见 [local-vs-global.md](local-vs-global.md)。backend-facing lowering 边界见 [../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)。`gaia run infer` CLI 入口与 priors / dep_beliefs / depth 见 [../cli/inference.md](../cli/inference.md)。

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

`gaia/engine/bp/factor_graph.py` 是当前实现：使用字符串 ID、十种 `FactorType`（七种确定性 + SOFT_ENTAILMENT + CONDITIONAL + PAIRWISE_POTENTIAL）、`variables` + `conclusion` 结构。势函数见 [potentials.md](potentials.md)。配套算法分模块：

- **`gaia/engine/bp/trw_bp.py`** — TRW-BP (Tree-Reweighted Belief Propagation)，默认近似推理算法；当前启用 synchronous 调度，residual 调度代码尚未稳定开放
- **`gaia/engine/bp/junction_tree.py`** — Junction Tree exact inference，用于 treewidth ≤ 20 的图
- **`gaia/engine/bp/mean_field.py`** — Mean Field Variational Inference (CAVI)，大图（n > 2000）的 fallback，硬约束图精度不足（详见「推理算法 / Mean Field VI」）
- **`gaia/engine/bp/exact.py`** — 小图 brute-force，用于测试和验证
- **`gaia/engine/bp/engine.py`** — `InferenceEngine`：CLI 主路径；根据 n 和 treewidth 自动选择算法
- **`gaia/engine/bp/__init__.py`** — `infer(graph, method=auto)`：legacy 便利封装；阈值与 `InferenceEngine` **不一致**，仅用于不需要 CLI parity 的旧调用（详见下方“两条路径的差异”）
- **`gaia/engine/bp/lowering.py`** — `lower_local_graph()`：Gaia IR → FactorGraph 的入口

**算法选择策略（CLI `gaia run infer` → `InferenceEngine.run` → `EngineConfig`）：**
1. 如果 n > 2000 → **fallback 到 Mean Field VI 并发出 `UserWarning`**。大图推理仍在调研中，MF 在 Gaia 硬约束图上有 30%~79% 系统误差，不是生产级；显式 `method="trw_bp"` 可绕过（慢但准确）。
2. 否则估计 treewidth：
   - treewidth ≤ 20 → Junction Tree（精确）
   - treewidth > 20 → TRW-BP（近似）

> **⚠️ 两条路径的差异 — 不要混用 `gaia.engine.bp.infer()` 和 `InferenceEngine`。** 模块下方的 `infer(graph, method="auto")` 是为了兼容旧调用而保留的便利函数，它的 large-graph fallback 路由到 **loopy BP**（`gaia/engine/bp/__init__.py` `_LOOPY_BP_NODE_LIMIT = 2000`），而 CLI 的 `gaia run infer` 走 `InferenceEngine.run`，n > 2000 时改用 **Mean Field VI**。两者其它阈值相同（treewidth ≤ 20 用 Junction Tree，否则 TRW-BP）。**新代码或希望与 CLI 输出一致的代码应直接使用 `InferenceEngine`**；`infer()` 仅在不关心 CLI parity 的小图测试中用。

### 从 Gaia IR 构建

`gaia.engine.bp.lowering.lower_local_graph(graph, node_priors=None, review_manifest=None)` 把 `LocalCanonicalGraph` lower 成 `FactorGraph`：

- 每个 `Knowledge` 节点变成一个二值变量，prior 来源见下节Prior 赋值规则。
- 每个 `Operator` 通过 `_OPERATOR_MAP` 映射到对应的确定性 FactorType（IMPLICATION / NEGATION / CONJUNCTION / DISJUNCTION / EQUIVALENCE / CONTRADICTION / COMPLEMENT），CPT 由真值表决定（详见 [formal-strategy-lowering.md](formal-strategy-lowering.md)）。
- 每个 `Strategy(type=infer)` 变成 CONDITIONAL 因子，CPT 来自作者的 `p_e_given_h` / `p_e_given_not_h`（含 `given` 时按 v0.5 gating 收缩为 MaxEnt）。如果 `p_e_given_not_h` 是 DSL 默认的中性 `0.5`，`gaia build check` / `gaia run infer` 会提示作者在知道背景/假阳性率时显式给出该值。
- 每个 `Strategy(type=associate)` 变成 PAIRWISE_POTENTIAL 因子，直接连接两个 Claim 变量（无 helper conclusion）。joint weights 由 `p_a_given_b` / `p_b_given_a` 和已声明的端点边际 prior 推导；如果两个端点都没有声明边际 prior，则用局部 Jaynes MaxEnt closure 补完 2x2 joint table，并发出 warning 建议作者给至少一个端点补 `register_prior(...)`。
- 每个 `FormalStrategy`（包括所有 v5 命名策略 formalize 后的形态）按内部 Operator 逐一 lower。
- `CompositeStrategy` 递归 lower 子策略。
- `Compose` 不产生 BP 因子（它是 IR 一等节点但语义上是 authoring container）。
- 已废弃的 `noisy_and` 仍然支持：lower 为 CONJUNCTION + SOFT_ENTAILMENT。
- `review_manifest` 是可选的 publish/inquiry 视图参数：传入时，未
  accepted 的 action-backed strategy/operator targets 会被跳过。CLI
  `gaia run infer` 传 `None`，所以本地 preview 不因 review 状态抑制 belief
  输出。

契约详见 [../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md) 和 [cli/inference.md](../cli/inference.md)。

### Prior 赋值规则（Jaynes 严格语义）

Lowering 时，每个 Claim 变量的 prior 按以下优先级确定：

1. **Expression / formula helper claim**（兼容函数 `not_(A)` / `and_(A, B)` / `or_(A, B)` 生成的 `*_result` helper，或 `claim(formula=...)` 为嵌套 connective 生成的 `__...` helper；现代 `~A` / `A & B` / `A | B` 自身只是 Formula AST）→ 无 prior（MaxEnt 0.5）
2. **Relation conclusion**（EQUIVALENCE/CONTRADICTION/COMPLEMENT/IMPLICATION 的 conclusion）→ `add_evidence(1)`（hard evidence，Cromwell-softened 为 `1 - ε`）；graph relation assertion 优先于 `node_priors`
3. **`node_priors` 字典**（调用方显式传入）→ 用户指定值
4. **`metadata[prior]`** → 使用编译后的 claim prior。它可能来自 `priors.py`、inline `claim(prior=...)` compatibility shortcut、continuous predicate records、或 legacy `reason+prior` compatibility paths
5. **默认**（无任何 prior）→ MaxEnt（0.5）

**关键约束**：只有独立 probabilistic input 应该拥有外部 prior。直接写
`claim(prior=0.7)` 仍会生效，但只是低优先级 compatibility shortcut；
新包应优先把有来源的 prior 写进 `priors.py`。零前提 `observe(...)` 会给
结论一个默认 pin；如果同一 claim 有 resolved `metadata["prior"]`，编译后
的 metadata prior 会作为本地 preview 的数值来源。

这确保了 Jaynes 严格语义（Gaia 做了一个工程性调整）：
- **Class I (Hard Evidence)**：`add_evidence(var, {0, 1})`。Gaia 把严格 δ {0, 1} **调整为** Cromwell 钳制 {ε, 1-ε}（ε = `CROMWELL_EPS` = 1e-3），保留贝叶斯可更新性，避免 log(0) = -∞ 在消息传递中污染整条链。代价：hard-evidence 变量 belief 上限 1-ε 而非 1.0，与原教旨 Jaynes Class I 存在 O(ε) 系统偏差（参考实现 `jaynes_ref/` 仍保持严格 δ 作为 ground truth）。
- **Class IV (Unary Priors)**：`observe()` 或 `node_priors`，观测到的不确定信息
- **Class V (MaxEnt Free)**：其他所有待推断变量，默认 0.5

### Cromwell's rule

所有 unary prior / evidence 和 soft probability 参数都被钳制到
`[epsilon, 1 - epsilon]`，其中 `epsilon = 1e-3`（见
`factor_graph.py:CROMWELL_EPS`）。确定性 operator potential 本身仍是 strict
0/1 truth table。Cromwell clamp 防止 prior/evidence 侧出现不可更新的
绝对 0 或 1，并保持 TRW-BP / JT / MF / exact 所有路径在数值上是一致的
soft-prior 处理。

**实现位置**：
- `factor_graph.py::add_evidence` — 写入 `variables[v] = 1-ε` 或 `ε`
- `trw_bp.py` — v→f 消息、`_prior_for`、早期 return 路径全部返回 `[1-ε, ε]` / `[ε, 1-ε]`
- `junction_tree.py` — seeding clique potentials 与边际 prior 使用同一值
- `mean_field.py` — CAVI 初始 `mu[v] = 1-ε` 或 `ε`，并从 soft-var 列表中排除
- `exact.py` — brute-force log-joint 用 `log(1-ε)` / `log(ε)` 代替严格 -∞ mask

## 推理算法

### TRW-BP (Tree-Reweighted Belief Propagation)

**默认算法**，用于中等规模图（n ≤ 2000，treewidth > 20）。

- **原理**：通过 edge weights ρ_e ∈ (0,1] 对消息加权，保证 ELBO 单调上升（有界近似）
- **调度**：当前公开支持 synchronous（同步）。Residual priority queue 仍在代码中实验，但构造器会拒绝 `schedule="residual"`，因为该路径尚未稳定。
- **收敛性**：比 loopy BP 更稳定；residual 加速不是当前可用的用户承诺
- **参数**：
  - `damping`: 0.5（默认）
  - `max_iterations`: 200
  - `convergence_threshold`: 1e-8
  - `schedule`: synchronous

### Junction Tree

**精确推理**，用于 treewidth ≤ 20 的图。

- **原理**：将图三角化为树结构，在 clique tree 上精确传播
- **复杂度**：O(n · 2^tw)，tw 是 treewidth
- **限制**：tw > 20 时内存和时间开销过大
- **Treewidth 估计**：使用 min-fill heuristic（`jt_treewidth()`）

### Mean Field VI

**大图 fallback（带警告）**，n > 2000 时的 last resort。

- **原理**：假设 q(x) = ∏ q_i(x_i) 完全分解，CAVI 坐标上升优化 ELBO
- **复杂度**：O(n · F · 2^k) per sweep，k 是最大 factor arity
- **收敛性**：ELBO 单调非递减，保证收敛
- **精度限制（严重）**：Gaia 的硬约束（IMPLICATION/EQUIVALENCE）是 delta-like 势函数，本质强相关，直接违反 MF 的完全分解假设。实测在 5 组硬约束图上误差 3%~79%（Diamond loopy 79%，Chain-3 71%）。**不是生产级算法**。大图 auto 路由到 MF 时会发出 `UserWarning`，调研中的替代方案：分层推理（schema/ground 分离）、分布式 TRW-BP、GPU 加速 TRW-BP
- **参数**：
  - `max_iterations`: 500
  - `convergence_threshold`: 1e-6
  - `track_elbo`: False（开启会增加 O(F·2^k) 开销）

### Exact Inference

**Brute-force**，用于小图测试和显式 `method="exact"` 调试。

- **原理**：枚举所有 2^n 种赋值，计算精确边际概率
- **限制**：`InferenceEngine` 默认拒绝 n > 26（`exact_max_vars=26`）；测试和快速验证通常仍应保持在更小图上
- **用途**：作为其他算法的 ground truth

## 消息计算（TRW-BP）

消息是 2 维向量 `[p(x=0), p(x=1)]`，始终归一化使总和为 1。这是 `Msg` 类型（NumPy `NDArray[float64]`，形状 `(2,)`）。

### 同步调度

每次迭代：

1. **Variable-to-factor 消息**：对每条 `(variable, factor)` 边，消息是该变量的先验乘以所有传入的 factor-to-var 消息的乘积（排除当前 factor——排除自身规则），再加 ρ 权重。

2. **Factor-to-variable 消息**：对每条 `(factor, variable)` 边，遍历其他变量的所有 2^(n-1) 种赋值，以 factor potential 和传入的 var-to-factor 消息加权进行边际化，再加 ρ 权重。

3. **Damping 和归一化**：新消息通过 `damping * new + (1 - damping) * old` 与旧消息混合，然后归一化。

4. **计算信念值**：每个变量的信念值是其先验乘以所有传入 factor-to-var 消息的乘积，再归一化。

5. **检查收敛**：如果任何信念值的最大绝对变化低于阈值，则停止。

### Residual 调度

Residual priority-queue 调度仍保留在实现中用于后续实验，但当前
`TRWBeliefPropagation(schedule="residual")` 会报错。用户可依赖的 TRW-BP
路径是 synchronous sweep。

### Conclusion 先验与约束激活

每个 Operator 通过 `_OPERATOR_MAP` 映射到对应的确定性 FactorType
（IMPLICATION / NEGATION / CONJUNCTION / DISJUNCTION / EQUIVALENCE /
CONTRADICTION / COMPLEMENT）。确定性势函数本身是 strict delta
`{0, 1}`；Cromwell clamp 用在 unary evidence / prior 和 soft 参数上。
Relation operator（equivalence / contradiction / complement，以及非公式
connective 的顶层 implication）的 conclusion 使用 `add_evidence(1)`（断言
关系成立），约束自然激活。Expression operator（conjunction /
disjunction / negation，以及 formula connective implication）的 conclusion
使用 π = 0.5（计算输出），belief 由 variables 决定。FormalStrategy 中
deduction/support skeleton 的 implication 走特殊路径：helper 被消费并降成
`CONDITIONAL` / `SOFT_ENTAILMENT`。详见
[formal-strategy-lowering.md §2](formal-strategy-lowering.md)。

## 参数

| 参数 | TRW-BP | Junction Tree | Mean Field |
|---|---|---|---|
| `damping` | 0.5 | N/A | N/A |
| `max_iterations` | 200 | N/A | 500 |
| `convergence_threshold` | 1e-8 | N/A | 1e-6 |
| `schedule` | synchronous | N/A | N/A |
| `track_elbo` | N/A | N/A | False |

## 诊断

### TRWDiagnostics

`TRWBeliefPropagation.run()` 返回 `TRWResult`，包含 `TRWDiagnostics`：

- **`iterations_run`**：执行了多少次迭代。
- **`converged`**：是否达到收敛阈值。
- **`max_change_at_stop`**：最终迭代中的最大信念变化。
- **`belief_history: dict[str, list[float]]`**：每个变量跨迭代的信念轨迹。用于可视化和调试。
- **`direction_changes: dict[str, int]`**：每个变量信念增量的符号反转次数。高计数表示振荡，这是冲突检测的信号——该变量从图的不同部分接收到矛盾证据。

### MFDiagnostics

`MeanFieldVI.run()` 返回 `MFResult`，包含 `MFDiagnostics`：

- **`iterations_run`**：执行了多少次 CAVI sweep。
- **`converged`**：是否达到收敛阈值。
- **`max_change_at_stop`**：最终迭代中的最大 μ 变化。
- **`elbo_history: list[float]`**：每次迭代的 ELBO 值（如果 `track_elbo=True`）。
- **`belief_history: dict[str, list[float]]`**：每个变量的 μ_i 轨迹。

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

- `gaia/engine/bp/factor_graph.py` — `FactorGraph`, `FactorType`, `CROMWELL_EPS`
- `gaia/engine/bp/lowering.py` — `lower_local_graph()`：Gaia IR → FactorGraph
- `gaia/engine/bp/trw_bp.py` — `TRWBeliefPropagation`，默认近似推理
- `gaia/engine/bp/junction_tree.py` — Junction Tree exact inference
- `gaia/engine/bp/mean_field.py` — Mean Field VI（大图 fallback，硬约束图精度不足，warning）
- `gaia/engine/bp/exact.py` — brute-force exact inference for small graphs
- `gaia/engine/bp/engine.py` — `InferenceEngine`：根据 n 和 treewidth 自动选择算法
- `gaia/engine/bp/__init__.py` — `infer()`：统一推理入口
- `gaia/engine/bp/potentials.py` — 各 FactorType 的势函数
- `gaia/engine/bp/contraction.py` — 张量收缩工具（用于 fold-composite 等）
