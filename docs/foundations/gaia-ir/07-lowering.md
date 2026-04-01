# Lowering — Backend 消费契约

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 被后端消费时的 lowering 边界。它不规定某个具体后端算法的内部实现，但规定 backend-facing 的结构语义。

## 目的

Gaia IR 定义的是**结构契约**。  
Lowering 定义的是：一个后端在消费 Gaia IR 时，应如何把这些结构解释成可执行的 runtime graph / runtime program。

当前默认后端是 BP，但本文件不把 lowering 绑定到 BP 内部实现。  
BP 的具体运行时图和消息传递细节见 [../bp/inference.md](../bp/inference.md)。

## 1. 输入与输出

一个 lowering 过程的最小输入是：

- 一个 `LocalCanonicalGraph`
- 一个展开策略（哪些 Strategy 保持折叠，哪些进入内部结构）

对**需要概率参数**的运行时后端，常见还会额外输入：

- 与 graph 匹配的参数输入
- `ResolutionPolicy`
- `prior_cutoff`
- backend 自己的运行配置

对采用 [06-parameterization.md](06-parameterization.md) 的 probabilistic backend，规范输入是 `LocalCanonicalGraph + Parameterization`。

lowering 的输出不是新的 Gaia IR，而是**后端的数据表示**。
在当前 BP 后端里，这个输出是 `FactorGraph`（variable nodes + factor nodes 的二部图）；在其他后端里，也可以是别的表示。

## 2. 基本原则

### 2.1 Gaia IR 不等于 Runtime Graph

后端**不直接**在原始 Gaia IR 对象上运行。

Gaia IR 提供：

- 命题节点
- 推理声明
- 确定性结构约束
- FormalExpr 内部节点封装边界

runtime graph 则由后端按自己的执行模型构造。

backend 在 runtime 层保留的是**对象 identity**（如 Knowledge QID、Strategy `lcs_...`），不是 `content_hash`。`content_hash` 主要服务于去重和匹配，不应替代 runtime node identity。

### 2.2 Lowering 是消费，不是反向定义

backend 可以消费 Gaia IR，但 backend 的当前实现细节**不反向定义** Gaia IR 本体。

也就是说：

- Gaia IR 先定义结构语义
- lowering 再把这些结构映射到某个 backend

## 3. Lowering 输入语义

### 3.1 Knowledge

lowering 时：

- `claim` 是潜在的 runtime variable 候选
- `setting` / `question` 默认不作为普通概率变量进入 runtime graph

若某个后端只对可取真值命题建变量，那么：

- `claim` 进入 runtime variable 集
- `setting` / `question` 只作为编译辅助信息存在

### 3.2 Operator

Operator 表示确定性结构约束。

lowering 时，后端应将其解释为：

- 一个确定性约束
- 或一个等价的硬因子 / 结构规则

`Operator.conclusion` 是该 Operator 的标准结果 claim。  
对于关系型 Operator，这通常是结构型 helper claim。

### 3.3 Strategy

Strategy 是不确定性承载层。lowering 时，需要决定：

- 保持折叠
- 递归展开
- 或部分展开

当前 contract 下，Strategy 的 lowering 由其形态决定。

## 4. 三种形态的 Lowering

### 4.1 Strategy（叶子）

叶子 Strategy 直接 lower 为一个 backend-level probabilistic support unit。

典型情形：

- `infer`
- `noisy_and`
- 未再细化的 leaf Strategy（`toolcall` / `proof` 未引入）

它们的外部行为由：

- `premises`
- `conclusion`
- parameterization 层提供的外部参数

共同决定。

### 4.2 CompositeStrategy

CompositeStrategy 本身不是新的语义家族，而是分解容器。

lowering 时有两种合法方式：

- **折叠**：把整个 CompositeStrategy 当成一个单元消费
- **展开**：递归 lower `sub_strategies`

具体选哪种，由 backend 的展开策略决定。

