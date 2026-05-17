# How to write a sound Gaia formalization

> **Gaia version:** 0.5.x
> **Author:** @kunyuan
> **Date:** 2026-05-17

把一个领域问题（临床试验、因果论证、模型比较等）编码成 Gaia knowledge package 时，本页给你提交前的一套 **决策路径**：从"这件事写成 claim 还是用 reasoning verb 生成"开始，到选什么 verb、怎么设先验、什么时候用 `bayes` 模块、推理结果不合理时回去检查什么。

本页**不**重复 [Foundations](../foundations/README.md) 的语义定义，每节都 cross-link 到 canonical 文档。如果你想看的是 verb / API 签名，直接去 [Language Reference](language-reference.md)。

## 前提

- 已完成 [Quick Start](quick-start.md) 并能编译一个最小 package
- 了解 [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md) 中 `Claim` / reasoning verb 的两层本体
- 了解 [Bayes Semantics](../foundations/gaia-lang/bayes.md) 中 `bayes.model` / `bayes.likelihood` 的客观 likelihood 设计意图

## 1. 第一层选择：直接 `claim(...)` 还是通过 reasoning verb 生成？

每个 reasoning verb（`derive` / `observe` / `infer` / `bayes.model` / `bayes.likelihood` / `equal` / `contradict` / `associate`）调用都**返回一个 Claim** 给作者。所以面对每个事实，你都在二选一：

| 写法 | 你得到什么 | 何时这么写 |
|---|---|---|
| `c = claim("...")` <br>+ `register_prior(c, ...)` | 一个独立命题，prior 由作者直接给 | 没有可写的推理 chain；命题本身就是论证起点 |
| `c = derive(...)` / `infer(...)` / `observe(...)` / `bayes.likelihood(...)` / ... | 一个 helper claim，**它的 belief 由 reasoning structure 推出** | 有可写的推理依据；让 verb 把推理结构进 IR |

> **关键 misconception**：很多新手把 `observe(claim_x)` 当成"给 `claim_x` 打观察标签"。错。`observe` 是**带 `given=` 的 reasoning verb**（它在 IR 里是一个 `Reasoning` 节点，与 `Claim` 节点平行）。把它当成属性意味着丢掉了 IR 上半层结构。详见 [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md)。

实操指南：能用 reasoning verb 表达的关系**就用**，不要为了"简化"把推理 chain 折成一个粗粒度 claim。粗粒度 claim 让外部证据无法 selectively update 内部各成分，正是 §8.3 要展开讨论的 bug。

## 2. 第二层选择：选哪个 reasoning verb

Gaia v0.5 的 reasoning verb **不是**沿一条单维谱系排开。它们是**三类完全不同的关系**，分别对应不同的 BP lowering 形态：

| 关系类别 | verb | lowering 形态 | 核心承诺 |
|---|---|---|---|
| **(A) 硬逻辑 / 关系约束** | `derive` / `equal` / `contradict` / `equivalence` / `complement` | deterministic potential（IMPLICATION 真值表、relation hard constraint） | 这是**逻辑必然**或**关系断言**，不是概率证据。BP 上接近确定性。 |
| **(B) 客观 likelihood** | `bayes.likelihood`（+ `bayes.model` + `Distribution`） | 由分布函数算出的连续 CPT | likelihood 数值**从分布函数客观计算**，作者只选 distribution + 参数，不写主观 likelihood ratio |
| **(C) 主观 likelihood** | `infer` / `associate` | 参数化 SOFT_ENTAILMENT / PAIRWISE_POTENTIAL，作者填 (p_e_given_h, p_e_given_not_h) 等 | likelihood 是**作者主观给**的（看法、专家估计、文献定性总结） |

横切这三类、独立维度的辅助动作：

- `observe` — 把 claim（或 distribution 的某个 measurement event）pin 到 `1 − CROMWELL_EPS`。它表达"已观察到为真"，不属于上面三类，常与 (B) 配套使用（`observe(dist, value, error)`）。

