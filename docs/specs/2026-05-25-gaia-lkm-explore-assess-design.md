# Gaia LKM Explore and Evidence Assess Design

> **Status:** Draft
>
> **Date:** 2026-05-25
>
> **Updated:** 2026-05-26
>
> **Scope:** `gaia-lkm-explore`, its handoff to `gaia-evidence assess`,
> and the first two stages of the larger Gaia research loop:
> `Explore -> Assess -> Propose -> Discover -> Merge`. This revision also
> defines the Gaia-side independent MVP that can later be wrapped by an
> external Scientific Agent CLI/TUI harness.

## Proposal: 细化 Gaia 研究闭环中的 Explore 与 Assess

这份 proposal 的定位需要说清楚：它不是要替代更大的 Gaia 研究闭环，而是细化其中前两个模块。

大闭环来自现有设计文档：

```text
Explore -> Assess -> Propose -> Discover -> Merge
```

完整语义是：

```text
探索领域
  -> 找到问题
  -> 分析已有研究
  -> 提出下一步研究
  -> 执行并得到结果
  -> 更新 Gaia 图和 belief
  -> 回传 LKM / knowledge base
```

这份 proposal 只聚焦前两步：

```text
Explore -> Assess
```

也就是回答：

- `gaia-lkm-explore` 到底应该负责什么？
- Evidence assessment 应该从哪里接手？
- Explore 和 Assess 之间的 typed artifact 应该长什么样？
- 这两步如何给后面的 `Propose -> Discover -> Merge` 提供干净输入？
- Gaia 这边应该先独立开发哪一层，才能以后被外部 agent harness 稳定调用？

## Current main baseline, 2026-05-26

After merging the latest `origin/main`, part of this proposal is no longer
purely future-facing. The current baseline already includes:

- a unified sibling CLI entrypoint, `gaia-lkm-explore`, under
  `gaia.lkm_explorer.client`;
- deterministic engine verbs including `init`, `observe`, `landscape`,
  `frontier`, `round`, `status`, and `render`;
- a neutral paper-level `landscape` command that aggregates saved
  `gaia search lkm` result envelopes before deep pulls;
- MapHealth connectivity, orphan/island detection, ratified separations, and
  consolidate-oriented readouts;
- pulled-paper claim triage metadata and `frontier --triage-pulled`;
- checkpoint-time promotion of pulled-paper `depends_on` scaffolds into live
  `derive` strategies for exploration inference.

The remaining proposal should therefore be read as the next layer on top of
that baseline, not as a replacement for it. The main missing pieces are:

- a first-class `scope` artifact rather than ad hoc seed text;
- a `focuses` / obligation artifact that turns landscape findings into assessment
  targets;
- a standard `lkm_exploration` artifact envelope with provenance and gate
  status;
- an explicit Explore gate that decides whether the artifact is ready for
  assessment;
- a `gaia-evidence assess --exploration ... --focus ...` handoff and matching
  assessment context schema;
- focus-aware deep-dive turns, so frontier expansion serves a chosen focus
  rather than only the global open frontier.

The first implementation slice is specified in
[LKM Explore Artifact MVP Design](2026-05-26-lkm-explore-artifact-mvp-design.md).
It covers the additive Explore-side artifacts (`scope`, `focuses`, `artifact`,
and `gate`) and leaves `gaia-evidence assess` for a later spec.

## 0. Gaia-side 独立推进定位

近期讨论里出现了一个相邻但不同的产品方向：建设一个可分发的
Scientific Agent CLI/TUI，让 agent 通过本地安装、登录认证、dry run、权限
gate、telemetry、审计日志和轨迹回放，主动把实验室环境改造成 agent-ready
CLI。这个方向很重要，但它不应该成为 Gaia 第一阶段的开发范围。

Gaia 这边第一阶段要独立做的是 **Research Loop Core**：

```text
agent / human / future TUI
  -> calls Gaia/LKM commands
  -> exchanges typed artifacts
  -> receives auditable research next steps
```

也就是说，Gaia 暂时不做外层 agent 产品，不做 TUI，不做公司级账号、遥测、
灰度发布或真实实验室设备接入。Gaia 负责提供稳定的科研语义内核：

