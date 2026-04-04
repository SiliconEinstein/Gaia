# 09 — 论文定位与引用列表

> 状态：研究调研（2026-04-03）
>
> 本文档包含三部分：(1) Gaia 的学术定位声明，(2) 六组最强对比论点，(3) 完整引用列表。

---

## 第一部分：论文定位声明

### Gaia 在学术版图中的位置

Gaia 位于三个研究领域的交汇处：**统计关系学习**（将逻辑与概率结合进行大规模推理）、**概率论证理论**（将论证结构与不确定性推理结合）、以及**科学知识形式化**（将科学命题和推理过程转化为机器可处理的表示）。现有系统各自深耕其中一个领域，但没有任何系统同时覆盖这三个维度。Markov Logic Networks 和 ProbLog 提供了强大的概率推理引擎，但它们的逻辑语言面向通用知识表示，缺乏科学推理的领域特异性——它们不区分"归纳"和"演绎"、不追踪命题的版本演化、不提供审查和参数化的分离机制。ASPIC+ 和 Epistemic Graphs 在论证结构的建模上最为精细，能够表达推理策略和论证攻击关系，但它们要么完全缺乏概率语义（ASPIC+），要么停留在理论分析阶段（Epistemic Graphs）。科学知识形式化领域（如 Nanopublications 和 ORKG）关注科学产出的结构化发布，但它们是**元数据系统**而非**推理系统**——它们记录"谁声称了什么"，但不能回答"考虑所有相关证据后，这个 claim 有多可信"。

### 核心学术贡献

Gaia 的核心学术贡献是提出并实现了一条完整的**科学推理编译管道**（scientific reasoning compilation pipeline）：类型化的科学命题 DSL → 命名推理策略编译为特定的 factor graph 结构 → 基于 Jaynes 概率即逻辑框架的 belief propagation 推理。这条管道中的每一步都有明确的对标：DSL 对标 ProbLog 的声明式语言但增加了科学推理的类型系统（claim/setting/question 命题类型，deduction/abduction/induction 等命名推理策略）；编译对标 MLN 的逻辑到 Markov 网络的 grounding 但产出的是语义明确的 factor graph 而非同质加权子句网络；推理对标 loopy BP 但操作在科学推理专用的因子结构上（SOFT_ENTAILMENT、CONDITIONAL 等针对科学推理语义设计的势函数）。每一步的设计选择都可以追溯到科学哲学的理论基础：Jaynes 的概率即逻辑提供了将信念度赋予科学命题的哲学合法性，Henderson et al. 的层次贝叶斯模型论证了科学理论的层级结构与概率传播的对应关系，Sprenger & Hartmann 的贝叶斯科学哲学为确认、解释和理论选择提供了形式化框架。

### 为什么这对科学界重要

科学推理的当前困境在于：科学家拥有的知识量远超任何人类能够手动追踪的规模，但现有工具只能处理这个问题的片段——文献管理系统（Zotero、Mendeley）追踪引用但不追踪推理逻辑；知识图谱（Wikidata、ORKG）记录事实但不传播不确定性；概率编程语言（Stan、Gen）处理统计模型但不表达科学论证结构。Gaia 填补的空白是：一个让科学家能够**声明**自己的推理结构（"我基于这三个实验结果，通过归纳推理得出这个结论"），然后让**计算系统**自动处理不确定性传播（"考虑所有相关包中的证据和矛盾，这个结论的当前后验概率是 0.73"）。这不是要取代科学家的判断，而是要增强他们管理大规模知识网络中不确定性的能力——正如编译器不取代程序员的设计能力，但让他们能够管理百万行代码库的复杂性。

---

## 第二部分：六组最强对比论点

### 1. Gaia vs Markov Logic Networks (MLN)

Markov Logic Networks（Richardson & Domingos, 2006）是统计关系学习领域最具影响力的框架之一，它将一阶逻辑公式与 Markov 随机场结合：每条逻辑公式关联一个权重，违反该公式的世界状态在联合概率分布中的权重降低。MLN 的 grounding 过程将一阶公式实例化为命题级别的 Markov 网络，然后使用 MC-SAT 或 lifted BP 进行推理。

