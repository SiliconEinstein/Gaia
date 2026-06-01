# Bayes 模块：LDL 降低药物 Phase II 示例

这个示例展示当前 Bayes authoring surface 的完整用法：

- `gaia.engine.lang` 提供变量、分布、观察、结构推理和先验注册。
- `gaia.engine.bayes` 提供 `bayes.model(...)` 和 `bayes.compare(...)`。
- 三个竞争假设同时接受两个观测指标的更新：连续 LDL 降低百分比和离散达标人数。
- 三模型比较必须显式使用 `exclusivity="pairwise_contradiction"`；当前 `exhaustive_pairwise_complement` 只支持两个模型。

## 场景

新型 PCSK9 抑制剂在 30 名他汀不耐受的高胆固醇患者中进行 Phase II 剂量探索试验，治疗 30 周后评估两个可观测指标：

| 指标 | 类型 | 变量 | 含义 |
|---|---|---|---|
| LDL 降低百分比 | 连续 `Normal` | `ldl_pct` | 个体 LDL-C 相对于基线的降低幅度 |
| 达标人数 | 离散 `Binomial` | `responders` | 达到至少 50% LDL 降低的患者数 |

## 三个竞争假设

| 假设 | LDL 均值降低 | 标准差 | 达标率 | 先验 |
|---|---:|---:|---:|---:|
| `h_strong` | 45% | 12% | 70% | 0.4 |
| `h_moderate` | 28% | 10% | 40% | 0.4 |
| `h_weak` | 12% | 8% | 10% | 0.2 |

观测数据：

- 30 名患者平均 LDL 降低 = 38%，测量误差 SEM = 2.2%。
- 17/30 名患者达到至少 50% LDL 降低。

## Package source

Put this code in `src/ldl_trial/__init__.py` of a Gaia package. The source uses
only the public authoring surfaces: `gaia.engine.lang` for DSL objects and
`gaia.engine.bayes` for model comparison. Compile and infer through the CLI
commands below rather than importing `gaia.engine.bp.*` internals.

```python
"""LDL 降低药物 Phase II 试验：三假设 Bayes 比较。"""

from gaia.engine.lang import (
    Binomial,
    Nat,
    Normal,
    Probability,
    Real,
    Variable,
    claim,
    derive,
    note,
    observe,
    parameter,
    register_prior,
)
import gaia.engine.bayes as bayes


# 1. 可观测变量
ldl_pct = Variable(symbol="ldl_pct", domain=Real)
responders = Variable(symbol="responders", domain=Nat)
response_rate = Variable(symbol="response_rate", domain=Probability)

context = note(
    "PCSK9 抑制剂通过阻止 LDL 受体降解来降低血浆 LDL-C。"
    "Phase II 试验纳入 30 名他汀不耐受的高胆固醇患者。"
)

# 2. 三个竞争假设。
# response_rate 是 deferred parameter；Binomial 模型会从各 hypothesis 的
# parameter(...) formula 中绑定 p。
h_strong = parameter(
    response_rate,
    0.70,
    content="强效模型：平均 LDL 降低约 45%，30 周达标率约 70%。",
    label="h_strong",
)
register_prior(
    h_strong,
    0.4,
    justification="同类 PCSK9 抑制剂 Phase II 数据支持较强疗效的先验可能性。",
)

h_moderate = parameter(
    response_rate,
    0.40,
    content="中等模型：平均 LDL 降低约 28%，30 周达标率约 40%。",
    label="h_moderate",
)
register_prior(
    h_moderate,
    0.4,
    justification="他汀不耐受患者中较弱反应也有相当先验可能性。",
)

h_weak = parameter(
    response_rate,
    0.10,
    content="弱效模型：平均 LDL 降低约 12%，30 周达标率约 10%。",
    label="h_weak",
)
register_prior(
    h_weak,
    0.2,
    justification="完全弱效概率较低，但剂量探索阶段仍不能排除。",
)

# 3. 观测数据。
# observe(variable, value=..., error=...) 会生成可被 bayes.compare 消费的
# observation claim。连续观测的 scalar error 表示加性 Normal 噪声。
data_ldl = observe(
    ldl_pct,
    value=38.0,
    error=2.2,
    rationale="30 名患者平均 LDL 降低 38%，SEM = 2.2%。",
    label="data_ldl",
)
data_resp = observe(
    responders,
    value=17,
    rationale="17/30 名患者 LDL 降低至少 50%。",
    label="data_resp",
)

# 4. 连续 LDL 降低的预测模型。
model_strong_ldl = bayes.model(
    h_strong,
    observable=ldl_pct,
    distribution=Normal("LDL under strong", mu=45.0, sigma=12.0),
    rationale="强效假设：平均 LDL 降低 45%，个体间变异 12 个百分点。",
    label="model_strong_ldl",
)
model_moderate_ldl = bayes.model(
    h_moderate,
    observable=ldl_pct,
    distribution=Normal("LDL under moderate", mu=28.0, sigma=10.0),
    rationale="中等假设：平均 LDL 降低 28%，个体间变异 10 个百分点。",
    label="model_moderate_ldl",
)
model_weak_ldl = bayes.model(
    h_weak,
    observable=ldl_pct,
    distribution=Normal("LDL under weak", mu=12.0, sigma=8.0),
    rationale="弱效假设：平均 LDL 降低 12%，个体间变异 8 个百分点。",
    label="model_weak_ldl",
)

# 5. 达标人数的预测模型。
# 这里三个模型复用同一个 Variable-backed Binomial 形状；具体 p 值由
# h_strong / h_moderate / h_weak 的 parameter(...) formula 决定。
responder_dist = Binomial("responders under response_rate", n=30, p=response_rate)
model_strong_resp = bayes.model(
    h_strong,
    observable=responders,
    distribution=responder_dist,
    rationale="强效假设：p = 0.70。",
    label="model_strong_resp",
)
model_moderate_resp = bayes.model(
    h_moderate,
    observable=responders,
    distribution=responder_dist,
    rationale="中等假设：p = 0.40。",
    label="model_moderate_resp",
)
model_weak_resp = bayes.model(
    h_weak,
    observable=responders,
    distribution=responder_dist,
    rationale="弱效假设：p = 0.10。",
    label="model_weak_resp",
)

# 6. 两个观测指标分别比较同一组三假设。
# 当前 exhaustive_pairwise_complement 只支持两个模型；三模型时使用
# pairwise_contradiction，语义是 at-most-one，允许 listed models 全错。
ldl_comparison = bayes.compare(
    data_ldl,
    models=[model_strong_ldl, model_moderate_ldl, model_weak_ldl],
    exclusivity="pairwise_contradiction",
    rationale="比较三种疗效模型对平均 LDL 降低的预测。",
    label="ldl_comparison",
)
resp_comparison = bayes.compare(
    data_resp,
    models=[model_strong_resp, model_moderate_resp, model_weak_resp],
    exclusivity="pairwise_contradiction",
    rationale="比较三种疗效模型对达标人数的预测。",
    label="resp_comparison",
)

# 7. 假设比较结果进入临床决策链。
recommend_phase3 = claim(
    "该 PCSK9 抑制剂应推进到 Phase III 关键试验。",
    label="recommend_phase3",
)
phase3_threshold = claim(
    "若强效模型成立，效应量足够支持推进 Phase III。",
    label="phase3_threshold",
)
register_prior(
    phase3_threshold,
    0.9,
    justification="平均 LDL 降低约 45% 明显超过 Phase II 继续开发阈值。",
)
derive(
    recommend_phase3,
    given=[h_strong, phase3_threshold],
    background=[context, ldl_comparison, resp_comparison],
    rationale="强效模型成立且效应量超过阈值时，推进 Phase III 是合理行动。",
    label="strong_model_to_phase3",
)
```

