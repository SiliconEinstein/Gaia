# Bayes 模块 — 生物医学示例：LDL 降低药物 Phase II 试验

示例展示 `gaia.engine.lang.bayes` 在一个复杂场景中的完整用法：
**三个竞争假设 × 两个不同类型可观测指标（连续 + 离散）× 测量噪声 × 与 derive/support 推理链混合编排**。

## 场景

新型 PCSK9 抑制剂在 30 名他汀不耐受的高胆固醇患者中进行 Phase II 剂量探索试验，
治疗 30 周后评估两个可观测指标：

| 指标 | 类型 | 变量 | 含义 |
|------|------|------|------|
| LDL 降低百分比 | 连续（Normal） | `ldl_pct` | 个体 LDL-C 相对于基线的降低幅度 |
| ≥50% 达标率 | 离散（Binomial） | `responders` | 达到 ≥50% LDL 降低的患者比例 |

## 三个竞争假设

| 假设 | LDL 均值降低 | 标准差 | ≥50% 达标率 | 先验 |
|------|-------------|--------|------------|------|
| `h_strong` | 45% | 12% | 70% | 0.4 |
| `h_moderate` | 28% | 10% | 40% | 0.4 |
| `h_weak` | 12% | 8% | 10% | 0.2 |

先验反映了前期 PK/PD 建模和同类药物（evolocumab/alirocumab）的 Phase II 数据。

## 观测数据

- 30 名患者平均 LDL 降低 = **38%**（SEM = 2.2%，即 12%/√30）
- **17/30** 患者达到 ≥50% LDL 降低

## 完整代码

