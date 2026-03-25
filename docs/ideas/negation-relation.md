# Negation 关系 — 第六个 reasoning_type

> **Status:** Idea — 需要 graph-ir 变更，暂不纳入实现范围

## 动机

当前 graph-ir（见 [graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2）定义了五个 reasoning_type：

1. entailment
2. induction
3. abduction
4. equivalent
5. contradict

缺少 **negation**（否定）。Negation 连接一个命题 P 与其否命题 ¬P，编码"二者真值互补"的逻辑约束。

## 语义

Negation 是双向约束：P 和 ¬P 的真值必须相反。

- P 为真 → ¬P 必为假
- P 为假 → ¬P 必为真
- 不允许 (P=1, ¬P=1) 或 (P=0, ¬P=0)

### 与 contradiction 的区别

Contradiction 编码的是"两个独立命题不应同时为真"——它惩罚 (1,1) 但不惩罚 (0,0)。两个矛盾的假说都为假是完全可能的（例如"暗能量是宇宙学常数" vs "暗能量是动态标量场"——两者可能都不对）。

Negation 编码的是"二者真值严格互补"——它同时惩罚 (1,1) 和 (0,0)。这是逻辑否定的语义：P 和 ¬P 必须恰好一真一假。

## Potential 函数

```
FactorNode(reasoning_type: negation):
    premises: [P, ¬P]
    conclusion: None  （双向约束）

| P | ¬P | Potential |
|---|-----|----------|
| 1 | 0   | 1 - ε    |  （兼容：P 真，¬P 假）
| 0 | 1   | 1 - ε    |  （兼容：P 假，¬P 真）
| 1 | 1   | ε        |  （不兼容：不能同时为真）
| 0 | 0   | ε        |  （不兼容：不能同时为假）
```

其中 ε = Cromwell 下界（见 [belief-propagation.md](../foundations/theory/belief-propagation.md)）。

### BP 行为

- P belief 高 → 反向消息压低 ¬P
- P belief 低 → 反向消息提升 ¬P
- 完全对称：¬P 的证据同样影响 P

## Graph-ir 变更

需要在 FactorNode 的 `reasoning_type` 枚举中添加 `negation`：

```
reasoning_type: entailment | induction | abduction
              | equivalent | contradict | negation | None
```

不变量与 `contradict` / `equivalent` 一致：`conclusion = None`，`premises` 至少包含 2 个节点。

## 用例

1. **Reductio ad absurdum（归谬法）**：假设 P，推出矛盾，因此 ¬P 成立。需要 negation 连接 P 和 ¬P（见 [reductio-strategy.md](reductio-strategy.md)）。

2. **Process of elimination（排除法）**：排除 H₁ 和 H₂ 后，得出 H₃。需要 negation 表达"H₁ 被否定"（见 [elimination-strategy.md](elimination-strategy.md)）。

3. **对立假说建模**：当一个假说 P 的否命题 ¬P 本身有独立的含义和证据链时（例如 P="暗能量随时间变化" vs ¬P="暗能量是常数"），negation 允许二者各自独立参与 BP，同时保持真值互补约束。

## 否命题的构造

¬P 是一个独立的 KnowledgeNode（type: claim），其内容是 P 的逻辑否定。构造 ¬P 需要 template 机制的支持（见 [template-mechanism.md](template-mechanism.md)）——给定 claim P，自动生成 ¬P 节点并建立 negation factor。

在 template 机制就绪之前，¬P 可以由作者手动创建。

## 依赖

- **graph-ir 变更**：需要在 reasoning_type 枚举中添加 `negation`
- **bp/potentials.md 更新**：需要定义 negation 的 potential 函数

## 参考

- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2 — reasoning_type 定义
- [../foundations/bp/potentials.md](../foundations/bp/potentials.md) — contradiction / equivalence 的 potential 函数
- [../foundations/theory/reasoning-hypergraph.md](../foundations/theory/reasoning-hypergraph.md) §5.4 — 概率化 Horn 子句（当前缺少否定）
