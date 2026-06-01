# Gaia Research Actions Package-Native Redesign

> **Status:** Draft
>
> **Date:** 2026-06-01
>
> **Branch:** `codex/research-actions-package-native`
>
> **English summary:** Redesign Research Loop as package-native Gaia research
> actions. `gaia research` should be a thin facade over Gaia package, inquiry,
> authoring, LKM package, and build primitives. Explore, Assess, and Propose
> communicate through Gaia package state instead of a parallel workflow protocol.
>
> **Related baseline:** PR #726, `codex/research-loop-agent-protocol`, 作为一次
> experimental baseline 保留，不在这个分支上继续修改。本设计从 Gaia package
> primitives 重新出发。
>
> **Related specs:**
>
> - [Gaia LKM Explore and Evidence Assess Design](2026-05-25-gaia-lkm-explore-assess-design.md)
> - [LKM Explore Artifact MVP Design](2026-05-26-lkm-explore-artifact-mvp-design.md)
> - [LKM Explore Iterative Landscape Design](2026-05-27-lkm-explore-iterative-landscape-design.md)
> - [Gaia Research Loop Agent Protocol Design](2026-05-28-gaia-research-loop-agent-protocol-design.md)

## 1. 摘要

Research Loop 不应该成为 Gaia 旁边的第二套研究系统。它应该成为 Gaia
package lifecycle 里的 package-native research action layer。

新的核心判断是：

```text
Gaia package = 长期研究工作区 + 沟通 contract
gaia research = Gaia 原子能力之上的薄编排层
Gaia CLI primitives = package / inquiry / authoring / build 的 source of truth
LLM / agent = 研究判断层，不维护平行状态系统
```

因此，`explore`、`assess`、`propose` 不应该被设计成一个统一的
`next/submit/gate` 状态机，而应该是几个可以独立调用、可以交替迭代的
research actions：

```text
gaia research explore
gaia research assess
gaia research propose
```

`gaia research ...` 是 canonical user/agent surface。Standalone
`gaia-research-loop` 可以作为实验或兼容入口存在，但不应该成为主接口；package-native
research behavior 应该能从 `gaia --help` 发现，并与 `gaia pkg`、`gaia inquiry`、
`gaia author`、`gaia build` 并列。

每个 action 都通过 Gaia package 状态沟通：

- `src/<pkg>/...`：稳定 formal knowledge；
- `.gaia/`：package 编译和运行 artifact；
- `.gaia/inquiry/`：focus、obligation、hypothesis、review；
- `.gaia/lkm_packages/`：被拉取的 LKM paper package；
- `.gaia/research/`：轻量 research action artifact，例如 landscape、assessment、
  proposal。

`merge` 暂时不设计。它应该发生在 `propose -> discovery/research` 之后，也就是
真的产生新实验、新模拟、新证明、新 benchmark 或新理论结果之后，再把这些结果正式
写回 Gaia package。

## 2. 为什么要重开设计

#726 里的 agent protocol 验证了几个有价值的点：

- task envelope 能让 agent 自解释地知道下一步要做什么；
- schema validation 能挡住格式错误和 ungrounded refs；
- Explore 需要多轮 landscape，而不是一次搜索；
- Assess 必须看到真实检索内容，而不只是 paper title；
- trace 和 artifact 对 audit 很有价值。

但 #726 也引入了一套新的长期状态系统：

```text
.gaia/research_loop/tasks/
.gaia/research_loop/candidates/
.gaia/research_loop/artifacts/
.gaia/research_loop/gates/
```

这会和 Gaia 已有能力重叠：

- `gaia pkg add` 已经负责添加 registry package 和 LKM paper package；
- `gaia inquiry focus` / `gaia inquiry obligation` 已经表达 focus 和 open
  proof/research obligations；
- `gaia inquiry context` 已经能构建 focus-centered context packet；
- `gaia inquiry review` 已经能保存 semantic review snapshot；
- `gaia author` 已经负责 package-native DSL 写入；
- `gaia build compile/check` 已经负责 package artifact 和结构验证。

所以新设计应该吸收 #726 的经验，但把 contract boundary 移回 Gaia package 和
Gaia CLI primitives。

