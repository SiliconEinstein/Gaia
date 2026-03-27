# Helper Claims

> **Status:** Draft — Gaia IR helper claim catalog
>
> **⚠️ Protected Contract Layer** — 本文档为 Gaia IR 的辅助约定文档，定义标准 helper claim 的语义边界、显式化规则、canonical naming 规则与 compiler 生成约束。

## 目的

Helper claim 用来承载两类中间对象：

- 推理细化时需要显式落图的中间命题
- Operator 关系节点化后的标准结果 claim

它的目标不是引入新的实体类型，而是把“中间对象”也收回到统一的 claim 世界里，使其保持：

- 可引用
- 可传播
- 可复用
- 可审查
- 可在未来工作中被支持或质疑

本文件要解决的核心问题有四个：

1. 哪些中间对象应该被建模成 helper claim
2. helper claim 与普通 claim 的关系是什么
3. helper claim 何时必须显式进入 `knowledges`
4. helper claim 应如何做稳定、可复现的 canonical naming

## 1. 定位与边界

### 1.1 Helper Claim 仍然是 Claim

Helper claim **不是**新的 Knowledge 类型。它始终编码为：

```text
Knowledge(type=claim)
```

如果某个中间对象：

- 可以被后续 Strategy 引用
- 可以被后续 Operator 引用
- 需要在图中传播 belief
- 需要被单独 review / canonicalize / compare

那么它就应当表现为 claim，而不是悬浮在 graph 外的注释对象。

### 1.2 Helper Claim 不是什么

Helper claim 不是：

- 新的 IR primitive
- BP / factor graph 对象
- `background` 的自由文本替代品
- 给作者偷塞任意结论的后门

也就是说，本文件处理的是 **claim 层的建模纪律**，不是下游数值推理器的实现细节。

### 1.3 为什么要单独出一份文档

`gaia-ir-v2-draft.md` 定义核心 schema；本文件定义 helper claim 的专门约定。

这样拆开的原因是：

- helper claim 本身不是新 schema 类型，不值得把大量细节塞进主 schema 文档
- helper claim 的 catalog、命名、生成和显式化规则需要较多解释
- 未来 helper 种类会继续增长，单独维护更稳

### 1.4 不是封闭枚举

本文只定义 **标准最小集合**，不是 closed enum。

- IR contract 允许未来增加新的 helper kind
- 新增 helper kind 时应优先复用已有命名模式
- 新 helper kind 的加入不应改变既有 helper kind 的语义

## 2. 编码约定

### 2.1 基本编码

标准 helper claim 使用普通 claim 编码：

```yaml
knowledge_id: gcn_xxxxxxxx
type: claim
content: "A 与 B 不可同真"
metadata:
  helper_kind: contradiction_result
  helper_origin: structural
  canonical_name: not_both_true(gcn_A,gcn_B)
```

其中：

- `type=claim` 是必须的
- `metadata.helper_kind` 用来标记 helper 的角色
- `metadata.helper_origin` 用来区分 `semantic` 与 `structural`
- `metadata.canonical_name` 用来承载规范命名

### 2.2 推荐元数据字段

标准 helper claim 推荐使用以下 metadata 字段：

| 字段 | 是否推荐 | 说明 |
|------|----------|------|
| `helper_kind` | 必须 | helper 的标准角色名，如 `prediction`、`contradiction_result` |
| `helper_origin` | 必须 | `semantic` 或 `structural` |
| `canonical_name` | 必须 | 该 helper claim 的规范命名字符串 |
| `helper_source` | 推荐 | `author` / `compiler` / `reviewer` / `promoted_local_node` |
| `generated_by_operator` | 推荐 | 若由 Operator 自动生成，则记录 operator 名 |
| `generated_from_strategy` | 推荐 | 若由某个 Strategy 细化而来，可记录 strategy id |

说明：

- `canonical_name` 承担规范身份职责
- `content` 承担人类可读表达职责
- 两者不应混为一谈

### 2.3 `content` 与 `canonical_name` 的分工

`content` 可以是面向人的句子，例如：

- “A 与 B 不可同真”
- “规律 L 在样本 YBCO 上成立”

但 helper claim 的规范身份 **不由 `content` 决定**。

规范身份由 `canonical_name` 决定，原因是：

