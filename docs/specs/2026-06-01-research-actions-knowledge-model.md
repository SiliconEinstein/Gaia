# Research Actions Knowledge Model

> **状态：** Historical / prior-art knowledge-model note。它仍可用于理解
> focus、obligation、assessment relation 和 stable Gaia source 的分层，但不再是
> 当前 canonical split target。
>
> **日期：** 2026-06-01
>
> **当前 canonical 验收标准：**
> [Research Module Split Acceptance](2026-06-13-research-module-split-acceptance.md)
>
> **Prior-art overview：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)

## 1. 为什么需要这份说明

> **2026-06-13 correction:** 本文的概念分层仍然有效；实现 ownership 已经改变。
> 上层 research workflow 应迁到 `gaia-research`，Gaia core 只保留 primitives 和
> stable package semantics。

`gaia research` 的核心风险不是命令怎么拼，而是把不同层级的研究对象混成一种
`claim(...)`。这会让 open question、process obligation、assessment judgment 和 stable
truth-bearing knowledge 全部挤进同一个语义层，后续 BP、review、promotion 都会变脏。

这份 note 固定四个层级：

```text
question / focus      = open inquiry lens
claim                 = truth-bearing proposition
obligation            = process requirement
assessment relation   = interpretive relation over existing evidence
formal relation       = compiled Gaia DSL relation
```

## 2. Focus 通常是 Question，不是 Claim

Research focus 通常是在问一个 field-facing 问题，而不是断言一个命题为真。

例如 deconfined criticality 的核心 focus 可以是：

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

Focus 本身不应该参与 true / false 判断。真正 truth-bearing 的是 candidate answer
claims：

```python
dqcp_continuous = claim("The Neel-VBS transition realizes a continuous DQCP.")
dqcp_weakly_first_order = claim("The Neel-VBS transition is weakly first-order.")
dqcp_walking = claim("The observed scaling is pseudo-critical walking behavior.")
```

因此 package model 应该是：

```text
Question / Focus
  targets Candidate Answer Claims
    supported / opposed / qualified by Evidence Claims
```

如果 Explore 只发现了一个 focus，但 answer claims 还没有准备好，它应该先存在于
inquiry state 或 `.gaia/research/explore/` artifact。用户接受后，再 promotion 成
`question(...)`。Answer claims 可以稍后补。

## 3. Obligation 是过程知识

Obligation 表达“接下来必须检查、证明、补证据、澄清边界的事情”。它不是 stable truth
claim。

默认位置应该是 inquiry state：

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

部分 obligation 未来可以 promotion 成 `question(...)`，但不是每个临时 obligation 都应该
写进 package source。

## 4. Assessment Relation 不是 Formal Relation

当前 Gaia DSL relation verbs 语义很强：

- `derive(conclusion, given=...)` 是 formal support step；
- `infer(evidence, hypothesis=...)` 是 probabilistic evidence model；
- `contradict(a, b)` 是 claim truth values 之间的 hard relation；
- `exclusive(a, b)` 是 closed partition / complement-style relation。

Assess 阶段需要更宽、更解释性的关系词表：

| Assessment relation | 含义 | 默认处理 |
| --- | --- | --- |
| `supports` | evidence favor 某个 answer claim | artifact-level；formalized 后才可能是 `derive` / `infer` |
| `opposes` | evidence count against 某个 answer claim | artifact-level；只有 hard conflict 才可能是 `contradict` |
| `qualifies` | evidence 缩小适用边界 | artifact-level；必要时形成 narrower claim |
| `undercuts` | evidence 削弱方法、假设或 inference route | artifact-level 或 obligation |
| `background_for` | 提供上下文，不直接支持 | artifact-level；必要时另写 `note(...)` |
| `needs_more_evidence` | gap 未解决 | candidate inquiry obligation |

Promotion 是显式动作，不是 assessment artifact 的默认副作用。

## 5. LKM Evidence 的 Promotion

当 assessment relation 的 source refs 来自 LKM 时，`promotion_hint` 只是可能的下游形态。
真正写入 `src/<pkg>/...` 前，必须经过 LKM-to-DSL mapping contract：

- raw LKM payload 是 science-facing source of truth；
- chain-backed claim 和 no-chain source claim 要区分；
- 不编造 synthetic bridge facts；
- support 用 `derive(...)` 或 `infer(...)`；
- adjudicable contradiction 才能进入 `contradict(...)`；
- LKM provenance 必须保留；
- duplicate / shared-factor 风险要显式检查。

这个 contract 目前由 `$lkm-explorer` skill 维护。`gaia research` 后续如果实现 promotion
command，应该吸收这套 mapping discipline，而不是另造一套规则。
