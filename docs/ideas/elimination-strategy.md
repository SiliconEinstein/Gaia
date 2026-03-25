# Elimination 论证策略 — 排除法

> **Status:** Idea — 依赖 negation reasoning_type，暂不纳入实现范围

## 动机

Process of elimination（排除法）是科学推理中的常见模式：在一组互斥且穷尽的假说中，逐一排除不成立的假说，剩下的即为结论。

典型场景：面对实验异常，有三个竞争假说 H₁、H₂、H₃。通过实验或推理排除 H₁ 和 H₂ 后，得出 H₃ 成立。

排除法需要 negation 关系来表达"假说被否定"（见 [negation-relation.md](negation-relation.md)），因此 defer 到 negation 就绪后实现。

## 语法草案

```typst
#claim[仪器误差导致异常信号] <hypo.instrument>
#claim[环境噪声导致异常信号] <hypo.noise>
#claim[新物理效应导致异常信号] <hypo.new_physics>

#claim[校准检查表明仪器正常] <evidence.calibration>
#claim[屏蔽实验排除了环境噪声] <evidence.shielding>

#elimination(
  eliminated: (<hypo.instrument>, <hypo.noise>),
  survivor: <hypo.new_physics>,
  evidence: (<evidence.calibration>, <evidence.shielding>),
)[仪器误差被校准排除，环境噪声被屏蔽排除，
  三个假说穷尽了所有可能解释]
```

### 参数说明

- `eliminated:` — 被排除的假说列表
- `survivor:` — 排除后剩余的假说（结论）
- `evidence:` — 排除各假说的证据
- Body — justification：为什么这些假说穷尽了可能性，以及每个被排除的假说为什么不成立

## 因子图

### 粗因子图

```
[E₁, E₂] → H₃
```

证据 E₁、E₂ 作为 premise，survivor H₃ 作为 conclusion。粗因子视角下，这是一个"排除后得出结论"的整体关系。

### 细因子图分解

编译器将 `#elimination` 展开为以下结构：

```
1. Pairwise contradiction（排除证据）：
   - contradict(H₁, E₁)     （证据 E₁ 与假说 H₁ 矛盾）
   - contradict(H₂, E₂)     （证据 E₂ 与假说 H₂ 矛盾）

2. Negation（否定被排除的假说）：
   - negation(H₁, ¬H₁)      （H₁ 和 ¬H₁ 真值互补）
   - negation(H₂, ¬H₂)      （H₂ 和 ¬H₂ 真值互补）

3. Exhaustive constraint（穷尽约束）：
   - entailment: [¬H₁, ¬H₂] → H₃   （其他假说都被排除，H₃ 必然成立）
```

### BP 路径

1. E₁ belief 高（校准证据）→ contradict(H₁, E₁) 压低 H₁
2. H₁ belief 低 → negation(H₁, ¬H₁) 提升 ¬H₁
3. 同理 E₂ → H₂ 被压低 → ¬H₂ 被提升
4. ¬H₁ 和 ¬H₂ belief 都高 → entailment [¬H₁, ¬H₂] → H₃ 提升 H₃

最终效果：通过排除替代假说，survivor H₃ 获得高 belief。

## 穷尽约束的关键性

排除法的有效性依赖于"假说穷尽了所有可能性"这一前提。细因子图中的 entailment `[¬H₁, ¬H₂] → H₃` 编码了这一穷尽约束。

这个 entailment 的 `steps` 字段应包含作者的 justification（为什么这三个假说穷尽了所有可能性）。如果穷尽性被质疑（例如有人提出第四个假说 H₄），这条 entailment 的 probability 应被降低。

### 与 contradiction 的组合

被排除的假说之间不需要两两矛盾（它们可能互相独立），但每个被排除的假说都与排除它的证据矛盾。Contradiction 在这里连接的是"假说"与"否定该假说的证据"，而非假说之间。

## 扩展性

- **N 选 1**：支持任意数量的候选假说，排除 N-1 个
- **N 选 M**：如果排除后剩余多个假说，survivor 可以是多个，需要额外的 disjunctive constraint（当前 graph-ir 不支持析取，待未来扩展）
- **嵌套排除**：每个 contradiction(Hᵢ, Eᵢ) 可以进一步展开——Eᵢ 本身可能来自 reductio 或其他论证策略

## 依赖

- **negation reasoning_type**（见 [negation-relation.md](negation-relation.md)）— 需要 negation 连接 Hᵢ 和 ¬Hᵢ
- **graph-ir 变更** — negation 本身需要 graph-ir 变更
- **reductio 策略**（可选）— 某些排除步骤本身可能是 reductio（见 [reductio-strategy.md](reductio-strategy.md)）

## 参考

- [negation-relation.md](negation-relation.md) — negation 关系定义
- [reductio-strategy.md](reductio-strategy.md) — reductio 策略（排除法的单步可能是归谬）
- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2 — contradict reasoning_type
- [../foundations/bp/potentials.md](../foundations/bp/potentials.md) — contradiction potential 函数
- [../foundations/theory/reasoning-hypergraph.md](../foundations/theory/reasoning-hypergraph.md) §5.4 — 概率化 Horn 子句
- [../specs/2026-03-25-gaia-lang-alignment-design.md](../specs/2026-03-25-gaia-lang-alignment-design.md) §7 — Ideas 列表
