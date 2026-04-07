# Gaia 新颖性分析

> **Status:** 参考文档（非规范层文档）
>
> 本文档逐维度分析 Gaia 在现有系统中的定位与新颖性，并附全景对比表和最近系统差异总结。

---

## 1. 新颖性逐维度分析

### 1.1 类型化科学命题 DSL（claim / setting / question / action）

Gaia 提供了一套面向科学知识形式化的 Python 内嵌 DSL（`gaia.lang`），其核心设计是将科学文本中的命题按认识论角色划分为三种类型：**claim**（可判真的科学断言，唯一携带先验概率并参与信念传播的类型）、**setting**（背景设定，提供上下文但不携带概率）、**question**（开放探究，记录研究方向但不参与推理）。这种类型划分不是任意的标签系统——它直接决定了后续编译和推理的行为：只有 claim 进入因子图成为变量节点，setting 和 question 仅作为结构性元数据参与图拓扑但不接收或发送 BP 消息。此外，claim 进一步区分为封闭命题（所有变量已绑定）和全称命题（含量化参数，可通过 deduction 实例化为封闭命题），使得 DSL 能自然表达科学规律与其具体实例之间的关系。

现有系统中，**ProbLog** 提供了 probabilistic facts 和 logical rules 的统一语言，但它是通用概率逻辑编程语言，不区分命题的认识论角色——所有 probabilistic fact 在语义上是平等的，没有 "这是背景假设" 和 "这是可判真的科学断言" 的内建区分。**MLN（Markov Logic Networks）** 将一阶逻辑公式与权重结合，但其基本单元是带权逻辑公式而非类型化命题。**Argdown** 作为论证编著语言区分了 statement 和 argument，但这是论证结构的区分，而非面向概率推理的认识论类型系统。**Nanopublications** 使用 assertion + provenance + publication info 的三层结构，但这是发布格式而非编著语言，不内建类型化命题声明。**AIF（Argument Interchange Format）** 区分了 inference nodes、conflict nodes 和 preference nodes，但这是论证图的本体分类，不直接映射到概率推理中的变量类型。

Gaia 的新颖性在于：将科学命题的**认识论类型**直接编码到 DSL 层面，并让这种类型在编译管线中产生确定性的结构后果——claim 成为 BP 变量，setting/question 不参与概率推理。这不是事后标注或元数据层的分类，而是语言级别的一等公民区分，直接影响编译目标（Gaia IR）和推理引擎的行为。在现有文献中，没有一个系统在同一套 DSL 中同时实现了科学命题的认识论类型化和面向因子图编译的语义约束。

### 1.2 命名推理策略编译为特定 factor 结构

Gaia 的核心设计之一是将 Polya 和 Jaynes 识别的推理模式——演绎（deduction）、溯因（abduction）、类比（analogy）、外推（extrapolation）、排除法（elimination）、分情况讨论（case analysis）、数学归纳（mathematical induction）——作为一等公民的 **命名推理策略（named reasoning strategies）** 暴露在 DSL 中，并在编译时将每种策略确定性地展开为特定的因子结构。例如：deduction 展开为 conjunction + implication（所有前提合取后严格蕴含结论，p1=1, p2=0.5）；abduction 展开为 disjunction + equivalence（假说与替代解释的析取等价于观测，当替代解释的先验较低时假说后验上升）；analogy 展开为 conjunction + implication，其中 bridge claim 作为接口命题携带独立先验，桥接先验越低类比越弱。每种策略的展开模板都有严格的数学推导：从 Jaynes 的 Bayes 定理和 Cox 公理出发，推导出每种推理模式的微观命题网络结构及其有效条件概率参数 (p1, p2)。

