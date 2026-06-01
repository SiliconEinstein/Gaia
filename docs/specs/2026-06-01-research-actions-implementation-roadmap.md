# Research Actions Implementation Roadmap

> **状态：** package-native research actions 的 canonical implementation roadmap。
>
> **日期：** 2026-06-01
>
> **Canonical overview：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)
>
> **迁移说明：**
> [Research Actions Migration Notes](2026-06-01-research-actions-migration-notes.md)

## 1. 实现原则

`gaia research` 应该按小切片实现。每个切片都必须保留 overview 中的硬性不变量：

- 不创建平行 focus registry；
- 不创建平行 obligation ledger；
- 默认不写 stable source；
- `gaia build check` 仍然是 package structural validation path；
- early Explore 保持 breadth-first，默认 pull budget 为 0。

近期净增量主要是把 Explore 重新归位：landscape-first、package-native，并明确哪些
`gaia-lkm-explore` 能力需要迁移。Assess 在这份 roadmap 中刻意较薄：先落 artifact
schema、relation vocabulary、grounding 和 promotion hints。完整 assessment
formalization、source promotion 和 LKM writeback 需要后续 spec。

## M1. Canonical CLI Skeleton And Manifest

实现：

```bash
gaia research status <pkg>
gaia research explore <pkg> --mode scan --dry-run
gaia research assess <pkg> --focus <target> --artifact-only
```

行为：

- 在主 `gaia` CLI 下注册 `research`；
- 确认目标是已有 Gaia package；
- 如果目标不存在，只建议或调用 `gaia pkg scaffold`，不要创建第二套 layout；
- 写入 `.gaia/research/manifest.json` 和 `events.jsonl`；
- 读取 current inquiry state；
- 输出 Gaia-native next-step suggestions；
- 不创建 parallel focus registry；
- 不 pull papers；
- 不写 stable source claims。

验证：

- `gaia --help` 能发现 `research`；
- dry action 创建 `.gaia/research/manifest.json`；
- `src/<pkg>/` 不变；
- `gaia build check` 仍是 package validation path；
- suggested gaps 输出为 `gaia inquiry obligation add ...` 建议，而不是
  `.gaia/research/` 下的 durable obligation ledger。

## M2. Explore Scan

实现 `gaia research explore --mode scan`。

它应该组合 `gaia search lkm`，并 port `gaia-lkm-explore` 中可复用的 deterministic
landscape-staging 逻辑。不要只 dump raw search output，也不要继承旧 central turn state
machine。

输出：

- landscape artifact；
- query provenance；
- paper leads；
- pull candidates；
- candidate coverage gaps；
- breadth-first coverage map，包括 query families、claim/method clusters、
  under-covered regions 和 candidate focuses。

验证：

- pull budget 默认 0；
- 除非显式请求，否则不创建 `.gaia/lkm_packages/`；
- landscape refs 保留 LKM provenance；
- 第一轮 scan 不强迫进入 top-paper assessment；
- candidate focuses 保持候选状态，不进入 canonical focus registry。

## M2b. Port Selected Exploration Utilities

按 package-native 边界迁移 `gaia-lkm-explore` 中已经验证过的 deterministic utilities。

应迁移：

- paper-lead landscape builder；
- query / round / artifact provenance normalization；
- pull-candidate dedup 和 rationale aggregation；
- MapHealth / orphan / fragmentation signals 到 status/check 或 candidate obligations。

不应迁移：

- `next/submit/gate` 作为主协议；
- `.gaia/exploration/map.json` 作为 canonical semantic state；
- `focuses.json` 作为 focus registry；
- early frontier ranking 作为 broad-scan completion criterion。

验证：

- migrated utilities 写 `.gaia/research/` artifacts，而不是 `.gaia/exploration/`
  source of truth；
- output refs 可追溯到 LKM search refs、paper ids、QIDs 或 inquiry ids；
- `src/<pkg>/` 不变。

## M3. Explore Expand

从 obligation 或 accepted focus 做 targeted exploration。

输出：

- targeted landscape artifact；
- obligation coverage update；
- optional pull candidates。

验证：

- command 需要 `--obligation`、`--focus` 或等价 target；
- artifact 链接回 inquiry id、focus 或 accepted research artifact；
- pulls 保持 budgeted 和 explicit。

## M4. Assessment Artifact Schema

定义 package-local assessment artifact schema 和第一版 relation vocabulary：

```text
supports
opposes
qualifies
undercuts
background_for
needs_more_evidence
```

每条 relation 可以携带 `promotion_hint`：

```text
depends_on
candidate_relation
derive
infer
contradict
question
obligation
none
```

验证：

- relation records 包含 epistemic status；
- source refs 可以 resolve 到 snippets、LKM ids、pulled packages、QIDs 或 inquiry ids；
- `promotion_hint` 不写 source。

## M5. Assess

实现 `gaia research assess --focus ...`。

输入：

- focus 或 obligation；
- inquiry context；
- selected landscape artifacts；
- optional pulled paper packages。

输出：

- assessment artifact；
- evidence packet；
- support / opposition / qualification / undercut relations；
- new candidate obligations。

验证：

- artifact 链接到 focus 或 obligation；
- evidence packet 包含 retrieved snippets；
- supporting/opposing refs 可 resolve；
- 默认不写 stable claims。

## M6. Propose

实现 `gaia research propose --from-assessment ...`。

输出：

- proposal artifact；
- open questions；
- hypotheses；
- candidate obligations。

验证：

- 默认只写 proposal artifact；
- `--accept` 可以写 inquiry state 或 package questions；
- 不写 stable truth claims。

## Later Specs

这些内容不在本 roadmap 中：

- assessment formalization engine；
- formal source promotion command；
- LKM writeback protocol；
- Propose -> Discover -> Merge 闭环；
- external TUI 或 agent product surface。
