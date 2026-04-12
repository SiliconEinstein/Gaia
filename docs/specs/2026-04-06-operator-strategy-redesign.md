# Operator & Strategy Redesign — Warrant-Based Audit

> **Status:** Proposal
>
> **Context:** 源于 2026-04-06 至 2026-04-12 对 BP lowering / factor graph / Peirce 与 Jaynes 推理理论的深入讨论。
> 核心发现：每个 relation operator 生成的 helper claim 就是一个可审计的 warrant，它既参与 BP 推理，也承载 reviewer 的审计判断。
> Deduction 和 support 是两个基础推理原语；abduction 和 induction 是 support 构建的二元 CompositeStrategy。

## 1. 动机

### 1.1 当前问题

1. **审计缺乏焦点**：reviewer 面对一整张因子图，不知道哪些点需要重点审查，哪些是作者声称"显然"的。
2. **Warrant 概念不清**：当前 IR 里有 helper claim 的概念，但没有把它们作为"给 reviewer 的审计任务"显式地组织起来。
3. **Prior 来源混乱**：有些 prior 由 operator 结构隐含决定，有些由 reviewer 判定，没有统一的 framework 说清楚"什么由结构给、什么由 review 给"。
4. **和推理理论的关系模糊**：Gaia 的 abduction / induction 对应 Peirce 和 Jaynes 哪个版本？Warrant 在 Toulmin 模型里是什么？没有明确映射。

### 1.2 核心 Insight

**每个 relation operator（implication, equivalence, contradiction, complement）在编译时产生一个 helper claim H。这个 H 就是一个 warrant**：

- **结构上**：H 是一个 Knowledge 节点，参与因子图 BP
- **内容上**：H.content 是结构性逻辑命题（如 `equivalence(A, B)`）
- **审计上**：H.metadata 里存一个 question（审计题目）和作者的 reason（回答）
- **后验上**：π(H) 由 reviewer 判定，反映 reviewer 对作者 reason 的认可程度

Warrant 不是单独的概念——它是 helper claim 在 review 流程中的角色解释。每个 relation operator 的 H 都是 warrant，每个 warrant 对应一个可独立审计的问题。

## 2. Warrant 的结构

### 2.1 作为 Helper Claim

当 FormalExpr 中出现一个 relation operator 时，编译器生成对应的 helper claim：

```
Operator(operator="equivalence", variables=[A, B], conclusion=H)
```

生成：

```
H = Knowledge(
    type="claim",
    content="equivalence(A, B)",                  # 结构性逻辑命题
    metadata={
        "helper_kind": "equivalence_result",
        "question": <derivable from operator + operands>,
        "warrant": <author's reason text>,
    },
)
```

H 和普通 claim 一样参与 BP。它的 prior π(H) 由 review 设定，直接影响因子图的消息传播。

### 2.2 三个 metadata 字段

| 字段 | 语义 | 来源 |
|------|------|------|
| `content` | 结构性断言（`equivalence(A, B)` 等） | Operator 类型 + 操作数 |
| `metadata["question"]` | 给 reviewer 的审计题目 | 可由 operator 类型 + 操作数动态生成，也可显式存储 |
| `metadata["warrant"]` | 作者的 reason 文本（回答 question） | DSL 的 `reason` 参数 |

Question 本质上是**从 operator 类型和操作数自动导出的审计模板**。例如：
- `implication([A, B])` 的 question："A 是否蕴含 B？"
- `equivalence([A, B])` 的 question："A 和 B 是否真的等价？"
- `contradiction([A, B])` 的 question："A 和 B 是否不能同时为真？"
- `complement([A, B])` 的 question："A 和 B 是否恰好真值相反？"

具体 question 由 operator type + operands 决定，不需要作者显式提供。

Warrant 是**作者给 reviewer 的回答**，是 imperative 风格的指令（"验证推导无跳跃"、"核对公式条件"），而不是陈述。作者通过 DSL 的 `reason` 参数写入，编译器把它填到 helper claim 的 metadata 里。

### 2.3 默认行为与 π 语义

**Computation operator**（conjunction, disjunction, not）的 conclusion：
- π 永远 = 0.5——这是结构性的（值由输入的布尔运算决定），不需要 review

**Relation operator**（implication, equivalence, contradiction, complement）的 conclusion：
- π **由 reviewer 通过 warrant review 指定**
- 未 review 前，π = 0.5 作为**占位值**（表示"等待审计"，不表示"没有信息"）
- Review 后，reviewer 根据 warrant 质量设定 π（可以是 1-ε、0.8、0.5 等）

作者省略 reason → `metadata["warrant"]` 填入默认占位（如"显而易见"）。这不改变 π——prior 仍然由 reviewer 判定。

**重要原则**：作者省略 reason ≠ 作者主张"显然" ≠ 系统默认接受。Relation operator 的推理约束在 review 前是**惰性的**（π=0.5 占位），review 后才**激活**。Review 纪律不被破坏。

## 3. Warrant 的两种语义方向

Warrant 的 prior 对推理结果的影响方向取决于它在结构里的角色：

### 3.1 正向 Warrant（Forward）

**高 π(H) → 加强推理**。

