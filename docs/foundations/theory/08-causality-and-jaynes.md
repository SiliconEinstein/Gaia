# 因果与 Jaynes：Gaia 的三层本体

> **Derivation chain position:** Layer 4 — Ontology Extension
> Plausible Reasoning → MaxEnt Grounding → Propositional Operators → … → **[this document]**
>
> 本文档解释 Gaia 在 v0.5 的纯命题框架之上引入 `Mechanism` 时的本体扩展，
> 以及 Pearl 的因果机制与 Jaynes 的命题概率框架在 Gaia 中如何各司其职、互相衔接。
> 它依赖 [`01-plausible-reasoning.md`](01-plausible-reasoning.md)（Cox 定理、三条规则）
> 和 [`02-maxent-grounding.md`](02-maxent-grounding.md)（MaxEnt / Min-KL）。

> **Status: Target design (v0.6+) — NOT current v0.5 contract.**
>
> 本文档不重写 v0.5 已有的命题层理论（[`01-plausible-reasoning.md`](01-plausible-reasoning.md) 与 [`02-maxent-grounding.md`](02-maxent-grounding.md) 在命题层完全有效）。它把因果机制的引入定位为**本体扩展**而非命题语义内的修正，并给出二者交汇的精确语义。
>
> **v0.5 mapping 提示——读到本文中具体名词时请按下表换算：**
>
> | 本文用词（v0.6+） | v0.5 IR 中的对应 |
> |---|---|
> | `Claim` | `Claim`（`KnowledgeType.claim`，仍然有效） |
> | `Action` | `Strategy`（基类）/ `CompositeStrategy` / `FormalStrategy` —— v0.5 IR 用 `Strategy` 这个词；`Action` 是 v0.6+ 设想的别称 |
> | `Mechanism` / `CausalFactor` | **v0.5 中没有对应的 IR 类型与 `FactorType`**——仅在本文档作为 v0.6+ 目标讨论 |
> | `mutilate()` / `do(...)` 查询 | **v0.5 不实现**；属于 v0.6+ 目标 |
>
> 因此：本文里像 `gaia build check --hole` 作用于 `Mechanism`、或 `Mechanism` 进入因子图等说法都是**目标设计**，**不是**当前 CLI 行为。v0.5 中所有与因果机制相关的认识论需求暂时都只能通过普通 `Claim` + `Strategy` + 关系算子（`equivalence` / `contradiction` / `complement`）的组合表达。
>
> 工程实现细节（IR schema、`mutilate()` 算法、do-calculus identification）参见对应 spec（`docs/specs/` 不在 published site，请通过 repo 浏览）：
>
> - [`2026-05-06-causal-mechanism-first-class-design.md`](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md)
> - [`2026-05-06-causal-counterfactual-binary-noise-design.md`](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-counterfactual-binary-noise-design.md)
> - [`2026-05-06-causal-transport-y0-design.md`](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-transport-y0-design.md)

## 1. 问题：Gaia 要回答的两类查询

[`01-plausible-reasoning.md`](01-plausible-reasoning.md) 和 [`02-maxent-grounding.md`](02-maxent-grounding.md) 解决了**观测性查询**：

> 给定证据 `E` 和背景信息 `I`，命题 `C` 应被赋予多大的 belief？

形式上：

```text
P(C | E, I)
```

这是 Jaynes-Cox 框架的原生问题域，BP 在因子图上计算它。

但科学论证里另有一类查询，纯命题框架原生处理不了：

> 如果**外部干预**把变量 `X` 强行设为 `x`，命题 `Y` 会变成多大概率？

形式上：

```text
P(Y | do(X = x), I)
```

以及更强的反事实查询：

```text
P(Y_{x'} | E, I)
```

读作"在现实里观测到证据 `E` 的情况下，假如当时 `X` 取的是 `x'` 而非实际值，那么 `Y` 会是什么"。

**关键事实**（Pearl 1995, *Causality* §1.3 反复证明）：在存在共同原因的图上，

```text
P(Y | X = x, I)  ≠  P(Y | do(X = x), I)
```

且这种差别**无法**通过对 `I` 添加任何概率约束来弥合。识别 `P(Y | do(X = x))` 需要**关于"X 是怎么生成的"的结构信息**——不是关于事件的信念，而是关于世界机制的声明。

v0.5 的命题层框架不承载这种信息。引入因果原语就是为了承载它。

## 2. Gaia 的三层本体