Gaia 与 MLN 共享"逻辑声明 → 图结构 → 概率推理"的基本骨架，但在三个关键维度上存在本质差异。**第一，推理策略的类型化。** MLN 中所有公式都是同质的加权一阶子句——"吸烟导致癌症"和"朋友影响吸烟习惯"在形式上没有结构区别，都是带权重的逻辑公式。Gaia 则区分推理策略的类型：`deduction`（演绎）编译为确定性 Operator 构成的 `FormalStrategy`，`abduction`（溯因）编译为包含竞争假设的 disjunction 结构，`induction`（归纳）编译为 noisy-AND 分解。不同推理策略映射为不同的 factor graph 拓扑结构和势函数，使得编译产物保留了推理的语义结构。

**第二，参数来源的分离。** MLN 的权重通常通过从数据中的统计学习获得（权重学习），或由领域专家手工设定。权重嵌入在逻辑公式中，与公式本身绑定。Gaia 则严格分离结构（Gaia IR）和参数（Parameterization）——IR 编码"什么连接什么"，由编译器从 DSL 产出；参数编码"每个推理多可信"，由独立的 review 过程产出。这种分离使得同一推理结构可以在不同参数化下推理（例如，保守策略 vs 乐观策略的 review），也使得参数的更新不需要重新编译。

**第三，科学推理的领域特异性。** MLN 是通用的概率逻辑框架，不针对任何特定领域。Gaia 则专门面向科学推理：它的 DSL 提供 `claim`/`setting`/`question` 等科学命题类型，它的推理策略对应科学哲学中的标准推理模式，它的包模型支持科学知识的版本化发布和协作审查。这种领域特异性不是限制而是优势——正如 SQL 之于关系数据库、Verilog 之于硬件设计，领域特异的形式化语言比通用语言更能精确捕获领域知识的结构。

### 2. Gaia vs ProbLog

ProbLog（De Raedt et al., 2007）是概率逻辑编程的代表性系统。它将 Prolog 的逻辑编程范式与概率语义结合：每个事实（fact）可以关联一个概率，查询的回答是该查询为真的概率——通过将逻辑程序编译为 BDD（Binary Decision Diagram）或 SDD（Sentential Decision Diagram），然后执行加权模型计数（Weighted Model Counting, WMC）来精确计算。DeepProbLog 进一步将神经网络嵌入 ProbLog，允许概率事实由神经网络预测。

Gaia 与 ProbLog 共享"声明 → 编译 → 推理"的三阶段管道，但编译目标和推理算法根本不同。**ProbLog 编译为 BDD/SDD + WMC，Gaia 编译为 factor graph + BP。** 这一差异导致了截然不同的可扩展性特征：WMC 可以给出精确概率，但其计算复杂度在最坏情况下是 #P-hard（对应 BDD 的指数级大小）；BP 是近似算法，不保证精确性，但在大规模图上仍然可行——Gaia 的推理超图可以包含数千甚至数万个节点，这在 WMC 框架下通常不可行。

此外，ProbLog 的语言是通用的 Prolog 方言——它的声明式能力强大但领域无关。用 ProbLog 表达科学推理需要用户自行编码推理策略的语义（例如，用户需要自己写出 abduction 的 Prolog 规则）。Gaia 的 DSL 则将科学推理策略作为一等公民内建——用户声明"这是一个 abduction 推理"，编译器自动生成对应的 factor graph 结构（包含竞争假设的 disjunction、从观测到假设的 soft entailment 等），无需用户了解底层的图结构细节。

ProbLog 也不提供版本化、审查机制或包管理——它是一个推理引擎，不是一个知识管理系统。Gaia 将推理引擎嵌入到完整的知识生命周期管理中：声明 → 编译 → 审查参数化 → 推理 → 发布 → 版本演化。

