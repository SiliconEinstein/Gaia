# How to write a sound Gaia formalization

> **Gaia version:** 0.5.x
> **Author:** @SiliconEinstein
> **Date:** 2026-05-17

当你把一个领域问题（临床试验、因果推断、模型比较等）编码为 Gaia knowledge package 时，本页帮你在提交前确保形式化结构是健全的。

## 前提

- 已完成 [Quick Start](quick-start.md)，能写出可编译的 package
- 了解 `claim`、`derive`、`observe`、`register_prior` 的基本用法
- 了解 `bayes` 模块的基本用法（→ [Bayes Semantics](../foundations/gaia-lang/bayes.md)）

## 步骤 1：为每条证据选择 observe() 或 claim()

Gaia v0.5 中 `observe()` 和 `claim()` 有明确分工：

| 证据类型 | 用什么 | 原因 |
|---------|--------|------|
| 字面测量值（温度计读数、试验组事件数） | `observe()` | 直接观测，钉到 Cromwell 上界 ≈ 0.999 |
| formula binding（`log_rr = -0.151`） | `observe()` | 数学恒等式，不是可错判断 |
| 带不确定性的证据总结（荟萃分析结论、流行病学关联） | `claim()` + `register_prior()` | 可错的解释性总结，需要先验表达不确定性 |

决策树：

```text
这条 claim 是直接测量/观测到的原始数据吗？
  ├── 是 → observe()
  │    例: "试验组事件数 142/7234"
  │    例: claim("log(RR) ≈ -0.151", formula=equals(log_rr, Constant(-0.151, Real)))
  │
  └── 否 → claim() + register_prior()
       例: "阿司匹林降低 ASCVD 14%（RR 0.86, CI 0.79–0.92）"
            这是荟萃分析的解释性总结，有异质性和偏倚风险
```

**关键点**：formula binding 被 `observe()` 是因为 binding 本身是 tautology（让 Bayes 引擎知道变量值已被观测），不是因为它"更可靠"。

> 详见 [Formalization Methodology](../foundations/theory/05-formalization-methodology.md) 中对 `observe()` Cromwell 语义的说明。

## 步骤 2：从 chainAnalysis 直接赋先验

每条证据的先验应直接来自 chainAnalysis 的独立评估，而非按证据类型分桶。

```python
register_prior(
    ascvd_reduction,
    0.65,
    justification="chainAnalysis prior=0.65: RCT meta-analysis, "
    "weak=[model, generalization, statistical]",
)
```

如果你有理由调整 chainAnalysis 的值，显式写出调整幅度和原因：

```python
register_prior(
    ascvd_reduction,
    0.75,
    justification="chainAnalysis 0.65 → 0.75: "
    "2025 更新荟萃分析在低偏倚子集确认了效应量，"
    "下调 generalization concern",
)
```

**每条证据的 justification 应该能回答：这个数字从哪来的？** 如果回答不了，先验还不够具体。

## 步骤 3：确保 bayes 模型参数独立于观测值

当你用 `bayes.model()` 设定竞争假设下的预期分布时，分布参数应编码 **"在这个假设下，事先预期什么"**，而非照搬你要检验的观测值。

参数来源的选择：

| 参数来源 | 适用性 |
|---------|--------|
| 领域知识（如：抗血小板药物预期产生 10–15% 事件降低） | 适合 |
| 独立数据集（如：二级预防效应量作为一级预防的参考） | 适合 |
| 同一荟萃分析的点估计和标准误 | 不适合 — 用观测拟合模型再检验同一观测，是循环论证 |

示例 — 为两个竞争假设设定预期分布：

```python
effective_ascvd_log_mean = -0.10   # 领域预期：约 10% 降低
effective_ascvd_log_sd = 0.08      # 表达疗效异质性

no_benefit_ascvd_log_mean = 0.0    # 无效假设预期无效应
no_benefit_ascvd_log_sd = 0.10     # 允许随机变异
```

## 步骤 4：对称覆盖所有竞争维度

对假设 A 做的每类定量分析，都应对称地施加到假设 B 上。

自检方法：列出你为每个假设做了哪些维度的似然比较，确认没有遗漏：

```text
                  假设 A（有效）    假设 B（无净获益）
ASCVD 维度         ✓ likelihood      ✓ likelihood
出血维度           ✓ likelihood      ✓ likelihood
                   ↑ 两个维度在 BP 图中自然平衡
```

如果某个维度只对一个假设建模了，结论会系统性偏向有建模的一方。

## 步骤 5：提交前审计图结构

### 5.1 拓扑对称性

对每个竞争假设统计：

- supporting 边数
- contradicting 边数
- equal 连接的先验分布

两边大致对称，或者不对称有明确的领域理由。

### 5.2 证据覆盖

- 所有 `observe()` / `claim()` 节点都连接到至少一个假设
- 没有只声明了先验但未参与推理的孤儿节点（如果确有原因不连接，写注释说明）

### 5.3 先验可追溯性

- 每个 `register_prior()` 的 `justification` 可追溯到 chainAnalysis 值或显式调整
- `p1` / `p2` 信息没有被压平成单一先验（如果 `p1=0.90, p2=0.10`，至少在 justification 中说明）

### 5.4 模型参数独立性

- `bayes.model()` 的 μ / σ 不等于你要检验的观测点估计 / 标准误

## 结果

通过以上步骤后，你的 package 应满足：

1. `gaia build compile` 通过
2. `gaia run infer` 产出的 belief 分布反映了证据的真实权重，没有因结构偏差被放大或压缩
3. 每个先验和模型参数都有可追溯来源

## 快速参考卡片

```text
┌────────────────────────────────────────────────────────────┐
│  Gaia 形式化提交前检查                                       │
├────────────────────────────────────────────────────────────┤
│  □ observe() 只用于字面测量 / formula binding                │
│  □ 证据总结用 claim() + register_prior()                    │
│  □ 先验直接来自 chainAnalysis，调整有显式 justification       │
│  □ bayes 模型参数独立于观测值                                │
│  □ 每个定量比较都有对称的 counterpart                        │
│  □ 竞争假设的边数 / 先验大致对称（不对称有领域理由）           │
│  □ 没有孤儿节点                                             │
│  □ 所有 prior 有可追溯来源                                   │
│  □ p1/p2 信息保留在 justification 中                         │
└────────────────────────────────────────────────────────────┘
```
