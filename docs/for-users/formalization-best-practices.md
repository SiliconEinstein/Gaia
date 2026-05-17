# How to write a sound Gaia formalization

> **Gaia version:** 0.5.x
> **Author:** @kunyuan
> **Date:** 2026-05-17

把领域问题（临床试验、因果论证、模型比较等）写成 Gaia 包时，你需要做一串选择：

1. 这个事实是直接写成一个 `claim`，还是通过 reasoning verb 生成？
2. 如果用 verb，选哪一个？
3. 先验怎么设？
4. 数值测量用什么 API？
5. `gaia run infer` 跑出来的 belief 不对，回去查什么？

本页按决策顺序逐一给出判断标准。读完你会有一个提交前的自检清单，以及 4 个可运行的 toy 包帮你定位最常见的 belief 异常。

## 前提

- 已完成 [Quick Start](quick-start.md) 并能编译一个最小 package
- 了解 [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md) 中 `Claim` 与 reasoning verb 的区别
- 了解 [Bayes Semantics](../foundations/gaia-lang/bayes.md) 中 `bayes.model` / `bayes.likelihood` 的用途

## 1. 先建节点，再连边

写 Gaia 包就是建一张图：**命题是节点，关系是边**。写作顺序也是两步——先创建所有 claim（节点），再用 reasoning verb 把它们连起来（边）。

```text
claim("药物 X 降低 LDL")          ← 节点
claim("药物 X 降低心梗发生率")     ← 节点
claim("LDL 终点达到显著性")        ← 节点

infer(evidence=ldl_endpoint, hypothesis=reduces_ldl, ...)  ← 边
```

> **常见误解**：把 `observe(claim_x)` 当成"给 `claim_x` 打一个观察标签"。实际上 `observe` 是一个 reasoning 动作——它在 IR 里是一个 Reasoning 节点，把已有 claim 固定为"已观察到为真"。详见 [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md)。

claim 要拆得够细——不要把多件事捆在一个节点里。捆绑节点让证据无法分别更新内部各成分（见 §7.3）。

## 2. 选哪个 reasoning verb？

Gaia v0.5 的 reasoning verb 分**三类**，分别对应完全不同的关系：

| 类别 | verb | 在 BP 里的效果 | 什么时候用 |
|---|---|---|---|
| **(A) 硬逻辑** | `derive` / `equal` / `contradict` / `equivalence` / `complement` | 接近 0/1 的硬约束（不是概率） | 逻辑必然、关系断言 |
| **(B) 客观似然** | `bayes.likelihood`（+ `bayes.model` + `Distribution`） | 从分布函数自动算出似然度 | 有数值测量 + 概率分布模型 |
| **(C) 主观似然** | `infer` / `associate` | 作者填写 `p_e_given_h` 等参数 | 专家判断、文献定性总结、无法用分布函数表达的关联 |

> **关键**：三类各有承诺，选错是 §7 最常见的 bug 来源。
> - (A) 不是概率关系——把方向性的概率证据写成 `derive` → §7.1。
> - (B) 的似然度从分布函数算，不从作者笔下来——把数值测量写成主观 `infer` → §3。
> - (C) 的 `justification` 必须能向审查者交代似然度比值来源。

具体怎么选：

**第一步：创建命题**

```text
这件事需要被单独赋真值、被证据更新、或作为推理的起点/终点吗？
├── 是 → claim("...")   （大多数情况）
└── 不需要单独存在，它只是推理的中间产物 → 跳过，推理 verb 会自动生成
```

**第二步：连接命题**

你已经有了一组 claim，现在要表达它们之间的关系：

