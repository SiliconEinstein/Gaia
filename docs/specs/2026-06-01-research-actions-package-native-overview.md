# Gaia Research Actions Package-Native Overview

> **状态：** `gaia research` 方向的 canonical overview。
>
> **日期：** 2026-06-01
>
> **实现路线图：**
> [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md)
>
> **迁移说明：**
> [Research Actions Migration Notes](2026-06-01-research-actions-migration-notes.md)
>
> **知识模型说明：**
> [Research Actions Knowledge Model](2026-06-01-research-actions-knowledge-model.md)

## 1. 核心判断

Research Loop 不应该成为 Gaia package 旁边的第二套长期系统。它应该成为
package-native 的 research action layer：

```text
Gaia package = 长期研究工作区 + 沟通 contract
Gaia CLI primitives = package / inquiry / authoring / build 的 source of truth
gaia research = Gaia primitives 之上的薄编排层
LLM / agent = 研究判断层，不维护平行状态系统
```

canonical user / agent surface 是：

```bash
gaia research explore ...
gaia research assess ...
gaia research propose ...
```

旧 `gaia-lkm-explore` 可以作为实验入口或兼容参考存在，但不能作为当前实现锚点；
不再维护独立的 in-repo `gaia-research-loop` skill 作为 workflow surface。

## 2. Package-Native 状态

Research actions 通过普通 Gaia package 沟通：

```text
<topic>-gaia/
  src/<topic>/...        stable formal source
  .gaia/inquiry/...      focus、obligation、hypothesis、review state
  .gaia/lkm_packages/... pulled LKM paper packages
  .gaia/research/...     landscape、assessment、proposal artifacts
```

`.gaia/research/` 是 artifact、provenance、audit layer。它不是第二套语义 source of
truth。

被接受的语义状态应该落在已有 Gaia 概念中：

- accepted focus：`gaia inquiry focus` 或 package `question(...)`；
- accepted obligation：`gaia inquiry obligation`；
- stable truth-bearing knowledge：package `claim(...)`；
- formal support / contradiction：`derive(...)`、`infer(...)`、`contradict(...)`
  或相关 Gaia DSL primitive。

## 3. Action 边界

### Explore

Explore 负责建立 literature / evidence landscape。

早期 Explore 必须 breadth-first、低成本。第一目标不是选出 top paper，而是摊开 field
结构：

- query families；
- paper / claim / method clusters；
- coverage dimensions；
- major schools 或 model families；
- known controversies；
- under-covered regions；
- candidate focuses 和 obligations。

`explore --mode scan` 默认 pull budget 为 0。它不应该强迫 agent 选择 top-1 / top-3
paper，不应该把 frontier ranking 当作完成标准，也不应该写 stable claims。

### Assess

Assess 固定一个 focus 或 obligation，围绕它评估现有 evidence。

它产出 assessment artifacts、evidence packets、tensions、confidence notes、
limitations 和 candidate obligations。默认不写 stable source claims。

第一版 assessment relation vocabulary 只停留在 artifact-level：

```text
supports
opposes
qualifies
undercuts
background_for
needs_more_evidence
```

`promotion_hint` 可以提示未来 Gaia 形式，但不能自动授权写 source。

### Propose

Propose 把 assessed gaps 转成 open-ended research questions、hypotheses、
experiments、simulations、proofs、benchmarks 或 research tasks。

默认只写 proposal artifacts。`--accept` 可以写 inquiry state 或 package questions，
但不能写 stable truth claims。

### Merge

Merge 不在本设计范围内。它应该发生在 discovery / research 真的产生新结果之后。

## 4. 硬性不变量

后续实现 PR 必须保留这些 invariants：

1. `.gaia/research/` 不是 canonical focus registry。
2. `.gaia/research/` 不是 canonical obligation ledger。
3. Explore、Assess、Propose 默认不写 stable claims。
4. Research artifacts 尽量引用 Gaia-native identifiers：QIDs、obligation ids、
   LKM paper ids、pulled package names、source paths、content hashes。
5. `gaia build check` 仍然是 package structural validation path。
6. Broad `explore --mode scan` 必须 breadth-first、field-coverage oriented，且默认
   pull budget 为 0。
7. Assessment artifacts 必须携带 epistemic status，不能被 flatten 成 paper claims 或
   discovery claims。

## 5. 复用已有 Primitive

`gaia research` 应该组合已有 Gaia CLI primitives：

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

如果某个 research action 需要 Gaia CLI 当前表达不了的能力，优先补底层 Gaia
primitive，而不是在 `gaia research` 里藏第二套语义实现。

## 6. 本文范围

这份 overview 是当前架构锚点。细节分流到两个 companion docs：

- focus / obligation / assessment relation 的知识模型：
  [Research Actions Knowledge Model](2026-06-01-research-actions-knowledge-model.md)；
- 旧系统关系和迁移取舍：
  [Research Actions Migration Notes](2026-06-01-research-actions-migration-notes.md)；
- 实现切片和验证方式：
  [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md)。
