# 第四章：概率编程语言

> **Status:** 研究调研（2026-04-03）
>
> 本章系统综述概率编程语言（Probabilistic Programming Languages, PPL）领域的代表性系统，分析它们与 Gaia 在架构设计、推理范式和应用领域上的异同。Gaia 不是一个通用 PPL——它以科学命题与推理策略为核心领域约束，换取在该领域内的结构化优势。

---

## 4.1 Stan (Carpenter et al., 2017)

### 架构

Stan 是当前最广泛使用的贝叶斯统计建模语言。其架构为：

```
Stan 程序（命令式 DSL）
  → 自动微分（reverse-mode AD）
    → HMC/NUTS 采样器（连续参数空间上的 Hamiltonian Monte Carlo）
```

Stan 程序由 `data`、`parameters`、`transformed parameters`、`model`、`generated quantities` 五个块组成。用户在 `model` 块中声明似然函数和先验分布，Stan 编译器将其转换为对数概率密度函数的梯度计算代码，再由 NUTS 采样器（No-U-Turn Sampler，一种自适应 HMC 变体）在连续参数空间上高效探索后验分布。

Stan 的核心技术优势在于自动微分。它实现了高性能的 reverse-mode AD 引擎，能够对任意可微的对数概率密度函数计算梯度。这使得 HMC 可以利用几何信息引导采样，远比传统的 Metropolis-Hastings 或 Gibbs 采样高效。

### Stan 擅长什么

Stan 在**连续参数估计**领域表现卓越：层次模型（hierarchical models）、广义线性模型、高斯过程、时间序列分析、生存分析等。它在社会科学（政治科学中的选举模型、心理学中的认知模型）、生态学（种群动态模型）、流行病学（疾病传播模型）等领域被广泛采用。Andrew Gelman 团队通过《Bayesian Data Analysis》教材和 Stan 文档，建立了一套完整的贝叶斯工作流方法论。

### 为什么 Stan 不适合 Gaia 的问题

Stan 与 Gaia 解决的是根本不同类别的问题。Stan 的变量是**连续参数**——回归系数、方差分量、超参数等。Stan 问的是 "how much?"——这个效应有多大？这个参数的后验分布是什么？

Gaia 的变量是**科学命题的二值真值**——"暗物质存在吗？""这个药物有效吗？"Gaia 问的是 "true or false, and how confident?"——这个命题为真的可信度是多少？给定新证据后，可信度如何更新？

更深层地说，Stan 操作在**参数空间**上：给定模型结构，估计模型参数。Gaia 操作在**命题空间**上：给定命题之间的推理关系，传播可信度。这两者的拓扑结构完全不同——Stan 的计算图是一个有向图模型（通常是树或简单结构），Gaia 的计算图是一个 factor graph（可能包含环路，需要 loopy BP）。

### Stan 对科学实践的影响

Stan 通过降低贝叶斯统计的门槛，实质性地改变了多个学科的研究实践。`brms`（R 语言前端）让研究者无需编写 Stan 代码即可拟合复杂的贝叶斯层次模型。Stan 社区发展出的贝叶斯工作流（先验预测检验、后验预测检验、LOO 交叉验证）成为方法论标准。

### Gaia 能否与 Stan 集成？

一个有吸引力的集成方式是：在单个 claim 的证据评估中使用 Stan 进行参数估计，然后将结果作为先验（prior）输入 Gaia。例如：一个 claim 声称 "药物 X 降低死亡率"，研究者用 Stan 对临床试验数据进行贝叶斯分析，得到效应量的后验分布 P(effect > 0) = 0.93，这个 0.93 就可以作为该 claim 在 Gaia 中的先验概率。这种分层架构——Stan 处理数据层的统计推断，Gaia 处理命题层的信念传播——在概念上是清晰的。

---

## 4.2 Gen (Cusumano-Towner et al., 2019)

### 架构

Gen 是 MIT 概率计算项目（Probcomp）开发的通用概率编程系统，其核心创新在于**模型与推理的分离**。

```
生成函数（Generative Function Interface）
  → 可编程推理（Programmable Inference）
    → 组合 MCMC、变分推理（VI）、重要性采样（IS）
```

