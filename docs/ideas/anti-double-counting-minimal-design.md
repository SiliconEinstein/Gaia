# Anti-Double-Counting Minimal Design — 最小可执行设计草案

> **Status:** Idea
>
> 本文档是 [double-counting-problem.md](double-counting-problem.md) 的 companion。前者讨论问题本身；本文讨论一个更窄的问题：
>
> > 在不过度增加 Gaia IR 复杂度的前提下，怎样让 lowering 结束后就已经落实 anti-double-counting，而不是再把复杂判断推给下游 LKM。

## 1. 目标与边界

本文只讨论 **v1 anti-double-counting design**。

它的目标不是：

- 解决命题等价是如何被发现的
- 解决命题 refinement 的完整语义体系
- 解决所有模糊的、无法结构化的证据重叠

它的目标是：

- 当 claim-level 的等价关系已经被接受并进入 IR 后，lowering 可以直接避免明显的重复计数
- 当后来的 package 只是重述或细化旧论证时，lowering 可以直接 suppress 旧 factor，而不是把新旧两条路径都算进去

换句话说，v1 追求的是：

> **只解决那些已经被显式写进 IR 的、可执行的 anti-double-counting 情况。**

## 2. 核心原则

### 2.1 不增加新的顶层 IR primitive

v1 尽量继续复用现有的：

- `Claim`
- `Strategy`
- `Operator`

而不是新增 `Judgment`、`Binding`、`CanonicalClaim` 等新的顶层对象。

### 2.2 package-level metadata 不够

一个 package 里可以有多个 conclusion，它们与旧工作的关系可能完全不同。

因此 anti-double-counting 语义不能主要挂在 package level。  
它必须直接挂在：

- claim 之间的关系上
- strategy 之间的关系上

### 2.3 lowering 必须直接可执行

好设计不应该要求下游 LKM 再去读自然语言、再猜 metadata、再发明一套二次推理逻辑。

v1 的标准应是：

> **IR 中一旦出现了这些结构，lowering 就知道 claim 要不要 merge，strategy factor 要不要 emit / suppress。**

## 3. v1 的最小设计

### 3.1 claim level：只保留 `equivalence` 和 `contradiction`

v1 不额外引入 claim-level `refines`。

claim level 只使用现有 Operator：

- `equivalence(A, B)`
- `contradiction(A, B)`

其中本文只关心 `equivalence` 的 anti-double-counting 作用：

- 一旦某个 `equivalence(A, B)` 已经作为可接受的关系进入 IR
- lowering 就把 `A`、`B` 视为同一个 runtime conclusion bucket

本文**不讨论**：

- `equivalence` 是如何被发现的
- 它与更完整的命题语义同一性理论是否完全重合

这里只把它当作 v1 lowering 可以消费的 **claim coalescing signal**。

### 3.2 strategy level：引入两种特殊 composite 语义

v1 的关键扩展不在 claim level，而在 strategy level。

普通 `CompositeStrategy` 只表达：

- 一个大论证由哪些子策略组成

但 anti-double-counting 还需要表达：

- 这组新策略与哪些旧策略是替代关系
- 哪些旧策略应该在 lowering 时被 suppress

因此 v1 需要给 `CompositeStrategy` 增加一个很小的、可执行的语义区分。

本文使用两个工作名：

- `refinement_composite`
- `restatement_composite`

它们不是新的顶层 primitive，而是 `CompositeStrategy` 的两种特殊 lowering 语义。

### 3.3 最小结构约定

概念上，一个带 anti-double-counting 语义的 composite 需要表达：

- `sub_strategies`
  lowering 后应该保留的那组新结构
- `targets`
  lowering 后应该被 suppress 的旧 strategy 引用
- `mode`
  这是 `refinement` 还是 `restatement`

最小伪 schema：

```yaml
CompositeStrategy:
  strategy_id: ...
  type: ...
  conclusion: ...
  sub_strategies: [ ... ]         # lowering 要保留的结构
  relation_mode: ordinary | refinement | restatement
  targets: [StrategyRef, ...]     # refinement/restatement 时必填
```

其中 `StrategyRef` 必须允许外部 strategy 引用。  
否则后来者无法通过一个新 package 去修正两个旧 package 之间的重复计数。

### 3.4 lowering 语义

普通 strategy：

- 正常 lower 成 factor

`refinement_composite`：

- `sub_strategies` 正常 lower
- `targets` 中的旧 strategy factor 被 suppress

`restatement_composite`：

- `sub_strategies` 中保留一份代表性支持结构
- `targets` 中的重复旧 strategy factor 被 suppress

claim-level `equivalence`：

- 先把相关 conclusion coalesce 到同一个 runtime claim bucket

因此 lowering 的顺序是：

1. 根据 `equivalence` 构建 claim equivalence classes
2. 对 strategies / composites 做 factor emission 或 suppression
3. 输出已经去重的 runtime graph

## 4. 为什么这样是最小的

这个设计刻意没有引入：

- claim-level `refines`
- `support_overlap` primitive
- 新的 `Judgment` 层
- package-level verdict object

原因是：

- `claim refinement` 是更大的语义组织问题，不是 v1 anti-double-counting 的必要条件
- `support_overlap` 如果不能直接转成 lowering 动作，就只是在把复杂度换个地方藏起来
- 新的 judgment primitive 会增加 IR 层级，但不一定减少 lowering 复杂度

v1 只保留两个 lowering 可以直接执行的动作：

- claim coalescing
- factor suppression