- 把开放研究问题变成 evidence landscape 和 candidate focuses（候选分析焦点）；
- 对某个 focus 做 evidence assessment，诊断矛盾与 gap；
- 产出可审计的 artifact，供下一步 proposal / discovery / merge 使用；
- 让外部 agent 只需要按 contract 读写 artifact、调用 CLI，就能接入 Gaia。

这个边界能让 Gaia 和未来的 Scientific Agent CLI/TUI 互补：

```text
Scientific Agent harness:
  Plan / Edit / Execute / Review UI, auth, telemetry, operational gates,
  environment refactoring, Lab CLI scaffold.

Gaia Research Loop Core:
  research semantics, LKM retrieval, evidence landscape, assessment,
  belief updates, audit artifacts, registry / LKM handoff.
```

因此本 spec 的 MVP 不包含 agent harness 本体，而是把 Gaia/LKM 的后端协议先做稳。

## 1. 为什么需要重新拆前两步

这次用 `gaia-lkm-explore` 跑「阿司匹林对一级预防心血管疾病的作用」时，流程能跑通，但暴露了一个职责混杂问题。

当前实际流程接近：

```text
seed
  -> search
  -> observe
  -> frontier
  -> pull paper
  -> formalize claims
  -> compile / infer
  -> checkpoint
```

这个流程的问题不是没有能力，而是太早进入局部深挖：

- 第一轮容易被某篇局部相关论文带偏，而不是先建立全局 evidence landscape。
- pull 一篇 paper 后会爆出大量 claim/question contacts，frontier 很快被细节淹没。
- 系统能扩图，但不清楚「为什么扩这个」「扩到什么时候停」「哪些 claim 值得评估」。
- Evidence assessment 没有干净输入，只能在一堆 raw hits、claims、frontier 里再整理上下文。

所以需要把前两步拆清楚：

```text
Explore: 建立领域地图，暴露问题
Assess: 分析已有研究与矛盾，判断哪些 gap 值得变成下一步研究
```

## 2. 核心哲学

前两步的哲学是：

> Explore 不给最终答案，Assess 不做开放探索。

更具体地说：

```text
Explore 负责 breadth-first，看见版图。
Assess 负责 depth-selective，解释矛盾。
```

Explore 的问题是：

```text
这个领域/问题的证据版图长什么样？
有哪些主要证据族、模型族、材料族？
哪里有冲突、空洞、未履行义务？
哪些区域值得 Assess？
```

Assess 的问题是：

```text
围绕一个 focus，已有证据到底说明了什么？
矛盾来自数据、模型、方法、population、systematics，还是概念混淆？
哪些 gap 是真实 gap？
下一步最小判别测试是什么？
```

它们的边界要靠 typed artifact 固定下来，而不是靠 prompt 约定。

## 3. 建议的前两步内部分解

我建议把大闭环里的前两步细化成下面几个子阶段。

注意：这些不是新的主链步骤，而是 Explore/Assess 内部的可实现模块。

```text
Explore
  1. Scope Adapter
  2. Landscape Builder
  3. Frontier / Obligation Mapper
  4. Explore Gate

Assess
  5. Assessment Context Builder
  6. Evidence Diagnosis
  7. Gap / Next-Test Mapper
  8. Assess Gate
```

这样既不破坏大闭环的五步结构，又能让前两步真正可实现、可审计。

## 4. Explore 应该怎么拆

### 4.1 Scope Adapter

职责：把 seed question / seed claim / topic 变成探索规格。

它不是单独主链模块，而是 Explore 的输入适配层。

输入：

```text
阿司匹林对一级预防心血管疾病的作用
```

输出：

```json
{
  "kind": "exploration_scope",
  "question": "Aspirin for primary prevention of cardiovascular disease",
  "population": ["adults without established CVD"],
  "intervention_or_object": "aspirin",
  "comparators": ["placebo", "usual care", "no aspirin"],
  "outcomes": ["MI", "stroke", "mortality", "major bleeding"],
  "subgroups": ["older adults", "diabetes", "high ASCVD risk"],
  "decision_context": "clinical net benefit"
}
```

对哈勃常数张力，scope 会变成：

```json
{
  "kind": "exploration_scope",
  "quantity": "H0",
  "early_universe_inference": ["Planck CMB under Lambda-CDM", "BAO + BBN"],
  "late_universe_measurement": ["SH0ES", "TRGB", "strong lensing", "standard sirens"],
  "model_families": ["Lambda-CDM", "early dark energy", "modified gravity"],
  "assessment_dimensions": ["systematics", "model dependence", "global fit", "parameter degeneracy"]
}
```

