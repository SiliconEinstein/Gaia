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

- 一个 `LocalCanonicalGraph` 或 `GlobalCanonicalGraph`
- 与之匹配的参数输入
- 一个展开策略（哪些 Strategy 保持折叠，哪些进入内部结构）

对需要参数的运行时后端，常见还会额外输入：

- `ResolutionPolicy`
- `prior_cutoff`
- backend 自己的运行配置

lowering 的输出不是新的 Gaia IR，而是**后端私有的运行时表示**。  
在当前 BP 后端里，这个输出是 `FactorGraph`；在其他后端里，也可以是别的 runtime graph。

## 2. 基本原则

### 2.1 Gaia IR 不等于 Runtime Graph

后端**不直接**在原始 Gaia IR 对象上运行。

Gaia IR 提供：

- 命题节点
- 推理声明
- 确定性结构约束
- public/private helper 边界

runtime graph 则由后端按自己的执行模型构造。

backend 在 runtime 层保留的是**对象 identity**（如 `gcn_...` / `lcn_...`），不是 `content_hash`。`content_hash` 主要服务于 canonicalization 和查询，不应替代 runtime node identity。

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
- 未再细化的 leaf `toolcall` / `proof`

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

### 4.3 FormalStrategy

FormalStrategy 表示一个已经给出确定性 skeleton 的命名推理单元。

lowering 时也有两种方式：

- **折叠**：把它消费成一个等效的 backend-level support unit
- **展开**：进入 `formal_expr`，把内部 Operator 结构显式 lower

这两种方式都合法，但折叠存在一个关键前提：

- 只有当其内部私有中间节点可以安全被 marginalize 时，才允许把整个 FormalStrategy 折成单个黑盒行为

## 5. Public / Private 节点与 Lowering

### 5.1 私有中间节点

一个节点若是某个 FormalStrategy 的私有内部节点，则：

- 它可以在 lowering 后仍然保留为 backend runtime node
- 也可以在满足条件时被该 Strategy 局部 marginalize 掉

关键是：这种处理只在该 Strategy 的封装边界内部合法。

### 5.2 公共节点

一个节点若已提升为公共 `claim`，则：

- 后端不能再把它当作“只属于单个 Strategy 的可随意消去节点”
- 若别的结构也引用它，它就必须在 lowering 后保持为可共享的 runtime identity

这条规则同样适用于公共 helper claim。

## 6. 参数层如何参与 Lowering

Lowering 只消费参数层，不定义参数层。

当前 contract 下：

- 参数化 Strategy 从 `StrategyParamRecord` 读取外部条件参数
- 普通 claim 从 `PriorRecord` 读取外部 prior
- 结构型 helper claim 默认不作为新的独立 prior 输入口

对直接 FormalStrategy：

- 不读取独立的持久化 strategy-level `conditional_probabilities`
- 其折叠行为若需要等效条件视图，应从内部结构与相关显式 claim prior 导出

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
- [05-canonicalization.md](05-canonicalization.md)：定义 local/global 身份映射
- [../bp/inference.md](../bp/inference.md)：定义当前 BP backend 如何把 lowering 结果跑起来

## 9. 当前仍待细化的点

- 不同 backend 是否共享同一套 `expand_set` 语义
- FormalStrategy 折叠为单个等效条件行为时的标准导出算法
- 关系型 Operator result claim 在不同 backend 中是否始终显式保留为 runtime node