典型代表：deduction 里的 implication H。

- Question：推理步骤是否成立？
- 高 π：reviewer 认可推理，因子图中约束生效，推理强度高
- 低 π：reviewer 质疑推理，约束弱化，推理强度低

### 3.2 反向 Warrant（Reverse）

**低 π(H) → 加强推理**。

典型代表：abduction 里的 AltExp（替代解释）。

- Question：替代解释是否可能？
- 低 π：reviewer 认为替代解释不成立，H 被 Bayesian 强抬升
- 高 π：reviewer 认为替代解释合理，H 的抬升被削弱

两种方向的共同点：都是"带 prior 的 Knowledge 节点，reviewer 对其 π 做判定"。语义方向只是 reviewer 如何解读 question——答"yes"对应高 π 还是低 π。

## 4. Review 流程

Reviewer 的工作是遍历 strategy 的 FormalExpr，找到每个 relation operator 的 helper claim H，然后对每个 H 做以下动作：

1. 读 `H.content` 和 `H.metadata["question"]` —— 理解审计题目
2. 读 `H.metadata["warrant"]` —— 看作者的回答
3. 判断 warrant 是否充分回答 question
4. 设定 π(H)：
   - 完全认可 → π(H) = 1-ε（正向）或 ε（反向，视语义方向而定）
   - 部分认可 → 介于 0.5 到 1-ε 之间
   - 不认可 → π(H) 接近 0.5（中性）或更低
5. 写入 review 记录

Review 的结果是 `PriorRecord` 对 H 的赋值——这个 prior 进入因子图，影响后续 BP 推理。

**Review Policy**：每种 relation operator 的 question 模板是固定的，由 operator type 决定。Review 工具可以根据 FormalExpr 的结构自动生成审计表单——reviewer 只需要逐项对照，不需要为每个策略手写审计规则。

## 5. Operator 层的保持

**Warrant 不是 Operator 的字段**。Operator 层保持纯粹的命题逻辑结构，不携带语义解释。

| Operator | Type | 产生 warrant？ | Warrant 的 question 模板 |
|----------|------|---------------|------------------------|
| `not` | computation | 否 | — |
| `conjunction` | computation | 否 | — |
| `disjunction` | computation | 否 | — |
| `implication` | reasoning | **是** | "A 是否蕴含 B？" |
| `equivalence` | reasoning | **是** | "A 和 B 是否真的等价？" |
| `contradiction` | reasoning | **是** | "A 和 B 是否不能共存？" |
| `complement` | reasoning | **是** | "A 和 B 是否恰好一真一假？" |

- **Computation operator**（conjunction, disjunction, not）的 conclusion 是确定性布尔函数的输出，不需要审计——它们是逻辑计算，不是推理判断
- **Relation operator**（implication, equivalence, contradiction, complement）的 conclusion 是对两个命题间关系的断言，这个断言可以被质疑，所以需要审计

Warrant 是 **relation operator 的副产品**，不是 Operator 的显式字段。

## 6. 基础推理原语：Deduction 和 Support

Warrant framework 的一个直接应用是区分 Gaia 的两个基础推理原语——**deduction** 和 **support**。它们覆盖了大部分常见的推理场景，也展示了 warrant 在单向和双向推理中的不同角色。

### 6.1 Deduction — 单向确定推理

Deduction 是最基础的推理单元：从前提通过一步 implication 推出结论。

**编译产物**：

```
# 多前提
conjunction([A, B, ...], M)      # computation, 无 warrant
implication([M, C], H)            # 产生 1 个 warrant H

warrants = [H]

# 单前提
implication([A, C], H)            # 直接 implication
warrants = [H]
```

- **方向**：单向（前提 → 结论）
- **Warrant 数量**：1（implication 的 helper claim H）
- **Warrant question**："从前提的合取到结论的推导是否成立？"
- **语义**：作者声称这是确定性推导

### 6.2 Support — 双向推理

Support 是双向推理原语：两个命题之间存在两个独立的 implication，分别对应充分性和必要性，各自有自己的 warrant。

**编译产物**：

```
implication([A, B], H_fwd)       # 正向（充分性：A 是 B 的充分条件）
implication([B, A], H_rev)       # 反向（必要性：A 是 B 的必要条件）

warrants = [H_fwd, H_rev]
```

- **方向**：双向（A ↔ B，通过两个独立 implication）
- **Warrant 数量**：2
- **Forward warrant（充分性）**：H_fwd — question："A 是否足以推出 B？"，由 `reason` 参数填写
- **Reverse warrant（必要性）**：H_rev — question："B 是否足以推出 A？（即 A 是否是 B 的必要条件）"，由 `reverse_reason` 参数填写
- **Review policy**：reviewer 分别估计两个方向的概率 $p_1$（充分性强度）和 $p_2$（必要性强度）
- **语义**：作者承认两个方向的推理强度可能不同，各自由 reviewer 独立判定

### 6.3 Support = FormalExpr，不是新算符

Support 不是一个新的 4 元 operator——它是 **FormalExpr 层面的组合模式**，编译为两个 ternary IMPLIES operator。这个设计选择有三个理由：