### 4.2 Landscape Builder

职责：breadth-first 建立领域地图。

它应该做：

- query planning；
- 多 query 检索；
- 去重；
- paper / artifact-level 聚类；
- evidence family / model family 标注；
- 代表性材料排序；
- coverage map。

阿司匹林例子里，landscape 不应该一上来 pull 某篇 paper 的全部 claims，而应该先形成：

```json
{
  "kind": "landscape",
  "clusters": [
    {"type": "major_rct", "items": ["ASPREE", "ARRIVE", "ASCEND"]},
    {"type": "meta_analysis", "items": ["updated primary prevention meta-analysis"]},
    {"type": "guideline", "items": ["USPSTF", "ACC/AHA", "ESC"]},
    {"type": "subgroup", "items": ["diabetes", "older adults", "high ASCVD risk"]}
  ],
  "coverage": ["benefit", "harm", "mortality", "subgroups", "guidelines"]
}
```

哈勃张力例子里，landscape 应该是：

```json
{
  "kind": "landscape",
  "evidence_families": [
    "Planck CMB",
    "ACT/SPT",
    "BAO+BBN",
    "SH0ES Cepheids+SNe",
    "TRGB",
    "strong lensing",
    "standard sirens"
  ],
  "model_families": [
    "Lambda-CDM",
    "early dark energy",
    "modified gravity",
    "extra relativistic species"
  ]
}
```

### 4.3 Frontier / Obligation Mapper

职责：从 landscape 和当前 Gaia graph 中找值得后续分析的区域。

它输出的不是最终结论，而是 candidate focus：

```json
{
  "candidate_focuses": [
    {
      "kind": "tension",
      "text": "MI risk reduction vs no clear mortality benefit",
      "why_it_matters": "benefit signal may not translate into clinically decisive outcome"
    },
    {
      "kind": "tension",
      "text": "ischemic benefit vs major bleeding harm",
      "why_it_matters": "central benefit-harm tradeoff"
    },
    {
      "kind": "gap",
      "text": "individual net benefit depends on baseline CVD and bleeding risk",
      "why_it_matters": "bridges population evidence to recommendation"
    }
  ]
}
```

这一步是 `gaia-lkm-explore` 现有 frontier 的升级版：从 claim-level frontier 变成 landscape-aware frontier。

### 4.4 Explore Gate

Explore 结束时要过一个 gate，判断它是否适合交给 Assess。

Gate 不问“结论对不对”，只问：

- 是否覆盖主要 evidence/model family？
- candidate focuses 是否有 provenance？
- 是否区分了 paper-level landscape 和 claim-level details？
- 是否暴露了 candidate contradictions / gaps / obligations？
- 是否避免把 retrieval score 当作 confidence？

## 5. Explore 的 typed artifact

建议 `gaia-lkm-explore` 的输出不要只是 `.gaia/exploration/map.json`，而是补一个更清楚的 artifact：

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "lkm_exploration",
  "id": "explore-001",
  "inputs": {
    "seed": "...",
    "scope": {}
  },
  "artifacts": {
    "landscape": {},
    "candidate_focuses": [],
    "exploration_graph": ".gaia/exploration/map.json",
    "gaia_ir": ".gaia/ir.json",
    "beliefs": ".gaia/beliefs.json"
  },
  "audit": {
    "coverage": {},
    "known_limitations": [],
    "allowed_next_steps": ["assess"]
  }
}
```

这个 artifact 是 Explore 交给 Assess 的正式接口。

它同时是外部 agent harness 接 Gaia 的第一层稳定接口。外部 harness 可以负责
把用户目标、实验日志、Lab CLI 输出或人工决策整理成输入；Gaia 只承诺消费和
生产 typed artifacts。第一版必须优先稳定下面这些字段，而不是追求 retrieval
或 classification 算法一步到位：

- `schema` / `kind` / `id`：让外部系统能做版本判断和路由。
- `inputs`：记录 seed、scope、调用参数和上游来源。
- `artifacts`：只放可复现路径或结构化 payload，不放 prompt-only 状态。
- `provenance`：记录 query、LKM result、paper/artifact id、Gaia graph source。
- `audit`：记录 coverage、known limitations、gate status、allowed next steps。
- `interface`：记录下游可调用命令，例如 `gaia-evidence assess --exploration ...`。

因此第一版 artifact 可以比最终 schema 小，但不能是临时日志；它必须能被
`gaia-evidence assess`、脚本和未来 TUI 作为同一个 contract 使用。

## 6. Assess 应该怎么接

Assess 不应该重新从自然语言问题开始，也不应该直接吞完整 raw frontier。

它应该接收一个 focus：

```bash
gaia-evidence assess \
  --exploration ./topic-gaia/.gaia/exploration/artifact.json \
  --focus tension:<id> \
  --world graph-plus-lkm \
  --out ./runs/assess-001