在现有系统中，**ASPIC+** 框架定义了严格规则和可废止规则两类推理结构，并允许规则之间的攻击和偏好，但它是论证理论框架，不编译到概率因子图，也没有把不同推理模式映射到不同的 factor 拓扑。**Epistemic Graphs**（Polberg & Hunter 2018 及后续工作）扩展了论证图使其能表达认知不确定性，支持不同强度的支持/攻击关系，但推理是在论证图上直接进行的语义评估，而非编译到 factor graph 后运行 BP。**DeepDive** 将知识库构建问题分解为特征提取、远程监督和概率推理，使用 factor graph + Gibbs sampling 做推理，但其 factor 结构由用户手写的 Datalog 规则生成，不提供预定义的推理策略模板。**ProbLog** 的推理策略隐含在 Prolog 风格的逻辑规则中——每条规则就是一种推理路径，但没有将 "这是溯因" 或 "这是类比" 作为语义标签显式暴露给用户。**Stewart & Buehler (2026)** 则强调高阶科学关系的**超图表示**与 agentic traversal，说明 pairwise KG 对科学知识并不充分，但它并未进入 Gaia 式的 factor graph + BP 推理范式。

Gaia 的新颖性在于：将科学推理中的经典推理模式**从认识论概念提升为编译器原语**。用户在 DSL 中声明 `abduction(observation=obs, hypothesis=hyp)`，编译器自动展开为 disjunction + equivalence 的确定性 operator skeleton，生成 helper claims 和 interface claims，并将结果写入 Gaia IR。这个展开是确定性的、可审计的、有数学推导支撑的。在现有系统中，推理策略要么是隐式的（ProbLog 的规则、MLN 的公式），要么是论证理论中的标签（ASPIC+ 的严格/可废止规则），没有一个系统将命名推理策略编译为有特定因子拓扑结构的 factor graph。

### 1.3 Jaynes 概率即逻辑的软件实现

Gaia 的理论根基是 Jaynes 的"概率即逻辑"纲领：概率不是频率统计量，而是对命题合理性的信念度量度；Cox 定理证明这是唯一自洽的似然推理系统。Gaia 将这一纲领工程化为一个完整的软件栈：DSL 层让用户声明命题和推理关系，IR 层编码推理超图的拓扑结构（无概率），参数化层独立提供先验和条件概率，BP 层在因子图上运行消息传递计算后验。整个系统严格遵循 Jaynes 的原则：所有概率都是条件概率（依赖于当前证据状态），Cromwell 规则禁止将经验命题的先验设为 0 或 1（所有概率被钳制到 [eps, 1-eps]），矛盾不是系统崩溃而是证据冲突（contradiction 作为一等 operator，通过 BP 自动让弱证据一方让步），MaxEnt 作为缺省先验选择原则（无额外信息时 p=0.5）。

在现有系统中，**Stan**、**Gen**、**Church/WebPPL** 和 **Infer.NET** 都是概率编程语言，但它们建模的是**统计概率**——随机变量上的分布，用于从数据推断参数。Gaia 建模的是**认知概率**——对命题真值的信念度。这是 Jaynes 在其著作中反复强调的关键区分：统计概率的对象是可重复事件的频率，认知概率的对象是对特定命题的合理性评估。Stan 和 Gen 无法自然地表达"广义相对论是正确的概率是多少"这类问题，因为这不是可重复实验。**ForneyLab / RxInfer.jl** 是基于 Forney-style factor graph 的消息传递推理框架，与 Gaia 在算法层面最接近（都使用 factor graph + BP），但它们面向信号处理和控制领域的连续值推理，不面向二值命题的科学推理。**BLOG** 是一种高层概率知识表示语言，处理 identity uncertainty 和 open-universe 模型，但同样面向统计建模而非 Jaynes 式的命题信念推理。

Gaia 的新颖性在于：它可能是 Jaynes "probability as logic" 纲领的**第一个完整软件实现**——不是将 Jaynes 的思想作为概率编程语言的哲学背景，而是将其作为系统架构的直接驱动力。Robot 隐喻（Jaynes 的思想实验）直接映射为 Gaia 的两层架构（内容层由外部智能体处理 + 图结构层由 Robot/BP 引擎自动计算），构造/验证分离直接映射为 DSL 编著与 BP 推理的独立性，弱三段论直接映射为 SOFT_ENTAILMENT 因子的消息传递行为（p1+p2 > 1 时满足全部四个弱三段论）。在已有文献和软件系统中，Jaynes 的思想通常被引用为哲学动机，但很少被工程化为一个端到端的命题推理系统。