1. **Operator 层保持统一**：所有 operator 都是 ternary CONDITIONAL factor，BP 引擎不需要支持新的 factor 类型
2. **数学等价**：两个独立 IMPLIES（各自带独立 prior）的乘积等价于一个 SOFT_ENTAILMENT 因子，边缘化 helper claim 后得到相同的有效势函数
3. **配对由编译器保证**：FormalExpr 在编译时生成配对的两个 implication，保证正反方向总是一起出现

两个方向的 prior（$p_1$, $p_2$）是独立自由参数，由 review 判定。

### 6.4 Support 替代 noisy_and 和 soft_entailment

原来独立的 `noisy_and` 和 `soft_entailment` 策略类型被 support 完全替代——它们都是 support 的参数特例：

| 使用场景 | $p_1$（正向） | $p_2$（反向） | 语义 |
|---------|--------------|--------------|------|
| 确定性 deduction | 1−ε | 0.5（silent） | 严格推导（等价于 deduction）|
| 原 `noisy_and` | < 1 | 0.5（silent） | 弱正向推理，无反向反馈 |
| 原 `soft_entailment` | 任意 | 任意 | 双向推理，两个方向都有意义 |
| 理论 ↔ 实验 | 1−ε | 高（如 0.7）| 正向强（理论预测观测），反向中等（实验确认增强理论可信度）|

所有这些场景使用**同一个 support FormalExpr 结构**，只是 $p_1$ 和 $p_2$ 的取值不同。**`noisy_and` 和 `soft_entailment` 作为独立策略类型被删除**——它们吸收进 support。

当 $p_2 = 0.5$ 时，反向 implication 对 BP 没有额外信息贡献，H_rev 实际上是 silent 的——此时 support 在数学上退化为单向的 deduction。作者选择 support 而非 deduction 的差别在于**想不想显式暴露反向 warrant 作为审计槽位**，即使它暂时是 silent。

### 6.5 Deduction vs Support 的选择

作者在这两个原语之间的选择取决于**他想向 reviewer 声明什么**：

| | Deduction | Support |
|---|-----------|-----------|
| 声明 | "这是确定性单向推导" | "这是双向关系，两个方向独立可审" |
| Warrant 数 | 1 | 2 |
| Review policy | BinaryAcceptance × 1 | ProbabilityEstimate × 2 |
| 典型场景 | 数学证明、逻辑推导 | 理论 ↔ 实验、前提 ↔ 结论的双向支撑 |

选择的本质不在 BP 结构（它们可以通过参数调整给出同样的数学效果），而在**作者和 reviewer 间的契约**——声明的强度和审计的维度。

### 6.6 Support 作为 Warrant framework 的印证

Support 是一个很好的例子，展示本 spec 的 warrant framework 的实际工作方式：

- **每个 relation operator 产生一个 warrant**：support 有两个 implication，所以有两个 warrant
- **Warrant 的 question 由 operator 模板自动导出**：两个 warrant 都是 implication 类型，question 分别基于 (A, B) 和 (B, A)
- **Warrant 的 prior 由 review 判定**：$p_1$ 和 $p_2$ 都是 reviewer 设的独立参数
- **语义角色是作者提供的**：是"正向 + 反向"还是"强 + 弱"由作者在 DSL 层（`reason` 和 `reverse_reason`）表达

其他策略（abduction, induction 等）的结构更复杂，但都遵循同样的 warrant 生成规则——每个 relation operator 的 helper claim 都是一个可独立审计的 warrant。

## 7. Compare 原语和复合推理策略

### 7.1 Compare — 预言匹配比较

Compare 是第三个 FormalStrategy 原语。它比较两个预言对同一个观测的匹配度，输出一个 comparison helper claim。

**编译产物**：

```
equivalence([pred_h, observation], H_eq1)       # 预言 1 是否匹配观测？
equivalence([pred_alt, observation], H_eq2)     # 预言 2 是否匹配观测？

warrants = [H_eq1, H_eq2]
conclusion = comparison_claim (π=0.5, 自动生成, 无 warrant)
```

- **输入**：两个预言 claim + 一个观测 claim
- **Warrants**：2（各问"预言是否匹配观测？"）
- **输出**：comparison helper claim（π=0.5，BP 从 equivalence warrants 推出后验）
- **第一个预言（pred_h）默认是声称更好的那个**

Compare 可以被 abduction 内部自动创建，也可以由作者**独立使用**——例如 A/B test 场景下直接比较两个方案的预测和实际效果，不需要完整的 abduction 包装。

**DSL 签名**：

```python
def compare(
    pred_h: Knowledge,          # 声称更好的预言（放在前面）
    pred_alt: Knowledge,        # 对比预言
    observation: Knowledge,     # 实际观测
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",   # → 说明为什么这两个预言可以对比
) -> Strategy:
```

**独立使用示例**（A/B test）：

```python
pred_A = claim("方案 A 预测转化率 12%")
pred_B = claim("方案 B 预测转化率 8%")
obs = claim("实测转化率 11.5%")

comp = compare(pred_A, pred_B, obs, reason="同一用户群同一时段的对照实验")
# comp.conclusion = comparison claim "A > B"
```