Gen 定义了一个统一的**生成函数接口**（Generative Function Interface, GFI），任何实现该接口的对象都可以作为概率模型的构建块。GFI 要求实现四个核心操作：`simulate`（前向采样）、`generate`（条件生成）、`update`（增量更新）、`assess`（评估概率）。通过这个接口，Gen 实现了推理算法与模型表示的彻底解耦。

推理侧，Gen 提供了一系列可组合的推理原语：Metropolis-Hastings kernel、HMC kernel、变分推理目标、粒子滤波等。用户可以像拼积木一样组合这些原语，为不同的模型组件选择最适合的推理策略。

### 模型/推理分离与 Gaia 的 Lang/IR/BP 分层

Gen 的架构设计哲学与 Gaia 有深层的呼应。Gen 将"写模型"与"写推理"解耦：

| Gen | Gaia |
|-----|------|
| 生成函数（模型） | Gaia Lang（知识声明） |
| Generative Function Interface | Gaia IR（中间表示） |
| 可编程推理引擎 | BP 引擎 |

两者都追求**编译管线式架构**：前端声明"我们知道什么"，中间表示编码结构，后端执行推理。但 Gen 的前端是图灵完备的——你可以用任意 Julia 代码编写生成过程；Gaia 的前端是一个**受限 DSL**——你只能声明命题、逻辑算子和推理策略。这种限制是 Gaia 的关键设计选择。

### Gen 的 Choice Map 与 Gaia 的 Factor Graph

Gen 使用 **choice map** 作为其核心抽象：一个从地址（address）到值的嵌套映射，记录生成函数执行过程中的所有随机选择。Choice map 是 Gen 推理算法操作的对象——条件化、提议（proposal）、评估都通过 choice map 进行。

Gaia 使用 **factor graph** 作为 IR：Knowledge 节点是变量，Operator 和 Strategy 编译为因子。Factor graph 是 BP 推理的操作对象。

两者的本质区别在于：choice map 是一个**执行轨迹**的表示——它记录的是"生成过程经过了哪些随机选择"；factor graph 是一个**联合分布分解**的表示——它编码的是"哪些变量之间存在什么依赖关系"。Gen 的表示更通用（能表达任意生成过程），Gaia 的表示更结构化（每个因子都有明确的推理语义：这是一个 deduction？一个 abduction？一个 noisy-AND？）。

### 通用性与特化的权衡

Gen 可以表达任意概率模型：贝叶斯网络、隐马尔可夫模型、非参数模型、程序归纳模型。Gaia 只能表达一种特定类型的模型：科学命题之间的推理关系图。

这种约束是 Gaia 的**核心价值所在**。正因为 Gaia 限制了问题的形式——类型化命题（claim/setting/question）+ 命名推理策略（deduction/abduction/analogy/...）+ 特定的因子类型（SOFT_ENTAILMENT/CONJUNCTION/CONDITIONAL/...）——它才能提供通用 PPL 无法提供的东西：审查侧车（review sidecar）、知识包（package）版本管理、跨包信念传播、推理策略的语义标注。

---

## 4.3 Church (Goodman et al., 2008) 与 WebPPL

### "概率程序 = 生成模型" 范式

Church 是由 Noah Goodman 等人在 MIT 开发的概率编程语言，基于 Scheme（Lisp 方言），是第一个图灵完备的概率编程语言。Church 确立了概率编程领域的核心范式：**一个概率程序就是一个生成模型**。

```scheme
(define (coin-model)
  (define fair-coin (flip 0.5))
  (define weight (if fair-coin 0.5 (uniform 0.01 0.99)))
  (condition (equal? (flip weight) #t))
  weight)
```

这段 Church 程序既是一个"关于硬币的故事"（生成过程），又是一个概率模型（定义了联合分布）。通过 `condition` 语句施加约束，推理引擎（拒绝采样、MCMC 等）自动计算后验分布。

WebPPL 是 Church 的 JavaScript 继承者，由斯坦福大学认知科学实验室维护。WebPPL 在浏览器中运行，降低了概率编程的入门门槛。

### 认知科学应用

Church 和 WebPPL 在认知科学领域有独特的地位。probmods.org（"Probabilistic Models of Cognition" 在线教材）使用 WebPPL 作为教学工具，覆盖了：

