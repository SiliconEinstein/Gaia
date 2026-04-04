# Gaia 相关工作综述

> 状态：研究调研（2026-04-03）
>
> 用途：为 Gaia 学术论文准备的文献综述与新颖性分析。Gaia 是一个将科学推理形式化的系统——通过类型化 DSL 声明科学命题，编译为 factor graph，基于 Jaynes 概率即逻辑框架执行 belief propagation 推理。

## 文档结构

| 文件 | 内容 | 涉及系统 |
|------|------|---------|
| [00-novelty-summary.md](00-novelty-summary.md) | 新颖性总结与全景对比表 | 全部 |
| [01-theoretical-foundations.md](01-theoretical-foundations.md) | 理论基础 | Jaynes, Pearl, Koller & Friedman, Polya, Nilsson |
| [02-statistical-relational-learning.md](02-statistical-relational-learning.md) | 统计关系学习与概率逻辑编程 | MLN, ProbLog, DeepProbLog, PSL, BLOG, DeepDive, Tuffy |
| [03-probabilistic-argumentation.md](03-probabilistic-argumentation.md) | 概率论证框架 | Dung, ASPIC+, Epistemic Graphs, Hunter & Thimm, Carneades, Toulmin |
| [04-probabilistic-programming.md](04-probabilistic-programming.md) | 概率编程语言 | Stan, Gen, Church/WebPPL, FACTORIE, Infer.NET, ForneyLab, PGMax |
| [05-scientific-knowledge.md](05-scientific-knowledge.md) | 科学知识形式化 | Stewart & Buehler, 证明助手, AlphaProof, Nanopub, ORKG |
| [06-uncertain-knowledge-graphs.md](06-uncertain-knowledge-graphs.md) | 不确定知识图谱 | UKGE, BEUrRE, PR-OWL, 综述 |
| [07-bp-applications.md](07-bp-applications.md) | BP 的非传统应用 | Yedidia/GBP, Survey Propagation, 知识编译 |
| [08-computational-philosophy.md](08-computational-philosophy.md) | 计算科学哲学 | Henderson, Grim, Sprenger & Hartmann, Pease/Lakatos, BEWA |
| [09-positioning.md](09-positioning.md) | 论文定位与引用列表 | — |

## 核心结论

Gaia 的核心 pipeline —— **类型化科学命题 DSL → 命名推理策略编译为特定 factor graph 结构 → belief propagation 推理** —— 在现有文献中没有直接重复。

最接近的五个系统：

1. **DeepDive**（Stanford）— 共享 "DSL → factor graph → inference" 骨架，但面向信息抽取而非科学推理
2. **Markov Logic Networks** — 共享 "逻辑 → factor graph → 推理"，但所有公式都是同质加权子句
3. **ProbLog** — 共享 "声明 → 编译 → 推理"，但用 BDD + 加权模型计数而非 factor graph + BP
4. **Epistemic Graphs** — 哲学上最接近（论证节点 + 概率信念度），但无工程系统
5. **ASPIC+** — 共享命名推理类型（strict/defeasible），但完全无概率

详细新颖性分析见 [00-novelty-summary.md](00-novelty-summary.md)。