> **关键 distinction（最常被混淆）**
>
> - **(A) 硬逻辑** 不是 likelihood — 它的 potential 是 0/1 真值表，不带概率参数。`A → B` 在 BP 上意思是"`A=1, B=0` 这一格被禁掉"，不是"A 让 B 多 likely"。
> - **(B) 客观 likelihood** 和 **(C) 主观 likelihood** 都是概率关系，区别在 likelihood 数字**从哪来**：(B) 从 `Distribution.pmf/pdf(value)` 算；(C) 从作者笔下来。
> - 把"方向性的概率关系"写成 (A) 硬逻辑 → 见 §7.1（reverse-direction `derive` bug）。
> - 把"应该走 (B) 客观"的数值测量写成 (C) 主观 → 见 §3。

决策树：

```text
我有一个事实 / 关系要写。
├── 这是 *已观察* 的事实吗？（无推理结构，也不是分布测量）
│   └── 是 → observe(claim)
│
├── 它是 (A) 硬逻辑 / 关系约束吗？
│   ├── 前提逻辑/数学上必然推出结论 → derive(conclusion, given=[premise])
│   ├── 两个命题等价                  → equal(A, B) / equivalence(A, B)
│   └── 两个命题互斥                  → contradict(A, B) / complement(A, B)
│
├── 它是 (B) 客观 likelihood — 数值测量 + 概率分布预测吗?
│   └── 是 → Distribution + bayes.model + observe(dist, value, error) + bayes.likelihood
│            （详见 §3）
│
├── 它是 (C) 主观 likelihood — 作者要写一个 likelihood ratio 吗?
│   ├── 方向性证据（"E 是 H 的证据"，作者给 P(E|H), P(E|¬H)）
│   │      → infer(evidence=E, hypothesis=H, p_e_given_h=..., p_e_given_not_h=...)
│   └── 对称关联（方向不明，作者给 P(A|B), P(B|A)）
│           → associate(A, B, p_a_given_b=..., p_b_given_a=...)
│
└── 都不是 → 写成 claim()，并用 register_prior 显式给先验
```

> **核心原则**：**先确定关系类别 (A/B/C)，再选具体 verb**。三类各有承诺：
>
> - 选 (A) 就要对得起"逻辑必然 / 关系断言"——把方向性的概率证据写成 (A) 是 §7.1 bug。
> - 选 (B) 就要对得起"客观性"——把要检验的观测数据来源混进 distribution 参数 = double-dipping，见 §5。
> - 选 (C) 就要对得起 `justification`——主观 likelihood ratio 必须能向审查者交代来源。

## 3. 数值测量：用 `bayes` 模块，不要用 formula binding 代替

带不确定性的数值测量在 v0.5 里有一等公民 API：

```python
import gaia.engine.bayes as bayes
from gaia.engine.lang import Variable, Real, observe

log_rr = Variable(symbol="log_rr", domain=Real)

# 在两个竞争假设下，log(RR) 的预期分布
log_rr_under_effective = bayes.Normal(mu=-0.10, sd=0.05)
log_rr_under_null      = bayes.Normal(mu=0.0,   sd=0.05)

m_effective = bayes.model(h_effective, observable=log_rr,
                          distribution=log_rr_under_effective)
m_null      = bayes.model(h_null,      observable=log_rr,
                          distribution=log_rr_under_null)

# 实际测得的 log(RR) 数值（带误差）
data = observe(log_rr_under_effective, value=-0.151, error=0.05)

bayes.likelihood(data, model=m_effective, against=[m_null])
```

错误写法（用 formula binding 当 evidence）：

```python
# WRONG: 把数值绑到一个 claim 上当 evidence
log_rr_var = Variable(symbol="log_rr", domain=Real)
data_claim = claim(
    "log(RR) ≈ -0.151",
    formula=equals(log_rr_var, Constant(-0.151, Real)),
)
observe(data_claim)
infer(evidence=data_claim, hypothesis=h_effective,
      p_e_given_h=0.95, p_e_given_not_h=0.10)  # 主观估计的 likelihood
```

错在哪：

1. **绕过了 bayes 模块的整套 likelihood machinery**——distribution 函数会从 `(mu, sd)` 自动算出每个假设下 observed value 的 likelihood，作者不需要主观给 `p_e_given_h`。
2. **把 (C) 主观 likelihood 用在了应该走 (B) 客观 likelihood 的场景**——见 §2。

什么时候**确实**该用 (C) `infer`？流行病学关联（"RR 0.86, CI 0.79–0.92" 是一个 meta-analysis 的总结，不是某个 likelihood 函数能直接算出来的统计量）、案例报告、专家定性证据。这时主观 likelihood ratio 是诚实的——你把"我作为作者认为这是有力证据"显式量化为 `(p_e_given_h, p_e_given_not_h)` 写出来，并在 `justification` 里说明为什么这么填。