## 3. 设计目标

1. Gaia package 是所有 research actions 的长期沟通介质。
2. `explore`、`assess`、`propose` 保持分离，可以单独调用。
3. `explore` 和 `assess` 允许交替迭代。
4. 优先复用 `gaia inquiry`、`gaia pkg`、`gaia author`、`gaia build`、
   `gaia search`。
5. 如果业务逻辑需要 Gaia CLI 当前不支持的能力，优先改进 Gaia CLI，而不是在
   research loop 里重复实现。
6. 所有 research action 都要留下 package-local provenance 和 audit trail。
7. assessment knowledge 和 stable formal knowledge 必须分层。

## 4. 非目标

本 spec 不做：

- `merge` 设计；
- 完整 `propose -> discovery/research -> merge` 闭环设计；
- Assess 后自动写 stable claims；
- Explore broad scan 阶段默认拉取 full paper graph；
- LKM writeback 的具体协议、节点类型、边类型和 publish 命令；
- 替代 `gaia inquiry`、`gaia pkg add`、`gaia author`、`gaia build`；
- 把 #726 的 `next/submit/gate` 保留为长期核心 API；
- 外部 agent 产品、TUI、auth、telemetry、实验室设备接入。

## 5. 核心原则

### 5.1 Package-native 沟通

每个 research action 都读写一个 Gaia package。Package 不只是 formal claim 的
容器，也是研究过程的工作区。

推荐布局：

```text
<topic>-gaia/
  pyproject.toml
  src/<topic>/...
  .gaia/
    ir.json
    inquiry/
    lkm_packages/
    research/
```

`gaia research` 可以创建轻量 artifact，但这些 artifact 必须在 package 内，并尽量
引用 Gaia-native objects，例如 QID、inquiry obligation id、LKM paper id、pulled
package name、review id。

### 5.2 已有 CLI primitives 上的薄 facade

`gaia research` 不是新的内核。它应该主要编排已有命令：

```text
gaia search lkm
gaia pkg add --lkm-paper ...
gaia inquiry focus ...
gaia inquiry obligation ...
gaia inquiry context ...
gaia inquiry review ...
gaia author question/note/artifact/claim/derive/contradict ...
gaia build compile/check ...
```

如果一个 research action 需要某种能力，而现有 Gaia CLI 表达不了，优先补底层 CLI
primitive，而不是在 `gaia research` 里偷偷维护另一套语义。

当前代码库里的 package ingestion primitive 是 `gaia pkg add`。如果未来出现顶层
`gaia add`，它应该只是更友好的 alias 或 wrapper；`gaia research` 在可执行建议和
agent-facing instructions 里应优先使用明确的 `gaia pkg add --lkm-paper ...`，
避免让 agent 学到两套混用 contract。

### 5.3 Explore 和 Assess 是 actions，不是一次性 phase

真实研究不是：

```text
Explore everything -> Assess everything
```

而更像：

```text
explore scan
  -> assess focus A
  -> discover gap
  -> explore expand for that gap
  -> reassess focus A
  -> propose open research question
```

所以 `explore` 和 `assess` 必须可以反复调用、局部调用、交替调用。

### 5.4 Assessment 不是 discovery

Assess 之后的内容值得保存、复用和审查，但它不是 primary discovery。至于是否以及如何
写回 LKM，需要单独设计，本 spec 暂不展开。

Assessment artifact 可以表达：

- 现有 evidence 支持什么；
- 哪些 evidence 反对或削弱这个判断；
- 哪些结论只在特定边界内成立；
- 置信度为什么低；
- 还剩哪些 obligation；
- 下一步研究最应该做什么。

但它不能默认伪装成新观察、新证明或新发现。

### 5.5 Propose 是开放研究问题，不是 package diff

`propose` 的语义是提出 open-ended research questions、hypotheses、
experiments、simulations、proofs、benchmarks 或 research tasks。

它不是 Git-style package diff proposal。Formal claim merge 应该放到未来
`merge` 设计里，而且只发生在 discovery/research 之后。

## 6. Research Actions 边界

### 6.1 Explore

Explore 负责扩大问题空间、建立 landscape。