- `content` 会因为措辞、语言、编辑风格而变化
- 同一个 helper claim 可以有多种自然语言表述
- 不能因为改写一句中文说明就改变图中的命题身份

因此：

- author 可以改 `content`
- compiler / reviewer 负责稳定地产生 `canonical_name`

## 3. 两大类 Helper Claim

### 3.1 语义型 Helper Claim

这类 helper claim 有独立科学语义，值得被单独 review、引用、复用或反驳。

它们的共同特点是：

- 本身是科学命题，不只是布线结果
- 未来工作可以直接针对它提出支持或挑战
- 通常允许独立 prior
- 一般应显式进入 `knowledges`

标准最小集合如下：

| helper_kind | 语义 | 典型来源 | 默认显式 | 默认允许独立 prior |
|-------------|------|----------|----------|--------------------|
| `prediction` | 假说/规律推出的预测命题 | abduction, induction | 是 | 是 |
| `instance` | 一般规律在具体对象上的实例命题 | induction, deduction | 是 | 是 |
| `bridge` | 类比中的桥梁主张 | analogy | 是 | 是 |
| `continuity` | 外推中的连续性/平滑性主张 | extrapolation | 是 | 是 |

建议：

- 这类 helper claim 优先显式写入 `knowledges`
- 如存在模式化复用需求，可直接使用参数化 claim
- 命名优先使用 named-argument canonical form

### 3.1.1 语义型 Helper 的推荐 canonical 模板

| helper_kind | 推荐 canonical 模板 | 说明 |
|-------------|---------------------|------|
| `prediction` | `prediction(model=X,target=Y)` | `X` 是预测依据，`Y` 是被预测命题/对象 |
| `instance` | `instance(schema=X,subject=Y)` | `X` 是一般规律或模板，`Y` 是具体对象/情形 |
| `bridge` | `bridge(source=X,target=Y)` | `X` 与 `Y` 分别是类比两端 |
| `continuity` | `continuity(left=X,right=Y,axis=Z)` | `Z` 表示连续变化所依赖的轴或维度 |

这些模板是 **推荐最小参数集**，不是最终封闭语法。

如果某个 helper kind 需要更多参数：

- 应优先扩展 named arguments
- 不应通过改变 functor 名来编码小差异

示例：

```yaml
knowledge_id: gcn_pred_01
type: claim
content: "广义相对论预测水星近日点将发生额外进动"
metadata:
  helper_kind: prediction
  helper_origin: semantic
  helper_source: author
  canonical_name: prediction(model=gcn_gr,target=gcn_mercury_shift)
```

### 3.2 结构型 Helper Claim

这类 helper claim 主要用于把结构关系节点化，使结构关系本身也能进入 claim 世界。

它们的共同特点是：

- 通常由 compiler / reviewer 自动生成
- 常常来自 Operator 的 `conclusion`
- 本身可以被后续步骤引用
- 通常不默认引入新的自由参数

结构型 helper claim 仍然是 claim，因此：

- 可以被后续 Strategy 当作 premise / conclusion 使用
- 可以被后续 Operator 引用
- 可以在未来的 formalization 或 review 中被单独讨论

但与语义型 helper 不同：

- 它们默认更接近“结构上派生出的命题”
- 它们是否具有独立 prior，通常由 downstream policy 决定

## 4. Operator 结果 Helper Claim

当前 v2 约定：**每个 Operator 都有 `conclusion`**。

这里需要分清两类情形：

1. `conclusion` 延续既有含义，表示推理链中的输出 claim
2. `conclusion` 表示结构关系的 canonical result claim

### 4.1 当前各 Operator 的处理方式

| operator | `conclusion` 的角色 | 推荐 helper_kind | 推荐 canonical_name |
|----------|---------------------|------------------|---------------------|
| `implication(A,B)` | 现有 consequent `B` | 不新增关系 helper | 不适用 |
| `conjunction(A₁,...,Aₖ,M)` | 合取结果 claim `M` | `conjunction_result` | `all_true(A₁,...,Aₖ)` |
| `disjunction(A₁,...,Aₖ)` | compiler-generated helper claim | `disjunction_result` | `any_true(A₁,...,Aₖ)` |
| `equivalence(A,B)` | compiler-generated helper claim | `equivalence_result` | `same_truth(A,B)` |
| `contradiction(A,B)` | compiler-generated helper claim | `contradiction_result` | `not_both_true(A,B)` |
| `complement(A,B)` | compiler-generated helper claim | `complement_result` | `opposite_truth(A,B)` |