### 1.4 版本化知识包模型 + 跨包引用

Gaia 将知识组织为**包（package）**——一个标准的 Python 库，遵循 semver 版本语义（PATCH: 元数据修正，MINOR: 新增知识但导出接口不变，MAJOR: 语义变更或删除）。包有唯一标识（UUID + QID namespace），导出的知识节点通过 `__all__` 机制控制可见性（exported / public / private 三级），跨包引用通过标准 Python import 实现——在 `pyproject.toml` 中声明依赖包，在代码中 `from other_package import some_claim`，编译时被引用的知识保留其 foreign QID，不会被铸造为本地新身份。整个包模型借鉴了编程语言的模块系统（Julia 的三层命名约定、Rust 的 crate 模型、Python 的 PyPI 分发），但应用于知识表示领域。

现有知识管理系统中，**Nanopublications** 提供了最小发布单元和 provenance 追踪，但没有包级别的版本化和模块化组织——每个 nanopub 是独立的发布单元，没有 "一组 nanopubs 构成一个包" 的结构概念。**RDF / OWL** 生态有 ontology versioning 的实践（如 OWL versionIRI），但这是本体论版本化，不是知识推理包的版本化。**Lean 的 mathlib** 有类似的模块化形式知识管理（定义、定理、模块、依赖），但面向确定性证明，没有概率语义。**MMT / OMDoc** 提供了理论级别的模块化知识管理（theory、view、morphism），但不面向概率推理包。**ProbLog**、**MLN** 和其他概率逻辑系统通常将知识库视为单一的规则集合，没有包级别的版本化和跨包引用机制——规则之间的引用是全局的，不区分 "本包定义" 和 "引用外部包的知识"。

Gaia 的新颖性在于：将**编程语言的包管理实践**（版本化、依赖声明、可见性控制、注册中心）引入知识表示领域，并与概率推理语义深度集成。跨包引用不仅仅是文本引用——被引用的知识在本地因子图中作为外部 occurrence 参与 BP 推理，在全局图中通过共享的 schema 节点实现跨包证据传播。这种"知识即代码、包即模块、引用即依赖"的设计理念在概率知识管理领域是全新的。

### 1.5 Review sidecar（不同审稿人赋不同先验）

Gaia 将概率参数化与图结构显式分离：Gaia IR 编码推理超图的拓扑结构（什么连接什么），完全不含概率值；概率参数（先验、条件概率）由独立的 **Review sidecar** 提供。每个 sidecar 是一个 Python 模块，导出一个 `ReviewBundle`，其中包含对各个 claim 的先验评估（`review_claim(evidence, prior=0.9, judgment="strong", justification="...")`)）和对各个策略的条件概率评估（`review_strategy(support, conditional_probability=0.85, ...)`）。关键设计是：同一个知识包可以有多个 review sidecar——不同的审稿人（人类、LLM agent、或算法）可以对同一套推理结构赋予不同的先验和条件概率。`gaia infer --review <name>` 选择使用哪个 sidecar 运行推理，全局图中则通过 resolution policy 从多条参数记录中解析出最终值。

在现有系统中，概率参数通常与模型结构绑定在一起。**Stan** 和 **Gen** 中的参数是模型的组成部分，由数据驱动的后验推断确定——不存在"多个审稿人对同一模型赋不同先验"的概念。**ProbLog** 中的概率标注（`0.7::fact`）直接写在程序中，是单一来源的。**MLN** 的权重通过训练学习，同样是单一来源。**DeepDive** 的因子权重也是从数据中学习的。**Epistemic Graphs** 允许不同的认知主体对同一论证图持有不同的评估，这在方向上最接近 Gaia 的 review sidecar 概念，但 Epistemic Graphs 是理论框架，没有对应的工程化实现和包级别的审查工作流。学术同行评审系统（如 OpenReview 的评分系统）收集多个审稿人的评分，但评分不直接驱动概率推理——它们是定性判断而非因子图的参数输入。