```

也可以保留大文档里定义的 graph 入口：

```bash
gaia-evidence assess \
  --graph ./topic-gaia \
  --focus contradiction:<id> \
  --world graph-plus-lkm \
  --out ./runs/assess-001
```

关键是两种入口进入统一 context：

```json
{
  "origin": "lkm_exploration | seed_question | gaia_graph",
  "focus": {
    "kind": "claim | question | contradiction | gap | tension | graph_region",
    "id": "...",
    "text": "..."
  },
  "known_claims": [],
  "known_relations": [],
  "candidate_evidence": [],
  "open_obligations": [],
  "retrieval_boundary": {},
  "world_mode": "graph_only | graph_plus_lkm"
}
```

## 7. Assess 的职责边界

Assess 负责：

- 判断矛盾成因；
- 区分 support / oppose / limit / conditional / insufficient evidence；
- 识别 evidence coverage；
- 诊断 remaining gaps；
- 形成 next tests；
- 为 Propose 提供可执行的 gap。

Assess 不负责：

- 大规模开放探索；
- 直接执行实验；
- 直接回写 LKM；
- 把所有 raw claims 都 formalize 成 Gaia graph。

Assess 输出：

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "evidence_assessment",
  "id": "assess-001",
  "origin": "lkm_exploration",
  "focus": {},
  "evidence_pool": [],
  "contradiction_diagnosis": [],
  "gap_map": [],
  "next_tests": [],
  "promotion_suggestions": [],
  "audit": {
    "coverage": {},
    "known_limitations": [],
    "allowed_next_steps": ["propose"]
  }
}
```

这个输出正好进入大闭环的下一步：

```text
Assess -> Propose
```

## 8. 和 Propose / Discover / Merge 如何整合

前两步的目标不是直接产生 research proposal，而是给 `gaia-propose` 一个干净输入。

### Assess 到 Propose

`gaia-propose direction` 应该吃 assessment artifact：

```bash
gaia-propose direction \
  --assessment ./runs/assess-001 \
  --out ./runs/proposal-001
```

它关注：

- 哪个 gap 最值得研究；
- 最小判别实验 / 计算 / 分析是什么；
- 结果 A/B/C 分别会更新哪些 belief；
- stop condition 是什么。

### Propose 到 Discover

`gaia-discovery run` 执行 proposal：

```bash
gaia-discovery run \
  --proposal ./runs/proposal-001 \
  --mode manual-result | script-result | literature-result \
  --out ./runs/discovery-001
```

Explore/Assess 在这里的作用是减少无意义 proposal：proposal 必须来自被证据评估过的 gap。

### Discover 到 Merge

Discovery 产出的 result claims 经审计后 promote 回 Gaia：

```bash
gaia-discovery promote \
  --discovery ./runs/discovery-001 \
  --to-gaia ./topic-gaia

gaia-lkm-merge prepare \
  --package ./topic-gaia \
  --out ./runs/merge-001
```

Merge 的职责是更新 belief，并准备 LKM 回灌。Explore/Assess 只提供上游上下文，不直接 submit。

## 9. gaia-lkm-explore 具体如何改

我建议不要把 `gaia-lkm-explore` 改成大而全的 workbench。它仍然只负责 Explore，但 Explore 内部要更结构化。

### 保留现有能力

现有命令仍然有价值：

```bash
gaia-lkm-explore init
gaia-lkm-explore observe
gaia-lkm-explore frontier
gaia-lkm-explore turn
gaia-lkm-explore render
gaia-lkm-explore status
```

但 `turn` 不应永远是默认的第一动作。它更适合成为 targeted deep dive 的一种策略。

### 新增 Explore 层命令

建议新增：