### 7.2 三层 Warrant 体系

本 spec 的三个 FormalStrategy 原语产生三种 warrant：

| 原语 | Operator | Warrants | 审计问题 |
|------|----------|----------|---------|
| **deduction** | 1 implication | 1 | "推导是否成立？" |
| **support** | 2 implications | 2 | "充分性？" + "必要性？" |
| **compare** | 2 equivalences | 2 | "预言 1 匹配观测？" + "预言 2 匹配观测？" |

### 7.3 Abduction — 假说比较（CompositeStrategy）

Abduction 实现的是 **IBE（Inference to the Best Explanation, Harman 1965）**——给定多个候选假说，选最好地解释观测的那个。这是 Peirce abduction 的"比较式"变体，不是"生成式"（假说生成由人类作者完成，Gaia 不自动化）。

Abduction 是**二元 CompositeStrategy**，内部组合 2 个 support + 1 个 compare：

```
abduction (CompositeStrategy)
  ├── composition warrant (H_valid)          ← CompositeStrategy 级别
  │     question: "两个 support 的预言是否关于同一个观测？"
  │     warrant: author's reason
  │
  ├── support_h (FormalStrategy)             ← 2 warrants (theory → prediction)
  ├── support_alt (FormalStrategy)           ← 2 warrants (theory → prediction)
  └── compare (FormalStrategy)               ← 2 warrants (pred vs obs equivalences)
  
  conclusion = compare.conclusion (comparison claim, π=0.5)
```

**DSL 签名**：

```python
def abduction(
    support_h: Strategy,        # support(H, pred_h) — 声称更好的理论在前
    support_alt: Strategy,      # support(Alt, pred_alt)
    observation: Knowledge,     # 实验观测
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",   # → composition warrant
) -> Strategy:
```

**内部自动创建**：
- `compare(support_h.conclusion, support_alt.conclusion, observation)`
- Composition warrant（`reason` 写入其 warrant text）

**Warrants 总数**：1（composition）+ 4（两个 support）+ 2（compare 的 equivalences）= **7**

**Review checklist**（自动生成）：
1. **Composition warrant**：两个 support 的预言是否关于同一实验？
2. **Support warrants × 4**：各理论→预言的充分性和必要性
3. **Compare warrants × 2**：各预言是否匹配实验观测？
4. **方向验证**：在 warrant 审计下，H 是否确实优于 Alt？

**使用示例**（Al 超导）：

```python
pred_new = claim("VDiagMC 预言 Tc = 0.97K")
pred_old = claim("McMillan 预言 Tc ∈ [0.5, 2K]")
obs_tc = claim("实验测得 Tc = 1.2K")

s_new = support([H_vdiagmc], pred_new,
    reason="严格第一性原理计算推出 Tc",
    reverse_reason="Tc 预言支持 VDiagMC 方法的有效性",
)
s_old = support([H_mcmillan], pred_old,
    reason="经验 μ* 给出 Tc 范围",
    reverse_reason="Tc 范围支持 McMillan 框架",
)

abd = abduction(s_new, s_old, observation=obs_tc,
    reason="两种方法都预言 Al 在相同压力条件下的 Tc",
)
# abd.conclusion = auto-generated comparison claim "VDiagMC > McMillan"
```

### 7.4 Induction — 证据累积（CompositeStrategy）

Induction 是**二元 CompositeStrategy**，组合 2 个 support，输出 law 本身：

```
induction (CompositeStrategy)
  ├── composition warrant (H_valid)
  │     question: "两个 support 的观测是否独立？是否支持同一个 law？"
  │     warrant: author's reason
  │
  ├── support_1 (FormalStrategy)             ← 2 warrants
  ├── support_2 (FormalStrategy)             ← 2 warrants
  
  conclusion = law
```

**DSL 签名**：

```python
def induction(
    support_1: Strategy,        # support(law, obs1) 或前一步 induction
    support_2: Strategy,        # support(law, obs2)
    law: Knowledge,             # 被累积支持的规律
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",   # → composition warrant（独立性论证）
) -> Strategy:
```

**Warrants 总数**：1（composition）+ 4（两个 support）= **5**

**使用示例**（Mendel 归纳）：

```python
s1 = support([H_discrete], obs_seed_shape,
    reason="H 预言 3:1", reverse_reason="2.96:1 在预期波动内")
s2 = support([H_discrete], obs_seed_color,
    reason="H 预言 3:1", reverse_reason="3.01:1 精确吻合")
s3 = support([H_discrete], obs_flower_color,
    reason="H 预言 3:1", reverse_reason="3.15:1 在预期波动内")

ind_12 = induction(s1, s2, law=H_discrete,
    reason="种子形状和颜色是形态学上无关的性状")
ind_123 = induction(ind_12, s3, law=H_discrete,
    reason="花色和种子性状在发育上独立")
```

### 7.5 Abduction vs Induction 的关键不对称

| | Abduction | Induction |
|---|-----------|-----------|
| 输入 | 2 supports（2 个假说→预言，1 个 Obs） | 2 supports（1 个假说，2 个 Obs） |
| 内部 | 1 compare（pred vs obs equivalences） | 无 compare |
| 输出 | **comparison helper claim**（相对判断） | **law 本身**（绝对支持） |
| Composition warrant | "预言关于同一实验？" | "观测独立？支持同一 law？" |
| Warrants 总数 | 7（1+4+2） | 5（1+4） |