- **心智理论**（Theory of Mind）：将对他人信念和意图的推理建模为概率程序的嵌套推理
- **因果推理**：将因果模型表示为生成过程，通过干预（intervention）进行反事实推理
- **概念学习**：将概念表示为概率程序，学习等同于程序归纳
- **语用学**（Rational Speech Acts）：将语言理解建模为说话者和听者之间的递归推理

### 过程式 vs 声明式

Church/WebPPL 与 Gaia 之间最根本的区别在于**表示方式**的不同：

- **Church 编写生成过程**：程序员描述"世界是如何生成的"——先采样一个参数，再根据参数生成数据，通过条件化数据反推参数。模型的结构隐含在代码的控制流中。
- **Gaia 声明命题和关系**：作者声明"我们知道什么、什么支持什么"——这是一个 claim，那是一个 setting，这个 claim 通过 deduction 策略从那些前提推出。模型的结构显式编码在 factor graph 的拓扑中。

这不仅是风格差异，而是**认识论立场**的差异。Church 追随的是**生成式认识论**——知识就是一个能产生观测数据的生成过程，学习就是推断生成过程的参数。Gaia 追随的是 **Jaynes 的概率即逻辑**——知识就是命题的可信度，推理就是命题之间可信度的传播。

### 哲学联系

尽管有上述差异，Church 和 Gaia 共享一个深层的哲学承诺：**推理就是概率推断**。两者都拒绝将推理还原为经典逻辑的真/假二值判断，都认为不确定性是推理的内在特征而非需要消除的噪声。但它们在不同的**抽象层次**上运作：Church 在计算过程层面进行概率推断（采样和条件化），Gaia 在命题网络层面进行概率推断（消息传递和信念更新）。

---

## 4.4 FACTORIE (McCallum et al., 2009)

### 架构

FACTORIE 是 UMass Andrew McCallum 团队开发的因子图编程框架，用 Scala 实现。

```
Scala 命令式因子图定义
  → Factor graph 数据结构
    → BP / MCMC / 在线学习
```

FACTORIE 的设计目标是为 NLP 任务提供高效的因子图工程系统。用户通过 Scala 代码命令式地定义变量、因子模板（factor template）和学习目标。因子模板是一种参数共享机制：同一模板的所有实例共享权重，通过足够统计量（sufficient statistics）进行在线学习。

### NLP 应用

FACTORIE 专为 NLP 设计，其典型应用包括：

- **命名实体识别**（NER）：标记因子 + 转移因子构成链式 CRF
- **共指消解**（Coreference Resolution）：实体提及之间的二元因子 + 聚类约束
- **依存句法分析**（Dependency Parsing）：弧头选择因子 + 树约束
- **关系抽取**：实体对之间的关系因子 + 全局约束

### FACTORIE 是与 Gaia 最接近的已有因子图工程系统

在所有相关系统中，FACTORIE 与 Gaia 在**工程层面**最为接近：两者都以 factor graph 作为核心数据结构，都支持 BP 推理，都面向特定领域。但它们的领域完全不同：FACTORIE 面向 NLP 序列标注和结构预测，Gaia 面向科学命题的信念传播。

### 详细对比

| 维度 | FACTORIE | Gaia |
|------|----------|------|
| **变量类型** | 任意离散/连续变量（标记、词、实体） | 二值命题变量（claim 为真/假） |
| **因子定义** | 程序员用 Scala 代码定义任意因子模板 | 受限为命名策略（deduction, abduction, ...）编译出的特定因子类型 |
| **参数来源** | 从标注数据中学习因子权重 | 领域专家声明先验概率和推理强度 |
| **图拓扑** | 程序员手动构建 | 从 Gaia Lang DSL 声明自动编译 |
| **推理** | BP + SampleRank（在线 MCMC 学习） | Loopy BP + Junction Tree + GBP |
| **知识表示** | 无——纯推理引擎 | 类型化命题 + 推理策略 + 知识包 |

核心区别在于 **Gaia 的约束是一种特性**。FACTORIE 允许你以编程方式构建任意因子图——这提供了最大灵活性，但也意味着因子图的结构没有语义约束。你可以构建一个"NER 标签序列"因子图，也可以构建一个"科学推理"因子图，FACTORIE 不关心它们之间的区别。

