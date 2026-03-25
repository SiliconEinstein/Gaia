# Factor Potential 函数

> **Status:** Current canonical

本文档定义了每种 factor 类型的计算语义（potential 函数）。结构定义（schema、字段、编译规则）见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

Factor potential 是一个函数，接受其所连接变量的联合赋值并返回一个非负权重，编码该赋值与约束的兼容程度。Potential 不是概率——它们无需归一化。仅比值有意义。

## Reasoning Factor

覆盖 deduction（高 p）、induction（中等 p）和 abstraction（过渡性的）。所有类型使用相同的 potential 形状；chain 类型决定条件概率参数的期望范围，而非不同的 potential 函数。

### 当前实现——条件 potential

| 所有前提为真？ | 结论值 | Potential |
|---|---|---|
| 是 | 1 | `p`（条件概率） |
| 是 | 0 | `1 - p` |
| 否 | 任意 | `1.0`（无约束） |

当任何前提为假时，当前运行时不施加约束——factor 保持沉默，结论停留在其先验值。这是**当前**的 local BP 契约。

参数化输入：`factor_parameters[factor_id].conditional_probability`

### 目标模型——Noisy-AND + Leak

当前的全有或全无门控违反了 Jaynes 第四三段论（弱否认）：当前提为假时，结论应变得更不可信，而不仅仅是回到先验值。目标模型用 leak 概率替换沉默回退：

| 所有前提为真？ | 结论值 | Potential |
|---|---|---|
| 是 | 1 | `p` |
| 是 | 0 | `1 - p` |
| 否 | 1 | `epsilon`（leak——接近零） |
| 否 | 0 | `1 - epsilon` |

**Leak 概率**（Henrion 1989）编码"即使前提不全为真，结论成立的背景概率"。对于 Gaia 的推理链，前提是结论的近似必要条件，因此 leak 应该极小。默认值：`epsilon = Cromwell 下界 (1e-3)`。

**Noisy-AND** 是 noisy-OR 的对偶（Pearl 1988, Henrion 1989）。Noisy-OR 用于析取因果模型（任何原因都可产生效果）；noisy-AND 用于合取因果模型（所有条件必须成立）。完整 CPT 需要 2^n 个参数（n 个前提）；noisy-AND + leak 仅需 2 个：`p` 和 `epsilon`。

### 四个三段论验证

以 `pi_1=0.9, pi_2=0.8, p=0.9, epsilon=0.001` 为例：

**C 的边际概率**：
```
P(C=1) = p * pi_1 * pi_2 + epsilon * (1 - pi_1 * pi_2)
       = 0.9 * 0.72 + 0.001 * 0.28
       = 0.648
```

- **三段论 1**（modus ponens）：P(C=1 | P1=1, P2=1) = p = 0.9
- **三段论 2**（弱确认）：P(P1=1 | C=1) = 0.9997 > 0.9（结论为真提升前提信念）
- **三段论 3**（modus tollens）：P(P1=1 | C=0) = 0.716 < 0.9（结论为假降低前提信念）
- **三段论 4**（弱否认）：P(C=1 | P1=0) = epsilon = 0.001（前提为假强烈降低结论——旧模型会给出 0.5）

## Contradiction（mutex_constraint）

由以下声明生成：`#relation(type: "contradiction", between: (<A>, <B>))`。Relation 节点 R 作为 `premises[0]` 参与。

### Potential

| R（relation） | 所有被约束的 claim | Potential |
|---|---|---|
| 1 | 全部为真 | `epsilon`（接近零——几乎不可能） |
| 其他任意组合 | | `1.0`（无约束） |

其中 `epsilon = CROMWELL_EPS (1e-3)`。

### BP 行为

当 relation 处于活跃状态（R 具有高信念值）且两个矛盾的 claim 都有证据时，factor 发送抑制性反向消息：

1. **弱证据先屈服**：具有较低先验几率的 claim 被相同的抑制消息更强烈地压制，因为似然比在几率空间中运算。
2. **双方都有压倒性证据**：当两个 claim 都有非常强的证据时，factor 降低 relation 节点自身的信念——"质疑矛盾本身"。R 的似然比趋近 `1 - b_A * b_B`，当两个信念都趋近 1 时该值趋近零。
3. **Relation 节点作为参与者**：在目标设计中，R 是完全的 BP 参与者（非只读门控），支持双向信息流。当前运行时已将 R 放在 `premises[0]`，允许此行为。

## Equivalence（equiv_constraint）

由以下声明生成：`#relation(type: "equivalence", between: (<A>, <B>))`。Relation 节点 R 作为 `premises[0]` 参与。

### Potential

| R（relation） | Claim A | Claim B | Potential |
|---|---|---|---|
| 1 | A = B（一致） | | `1 - epsilon`（高兼容性） |
| 1 | A != B（不一致） | | `epsilon`（低兼容性） |
| 0 | 任意 | 任意 | `1.0`（无约束） |

### BP 行为

