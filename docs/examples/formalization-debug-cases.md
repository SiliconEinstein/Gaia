# Formalization Debug Cases — Belief 不对怎么办

> **Gaia version:** 0.5.x
> **Author:** @kunyuan
> **Date:** 2026-05-17
>
> **本例展示**：当 `gaia run infer` 跑出来的 belief 让你觉得不对劲时，用 4 个最小 toy 包按"先排除代码 bug，再认科学 insight"的顺序定位根因。

## 场景

你写完一个 Gaia 包、跑了 `gaia run infer`，看到某个 hypothesis 的 belief 数字让你觉得"不对"——可能高得离谱、低得离谱、或者就是不符合你的领域直觉。

这种感觉有信号——但**不能直接调参数**。Gaia BP 是 (priors + reasoning structure) → beliefs 的确定性映射。看到 belief 不对，回去检查的是**逻辑结构**，按顺序排查：

1. **推理关系写错了？** — `derive` 方向反了 / 该用 `infer` 用了 `derive`
2. **同一份证据被重复计数？** — 同一份数据通过多条路径进入 BP
3. **一个 claim 里捆了多件事？** — 外部证据无法分别更新
4. **以上都不是？** — 代码对，直觉需要更新

下面 4 节各对应一个可直接运行的 toy 包（`examples/<name>-toy-gaia/`，独立 `gaia build compile + gaia run infer`）。

> 本页是 [How to write a sound Gaia formalization](../for-users/formalization-best-practices.md) §7 的配套示例。verb 选择、先验设置、`bayes` 模块、CLI audit 工具链的完整讨论在主 how-to。

## 代码 + 运行

每个 toy 包仓库布局一致：

```text
examples/<name>-toy-gaia/
├── pyproject.toml
└── src/<name>_toy/
    ├── __init__.py        # claims + reasoning verbs
    └── priors.py          # register_prior calls
```

下面四节展示每个 toy 包的关键代码、错误对照、运行命令、实测 belief。

### Case 1 · 把概率证据写成了硬逻辑

**Toy package**: [`examples/derive-direction-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/derive-direction-toy-gaia)

包内用 `infer` 表达"地湿是下雨的概率证据"（正确写法）：

```python
infer(
    evidence=ground_is_wet,
    hypothesis=it_rained,
    p_e_given_h=0.95,
    p_e_given_not_h=0.20,
    label="wetness_is_evidence_of_rain",
)
observe(ground_is_wet)
```

`priors.py` 给 `it_rained` 设 5% 先验。

错误写法（**不要这么写**）：

```python
# 错误：编码的是"地湿逻辑上蕴含下过雨"
derive(it_rained, given=[ground_is_wet], rationale="...")
```

运行：

```bash
cd examples/derive-direction-toy-gaia
gaia build compile
gaia run infer
```

**预期 belief**（从 `.gaia/beliefs.json`）：

| 写法 | `it_rained` belief |
|---|---|
| 正确（`infer`）| **0.20** |
| 错误（reversed `derive`）| **0.97** |

5× 差距揭示问题：`derive` 是逻辑必然（接近确定性），观察"地湿"把"下雨"belief 强推到 ≈1，绕过了 0.05 的 prior。`infer` 才做真正的 Bayes 反演，似然度比值 9.5/4 应用到 prior 0.05 得到合理后验 0.20。

### Case 2 · 同一份证据被重复计数

**Toy package**: [`examples/double-counting-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/double-counting-toy-gaia)

正确写法（单一 evidence claim + 单一 infer）：

```python
disease_x = claim("Patient has rare disease X.")
lab_assay_positive = claim("The lab assay returned positive.")

infer(
    evidence=lab_assay_positive,
    hypothesis=disease_x,
    p_e_given_h=0.90,
    p_e_given_not_h=0.10,
)
observe(lab_assay_positive)
```

错误写法（**不要这么写**）：

```python
# 错误：同一份 lab assay 拆成两条独立 evidence claim
titer_high     = claim("Antibody titer above threshold.")
panel_positive = claim("Biomarker panel positive.")

infer(evidence=titer_high,    hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
infer(evidence=panel_positive, hypothesis=disease_x,
      p_e_given_h=0.90, p_e_given_not_h=0.10)
observe(titer_high); observe(panel_positive)
```

`register_prior(disease_x, 0.05)` 之后跑 `gaia run infer`：

| 写法 | `disease_x` belief |
|---|---|
| 正确（单一 infer）| **0.32** |
| 错误（两条 infer，double count）| **0.81** |

**怎么发现**：用 `gaia inspect starmap` 把所有指向 `disease_x` 的入边追到根。如果根上的 evidence 在物理/数据来源上是同一件事（同一份 lab、同一篇论文、同一次测量），合并成单一 evidence claim。

### Case 3 · 一个 claim 里捆了多件事