Gaia 则**强制你只能构建科学推理因子图**——每个变量必须是一个类型化命题（claim/setting/question），每个因子必须对应一个命名推理策略或逻辑算子。这种约束确保了**认识论结构**（epistemological structure）的存在：你不仅知道两个变量之间有依赖关系，还知道这种依赖是一个 "deduction"、一个 "abduction" 还是一个 "analogy"，每种都有不同的势函数语义。

### Gaia 可以从 FACTORIE 学到什么

- **高效因子图数据结构**：FACTORIE 使用紧凑的邻接表和因子模板索引，在百万级变量的图上仍能高效运行
- **增量推理**（Incremental Inference）：FACTORIE 的 SampleRank 支持在线学习和增量更新，这对 Gaia 的全局推理（LKM 层面，新包接入后的增量信念更新）有参考价值
- **因子模板**（Factor Templates）：参数共享机制可以启发 Gaia 对同类推理策略的参数化

---

## 4.5 Infer.NET (Microsoft Research, 2018)

### 架构

Infer.NET 是微软研究院开发的概率编程框架，其核心理念是**消息传递即编译**。

```
.NET 模型规约（C# API）
  → 模型编译器
    → 生成 C# 消息传递代码
      → 执行推理（EP / VMP / Gibbs）
```

用户通过 C# API 声明概率模型（变量、分布、因子），Infer.NET 编译器分析模型结构，为每个因子生成专用的消息更新 C# 代码。这些生成的代码执行 Expectation Propagation（EP）、Variational Message Passing（VMP）或 Gibbs 采样。

### 消息传递即编译

Infer.NET 的"编译"方法论与 Gaia 的管线在架构层面最为相似：

| Infer.NET | Gaia |
|-----------|------|
| C# 模型声明 → 编译器 → 生成消息传递代码 | Gaia Lang → 编译器 → Gaia IR → lowering → factor graph → BP |
| 编译时确定消息调度 | 运行时同步调度（当前），未来可能编译时优化 |
| 生成专用 C# 代码 | 通用 BP 引擎（NumPy 实现） |

Infer.NET 的编译方法有一个 Gaia 目前不具备的优势：**编译时消息调度优化**。Infer.NET 在编译时分析模型的因子图结构，确定最优的消息更新顺序，并生成专用代码。Gaia 当前使用同步调度（每次迭代更新所有消息），但 ForneyLab/RxInfer.jl（见 4.6 节）展示了自动调度生成的可行性。

### 与 Gaia 的关键区别

Infer.NET 是一个**纯推理库**——它没有知识表示层。用户用 C# 代码手动构建模型，Infer.NET 只负责推理。它不关心变量是什么（回归系数？分类标签？科学命题的真值？），不提供类型系统来约束模型结构，不提供知识包、审查流程或版本管理。

Gaia 的价值不仅在推理引擎，而在**完整的知识管线**：声明（Gaia Lang）→ 编译（compiler）→ 结构表示（Gaia IR）→ 参数化（parameterization）→ lowering → 推理（BP）→ 审查（review sidecar）→ 发布（registry）。Infer.NET 只覆盖这条管线中"推理"这一个环节。

---

## 4.6 ForneyLab / RxInfer.jl (Eindhoven, 2019+)

### 架构

ForneyLab（及其后继者 RxInfer.jl 和模型规约层 GraphPPL.jl）是荷兰 Eindhoven 理工大学 BIASlab 开发的因子图概率编程系统。

```
GraphPPL.jl（模型规约 DSL）
  → Forney-style factor graph
    → 自动消息传递调度生成
      → 响应式推理（RxInfer.jl）
```

### Forney-style Factor Graph

传统的 factor graph 中，节点分为变量节点和因子节点，边连接变量与因子。ForneyLab 使用 **Forney-style factor graph**（也称 Normal Factor Graph）——**边是变量，节点是因子**。这种 "对偶" 表示在信号处理领域更自然：信号沿边流动，每个节点执行一个计算操作。

Gaia 使用传统的因子图表示（Knowledge 是变量节点，Operator/Strategy lowering 后成为因子节点），但 Forney-style 表示的某些工程优势值得关注——特别是它天然适合流式消息传递。