Gaia 的新颖性在于：将**参数化与结构的分离**和**多审稿人参数化**作为系统的一等架构原则。这不仅是技术便利（方便切换参数来比较不同视角的推理结果），更反映了 Jaynes 框架的认识论立场——概率是条件概率，条件化在不同的证据状态（不同审稿人的评估）上产生不同的后验。在全局图中，同一个变量或因子可以有来自不同来源的多条参数记录，resolution policy 负责解析。这种设计在概率推理系统中是独特的。

### 1.6 多算法 BP 推理引擎（JT / GBP / loopy BP 按 treewidth 自动选择）

Gaia 的推理引擎（`gaia.bp.engine.InferenceEngine`）实现了三种消息传递算法的自动选择：**Junction Tree (JT)** 用于 treewidth <= 15 的图（精确推理，O(n * 2^w)）；**Generalized Belief Propagation (GBP)** 用于 15 < treewidth <= 30 的图（region decomposition，近似精确）；**loopy BP** 用于 treewidth > 30 的大规模稠密图（近似推理，带 damping 和收敛诊断）。此外还支持 brute-force exact inference（<= 26 变量）用于测试验证。选择逻辑基于对因子图 treewidth 的快速估计（O(n^2)），用户也可强制指定算法。所有算法共享同一套 factor potential 函数（六种确定性算子 + SOFT_ENTAILMENT + CONDITIONAL），共享 Cromwell 规则、damping、收敛判定。诊断输出包括信念轨迹历史（belief_history）和振荡检测（direction_changes），后者是冲突证据的信号。

在现有系统中，通用概率推理库通常只提供单一推理算法或由用户手动选择。**Infer.NET** 提供了 EP（Expectation Propagation）、VMP（Variational Message Passing）和 Gibbs sampling 等算法，用户需手动选择。**ForneyLab / RxInfer.jl** 专注于 Forney-style factor graph 上的消息传递，支持 BP 和变分推理，但面向连续值信号处理而非二值命题。**Stan** 使用 HMC/NUTS（连续参数空间的 MCMC），**PyMC3** 使用多种 MCMC sampler——这些都不是 BP 范畴的算法。**libDAI**（Mooij 2010）是最接近的通用因子图推理库，实现了 BP、JT、GBP、HAK 等多种算法，并支持自动选择，但它是通用 C++ 库，不面向科学知识推理的领域语义。

Gaia 的新颖性不在于单个推理算法的发明（JT、GBP、loopy BP 都是成熟的算法），而在于将**多算法自动选择**与**面向科学推理的因子图语义**集成。Gaia 的因子图不是任意的概率图模型——它由 Gaia IR 经 lowering 产生，因子类型由推理策略的编译结果确定，势函数由 Jaynes 框架的弱三段论推导确定。推理引擎在这种语义特定的因子图上自动选择最优算法，无需用户了解 treewidth 或算法细节。

### 1.7 发布 pipeline（compile -> check -> infer -> register）

Gaia 定义了一条完整的知识包生命周期管线：`gaia init`（脚手架）-> `gaia add`（添加依赖）-> 编写 DSL 代码 -> `gaia compile`（DSL -> IR，确定性编译，无网络访问）-> `gaia check`（命名规范、IR 结构校验、制品新鲜度检查）-> `gaia infer --review <name>`（加载 review sidecar，lowering 到 factor graph，运行 BP，输出 beliefs.json）-> `git tag` -> `gaia register`（生成 registry 元数据，通过 GitHub PR 提交到官方注册中心）。这条管线借鉴了现代软件包发布的最佳实践——版本标签、制品哈希完整性校验、注册中心 PR 审查——但应用于知识包而非代码包。

在现有系统中，**Nanopublications** 有发布工作流（创建 assertion → 添加 provenance → 签名 → 发布到 nanopub 服务器），但这是单向发布流程，不包含编译、校验和推理步骤。**Lean 的 mathlib** 有提交流程（PR → CI 检查 → 审查 → 合并），类似于 Gaia 的 register → PR → CI → 合并，但面向确定性证明。概率逻辑系统（ProbLog、MLN、PSL、DeepDive）通常没有定义标准化的知识发布管线——用户编写规则，运行推理，获得结果，但没有"编译 → 校验 → 参数化 → 注册"的结构化工作流。**学术出版系统**（期刊投稿 → 同行评审 → 修订 → 接受/拒绝）在工作流层面最接近 Gaia 的 review/publish 模型，但这些系统不处理形式化的推理结构和概率推理。