**Toy package**: [`examples/non-atomic-claim-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/non-atomic-claim-toy-gaia)

正确写法（两个独立 claim）：

```python
reduces_ldl           = claim("Drug X reduces LDL cholesterol.")
reduces_heart_attacks = claim("Drug X reduces heart-attack incidence.")

infer(evidence=ldl_endpoint_positive,
      hypothesis=reduces_ldl,
      p_e_given_h=0.95, p_e_given_not_h=0.10)
infer(evidence=heart_attack_endpoint_null,
      hypothesis=reduces_heart_attacks,
      p_e_given_h=0.20, p_e_given_not_h=0.85)
observe(ldl_endpoint_positive); observe(heart_attack_endpoint_null)
```

错误写法（**不要这么写**）：

```python
# 错误：一个 claim 同时声明两件独立的事
ldl_and_heart_attack = claim(
    "Drug X reduces LDL cholesterol AND reduces heart-attack incidence."
)
infer(evidence=ldl_endpoint_positive,
      hypothesis=ldl_and_heart_attack, ...)
infer(evidence=heart_attack_endpoint_null,
      hypothesis=ldl_and_heart_attack, ...)
```

跑 `gaia run infer`：

| 写法 | belief |
|---|---|
| 正确（拆开）| `reduces_ldl` = **0.90**、`reduces_heart_attacks` = **0.19** |
| 错误（捆绑）| `ldl_and_heart_attack` = **0.69**（两个信号 collapse，无法分辨）|

**怎么发现**：当一个 claim 的 belief 卡在 0.4–0.7 中性段，看 content 字符串里有没有 "AND" / "并且" / "同时" / "对...也"。有就该拆。

### Case 4 · 代码没错，直觉需要更新

**Toy package**: [`examples/base-rate-fallacy-toy-gaia/`](https://github.com/SiliconEinstein/Gaia/tree/v0.5/examples/base-rate-fallacy-toy-gaia)

包内代码是清洁的单一 Bayes 反演——**没有 Case 1–3 的任何 bug**：

```python
disease_x = claim("Patient has rare disease X.")
test_positive = claim("Test for X returned positive.")

infer(
    evidence=test_positive,
    hypothesis=disease_x,
    p_e_given_h=0.95,        # sensitivity
    p_e_given_not_h=0.05,    # 1 - specificity
)
observe(test_positive)
```

`priors.py`：

```python
register_prior(
    disease_x,
    value=0.01,
    justification="Population prevalence of disease X is 1%.",
)
```

跑 `gaia run infer`：

| Hypothesis | belief |
|---|---|
| `disease_x` | **0.16** |

**直觉冲突**：测试 95% 准确，阳性后患病概率应该 ≈ 95%？

**Bayes 真相**：`0.95 × 0.01 / (0.95 × 0.01 + 0.05 × 0.99) ≈ 0.16`。1% 的低基率 prior 在 19:1 的似然度比值后只移到 0.16。把 prior 改成 50%（高基率）belief 会跳到 ~0.95，naive 直觉就对了——所以根在 base rate，不在测试敏感度。

**怎么确认是 Case 4 而非 Case 1–3**：

- 试 Case 1 修复（换 verb）— belief 不变（verb 已经选对）。
- 试 Case 2 修复（去重）— belief 不变（没有 double counting）。
- 试 Case 3 修复（拆 claim）— belief 不变（claim 已经原子）。
- **三个都不动 belief** — 保持包不动，更新直觉。

这正是把推理形式化的科学价值——"直觉对/不对"和"Bayes 算的对/不对"分到了两个不同的 audit channel。

## 关键机制

下面三个机制只在本例集合里有独立价值，不重复主 how-to / Foundations。

- **`gaia inspect starmap` 用作反向追踪工具**：当 belief 看起来不对，starmap HTML 输出能可视化"哪些 evidence claim 通过哪些 reasoning 边到达了 hypothesis"。Case 1–3 的根因全都能通过 starmap 一眼看出（反向 derive 边、并列重复 evidence、捆绑 claim）。详见 [CLI Commands](../for-users/cli-commands.md)。

- **Cromwell ε 钳制对 belief 数值的影响**：所有 prior 和 evidence pin 都被钳到 `[0.001, 0.999]`，所以"应该是 0 或 1"的 belief 实际上是 ε 或 1 − ε。Case 4 手算 `0.95 × 0.01 / 分母 = 0.161`，Gaia 实测 0.158——差异来自 Cromwell ε。详见 [Belief Propagation § Inference](../foundations/bp/inference.md)。

- **`infer` vs `derive` 在 BP 里的数值差**：`derive(C, given=[P])` lower 成接近确定性的约束，`infer(evidence=E, hypothesis=H, p_e_given_h, p_e_given_not_h)` lower 成参数化软约束。Case 1 的 0.97 vs 0.20 正是这两类约束的实际数值差。详见 [Belief Propagation § Formal Strategy Lowering](../foundations/bp/formal-strategy-lowering.md) 与 [Theory § Propositional Operators §4](../foundations/theory/03-propositional-operators.md)。