> **Open question：CompositeStrategy 折叠时的参数来源。** 当前 contract 只定义了参数化 leaf Strategy（读 StrategyParamRecord）和 FormalStrategy（从 FormalExpr + claim prior 导出）的折叠路径。CompositeStrategy 折叠为单个单元时的条件概率来源尚未定义——是需要显式 StrategyParamRecord，还是从 sub_strategies 自动 marginalize，或禁止折叠？待后续设计明确。

### 4.3 FormalStrategy

FormalStrategy 表示一个已经给出确定性 skeleton 的命名推理单元。

FormalExpr 内部节点是严格私有的（禁止外部引用），因此 FormalStrategy 总是可以被折叠。lowering 时有两种方式：

- **折叠**：对私有中间变量做变量消去，整个 FormalStrategy 等效为 P(conclusion | premises)
- **展开**：进入 `formal_expr`，把内部 Operator 结构显式 lower

两种方式都合法，选择由 `expand_set` 决定。

对 `abduction` 这类带自动补齐 interface claim 的命名策略，这两条路都必须保留同一语义：

- **折叠**：把 `Obs`、`AlternativeExplanationForObs` 等接口 claim 与内部 helper skeleton 一起消去为一个等效条件单元
- **展开**：保留 public interface claim，显式 lower `disjunction` / `equivalence` 等 helper 结构

## 5. FormalExpr 内部节点与 Lowering

FormalExpr 内部节点是严格私有的（禁止外部引用），因此 FormalStrategy 总是可以被折叠。封装规则和概率语义见 [04-helper-claims.md §3](04-helper-claims.md#3-formalexpr-内部-claim-的封装) 和 [06-parameterization.md](06-parameterization.md)。

Lowering 时，后端对每个 FormalStrategy 可以选择：

- **折叠**：对私有中间变量做变量消去，整个 FormalStrategy 等效为 P(conclusion | premises)
- **展开**：保留内部节点作为 runtime node，在展开后的图上推理

两种方式都合法。选择哪种由 `expand_set` 决定

## 6. 参数层如何参与 Lowering

Lowering 只消费参数层，不定义参数层。

当前 contract 下：

- 参数化 Strategy 从 `StrategyParamRecord` 读取外部条件参数
- 普通 claim 从 `PriorRecord` 读取外部 prior
- 结构型 helper claim **禁止**携带独立 PriorRecord（见 [04-helper-claims.md §6](04-helper-claims.md#6-与-parameterization-的关系)）

对直接 FormalStrategy：

- 不读取独立的持久化 strategy-level `conditional_probabilities`
- 其折叠行为若需要等效条件视图，应从内部结构与相关 interface claim prior 导出

## 7. 当前 BP 后端的特化

对当前 BP 后端：

- lowering 的结果是 `FactorGraph`
- `claim` 节点进入 variable 集
- Strategy / Operator 被解释成 factor 或约束
- 具体的 runtime graph 形状、消息传递与诊断字段见 [../bp/inference.md](../bp/inference.md)

本文件只规定：

- 哪些 Gaia IR 结构允许折叠/展开
- 哪些节点允许被局部消去
- 哪些 identity 必须在 lowering 后保留

## 8. 与其他文档的分工

- [02-gaia-ir.md](02-gaia-ir.md)：定义 Gaia IR 本体结构
- [04-helper-claims.md](04-helper-claims.md)：定义结构型 helper claim 的 public/private 边界
- [06-parameterization.md](06-parameterization.md)：定义参数输入层
- [05-canonicalization.md](05-canonicalization.md)：定义 `content_hash` 角色，以及 Gaia IR 为公共 canonicalization / cross-package review-curation 保留哪些信息
- [../bp/inference.md](../bp/inference.md)：定义当前 BP backend 如何把 lowering 结果跑起来

## 9. 当前仍待细化的点

- 不同 backend 是否共享同一套 `expand_set` 语义
- FormalStrategy 折叠为单个等效条件行为时的标准导出算法
- 关系型 Operator result claim 在不同 backend 中是否始终显式保留为 runtime node
