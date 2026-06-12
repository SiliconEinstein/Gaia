# Research Actions Migration Notes

> **状态：** package-native research actions 设计的 canonical migration companion。
>
> **日期：** 2026-06-01
>
> **Canonical overview：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)
>
> **Roadmap：**
> [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md)

## 1. 文档状态图

当前实现锚点是 package-native `gaia research` 设计。旧 exploration 文档仍然有参考价值，
但不是 implementation contract。

| 文档或分支 | 状态 | 可以用于 | 不要作为 |
| --- | --- | --- | --- |
| `2026-06-01-research-actions-package-native-overview.md` | canonical | 架构锚点 | 迁移细节日志 |
| `2026-06-01-research-actions-knowledge-model.md` | canonical | focus / obligation / assessment relation 分层 | 迁移计划 |
| `2026-06-01-research-actions-implementation-roadmap.md` | canonical | 实现切片和验证 | 架构长篇论证 |
| `2026-05-25-gaia-lkm-explore-assess-design.md` | experimental / historical | 早期 Explore / Assess 拆分思路 | 当前 contract |
| `2026-05-26-lkm-explore-artifact-mvp-design.md` | experimental / historical | artifact MVP 经验 | 当前 artifact schema |
| `2026-05-27-lkm-explore-iterative-landscape-design.md` | experimental / historical | iterative landscape 经验 | 当前实现计划 |
| PR #726 / `codex/research-loop-agent-protocol` | experimental branch baseline | task envelope 和 validation 经验 | canonical workflow API |

## 2. `gaia-lkm-explore` CLI / Engine

`gaia-lkm-explore` 是 Gaia repo 内已有的 experimental LKM exploration CLI / engine。
它验证了很多有价值的 workflow 机制：

- landscape scan 和多轮扩图；
- query、round、frontier、artifact trace；
- paper leads 和 pull candidates；
- MapHealth / orphan / fragmentation signals；
- checkpoint 时的 `depends_on -> derive` promotion；
- frontier render 和 status surface。

它的长期定位应该是 reference 和 migration source，而不是 `gaia research` 旁边的第二个
canonical product surface。

现有 deterministic 能力的去向：

| 现有能力 | 未来去向 |
| --- | --- |
| paper-level landscape staging / dedup | port 到 `gaia research explore --mode scan`；保持 breadth-first 和默认 pull budget 0 |
| query、round、artifact trace | port 到 `.gaia/research/events.jsonl` 和 artifact provenance |
| frontier ranking / scorer | port 到 targeted expand 或 pull-candidate ranking；不能作为 early scan 完成标准 |
| MapHealth / orphan / fragmentation | port 到 `gaia research status` 或 future `gaia research check`；生成 candidate obligations |
| round bookkeeping | 转成 event / artifact provenance；不保留中央 turn state |
| `depends_on -> derive` promotion | 不放在 Explore；只在显式 formalization / promotion gate 使用 |
| `focuses.json` registry | 丢弃为 source of truth；accepted focus 进入 `gaia inquiry focus` 或 `question(...)` |
| `next/submit/gate` central protocol | 丢弃为 canonical API；最多保留短期 compatibility |

## 3. `$lkm-explorer` Skill

`$lkm-explorer` 和 `gaia-lkm-explore` 不同。它是 `gaia-lkm-skills` 里的 agent-side
LKM-to-Gaia formalization workflow。它把选中的 raw LKM evidence / source payload 映射成
stable Gaia DSL：

```text
claim(...)
derive(...)
contradict(...)
question(...)
```

并在 Gaia statement metadata 中保留 `lkm_id`、`provenance_source` 等 LKM provenance。

package-native research design 不应该重造这套 mapping governance。`$lkm-explorer` 的
mapping contract 应该被视为 LKM evidence 晋级到 stable Gaia source 的 promotion
contract。

同一份 LKM 输入可以处于两个合法状态：

| 状态 | 位置 | 含义 |
| --- | --- | --- |
| Research artifact | `.gaia/research/explore/` 或 `.gaia/research/assess/` | search lead、item reference、candidate relation、candidate focus；还不能进入 BP |
| Formal Gaia source | `src/<pkg>/...` | 已接受并 formalized 的 Gaia DSL source |

从 artifact promotion 到 formal source 时，必须检查 raw payload、evidence status、scope
match、duplicate/shared-factor risk 和 provenance metadata。Assessment artifact 里的
`promotion_hint` 只能提示可能的下游形式，不能机械授权写 source。

## 4. PR #726 的经验

PR #726 验证了有用的 agent-protocol 经验：

- self-contained task instructions；
- schema validation；
- allowed refs 和 grounding checks；
- assessment context 里必须有从 landscape/search result 汇总出的 items；
- event traces。

这些经验应该被吸收到 package-native actions 或 Gaia primitives 背后。

PR #726 不应该成为 canonical architecture：

- 不保留 central `next/submit/gate` 作为 primary API；
- 不保留 `focuses.json` 作为 canonical focus registry；
- 不用 `assessment_context.json` 取代 `gaia inquiry context`；
- 不用 research-loop gate 取代 `gaia build check` 或 inquiry review。

## 5. 后续文档规则

新的实现 PR 如果需要引用历史文档，应该先链接 canonical overview，再把历史文档作为
reference material。不要再把新需求加到 historical specs 里。

## 6. 共存期 Artifact 规则

在 `gaia-lkm-explore` 还没有 deprecate 前，可能同时存在两棵 artifact 树：

```text
.gaia/exploration/   # legacy experimental engine state
.gaia/research/      # package-native research trace / audit artifacts
```

共存期规则：

- `.gaia/research/` 是 `gaia research` 的 trace / audit artifact location；语义
  source of truth 应落在 package source 和 `.gaia/inquiry/`。
- `.gaia/exploration/` 可以作为 import / migration source 读取，但不能作为新的
  canonical source of truth。
- `gaia research` 不应双写两棵树；需要兼容旧结果时，显式执行 import/migrate step，
  并把原始 `.gaia/exploration/` path 记录为 provenance。
- 删除 `gaia-lkm-explore` entry point 前，必须先有文档化的替代命令覆盖主要 workflow。