### 4.2 关键解释

#### `contradiction`

`not_both_true(A,B)` 不是“仅供内部使用的布线标记”，而是一个真正可引用的命题：

- 它可以在未来被别的 Strategy 引用
- 它可以在后续 formalization 中被展开或被审查
- 它可以在别的工作里被重新讨论

因此，把 `contradiction` 的结果 claim 显式落图是合理且必要的。

#### `equivalence`

`same_truth(A,B)` 表达的是命题关系本身，而不是 dedupe 补丁。

一旦一个 equivalence 关系被承认为图中的结构，这个关系本身就应该可以被后续工作引用。

#### `complement`

`opposite_truth(A,B)` 表达真值互补关系。它不同于一般意义上的矛盾冲突：

- `contradiction` 强调“不可能同时为真”
- `complement` 强调“真值互为补集”

因此两者都需要自己的 result helper claim。

#### `disjunction`

`any_true(A₁,...,Aₖ)` 是析取命题本身。若后续工作要引用“至少一个分支为真”这一事实，就应直接引用这个 helper claim，而不是绕回 operator。

#### `implication`

当前版本中，`implication` 仍保留旧语义：

- `Operator.conclusion` 直接指向 consequent claim
- 尚未把 `implication(A,B)` 自身 fully reify 成单独的关系命题

这是当前 schema 的有意特例。未来若要把 implication 也关系命题化，可在不破坏其余 helper naming 的前提下单独推进。

### 4.3 生成约束

关系型 Operator 的 `conclusion` 遵循以下规则：

1. 由 compiler / reviewer 自动生成
2. 命名必须稳定、可复现
3. 一旦进入 IR，应视为标准 claim
4. 不允许作者借关系型 Operator 的 `conclusion` 字段手写任意主观结论
5. 若同一 scope 内已存在同 canonical name 的 helper claim，应优先复用而不是重复生成

## 5. Canonical Naming

本节定义 helper claim 的 canonical naming grammar 与归一化规则。

其目标不是替代人类可读 `content`，而是为以下任务提供稳定锚点：

- compiler 自动生成 helper claim
- reviewer 判断两个 helper claim 是否同构
- canonicalization / dedup
- 未来 deterministic id 生成

### 5.1 基本语法

推荐 grammar 如下：

```text
canonical_name := functor "(" args? ")"
functor        := ascii_snake_case
args           := positional_args | named_args
positional_args:= arg ("," arg)*
named_args     := named_arg ("," named_arg)*
named_arg      := key "=" arg
key            := ascii_snake_case
arg            := normalized_ref | literal
```

约束：

- functor 一律使用 ASCII `snake_case`
- 单个 `canonical_name` 中不要混用 positional args 与 named args
- 结构型 helper 默认使用 positional args
- 语义型 helper 默认使用 named args

示例：

- `all_true(gcn_a,gcn_b,gcn_c)`
- `same_truth(gcn_a,gcn_b)`
- `not_both_true(gcn_a,gcn_b)`
- `prediction(model=gcn_gr,target=gcn_mercury_shift)`
- `instance(schema=gcn_law,subject=obj_ybco)`

### 5.2 `canonical_name` 的输入是什么

`canonical_name` 不是直接从自然语言 `content` 生成的，而是从 **已归一化的参数引用** 生成的。

当前 Gaia IR 中，实际可操作的稳定输入通常是：

- 已经解析完成的 `Knowledge` 引用
- 对象/实体的稳定标识
- 少量必要的规范 literal

因此，当前推荐做法是：

- 对结构型 helper，使用已归一化的 operand references
- 对语义型 helper，使用命名参数绑定到稳定 references

需要强调的是：

- `canonical_name` 假定其参数已经是稳定引用
- 它负责 helper claim 的规范命名
- 它**不负责**单独解决底层命题身份统一问题

换句话说，operand 自身的 identity 问题应先由更底层的 canonicalization 解决；helper claim 的 `canonical_name` 在此基础上继续向上组合。

### 5.3 归一化规则

### 5.3.1 通用规则

所有 helper claim 均适用以下通用规则：

