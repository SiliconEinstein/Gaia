# Template 机制 — 可参数化的图结构生成器

> **Status:** Idea — 需要 gaia-lang 语法设计，暂不纳入 v1 实现范围

## 动机

Graph-ir 已定义 `template` 作为第四种知识类型（见 [graph-ir.md](../foundations/graph-ir/graph-ir.md) §1.2），具有 `parameters` 字段存储自由变量列表。然而 gaia-lang v1 暂不暴露 template 语法（见 [设计 spec](../specs/2026-03-25-gaia-lang-alignment-design.md) §2.5）。

本文档探索 template 的通用机制设计：template 不仅是含自由变量的命题模式，更是**可参数化的图结构生成器**——给定参数，生成一组 KnowledgeNode 和 FactorNode。

## 核心概念

### Template 的两层含义

**1. 命题模板（graph-ir 已支持）**

含自由变量的命题模式。实例化时绑定变量，生成 closed claim。

```
Template: "在{体系}中，{物体}的加速度与质量无关"
  parameters: [体系, 物体]

实例化: {体系=月球真空, 物体=羽毛和锤子}
  → Claim: "在月球真空中，羽毛和锤子的加速度与质量无关"
```

实例化是 entailment 的特例（probability=1.0），graph-ir 已定义（见 [graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2 entailment 子场景），potentials.md 已有对应的 potential 函数（见 [potentials.md](../foundations/bp/potentials.md) §Instantiation）。

**2. 图结构模板（本 idea 的核心扩展）**

给定参数，生成一组节点和因子。这超越了单个命题的实例化——它生成整个子图。

```
Template: negation_of(P)
  parameters: [P: claim]
  generates:
    - ¬P: claim (content = negate(P.content))
    - negation(P, ¬P): factor
```

## 用例

### 1. 否命题构造（Negation construction）

给定 claim P，自动生成 ¬P 节点和 negation factor。

```
negation_of(P: claim) → {
  ¬P: claim,
  f: factor(reasoning_type: negation, premises: [P, ¬P])
}
```

这是 [negation-relation.md](negation-relation.md) 的基础设施：作者不需要手动创建 ¬P 节点，template 机制自动完成。

### 2. 推理模式实例化（Reasoning pattern instantiation）

将常见的论证模式抽象为 template，按需实例化。

```
modus_tollens(P: claim, Q: claim, not_Q: claim) → {
  f1: factor(entailment, premises: [P], conclusion: Q),
  f2: factor(negation, premises: [Q, not_Q]),
  f3: factor(negation, premises: [P, ¬P]),
  entailment: [not_Q] → ¬P
}
```

### 3. 全称量化（Universal quantification）

Template 是全称命题 ∀x. P(x) 的自然表达。当前 graph-ir 的 template 类型已支持这一用例——template 节点通过 instantiation factor 连接到具体 claim。

Theory 层的分析见 [reasoning-hypergraph.md](../foundations/theory/reasoning-hypergraph.md) §6.4：Template 不直接参与 BP，但通过 instantiation 桥接到 claim。[potentials.md](../foundations/bp/potentials.md) §Instantiation 已定义了 BP 行为：多个实例的反向消息在 template 节点聚合，实现归纳强化。

### 4. 论证策略的底层机制

当前四个论证策略（abduction、induction、analogy、extrapolation）的编译器展开可以理解为内置的、硬编码的 template。通用 template 机制将允许用户定义新的论证策略，而不需要修改编译器。

## 设计约束

### 与 graph-ir 的关系

Graph-ir 的 KnowledgeNode 已有 `type: template` 和 `parameters: list[Parameter]`。通用 template 机制需要扩展：

- **输出 schema**：template 不仅生成 KnowledgeNode，还生成 FactorNode
- **参数类型**：当前 `parameters` 是字符串级别的自由变量。图结构模板需要类型化参数（`P: claim`、`R: factor` 等）
- **内容生成**：命题模板只做字符串替换。图结构模板需要程序化的内容生成（如 `negate(P.content)`）

这些扩展可能需要 graph-ir 变更，但也可以作为 gaia-lang 编译层的特性实现，不改变 graph-ir 本身。具体方案需要进一步设计。

### 与 gaia-lang 的关系

需要设计 template 的声明和调用语法。初步思路：

```typst
// 声明 template
#template(
  name: "negation_of",
  params: (P: "claim"),
)[给定 claim P，构造其否命题 ¬P 及 negation 关系]

// 调用 template
#apply-template("negation_of", P: <hypo.aristotle>)
```

语法设计需要考虑：
- 与 Typst 的 function 机制的关系
- 参数的类型检查（编译时还是运行时）
- 生成的节点和因子的标签命名规则
- 嵌套调用和递归

## 与现有设计的关系

| 现有机制 | 与 template 的关系 |
|---------|-------------------|
| graph-ir `type: template` | template 机制的基础。已有 `parameters` 字段 |
| instantiation factor | 命题模板实例化已支持。图结构模板是扩展 |
| 论证策略编译器展开 | 可理解为内置 template。通用机制使其可扩展 |
| Typst function | gaia-lang 运行时文件（`libs/typst/gaia-lang-v4/`）中已有 Typst function。template 可以复用 Typst 的函数机制 |

## 依赖

- **graph-ir template 类型** — 已存在，但可能需要扩展以支持图结构模板
- **gaia-lang 语法设计** — 需要设计 template 的声明和调用语法
- **negation reasoning_type**（部分依赖）— negation_of template 是第一个用例，但 template 机制本身不依赖 negation

## 参考

- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §1.2 — template 知识类型定义
- [../foundations/bp/potentials.md](../foundations/bp/potentials.md) §Instantiation — 实例化 potential 函数
- [../foundations/theory/reasoning-hypergraph.md](../foundations/theory/reasoning-hypergraph.md) §6.4 — Template 桥接角色
- [negation-relation.md](negation-relation.md) — 否命题构造是第一个用例
- [../specs/2026-03-25-gaia-lang-alignment-design.md](../specs/2026-03-25-gaia-lang-alignment-design.md) §2.5 — Defer template 的决定