Gaia 的新颖性在于：将**软件工程的 CI/CD 实践**和**学术出版的同行评审流程**融合到一个面向概率知识的发布管线中。编译步骤确保 DSL 声明被规范化为机器可读的 IR；校验步骤确保结构完整性；推理步骤提供信念预览让作者在发布前评估自己的推理结构；注册步骤通过 PR 机制引入社区审查。这种端到端的知识发布管线在现有系统中没有对应物。

---

## 2. 全景对比表

| 系统 | 年份 | 知识表示 | 类型化命题 | 命名推理策略 | 编译目标 | 推理方法 | 参数来源 | 不确定性表示 | 包模型 | 审稿系统 |
|------|------|---------|-----------|-------------|---------|---------|---------|-------------|-------|---------|
| **Gaia** | 2024- | 类型化命题超图（claim/setting/question + operator + strategy） | claim/setting/question 三类，claim 唯一携带概率 | deduction/abduction/analogy/extrapolation/elimination/case_analysis/math_induction，编译时展开为 operator skeleton | Gaia IR -> factor graph（variable + factor 二部图） | JT/GBP/loopy BP 按 treewidth 自动选择 | Review sidecar（多审稿人独立赋参数） | 二值命题先验 + 条件概率，Cromwell 规则 | 版本化 Python 包 + PyPI 命名 + 注册中心 PR | Review sidecar + LLM/人类多源审查 |
| **MLN** | 2006 | 一阶逻辑公式 + 权重 | 无类型区分，所有谓词平等 | 无，用户手写逻辑公式 | Markov 网络 / ground factor graph | MC-SAT、Gibbs sampling、lifted inference | 数据驱动权重学习 | 对数线性权重 → Gibbs 分布 | 无包模型 | 无 |
| **ProbLog** | 2007 | 概率逻辑程序（probabilistic facts + Horn clauses） | 无类型区分，fact/rule 二分 | 无，推理策略隐含在规则结构中 | BDD（Binary Decision Diagram） | 加权模型计数 / knowledge compilation | 用户标注 fact 概率 | 概率 fact 标注 (0.7::fact) | 无包模型（单文件程序） | 无 |
| **PSL** | 2012 | 一阶软逻辑规则 + 连续真值 [0,1] | 无类型区分 | 无，用户手写规则模板 | Hinge-loss MRF | ADMM / consensus optimization | 数据驱动权重学习 | 连续真值 [0,1] + Lukasiewicz 逻辑 | 无包模型 | 无 |
| **DeepDive** | 2015 | Datalog 规则 + 远程监督 | 无类型区分 | 无，factor 由 Datalog 规则生成 | Factor graph (grounding) | Gibbs sampling (DimmWitted) | 远程监督 + 权重学习 | 因子权重 → Gibbs 分布 | 无包模型 | 无 |
| **FACTORIE** | 2009 | 命令式因子图 DSL (Scala) | 无面向科学的类型化 | 无，factor template 由用户定义 | Factor graph（Java 对象） | Gibbs sampling、SampleRank | 在线/批量权重学习 | 实值权重 → Gibbs 分布 | 无包模型 | 无 |
| **ASPIC+** | 2010 | 严格规则 + 可废止规则 + 偏好 | 严格/可废止二分 | 严格规则 vs 可废止规则（非命名策略） | 论证框架（攻击图） | Dung 语义扩展（grounded/preferred/stable） | 规则强度由偏好排序决定 | 定性（接受/拒绝/未决） | 无包模型 | 无 |
| **Epistemic Graphs** | 2018 | 认知图（命题 + 支持/攻击边 + 强度） | 无面向科学的类型化 | 无，支持/攻击关系直接标注 | 认知图（无编译） | 迭代语义评估 / 约束满足 | 手工标注强度 | 连续强度值 [0,1] | 无包模型 | 多主体评估（理论层面） |
| **Carneades** | 2007 | 论证方案 + 批判问题 | 前提/例外/假设 分层 | 论证方案（argumentation schemes） | 论证图 + CAES 证明标准 | 证明标准评估（preponderance/clear & convincing/beyond doubt） | 受众可接受性判断 | 定性证明标准 | 无包模型 | 受众角色概念 |
| **Stewart & Buehler 2026** | 2026 | 高阶科学关系超图（hypergraph） | 无 Gaia 式类型化命题 | 无 | Hypergraph | 超图遍历 + agentic hypothesis generation | 无显式概率参数 | 无显式概率语义 | 无包模型 | 无 |
| **Stan** | 2012 | 声明式统计模型（参数 + 数据 + 模型块） | 无命题类型 | 无，模型结构即推理逻辑 | HMC/NUTS 采样器 | MCMC (HMC/NUTS) + 变分推断 | 数据似然 | 连续后验分布 | 无知识包模型 | 无 |
| **Gen** | 2019 | 通用概率程序（Julia） | 无命题类型 | 无 | 执行轨迹（trace） | 可编程推理（MCMC/importance/SMC 等） | 数据 + 先验 | 连续/离散后验分布 | Julia 包模型（非知识包） | 无 |
| **Church / WebPPL** | 2008 / 2014 | 函数式概率程序 | 无命题类型 | 无 | 执行轨迹 | 枚举 / MCMC / 变分推断 | 程序中的先验分布 | 连续/离散后验分布 | 无知识包模型 | 无 |
| **Infer.NET** | 2008 | 因子图 DSL (C#) | 无命题类型 | 无，factor 由用户定义 | 因子图（编译为消息传递代码） | EP / VMP / Gibbs | 数据 + 先验 | 后验分布（近似） | 无知识包模型 | 无 |
| **ForneyLab / RxInfer** | 2019 / 2022 | Forney-style factor graph (Julia) | 无命题类型 | 无 | Forney factor graph | 消息传递（BP / VMP / EP / 混合） | 先验 + 观测数据 | 连续后验分布 | Julia 包模型（非知识包） | 无 |

---

## 3. 与最接近系统的差异总结

### 3.1 DeepDive

**Gaia 从 DeepDive 借鉴了什么：** DeepDive 证明了 factor graph 是大规模知识库构建的有效推理基础。其 "知识库构建即推理" 的理念——将信息提取、去重、关系提取等任务统一建模为 factor graph 上的联合推理问题——直接启发了 Gaia 将知识包中的多种推理关系统一编译到同一个 factor graph 进行联合 BP 的设计。DeepDive 使用 Datalog 规则定义 factor 模板然后 grounding 到具体 factor graph 的管线，也类似于 Gaia 从 DSL 编译到 IR 再 lowering 到 factor graph 的三阶段管线。

**Gaia 的独有贡献：** DeepDive 面向的是从非结构化文本中提取结构化知识的任务，其 factor 结构由 Datalog 规则直接定义，不区分推理模式的认识论类型。Gaia 面向的是科学知识的显式形式化——命题由人类或 AI 编写而非从文本提取，推理策略作为一等公民被命名和编译，知识被组织为版本化的包而非单一的知识库。此外，DeepDive 的参数由数据驱动的权重学习确定，Gaia 的参数由 review sidecar 中的审稿人判断提供——这反映了统计概率与认知概率的根本差异。

### 3.2 MLN（Markov Logic Networks）

**Gaia 从 MLN 借鉴了什么：** MLN 奠定了"逻辑公式 + 概率权重"的范式——用逻辑结构表达知识间的关系，同时允许软约束（权重有限意味着公式可被违反）。Gaia 的 Strategy 层承继了这一思想：每条推理策略都是一个带条件概率的软约束，前提不成立不会导致结论必然不成立。MLN 的 grounding（从一阶公式到 ground Markov network）也类似于 Gaia 的 lowering（从 Gaia IR 到 factor graph）。

**Gaia 的独有贡献：** MLN 是通用的——任何一阶逻辑公式都可以成为 MLN 中的公式，不区分公式表达的推理类型。Gaia 的推理策略是类型化和命名的——`abduction` 和 `deduction` 不是同一种公式的不同实例，而是编译到不同 factor 拓扑结构的不同语义家族。MLN 的权重是实值且通过数据学习，Gaia 的条件概率来自审稿人判断，且每种推理策略的有效参数有来自 Jaynes 理论的数学推导。MLN 没有包模型和审稿系统，知识库是单一的公式集合。

### 3.3 ProbLog

**Gaia 从 ProbLog 借鉴了什么：** ProbLog 证明了可以在逻辑编程的基础上无缝叠加概率语义——用户写 Prolog 风格的规则，系统自动处理概率推理。Gaia 类似地在 Python DSL 的基础上叠加概率语义——用户写 `claim()` 和 `deduction()` 声明，系统自动编译到因子图并运行 BP。ProbLog 的 "概率 fact" 概念也启发了 Gaia 的 claim 先验标注。

**Gaia 的独有贡献：** ProbLog 基于逻辑编程范式，推理通过 Prolog 风格的 backward chaining + 加权模型计数实现。Gaia 基于因子图范式，推理通过前向消息传递（BP）实现——这使得 Gaia 能自然处理环状推理结构（观测支持假说，假说又预测新观测），而 ProbLog 在循环程序上的语义需要特殊处理。更关键的是，ProbLog 不区分推理策略的认识论类型——一条规则就是一条规则，没有"这是溯因"或"这是演绎"的语义标签。ProbLog 也没有包模型、版本化、跨包引用和审稿系统。

### 3.4 Epistemic Graphs

**Gaia 从 Epistemic Graphs 借鉴了什么：** Epistemic Graphs（Polberg & Hunter 2018 及后续工作）将论证图扩展到认知领域，允许不同强度的支持和攻击关系，并支持多主体对同一图的不同评估。这在方向上最接近 Gaia 的 review sidecar 概念——同一推理结构，不同认知主体可以赋予不同的强度评估。Epistemic Graphs 对论证图中 "epistemic state" 与 "argument structure" 分离的设计也启发了 Gaia 将 IR 结构与参数化层分离的架构。

**Gaia 的独有贡献：** Epistemic Graphs 是一个理论框架，主要以论文和形式定义的形式存在，缺乏工程化的软件实现。Gaia 是一个完整的软件栈——从 DSL 到编译器到 IR 到 BP 引擎到 CLI 管线。Epistemic Graphs 的推理是基于论证语义的迭代评估，Gaia 的推理是基于 Jaynes 框架的 factor graph BP——后者有严格的概率论基础（Cox 定理保证的唯一性）和成熟的计算工具（JT、GBP 等）。此外，Gaia 提供了完整的包模型和发布管线，而 Epistemic Graphs 不涉及知识的打包、版本化和发布。

### 3.5 ASPIC+

**Gaia 从 ASPIC+ 借鉴了什么：** ASPIC+ 将论证理论系统化为严格规则（确定性推理）和可废止规则（可被攻击的推理）的分层框架，并定义了规则之间的攻击关系和偏好机制。Gaia 的 Operator（确定性逻辑约束）和 Strategy（不确定推理声明）的二层分离直接反映了 ASPIC+ 的严格/可废止二分思想——Operator 类似于严格规则（真值表完全确定，无自由参数），Strategy 类似于可废止规则（前提支持结论的程度由条件概率决定）。

**Gaia 的独有贡献：** ASPIC+ 的推理语义基于 Dung 的抽象论证框架（grounded/preferred/stable extensions），产出是定性的（论证被接受/拒绝/未决）。Gaia 的推理语义基于 Bayesian 概率和 BP，产出是定量的（每个 claim 有精确的后验概率值）。ASPIC+ 的可废止规则不区分推理模式——"溯因规则"和"类比规则"在框架中没有结构性差异。Gaia 的命名策略则编译到不同的 factor 拓扑——abduction 产生 disjunction + equivalence，deduction 产生 conjunction + implication，这种结构性差异直接影响 BP 消息传递的行为。ASPIC+ 也没有包模型、版本化、跨包引用、审稿系统和发布管线。
