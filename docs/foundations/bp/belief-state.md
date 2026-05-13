# BeliefState — 信念定义

> **Status:** Current canonical (v0.5)
>
> 本文档定义 BeliefState schema，用于 LKM 全局推理。本地 CLI 推理产生的 `.gaia/beliefs.json` 使用不同的 schema（见 §Local CLI Beliefs Format）。

BeliefState 是 BP 在 GlobalCanonicalGraph 上的纯输出——后验信念值。它记录产生它的条件（resolution policy），使结果可重现。

Gaia IR 结构定义见 [Gaia IR Structure](../gaia-ir/02-gaia-ir.md)，参数模型见 [Parameterization](../gaia-ir/06-parameterization.md)。

## Schema

```
BeliefState:
    bp_run_id:            str              # 唯一运行 ID
    created_at:           str              # ISO 8601

    # ── 重现条件 ──
    resolution_policy:    str              # "latest" | "source:<source_id>"
    prior_cutoff:         str              # ISO 8601，只用此时间点之前的记录

    # ── 信念 ──
    beliefs:              dict[str, float] # 以 gcn_ ID 为键
                                           # 只有 type=claim 的 Knowledge 有 belief

    # ── 编译信息（可选诊断） ──
    compilation_summary:  dict | None      # Strategy → 编译路径（"direct" / "composite" / "formal_expr"）

    # ── 诊断 ──
    converged:            bool
    iterations:           int
    max_residual:         float
```

## Local CLI Beliefs Format

本地 CLI `gaia infer` 写入的 `.gaia/beliefs.json` 使用不同的 schema，针对本地包优化：

```json
{
  "ir_hash": "...",
  "gaia_lang_version": "...",
  "beliefs": [
    {"knowledge_id": "github:pkg::label", "label": "label", "belief": 0.73}
  ],
  "diagnostics": {
    "converged": true,
    "iterations": 42,
    "max_residual": 0.0001
  }
}
```

**与 BeliefState 的区别**：
- `beliefs` 是 list of records，不是 `dict[str, float]`
- 使用本地 QID（`github:pkg::label`），不是全局 `gcn_*` ID
- 缺少 `bp_run_id`, `created_at`, `resolution_policy`, `prior_cutoff`, `compilation_summary`
- 包含 `ir_hash` 和 `gaia_lang_version` 用于本地一致性检查

**转换到 BeliefState**：上传到 LKM 时需要：
1. 将本地 QID 映射到全局 `gcn_*` ID
2. 将 `beliefs` list 转换为 `dict[gcn_id, float]`
3. 添加 `bp_run_id`, `created_at`, `resolution_policy`, `prior_cutoff`
4. 可选：添加 `compilation_summary` 用于诊断

## 关键规则

- **beliefs 只对 Claim**：只有 `type=claim` 的 Knowledge 有 belief。Setting 和 Question 没有 belief。
- **可重现**：`resolution_policy` + `prior_cutoff` 完整定义了参数组装条件。`prior_cutoff` 记录 BP 运行时的时间点，确保用 `latest` policy 重跑时只取该时间之前的记录，结果可重现。
- **可多次运行**：同一 resolution policy + prior_cutoff 可以有多次 BP 运行（不同调度策略、阻尼系数等），每次产出不同的 BeliefState。
- **belief 是后验**：belief 是 BP 计算后的后验信念值，不是 prior。
- **组装完整性**：组装时每个参数化 Strategy 都必须有 conditional_probabilities 值；直接 FormalStrategy 则必须带有对应的 FormalExpr，且其相关显式 claim 必须有可用 prior。否则 BP 拒绝运行。
- **compilation_summary**：记录每个 Strategy 的编译路径——direct（折叠为 ↝ 因子）、composite（递归展开子策略）或 formal_expr（通过 FormalExpr 在 Operator 层运行），用于诊断和可重现性。

## 诊断字段

- `converged`：BP 是否在容差内收敛
- `iterations`：实际运行的迭代数
- `max_residual`：停止时的最大消息变化量
- `compilation_summary`：每个 Strategy 的 BP 编译路径（direct / composite / formal_expr），便于诊断推理链路

这些字段用于判断 belief 的可靠性。未收敛的 BeliefState 仍然有效，但应标记为近似值。

## 源代码

- `gaia/bp/engine.py` — `InferenceEngine.run()` 产出 beliefs
- `gaia/bp/bp.py` — `BeliefPropagation.run()`（loopy BP 路径）
- `gaia/bp/lowering.py` — `lower_local_graph()`：Gaia IR → FactorGraph
- `gaia/ir/strategy.py` — `Strategy / CompositeStrategy / FormalStrategy`
