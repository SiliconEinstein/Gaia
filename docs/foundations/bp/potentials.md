# Factor Potential 函数

> **Status:** Current canonical（与 `gaia/bp/` v2 实现及 theory 对齐）

本文档定义 `gaia.bp` 中每种 **FactorType** 的势函数语义。理论依据：[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)。IR 算子与 lowering 契约：[../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md)、[../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)。

势函数对因子所连变量的联合赋值返回非负权重；无需归一化，仅比值有意义。所有经验概率遵守 Cromwell 规则（`CROMWELL_EPS = 1e-3`）。

## Factor 结构（variables + conclusion）

每个因子有：

- `variables`：输入变量 ID 列表（有序；对 CONDITIONAL，顺序决定 CPT 行索引）。
- `conclusion`：输出变量 ID（与 `variables` 不交）。
- 参数化因子额外携带：`SOFT_ENTAILMENT` 使用 `p1`, `p2`；`CONDITIONAL` 使用 `cpt`（长度 `2^k`）。

## 确定性算子（Cromwell 软化）

真值表一致时 ψ = `1 - CROMWELL_EPS`，否则 ψ = `CROMWELL_EPS`（代替硬 0/1）。

| FactorType | 语义 | 理论参照 |
|------------|------|---------|
| **IMPLICATION** | `variables=[A, B]`, `conclusion=H`：H=1 当 A→B 成立（禁止 A=1 且 B=0）；H=0 当违反 | 06-factor-graphs §3.3 |
| **CONJUNCTION** | `variables=[A₁,…,Aₖ]`, `conclusion=M`：M = ∧ Aᵢ | §3.2 |
| **DISJUNCTION** | `variables=[A₁,…,Aₖ]`, `conclusion=D`：D = ∨ Aᵢ | §3.6 补充 |
| **EQUIVALENCE** | `variables=[A,B]`, `conclusion=H`：H = 1 当且仅当 A=B | §3.4 |
| **CONTRADICTION** | `variables=[A,B]`, `conclusion=H`：H = 0 当且仅当 A=B=1；否则 H=1 | §3.5 |
| **COMPLEMENT** | `variables=[A,B]`, `conclusion=H`：H = XOR(A,B) | §3.1 / §3.6 |

所有确定性算子在因子图中统一为 **CONDITIONAL 三元因子**，上表中的真值语义对应各自的 CPT 模板。Conclusion 的先验决定其角色：**relation operator**（EQUIVALENCE / CONTRADICTION / COMPLEMENT / IMPLICATION）的 conclusion 是断言（$\pi = 1-\varepsilon$，激活约束）；**computation operator**（CONJUNCTION / DISJUNCTION）的 conclusion 是计算输出（$\pi = 0.5$，belief 由 variables 决定）。详见 [formal-strategy-lowering.md §2](formal-strategy-lowering.md)。

## SOFT_ENTAILMENT（软蕴含 ↝）

`variables=[M]`（单前提），`conclusion=C`，参数 `p1`, `p2`（须满足 `p1 + p2 > 1`）。

| M | C | ψ |
|---|---|---|
| 1 | 1 | p1 |
| 1 | 0 | 1−p1 |
| 0 | 0 | p2 |
| 0 | 1 | 1−p2 |

理论参照：06-factor-graphs §3.7。

- `p2 = 0.5`：前提为假时对 C 无信息（MaxEnt 默认；对应原「沉默」行为）。
- `p2 = 1 − ε`：前提为假时强烈压低 C=1（noisy-AND + leak 的 ↝ 部分）。

### 多前提 noisy_and 分解

多前提 `noisy_and` 在 lowering 中分解为 **CONJUNCTION(A₁,…,Aₖ → M)** 再 **SOFT_ENTAILMENT(M → C)**（理论 §3.8）。`k=1` 时省略 CONJUNCTION。

### 四个弱三段论

SOFT_ENTAILMENT 在 `p1 + p2 > 1` 时满足 07-belief-propagation.md §2.3 的全部四个弱三段论：

- **C1**（modus ponens 方向）：增强 M 的信念提升 C。
- **C2**（弱确认）：C 为真时提升 M 的信念。
- **C3**（modus tollens 方向）：C 为假时降低 M 的信念。
- **C4**（弱否认）：M 为假时降低 C 的信念。当 `p2 > 0.5` 时 C4 生效；`p2 = 0.5` 时 C4 保持中性（沉默）。

## CONDITIONAL（IR `infer` 完整 CPT）

`variables=[A₁,…,Aₖ]`, `conclusion=C`, `cpt` 长度 `2^k`。

- 行索引：`idx = Σᵢ assignment[Aᵢ] · 2^i`（与 `variables` 顺序一致）。
- `ψ = cpt[idx]` 当 C=1，否则 `ψ = 1 − cpt[idx]`。

IR 参照：02-gaia-ir §3.4 `infer` 类型。

可选 **degraded** lowering：用全为真/全为假两行压缩为 ∧ + ↝（信息损失）；默认使用 CONDITIONAL 保留完整 CPT。

## 与旧五类因子的迁移对照

| 旧 FactorType | 新表示 |
|---------------|--------|
| ENTAILMENT（沉默，单参数 p） | SOFT_ENTAILMENT，`p1=p, p2=0.5` |
| INDUCTION / ABDUCTION（noisy-AND） | CONJUNCTION + SOFT_ENTAILMENT，`p1=p, p2=1−ε` |
| CONTRADICTION（relation_var） | CONTRADICTION，`variables=[A,B], conclusion=R`（原 relation_var 即 conclusion） |
| EQUIVALENCE（relation_var） | EQUIVALENCE，同上 |

## 参考

- 消息传递与弱三段论：[../theory/07-belief-propagation.md](../theory/07-belief-propagation.md)
- 算子到势函数映射：[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)
- Lowering 契约：[../gaia-ir/07-lowering.md](../gaia-ir/07-lowering.md)
- 推理入口：[inference.md](inference.md)