```text
这是什么关系？
│
├── 已观察到为真
│   ├── 无条件（"我看到了 / 测到了"）→ observe(claim)
│   └── 有条件（"在 X 的前提下观察到了 Y"）→ observe(claim, given=[前提])
│       与无条件不同：带 given= 的 observe 不会把 claim 钉到 1.0，
│       它只记录条件观察关系，belief 仍由 BP 推算。
│
├── 逻辑/数学必然
│   ├── A 推出 B    → derive(B, given=[A])
│   ├── A 与 B 等价 → equal(A, B)
│   └── A 与 B 互斥 → contradict(A, B)
│
├── 数值测量 + 概率分布（如 "log(RR) = -0.151 ± 0.05"）
│   └── Distribution + bayes.model + bayes.data(observable, value, error) + bayes.likelihood
│        （详见 §3）
│
└── 作者主观似然度判断
    ├── E 是 H 的证据 → infer(evidence=E, hypothesis=H, p_e_given_h=..., p_e_given_not_h=...)
    └── A 与 B 对称关联 → associate(A, B, p_a_given_b=..., p_b_given_a=...)
```

> **💡 快速自检**：写完每个 verb 后问自己——这个关系真的是我选的那一类吗？如果我选了 `derive`，它真的是逻辑必然，还是我其实在表达一个概率证据？

## 3. 数值测量：用 `bayes` 模块

带不确定性的数值测量（比如"log(RR) = -0.151 ± 0.05"）在 v0.5 里有专门 API：

```python
import gaia.engine.bayes as bayes
from gaia.engine.lang import Real, Variable, parameter

effect = Variable(symbol="effect", domain=Real)
log_rr = Variable(symbol="log_rr", domain=Real)

h_effective = parameter(
    effect,
    -0.10,
    content="The intervention has a clinically meaningful negative log(RR).",
    prior=0.5,
    label="h_effective",
)
h_null = parameter(
    effect,
    0.0,
    content="The intervention has no log(RR) effect.",
    prior=0.5,
    label="h_null",
)

# 在每个竞争假设下，log(RR) 围绕该假设的 effect 值波动
model_effective = bayes.model(
    h_effective,
    observable=log_rr,
    distribution=bayes.Normal(mu=effect, sigma=0.05),
)
model_null = bayes.model(
    h_null,
    observable=log_rr,
    distribution=bayes.Normal(mu=effect, sigma=0.05),
)

# 实际测得的 log(RR) 数值（带误差）
data = bayes.data(log_rr, value=-0.151, error=0.05, label="observed_log_rr")

bayes.likelihood(data, model=model_effective, against=[model_null])
```

这里有两个容易混淆的点：

- `bayes.Normal(..., sigma=...)` 的参数名是 `sigma`，不是 `sd`。
- `bayes.data(...)` 才是 `bayes.likelihood(...)` 的观测数据入口。`observe(distribution, value=..., error=...)` 属于"单个不确定 quantity + predicate"表面，用来记录 measurement event；它不会生成 `bayes.likelihood(...)` 所需的 observed formula Claim。

**不要这样写**（把数值绑到 claim 上再手工给似然度）：

```python
# 错误：绕过了 bayes 模块的整套似然度计算
log_rr_var = Variable(symbol="log_rr", domain=Real)
data_claim = claim(
    "log(RR) ≈ -0.151",
    formula=equals(log_rr_var, Constant(-0.151, Real)),
)
observe(data_claim)
infer(evidence=data_claim, hypothesis=h_effective,
      p_e_given_h=0.95, p_e_given_not_h=0.10)  # 作者手工填的似然度
```

错在哪：distribution 函数会从 `(mu, sigma)` 自动算出每个假设下 observed value 的似然度，作者不需要也不应该手工给 `p_e_given_h`。这是把应该走 (B) 客观似然度的场景错写成 (C) 主观。

**什么时候确实该用 `infer`**：流行病学关联（"RR 0.86, CI 0.79–0.92" 是 meta-analysis 总结，不是某个分布函数能直接算的）、案例报告、专家定性证据。这时手工填似然度比值是诚实的——你把"我作为作者认为这是有力证据"显式量化为数字，在 `justification` 里说明为什么这么填。