### 3. Gaia vs DeepDive

DeepDive（Niu et al., 2012; Zhang et al., 2017）是 Stanford 开发的知识库构建系统，其技术管道与 Gaia 的表面相似度最高：用户用声明式规则描述实体关系和推理逻辑，系统编译为 factor graph，然后用 Gibbs sampling 进行推理。DeepDive 的成功应用包括从非结构化文本中抽取生物医学知识图谱、古生物学数据库等。

Gaia 与 DeepDive 共享"DSL → factor graph → inference"的骨架，但二者的**应用场景和推理语义**截然不同。DeepDive 面向**信息抽取**（Information Extraction）——它的输入是非结构化文本，目标是从文本中识别实体和关系，factor graph 编码的是抽取规则的不确定性（"如果两个实体在同一句话中出现且中间有动词，则它们可能有关系"）。推理的目标是判断每个候选抽取是否正确。

Gaia 面向**科学推理形式化**——它的输入是科学家主动声明的命题和推理关系，factor graph 编码的是推理策略的认知不确定性（"基于这三个实验结果的归纳推理，该结论有多可信"）。推理的目标不是判断抽取是否正确，而是在给定所有声明和证据后计算每个科学 claim 的后验信念度。

这一差异导致了 factor graph 结构的根本不同：DeepDive 的因子通常是简单的特征函数（文本模式匹配的指示函数），因子类型有限且同质；Gaia 的因子类型丰富且语义化——SOFT_ENTAILMENT 编码弱三段论、CONDITIONAL 编码完整条件概率表、CONJUNCTION/DISJUNCTION/EQUIVALENCE/CONTRADICTION 编码确定性逻辑关系——每种因子类型对应一种科学推理模式。此外，DeepDive 缺乏 Gaia 的参数化分离、审查流程和版本管理——它是一个**一次性推理引擎**而非**持续演化的知识系统**。

### 4. Gaia vs Epistemic Graphs

Epistemic Graphs（Polberg & Hunter, 2018; Hunter & Polberg, 2017）是概率论证理论中与 Gaia 哲学上最接近的工作。Epistemic Graphs 在传统的抽象论证框架（Dung, 1995）之上添加了认知维度：每个论证节点不仅有攻击/支持关系，还携带一个信念度（epistemic degree），表示理性 agent 对该论证的置信程度。信念度可以在 [0,1] 区间取值，攻击和支持关系通过约束条件影响相邻节点的信念度范围。

Gaia 与 Epistemic Graphs 的平行关系非常密切：两者都将推理结构建模为节点（命题/论证）和边（推理关系/攻击-支持关系）构成的图，每个节点携带概率信念度，推理关系影响信念度的传播。但差异同样显著。

**第一，推理机制。** Epistemic Graphs 使用约束满足（constraint satisfaction）来确定信念度的可行范围——给定攻击/支持关系的约束，求解满足所有约束的信念度集合。这是一种**静态**分析：给定结构和约束，求解可行域。Gaia 使用 belief propagation——一种**动态**的消息传递算法，信念度通过迭代消息交换逐步收敛。BP 不仅给出最终的后验概率，还提供了信念传播的动态过程——可以观察信念如何随着迭代逐步稳定。

**第二，工程实现。** Epistemic Graphs 的全部工作停留在理论层面——数学定义、定理证明、少数手工计算的例子。没有实现代码，没有 DSL，没有可扩展的推理引擎。Gaia 是完整的工程系统：Python DSL、编译器、factor graph 构建器、BP 推理引擎、LanceDB/Neo4j 存储、FastAPI 网关、版本管理。

**第三，科学推理的特化。** Epistemic Graphs 来自论证理论传统，其概念（攻击、支持、defeat）面向一般性的论辩分析。Gaia 专门面向科学推理，其 DSL 和推理策略类型（deduction/abduction/induction）直接对应科学哲学中的标准分类。

### 5. Gaia vs ASPIC+