## 5. 例子分析

### 5.1 作者继续旧 conclusion，补一条新证据

这是最简单、也是最重要的场景。

```yaml
# old package
claim X
strategy S_old: O1 -> X

# new package
import X
strategy S_new: O2 -> X
```

lowering：

- `X` 只有一个 runtime claim
- `S_old` emit
- `S_new` emit

这里不需要特殊 composite。  
只要作者直接引用旧 conclusion，而不是再造一个 `X'`，就不会产生 claim duplication。

### 5.2 作者继续旧 conclusion，但只是把旧论证拆细

```yaml
# old package
claim X
strategy S_old: A -> X

# new package
import X
strategy S1: A -> B
strategy S2: B -> X
composite R:
  relation_mode: refinement
  sub_strategies: [S1, S2]
  targets: [S_old]
```

lowering：

- `S1`、`S2` emit
- `S_old` suppress

这里 `CompositeStrategy` 负责暴露新的内部结构；  
`relation_mode=refinement` 负责告诉 lowering：旧的粗 factor 不该和新的细结构一起重复计数。

### 5.3 后来的 researcher 发现两个旧 conclusion 等价，其中一个 strategy 只是另一个的重复

```yaml
# pkg A
claim A
strategy S_A: O_A -> A

# pkg B
claim B
strategy S_B: O_B -> B

# later relation package
operator equivalence(A, B)
composite R:
  relation_mode: restatement
  sub_strategies: [S_A]
  targets: [S_B]
```

lowering：

1. 先由 `equivalence(A, B)` 把 `A`、`B` 放入同一个 conclusion bucket
2. 再由 `restatement_composite` suppress `S_B`
3. 最终只保留 `S_A` 的 support factor

这就是“后来者通过一个新 package 修正旧包之间的 double counting”。

### 5.4 partial overlap：两个粗策略共享一部分支持

原始形态：

```yaml
S_A: D + H1 -> X
S_B: D + H2 -> X
```

如果保持这种粗粒度结构，lowering 看不出 `D` 是共享部分，很容易算两次。

v1 的处理方式不是发明 `support_overlap` primitive，而是**先 refine，再去重子结构**。

```yaml
strategy S_shared: D -> C
strategy S_A_tail: C + H1 -> X
strategy S_B_tail: C + H2 -> X

composite R_A:
  relation_mode: refinement
  sub_strategies: [S_shared, S_A_tail]
  targets: [S_A]

composite R_B:
  relation_mode: refinement
  sub_strategies: [S_shared, S_B_tail]
  targets: [S_B]
```

这时 lowering：

- `S_A` suppress
- `S_B` suppress
- `S_shared` emit 一次
- `S_A_tail` emit
- `S_B_tail` emit

结果：

- 共享部分 `D` 不再被重复计算
- 两条路径的增量部分 `H1`、`H2` 仍然保留

这正是 partial overlap 的正确处理方式。

### 5.5 partial overlap 的另一种情况：共享子策略最初也被写成了两份

例如后来者先分别抽出了：

```yaml
S_shared_A: D -> C
S_shared_B: D -> C
```

这时还可以再加一层：

```yaml
composite R_shared:
  relation_mode: restatement
  sub_strategies: [S_shared_A]
  targets: [S_shared_B]
```

于是 lowering 仍然只保留一份共享支持。

这说明：

> partial overlap 不需要单独的 `support_overlap` primitive；  
> 只要能被 refine 成显式子策略，再用 restatement 去重，就足够了。

## 6. 这套设计能 cover 什么

v1 可以直接 cover：

- 已知旧 conclusion，追加新证据
- 已知旧 conclusion，细化旧 strategy
- 后来者发现两个旧 conclusion 等价，并 suppress 重复 strategy
- partial overlap，但共享部分可以被结构化拆出来

## 7. 这套设计故意不 cover 什么

### 7.1 命题 refinement

例如：

- `B` 是 `A` 的更窄版本
- `B` 是 `A` 的条件化版本

这当然是重要问题，但它不是 v1 anti-double-counting 的必要条件。  
它可以后续再单独设计。

### 7.2 无法结构化的模糊重叠

如果两个 strategy 的共享性只是一种模糊判断，而不能被拆成显式共享子策略，那么 v1 不尝试自动修复。

在这种情况下，系统应当保持保守，而不是发明一个 lowering 无法执行的模糊标签。

### 7.3 `equivalence` 的发现与接受流程

本文只假设：

- 某个 `equivalence(A, B)` 已经进入了 IR

本文不讨论：

- 它是通过什么 review / curation 过程进入的
- 它与更完整的命题同一性理论应如何对齐

这属于另一层问题。

## 8. 总结

如果目标是：

> 不 over-engineer，且 lowering 结束后就已经落实 anti-double-counting

那么一个足够小、又足够可执行的 v1 设计是：

- claim level 只保留 `equivalence` / `contradiction`
- strategy level 在 `CompositeStrategy` 上增加两种特殊 lowering 语义：
  - `refinement_composite`
  - `restatement_composite`
- partial overlap 不单独发明 primitive，而是通过：
  - refine 暴露共享子结构
  - restate 去重共享子结构

这套设计的好处是：

- 不需要新的顶层 judgment 层
- 不把复杂判断推给 package-level metadata
- 不把复杂度继续 offload 给下游 LKM
- 只要求 lowering 执行两类明确动作：
  - claim coalescing
  - factor suppression

这是本文认为最接近“第一版可落地的最小 anti-double-counting 设计”的方案。