> 详见 [Bayes Semantics § Hypothesis comparison surface](../foundations/gaia-lang/bayes.md#hypothesis-comparison-surface-existing-v05)。

## 4. 设先验：`register_prior` + source_id + justification

先验绑定的 canonical API：

```python
from gaia.engine.lang import register_prior

register_prior(
    h_drug_effective,
    value=0.5,
    justification=(
        "Pre-trial neutrality: the trial is the first conclusive readout."
    ),
    source_id="user_priors",   # 默认值
    created_at=None,            # 默认 datetime.now(UTC)
)
```

要点：

- **value 必须在 `[CROMWELL_EPS, 1 − CROMWELL_EPS]` 内**（即 `[1e-3, 0.999]`）。在边界上的"确定 prior"几乎总是 bug——通常意味着你想表达的是"已观察到为真"，应该用 `observe(claim)` 而不是 `register_prior(claim, 0.999, ...)`。
- **justification 是必填**——空字符串 / 全空白会被拒绝。设先验是**方法论上重的动作**，必须能回答"这个数字从哪来"，让审查者审计。
- **source_id 标识来源**——v0.5 设计核心是 multi-source priors。同一 claim 可以有 `"user_priors"`（作者）/ `"continuous_inference"`（自动推断）/ `"reviewer_alice"`（审稿人）/ `"calibration_2026q2"`（校准数据）等多条记录，编译时 `ResolutionPolicy` 选 winning value 写进 `metadata['prior']`。所有记录（含落选）都进 IR，可被 `gaia inquiry review` 的 `prior_dissent` / `prior_overridden` 诊断查询。

> **Gaia 不规定数值生成方法**。`justification` 是给审查者读的字符串，没有 magic 关键词。诚实地写"这个 0.7 来自 Doll-Hill 1956 + 2024 更新元分析的低偏倚子集，我把 generalization concern 从 0.65 上调到 0.7"——这是好 justification。"chainAnalysis prior=0.7" 不是。
>
> 详见 [`gaia/engine/lang/dsl/register_prior.py`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/gaia/engine/lang/dsl/register_prior.py) docstring。

## 5. `bayes` 模块的客观性承诺

`bayes.model(hypothesis, observable=..., distribution=...)` 的语义承诺是：

> **distribution 编码假设的 prior 期望**；observed value 单独通过 `observe(dist, value, error)` 进入。

具体推论：

| 参数来源 | 是否合法 |
|---|---|
| 领域知识、独立 calibration 数据集、姐妹研究、文献总结 | ✅ 合法 prior elicitation |
| 同一份要检验数据的点估计 / 标准误 | ❌ 违反客观性 — 用同一份数据 fit 模型再检验该模型，构成 double-dipping |
| Empirical Bayes / hierarchical prior，**只要 prior 数据集和 likelihood 数据集分开** | ✅ 合法 |

判别提示：写完 `bayes.model(..., distribution=Normal(mu=X, sd=Y))` 后问自己——"`X` 和 `Y` 这两个数字，我是怎么知道的？" 如果答案是"从我马上要 `observe()` 进 likelihood 的同一份数据里算出来的"，**这是 bug**，回到 §2 表格选 `infer` 而不是 `bayes`，或者去找一份独立的 prior 数据集。

## 6. 不要 audit 拓扑，用 CLI

新手常见的失败模式：写完包之后想"机械可执行的图结构 audit checklist"——数边数、追求假设之间 supporting/contradicting 边对称、检查"孤儿节点"是否存在等。这些都是 **倒果为因**。

**真实工具链**：

| 命令 | 解决什么问题 |
|---|---|
| `gaia build compile` | 包能否编译成 IR |
| `gaia build check` | IR 结构合法性 |
| `gaia build check --hole` | 哪些 prior 缺失（MaxEnt 自由度报告） |
| `gaia build check --gate` | 哪些 reasoning 还没通过 review gate |
| `gaia inquiry review` | 作者面 review 流，逐条 accept/reject reasoning |
| `gaia inquiry review` 的 `prior_dissent` 诊断 | 多源 prior 数值差距过大时报警（[`gaia/engine/inquiry/diagnostics.py`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/gaia/engine/inquiry/diagnostics.py)） |
| `gaia inquiry review` 的 `prior_overridden` 诊断 | resolved prior 不是默认源时报警 |
| `gaia run infer` | BP 推理，输出 belief |
| `gaia inspect starmap` | 可视化整张推理图（HTML） |
| `gaia trace verify / review / inspect` | 独立 sub-app，audit 推理路径 |

**Soundness 不是数边数**——是这套 CLI + `register_prior` 的 source_id/justification 全部能 walk。

> 详见 [CLI Workflow](../foundations/cli/workflow.md) 和 [CLI Commands](cli-commands.md)。

## 7. 推理 belief 偏离合理范围 — 反推 4 类 root cause

Gaia BP 是 **(priors + reasoning structure) → beliefs** 的确定性映射。当 `gaia run infer` 输出的 belief 让你直觉上不舒服，回去检查的不是 BP 算法，而是**逻辑结构**。

按从最容易踩到最 nontrivial 的顺序排：

```text
belief 异常偏离 → 检查顺序
├── 7.1 逻辑推理关系错了（derive 反向了？应该用 infer 的地方用了 derive？）
├── 7.2 同源证据被 double counting
├── 7.3 claim 不够原子化，多个事实捆绑在一个变量
└── 7.4 结构正确但反直觉——是真正的贝叶斯洞见
```

下面 4 个子节各对应一个 didactic toy package（在 [`examples/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples) 下，可直接 `gaia build compile` + `gaia run infer` 跑通）。每节给出错误代码片段、正确代码片段、各自的 belief 数值、判别信号。聚合页见 [Examples / Formalization Debug Cases](../examples/formalization-debug-cases.md)。

### 7.1 逻辑推理关系错了

**toy 包**：[`examples/derive-direction-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/derive-direction-toy-gaia)

**症状**：单个 claim 的 belief 异常贴近 0 或 1，超出证据强度应该提供的更新幅度。

**常见原因**：把本应是 (C) 主观 likelihood 的证据关系（用 `infer`）写成 (A) 硬逻辑（用 `derive`）；或者 `derive` 方向反了（写成 `derive(cause, given=[effect])` 而不是 `derive(effect, given=[cause])`）。这是 §2 三类关系最常被踩混的边界——(A) 在 v0.5 lower 成接近确定性的 IMPLICATION potential，方向一旦反或者本来就不该是硬逻辑，BP 就会把 belief 强 push 过去。

**错误写法**（不要写）：

```python
it_rained = claim("It rained today.", label="it_rained")
ground_is_wet = claim("The ground is wet.", label="ground_is_wet")

# WRONG: this encodes "wet ground logically implies rain"
derive(
    it_rained,
    given=[ground_is_wet],
    rationale="...",
)
observe(ground_is_wet)
```

`register_prior(it_rained, 0.05, ...)` 之后跑 infer：**`it_rained` belief = 0.97**。`derive` 把"地湿就下雨过"当 logical implication，IMPLICATION potential 接近确定性，让低 prior 也被推到接近 1。

**正确写法**：

```python
infer(
    evidence=ground_is_wet,
    hypothesis=it_rained,
    p_e_given_h=0.95,        # 下雨后地湿
    p_e_given_not_h=0.20,    # 没下雨地也可能湿（洒水、邻居浇花、露水）
    rationale="...",
)
observe(ground_is_wet)
```

跑 infer：**`it_rained` belief = 0.20**——经典 Bayes posterior：`0.95 · 0.05 / (0.95 · 0.05 + 0.20 · 0.95) ≈ 0.20`。

**判别信号**：写完之后用 5 秒手算"如果只看这条 reasoning，likelihood ratio 是多少？" 如果你的 likelihood ratio 是 9.5（如 `0.95 / 0.10`），后验从 prior 0.05 移到 0.20 是合理的——belief 飙到 0.97 说明你写的不是 likelihood，是 implication，回去 §2 表格选对 verb。

### 7.2 Double counting

**toy 包**：[`examples/double-counting-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/double-counting-toy-gaia)

**症状**：某个 hypothesis 的 belief 被推得过高/过低，且追溯发现"同一份证据"通过多条 path 影响它。

**常见原因**：

- 同一 lab 报告被作者写成两条独立 evidence claim（一条说"titer 高"、一条说"panel 阳性"），各自做一次 `infer`——其实是同一份测量。
- 同一份 meta-analysis 既被 `register_prior` 反映到 hypothesis 的先验里（"prior=0.85 based on M-2024"），又通过 `bayes.likelihood` 再次进入。
- 一个 claim 被多条 `derive` 链通过同源前提到达，前提背后是同一份原始证据。

**错误写法**（不要写）：

```python
disease_x = claim("Patient has rare disease X.")
titer_high = claim("Antibody titer is above threshold.")
panel_positive = claim("Biomarker panel positive.")

# WRONG: 同一份 lab assay 拆成两条 evidence claim
infer(evidence=titer_high,    hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
infer(evidence=panel_positive, hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
observe(titer_high)
observe(panel_positive)
```

`register_prior(disease_x, 0.05)` 之后跑 infer：**`disease_x` belief = 0.81**——同一份 9× likelihood ratio 被乘了两次。

**正确写法**：

```python
disease_x = claim("Patient has rare disease X.")
lab_assay_positive = claim("The lab assay returned positive.")

infer(evidence=lab_assay_positive, hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
observe(lab_assay_positive)
```

跑 infer：**`disease_x` belief = 0.32**——单一证据的合理后验（手算 `0.90 · 0.05 / (0.90 · 0.05 + 0.10 · 0.95) ≈ 0.32`）。

**判别信号**：当 belief 看起来过高时，沿 `gaia inspect starmap` 把所有指向该变量的入边追到根。如果根上的 evidence 在物理 / 数据来源上是同一件事，就是 double counting。修复方式是合并成单一 canonical evidence claim。

### 7.3 Claim 不够原子化

**toy 包**：[`examples/non-atomic-claim-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/non-atomic-claim-toy-gaia)

**症状**：某个 claim 的 belief 卡在 mid-range（接近 0.5–0.7 的中性），即使你已经为它加了多条强证据。或者反过来——多个独立证据的信号互相 cancel，作者无法判断哪个 sub-claim 被支持。

**常见原因**：一个 claim 把两件**应该独立 update** 的事捆在一起。例如 `claim("理论 T 预测 X 且实验 E 观察到 X（一致）")`——三件事："T 预测 X" + "E 观察到 X" + "二者一致"。当新数据出现"另一个 E' 观察到 not X"时，作者想 update 的是"E vs E' 一致性"那一支，但 BP 只能整体 update 这个捆绑 claim，信号被稀释。

**错误写法**（不要写）：

```python
# WRONG: 一个 claim 同时声明两个独立的疗效
ldl_and_heart_attack = claim(
    "Drug X reduces LDL cholesterol AND reduces heart-attack incidence."
)

# 一个 trial 给两个 endpoint 各做一次 likelihood update
infer(evidence=ldl_endpoint_positive,
      hypothesis=ldl_and_heart_attack,
      p_e_given_h=0.95, p_e_given_not_h=0.10)
infer(evidence=heart_attack_endpoint_null,
      hypothesis=ldl_and_heart_attack,
      p_e_given_h=0.20, p_e_given_not_h=0.85)
observe(ldl_endpoint_positive)
observe(heart_attack_endpoint_null)
```

`register_prior(ldl_and_heart_attack, 0.5)` 之后跑 infer：**`ldl_and_heart_attack` belief = 0.69**——一个中性偏高的数字，**作者从这一个数字读不出来**到底是 LDL 那支强还是 HA 那支被否定。两个信号 collapse 进同一变量。

**正确写法**：

```python
reduces_ldl           = claim("Drug X reduces LDL cholesterol.")
reduces_heart_attacks = claim("Drug X reduces heart-attack incidence.")

infer(evidence=ldl_endpoint_positive,
      hypothesis=reduces_ldl,
      p_e_given_h=0.95, p_e_given_not_h=0.10)
infer(evidence=heart_attack_endpoint_null,
      hypothesis=reduces_heart_attacks,
      p_e_given_h=0.20, p_e_given_not_h=0.85)
observe(ldl_endpoint_positive)
observe(heart_attack_endpoint_null)
```

跑 infer：**`reduces_ldl` = 0.90、`reduces_heart_attacks` = 0.19**——两个清晰可读的信号。LDL 那支强支持，HA 那支被反驳。作者能据此做决策。

**判别信号**：当一个 claim 的 belief 在 0.4–0.7 之间停滞，看一下 claim 的 content 字符串里有没有 "AND" / "并且" / "同时" / "对...也" 之类的连接词。如果有，多半是该拆。

### 7.4 真正的贝叶斯悖论（结构对，直觉错）

**toy 包**：[`examples/base-rate-fallacy-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/base-rate-fallacy-toy-gaia)

**症状**：上面 7.1 / 7.2 / 7.3 都排除后，belief 仍然反直觉。**这时是包对了，直觉错了**——这是科学 insight，不是 bug。

**常见情形**：

- **Base-rate fallacy**：高敏感度测试 + 低患病率 → 阳性的人真患病率很低
- **Simpson's paradox**：aggregated 趋势与 stratified 趋势相反
- **Berkson's paradox**：条件化引入虚假关联

**例子（base-rate fallacy）**：

```python
disease_x = claim("Patient has rare disease X.")
test_positive = claim("Test for X returned positive.")

infer(evidence=test_positive, hypothesis=disease_x,
      p_e_given_h=0.95,        # sensitivity
      p_e_given_not_h=0.05)    # 1 - specificity
observe(test_positive)
```

`register_prior(disease_x, 0.01)` 之后跑 infer：**`disease_x` belief = 0.16**。

**直觉冲突**：测试 95% 准确，阳性结果应该 ≈ 95% 患病？

**Bayes 答案**：`0.95 · 0.01 / (0.95 · 0.01 + 0.05 · 0.99) = 0.16`。低基率 prior `0.01` 在 19:1 的 likelihood ratio 后仍然只移到 0.16。

**判别信号**：

- 如果你套 7.1 的修复（换 verb）—— belief 不变（因为 verb 已经选对了）。
- 如果你套 7.2 的修复（去重 evidence）—— belief 不变（因为没有 double counting）。
- 如果你套 7.3 的修复（拆 claim）—— belief 不变（因为 claim 已经原子）。
- 如果**三个都不动 belief**——这就是 §7.4：保持包不动，去 update 直觉。

**实操建议**：把 prior、likelihood ratio、posterior 三个数字写进 `rationale` 字段。当审稿人看到反直觉 belief 时，能从 rationale 里一眼读出 Bayes 算式确认结构对。

> §7.4 是 Gaia 的 **scientific value**：它把"直觉感觉对/不对"和"Bayes 数学算的对/不对"分到了两个不同的 audit channel。包对了不等于答案符合直觉；这正是把推理形式化的意义。

## 8. 提交前 checklist

- [ ] §1 第一层选择：每个事实，要么是直接 `claim()`，要么由 reasoning verb 生成；没有"同时"
- [ ] §2 第二层选择：每个 reasoning verb 选对了客观/主观档位（`bayes.*` 是客观，`infer`/`associate` 是主观）
- [ ] §3 数值测量走 `Distribution + observe(dist, value, error) + bayes.likelihood`，不用 formula binding 替代
- [ ] §4 每个 `register_prior` 有非空 `justification` + 合适的 `source_id`
- [ ] §5 `bayes.model` 的 distribution 参数与 `observe(dist, ...)` 喂进去的数据来源**分开**
- [ ] §6 没有用"边数对称 / 拓扑均衡"作 audit 标准；用 `gaia build check` / `gaia inquiry review` / `gaia inspect starmap`
- [ ] §7 跑完 `gaia run infer`，每个 belief 数值都过得了 §7.1–7.4 的 sanity check

## 9. 延伸阅读

- [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md) — Knowledge 与 Reasoning verb 的本体分层、IR lowering 规则
- [Bayes Semantics](../foundations/gaia-lang/bayes.md) — `bayes.model` / `bayes.likelihood` 的客观 likelihood 设计
- [Theory § Formalization Methodology](../foundations/theory/05-formalization-methodology.md) — 形式化方法论的整体框架
- [Theory § Causality and Jaynes](../foundations/theory/08-causality-and-jaynes.md) §8 — Verb 决策表（含 `mechanism()` v0.6 拓展）
- [Belief Propagation § Inference](../foundations/bp/inference.md) — Prior 赋值规则、Cromwell ε 钳制
- [Belief Propagation § Choosing An Algorithm](../foundations/bp/choosing-algorithm.md) — Belief 数值的 BP 算法路径
- [Examples / Formalization Debug Cases](../examples/formalization-debug-cases.md) — §7 全部 4 个 toy 包的聚合页