它回答：

- 这个领域/问题的 literature 和 evidence landscape 长什么样？
- 有哪些 paper families、claim families、method families、model families、
  population/system families？
- coverage gaps 在哪里？
- 哪些 candidate focuses / obligations 值得进入 Assess？

Explore 可以产出：

- landscape snapshots；
- query provenance；
- paper leads；
- evidence snippets；
- coverage observations；
- candidate focuses；
- candidate obligations；
- pull candidates with rationale。

Explore 不应该：

- 做最终 evidence adjudication；
- 把每篇 paper 过早 formalize 成 package claims；
- 默认 deep-pull 每篇相关 paper；
- 写 stable claims 到 `src/<pkg>/`。

### 6.2 Assess

Assess 固定一个 focus 或 obligation，然后评估现有 evidence。

它回答：

- 围绕这个 focus，现有 evidence 到底说明什么？
- 哪些 claims 支持它，哪些 claims 反对它？
- 哪些 tension 是真实冲突，哪些只是方法、范围或概念差异？
- 哪些 uncertainty 仍然存在？
- 是否需要回到 Explore 补检索、补 paper、补证据族？

Assess 可以产出：

- assessment artifact；
- evidence packet；
- tensions and contradictions；
- confidence notes；
- limitations；
- missing evidence；
- obligations for further work。

Assess 必须绑定到以下之一：

- Gaia claim 或 question QID；
- current inquiry focus；
- inquiry obligation；
- package-local research focus，且可以追溯回 inquiry state。

Assess 不应该：

- 默认写 stable formal claims；
- 自动关闭 obligations；
- 把自己的 interpretive judgment 当成 discovery result。

### 6.3 Propose

Propose 把 assessed gaps 和 landscape tensions 转成开放研究方向。

它回答：

- 下一步应该问什么新问题？
- 哪个实验、模拟、证明、数据集或 benchmark 最能降低不确定性？
- 哪些 obligations 应该被追踪？
- 哪些 hypotheses 值得作为 working hypotheses 保存？

Propose 可以产出：

- proposal artifacts；
- open questions；
- hypotheses；
- candidate inquiry obligations；
- suggested discovery tasks。

默认行为应该只写 proposal artifact。写入 `.gaia/inquiry/` 应该需要显式确认，例如
`--accept`。

## 7. Explore / Assess 交替迭代

Explore 和 Assess 必须允许交替。这个循环由 obligations 和 coverage gaps 驱动。

推荐形态：

```bash
gaia research explore <pkg> --mode scan
gaia research assess <pkg> --focus <focus-or-qid>
gaia research explore <pkg> --mode expand --obligation <obligation-id>
gaia research assess <pkg> --focus <focus-or-qid> --revision
gaia research propose <pkg> --from-assessment <assessment-id>
```

规则：

- 每次 Assess 必须绑定一个 focus 或 obligation。
- 每次 targeted Explore 必须声明自己是 broad scan 还是 obligation-driven
  expansion。

这样既保留研究灵活性，又不会把 map-making 和 evidence weighing 混成一团。

## 8. Paper pull 策略

过早拉取 LKM paper package 会造成 deep-dive bias。Explore broad scan 阶段如果
太快 `gaia pkg add --lkm-paper`，系统会被少数高相关 paper 的 claim graph 带偏。

默认策略应该是：

```text
search first, pull later
```

### 8.1 Explore scan

`explore --mode scan` 默认不 deep pull。

它可以保存：

- paper ids；
- titles；
- snippets；
- query provenance；
- ranking signals；
- candidate pull rationale。

除非显式设置 pull budget，否则不运行 `gaia pkg add --lkm-paper`。

### 8.2 Explore expand

`explore --mode expand` 可以在 obligation 需要 deeper evidence 时拉少量 selected
paper packages。

pull 必须有 rationale，例如：

- paper 被多个 query family 命中；
- paper 是某个 controversy 的 anchor；
- paper 对 inspect 某个 claim 必要；
- paper 被 assessment gap 选中；
- paper 对降低某个 tension 的不确定性 expected value 高。

### 8.3 Assess prepare

