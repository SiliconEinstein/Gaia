# BeliefState — 信念定义

> **Status:** Target design

BeliefState 是 BP 在 GlobalCanonicalGraph 上的纯输出——后验信念值。它记录产生它的条件（resolution policy），使结果可重现。

Graph IR 结构定义见 [graph-ir.md](graph-ir.md)。概率参数见 [parameterization.md](parameterization.md)。三者的关系见 [overview.md](overview.md)。

## Schema

```
BeliefState:
    bp_run_id:            str              # 唯一运行 ID
    timestamp:            str              # ISO 8601

    # ── 重现条件 ──
    resolution_policy:    str              # "latest" | "source:<source_id>"
    prior_cutoff:         str              # ISO 8601，只用此时间点之前的记录

    # ── 信念 ──
    beliefs:              dict[str, float] # 以 gcn_ ID 为键
                                           # 只有 type=claim 的节点有 belief

    # ── 诊断 ──
    converged:            bool
    iterations:           int
    max_residual:         float
```

## 关键规则

- **beliefs 只对 Claim**：只有 `type=claim` 的节点有 belief。Setting、Question、Template 没有 belief。
- **可重现**：`resolution_policy` + `prior_cutoff` 完整定义了参数组装条件。`prior_cutoff` 记录 BP 运行时的时间点，确保用 `latest` policy 重跑时只取该时间之前的记录，结果可重现。
- **可多次运行**：同一 resolution policy + prior_cutoff 可以有多次 BP 运行（不同调度策略、阻尼系数等），每次产出不同的 BeliefState。
- **belief 是后验**：belief 是 BP 计算后的后验信念值，不是 prior。

## 诊断字段

- `converged`：BP 是否在容差内收敛
- `iterations`：实际运行的迭代数
- `max_residual`：停止时的最大消息变化量

这些字段用于判断 belief 的可靠性。未收敛的 BeliefState 仍然有效，但应标记为近似值。

## 源代码

- `libs/inference/bp.py` -- `BeliefPropagation.run()` 产出 beliefs
- `libs/storage/models.py` -- `BeliefSnapshot`
