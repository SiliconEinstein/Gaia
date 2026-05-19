# Gaia Upgrade Specs Index

本文档集把前面讨论过的 Gaia 升级路线拆成可执行的 Markdown spec。每个版本都按相同结构组织：目标、范围、数据契约、API/CLI 变更、实现任务、测试、验收标准和非目标。

Status: idea-stage draft, imported under `docs/ideas/gaia-upgrade-specs/`.

## 版本列表

| 文件 | 版本 | 主题 | 目标摘要 |
|---|---:|---|---|
| `01-v0.5.x-contract-freeze.md` | v0.5.x | Contract Freeze | 以 v0.5 代码事实为准，冻结当前语义、版本矩阵和 golden snapshots。 |
| `02-v0.6-evidence-contract.md` | v0.6 | Evidence Contract | 把 `InferAction` 收敛成正式 likelihood evidence contract，并引入 contexted belief output。 |
| `03-v0.7-evidence-model-adapters.md` | v0.7 | Evidence Model Adapters | 加入常见科学证据模型 adapter：binomial、two-binomial、Gaussian measurement、Bayes factor。 |
| `04-v0.8-context-reproducibility.md` | v0.8 | Context Reproducibility | 把 `InformationContext` / `BeliefState` 做成可重放、可 diff、可锁定的 reproducibility contract。 |
| `05-v0.9-quantity-unit-measurement.md` | v0.9 | Quantity / Unit / Measurement | 给 Gaia 加入最小科学量、单位、误差和测量模型语义。 |
| `06-v0.10-explain-sensitivity-audit.md` | v0.10 | Explain / Sensitivity / Audit | 从“算 posterior”升级为“解释 posterior、诊断脆弱性、审计证据”。 |
| `07-v0.11-cross-package-reasoning.md` | v0.11 | Cross-package Reasoning | 稳定跨 package 推理、dependency contexts、foreign claim mapping 和重复证据控制。 |
| `08-v1.0-stable-kernel.md` | v1.0 | Stable Kernel | 发布稳定的 claim-centered、action-backed、review-gated Jaynesian propositional reasoning kernel。 |
| `09-python-ecosystem-integration-spec.md` | v0.6-v1.0 | Python Ecosystem Integration | 规定成熟 Python 包只能通过 adapter 提供计算、验证、图算法、概率后端、单位和数据互操作，不能定义 Gaia 语义。 |

## 总体设计不变量

以下不变量跨版本保持稳定：

```text
Claim 是唯一 belief variable。
Action 是作者声明的推理动作，不是概率变量。
InferAction / EvidenceFactor 表示 likelihood，不表示 posterior。
Observe 表示 evidence 是否进入当前信息状态 I。
ReviewManifest 决定哪些 action/factor 激活，而不是给 action 提供概率。
BeliefState 记录 P(Claim | Context) 和推理 provenance。
BP / JT / GBP / exact 只是计算后端，不定义 Gaia 的最高语义。
```

## 当前目录结构

当前先作为 idea-stage drafts 放入：

```text
docs/ideas/gaia-upgrade-specs/
  00-index.md
  01-v0.5.x-contract-freeze.md
  02-v0.6-evidence-contract.md
  03-v0.7-evidence-model-adapters.md
  04-v0.8-context-reproducibility.md
  05-v0.9-quantity-unit-measurement.md
  06-v0.10-explain-sensitivity-audit.md
  07-v0.11-cross-package-reasoning.md
  08-v1.0-stable-kernel.md
  09-python-ecosystem-integration-spec.md
```

Promotion target, once accepted and aligned with implementation, may be
`docs/specs/` or the relevant `docs/foundations/` subtrees.

## 建议执行顺序

```text
P0. v0.5.x: contract freeze + golden snapshots
P1. v0.6: evidence contract + minimal contexted BeliefState
P2. v0.7: evidence adapters
P3. v0.8: reproducible context replay / diff / lock
P4. v0.9: quantity / unit / measurement
P5. v0.10: explain / sensitivity / audit
P6. v0.11: cross-package reasoning
P7. v1.0: stable kernel release
```