Assess 可以拉 selected paper package，因为它已经绑定到一个 focus。这里是 deeper
evidence access 的自然位置。

但即使在 Assess 里，pull 也应该显式、预算化、可追踪。

## 9. Package 状态模型

### 9.1 Formal source

```text
src/<pkg>/...
```

这里存 stable formal Gaia DSL declarations。`explore`、`assess`、`propose`
默认都不应该写 stable claims 到这里。

`gaia author question` 可以用于用户接受后的 open question。Stable claims 应该留给
未来 `merge` 或明确的人类确认 authoring。

### 9.2 Inquiry state

```text
.gaia/inquiry/
  state.json
  tactics.jsonl
  reviews/
```

这里是以下对象的 canonical home：

- current focus；
- focus stack；
- obligations；
- hypotheses；
- local review snapshots。

Research actions 应该复用这里，而不是自己维护一个长期 focus / obligation ledger。

### 9.3 LKM paper packages

```text
.gaia/lkm_packages/
```

被拉取的 LKM paper 应该通过 `gaia pkg add --lkm-paper` materialize 成 local Gaia
package dependency。Research actions 可以建议 pull，但 package materialization 由
`gaia pkg add` 这个 primitive 承担。

### 9.4 Research artifacts

```text
.gaia/research/
  manifest.json
  events.jsonl
  explore/
  assess/
  propose/
```

这里存不是 formal Gaia DSL 的轻量 artifact：

- landscape snapshots；
- search manifests；
- assessment packets；
- proposal artifacts；
- action traces；
- provenance indexes。

这些 artifact 应该尽量引用 package-native objects：

- LKM paper ids；
- pulled package names；
- QIDs；
- inquiry obligation ids；
- review ids；
- source paths；
- content hashes。

## 10. Artifact 状态类型

Research artifacts 必须显式带 epistemic status。

| Status | 含义 | 例子 |
| --- | --- | --- |
| `search_result` | 外部检索输出 | LKM search envelope |
| `landscape` | breadth-first 领域地图 | paper leads 和 coverage |
| `assessment` | 对已有 evidence 的解释 | evidence packet |
| `proposal` | 下一步研究建议 | open question 或 experiment plan |
| `formal` | stable package knowledge | Gaia DSL claim |
| `discovery` | 新研究结果 | future merge input |

这个区分是为了避免后续系统把 assessment artifact 误读成 paper claim 或 discovery
claim。未来如果设计 LKM writeback，也必须保留这个 epistemic status。

## 11. 硬性不变量

后续实现 PR 必须满足这些 invariants。它们比具体命令实现更重要。

1. `.gaia/research/` 不能成为 canonical focus registry。Accepted focus 必须进入
   `gaia inquiry focus`，或在用户确认后 promotion 成 package `question(...)`。
2. `.gaia/research/` 不能成为 canonical obligation ledger。Accepted gaps 必须能通过
   `gaia inquiry obligation list` 看见。
3. `explore`、`assess`、`propose` 默认不写 stable claims。只有显式 accept /
   promotion / future merge 命令才能写入 stable formal source。
4. Research artifacts 必须尽量引用 Gaia-native identifiers：QIDs、obligation ids、
   LKM paper ids、pulled package names、source paths、content hashes。
5. `gaia build check` 仍然是 package structural validation path。Research-specific
   checks 可以存在，但不能替代 package checks。
6. Broad `explore --mode scan` 默认 pull budget 为 0。
7. Assessment artifacts 必须带 epistemic status，不能被解释成 paper claims 或
   discovery claims。

## 12. Gaia Package 里的 Knowledge Model

这里是本设计最关键的语义问题：research 过程中提炼出的 focus、obligation、
assessment relation 最终在 Gaia package 里是什么？

当前 Gaia DSL 对 stable formal knowledge 已经比较强：

- `claim(...)` 是 truth-bearing，可以进入 BP；
- `question(...)` 是 open inquiry，不参与 BP；
- `note(...)` 是非概率背景上下文；
- `derive(...)`、`observe(...)`、`compute(...)`、`infer(...)` 表达支持或证据；
- `equal(...)`、`contradict(...)`、`exclusive(...)`、`decompose(...)` 表达强
  structural relations；