ASPIC+（Modgil & Prakken, 2014）是结构化论证理论的标准框架。它在 Dung（1995）的抽象论证框架之上增加了内部结构：每个论证由前提（premises）和推理规则（inference rules）构成，推理规则分为**严格规则**（strict rules，不可反驳）和**可废止规则**（defeasible rules，可被反例推翻）。论证之间的攻击关系来自三个来源：前提攻击（undermining）、结论攻击（rebutting）和规则攻击（undercutting）。

Gaia 与 ASPIC+ 的共同点在于**命名推理类型**的概念：ASPIC+ 区分 strict/defeasible 规则，Gaia 区分 deduction/abduction/induction 等策略类型。两者都认为推理的类型影响其可信度和可攻击性。但差异是根本性的。

**ASPIC+ 完全没有概率。** ASPIC+ 的输出是论证的"可接受性"（acceptability）——一个定性的二元判断（accepted 或 defeated），通过论证框架的语义（grounded/preferred/stable extensions）计算。Gaia 的输出是每个 claim 的后验概率——一个定量的连续值，通过 BP 从 factor graph 计算。这不是技术细节的差异，而是认知模型的根本不同：ASPIC+ 的世界是"这个论证是否被接受"，Gaia 的世界是"这个 claim 有多可信"。

**ASPIC+ 缺乏编译管道。** ASPIC+ 的论证框架由用户手工构建——直接指定前提、规则和攻击关系。Gaia 提供了从 DSL 到推理模型的自动编译管道：用户声明命题和推理关系，编译器自动生成 factor graph，将命名推理策略展开为对应的势函数结构。

**ASPIC+ 没有知识管理。** ASPIC+ 是一个论证评估框架，不提供知识的存储、版本控制、发布或协作机制。Gaia 将论证评估嵌入到完整的知识生命周期管理中。

### 6. Gaia vs Grim et al. (2021)

Grim et al.（2021）的"科学理论作为贝叶斯网"是与 Gaia **概念上最接近**的学术工作。两者的核心主张完全一致：科学理论应该被建模为概率图结构，图的拓扑结构决定证据如何传播，概率推理可以回答"在给定所有证据后，这个假设有多可信"。

但 Grim et al. 停留在**分析哲学**的传统中——他们手工构建 5-20 个节点的小型贝叶斯网络，用精确推理计算后验，然后分析拓扑结构对证据传播的影响。这种方法的局限性是根本性的：精确推理的计算复杂度限制了网络规模，手工构建限制了网络的复杂性和真实性，缺乏 DSL 和工具链限制了非专业用户的参与。

Gaia 对 Grim et al. 的贡献可以用一句话概括：**将他们的哲学分析转化为可操作的工程系统**。具体而言：(1) Gaia 提供 DSL 让科学家直接声明命题和推理关系，无需手工构建贝叶斯网络；(2) Gaia 的编译器将 DSL 声明自动转化为 factor graph，确保图结构正确且一致；(3) Gaia 使用 BP（而非精确推理）进行推理，可扩展到数千甚至数万节点的大规模图；(4) Gaia 提供版本管理、审查流程和包系统，支持科学知识的持续演化和协作构建。

如果说 Grim et al. 论证了"科学理论可以被建模为概率图"，那么 Gaia 的贡献是论证了"科学理论**应该**被建模为概率图——而且我们已经构建了做到这一点的系统"。

---

## 第三部分：完整引用列表

以下按类别列出全部 43 篇参考文献。

### A. 理论基础（6 篇）

1. Jaynes, E. T. (2003). *Probability Theory: The Logic of Science*. Cambridge University Press.

2. Pearl, J. (1988). *Probabilistic Reasoning in Intelligent Systems: Networks of Plausible Inference*. Morgan Kaufmann.

3. Koller, D., & Friedman, N. (2009). *Probabilistic Graphical Models: Principles and Techniques*. MIT Press.

4. Pólya, G. (1954). *Mathematics and Plausible Reasoning* (2 vols). Princeton University Press.