### 7.6 组合模式

**多假说（N>2）——平行 abduction + deduction 综合**：

```python
abd_12 = abduction(s_H1, s_H2, obs, reason="...")  # → "H1 > H2"
abd_13 = abduction(s_H1, s_H3, obs, reason="...")  # → "H1 > H3"

best = deduction(
    premises=[abd_12.conclusion, abd_13.conclusion],
    conclusion=claim("H1 是对 obs 的最佳解释"),
    reason="H1 在所有二元比较中都胜出",
)
```

**多观测（N>2）——链式 induction**：

```python
ind_12 = induction(s1, s2, law=H, reason="obs1 和 obs2 独立")
ind_123 = induction(ind_12, s3, law=H, reason="obs3 和前两者独立")
ind_1234 = induction(ind_123, s4, law=H, reason="obs4 和前三者独立")
```

**跨多实验比较 H1 vs H2——abduction + induction 组合**：

```python
# 每个实验比较 H1 vs H2
abd_exp1 = abduction(s_H1_exp1, s_H2_exp1, obs_exp1, reason="...")
abd_exp2 = abduction(s_H1_exp2, s_H2_exp2, obs_exp2, reason="...")

# 多次比较累积"H1 一致优于 H2"
general_claim = claim("H1 在多个实验中一致优于 H2")
s_comp1 = support([abd_exp1.conclusion], general_claim, reason="...", reverse_reason="...")
s_comp2 = support([abd_exp2.conclusion], general_claim, reason="...", reverse_reason="...")

ind = induction(s_comp1, s_comp2, law=general_claim, reason="两个实验独立进行")
```

**Peirce 完整循环——deduction + support + abduction + induction**：

```python
# 1. Deduction: theory → prediction
pred_h = claim("H 预言 Tc = 0.97K")
deduction([H], pred_h, reason="第一性原理计算")

# 2. Support: theory → prediction (for each hypothesis)
s_h = support([H], pred_h, reason="计算推出", reverse_reason="预言验证方法")
s_alt = support([Alt], pred_alt, reason="经验公式", reverse_reason="范围支持框架")

# 3. Abduction: compare predictions against observation
abd = abduction(s_h, s_alt, observation=obs, reason="同一实验条件")

# 4. Induction: accumulate across experiments
ind = induction(abd_exp1_support, abd_exp2_support, law=general_claim, reason="独立实验")
```

### 7.7 结构性约束独立于策略

假说之间和观测之间的关系**不内嵌在 abduction/induction 内部**，由作者在知识图中单独添加：

```python
# 假说间互斥（可选，abduction 不要求）
contradiction(H1, H2, reason="两种机制不兼容")

# 穷尽性（可选）
disjunction([H1, H2, H3], reason="已知的三种候选")
```

**分离的好处**：策略保持最简，约束可复用、独立演化、graceful degradation。

特别注意：**abduction 不要求互斥**。两个假说可以是子集关系（如"参数 = 0.3" vs "参数 ∈ [0,1)"），abduction 仍然比较哪个预言更好匹配观测。

## 8. Peirce 的科学方法论循环

### 8.1 Toulmin 的论证模型

Toulmin 的六要素可以对应到 Gaia 的结构：

| Toulmin 要素 | Gaia 对应 |
|-------------|----------|
| **Data（证据）** | Strategy 的 premise claims |
| **Claim（主张）** | Strategy 的 conclusion claim |
| **Warrant（推理依据）** | Relation operator 的 helper claim H |
| **Backing（后盾）** | 嵌入在 warrant 文本里（不单独建模） |
| **Qualifier（限定词）** | BP 计算出的后验 π |
| **Rebuttal（反驳）** | contradiction operator |

Gaia 对 Toulmin 的扩展：warrant 不再是自由文本，而是结构化的 helper claim + 审计 prior，可被 BP 严格传播。

### 8.2 Peirce 的科学方法三阶段

Peirce 提出所有科学推理都是三阶段循环：

```
Abduction (假说) → Deduction (预言) → Induction (验证) → 循环
```

本 spec 的四种策略直接映射这个循环：

| Peirce 阶段 | Gaia 策略 | 做什么 | 输出 |
|------------|----------|--------|------|
| **Abduction** | abduction (CompositeStrategy) | 比较两个假说对观测的解释力 | comparison claim（相对判断） |
| **Deduction** | deduction (FormalStrategy) | 从假说推出可检验的预言 | prediction claim |
| **Induction** | induction (CompositeStrategy) | 从多个观测累积对假说的支持 | H 本身（后验上升） |
| — | support (FormalStrategy) | 基础推理原语，被以上三者使用 | — |

### 8.3 Jaynes 弱三段论的实现

每个 support 在因子图中实现 Jaynes 的弱三段论：

- Forward implication 编码 $P(Obs|H)$（假说对观测的预言力）
- Reverse implication 编码 $P(H|Obs)$ 的反向推理强度
- BP 按 Bayes 公式计算后验

