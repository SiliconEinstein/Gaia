# Helper Claims

> **Status:** Draft — Gaia IR helper claim catalog
>
> **⚠️ Protected Contract Layer** — 本文档为 Gaia IR 的辅助约定文档，定义标准 helper claim 的最小集合与命名边界。

## 目的

Helper claim 用来承载两类东西：

- 推理细化时需要显式落图的中间命题
- Operator 关系节点化后的标准结果 claim

它的目标不是引入新的实体类型，而是让“中间对象”保持可引用、可传播、可复用。

## 1. 基本原则

### 1.1 仍然是 claim

Helper claim **不是**新的 Knowledge 类型。它始终编码为：

```text
Knowledge(type=claim)
```

如需参数化模式，直接使用 `parameters`；如需标记 helper 身份，建议使用：

```text
metadata.helper_kind
metadata.helper_origin
```

### 1.2 不是封闭枚举

本文只定义 **标准最小集合**，不是 closed enum。

- IR contract 允许未来增加新的 helper kind
- 新增 helper kind 时应优先复用已有命名模式

### 1.3 可传播、可引用

所有 helper claim 都是 claim，因此：

- 可以被 Strategy 引用为 premise / conclusion
- 可以被后续 Operator 引用
- 可以在 downstream 中参与概率传播

但不同 helper claim 的**自由度**不同：

- 语义型 helper claim 通常允许独立 prior
- 结构型 helper claim 通常由 Operator 结构确定，是否允许单独参数化由 downstream policy 决定

## 2. 两大类 helper claim

### 2.1 语义型 helper claim

这类 helper claim 有独立科学语义，值得被单独 review、引用、复用或反驳。

标准最小集合：

| helper_kind | 作用 | 典型来源 |
|-------------|------|----------|
| `prediction` | 假说/规律推出的预测 | abduction, induction |
| `instance` | 一般规律在具体对象上的实例 | induction, deduction |
| `bridge` | 类比中的桥梁主张 | analogy |
| `continuity` | 外推中的连续性/平滑性主张 | extrapolation |

建议：

- 这类 helper claim 优先显式写入 `knowledges`
- 如存在模式化复用需求，可直接使用参数化 claim

示例：

```yaml
type: claim
content: "该规律在样本 YBCO 上成立"
parameters:
  - {name: "law", type: "claim"}
  - {name: "sample", type: "material"}
metadata:
  helper_kind: instance
```

### 2.2 结构型 helper claim

这类 helper claim 主要用于把 Operator 关系节点化，使结构关系本身也可被引用。

它们通常由 compiler / reviewer 自动生成，而不是由作者随意手写。

## 3. Operator 结果 helper claim

当前 v2 约定：**每个 Operator 都有 `conclusion`**。

- 对 `implication` / `conjunction`，`conclusion` 延续现有用法，是推理链中的输出 claim
- 对 `equivalence` / `contradiction` / `complement` / `disjunction`，`conclusion` 是标准结构型 helper claim

### 3.1 标准列表

| operator | `conclusion` 含义 | 推荐 helper_kind | 说明 |
|----------|------------------|------------------|------|
| `implication(A,B)` | `B` | `implication_result` | 延续现有写法，输出仍是 consequent |
| `conjunction(A₁,...,Aₖ,M)` | `M = A₁∧...∧Aₖ` | `conjunction_result` | 合取命题本身 |
| `disjunction(A₁,...,Aₖ)` | `any_true(A₁,...,Aₖ)` | `disjunction_result` | 至少一个为真的关系命题 |
| `equivalence(A,B)` | `same_truth(A,B)` | `equivalence_result` | 两命题同真同假 |
| `contradiction(A,B)` | `not_both_true(A,B)` | `contradiction_result` | 两命题不可同真 |
| `complement(A,B)` | `opposite_truth(A,B)` | `complement_result` | 两命题真值互补 |

### 3.2 生成规则

关系型 Operator 的 `conclusion` 遵循以下规则：

1. 由 compiler / reviewer 自动生成
2. 命名应稳定、可复现
3. 进入 IR 后应视为标准 claim，可被后续 Strategy/Operator 引用
4. 不允许作者借关系型 Operator 的 `conclusion` 字段手写任意主观结论

## 4. 显式性规则

### 4.1 必须显式

以下 helper claim 应显式写入 `knowledges`：

- 所有语义型 helper claim
- 所有会被跨步骤引用的结构型 helper claim
- 所有作为 `Operator.conclusion` 暴露给外部图结构的 helper claim

### 4.2 可以局部自动生成

仅服务于单个 FormalExpr、且不会被外部引用的局部结构节点，可以由 compiler 自动生成。

这类节点如果后来需要：

- 被后续 Strategy 引用
- 被另一个 Operator 引用
- 被 downstream 参数化或传播

则应提升为显式 helper claim。

## 5. 与 Strategy 的关系

Helper claim 常见于以下细化模式：

| Strategy | 常见 helper claim |
|----------|------------------|
| `deduction` | `conjunction_result` |
| `abduction` | `prediction`, `equivalence_result` |
| `induction` | `instance`, `equivalence_result` |
| `analogy` | `bridge`, `conjunction_result` |
| `extrapolation` | `continuity`, `conjunction_result` |
| `reductio` | `contradiction_result`, `complement_result` |
| `elimination` | `contradiction_result`, `complement_result`, `conjunction_result` |
| `case_analysis` | `disjunction_result`, `conjunction_result` |

## 6. 开放点

当前仍未完全定稿的点：

- helper claim 的 canonical naming grammar
- 哪些结构型 helper claim 默认允许独立 prior
- `implication` 是否长期保留“conclusion = consequent”这一特例，还是未来也改成关系命题化
