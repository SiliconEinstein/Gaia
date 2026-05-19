# Gaia Jaynes Context 与 Review Packet 设计草案

日期：2026-05-17

状态：草案

## 目标

这份文档先定义 Jaynes robot 使用的 `ContextPacket`，再在它的基础上定义
review 的显示格式。

核心判断是：review report 难懂，并不是因为缺少一个更复杂的 review 命令，
而是因为还没有一个稳定的、面向 agent 的上下文切片格式。review 应该复用这
个上下文，而不是自己重新从 reasoning graph 里拼 narrative。

## 第一性原理

Jaynes robot 做的是条件化推理：

```text
P(H | I)
```

这里的 `I` 是条件化信息。它不是概率结果，不是审稿意见，也不是提示词建议。
在 Gaia 里，`I_agent` 应该是从完整内部状态 `I_robot_internal` 中切出来的
一个可读、可遍历、以 focus 为中心的上下文包。

所以：

- `context` 负责告诉 agent：理解这个 focus 时应该看哪些文本和结构。
- `infer` 负责基于图和参数更新 belief。
- `review` 负责基于 context 和 audit question 做接受、拒绝或要求补充输入。

## 核心直觉

每一个 reviewable target 背后都有一个共同形态：

```text
conclusion ~= nontrivial inputs + background + rationale + LLM/common-sense bridge
```

作者在 Python DSL 里已经写了若干重要文字：

- claim/note/question 的 label 和 content
- strategy/operator/action 的 inputs
- `background`
- `rationale`

Jaynes context 的职责，是把这些已经存在的材料忠实展开，让 agent 能理解这个
结论为什么被提出，以及它依赖哪些直接材料。

## 非目标

`ContextPacket` 默认不包含：

- prior、posterior、belief 或任何概率状态
- review question
- failure modes
- "what to understand"
- "possible ambiguities"
- 自动生成的大段解释性 narrative
- 从所有 root 到 focus 的完整 path 枚举

这些属于其他层。

如果某个下游任务需要它们，应该显式叠加：

```text
review packet = context packet + audit question + decision schema
inference view = context reference + belief state
reading guide = context packet + optional human/agent guide
```

## 基本对象

### Focus

当前 agent 要理解的对象。它可以是：

- claim
- relation/operator 产生的 conclusion
- strategy/action 产生的 conclusion
- compose workflow 的 output
- review target 指向的 action、strategy、operator、knowledge 或 compose

Focus 必须有机器可定位的 identity，也必须有人/agent 可读的文本。

### Incoming Channel

Incoming channel 是直接通向 focus 的一个 load-bearing 入口。

它不是 root-to-focus path。它是 focus 的直接来源，例如：

- `derive(A, B -> C)`
- `equal(D, E -> C)`
- `contradict(D, E -> C)`
- `observe(source -> C)`
- `compute(inputs -> C)`
- `infer(model, data -> likelihood/update target)`
- `compose(actions -> C)`

一个 focus 可以有多个 incoming channels。context 默认列出这些 channel，
而不递归展开每个 input 的完整祖先图。

### Boundary Node

Boundary node 是 incoming channel 的 input 或 frontier 节点。context 会给出
它的 label、kind、content 和可展开引用，但默认不继续展开它的上游。

这避免 DAG path 爆炸。

### Shared Background

多个 incoming channels 共享的背景信息应当单独列出，避免在每条 channel 中
重复出现，让 agent 误以为这些是独立证据。

### Rationale

`rationale` 是作者在 DSL 里写出的桥接推理。它属于 context，因为它是 `I_agent`
的一部分。

`rationale` 不是 review 结果，也不是系统自动替作者补充的解释。review 可以质疑
它，但不应把质疑内容混进 context。

## ContextPacket 字段

最小结构如下：

```yaml
focus:
  label: string
  kind: claim | relation | strategy | action | compose | knowledge | operator
  content: string
  target_id: string | null
  source_ref: string | null

incoming_channels:
  - index: integer
    kind: derive | equal | contradict | exclusive | observe | compute | infer | compose | other
    label: string | null
    target_kind: string | null
    target_id: string | null
    action_label: string | null
    conclusion:
      label: string
      content: string
    inputs:
      - label: string
        kind: claim | note | question | setting | other
        content: string
    background:
      - label: string
        kind: note | claim | other
        content: string
    rationale: string | null

boundary_nodes:
  - label: string
    kind: claim | note | question | setting | other
    content: string
    expand_ref: string

shared_background:
  - label: string
    kind: note | claim | other
    content: string

downstream:
  - label: string
    kind: claim | relation | action | other
    content: string | null
    expand_ref: string
```

实现可以先只支持 Markdown 渲染，但内部最好保留结构化对象，方便后续 JSON 输出
和 agent 调用。

## Markdown 渲染格式

默认渲染应尽量朴素，不做解释性发挥。

```md
# Context: <focus-label>

## Focus

label: <focus-label>
kind: <kind>
target_id: <target-id-if-any>

content:
  <focus content>

## Incoming Channels

### [1] <channel-kind>

label: <channel label if any>
target_kind: <target kind if any>
target_id: <target id if any>
action_label: <action label if any>

conclusion:

- label: <conclusion label>
  kind: <kind>
  content:
    <conclusion content>

inputs:

- label: <input label>
  kind: <kind>
  content:
    <input content>

background:

- label: <background label>
  kind: <kind>
  content:
    <background content>

rationale:
  <author-written rationale>

## Boundary Nodes

### <boundary label>

kind: <kind>
content:
  <content>

expand:
  gaia context show <boundary label>

## Shared Background

### <background label>

kind: <kind>
content:
  <content>

## Downstream

- label: <downstream label>
  kind: <kind>
  expand: gaia context show <downstream label>
```