Abduction 通过比较两个 support 的 warrants 来判断"哪个假说更好"——本质上比较 $P(Obs|H_1)$ vs $P(Obs|H_2)$。

### 8.4 Peirce 与 Jaynes 的统一

Gaia 同时实现了 Peirce 和 Jaynes 的框架：

- **Jaynes 的数学**：每个 support 的 warrants 编码 Baynes 弱三段论的参数，BP 严格按 Bayes 公式计算
- **Peirce 的本体论**：假说和替代假说都是命名的 Knowledge claims，可以被其他策略支持或挑战

作者可以只写一个简单的 abduction（退化为 Jaynes 的弱三段论），也可以构建完整的 Peircean 循环（abduction → deduction → induction → 反馈）。

## 9. Review Policy Checklist

### 9.1 两种 Review 类型

| 类型 | 适用于 | 语义 | 不通过时 |
|------|--------|------|---------|
| **BinaryAcceptance** | 结构性校验 | 对或错，无中间态 | 打回修改 |
| **ProbabilityEstimate** | 程度性判断 | 强或弱，连续概率 | 设低 π |

分配规则：

| Warrant 来源 | Review 类型 | 理由 |
|-------------|-----------|------|
| deduction 的 implication | BinaryAcceptance | 推导对或不对 |
| support 的 forward / reverse | ProbabilityEstimate | 充分性/必要性有强弱之分 |
| compare 的 equivalence | ProbabilityEstimate | 预言匹配观测有好坏之分 |
| composition warrant（abduction / induction） | BinaryAcceptance | 组合有效或无效，无中间态 |

### 9.2 Deduction Review

**Warrants**：1（implication H）

**Question 模板**：

> "从 {premises 的合取} 到 {conclusion} 的推导是否成立？是否有跳步或隐含假设？"

**π 判定**：

| 判断 | π(H) |
|------|------|
| 推导严格无误 | 1-ε |
| 基本正确，微小近似 | ~0.95 |
| 有明确逻辑缺口 | ~0.5-0.8 |
| 推导不成立 | 打回修改 |

### 9.3 Support Review

**Warrants**：2（H_fwd + H_rev）

**Forward question 模板**：

> "{premises} 是否足以推出 {conclusion}？即 {premises} 成立时，{conclusion} 是否必然或大概率成立？"

**Reverse question 模板**：

> "{conclusion} 成立时，是否反过来支持 {premises}？即 {conclusion} 是否是 {premises} 的特征性后果？"

**π 判定**：

| 方向 | 场景 | π |
|------|------|---|
| Forward | 严格数学推导 | 1-ε |
| Forward | 强经验支持 | 0.8-0.95 |
| Forward | 弱关联 | 0.5-0.7 |
| Reverse | 结论是前提的 smoking gun | 0.9+ |
| Reverse | 结论也可由其他原因产生 | 0.3-0.6 |
| Reverse | 无反向信息 | 0.5（silent） |

### 9.4 Compare Review

**Warrants**：2（H_eq1 + H_eq2）

**Question 模板**（对每个 equivalence）：

> "{prediction} 是否匹配实际观测 {observation}？预言值和实验值是否一致（在合理误差范围内）？"

**π 判定**：

| 场景 | π |
|------|---|
| 预言精确命中观测 | 1-ε |
| 预言在误差范围内匹配 | 0.8-0.95 |
| 预言方向对但数值有偏差 | 0.5-0.8 |
| 预言范围包含观测但太宽泛 | 0.3-0.6 |
| 预言和观测矛盾 | ε |

**Comparison claim**：π=0.5 自动，reviewer 不直接审。后验由 BP 从两个 equivalence warrants 推出。

### 9.5 Abduction Review

**Warrants**：7（1 composition + 4 support + 2 compare）

**Checklist**（review 工具按层级自动生成）：

| # | 层级 | Question | Review 类型 |
|---|------|----------|------------|
| 1 | abduction | 两个 support 的预言是否关于同一个实验观测？ | BinaryAcceptance |
| 2 | support_h | H → pred_h 充分？ | ProbabilityEstimate |
| 3 | support_h | pred_h → H 必要？ | ProbabilityEstimate |
| 4 | support_alt | Alt → pred_alt 充分？ | ProbabilityEstimate |
| 5 | support_alt | pred_alt → Alt 必要？ | ProbabilityEstimate |
| 6 | compare | pred_h 匹配 observation？ | ProbabilityEstimate |
| 7 | compare | pred_alt 匹配 observation？ | ProbabilityEstimate |

Composition warrant（#1）不通过 → 打回，比较无效。其余 6 个是 ProbabilityEstimate。

Review 工具递归遍历策略树，每层只审该层的 warrants，不越级。

### 9.6 Induction Review

**Warrants**：5（1 composition + 4 support）

**Checklist**：

| # | 层级 | Question | Review 类型 |
|---|------|----------|------------|
| 1 | induction | 两个观测是否独立？是否支持同一个 law？ | BinaryAcceptance |
| 2 | support_1 | law → obs1 充分？ | ProbabilityEstimate |
| 3 | support_1 | obs1 → law 必要？ | ProbabilityEstimate |
| 4 | support_2 | law → obs2 充分？ | ProbabilityEstimate |
| 5 | support_2 | obs2 → law 必要？ | ProbabilityEstimate |