- `depends_on(...)` 和 `candidate_relation(...)` 表达 scaffold-tier unfinished
  formalization；
- `gaia inquiry obligation` 表达 package source / IR 之外的 mutable inquiry
  obligations。

这些能力足以承载很多 formalized outcomes，但还不完整覆盖 research-loop 业务逻辑。
缺的是 assessment-level relations：`supports`、`opposes`、`qualifies`、
`undercuts`、`background_for`、`needs_more_evidence`。未来可以扩展
`replicates`、`extends` 等更细关系，但第一版词表应刻意收窄。这些关系不应该全都
变成 BP factor 或 hard logical operator。

### 12.1 Focus 通常应该是 Question，不是 Claim

Research focus 是 inquiry lens。它经常是在问多个 candidate answer claims 之间
哪个更合理，或者边界条件是什么。

例子：

```python
dqcp_focus = question(
    "Is the Neel-VBS transition a true continuous DQCP, weakly first-order, "
    "or pseudo-critical/walking behavior?",
    targets=[
        dqcp_continuous,
        dqcp_weakly_first_order,
        dqcp_walking,
    ],
)
```

Focus 本身不是 true / false。真正 truth-bearing 的是 answer claims：

```python
dqcp_continuous = claim("The Neel-VBS transition realizes a continuous DQCP.")
dqcp_weakly_first_order = claim("The Neel-VBS transition is weakly first-order.")
dqcp_walking = claim("The observed scaling is pseudo-critical walking behavior.")
```

Paper claims 通常应该支持或反对 answer claims，而不是直接支持或反对 focus
question。

因此 package model 应该是：

```text
Question / Focus
  targets Candidate Answer Claims
    supported / opposed / qualified by Evidence Claims
```

如果 Explore 发现了一个 focus，但 answer claims 还没准备好，它可以先存在于
inquiry state 或 `.gaia/research/explore/` artifact。用户接受后，再 promotion 成
`question(...)`。Answer claims 可以稍后补。

### 12.2 Obligation 是过程知识，不是 stable truth claim

Obligation 表达的是“接下来必须证明、检查、补证据、澄清边界的事情”。它不是对世界
的稳定命题。

当前 Gaia 已经有合适的默认位置：

```text
.gaia/inquiry/state.json
  synthetic_obligations[]
```

Obligation 可以 attach 到：

- focus question；
- answer claim；
- assessment artifact；
- pulled paper package 或 paper claim；
- early exploration 阶段的 freeform research target。

部分 obligation 未来可能 promotion 成 `question(...)`，但不是每个临时 obligation
都应该写进 package source。

### 12.3 Assessment relation 比 formal relation 更丰富

当前 Gaia relation verbs 语义很强：

- `contradict(a, b)` 是 claim truth values 之间的 hard relation；
- `exclusive(a, b)` 是 closed partition / complement-style relation；
- `derive(conclusion, given=...)` 是 formal support step；
- `infer(evidence, hypothesis=...)` 是 probabilistic evidence model。

Assessment 需要更宽的关系词表：

| Assessment relation | 含义 | Package treatment |
| --- | --- | --- |
| `supports` | evidence favor 某个 answer claim | 只有 formalized 后才 promotion 成 `derive` 或 `infer` |
| `opposes` | evidence count against 某个 answer claim | 只有逻辑不兼容时才是 `contradict`，否则可能是 `infer` 或 artifact relation |
| `qualifies` | evidence 缩小适用边界 | 先存在 assessment artifact，必要时变成 narrower claim |
| `undercuts` | evidence 削弱方法、假设或 inference route | 通常是 assessment artifact 或 obligation |
| `background_for` | 提供上下文，不直接支持 | `note(...)` 或 artifact relation |
| `needs_more_evidence` | gap 未解决 | inquiry obligation |

因此 assessment relations 应该先作为 research artifacts 存在。Promotion rules 再决定
什么时候进入 Gaia DSL：

```text
assessment supports -> derive / infer
assessment opposes -> contradict / infer / candidate_relation
assessment qualifies -> narrower claim + derive, or stays assessment-only
assessment undercuts -> obligation / assessment artifact
assessment needs_more_evidence -> inquiry obligation
```

