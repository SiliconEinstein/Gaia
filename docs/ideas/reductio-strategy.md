# Reductio 论证策略 — 归谬法

> **Status:** Idea — 依赖 negation reasoning_type，暂不纳入实现范围

## 动机

Reductio ad absurdum（归谬法 / 反证法）是科学论证中常见的推理模式：假设 P 成立，从 P 推导出某个结果 Q，发现 Q 与已知事实 R 矛盾，因此结论是 ¬P。

当前 gaia-lang 的四个论证策略（abduction、induction、analogy、extrapolation，见 [设计 spec](../specs/2026-03-25-gaia-lang-alignment-design.md) §4）不包含归谬法。归谬法需要 negation 关系（见 [negation-relation.md](negation-relation.md)），因此 defer 到 negation 就绪后实现。

## 语法草案

```typst
#claim[亚里士多德的落体假说：重物比轻物下落更快] <hypo.aristotle>
#claim[将轻球绑在重球上后，复合体速度慢于重球] <derive.slow>
#claim[将轻球绑在重球上后，复合体更重故速度快于重球] <derive.fast>
#relation(type: "contradiction", between: (<derive.slow>, <derive.fast>))

#reductio(
  assumption: <hypo.aristotle>,
  absurdity: (<derive.slow>, <derive.fast>),
)[从假设推出 T₁ 和 T₂，二者矛盾]
```

### 参数说明

- `assumption:` — 被假设为真的命题 P（将被归谬）
- `absurdity:` — 矛盾的命题对 (Q, R)，或者指向一个已有的 contradiction relation
- Body — justification：为什么从 P 能推出矛盾

## 因子图

### 粗因子图

```
contradict(P, R) — 假设 P 导致与已知事实 R 矛盾
```

粗因子视角下，reductio 是一个整体的"归谬"关系：P 的假设导致矛盾，因此 P 不成立。

### 细因子图分解

编译器将 `#reductio` 展开为以下细因子图：

```
1. entailment: P → Q          （从假设 P 推导出结果 Q）
2. contradict(Q, R)            （Q 与已知事实 R 矛盾）
3. negation(P, ¬P)             （P 和 ¬P 真值互补）
```

其中：
- P 是作者传入的 `assumption`
- Q 是 P 的推导结果（可以是作者显式提供的 claim，也可以由编译器从 body 中提取）
- R 是与 Q 矛盾的已知事实
- ¬P 是编译器自动生成的否命题节点，是 reductio 的最终结论

### BP 路径

1. R 的 belief 高（已知事实）
2. contradict(Q, R) 压低 Q 的 belief
3. entailment P→Q 的反向消息：Q belief 低 → P belief 被压低
4. negation(P, ¬P)：P belief 低 → ¬P belief 被提升

最终效果：¬P 获得高 belief——归谬成功。

## 与伽利略连球悖论的对应

05-formalization-methodology.md §3.3 中伽利略的连球悖论正是一个 reductio：

- P = A（"重者更快"）
- Q = T₁（"复合体应比重球更慢"）
- R = T₂（"复合体应比重球更快"）
- T₁ ⊗ T₂（矛盾）
- 结论：A 不成立

当前粗因子图中，这个推理通过 entailment(A→T₁) + entailment(A→T₂) + contradict(T₁,T₂) 来表达。加入 reductio 策略和 negation 后，可以更精确地建模为 reductio(assumption: A, absurdity: (T₁, T₂))，并自动生成 ¬A 节点。

## 依赖

- **negation reasoning_type**（见 [negation-relation.md](negation-relation.md)）— 需要 negation 来连接 P 和 ¬P
- **graph-ir 变更** — negation 本身需要 graph-ir 变更
- **template 机制**（可选）— 自动构造 ¬P 节点

## 参考

- [negation-relation.md](negation-relation.md) — negation 关系定义
- [../foundations/theory/05-formalization-methodology.md](../foundations/theory/05-formalization-methodology.md) §3.3 — 伽利略连球悖论
- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2 — contradict reasoning_type
- [../foundations/bp/potentials.md](../foundations/bp/potentials.md) — contradiction potential 函数
- [../specs/2026-03-25-gaia-lang-alignment-design.md](../specs/2026-03-25-gaia-lang-alignment-design.md) §4 — 当前论证策略设计