Composition warrant（#1）不通过 → 打回，要求作者建模共享因素或重组观测。

### 9.7 Review 工具算法

```
def review(strategy):
    if strategy is CompositeStrategy:
        review composition_warrant → BinaryAcceptance
        if not accepted: return REJECT("组合无效")
        for sub in strategy.sub_strategies:
            review(sub)  # 递归
    elif strategy is FormalStrategy:
        for operator in strategy.formal_expr:
            if operator is relation_operator:
                H = operator.conclusion
                show H.metadata["question"]
                show H.metadata["warrant"]
                collect π(H) from reviewer → PriorRecord
```

**默认行为**：未 review 的 warrant，π = 0.5（中性，无信息）。

## 10. 对下游的影响

### 9.1 Lowering

Lowering 层需要：

1. 为每个 relation operator 的 helper claim 分配 prior
2. **不再**按 operator type 默认赋予 1-ε 或 0.5 的 prior
3. 默认 π(H) = 0.5（中性），由 review 层覆盖

相关的 lowering 规则（operator CPT、Cromwell 软化等）保持不变。

### 9.2 Review 工具

Review 工具根据 FormalExpr 的结构自动生成审计表单：

1. 遍历 FormalExpr，找到所有 relation operators
2. 对每个 operator，生成对应的 question 文本（用 operator type + operands 实例化模板）
3. 读取 helper claim 的 `metadata["warrant"]` 显示作者的回答
4. 收集 reviewer 的 π 判定，写入 PriorRecord

这个流程对所有 strategy type 统一——不需要为每种 strategy 手写 review 逻辑。

### 9.3 Review 文档

Warrant 的 question 模板库（relation operator → 审计问题）应该作为 review policy 的一部分，放在 `docs/foundations/review/` 下。

Strategy 层的具体 review 需求（每种 strategy type 产生哪些 warrants、哪些 warrants 是核心审计点、默认 question 文本如何）由 `docs/foundations/gaia-lang/` 下的策略定义文档描述。

## 11. 后续工作

### 11.1 已完成

- **DSL 签名**（§6-7）：deduction、support、compare、abduction、induction 的 Python 函数签名
- **Review policy checklist**（§9）：question 模板、π 判定标准、BinaryAcceptance vs ProbabilityEstimate 分类、review 工具算法

### 11.2 Deferred

- **case_analysis / elimination**：是否也采用"二元 CompositeStrategy + 独立约束"模式
- **analogy / extrapolation / mathematical_induction**：未讨论

### 11.3 本 spec 确立的内容

1. **Warrant 核心概念**（§2-5）：relation operator 的 helper claim 就是可审计的 warrant
2. **三个推理原语**（§6-7）：deduction（1 IMPLIES，1 warrant）、support（2 IMPLIES，2 warrants）、compare（2 equivalences，2 warrants + comparison claim）
3. **两个复合策略**（§7）：abduction（2 supports + 1 compare + 1 composition warrant = 7 warrants）和 induction（2 supports + 1 composition warrant = 5 warrants）
4. **结构性约束独立于策略**：contradiction / disjunction 等由作者在图里单独添加，abduction 不要求互斥

## 12. 迁移与实施

### 12.1 文档更新

**IR 文档**（`docs/foundations/gaia-ir/`，Protected Layer，需用户批准独立 PR）：

- `04-helper-claims.md` §6：允许 relation operator 的 helper claim 携带 review prior（当前文档禁止所有 helper claim 的独立 prior，需要区分 computation 和 relation）
- `02-gaia-ir.md` §2：在 relation operator 的描述里加上 warrant metadata 的结构说明
- `06-parameterization.md`：说明 relation operator helper claim 的 prior 来源于 review

**理论文档**（`docs/foundations/theory/`，Protected Layer）：

- `04-reasoning-strategies.md`：更新 abduction 定义，区分 Peirce 生成式 abduction 和 IBE（本 spec 实现的是 IBE）；新增 support/compare 原语的理论基础

### 12.2 代码改动

- Helper claim 编译时自动填充 `metadata["question"]`（或延迟到 review 工具动态生成）
- `reason` DSL 参数 → 对应 helper claim 的 `metadata["warrant"]`
- Review 工具根据 operator type 生成审计表单

具体代码改动范围取决于后续策略接口讨论的结论。

### 12.3 实施顺序

1. 本 spec 作为完整 proposal（warrant + 原语 + 复合策略），先和用户对齐
2. 更新 IR 文档和 helper claim 规范（Protected Layer 改动）
3. 实现 support 作为 FormalExpr；删除 `noisy_and` 和 `soft_entailment`
4. 实现 abduction 和 induction 作为二元 CompositeStrategy
5. 实现 comparison helper claim 的自动生成（abduction 输出）
6. 独立讨论 case_analysis / elimination 的改造
7. 更新 BP 文档（potentials.md, formal-strategy-lowering.md）

## 附录 A：Support 与 SOFT_ENTAILMENT 的数学等价性