### 自动消息传递调度

ForneyLab/RxInfer.jl 的核心贡献是**自动生成消息传递调度**（message passing schedule）。给定一个因子图：

1. 分析图结构，识别树部分和环路部分
2. 树部分使用精确消息传递（自叶向根再向叶的两遍扫描）
3. 环路部分使用迭代消息传递（loopy BP 或 structured VI）
4. 生成一个确定性的消息更新调度序列

**这是与 Gaia 的 "compile → factor graph → message passing" 管线最接近的已有系统。** 两者共享同一个宏观架构：高层声明 → 编译为因子图 → 消息传递推理。但 ForneyLab/RxInfer.jl 面向的领域是**信号处理和控制**：高斯消息（而非二值消息）、连续时间模型（而非离散命题网络）、在线流式推理（而非批量信念更新）。

### GraphPPL.jl：模型规约语言

GraphPPL.jl 是 RxInfer.jl 的模型规约层，提供 `@model` 宏定义因子图：

```julia
@model function linear_regression(n)
    a ~ Normal(0, 10)
    b ~ Normal(0, 10)
    for i in 1:n
        y[i] ~ Normal(a * x[i] + b, 1.0)
    end
end
```

这与 Gaia Lang 的声明式风格形成有趣对比：GraphPPL 使用概率分布语法（`~` 操作符），Gaia Lang 使用知识声明语法（`claim()`、`noisy_and()` 等）。两者都从高层声明编译为因子图，但声明的"语汇"完全不同——一个说"变量服从什么分布"，另一个说"命题之间有什么推理关系"。

### Gaia 可以从 ForneyLab/RxInfer.jl 学到什么

1. **自动消息调度生成**：Gaia 当前使用同步 loopy BP（每次迭代更新所有消息）。ForneyLab 展示了如何根据图结构自动生成更高效的调度——先处理树部分（精确），再迭代环路部分。这对大规模 factor graph（LKM 全局推理）尤其重要。
2. **响应式推理**：RxInfer.jl 使用 Reactive Extensions 实现流式推理——新观测到达时，只更新受影响的消息。这对 Gaia 的增量推理场景（新包接入后只更新相关区域的信念）有直接启发。
3. **混合消息类型**：RxInfer.jl 支持在同一个图中混合不同类型的消息（高斯、伯努利、分类分布等）。Gaia 当前只有二值消息 `[p(x=0), p(x=1)]`，但如果未来扩展到连续参数命题，混合消息框架将是必要的。

---

## 4.7 PGMax (Google DeepMind, 2023)

### 架构

PGMax 是 DeepMind 基于 JAX 开发的因子图推理库。

```
Python API（因子图规约）
  → JAX 编译
    → GPU 加速的 Loopy BP
      → 可微分 BP（梯度反传）
```

PGMax 利用 JAX 的 XLA 编译和自动微分能力，实现了 GPU 加速的 loopy BP。其核心创新是**可微分 BP**（Differentiable BP）——BP 的消息传递过程本身是可微的，因此可以将 BP 嵌入端到端的深度学习管线中，通过反向传播学习因子图的参数（势函数权重）。

### 纯推理引擎

PGMax 是一个纯推理引擎——没有模型规约语言，没有知识表示层，没有知识管理。用户直接用 Python API 构建因子图（变量列表 + 因子列表 + 势函数），然后调用 BP。

### 对 Gaia 的潜在价值

PGMax 对 Gaia 的价值在于**计算后端**。Gaia 当前的 BP 引擎是纯 NumPy 实现（`gaia/bp/factor_graph.py`），在小规模图上性能足够，但 LKM 层面的全局推理可能涉及数十万节点。PGMax 提供了一条清晰的 GPU 加速路径：

1. 将 Gaia IR lowering 后的 factor graph 转换为 PGMax 的因子图格式
2. 使用 PGMax 执行 GPU 加速的 loopy BP
3. 将推理结果（边际信念）回传给 Gaia

此外，PGMax 的可微分 BP 为**从数据中学习因子参数**提供了可能。当前 Gaia 的 SOFT_ENTAILMENT 参数 `p1`、`p2` 由领域专家手动设定，未来可以通过可微分 BP 从已标注的知识库中自动学习。

---