1. functor 名必须稳定，不能把文案差异编码进 functor
2. 参数引用必须使用稳定 token，不能直接嵌入自由文本句子
3. `canonical_name` 的身份不依赖 `content`
4. 同一 helper claim 不应同时拥有多个 canonical name

### 5.3.2 二元对称关系

对称二元 helper 的参数必须排序后再命名。

适用对象：

- `same_truth(A,B)`
- `not_both_true(A,B)`
- `opposite_truth(A,B)`

归一化规则：

- 先取两个参数的稳定引用
- 按稳定排序规则排序
- 再生成 canonical name

因此：

- `same_truth(A,B)` 与 `same_truth(B,A)` 是同一个 canonical name
- `not_both_true(A,B)` 与 `not_both_true(B,A)` 是同一个 canonical name

### 5.3.3 可交换多元关系

可交换多元 helper 的参数应执行：

1. flatten
2. dedupe
3. sort

适用对象：

- `all_true(...)`
- `any_true(...)`

解释：

- `all_true(A, all_true(B,C))` 应归一到 `all_true(A,B,C)`
- `all_true(A,B,A)` 应归一到 `all_true(A,B)`
- `any_true(B,A,C)` 应归一到 `any_true(A,B,C)`

这里的 flatten 只针对 **同 functor 的结构型 helper**。也就是说：

- `all_true(A, all_true(B,C))` 可以 flatten
- `all_true(A, prediction(...))` 不会特殊 flatten

### 5.3.4 语义型 Helper 的参数顺序

语义型 helper 建议使用 named args，而不是依赖位置。

原因是：

- 语义型 helper 的角色参数更容易扩展
- named args 对人更可读
- named args 对 schema 演化更稳

因此：

- `prediction(model=X,target=Y)` 推荐
- `prediction(X,Y)` 不推荐

对于 named args：

- 参数键名应按 catalog 规定使用
- 生成时应使用固定键顺序
- 未使用的可选参数不写入 canonical name

### 5.4 推荐 functor 列表

当前标准 functor 如下：

| helper_kind | functor |
|-------------|---------|
| `conjunction_result` | `all_true` |
| `disjunction_result` | `any_true` |
| `equivalence_result` | `same_truth` |
| `contradiction_result` | `not_both_true` |
| `complement_result` | `opposite_truth` |
| `prediction` | `prediction` |
| `instance` | `instance` |
| `bridge` | `bridge` |
| `continuity` | `continuity` |

约束：

- functor 一旦标准化，就不应轻易重命名
- 新 helper kind 应优先增加新参数，而不是随意增加相近 functor

### 5.5 `knowledge_id` 与 `canonical_name`

`canonical_name` 负责表达规范语义名；`knowledge_id` 负责图中的节点引用。

推荐做法是：

- 先确定 `canonical_name`
- 再按 scope 的 id policy 派生出对应 `knowledge_id`

本文件不强行规定唯一 hash 算法，但推荐属性如下：

- 同 scope 下，同 canonical name 应稳定落到同一 helper claim
- 不同 scope 下，允许拥有不同 `knowledge_id`
- `knowledge_id` 可以由 `scope + canonical_name` 的确定性摘要派生

也就是说：

- `canonical_name` 是语义锚点
- `knowledge_id` 是图内引用锚点

## 6. 显式性与生命周期

### 6.1 必须显式

以下 helper claim 应显式写入 `knowledges`：

- 所有语义型 helper claim
- 所有作为 `Operator.conclusion` 暴露给外部图结构的 helper claim
- 所有会被跨步骤引用的结构型 helper claim
- 所有未来可能单独参与 review / parameterization / belief propagation 的 helper claim

### 6.2 可以局部自动生成

仅服务于单个 `FormalExpr`、且不会被外部引用的局部结构节点，可以由 compiler 自动生成。

典型例子：

- 某个局部 operator 链内部暂时使用的辅助节点
- 只在单个展开步骤里临时出现、且不会暴露到外层图的中间项

这类节点一旦需要：

- 被另一个 Strategy 引用
- 被另一个 Operator 引用
- 被下游系统单独参数化
- 被后续工作单独讨论

就应提升为显式 helper claim。

### 6.3 生命周期状态

helper claim 在工程上通常有三种来源：

1. `author`
作者显式写入的 helper claim，常见于 semantic helper

