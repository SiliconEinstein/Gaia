# Gaia 中的 Contradiction 处理

| 文档属性 | 值 |
|---------|---|
| 状态 | Draft |
| 日期 | 2026-03-08 |
| 关联文档 | [../../design/theoretical_foundations.md](../../design/theoretical_foundations.md), [probabilistic-semantics.md](probabilistic-semantics.md) |

---

## 1. 目的

本文给出 Gaia 中 `contradiction` 的推荐设计，目标是同时满足：

- 与 Jaynes 的 plausible reasoning 一致
- 与 BP / factor graph 的数学语义一致
- 与 Gaia 的 review / publish / LKM 流程一致
- 避免把“互斥约束”“显式矛盾对象”“撤回动作”混成一个 edge type

核心结论先写在前面：

> `contradiction` 在 BP 核心层应优先建模为 **headless exclusion factor**。  
> 显式“矛盾存在”对象属于 **review / diagnostic artifact**。  
> `retraction` 应是 **候选动作或显式动作**，而不是 contradiction 的自动副作用。

---

## 2. 问题定义

在一个科学知识系统里，发现矛盾并不自动回答下面三个问题：

1. 哪两个命题不能同时为真？
2. 这个矛盾是否足够强，值得写进审计结论？
3. 最终应该撤回哪个 claim、哪个 edge，还是应该补充 context？

这三件事必须分开。

如果把它们全部塞进一条 `contradiction` edge，就会出现两类设计混乱：

- **BP 语义混乱**：同一个 factor 既想做联合概率惩罚，又想支持一个显式 head 节点
- **产品语义混乱**：系统一旦发现冲突，就被迫自动决定“该怪谁”

Jaynes 的处理方式更保守，也更适合 Gaia：

> 发现矛盾，首先意味着学到一个新的联合约束：  
> `P(A ∧ B | I)` 很小。  
> 它不直接意味着 `A` 假、`B` 假，或某个上游 premise 一定假。

这就是 Gaia 里 contradiction 的正确起点。

---

## 3. 推荐的三层语义

### 3.1 BP 核心层：headless exclusion factor

在 BP 图里，`contradiction` 应默认表示：

```text
not all tails can be true at the same time
```

对 tail 集合 `T = {t1, t2, ..., tn}`，推荐势函数：

```text
phi(T) = 1      if not all tails are true
phi(T) = ε      if all tails are true
```

其中：

- `ε` 很小，表示联合状态高度不可信
- 可由 edge probability 导出，例如 `ε = 1 - p`
- `p` 越高，all-tails-true 的惩罚越强

这对应 Jaynes 的说法：

```text
P(t1 ∧ t2 ∧ ... ∧ tn | I) ≈ 0
```

这样的好处很明确：

- 概率语义简单
- backward inhibition 是自然出现的，不需要额外 hack
- prior 弱、证据少、结构支撑少的前提会先下降
- 完全符合 “weaker evidence yields first”

更重要的是，这个层面不需要回答“到底谁错了”。

### 3.2 Review 层：contradiction report / diagnostic artifact

用户和 reviewer 通常仍然需要一个显式对象来记录：

- 哪些命题冲突
- 冲突发生在什么 context
- 冲突强度如何
- 有哪些共同上游支持
- 哪些对象最值得复查

这时应生成一个 **diagnostic artifact**，例如：

```text
contradiction_report:
  conflicting_claims: [A, B]
  context: Ctx
  strength: 0.93
  shared_supports: [H1, H2]
  suggested_actions: [...]
```

这个对象属于：

- review sidecar
- audit report
- server-side integration metadata

它不应该和 BP 的 exclusion factor 绑死成同一个对象。

如果 Gaia authoring 层想保留 `tied_balls_contradiction` 这类“显式矛盾命题”，更稳的做法也不是让同一个 factor 同时承担两种职责，而是：

- 图里保留 headless contradiction factor
- review 另外生成一个“矛盾成立”的诊断对象

### 3.3 Resolution 层：retraction candidate，而不是自动 retraction

矛盾出现后，下一步不应直接是：

```text
contradiction -> retract(shared premise)
```

更合理的流程是：

1. contradiction factor 降低“联合同真”的概率
2. review 利用 provenance / shared support tracing 找候选责任源
3. 系统生成 `retraction candidates`
4. reviewer 或作者决定：
   - retract 某个 claim
   - retract 某条 inference edge
   - weaken 一个 claim
   - 增加新的 context / setting
   - 保留 tension，暂不裁决

所以 `retraction` 应在 Gaia 中保持为：

- 显式动作
- 或经 review 确认后的候选动作

而不是 contradiction 的自动副作用。

---

## 4. 为什么不建议让 contradiction 默认带 head

一个带 head 的 contradiction factor 试图同时表达：