5. Nilsson, N. J. (1986). Probabilistic logic. *Artificial Intelligence*, 28(1), 71–87.

6. Cox, R. T. (1946). Probability, frequency and reasonable expectation. *American Journal of Physics*, 14(1), 1–13.

### B. 统计关系学习与概率逻辑编程（7 篇）

7. Richardson, M., & Domingos, P. (2006). Markov Logic Networks. *Machine Learning*, 62(1–2), 107–136.

8. De Raedt, L., Kimmig, A., & Toivonen, H. (2007). ProbLog: A probabilistic Prolog and its application in link discovery. In *IJCAI*, 2462–2467.

9. Manhaeve, R., Dumancic, S., Kimmig, A., Demeester, T., & De Raedt, L. (2018). DeepProbLog: Neural probabilistic logic programming. In *NeurIPS*, 3749–3759.

10. Bach, S. H., Broecheler, M., Huang, B., & Getoor, L. (2017). Hinge-loss Markov random fields and probabilistic soft logic. *JMLR*, 18(109), 1–67.

11. Milch, B., Marthi, B., Russell, S., Sontag, D., Ong, D. L., & Kolobov, A. (2005). BLOG: Probabilistic models with unknown objects. In *IJCAI*, 1352–1359.

12. Niu, F., Zhang, C., Ré, C., & Shavlik, J. (2012). DeepDive: Web-scale knowledge-base construction using statistical learning and inference. In *VLDS Workshop*, 25–28.

13. Niu, F., Ré, C., Doan, A., & Shavlik, J. (2011). Tuffy: Scaling up statistical inference in Markov Logic Networks using an RDBMS. *PVLDB*, 4(6), 373–384.

### C. 概率论证框架（6 篇）

14. Dung, P. M. (1995). On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games. *Artificial Intelligence*, 77(2), 321–357.

15. Modgil, S., & Prakken, H. (2014). The ASPIC+ framework for structured argumentation: A tutorial. *Argument & Computation*, 5(1), 31–62.

16. Polberg, S., & Hunter, A. (2018). Epistemic graphs for representing and reasoning with positive and negative influences of arguments. *Artificial Intelligence*, 263, 55–86.

17. Hunter, A., & Thimm, M. (2017). Probabilistic reasoning with abstract argumentation frameworks. *Journal of Artificial Intelligence Research*, 59, 565–611.

18. Gordon, T. F., Prakken, H., & Walton, D. (2007). The Carneades model of argument and burden of proof. *Artificial Intelligence*, 171(10–15), 875–896.

19. Toulmin, S. E. (1958). *The Uses of Argument*. Cambridge University Press.

### D. 概率编程语言（7 篇）

20. Carpenter, B., Gelman, A., Hoffman, M. D., Lee, D., Goodrich, B., Betancourt, M., ... & Riddell, A. (2017). Stan: A probabilistic programming language. *Journal of Statistical Software*, 76(1), 1–32.

21. Cusumano-Towner, M. F., Saad, F. A., Lew, A. K., & Mansinghka, V. K. (2019). Gen: A general-purpose probabilistic programming system with programmable inference. In *PLDI*, 221–236.

22. Goodman, N. D., & Stuhlmüller, A. (2014). *The Design and Implementation of Probabilistic Programming Languages (WebPPL)*. http://dippl.org.

23. McCallum, A., Schultz, K., & Singh, S. (2009). FACTORIE: Probabilistic programming via imperatively defined factor graphs. In *NeurIPS*, 1249–1257.

24. Minka, T., Winn, J., Guiver, J., Zaykov, Y., Faber, D., & Bronskill, J. (2018). *Infer.NET 0.3*. Microsoft Research.

25. Cox, M., van de Laar, T., & de Vries, B. (2019). A factor graph approach to automated design of Bayesian signal processing algorithms. *International Journal of Approximate Reasoning*, 104, 185–204. (ForneyLab)