Support 编译为两个独立的 IMPLIES。边缘化 helper claims 后，有效势函数与 SOFT_ENTAILMENT 在 BP 中等价（比值一致）。

**推导**：

对 `IMPLIES([A, B], H_fwd)` with π(H_fwd) = p₁，边缘化 H_fwd 后有效势函数：

| A | B | ψ_fwd(A,B) |
|---|---|-----------|
| 0 | 0 | ≈ p₁（vacuous） |
| 0 | 1 | ≈ p₁（vacuous） |
| 1 | 0 | ≈ 1-p₁（violation） |
| 1 | 1 | ≈ p₁（ok） |

对 `IMPLIES([B, A], H_rev)` with π(H_rev) = p₂，边缘化 H_rev 后：

| A | B | ψ_rev(A,B) |
|---|---|-----------|
| 0 | 0 | ≈ p₂（vacuous） |
| 0 | 1 | ≈ 1-p₂（violation: B=1 but A=0） |
| 1 | 0 | ≈ p₂（vacuous） |
| 1 | 1 | ≈ p₂（ok） |

乘积 ψ(A,B) = ψ_fwd · ψ_rev：

| A | B | ψ(A,B) |
|---|---|--------|
| 0 | 0 | p₁·p₂ |
| 0 | 1 | p₁·(1-p₂) |
| 1 | 0 | (1-p₁)·p₂ |
| 1 | 1 | p₁·p₂ |

**关键比值**（BP 只依赖比值，不依赖绝对值）：

$$\frac{\psi(A\!=\!1, B\!=\!1)}{\psi(A\!=\!1, B\!=\!0)} = \frac{p_1 \cdot p_2}{(1-p_1) \cdot p_2} = \frac{p_1}{1-p_1}$$

$$\frac{\psi(A\!=\!0, B\!=\!0)}{\psi(A\!=\!0, B\!=\!1)} = \frac{p_1 \cdot p_2}{p_1 \cdot (1-p_2)} = \frac{p_2}{1-p_2}$$

与 SOFT_ENTAILMENT(p₁, p₂) 的比值完全一致。绝对值差一个常数因子，被配分函数吸收。因此两者在 BP 中产生相同的消息传播行为。∎

## 附录 B：与当前 IR 文档的关系

当前 IR 文档（02-gaia-ir.md）的 abduction 使用 `disjunction + equivalence` 结构。本 spec 提议的 "support-based CompositeStrategy" 是一种**替代设计**。两者在简单情况下数学等价（Jaynes 弱三段论），但新设计：

- 提供 per-hypothesis 的独立审计（每个 support 有自己的 warrants）
- 支持 N>2 假说的链式比较
- 将穷尽性/互斥约束分离为独立的图结构
- 输出 comparison claim 而非直接输出 H

IR 文档的结构在本 spec 之前是正确的；本 spec 是对它的**演进提案**。实施时需要更新 IR 文档（Protected Layer，需用户批准）。

## 附录 C：术语澄清

| 术语 | 定义 |
|------|------|
| **Warrant** | Relation operator 的 helper claim 在 review 流程中的角色——一个可审计的 prior 节点，带 question + reason in metadata |
| **Comparison helper claim** | Abduction 自动生成的输出 claim（π=0.5，无 warrant，posterior 由 BP 从 support warrants 推出） |
| **Forward warrant** | 高 π 加强推理的 warrant（implication H） |
| **Reverse warrant** | 作用方向相反：高 π 反向支持某假说（support 的 reverse implication H） |
| **Reasoning primitive** | Deduction（1 IMPLIES）、Support（2 IMPLIES）、Compare（2 equivalences）——复合策略的构建块 |
| **CompositeStrategy** | 二元组合：abduction（比较）或 induction（累积），由 support 构建 |
| **Structural constraint** | 独立于策略的 graph operator（contradiction, disjunction, complement），作者按需添加。观测间共享因素通过普通 claim + support 建模 |

## 附录 D：策略全景

```
                    ┌─────────────────────────────────┐
                    │      Reasoning Primitives        │
                    │                                   │
                    │  deduction  support   compare     │
                    │  (1 IMPL)  (2 IMPL)  (2 EQUIV)   │
                    └────────┬──────────┬──────────────┘
                             │          │
                    ┌────────┴──────────┴──────────────┐
                    │     Composite Strategies          │
                    │     (binary, built from           │
                    │      support)                  │
                    │                                   │
                    │  abduction         induction      │
                    │  (H1 vs H2 → comp) (H+Obs → H)   │
                    └────────┬──────────┬──────────────┘
                             │          │
                    ┌────────┴──────────┴──────────────┐
                    │     Standalone Graph Operators    │
                    │     (orthogonal to strategies)    │
                    │                                   │
                    │  contradiction  (pairwise excl.)  │
                    │  disjunction    (exhaustiveness)  │
                    │  complement     (XOR)             │
                    └──────────────────────────────────┘
```

策略管推理（hypothesis ↔ observation），图结构管约束（hypothesis ↔ hypothesis）。观测间的共享因素（如系统偏差）通过普通的 claim + support 建模，不需要新 operator。两者正交，BP 联合推理。
