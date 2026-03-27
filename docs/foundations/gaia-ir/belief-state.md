# BeliefState — 信念定义

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。详见 [documentation-policy.md](../../documentation-policy.md#12-变更控制)。

BeliefState 是某个 runtime projection 上的推理输出——后验信念值。它的 belief 以 canonical claim（`gcn_`）为键记录，因此不同 local package 中汇聚到同一 `gcn_` 的证据会在同一条 belief 轴上体现。

Gaia IR 结构定义见 [gaia-ir-v2-draft.md](gaia-ir-v2-draft.md)。概率参数见 [parameterization.md](parameterization.md)。整体关系见 [overview.md](overview.md)。

## Schema

```
BeliefState:
    bp_run_id:            str              # 唯一运行 ID
    created_at:           str              # ISO 8601

    # ── 重现条件 ──
    resolution_policy:    str              # "latest" | "source:<source_id>"
    projection_policy:    dict             # 本次运行选用了哪些 local package / curation package
    prior_cutoff:         str | None       # ISO 8601；若使用 latest，可截断参数记录以保证可重现

    # ── 信念 ──
    beliefs:              dict[str, float] # 以 gcn_ ID 为键
                                           # 只有 type=claim 的 canonical Knowledge 有 belief

    # ── 编译信息（可选诊断） ──
    compilation_summary:  dict | None      # local Strategy / Operator 的运行时编译路径摘要

    # ── 诊断 ──
    converged:            bool
    iterations:           int
    max_residual:         float
```

## 关键规则

- **beliefs 只对 canonical claim**：只有 `type=claim` 的 `gcn_` 有 belief。`setting` 与 `question` 没有 belief。
- **可重现**：`projection_policy + resolution_policy + prior_cutoff` 共同定义了本次运行使用了哪些 local 图、哪些参数记录。
- **可多次运行**：同一组 `gcn_` 可以在不同 projection / policy 下多次运行，每次产出不同的 BeliefState。
- **belief 是后验**：belief 是 runtime 计算后的后验值，不是 prior。
- **组装完整性**：当前 runtime projection 中，每个参与推理的 canonical claim 都必须有 prior；每个以折叠模式运行的 local Strategy 都必须有可用的 `StrategyParamRecord`。否则 runtime 拒绝运行。
- **compilation_summary**：用于记录某条 local Strategy 在本次运行中是折叠、递归展开还是通过 `formal_expr` 编译，便于诊断与复现。

## projection_policy 的角色

当前 Gaia IR 不持久化 global Strategy / global Operator。因而 BeliefState 若要可重现，必须记录本次运行到底选择了哪些 local graph。

典型 `projection_policy` 可能包含：

- package/version 白名单
- 是否包含 server curation package
- `expand_set`
- 其他与 runtime projection 相关的实现策略

BeliefState 不需要规定这些策略的唯一格式，但需要保证：**同一份 policy 能重新构造出同一份 runtime projection。**

## 诊断字段

- `converged`：推理是否在容差内收敛
- `iterations`：实际运行的迭代数
- `max_residual`：停止时的最大消息变化量
- `compilation_summary`：本次运行中 local Strategy / Operator 的编译摘要

这些字段用于判断 belief 的可靠性。未收敛的 BeliefState 仍可保存，但应视为近似结果。

## 源代码

- `libs/inference/bp.py` -- 运行推理并产出 beliefs
- `libs/inference/factor_graph.py` -- runtime projection / 编译
- `libs/storage/models.py` -- `BeliefSnapshot`