```python
"""LDL 降低药物 Phase II 试验 — 三假设贝叶斯比较。

两个可观测指标（连续 LDL + 离散达标率），带测量噪声，
bayes.likelihood 与 derive/support 推理链在同一 BP 图上联合推理。
"""

from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.lang import (
    Constant,
    Nat,
    Real,
    Variable,
    bayes,
    claim,
    derive,
    equals,
    note,
    observe,
    parameter,
    register_prior,
    support,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="ldl_trial_pkg", namespace="biomed")
token = _current_package.set(pkg)

try:
    # ═════════════════════════════════════════════════════════
    # 1. 可观测变量
    # ═════════════════════════════════════════════════════════
    ldl_pct = Variable(symbol="ldl_pct", domain=Real)
    responders = Variable(symbol="responders", domain=Nat)

    # ═════════════════════════════════════════════════════════
    # 2. 背景知识
    # ═════════════════════════════════════════════════════════
    context = note(
        "PCSK9 抑制剂通过阻止 LDL 受体降解来降低血浆 LDL-C。"
        "Phase II 试验纳入 30 名他汀不耐受的高胆固醇患者，"
        "治疗 30 周后评估 LDL 降低百分比和达标率。"
    )

    # ═════════════════════════════════════════════════════════
    # 3. 三个竞争假设
    # ═════════════════════════════════════════════════════════
    #
    # parameter() 将 Variable(responders) 绑定到具体值。
    # 编译时 bayes.model 的 Binomial(n=30, p=responders) 从各假设的
    # formula 中解析 p：h_strong→0.70, h_moderate→0.40, h_weak→0.10。

    h_strong = parameter(
        responders, 0.70,
        content="强效模型：LDL 降低 45±12%，30 周达标率 70%",
        prior=0.4,
        label="h_strong",
    )
    register_prior(h_strong, 0.4,
        justification="基于同类 PCSK9 抑制剂 Phase II 数据的先验期望。")

    h_moderate = parameter(
        responders, 0.40,
        content="中等模型：LDL 降低 28±10%，30 周达标率 40%",
        prior=0.4,
        label="h_moderate",
    )
    register_prior(h_moderate, 0.4,
        justification="部分他汀不耐受患者反应较弱的可能性相当。")

    h_weak = parameter(
        responders, 0.10,
        content="弱效模型：LDL 降低 12±8%，30 周达标率 10%",
        prior=0.2,
        label="h_weak",
    )
    register_prior(h_weak, 0.2,
        justification="完全无效的概率较低但不能排除。")

    # ═════════════════════════════════════════════════════════
    # 4. LDL 降低（连续指标）的预测模型
    # ═════════════════════════════════════════════════════════
    #
    # 每个假设预测不同的 Normal(mu, sigma)。
    # 参数是具体数值——不同假设的预测分布形状不同，
    # 不只是参数值差异（不像 Mendel 示例中共用 Binomial 对象）。

    model_strong_ldl = bayes.model(
        h_strong,
        observable=ldl_pct,
        distribution=bayes.Normal(mu=45.0, sigma=12.0),
        label="model_strong_ldl",
        rationale="强效假设：平均 LDL 降低 45%，个体间变异 12 个百分点",
    )

    model_moderate_ldl = bayes.model(
        h_moderate,
        observable=ldl_pct,
        distribution=bayes.Normal(mu=28.0, sigma=10.0),
        label="model_moderate_ldl",
        rationale="中等假设：平均 LDL 降低 28%，个体间变异 10 个百分点",
    )

    model_weak_ldl = bayes.model(
        h_weak,
        observable=ldl_pct,
        distribution=bayes.Normal(mu=12.0, sigma=8.0),
        label="model_weak_ldl",
        rationale="弱效假设：平均 LDL 降低 12%，个体间变异 8 个百分点",
    )

    # ═════════════════════════════════════════════════════════
    # 5. 达标率（离散指标）的预测模型
    # ═════════════════════════════════════════════════════════
    #
    # 与 Mendel 示例相同模式：Binomial(n, p) 中 p 是 Variable，
    # 三个假设共享同一个 distribution 对象，编译时通过参数绑定区分。

    model_strong_resp = bayes.model(
        h_strong,
        observable=responders,
        distribution=bayes.Binomial(n=30, p=responders),
        label="model_strong_resp",
        rationale="强效假设：70% 达标率 → Binomial(30, 0.70)",
    )

    model_moderate_resp = bayes.model(
        h_moderate,
        observable=responders,
        distribution=bayes.Binomial(n=30, p=responders),
        label="model_moderate_resp",
        rationale="中等假设：40% 达标率 → Binomial(30, 0.40)",
    )

    model_weak_resp = bayes.model(
        h_weak,
        observable=responders,
        distribution=bayes.Binomial(n=30, p=responders),
        label="model_weak_resp",
        rationale="弱效假设：10% 达标率 → Binomial(30, 0.10)",
    )

    # ═════════════════════════════════════════════════════════
    # 6. 观测数据
    # ═════════════════════════════════════════════════════════

    # ── 6a. LDL 连续观测（带测量噪声） ──
    #
    # 样本均值 = 38%，SEM = 2.2%。
    # noise 元数据告诉编译器：在计算似然时，将预测分布与
    # Normal(0, 2.2) 卷积。

    data_ldl = claim(
        "Observed mean LDL reduction = 38% (SEM = 2.2%)",
        formula=equals(ldl_pct, Constant(38.0, Real)),
        metadata={
            "bayes": {
                "noise": {
                    "kind": "normal",
                    "params": {"mu": 0.0, "sigma": 2.2},
                }
            }
        },
    )
    observe(data_ldl, rationale="30 名患者平均 LDL 降低 38%，SEM = 2.2%",
            label="observe_ldl")
    data_ldl.label = "data_ldl"

    # ── 6b. 达标率离散观测 ──

    data_resp = claim(
        "Observed 17/30 patients achieved ≥50% LDL reduction",
        formula=equals(responders, Constant(17, Nat)),
    )
    observe(data_resp, rationale="17/30 患者 LDL 降低 ≥50%",
            label="observe_resp")
    data_resp.label = "data_resp"

    # ═════════════════════════════════════════════════════════
    # 7. 似然比较
    # ═════════════════════════════════════════════════════════

    # ── 7a. LDL 连续数据的似然比较 ──
    #
    # 编译器对每个假设计算卷积似然：
    #   P(38 | h_strong)   = log Normal(38 | 45, √(12²+2.2²)=12.2) ≈ -3.47
    #   P(38 | h_moderate) = log Normal(38 | 28, √(10²+2.2²)=10.2) ≈ -3.65
    #   P(38 | h_weak)     = log Normal(38 | 12, √(8²+2.2²)=8.3)   ≈ -8.06

    ldl_comparison = bayes.likelihood(
        data_ldl,
        model=model_strong_ldl,
        against=[model_moderate_ldl, model_weak_ldl],
        exclusivity="exhaustive_pairwise_complement",
        label="ldl_comparison",
    )

    # ── 7b. 达标率离散数据的似然比较 ──
    #
    #   P(17/30 | h_strong)   = log Binomial(17 | 30, 0.70) ≈ -2.15
    #   P(17/30 | h_moderate) = log Binomial(17 | 30, 0.40) ≈ -3.58
    #   P(17/30 | h_weak)     = log Binomial(17 | 30, 0.10) ≈ -14.60
    #
    # 离散数据对 h_weak 的排除力远强于连续数据——
    # 17/30 = 57% 远离 10%，且 Binomial 方差小。

    resp_comparison = bayes.likelihood(
        data_resp,
        model=model_strong_resp,
        against=[model_moderate_resp, model_weak_resp],
        exclusivity="exhaustive_pairwise_complement",
        label="resp_comparison",
    )

    # ═════════════════════════════════════════════════════════
    # 8. 推理链：假设比较 → 临床决策
    # ═════════════════════════════════════════════════════════
    #
    # bayes.likelihood 处理了"数据支持哪个假设"。
    # 下面用 derive + support + register_prior 把胜出假设
    # 连接到临床行动建议。两套机制在同一 BP 图上联合推理。

    recommend_phase3 = claim(
        "该 PCSK9 抑制剂应推进到 Phase III 关键试验。",
        prior=0.5,
        label="recommend_phase3",
    )

    strong_to_phase3 = derive(
        "若强效模型成立（LDL 降低 ≥40%，达标率 ≥60%），"
        "效应量足够支持推进 Phase III。",
        given=h_strong,
        background=[context],
        rationale="FDA 指南要求 Phase II 平均 LDL 降低 ≥30%。"
        "强效模型估计 45%，远超阈值。",
        label="strong_to_phase3",
    )
    register_prior(strong_to_phase3, 0.90,
        justification="p2=0.90: 指南明确，效应量远超阈值。")

    phase3_support = support(
        [strong_to_phase3, ldl_comparison, resp_comparison],
        recommend_phase3,
        background=[context],
        rationale="数据支持强效模型 + 效应量超 FDA 阈值 → 推进 Phase III。",
        label="phase3_support",
    )

finally:
    _current_package.reset(token)

# ═════════════════════════════════════════════════════════
# 9. 编译与推理
# ═════════════════════════════════════════════════════════

compiled = compile_package_artifact(pkg)
beliefs, _ = exact_inference(lower_local_graph(compiled.graph))

h_strong_id = compiled.knowledge_ids_by_object[id(h_strong)]
h_moderate_id = compiled.knowledge_ids_by_object[id(h_moderate)]
h_weak_id = compiled.knowledge_ids_by_object[id(h_weak)]
recommend_id = compiled.knowledge_ids_by_object[id(recommend_phase3)]

print(f"h_strong     posterior: {beliefs[h_strong_id]:.4f}")
print(f"h_moderate   posterior: {beliefs[h_moderate_id]:.4f}")
print(f"h_weak       posterior: {beliefs[h_weak_id]:.4f}")
print(f"Recommend Phase III : {beliefs[recommend_id]:.4f}")

# 预期结果：
#   h_strong     posterior: ~0.90   ← LDL + 达标率双重支持
#   h_moderate   posterior: ~0.10   ← 仍有少量支持
#   h_weak       posterior: <0.01   ← 几乎被排除
```