```bash
gaia-lkm-explore scope ./topic-gaia --seed "..."
gaia-lkm-explore landscape ./topic-gaia --from-scope scope.json
gaia-lkm-explore focuses ./topic-gaia --from-landscape landscape.json
gaia-lkm-explore artifact ./topic-gaia
gaia-lkm-explore gate ./topic-gaia
```

语义：

- `scope`：生成或修订 exploration scope。
- `landscape`：breadth-first 建 evidence/model landscape。
- `focuses`：生成 candidate tensions / gaps / obligations as assessment focuses。
- `artifact`：导出标准 `lkm_exploration` artifact。
- `gate`：检查是否可以交给 `gaia-evidence assess`。

### 现有 frontier 如何融入

当前 frontier 不废弃，而是下沉为：

```bash
gaia-lkm-explore turn ./topic-gaia --focus <focus-id>
```

也就是：

```text
landscape-aware focuses
  -> selected focus
  -> targeted frontier expansion
  -> materialize relevant claims
```

这样 frontier expansion 不再盲目扩张，而是服务某个 focus。

## 10. 应用场景

### 医学证据综合：阿司匹林一级预防

Explore 建 landscape：

- RCT：ASPREE、ARRIVE、ASCEND；
- meta-analysis；
- guideline：USPSTF、ACC/AHA、ESC；
- subgroup：older adults、diabetes、高 ASCVD risk；
- benefit-harm model。

Explore 输出 focuses：

- MI 下降 vs mortality no clear benefit；
- ischemic benefit vs major bleeding harm；
- older adults harm signal vs selected subgroup benefit；
- population-level recommendation vs individualized net benefit。

Assess 接手其中一个 focus，例如：

```text
ischemic benefit vs major bleeding harm
```

Assess 输出：

- 证据是否一致；
- 哪些人群适用；
- harm/benefit magnitude；
- 剩余 gap；
- 是否需要个体化 benefit-harm model。

然后 Propose 才提出下一步研究任务。

### 数学物理理论问题：哈勃常数张力

Explore 建 landscape：

- early universe: Planck CMB、ACT/SPT、BAO+BBN；
- late universe: SH0ES、TRGB、strong lensing、standard sirens；
- model families: Lambda-CDM、early dark energy、modified gravity、N_eff。

Explore 输出 focuses：

- Planck inferred H0 vs SH0ES local H0；
- Cepheid ladder vs TRGB ladder；
- new physics vs local systematics；
- H0 improvement vs S8/BAO/CMB side effects。

Assess 接手其中一个 focus，例如：

```text
early dark energy can reduce H0 tension without degrading global fit
```

Assess 评估：

- fit improvement；
- Bayesian evidence；
- BAO/SNe compatibility；
- S8 side effects；
- parameter degeneracy；
- fine-tuning；
- independent predictions。

### 工程技术选型

Explore 建 landscape：

- docs；
- benchmarks；
- GitHub issues；
- case studies；
- pricing；
- integration constraints。

Explore 输出 focuses：

- latency vs cost；
- maturity vs flexibility；
- cloud lock-in vs self-hosting；
- feature richness vs operational complexity。

Assess 评估具体 focus，例如：

```text
self-hosted option reduces vendor lock-in but increases operational burden
```

然后 Propose 可以产出最小 PoC 或 benchmark plan。

## 11. Gaia Research Loop Core MVP

最小版本不要一次做完整闭环，也不要先做外层 agent 产品。第一阶段只做
Gaia/LKM 后端协议和前两步能力，让外部 agent 或人类用户能按同一条命令链调用。

MVP 名称：

```text
Gaia Explore/Assess Artifact MVP
```

MVP 命令链：

```bash
gaia-lkm-explore scope ./topic-gaia --seed "..."
gaia-lkm-explore landscape ./topic-gaia
gaia-lkm-explore focuses ./topic-gaia
gaia-lkm-explore artifact ./topic-gaia
gaia-lkm-explore gate ./topic-gaia

gaia-evidence assess \
  --exploration ./topic-gaia/.gaia/exploration/artifact.json \
  --focus tension:<id> \
  --out ./runs/assess-001
```

MVP 交付物：

- `exploration_scope.json`
- `landscape.json`
- `candidate_focuses.json`
- `lkm_exploration.artifact.json`
- `explore_gate_report.json`
- `assessment_context.json`
- `evidence_assessment.artifact.json`
- 一份 “external agent integration” 文档，说明外部 harness 只需调用哪些命令、读写哪些 artifact。