- **一致增强 relation**：当 A 和 B 具有相似信念值时，等价关系得到确认，R 的信念被推高。
- **不一致削弱 relation**：当 A 和 B 出现分歧时，BP 降低 R 的信念——系统质疑等价关系是否成立。
- **N 元分解**：对于 3 个以上节点的等价关系，分解为成对 factor `(R, A, B)`、`(R, A, C)`、`(R, B, C)`，全部共享同一 relation 节点 R。这意味着任何一对之间的不一致都会削弱整体等价关系。

## Retraction

由以下操作生成：`type: "retraction"` 的 chain。前提是反对结论的证据。

### Potential

| 所有前提为真？ | 结论值 | Potential |
|---|---|---|
| 是 | 1 | `1 - p`（被抑制） |
| 是 | 0 | `p` |
| 否 | 任意 | `1.0`（无约束） |

Retraction 是反向条件：当撤回证据存在时，结论被抑制而非被支持。撤回证据的缺席不是支持的证据——factor 保持沉默。

**为何沉默对 retraction C4 是正确的**：retraction 证据 E 不存在意味着这个针对 C 的特定论证消失。C 的信念值随后由其其他支持/反对 factor 决定。"没有反对证据"不等于"有支持证据"。

## Instantiation

由以下操作生成：schema 节点（参数化 knowledge）展开为 ground 实例。建模逻辑蕴含 forall x.P(x) -> P(a)。

### Potential

| Schema（前提） | Instance（结论） | Potential |
|---|---|---|
| 1（forall x.P(x) 成立） | 1（P(a) 成立） | `1.0` |
| 1（forall x.P(x) 成立） | 0（P(a) 不成立） | `0.0`（矛盾） |
| 0（forall x.P(x) 不成立） | 1（P(a) 成立） | `1.0`（实例可独立成立） |
| 0（forall x.P(x) 不成立） | 0（P(a) 不成立） | `1.0` |

这是确定性蕴含——不需要参数化的 `conditional_probability`。它强制执行：

- **正向（演绎）**：schema 被相信 -> 实例必须被相信。
- **反向（反例）**：实例被不信 -> schema 必须被不信。
- **无逆向归纳**：实例被相信 -> 对 schema 无约束（一个例子不能证明全称命题）。

### 通过 BP 消息聚合实现归纳强化

```
V_schema ---- F_inst_1 ---- V_ground_1 (belief=0.9)
         ---- F_inst_2 ---- V_ground_2 (belief=0.85)
         ---- F_inst_3 ---- V_ground_3 (belief=0.1)   <-- counterexample
```

每个 instantiation factor 向 V_schema 发送反向消息。BP 在共享的 schema 节点处聚合这些消息：

- V_ground_3 信念值低 -> 通过 F_inst_3 的反向消息推低 V_schema。
- V_schema 信念值下降 -> 通过 F_inst_1、F_inst_2 的正向消息削弱这些实例。
- 净效果：一个强反例削弱全称命题及其所有实例。

归纳推理自然地从 BP 的消息聚合中涌现——无需特殊逻辑。这是 Popper/Jaynes 的观点：一个反例强烈证伪全称命题，但任何数量的确认实例仅能渐进地支持它。

## Factor 类型总结

| Factor 类型 | 当前运行时名称 | 目标 BP 家族 | Potential 形状 |
|---|---|---|---|
| `reasoning` | `infer` / `deduction` / `induction` | `reasoning_support` | 条件（当前）/ Noisy-AND + leak（目标） |
| `abstraction` | `abstraction` | `deterministic_entailment`（过渡性） | 与 reasoning 相同（当前） |
| `instantiation` | `instantiation` | `deterministic_entailment` | 确定性蕴含 |
| `mutex_constraint` | `contradiction` / `relation_contradiction` | `constraint` | 全真惩罚 |
| `equiv_constraint` | `equivalence` / `relation_equivalence` | `constraint` | 一致/不一致 |
| `retraction` | `retraction` | `reasoning_support`（反向） | 反向条件 |

## 当前实现与目标对比

| 方面 | 当前 | 目标 |
|---|---|---|
| Reasoning potential | 全有或全无门控（任何前提为假时沉默） | Noisy-AND + leak（前提为假时抑制结论） |
| Relation 节点 | 门控变量（当前运行时有 `gate_var` 机制） | 完全 BP 参与者（无门控；双向消息） |
| 约束强度 | 由 relation 节点当前信念值固定 | 动态，由 BP 证据更新 |
| Abstraction | 独立的 factor 类型，使用类 infer 核 | 被接受的 abstraction 降级为 `deterministic_entailment` |

核心消息传递框架在当前实现和目标之间不变。仅 factor potential 函数和门控机制有所不同。

## 源代码

- `libs/inference/bp.py` -- `_evaluate_potential()`, `BeliefPropagation`
- `libs/inference/factor_graph.py` -- `FactorGraph`, `CROMWELL_EPS`
- `docs/foundations/theory/belief-propagation.md` -- 纯 BP 算法
- [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md) -- factor 结构定义