## 与 Mendel 示例的对比

| 维度 | Mendel 示例 | 本示例 |
|------|-----------|--------|
| 假设数 | 2（Mendel vs blending） | **3**（strong vs moderate vs weak） |
| 可观测指标 | 1（显性计数，离散） | **2**（LDL 连续 + 达标率离散） |
| 分布类型 | Binomial + BetaBinomial | **Normal + Binomial** |
| 测量噪声 | 无 | **Normal(0, 2.2) 加性噪声** |
| 参数形式 | 共享 Binomial 对象，Variable 绑定 | LDL 各假设独立 Normal；达标率共享 Binomial |
| 推理链 | 纯似然比较 | **似然比较 + derive/support → 临床决策** |
| 互斥模式 | `"none"`（假设独立比较） | `"exhaustive_pairwise_complement"`（恰好一个为真） |

## 关键机制

### 1. 多假设 × 多可观测指标的联合更新

两个 `bayes.likelihood`（一个连续、一个离散）独立计算各假设的对数似然，
降落到 IR 的 `infer` 策略。BP factor graph 上的 belief propagation 自动联合两者——
**不需要手动加权**。离散数据（达标率）对 h_weak 的排除力远强于连续数据，
因为 Binomial 方差小且 17/30 = 57% 距 10% 很远。

### 2. 测量噪声卷积

编译器在 `_log_likelihood_with_noise()` 中将预测分布与 Normal 噪声卷积：

```
P(obs | H) = ∫ Normal(obs | θ, σ_noise) × f_pred(θ | H) dθ
```

对 Normal 预测分布，简化为 σ_conv = √(σ_pred² + σ_noise²)。

### 3. Variable 延迟绑定

`Binomial(n=30, p=responders)` 中 `p` 是 Variable。三个假设共享同一个 distribution 对象。
`_bind_distribution()` 从各假设的 formula（`parameter(responders, value)`）中解析绑定：
h_strong→p=0.70, h_moderate→p=0.40, h_weak→p=0.10。

这与 Mendel 示例的模式相同，但扩展到三个假设。

### 4. 两种贝叶斯机制的混合编排

| 机制 | 作用 | 本例使用位置 |
|------|------|-------------|
| `bayes.model` + `bayes.likelihood` | 计算 P(data \| hypothesis) | LDL 连续数据 + 达标率离散数据 |
| `derive` + `support` + `register_prior` | 定性推理链：假设 → 行动 | h_strong → Phase III 推荐 |

两种机制在同一个 BP factor graph 上联合推理：似然因子更新假设的后验概率，
推理链将假设的后验传播到决策节点。

### 5. Cromwell 钳制

似然比 `exp(logL_i - logL_max)` 被 `_clamp()` 限制在 `[ε, 1-ε]`。
h_weak 的 logL 极低（−14.60），但后验不会恰好为零——保留"新证据可能反转结论"的贝叶斯原则。

### 6. 三假设互斥

`exclusivity="exhaustive_pairwise_complement"` + 三个假设 →
编译器自动生成三对 `Contradict` 算子 + 一个 clamped disjunction helper，
确保恰好一个假设为真，后验概率总和归一化。