## Run it

Compile and infer through the public CLI:

```bash
gaia build compile ./ldl-trial-gaia
gaia run infer ./ldl-trial-gaia
```

The current engine gives these posterior values for the claims above:

```text
h_strong posterior   : 0.5258
h_moderate posterior : 0.2783
h_weak posterior     : 0.0000
Recommend Phase III  : 0.7362
```

在三模型 `pairwise_contradiction` 语义下，三个假设的后验不会强制归一化为 1，因为模型空间保留了“列出的三个模型都不完全正确”的状态。

## 关键机制

### 1. 多指标联合更新

两个 `bayes.compare(...)` action 分别把连续 LDL 数据和离散达标人数转成 likelihood factors。它们落到同一张 factor graph 上，因此会共同更新 `h_strong` / `h_moderate` / `h_weak`。

### 2. 测量噪声卷积

`observe(ldl_pct, value=38.0, error=2.2)` 把 SEM 写入 observation metadata。编译器在连续 likelihood 中把预测分布与测量噪声卷积：

```text
sigma_conv = sqrt(sigma_pred^2 + sigma_noise^2)
```

### 3. Deferred Variable binding

`Binomial("responders under response_rate", n=30, p=response_rate)` 中的 `response_rate` 是 `Variable`。编译时，`bayes.compare(...)` 会从每个 hypothesis 的 `parameter(response_rate, value)` formula 中绑定具体值：

- `h_strong` -> `p = 0.70`
- `h_moderate` -> `p = 0.40`
- `h_weak` -> `p = 0.10`

### 4. 三模型 exclusivity

当前 `exhaustive_pairwise_complement` 是两个模型的标准模型选择契约。三模型时 Gaia 还没有 N-ary Exclusive primitive，所以示例显式使用：

```python
exclusivity="pairwise_contradiction"
```

这表示这些模型两两不能同时为真，但允许“三个列出的模型都不完全正确”的状态。这个 open-world 语义比标准二模型 exhaustive comparison 更保守。

### 5. 与结构推理链混合

`bayes.compare(...)` 更新疗效假设；`derive(...)` 把“强效模型成立 + 效应量超过阈值”连接到 Phase III 建议。Bayes 比较和结构推理链使用同一个 BP 图，不需要手动加权。

## 与 Mendel 示例的对比

| 维度 | Mendel 示例 | 本示例 |
|---|---|---|
| 假设数 | 2 | 3 |
| 可观测指标 | 1 个离散计数 | 连续 LDL + 离散达标人数 |
| 分布类型 | `Binomial` / `BetaBinomial` | `Normal` + `Binomial` |
| 测量噪声 | 无 | `observe(..., error=2.2)` |
| 参数形式 | 固定参数或复合替代 | `Normal` 固定参数 + `Binomial` deferred binding |
| 推理链 | 纯模型比较 | 模型比较 + `derive(...)` 临床决策 |
| 互斥模式 | 两模型可用默认 exhaustive | 三模型显式 `pairwise_contradiction` |