不在 MVP 范围内：

- 自研 TUI / desktop / VSCode plugin；
- 公司级 auth、telemetry、灰度发布和发包系统；
- Lab CLI scaffold 和真实实验设备接入；
- 自动执行实验或自动回写 LKM；
- 完整的 `Propose -> Discover -> Merge` 实现。

这些能力属于 Scientific Agent harness 或后续 Gaia 阶段。MVP 只保证：一个
agent 可以把 Gaia 当作 research loop backend 调用。

## 12. 实现路线

### Phase 0: 固定 artifact contract

先实现 schema 和读写位置，不追求算法完美：

```text
.gaia/exploration/scope.json
.gaia/exploration/landscape.json
.gaia/exploration/focuses.json
.gaia/exploration/artifact.json
.gaia/exploration/gate_report.json
runs/<id>/assessment_context.json
runs/<id>/assessment.artifact.json
```

contract 必须包含：

- `schema` / `kind` / `id`；
- `inputs` / `provenance`；
- `artifacts`；
- `audit.coverage` / `audit.known_limitations` / `audit.allowed_next_steps`；
- gate status 和人类可读的 failure reasons。

### Phase 1: Instrument 当前 explore

在现有 `gaia-lkm-explore` 上补齐可复现记录：

- query plan；
- raw hits；
- unique papers；
- pulled papers；
- generated claims；
- selected root claims；
- frontier size；
- active time；
- user decisions；
- failure / timeout。

目的：让 artifact 的 provenance 有真实来源，也量化检索效率、claim 转化率和
frontier 噪声。

### Phase 2: 做 breadth-first landscape

实现：

- 从 scope 生成 query plan；
- 每个 query 拉 top-k；
- paper/artifact 去重；
- evidence/model family 分类；
- 输出 landscape；
- 暂时不 deep pull。

这一步的成功标准是 paper/artifact-level landscape，而不是 claim-level 深挖。

### Phase 3: 做 focuses / obligation mapper

从 landscape 和已有 Gaia graph 生成：

- candidate tensions；
- gaps；
- open obligations；
- recommended assessment focuses。

初期可以 LLM-assisted，后面加 domain templates。每个 focus 必须带 provenance，
不能只是自然语言猜测。

### Phase 4: 打通 Assess handoff

让 `gaia-evidence assess` 能吃：

```bash
--exploration lkm_exploration.artifact.json
--focus <focus-id>
```

并生成标准 assessment context，再输出 `evidence_assessment.artifact.json`。
第一版 assessment 可以是 conservative summary + gap/next-test mapper，不需要
一次完成完整 scientific reviewer。

### Phase 5: 把现有 turn 改成 focus-aware

支持：

```bash
gaia-lkm-explore turn ./topic-gaia --focus <focus-id>
```

这样 deep dive 服务某个 focus，而不是在全局 frontier 里漂移。

## 13. MVP 验收标准

- Explore 能生成 paper/artifact-level landscape。
- Explore 能暴露 candidate tensions/gaps，并为每个 focus 记录 provenance。
- `gaia-lkm-explore gate` 能判断 artifact 是否足够交给 Assess。
- Assess 能消费 focus，而不是从头搜。
- Assess 能输出 `gap_map` / `next_tests`，供 Propose 使用。
- 外部 agent 可以只靠命令链和 artifact contract 接入，不需要理解 Gaia 内部数据结构。

## 14. 一句话定位

这份 proposal 是大闭环：

```text
Explore -> Assess -> Propose -> Discover -> Merge
```

中前两步的细化设计，也是 Gaia 侧可独立开发的 Research Loop Core MVP。

它建议把 `gaia-lkm-explore` 定位为真正的 Explore 模块：负责建立 landscape、暴露 focuses（分析焦点）、生成 typed exploration artifact；把 Evidence Assessment 定位为第二步：负责围绕 focus 诊断证据、解释矛盾、生成 gap_map 和 next_tests。

这样后面的 Propose / Discover / Merge 就不再面对散乱搜索结果，而是面对经过 Explore 和 Assess 整理过的、可审计的研究问题；未来外部 Scientific Agent CLI/TUI 也可以把 Gaia 当作稳定 research backend，而不是侵入 Gaia 内部实现。