## Mendel 示例

以下示例只展示 context，不展示概率，也不展示 review question。

```md
# Context: f2_discrete_classes_mendel_match

## Focus

label: f2_discrete_classes_mendel_match
kind: relation
operator: equal
target_id: lco_101ddd4338122eb4

content:
  孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。

## Incoming Channels

### [1] equal

target_kind: operator
target_id: lco_101ddd4338122eb4
action_label: example:mendel_v0_5::action::f2_discrete_classes_mendel_match

conclusion:

- label: f2_discrete_classes_mendel_match
  kind: claim
  content:
    孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。

inputs:

- label: mendel_predicts_discrete_classes
  kind: claim
  content:
    孟德尔模型预言 F2 会出现显性和隐性两个离散表型类别。

- label: f2_has_discrete_classes_observation
  kind: claim
  content:
    F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。

background:

- label: monohybrid_cross_setup
  kind: note
  content:
    单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，
    另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。

- label: dominance_background
  kind: note
  content:
    在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。

rationale:
  孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。

## Boundary Nodes

### mendel_predicts_discrete_classes

kind: claim
content:
  孟德尔模型预言 F2 会出现显性和隐性两个离散表型类别。

expand:
  gaia context show mendel_predicts_discrete_classes

### f2_has_discrete_classes_observation

kind: claim
content:
  F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。

expand:
  gaia context show f2_has_discrete_classes_observation

## Shared Background

### monohybrid_cross_setup

kind: note
content:
  单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，
  另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。

### dominance_background

kind: note
content:
  在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。
```

## Context 与 Review 的关系

Review 不重新发明上下文。Review packet 应该是：

```text
ReviewPacket = ReviewTarget metadata + audit_question + ContextPacket + decision block
```

其中：

- `ReviewTarget metadata` 来自 `ReviewManifest`
- `audit_question` 来自 warrant/review template
- `ContextPacket` 来自 focus-centered context generator
- `decision block` 是 reviewer 写回的 judgement

### Review Markdown 格式

```md
# Review: <target label>

## Target

review_id: <review id>
status: unreviewed
target_kind: <target kind>
target_id: <target id>
action_label: <action label>

## Audit Question

<audit question>

## Context

<embedded ContextPacket or link to generated context file>

## Decision

status: accepted | rejected | needs_inputs

notes:
  <reviewer notes>
```

## `gaia review list`

`list` 应该是 review queue，不是 raw warrant dump。它展示压缩 context：

```text
[unreviewed] f2_discrete_classes_mendel_match
target: operator lco_101ddd4338122eb4

question:
  Are [@mendel_predicts_discrete_classes] and
  [@f2_has_discrete_classes_observation] truly equivalent?

focus:
  孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。

inputs:
  - mendel_predicts_discrete_classes:
    孟德尔模型预言 F2 会出现显性和隐性两个离散表型类别。
  - f2_has_discrete_classes_observation:
    F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。

show:
  gaia review show f2_discrete_classes_mendel_match
```

这比只显示 label 更适合 agent review。

## CLI 最小形态

建议先实现四个入口：

```text
gaia context show <focus>
gaia context show <focus> --format json
gaia review list [path]
gaia review show <target>
```

后续再实现写回：

```text
gaia review accept <target> --notes "..."
gaia review reject <target> --notes "..."
gaia review needs-inputs <target> --notes "..."
```

`gaia build check --warrants` 可以保留为兼容和调试入口，但不应继续作为主入口。

## Label 歧义

label 不是稳定唯一身份。比如同一个 action label 可能对应多个 strategy review target。

因此所有可写回的 review 操作必须解析到：

```text
(action_label, target_kind, target_id)
```

如果用户输入的 label 有歧义，CLI 应列出候选：

```text
Ambiguous target: mendel_count_likelihood

[1] strategy lcs_662f92cb0e218f89
    action_label: example:mendel_v0_5::action::mendel_count_likelihood

[2] strategy lcs_1ab76e14b2f2ec26
    action_label: example:mendel_v0_5::action::mendel_count_likelihood

Use:
  gaia review show lcs_662f92cb0e218f89
```

## 实现边界

第一版不要实现复杂 narrative engine。

第一版只需要：

1. 从 IR 中找到 focus object。
2. 找到直接 incoming channels。
3. 收集 channel 的 inputs、background、rationale。
4. 把 inputs 作为 boundary nodes。
5. 对重复 background 去重。
6. 渲染 Markdown。
7. 为 agent 保留 JSON 输出。

不要：

- 枚举所有 root-to-focus paths
- 自动生成科学解释
- 混入 belief state
- 把 review failure modes 塞进 context
- 为每种 action 设计完全不同的格式

## 验收标准

一个好的 `ContextPacket` 应该满足：

- agent 不需要再解析 label 才能知道 focus 和 inputs 的实际内容。
- context 里有 DSL 作者写下的 `rationale`。
- context 不包含概率输出。
- context 不包含 review judgement。
- 多个 incoming channels 不被揉成一条 narrative。
- DAG 不会因为 path 枚举而爆炸。
- 每个 boundary node 都有可展开引用。
- review 能在 context 之上自然叠加 audit question 和 decision。

## 未决问题

1. `Focus` 是只允许 claim/review target，还是允许任意 IR node？
2. downstream 默认展示几层？第一版可以只展示直接 downstream 或完全不展示。
3. shared background 的去重规则用 label、id，还是内容 hash？
4. context 文件是否应该落盘，还是只按需渲染？
5. review report 是否内嵌 context，还是引用一个 context artifact？

第一版建议选择最小路线：

```text
Focus = claim label or review target
downstream = omitted by default
dedupe = id/label based
context = rendered on demand
review show = embed context
```