为容纳因果机制，Gaia 在 v0.6 把知识从 v0.5 的"全部都是命题"扩展到**三层本体**（参见 [mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §0）：

| 本体类型 | Gaia object | 例子 | 真值结构 | 是否进 BP |
|---------|---------------|------|---------|----------|
| **命题（Proposition）** | `Claim` | "H₃S 在 200 GPa 下是高温超导体" | 有真值，有 `prior = P(true)` | 是，作为 `ProbabilityFactor` |
| **推理步（Reasoning step）** | `Action`（`derive` / `infer` / `equal` / `contradict` / `associate` / …） | "由 X 逻辑推出 Y" | 没有真值（行为不是命题），其结论 claim 才有真值 | 间接，通过其结论 claim 进 BP |
| **世界结构（World structure）** | `Mechanism` | "吸烟通过焦油作用于肺癌" | **没有真值**——它要么是、要么不是结构性故事；不存在 `P(mechanism) = 0.7` | 是，作为 `CausalFactor`（不同于 `ProbabilityFactor`） |

三者职责互补，**不能互相归约**：

- 把 `Mechanism` 折叠成 `Claim` → `prior` 字段语义畸形（详见 §3）；
- 把 `Action` 折叠成 `Mechanism` → 失去推理图的结构；
- 把 `Claim` 折叠成 `Action` → 失去 belief 的承载者。

这个本体三分**不是 Gaia 独创的哲学发明**，它对应于科学认识论里早已被 Cartwright、Pearl、van Fraassen 等人反复指出的三类对象：

- **observable propositions**（命题）—— Jaynes 的天然辖区；
- **inferential moves**（推理）—— 论证理论的辖区；
- **causal mechanisms**（机制）—— Pearl 结构因果模型的辖区。

Gaia 把这三类显式区分到 IR 上，是为了让作者**写他/她想说的事**，而不是被迫把一切硬塞进"概率命题"里。

## 3. 为什么 `Mechanism` 不是 `Claim`

[mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §0 给出了五条工程症状，解释为什么把因果边塞进 `Claim(kind=CAUSAL)` 不通。这里只摘最 fundamental 的一条。

**`Claim.prior = P(claim 为真)` 这条契约，在因果机制上语义崩塌**。考虑：

```python
mechanism(cause=smoking, effect=lung_cancer, cpd=(0.15, 0.01))
```

它的语义有两个候选解读：

- (a) `prior = P(此机制存在)` — 即"吸烟确实通过某种因果链作用于肺癌"的可信度；
- (b) `prior = P(effect | cause = 1)` — 即给定吸烟时肺癌发生的条件概率（在这例子里就是 0.15）。

(a) 和 (b) 是**完全不同的数值**且**不能并存于同一字段**。如果把 `Mechanism` 当 `Claim`，`prior` 必须二选一，且无论选哪个都会让另一个语义在别处寄生（v0.5 老 spec 选 (a) 后被迫把 (b) 放进 `Cause` Action 的 metadata，又被编译器复制回 claim metadata，造成"metadata round-trip 是类型系统在告诉你这个字段长在错的地方"）。

更深层地：**(a) 是命题层问题（机制是否存在是个真值断言），(b) 是结构层声明（机制的强度参数）**。把两者合并即等于否认两层的本体差别。

`Mechanism` 解法：**结构层不带真值，结构层只带强度参数**。`Mechanism.cpd` 字段承载 (b)，IR validator 显式拒绝在 `Mechanism` 上写 `prior`。命题层若需要表达 (a)（"我对这个机制存在的可信度"），可以另写一个 `Claim`：

```python
mechanism_existence = claim(
    "Mechanism: smoking → lung_cancer",
    prior=0.95,
    rationale="Doll-Hill 1956 + reproducible meta-analyses",
)
mechanism(cause=smoking, effect=lung_cancer, cpd=(0.15, 0.01))
```

两者**显式分开，各管各的语义**。

## 4. v0.5 命题层的 Jaynesian 承诺：完全保留，但范围明确

v0.5 [`01-plausible-reasoning.md`](01-plausible-reasoning.md) 和 [`02-maxent-grounding.md`](02-maxent-grounding.md) 定义的内容：

- Cox 定理 → 概率是似然推理的唯一一致形式化；
- 加法规则、乘法规则、Bayes 规则；
- 联合分布 `p(x | I)` 是根对象，所有 belief 从它派生；
- 信息 = 对联合分布的约束（硬逻辑约束 + 软统计约束）；
- 没有旧分布时用 MaxEnt，有旧分布时用 Min-KL。

**这些命题在命题层完全成立，本文档不修改任何一条**。需要明确的只是**它们的辖区**：

> Cox / MaxEnt / Min-KL 描述的是**命题层内部**的规则。它们不声称命题层是 Gaia 的全部知识。

具体来说：

- 当 `I` 只包含命题约束时，v0.5 的 worked examples（[`02-maxent-grounding.md`](02-maxent-grounding.md) §6 Horn 规则、§7 软约束）**完全有效，无需任何修正**；
- 当 `I` 还包含 `Mechanism` 声明时，命题层 BP 仍按相同规则跑，只是因子图里多了 `CausalFactor`（来自 `Mechanism` lowering）和 `ProbabilityFactor` 共存——见 §5；
- 查询 `P(Y | do(X = x))` 时，**命题层 BP 在一个不同的因子图（mutilated FG）上跑**，但跑的还是同一套 BP 规则——见 §6。

也就是说：**Gaia 是 "Jaynesian on propositions, structurally extended for mechanisms"**。这不是哲学摇摆，是承认科学知识有多种本体类型而 Jaynes 的形式化只覆盖其中一种。

> **历史注**：Jaynes 本人（*Probability Theory: The Logic of Science* §3.6）反对 Pearl 的 do() 框架，主张"所有因果陈述都可还原为对适当背景信息 I 的条件化"。这个立场技术上自洽（你确实可以把 SCM 编码进 I），但操作上空洞——**真要识别因果效应你还得做 Pearl 在做的事**（d-separation、back-door criterion、ID algorithm），只是用 Jaynes 的记号而已。Gaia 选择**承认结构信息是另一种本体**，这与其说是反 Jaynes，不如说是把"Jaynes 框架到底覆盖到哪里"画清楚。

## 5. `Mechanism` 与命题层的交汇：FactorGraph

`Mechanism` 和 `Claim` 在 IR 上是平行的本体范畴，但它们最终都通过 lowering 进入**同一个因子图**：

```text
        IR                         FactorGraph (BP runs here)
        ──                         ──────────────────────────
                                                    ┌─────────────────┐
        Claim  ──────── lower ──────────────────►   │ ProbabilityFactor │
                                                    │ (modality=logical) │
                                                    └─────────────────┘
                                                    ┌─────────────────┐
        Mechanism ───── lower ──────────────────►   │  CausalFactor   │
                                                    │ (modality=causal) │
                                                    └─────────────────┘
                                                            │
                                                            ▼
                                                    BP messages flow
                                                    over both factor types
                                                    indistinguishably
                                                    (in observational mode)
```

**关键设计**（参见 [mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §6.3 与 §4.4）：

- 两类因子在因子图上**形式相同**——都是 `(variables, potential)` 对；
- 不同的是携带的 modality 标签（`CausalFactor` vs 其他逻辑/概率因子）；
- 在**观测性查询**模式下，BP 对两类因子**一视同仁**——modality 标签被忽略；
- 在**干预性查询**模式下（`do()`），modality 标签被使用——`mutilate()` 删除被干预节点的 `CausalFactor` 入边，但**保留**逻辑因子（详见 §6）。

这意味着：

> v0.5 的 BP 引擎处理含 `Mechanism` 的图时**不需要任何算法改动**——它只要把 `CausalFactor` 当作普通因子算出 marginal 即可。`Mechanism` 的因果性只在**查询时**通过 `mutilate()` 表达，不在 inference 内核内表达。

这个分工让 Gaia 同时享有：
- Jaynes 派的命题层一致性（BP / Cromwell / MaxEnt 全部不变）；
- Pearl 派的因果识别能力（`do()` / d-separation / back-door / ID algorithm）；
- 二者在因子图层面互不污染。

### 5.1 MaxEnt 在含 `Mechanism` 图上的语义

[`02-maxent-grounding.md`](02-maxent-grounding.md) 描述的 MaxEnt 是"在命题约束集 `C(I)` 下选熵最大的联合分布"。引入 `Mechanism` 后：

- `Mechanism` **不直接进入 `C(I)`**——它不是命题约束，没有真值，不能写成 `E[f(X)] = c` 这种等式约束的形式；
- `Mechanism` 通过 lowering 转成 `CausalFactor`，**直接给出条件概率 `P(effect | cause)`**——这是 fully specified 的局部分布，不是 MaxEnt 待选的自由度；
- 因此**`Mechanism` 节点上没有 MaxEnt 自由度**——`gaia build check --hole` 在 `Mechanism` 上不报告 prior_hole；
- 命题层的其他自由度（独立 `Claim` 没有 prior 时）仍按 v0.5 MaxEnt 处理，不受 `Mechanism` 引入影响。

实际效果：**MaxEnt 自由度只在命题层声明，结构层（`Mechanism`）的参数由作者直接给（`cpd=(α, β)`），没有 MaxEnt 选择**。这与 v0.5 [`02-maxent-grounding.md`](02-maxent-grounding.md) §3.3 描述的"乘积分解 = MaxEnt + 硬约束的自然结果"在数学上自洽——`CausalFactor` 是 fully-specified 的局部因子，它给乘积分解贡献一个完整的局部项，不参与 MaxEnt 优化。

## 6. `do()` 是查询，不是信息

这是 Gaia 因果语义最容易被误解的一点，必须明确：

> **`mechanism(cause=X, effect=Y, cpd=...)` 是结构声明，添加进 IR**；
> **`do(X = x).query(Y)` 是查询操作，不修改 IR**。

把这点和 v0.5 的纯命题层对比：

| v0.5 模式 | 添加进 IR 的东西 | 触发的查询 |
|----------|----------------|-----------|
| `claim("X is true", prior=0.7)` | `Claim` 节点 + `PriorRecord` | `gaia run infer` 计算 marginal |
| `observe(claim_X)` | observation `Action`（pin 到 1−ε） | 同上 |
| `derive(Y, given=[X])` | deduction `Action` | 同上 |

| v0.6 因果模式 | 添加进 IR 的东西 | 触发的查询 |
|--------------|----------------|-----------|
| `mechanism(cause=X, effect=Y, cpd=...)` | `Mechanism` 节点（含 `cpd`） | `do(X = x).query(Y)` 触发 mutilate + BP |

`do()` 之所以是查询而非信息，是因为它**不修改 `I`**——它在**同一个 `I`** 上发出"如果干预为 `X = x`，会发生什么"的问题。BP 在不同查询下用不同的因子图（observational 用原图，interventional 用 mutilated 图），但底层的 `I` 不变。

**形式化的 mutilate 语义**：给定查询 `do(X = x).query(Y)`，

1. 复制因子图 `FG → FG'`；
2. 在 `FG'` 中删除所有 `CausalFactor` 满足"其 conclusion ∈ {X}"——也就是切掉 X 的因果入边（详见 [mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §6.3）；
3. 在 `FG'` 中保留所有逻辑因子（`derive` lowering 出的 `SOFT_ENTAILMENT`、`IMPLICATION` operator 因子等）——干预世界不否认逻辑约束；
4. 在 `FG'` 中钳位 `X = x`；
5. 在 `FG'` 上跑标准 BP，读出 `Y` 的 marginal。

这个算法是 Pearl 的 truncated factorization 在因子图上的 modality-aware 实现。它**不引入新的 inference 概念**——只是在不同的因子图上跑同一个 BP。

### 6.1 为什么 `P(Y | X = x)` 和 `P(Y | do(X = x))` 不冲突

二者**计算在不同的因子图上**，给出不同的 marginal——这不是矛盾，是查询语义不同：

- `P(Y | X = x, I)`：原因子图 + observe(X = x) + BP → 这是观测性条件化；
- `P(Y | do(X = x), I)`：mutilated 因子图 + clamp(X = x) + BP → 这是干预性查询。

存在共因时二者数值不同，是 Pearl 反复论证的核心事实。Gaia 通过让作者**显式选查询语义**（用 `observe` 还是 `do`）而非显式选概率定义，把这个分歧落到 API 上。

## 7. Counterfactual：第三阶梯通过外生噪声材料化覆盖

[counterfactual-binary-noise spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-counterfactual-binary-noise-design.md) 把 Pearl level 3 的反事实查询纳入 v0.6 范围。本文档只讲它在本体框架下的位置，工程细节不重复。

反事实查询：

```text
P(Y_{x'} | E, I)
```

读作"现实里观测到 `E`，假如 `X` 当时是 `x'`，`Y` 会怎样"。Pearl 的标准答法是 abduction–action–prediction 三步：

1. **Abduction**：在观测因子图上 BP，得到外生噪声 `U` 的 joint posterior `P(U | E)`；
2. **Action**：mutilate + clamp(X = x') 得到反事实因子图，**安装步骤 1 算出的 `U` joint posterior**；
3. **Prediction**：在反事实因子图上 BP，读出 `Y` 的 marginal。

**对本体框架的影响**：不引入第四类本体。`U`（外生噪声）是 `Mechanism` lowering 时材料化出的额外 BP 变量（在二值 `binary_directed` 机制下，`U` 也是二值的，因此 BP 可以原生处理）。`U` 在**结构层**——它属于 mechanism 的"内部组装"，作者不需要直接接触。

也就是说：**Pearl 三阶梯（associational / interventional / counterfactual）在 Gaia 中由"两层本体 + 三种查询"承载**，而不是"三层本体"——因为 counterfactual 查询用的还是同一套 `Mechanism` 知识，只是查询算法多了 abduction 和 prediction 两步。

## 8. 作者决策指南

下面这张表回答"我想说 X，应该用哪个 verb"——这是 v0.6 之后作者写 Gaia 包时的核心 lookup：

| 我想表达的事情 | 用什么 verb | 为什么 |
|--------------|-----------|-------|
| "X 是个命题，我对它的 prior 是 0.7" | `claim(content, prior=0.7, ...)` | 命题层赋值 |
| "由 X 在逻辑上能推出 Y（数学/定义）" | `derive(Y, given=[X], rationale="...")` | 逻辑推理步，干预下保留 |
| "X 是 Y 的统计证据（似然比）" | `infer(evidence=X, hypothesis=Y, p_e_given_h=..., p_e_given_not_h=...)` | 命题层 Bayes update |
| "X 与 Y 等价" | `equal(X, Y)` | 命题层等价 |
| "X 与 Y 不能并存" | `contradict(X, Y)` | 命题层互斥 |
| "X 与 Y 关联但方向不明" | `associate(X, Y, p_a_given_b=..., p_b_given_a=...)` | 命题层对称关联 |
| **"X 是 Y 的因，机制 CPD 是 (α, β)"** | **`mechanism(cause=X, effect=Y, cpd=(α, β))`** | **结构层声明，可触发 do() 查询** |
| "如果干预把 X 设为 x，Y 会是什么" | `do(X=x).query(Y)` | 干预性查询 |
| "现实是 E，假如 X 当时是 x'，Y 会是什么" | `do(X=x').counterfactual(observed=E).query(Y)` | 反事实查询 |
| "假说 H 预测可观测量 Z 服从分布 D，并用数据 E 做模型比较" | `bayes.model(H, observable=Z, distribution=D)` + `bayes.compare(E, models=[...])` | model comparison（命题层） |

### 8.1 何时该选 `mechanism()` vs `derive()` 的关键差别

二者在某些命题上**看起来都行**（例如"重力使物体下落"），但语义明显不同：

| | `derive(falling, given=[gravity])` | `mechanism(cause=gravity, effect=falling, cpd=...)` |
|---|---|---|
| 在 `do(gravity=0).query(falling)` 下的行为 | **保留**——逻辑约束不被干预切断 | **被切断**——因果机制被 mutilate 移除 |
| 物理意义 | "在我们的逻辑/数学框架内，gravity 与 falling 必然相关" | "gravity 是导致 falling 的物理机制；如果某种方式关闭重力，就没有下落" |

**作者决策原则**：

- 如果你想表达的是**定义/数学/常识层面的必然关联**（例如"圆周率等于周长除以直径"、"温度高于熔点则物质液化"），用 `derive`——这种关联在 do() 下**应该保留**；
- 如果你想表达的是**物理/生物/社会层面的因果机制**（例如"吸烟导致肺癌"、"重力导致下落"），用 `mechanism`——这种关联在干预下**应该被切断**（你拒绝这个机制不等于否认逻辑）。

[mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §4.4 思想实验 1–8 给出了 8 个具体例子来训练这个直觉。

### 8.2 mixed-modality：当一个节点同时有 causal 和 logical 入边

v0.5 老 spec 把这种情况报 warning。新 spec 保留这个 warning，意图明确：作者要么显式声明所有入边都是 causal，要么显式分开（一些是 mechanism、一些是 derive）。**不允许"看起来都对"的隐式混淆**——因为这种情况下 do() 的行为会出乎作者意料。

## 9. 与 v0.5 命题层文档的关系

[`01-plausible-reasoning.md`](01-plausible-reasoning.md)、[`02-maxent-grounding.md`](02-maxent-grounding.md)、[`03-propositional-operators.md`](03-propositional-operators.md) 等命题层文档**完全保留有效**。本文档只在两处加了 cross-reference 链接，承认它们的辖区是命题层：

1. [`01-plausible-reasoning.md`](01-plausible-reasoning.md) §1.1 在五项"科学推理比数学逻辑多了什么"列表后增加一项："**结构性知识**——除了概率约束（'P(C) = 0.7'）和逻辑约束（'A → B'），科学推理还涉及结构性声明（'X 是 Y 的因'、'机制是 M'）。详见 [`08-causality-and-jaynes.md`](08-causality-and-jaynes.md)。"
2. [`02-maxent-grounding.md`](02-maxent-grounding.md) §2 加一段脚注：本文档定义的"约束集 `C(I)`"涵盖命题层的概率约束和逻辑约束。当 `I` 还包含因果机制声明时，这些机制不进入 `C(I)`，而是直接 lower 成 `CausalFactor` 进入因子图——详见 [`08-causality-and-jaynes.md`](08-causality-and-jaynes.md)。

老文档的所有 worked example、所有数学结果**无需修改**。

## 10. 与外部因果库的关系

> 与 [mechanism-first-class spec](https://github.com/SiliconEinstein/Gaia/blob/main/docs/specs/2026-05-06-causal-mechanism-first-class-design.md) §1.2 重复声明——避免读者从理论文档进入时困惑"为什么不直接用 DoWhy"。

外部因果库可以分两类：

| 库 | 解决的问题 | Gaia 是否引入 |
|----|----------|--------------|
| **DoWhy / EconML / CausalNex / Ananke / causal-learn** | **数据驱动**——从观测数据**学**结构和效应 | 否。Gaia 是 author-driven（结构由作者声明），不学结构 |
| **NetworkX** | DAG 算法（祖先、d-separation、adjustment set） | 是，作为 kernel 依赖 |
| **y0** | 符号化 do-calculus identification（ID/IDC algorithm） | 是，作为 `gaia[causal-do]` extra（lazy import） |
| **pgmpy 的 do()** | 在自己的 BN 模型上做数值干预 | 否。Gaia 自己的 BP 引擎做数值干预，因为 mutilate 需要区分 causal 与 logical 因子（pgmpy 没有这个区分） |

也就是说：Gaia 的因果层是**"作者声明结构 + Gaia BP 跑数值 + y0 跑符号识别"**，**不**包含从数据学结构这一支。这与 Gaia 整体作为"形式化作者推理"的定位一致。

## 11. 总结

Gaia 的因果设计可以一句话概括：

> **Jaynes 的命题层（v0.5）保留不动；Pearl 的结构层（v0.6 `Mechanism`）作为平行本体引入；二者通过 lowering 到同一个因子图、由 modality-aware BP 算法承载查询语义的差异——`do()` 切换到 mutilated 因子图，反事实再加 abduction-action-prediction 三步。**

这个设计的好处：

1. **v0.5 的 Jaynesian 哲学不破裂**——命题层的 Cox / MaxEnt / Min-KL 完全保留；
2. **Pearl 的因果机器全套可用**——d-separation / back-door / ID algorithm / counterfactual 都是一等公民；
3. **作者负担最小化**——不需要自己 reconciling 哲学，只需要按 §8 决策表选 verb；
4. **BP 引擎不需要因果版本**——因果性在查询时通过图重写表达，不在 inference 内核内表达；
5. **承认本体多元性是诚实的**——科学知识不是一种本体，硬把 `Mechanism` 塞进 `Claim` 是为了形式统一而牺牲语义清晰，得不偿失。

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003) — 命题层基础
- Cox, R.T. "Probability, Frequency and Reasonable Expectation" (1946) — Cox 定理
- Pearl, J. *Causality* (2nd ed., 2009) — 结构因果模型、do-calculus、反事实三步法
- Pearl, J., Mackenzie, D. *The Book of Why* (2018) — 三阶梯科普版
- Cartwright, N. *Hunting Causes and Using Them* (2007) — 哲学层面对"causal mechanism 不可还原为概率"的论证
- Spirtes, Glymour, Scheines. *Causation, Prediction, and Search* (2nd ed., 2000) — DAG 因果发现的另一脉
- Shpitser, I., Pearl, J. "Identification of Conditional Interventional Distributions" (UAI 2006) — ID algorithm，y0 实现的算法基础