1. `A` 和 `B` 不能同真
2. “矛盾存在”这个结论节点 `C` 应上升

这两个目标不天然冲突，但放进同一个 potential 里会让语义变得很难稳定：

- tail 惩罚希望 `all tails = true` 的联合质量被压低
- head 确认希望 `C = 1` 的概率被抬高
- 当 `p -> 1` 时，前者会把联合质量压到接近 0，后者却又想从这个状态里提取“矛盾已经成立”的质量

这就是为什么“contradiction head 是否单调上升”会变成一个很脆弱的问题。

从系统分层看，更自然的拆法是：

- **exclusion**：属于概率图
- **diagnostic conclusion**：属于 review 报告

也就是说：

```text
BP handles incompatibility.
Review handles explanation.
```

---

## 5. Prior 的契约：Cromwell 规则与 hard conflict

Jaynes 的 Cromwell 规则给了 Gaia 一个很重要的约束：

> 对经验命题，不应赋予 prior = 0 或 1。

对 Gaia 的推荐契约是：

### 5.1 经验命题

经验 claim、review score、实验支持、科学结论等：

- prior 必须在 `(0, 1)` 开区间内
- `build` / `validate` 阶段就应检查
- 如果用户提供 `0` 或 `1`，应显式报错或显式归一化并告知

### 5.2 定义性 / 逻辑性真理

例如：

- 类型约束
- 明确定义的 setting
- 逻辑恒真

如果确实需要 0/1 概率，最好不要复用普通经验 claim 的 BP 语义，而应单独建模为：

- deterministic constraint
- schema-level invariant
- type/system rule

### 5.3 零分区的处理

如果 BP 图中真的出现零分区（`Z = 0`）：

- 不应静默回退到 `[0.5, 0.5]`
- 应显式抛出 `InconsistentGraphError` 或同类错误

因为这表示的不是“中立无信息”，而是：

```text
the model as constructed is mutually incompatible
```

---

## 6. 对 Gaia 流程的影响

### 6.1 build

`gaia build` 负责：

- prior 合法性检查
- contradiction schema 检查
- 将 authoring-level contradiction lowering 成 BP exclusion factor

### 6.2 review

`gaia review` 负责：

- 识别冲突 claim 组
- 生成 contradiction reports
- 回溯 shared supports
- 生成 retraction / weakening / context-splitting candidates

### 6.3 publish / ingest

`gaia publish` 和 server ingest 负责：

- 持久化已确认的 retraction
- 保留 unresolved contradiction 作为 tension
- 不把每个 contradiction 都强行翻译成“某个 claim 已被推翻”

这与科学研究的真实工作流更一致：

- 冲突可以长期存在
- 有时只是 context 不足
- 有时只是上位抽象太强
- 并不是每次都要立刻裁决一个“输家”

---

## 7. 对 Galileo 类例子的建议

以 Galileo 的绑球思想实验为例，推荐做法是：

1. `tied_pair_slower_than_heavy`
2. `tied_pair_faster_than_heavy`
3. compiler / review 生成一个 headless contradiction factor，表示二者不能同真
4. review sidecar 生成：

```text
contradiction_report:
  conflicting_claims:
    - tied_pair_slower_than_heavy
    - tied_pair_faster_than_heavy
  likely_shared_support:
    - heavier_falls_faster
```

5. 再由 review 或作者确认是否要产生：

```text
retraction_candidate:
  target: heavier_falls_faster
  reason: tied_balls contradiction under shared law
```

这里最重要的是：

- **矛盾本身** 是 BP 的事
- **谁该回撤** 是 review 的事

---

## 8. 建议的实现顺序

### Phase 1

- 保留现有 `contradiction` edge type
- 在 compiler/runtime 中优先支持 headless contradiction factor
- 文档明确：这是推荐语义

### Phase 2

- review pipeline 生成 contradiction reports
- 追踪 shared direct supports
- 生成 retraction candidates

### Phase 3

- 再决定是否需要保留 headful contradiction 作为一等图对象
- 如果保留，应将其定义成 diagnostic node，而不是 exclusion factor 的同义物

---

## 9. 最终建议

Gaia 中最稳健的 contradiction 设计应当是：

1. **BP 层**：`contradiction = exclusion factor`
2. **Review 层**：`contradiction_report = explicit audit artifact`
3. **Resolution 层**：`retraction = reviewed action, not automatic consequence`

这套设计最符合：

- Jaynes 的概率论逻辑
- BP 的数值稳定性
- Gaia 的 research-package 工作流
- 科学知识系统对“长期保留 tension”的需要

一句话概括：

> 在 Gaia 里，发现 contradiction 的第一步应该是  
> **降低“同时为真”的联合概率**，  
> 而不是**立即制造一个胜负判决**。