## 4.8 Figaro (Charles River Analytics)

### 架构

Figaro 是 Charles River Analytics 开发的面向对象概率编程系统，用 Scala 实现。

```
Scala 面向对象模型定义（Element 类层次）
  → Factor graph 构建
    → BP / 变量消除 / MCMC
```

Figaro 的设计理念是将概率编程嵌入一门成熟的面向对象语言中。每个随机变量是一个 `Element` 对象，Element 之间通过函数式组合构建复杂模型。Figaro 支持多种推理算法：belief propagation、变量消除（variable elimination）、Metropolis-Hastings MCMC，以及它们的组合。

### 通用性与局限

Figaro 是一个通用 PPL——不针对任何特定领域。它的 factor graph + BP 推理与 Gaia 在机制上相似，但不提供任何领域特化：没有类型化命题、没有推理策略分类、没有知识包管理、没有审查流程。Figaro 证明了"面向对象 + 因子图 + BP"的工程可行性，但其通用性意味着它无法为科学推理提供 Gaia 所具有的结构化保证。

---

## 4.9 总结：Gaia 在 PPL 版图中的位置

概率编程领域可以沿两个轴组织：

- **横轴：变量类型**——从连续参数（Stan、PyMC）到离散结构（FACTORIE）到二值命题（Gaia）
- **纵轴：通用性**——从图灵完备（Gen、Church）到领域特化（FACTORIE → NLP，Gaia → 科学推理）

```
         通用性 ↑
              |
    Gen/Church ●──────────────── Figaro ●
              |                          |
              |                          |
              |    Infer.NET ●           |
              |                          |
              |           ForneyLab ●    |
              |                          |
              |                 PGMax ●  |
              |                          |
    Stan/PyMC ●              FACTORIE ●  |
              |                          |
              |                   Gaia ● |
              |                          |
         特化 ↓───────────────────────────→
         连续参数                    离散命题
```

### 关键定位

**Gaia 不是通用 PPL。** 它不试图与 Stan、Gen 或 Church 竞争通用建模能力。Gaia 以**牺牲通用性**换取**领域特化的结构化优势**：

1. **类型化命题**：每个变量都是一个科学命题（claim/setting/question），而非匿名的随机变量。这使得知识库具有自解释性——你不需要阅读代码就能理解每个变量的含义。

2. **命名推理策略**：每个因子都对应一个命名的推理策略（deduction, abduction, analogy, elimination, ...），而非匿名的势函数。这使得推理过程可审计——你不仅知道信念更新了，还知道**为什么**更新（因为这条 deduction 链传播了新证据）。

3. **审查侧车**（Review Sidecar）：每个推理策略都可以附带结构化的审查报告，记录推理的合理性评估。这在通用 PPL 中没有对应物——Stan 不会质疑你的模型是否合理，它只负责采样。

4. **知识包**（Knowledge Package）：模型不是一段程序，而是一个可版本化、可发布、可审查的知识容器。这对应的是科学出版的工作流，而非软件开发的工作流。

5. **编译管线**：Gaia Lang → Gaia IR → Factor Graph → BP，每一层都有明确的契约和校验（validation）。这种分层编译架构在 PPL 领域中只有 ForneyLab/RxInfer.jl 可以比拟，但后者面向信号处理而非科学推理。

### 与最接近系统的精确距离

- **FACTORIE**：共享"因子图 + BP"核心，但 FACTORIE 允许任意因子图而 Gaia 强制认识论结构。FACTORIE 面向 NLP，Gaia 面向科学推理。
- **Infer.NET**：共享"编译式消息传递"理念，但 Infer.NET 是纯推理库，无知识表示层。
- **ForneyLab/RxInfer.jl**：共享"DSL → 因子图 → 消息传递"完整管线，但面向信号处理（高斯消息、连续变量），而 Gaia 面向科学命题（二值消息、离散命题）。
- **PGMax**：共享"loopy BP"推理算法，但 PGMax 是纯计算后端，可能成为 Gaia 的 GPU 加速组件。

在整个 PPL 版图中，Gaia 占据一个独特的生态位：**面向科学命题的、带有完整知识管理流程的、基于 factor graph + BP 的领域特化推理系统**。没有任何已有 PPL 同时具备这三个特征。
