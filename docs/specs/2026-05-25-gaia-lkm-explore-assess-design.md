# Gaia LKM Explore and Evidence Assess Design

> **Status:** Draft
>
> **Date:** 2026-05-25
>
> **Scope:** `gaia-lkm-explore`, its handoff to `gaia-evidence assess`,
> and the first two stages of the larger Gaia research loop:
> `Explore -> Assess -> Propose -> Discover -> Merge`.

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
  "candidate_foci": [
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
- candidate foci 是否有 provenance？
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
    "candidate_foci": [],
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
  "kind": "evidence_assessment",
  "origin": "lkm_exploration",
  "focus": {},
  "evidence_pool": [],
  "contradiction_diagnosis": [],
  "gap_map": [],
  "next_tests": [],
  "promotion_suggestions": [],
  "audit": {}
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
gaia-lkm-explore foci ./topic-gaia --from-landscape landscape.json
gaia-lkm-explore artifact ./topic-gaia
gaia-lkm-explore gate ./topic-gaia
```

语义：

- `scope`：生成或修订 exploration scope。
- `landscape`：breadth-first 建 evidence/model landscape。
- `foci`：生成 candidate tensions / gaps / obligations。
- `artifact`：导出标准 `lkm_exploration` artifact。
- `gate`：检查是否可以交给 `gaia-evidence assess`。

### 现有 frontier 如何融入

当前 frontier 不废弃，而是下沉为：

```bash
gaia-lkm-explore turn ./topic-gaia --focus <focus-id>
```

也就是：

```text
landscape-aware foci
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

Explore 输出 foci：

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

Explore 输出 foci：

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

Explore 输出 foci：

- latency vs cost；
- maturity vs flexibility；
- cloud lock-in vs self-hosting；
- feature richness vs operational complexity。

Assess 评估具体 focus，例如：

```text
self-hosted option reduces vendor lock-in but increases operational burden
```

然后 Propose 可以产出最小 PoC 或 benchmark plan。

## 11. 最小实现路线

### Phase 0: Instrument 当前 explore

先补齐当前流程记录：

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

目的：量化检索效率、claim 转化率、frontier 噪声。

### Phase 1: 定义 Explore artifact schema

先实现：

```text
exploration_scope.json
landscape.json
candidate_foci.json
lkm_exploration.artifact.json
explore_gate_report.json
```

这些 contract 比算法更重要。

### Phase 2: 做 breadth-first landscape

实现：

- 从 scope 生成 query plan；
- 每个 query 拉 top-k；
- paper/artifact 去重；
- evidence/model family 分类；
- 输出 landscape；
- 暂时不 deep pull。

### Phase 3: 做 foci / obligation mapper

从 landscape 和已有 Gaia graph 生成：

- candidate tensions；
- gaps；
- open obligations；
- recommended assess foci。

初期可以 LLM-assisted，后面加 domain templates。

### Phase 4: 打通 Assess handoff

让 `gaia-evidence assess` 能吃：

```bash
--exploration lkm_exploration.artifact.json
--focus <focus-id>
```

并生成标准 assessment context。

### Phase 5: 把现有 turn 改成 focus-aware

支持：

```bash
gaia-lkm-explore turn ./topic-gaia --focus <focus-id>
```

这样 deep dive 服务某个 focus，而不是在全局 frontier 里漂移。

## 12. MVP

最小版本不要一次做完整闭环。

只做前两步的接口打通：

```text
gaia-lkm-explore landscape
gaia-lkm-explore foci
gaia-lkm-explore artifact
gaia-evidence assess --exploration ... --focus ...
```

验收标准：

- Explore 能生成 paper/artifact-level landscape。
- Explore 能暴露 candidate tensions/gaps。
- Assess 能消费 focus，而不是从头搜。
- Assess 能输出 gap_map / next_tests，供 Propose 使用。

## 13. 一句话定位

这份 proposal 是大闭环：

```text
Explore -> Assess -> Propose -> Discover -> Merge
```

中前两步的细化设计。

它建议把 `gaia-lkm-explore` 定位为真正的 Explore 模块：负责建立 landscape、暴露 foci、生成 typed exploration artifact；把 Evidence Assessment 定位为第二步：负责围绕 focus 诊断证据、解释矛盾、生成 gap_map 和 next_tests。

这样后面的 Propose / Discover / Merge 就不再面对散乱搜索结果，而是面对经过 Explore 和 Assess 整理过的、可审计的研究问题。