2. `compiler`
由编译器根据 operator / strategy 结构自动生成的 helper claim，常见于 structural helper

3. `promoted_local_node`
原本只是局部结构节点，后来因为需要复用或传播，被提升成显式 helper claim

推荐在 `metadata.helper_source` 中记录这一点。

## 7. Compiler 生成算法

对于 compiler-generated helper claim，推荐流程如下：

1. 确定 helper kind
2. 解析参与命名的 operand references
3. 按 helper kind 的规则做 normalize
4. 生成 canonical name
5. 在当前 scope 查找是否已有同 canonical name 的 helper claim
6. 若已有则复用；若没有则 materialize 新 claim
7. 将 `Operator.conclusion` 指向该 claim

### 7.1 关系型 Operator 的强约束

对 `equivalence` / `contradiction` / `complement` / `disjunction`：

- 作者不应手写一个任意的 `conclusion`
- compiler / reviewer 应生成标准 helper claim
- 该 claim 的 `canonical_name` 应直接来自 operator operands

### 7.2 `conjunction` 的特殊性

`conjunction` 常有一个显式结果 claim `M`。此时推荐约束为：

- 若 `M` 是标准 helper claim，则其 `canonical_name` 应为 `all_true(...)`
- 若 `M` 是作者显式命名的更高层语义 claim，则应谨慎使用 `conjunction`

实践上，若 `M` 只是结构性合取结果，优先让它成为标准 `conjunction_result` helper claim。

## 8. 与概率传播的关系

所有 helper claim 都是 claim，因此都可以进入传播过程。

但“可以传播”与“拥有独立自由度”不是一回事。

### 8.1 默认规则

| 类型 | 可传播 | 默认允许独立 prior | 说明 |
|------|--------|--------------------|------|
| 语义型 helper claim | 是 | 是 | 本身就是可被支持/反驳的命题 |
| 结构型 helper claim | 是 | 默认否 | 常由结构关系决定，更接近派生命题 |

### 8.2 Policy 与 Contract 的边界

本文件只规定 helper claim 可以进入统一的 claim 图。

本文件**不强行规定**下游必须如何对它们参数化。具体 policy 例如：

- 哪些结构型 helper 允许独立 prior
- 哪些 helper 只能由严格结构派生 belief
- 哪些 helper 可以在特定 pipeline 中被软化

属于 parameterization / runtime policy 的问题。

## 9. 示例

### 9.1 `contradiction` 的 result helper claim

```yaml
- knowledge_id: gcn_a
  type: claim
  content: "实验结果支持命题 A"

- knowledge_id: gcn_b
  type: claim
  content: "实验结果支持命题 B"

- knowledge_id: gcn_contra_ab
  type: claim
  content: "A 与 B 不可同真"
  metadata:
    helper_kind: contradiction_result
    helper_origin: structural
    helper_source: compiler
    generated_by_operator: contradiction
    canonical_name: not_both_true(gcn_a,gcn_b)

- operator_id: gco_01
  operator: contradiction
  variables: [gcn_a, gcn_b]
  conclusion: gcn_contra_ab
```

这里的 `gcn_contra_ab`：

- 是 claim
- 可以被未来的工作引用
- 可以在新的 formalization 中继续被讨论

### 9.2 语义型 `prediction` helper claim

```yaml
- knowledge_id: gcn_gr
  type: claim
  content: "广义相对论成立"

- knowledge_id: gcn_mercury_shift
  type: claim
  content: "水星近日点发生额外进动"

- knowledge_id: gcn_pred_01
  type: claim
  content: "若广义相对论成立，则应观察到水星近日点额外进动"
  metadata:
    helper_kind: prediction
    helper_origin: semantic
    helper_source: author
    canonical_name: prediction(model=gcn_gr,target=gcn_mercury_shift)
```

这个 `prediction` helper claim：

- 应显式进入 `knowledges`
- 可以拥有独立 prior
- 可以被后续 abduction / equivalence / contradiction 等结构引用

## 10. 当前开放点

当前仍未完全定稿的点：

- `implication` 是否长期保留“`conclusion = consequent`”这一特例，还是未来也关系命题化
- 哪些结构型 helper claim 在默认 policy 下允许独立 prior
- semantic helper catalog 是否要继续扩展到 observation-match、measurement-bridge 等更细粒度类型