每条 assessment relation 都应该携带 `promotion_hint`，第一版限定在：

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

这允许 assessment 先有用起来，同时避免过早扩展 Gaia DSL。

### 12.4 当前 Gaia 语法缺口

现在能表达：

- `question(...)`：accepted focus questions；
- `claim(...)`：candidate answer claims；
- `derive(...)` / `infer(...)`：formalized support；
- `contradict(...)` / `exclusive(...)`：强 answer-claim relations；
- `depends_on(...)`：unfinished support dependencies；
- `candidate_relation(...)`：unfinished equal/contradict/exclusive relations；
- `.gaia/inquiry/state.json`：obligations 和 hypotheses。

还缺：

- first-class assessment relation vocabulary；
- `gaia inquiry context` 对 question、obligation、assessment artifact 的支持；
- richer obligation metadata 和 lifecycle；
- 把 assessment/proposal artifact accept 到 inquiry state 的命令；
- 未来如果要写回 LKM，还需要 package-to-LKM identity mapping 和 artifact status
  preservation，但这部分暂不在本 spec 中设计。

结论：不要把所有 focus 和 obligation 都重载成 `claim(...)`。Gaia 需要保持分层：

```text
question = open inquiry
claim = truth-bearing proposition
obligation = process requirement
assessment relation = interpretive relation over existing evidence
formal relation = compiled Gaia DSL relation
```

## 13. LKM 整合边界（暂不设计写回）

Assess 之后的分析内容未来可能值得写回 LKM，因为它包含对 evidence 的解释、张力、
限制和后续研究问题。但现在还不应该设计具体写回协议。

本 spec 只保留三条边界约束：

1. Assessment artifact 不能被 flatten 成 paper claim。
2. Proposal artifact 不能被 flatten 成 discovery claim。
3. 如果未来要写回 LKM，必须保留 artifact 的 epistemic status、package provenance
   和 source references。

换句话说，本阶段只设计 Gaia package 内部如何表达和组织 research actions，不设计
LKM 的节点类型、边类型、publish command、去重逻辑或长期存储 contract。

## 14. CLI 形态

`gaia research ...` 是 canonical CLI surface。第一版至少应注册在主 `gaia` CLI 下，
让用户和 agent 从 `gaia --help` 能发现它。

推荐顶层形式：

```bash
gaia research status <pkg>
gaia research explore <pkg> --mode scan
gaia research explore <pkg> --mode expand --obligation <id>
gaia research assess <pkg> --focus <focus-or-qid>
gaia research propose <pkg> --from-assessment <id>
```

还需要 dry-run 和 artifact-only mode：

```bash
gaia research explore <pkg> --mode scan --dry-run
gaia research assess <pkg> --focus <focus-or-qid> --artifact-only
gaia research propose <pkg> --from-assessment <id> --accept
```

`--accept` 只用于把 proposal 输出写入 inquiry state 或 accepted package question。
它不写 stable claims。

### 14.1 `gaia pkg add` layering

当前实现应以 `gaia pkg add --lkm-paper ...` 作为 paper package ingestion primitive。

分层约定：

- `gaia pkg add --lkm-paper ...`：明确的 package-local primitive，适合 `gaia research`
  生成可执行建议或内部调用；
- future `gaia add ...`：如果出现，只能作为更友好的 user-facing alias；
- `gaia research explore/assess`：在 agent-facing instructions 里使用
  `gaia pkg add --lkm-paper ...`，避免同时教学两种入口。

## 15. 复用已有 Gaia CLI

### 15.1 Explore 复用

- `gaia search lkm`：retrieval；
- `gaia pkg add --lkm-paper`：只用于 gated pulls；
- `gaia inquiry obligation add`：用户接受后的 coverage gaps；
- `gaia inquiry hypothesis add`：用户接受后的 working hypotheses；
- `.gaia/research/explore/`：landscape artifacts。

### 15.2 Assess 复用