> 详见 [Bayes Semantics § Hypothesis comparison surface](../foundations/gaia-lang/bayes.md#hypothesis-comparison-surface-existing-v05)。

## 4. 设先验：`register_prior`

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

三个要点：

- **value 必须在 `[0.001, 0.999]` 内**（Cromwell 钳制边界）。边界上的"确定 prior"几乎总是 bug——通常意味着你想表达的是"已观察到为真"，应该用 `observe(claim)`。
- **justification 必填**。空字符串或全空白会被拒绝。设先验是方法论上重的动作，必须能回答"这个数字从哪来"。
- **source_id 标识来源**。同一 claim 可以有 `"user_priors"`（作者）/ `"continuous_inference"`（自动推断）/ `"reviewer_alice"`（审稿人）等多条记录。编译时 `ResolutionPolicy` 选 winning value；所有记录（含落选）都进 IR，可被 `gaia inquiry review` 诊断查询。

> Gaia 不规定 prior 数值的生成方法。`justification` 是给审查者读的字符串，没有 magic 关键词。诚实地写"这个 0.7 来自 Doll-Hill 1956 + 2024 更新元分析的低偏倚子集，我把 generalization concern 从 0.65 上调到 0.7"——这是好 justification。"chainAnalysis prior=0.7" 不是。
>
> 详见 [`register_prior` docstring](https://github.com/SiliconEinstein/Gaia/blob/v0.5/gaia/engine/lang/dsl/register_prior.py)。

> **💡 快速自检**：你能用一句话说出这个 prior 数值的来源吗？如果不能，回去补 `justification`。

## 5. `bayes.model` 的参数不能来自同一份数据

`bayes.model(hypothesis, observable=..., distribution=...)` 的核心规则：

**distribution 的参数和 `bayes.data(..., value, error)` 的数据必须来自不同来源。**

| 参数来源 | 是否合法 |
|---|---|
| 领域知识、独立 calibration 数据集、姐妹研究、文献总结 | ✅ 合法 |
| 同一份要检验数据的点估计 / 标准误 | ❌ 用同一份数据 fit 模型再检验该模型 |
| Empirical Bayes / hierarchical prior，**只要 prior 数据集和 likelihood 数据集分开** | ✅ 合法 |

写完 `bayes.model(..., distribution=Normal(mu=X, sigma=Y))` 后问自己：**"`X` 和 `Y` 这两个数字，我是怎么知道的？"** 如果答案是"从我马上要 `bayes.data(...)` 进 likelihood 的同一份数据里算出来的"，回去 §2 选 `infer` 而不是 `bayes`，或者找一份独立的 prior 数据集。

## 6. 工作流：从代码到 belief

写完 `__init__.py` 和 `priors.py` 之后，接下来的 pipeline 是固定的。每一步的输出是下一步的输入。

```text
① 编译                ② 检查                 ③ 审查（可选）          ④ 门禁（发布前）        ⑤ 推理                ⑥ 渲染                 ⑦ 注册
gaia build compile →  gaia build check     →  gaia inquiry review →  gaia build check    →  gaia run infer     →  gaia run render     →  git tag
                      --hole                                        --gate                                                        gaia pkg register
```

| 步骤 | 命令 | 必须？ | 干什么 | 通过标准 |
|---|---|---|---|---|
| **① 编译** | `gaia build compile` | ✅ 必须 | 把 Python 代码编译成 IR。失败说明代码有语法/语义错误。 | 无报错退出 |
| **② 检查** | `gaia build check --hole` | ✅ 必须 | 检查 IR 结构合法性 + 列出缺失 prior 的 claim。是 `check` 的超集。逐个补 `register_prior` 直到输出为空。 | 无结构错误 + 无 hole |
| **③ 审查** | `gaia inquiry review` | 可选 | 交互式逐条 accept/reject reasoning，检查 prior_dissent（多源 prior 差距过大）、prior_overridden（resolved prior 不是默认源）。多人协作时推荐。 | 无 unresolved dissent |
| **④ 门禁** | `gaia build check --gate` | 发布前推荐 | 质量关卡：检查是否还有未补的 hole、未 formalize 的依赖、未经 review accept 的 reasoning。有任何一项未通过则 exit non-zero。 | Quality gate passed |
| **⑤ 推理** | `gaia run infer` | ✅ 必须 | 运行 BP，输出每个 claim 的 belief。 | 无报错；belief 数值通过 §7 sanity check |
| **⑥ 渲染** | `gaia run render` | 发布前 | 生成 presentation 产物：`--target docs` 输出 `docs/detailed-reasoning.md`，`--target github`（需先 infer）输出 `.github-output/`。 | 产物生成成功 |
| **⑦ 注册** | `git tag v<version>` + `gaia pkg register` | 发布时 | 打版本标签，提交到 Gaia registry。 | registry PR 创建成功 |

调试工具（belief 异常时用，不属于 pipeline 主线）：

| 命令 | 干什么 |
|---|---|
| `gaia inspect starmap` | 生成整张推理图（HTML），反向追踪证据路径 |
| `gaia trace verify / review / inspect` | 逐路径 audit 推理链 |

> 不要用"边数对称 / 孤儿节点 / 拓扑均衡"当 audit 标准——soundness 不来自拓扑，来自每一步 CLI 的结果 + `register_prior` 的 source_id/justification 全部可追溯。

日常开发的最小循环：

```text
compile → check --hole → 补 prior → compile → check --hole（确认无 hole）→ infer
```

`--hole` 是无参数 `check` 的超集——它包含全部基础结构诊断，再加 prior 缺失报告。有 hole 就回去补 `register_prior` 重新编译，直到 `--hole` 输出为空再进 infer。

> 详见 [CLI Workflow](../foundations/cli/workflow.md) 和 [CLI Commands](cli-commands.md)。

## 7. Belief 不对？按这 4 步反推

`gaia run infer` 输出的 belief 让你觉得不对劲时，回去检查的不是 BP 算法，而是**你写的逻辑结构**。按顺序排查：

1. **推理关系写错了？** — 该用 `infer` 的地方用了 `derive`？`derive` 方向反了？
2. **同一份证据被重复计数？** — 同一份数据通过多条路径进入 BP
3. **一个 claim 里捆了多件事？** — 外部证据无法分别更新
4. **以上都不是？** — 代码对，直觉需要更新

定位到问题后，改代码，然后重新走 §6 的循环：`compile → check --hole → infer`。**注意**：修改推理结构（比如拆 claim、换 verb）可能引入新的 hole，所以不要跳过 `check --hole`。

下面 4 个子节各对应一个可运行的 toy 包（在 [`examples/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples) 下，可直接 `gaia build compile` + `gaia run infer` 跑通）。聚合页见 [Examples / Formalization Debug Cases](../examples/formalization-debug-cases.md)。

### 7.1 把概率证据写成了硬逻辑

**Toy 包**：[`examples/derive-direction-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/derive-direction-toy-gaia)

**症状**：某个 claim 的 belief 异常贴近 0 或 1（比如 0.97），远超证据强度应该提供的更新幅度。

**常见原因**：把本应是主观似然度的证据关系（用 `infer`）写成了硬逻辑（用 `derive`）；或者 `derive` 方向反了（`derive(cause, given=[effect])` 而不是反过来）。§2 (A) 类在 BP 中 lower 成接近确定性的约束——方向一反或关系类型选错，belief 就被强推进角落。

**错误写法**（不要这样写）：

```python
it_rained = claim("It rained today.", label="it_rained")
ground_is_wet = claim("The ground is wet.", label="ground_is_wet")

# 错误：这行编码的是"地湿逻辑上蕴含下过雨"
derive(
    it_rained,
    given=[ground_is_wet],
    rationale="...",
)
observe(ground_is_wet)
```

`register_prior(it_rained, 0.05, ...)` 之后跑 infer：**`it_rained` = 0.97**。`derive` 把"地湿就下雨过"当逻辑必然，低 prior 也被推到接近 1。

**正确写法**：

```python
infer(
    evidence=ground_is_wet,
    hypothesis=it_rained,
    p_e_given_h=0.95,        # 下雨后地湿
    p_e_given_not_h=0.20,    # 没下雨地也可能湿（洒水、露水）
    rationale="...",
)
observe(ground_is_wet)
```

跑 infer：**`it_rained` = 0.20**。手算验证：`0.95 × 0.05 / (0.95 × 0.05 + 0.20 × 0.95) ≈ 0.20`。

> **💡 判别**：写完用 5 秒手算——只看这条 reasoning，似然度比值是多少？如果比值 ~5 但 belief 飙到 0.97，说明你写的不是似然度，是逻辑必然。回去 §2 选对 verb。

### 7.2 同一份证据被重复计数

**Toy 包**：[`examples/double-counting-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/double-counting-toy-gaia)

**症状**：某个 hypothesis 的 belief 被推得过高，追溯发现"同一份证据"通过多条路径影响它。

**常见原因**：

- 同一份 lab 报告被拆成两条独立 evidence claim（"titer 高" + "panel 阳性"），各做一次 `infer`——其实是同一份测量。
- 同一份 meta-analysis 既反映在 prior 里，又通过 `bayes.likelihood` 再次进入。
- 一个 claim 被多条 `derive` 链通过同源前提到达。

**错误写法**（不要这样写）：

```python
disease_x = claim("Patient has rare disease X.")
titer_high = claim("Antibody titer is above threshold.")
panel_positive = claim("Biomarker panel positive.")

# 错误：同一份 lab assay 拆成两条 evidence claim
infer(evidence=titer_high,    hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
infer(evidence=panel_positive, hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
observe(titer_high)
observe(panel_positive)
```

`register_prior(disease_x, 0.05)` 之后跑 infer：**`disease_x` = 0.81**。同一份 9× 似然度比值被乘了两次。

**正确写法**：

```python
disease_x = claim("Patient has rare disease X.")
lab_assay_positive = claim("The lab assay returned positive.")

infer(evidence=lab_assay_positive, hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
observe(lab_assay_positive)
```

跑 infer：**`disease_x` = 0.32**。手算验证：`0.90 × 0.05 / (0.90 × 0.05 + 0.10 × 0.95) ≈ 0.32`。

> **💡 判别**：用 `gaia inspect starmap` 把所有指向该变量的入边追到根。如果根上的 evidence 在物理/数据来源上是同一件事，合并成单一 evidence claim。

### 7.3 一个 claim 里捆了多件事

**Toy 包**：[`examples/non-atomic-claim-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/non-atomic-claim-toy-gaia)

**症状**：某个 claim 的 belief 卡在 0.4–0.7 的中性段，即使你已经为它加了多条强证据。或者多个独立证据的信号互相 cancel，你不知道哪个子结论被支持。

**常见原因**：一个 claim 把两件应该独立 update 的事捆在一起。例如 `claim("药物 X 降低 LDL 且降低心梗发生率")`——两条独立疗效。当 LDL 那支证据强而心梗那支证据弱时，两个信号 collapse 进同一个变量，belief 给出一个中性数字，作者无法据此做决策。

**错误写法**（不要这样写）：

```python
# 错误：一个 claim 同时声明两个独立疗效
ldl_and_heart_attack = claim(
    "Drug X reduces LDL cholesterol AND reduces heart-attack incidence."
)

infer(evidence=ldl_endpoint_positive,
      hypothesis=ldl_and_heart_attack,
      p_e_given_h=0.95, p_e_given_not_h=0.10)
infer(evidence=heart_attack_endpoint_null,
      hypothesis=ldl_and_heart_attack,
      p_e_given_h=0.20, p_e_given_not_h=0.85)
observe(ldl_endpoint_positive)
observe(heart_attack_endpoint_null)
```

`register_prior(ldl_and_heart_attack, 0.5)` 之后跑 infer：**`ldl_and_heart_attack` = 0.69**。一个中性偏高的数字，看不出 LDL 那支强还是 HA 那支被否定。

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

跑 infer：**`reduces_ldl` = 0.90**、**`reduces_heart_attacks` = 0.19**。两个清晰可读的信号，作者能据此做决策。

> **💡 判别**：当一个 claim 的 belief 卡在 0.4–0.7，看 content 字符串里有没有 "AND" / "并且" / "同时" / "对...也"。有就该拆。

### 7.4 代码没错，直觉需要更新

**Toy 包**：[`examples/base-rate-fallacy-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/base-rate-fallacy-toy-gaia)

**症状**：上面 7.1–7.3 全部排除后，belief 仍然反直觉。**这时是包对了，直觉错了。**

**常见情形**：Base-rate fallacy（低基率 + 高敏感度测试 → 阳性后验仍然低）、Simpson's paradox、Berkson's paradox。

```python
disease_x = claim("Patient has rare disease X.")
test_positive = claim("Test for X returned positive.")

infer(evidence=test_positive, hypothesis=disease_x,
      p_e_given_h=0.95,        # sensitivity
      p_e_given_not_h=0.05)    # 1 - specificity
observe(test_positive)
```

`register_prior(disease_x, 0.01)` 之后跑 infer：**`disease_x` = 0.16**。

**直觉冲突**：测试 95% 准确，阳性后应该 ≈ 95% 患病？**Bayes 答案**：`0.95 × 0.01 / (0.95 × 0.01 + 0.05 × 0.99) ≈ 0.16`。1% 的低基率 prior 在 19:1 的似然度比值后仍然只移到 0.16。

> **💡 判别**：依次尝试 §7.1（换 verb）、§7.2（去重）、§7.3（拆 claim）的修复。如果 belief 三次都不变——保持包不动，去更新直觉。建议把 prior、似然度比值、后验三个数字写进 `rationale`，审查者看到反直觉 belief 时能一眼验算。

## 8. 提交前：跑一遍完整 pipeline

**CLI 能自动检查的**，一条命令不通过就不能提交：

```text
gaia build compile          ← 能编译通过
gaia build check --hole     ← 无结构错误、无缺失 prior
gaia build check --gate     ← 质量门禁：无 hole、无未审查 reasoning、无未 formalize 依赖
gaia run infer              ← BP 推理无报错，belief 输出完整
```

如果 `check --gate` 要求审查完所有 reasoning，先跑 `gaia inquiry review` 逐条 accept/reject，再回到 `--gate`。

**CLI 检查不出来、需要你手动判断的**：

- [ ] 每个 `register_prior` 的 `justification` 能说清数值来源——CLI 只检查非空，不检查写的是什么
- [ ] `bayes.model` 的参数和 `bayes.data(...)` 的数据不是同一份——CLI 不知道你的数据来源
- [ ] `gaia inspect starmap` 看一眼图——没有反向 derive、没有同一份证据被拆成多条边、没有把多件事写进同一个 claim（详见 §7.1–7.3 的判别信号）
- [ ] belief 数值在领域语境下合理——CLI 只算数，不判断合不合理

## 9. 提交

§8 全部通过后：

```text
gaia run render                  ← 生成 presentation 产物：docs/detailed-reasoning.md
                                 （--target github 需要先跑过 infer）
git tag v<version>               ← 打版本标签
gaia pkg register                ← 提交到 Gaia registry
```

> 完整 pipeline 详见 [CLI Workflow](../foundations/cli/workflow.md)。

## 10. 延伸阅读

- [Knowledge And Reasoning](../foundations/gaia-lang/knowledge-and-reasoning.md) — Knowledge 与 Reasoning verb 的本体分层、IR lowering 规则
- [Bayes Semantics](../foundations/gaia-lang/bayes.md) — `bayes.model` / `bayes.likelihood` 的客观 likelihood 设计
- [Theory § Formalization Methodology](../foundations/theory/05-formalization-methodology.md) — 形式化方法论的整体框架
- [Theory § Causality and Jaynes](../foundations/theory/08-causality-and-jaynes.md) §8 — Verb 决策表（含 `mechanism()` v0.6 拓展）
- [Belief Propagation § Inference](../foundations/bp/inference.md) — Prior 赋值规则、Cromwell ε 钳制
- [Belief Propagation § Choosing An Algorithm](../foundations/bp/choosing-algorithm.md) — Belief 数值的 BP 算法路径
- [Examples / Formalization Debug Cases](../examples/formalization-debug-cases.md) — §7 全部 4 个 toy 包的聚合页