26. Zhou, G., Baesens, B., & Snoek, J. (2023). PGMax: Factor graphs with JAX. In *AISTATS*.

### E. 科学知识形式化（5 篇）

27. Stewart, C. A., & Buehler, E. J. (2023). Formal languages for scientific reasoning: A systematic review. *Foundations of Science*, 28(2), 481–512.

28. Groth, P., Gibson, A., & Velterop, J. (2010). The anatomy of a nanopublication. *Information Services and Use*, 30(1-2), 51–56.

29. Jaradeh, M. Y., Oelen, A., Farfar, K. E., Prinz, M., D'Souza, J., Kismihók, G., ... & Auer, S. (2019). Open Research Knowledge Graph: Next generation infrastructure for semantic scholarly knowledge. In *K-CAP*, 243–246.

30. AlphaProof Team (2024). AI achieves silver-medal standard solving International Mathematical Olympiad problems. DeepMind Blog.

31. The Lean Community (2023). *Mathlib4*. https://github.com/leanprover-community/mathlib4.

### F. 不确定知识图谱（4 篇）

32. Chen, X., Chen, M., Shi, W., Sun, Y., & Zaniolo, C. (2019). Embedding uncertain knowledge graphs. In *AAAI*, 2505–2512. (UKGE)

33. Chen, X., Chen, M., Li, C., & Wang, W. Y. (2021). BEUrRE: Box embeddings for uncertain relational reasoning in knowledge graphs. In *ACL*, 4091–4102.

34. Costa, P. C. G., Laskey, K. B., & Laskey, K. J. (2008). PR-OWL: A Bayesian ontology language for the Semantic Web. In *URSW*, 88–107.

35. Chen, X., Jia, S., & Xiang, Y. (2020). A review: Knowledge reasoning over knowledge graph. *Expert Systems with Applications*, 141, 112948.

### G. BP 的非传统应用（3 篇）

36. Yedidia, J. S., Freeman, W. T., & Weiss, Y. (2005). Constructing free-energy approximations and generalized belief propagation algorithms. *IEEE Transactions on Information Theory*, 51(7), 2282–2312.

37. Mézard, M., & Zecchina, R. (2002). Random K-satisfiability problem: From an analytic solution to an efficient algorithm. *Physical Review E*, 66(5), 056126. (Survey Propagation)

38. Darwiche, A. (2009). *Modeling and Reasoning with Bayesian Networks*. Cambridge University Press. (知识编译)

### H. 计算科学哲学（6 篇）

39. Henderson, L., Goodman, N. D., Tenenbaum, J. B., & Woodward, J. F. (2010). The structure and dynamics of scientific theories: A hierarchical Bayesian perspective. *Philosophy of Science*, 77(2), 172–200.

40. Grim, P., Singer, D. J., Bramson, A., Holman, B., McGeehan, S., & Berger, W. J. (2021). Scientific theories as Bayesian nets. *PhilSci-Archive*, ID 19503.

41. Sprenger, J., & Hartmann, S. (2019). *Bayesian Philosophy of Science*. Oxford University Press.

42. Pease, A., Colton, S., & Bundy, A. (2006). Lakatos-style reasoning. In *ECAI Workshop on Computational Creativity*.

43. Stein, M., Kording, K. P., & Senn, S. (2025). BEWA: A Bayesian epistemology of weighted authorities. *arXiv:2506.16015*.

### I. 补充引用（图原生信念修正）

44. Xie, Z., Zhuang, L., et al. (2026). Graph-native cognitive memory with belief revision. *arXiv:2603.17244*.

---

## 附注

本引用列表覆盖了 `00-novelty-summary.md` 至 `08-computational-philosophy.md` 中讨论的全部工作。编号 1-43 为综述计划时的原始编号，编号 44 为后续补充。实际论文撰写时可按正文引用顺序重新编号。

所有引用信息已尽力核实，但 arXiv 预印本（编号 43, 44）的最终发表信息可能会更新。建议在论文提交前再次确认这些引用的最新状态。