- `gaia inquiry focus`：resolve 或 set focus；
- `gaia inquiry context`：构建 focus-centered context；
- `gaia inquiry review`：检查已有 package state；
- `gaia pkg add --lkm-paper`：拉 selected evidence；
- `.gaia/research/assess/`：assessment artifacts。

### 15.3 Propose 复用

- assessment artifacts 作为输入；
- `gaia inquiry obligation add`：accepted obligations；
- `gaia inquiry hypothesis add`：accepted hypotheses；
- `gaia author question`：accepted package-level open questions；
- `.gaia/research/propose/`：proposal artifacts。

## 16. 需要补的 Gaia CLI 能力

### 16.1 Inquiry obligation metadata

当前 obligation 主要支持 `target_qid`、`content`、`kind`。Research actions 需要更
丰富 metadata：

- source assessment id；
- linked paper refs；
- linked query provenance；
- uncertainty type；
- suggested action type；
- status transitions beyond open/closed。

推荐改法：扩展 `gaia inquiry obligation add` 和 inquiry state model，而不是另写
research-loop obligation schema。

### 16.2 Inquiry focus over freeform research questions

`gaia inquiry focus` 可以保存 freeform focus，但 `gaia inquiry context` 对 claim
focus 的支持更强。Explore 经常会先产生 focus，再产生 formal claim。

推荐改法：让 `gaia inquiry context` 能为以下对象生成有用 context：

- question nodes；
- obligation ids；
- freeform focuses with linked research artifacts；
- package-local research focus ids。

### 16.3 Assessment relation vocabulary

当前 `candidate_relation(...)` 只支持 `equal`、`contradict`、`exclusive`。Assess
需要非 lowering 的 relation types。第一版只设计 artifact-level 词表：

```text
supports
opposes
qualifies
undercuts
background_for
needs_more_evidence
```

推荐改法：先定义 artifact-level relation vocabulary；未来如果需要，再做 DSL
scaffold primitive。

可能形态：

```python
assessment_relation(
    source=evidence_claim,
    target=answer_claim,
    relation="qualifies",
    assessment_id="...",
    rationale="...",
)
```

第一版可以不进 DSL，只作为 `.gaia/research/assess/` schema，但词表要和未来
promotion hints 和其他下游整合保持兼容。

### 16.4 Question targets and answer claims

`question(...)` 已经支持 `targets`，但 CLI flow 对“先发现 focus，后定义 answer
claims”的情况还不理想。

推荐改法：

- 允许 `gaia author question` 记录 provisional targets 或 metadata；
- 增加更新 question targets 的能力；
- 约定从 accepted focus 生成 answer-claim labels 的规则。

### 16.5 Search result artifact standardization

`gaia search lkm` 应该输出稳定、package-friendly 的 envelope，让 `gaia research`
不用再做大量翻译。

推荐改法：在 `gaia search` 层标准化 search output 和 provenance。

### 16.6 Assessment artifact schema

Assessment artifact 需要稳定 shape，但这不代表要回到 standalone workflow protocol。
它应该是 package-local research artifact，引用 Gaia objects。

推荐改法：添加 `gaia.engine.research` 或 `gaia.research` schema models，只做
artifact validation 和 docs，不取代 package / inquiry。

### 16.7 LKM writeback 暂缓

LKM writeback 需要单独设计。当前 spec 不定义 publish command，也不定义 LKM 节点或
边 schema。

这一阶段只要求 `.gaia/research/` artifacts 保留足够 provenance，使未来设计写回时
不会丢失 package、QID、paper id、snippet、assessment status 等来源信息。

## 17. 从 #726 迁移

#726 作为 experimental baseline，不作为最终 contract。

应该保留的经验：

- self-contained agent instructions 有价值；
- schema validation 有价值；
- allowed refs 和 grounding checks 有价值；
- retrieved snippets 必须进入 assessment；
- event traces 有价值。

不应该保留为长期架构的部分：

- `next/submit/gate` 作为中央用户协议；
- `focuses.json` 作为 canonical focus registry；
- `assessment_context.json` 取代 `gaia inquiry context`；
- paper leads 取代 `gaia pkg add --lkm-paper`；
- research-loop-only gate state 成为 readiness source of truth。

如果复用 #726 的代码经验，必须迁移到 package-native actions 或 Gaia CLI primitives
背后。

## 18. 实现切片

### M1: Canonical CLI skeleton + package-native manifest

第一轮实现应该刻意小。目标是证明 package-native boundary，而不是做完整 Explore。

建议只实现：

```bash
gaia research status <pkg>
gaia research explore <pkg> --mode scan --dry-run
gaia research assess <pkg> --focus <target> --artifact-only
```

行为：

- 注册在主 `gaia` CLI 下；
- 确认 existing Gaia package；如果目标不存在，只建议或调用 `gaia pkg scaffold`，
  不自行生成 package layout；
- 写入 `.gaia/research/manifest.json` 和 `events.jsonl`；
- 读取 current inquiry state；
- 输出下一步 Gaia-native primitive 建议；
- 不创建 parallel focus registry；
- 不 pull papers；
- 不写 stable source claims。

验证：

- 创建 package 后 dry research action 会生成 `.gaia/research/manifest.json`；
- 不修改 `src/<pkg>` formal source。
- `gaia --help` 能发现 `research` group。
- `gaia build check` 仍然是 package 结构验证路径。
- suggested gaps 应表达为可执行的 `gaia inquiry obligation add ...` 建议，而不是
  `.gaia/research/` 下的长期 obligation ledger。

### M2: Explore scan

实现 `gaia research explore --mode scan`，薄封装 LKM search。

输出：

- landscape artifact；
- query provenance；
- paper leads；
- pull candidates；
- candidate coverage gaps。

验证：

- 默认 pull budget 为 0；
- 除非显式请求，否则不创建 `.gaia/lkm_packages/`；
- landscape refs 保留 LKM provenance。

### M3: Explore expand

从 obligation 做 targeted exploration。

输出：

- targeted landscape artifact；
- obligation coverage update；
- optional pull candidates。

验证：

- command 需要 `--obligation` 或等价 target；
- artifact 链接回 obligation id。

### M4: Assessment artifact and relation vocabulary

定义 package-local assessment artifact schema 和 relation vocabulary。

输出：

- focus question 的 candidate answer claims；
- support / opposition / qualification / undercut relations；
- promotion hints to Gaia DSL。

验证：

- assessment relations 明确区分 interpretive status 和 formal DSL status；
- 不在语义不足时 emit hard formal relations。

### M5: Assess

实现 `gaia research assess --focus ...`。

输入：

- focus 或 obligation；
- inquiry context；
- selected landscape artifacts；
- optional pulled paper packages。

输出：

- assessment artifact；
- evidence packet；
- new candidate obligations。

验证：

- assessment artifact 链接到 focus 或 obligation；
- supporting/opposing refs 能 resolve 到 LKM ids、pulled packages、QIDs 或
  stored snippets；
- 不写 stable claims。

### M6: Propose

实现 `gaia research propose --from-assessment ...`。

输出：

- proposal artifact；
- open questions；
- hypotheses；
- candidate obligations。

验证：

- 默认只写 proposal artifact；
- `--accept` 才写入 inquiry state 或 package questions；
- 不写 stable claims。

## 19. 开放问题

1. `.gaia/research/` 只用 JSON 文件，还是为了大规模检索/审查加 SQLite 或 index？
2. accepted open questions 什么时候用 `gaia author question`，什么时候只用
   `gaia inquiry obligation add`？
3. assessment artifacts 是否参与 `gaia build check`，还是应该有单独的
   `gaia research check`？
4. assessment relation vocabulary 应该只是 artifact schema，还是也应该成为 Gaia DSL
   scaffold？
5. `question(...)` 是否需要 first-class alternatives / answer claims，还是现有
   `targets=[...]` 加 CLI 支持就够？

## 20. 推荐近期决策

在新分支上推进 package-native `gaia research` 设计，#726 保持 experimental baseline。

第一轮实现不要追求全自动。它只需要证明新的边界成立：

```text
package-native state
  + Gaia CLI primitives
  + lightweight research artifacts
  + no duplicate long-term focus/obligation truth source
```

一旦这个边界跑通，外层 agent skill 就可以编排这些 actions，而不需要维护一套平行
research-loop protocol。
