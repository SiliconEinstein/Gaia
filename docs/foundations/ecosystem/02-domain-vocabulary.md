# 领域词汇表

> **Status:** Current canonical

Gaia 文档中使用的核心术语。

## Knowledge

一个版本化的命题——知识图的基本单元。一个 Knowledge 对象携带内容（命题文本）、类型（claim、question、setting、action、contradiction、equivalence）以及作者分配的先验（初始信念度）。

完整的类型分类参见 `../gaia-lang/knowledge-types.md`。存储 schema 参见 `../gaia-ir/gaia-ir.md`。

## Reasoning

一个连接前提到结论的推理结构。每个 Reasoning 有一个类型（deduction、induction、abstraction、contradiction、retraction、equivalence），用于分类推理模式。在 Gaia IR 中，每个 Reasoning 产生一个 factor node。

因子节点详情参见 `../gaia-ir/gaia-ir.md`。

## Module

包内 Knowledge 对象和 Reasoning 的逻辑分组。在编写表面中，每个 `.typ` 文件（`lib.typ` 和 `gaia.typ` 除外）隐式地是一个 Module。Module 用于组织清晰性——它们不创建独立的 BP 边界。

## Package

一个完整的、版本化的知识容器。类似于 git 仓库或已发表的论文。提交、审查和集成的单元。身份标识：`(package_id, version)`。

包编写结构参见 `../gaia-lang/package-model.md`。包生命周期参见 `../cli/lifecycle.md`。

## Factor Graph

一个包含 variable node（变量节点，知识对象）和 factor node（因子节点，推理约束）的二部图。Belief Propagation 的核心计算结构。参见 `../gaia-ir/overview.md` 和 `../bp/inference.md`。

## Gaia IR

Gaia Lang 与 BP 之间的结构中间表示。一个一等提交制品，具有三个身份层：RawGraph、LocalCanonicalGraph 和 GlobalCanonicalGraph。参见 `../gaia-ir/overview.md`。

## Belief

一个 Knowledge 对象的后验合理性，由 BP 计算。取值在 [0, 1] 范围内，其中 0.5 表示最大无知（MaxEnt）。参见 `../theory/07-belief-propagation.md`。

## Review Server

独立部署的 LLM/agent 审核服务。审核包内部推理过程的逻辑可靠性，给出条件概率初始值。不判断前提本身是否正确。可多实例，需在 Official Registry 注册。详见 [06-review-and-curation.md](06-review-and-curation.md)。

## Official Registry

所有已注册包的聚合索引，采用 Julia General registry 模型（一个 git 仓库，一切通过 PR）。注册包、reviewer、LKM 的元数据，存储推理结果。可 fork、可联邦。详见 [05-registry-operations.md](05-registry-operations.md)。

## LKM Repo

各 LKM Server 各自维护的运营仓库。通过 Issues 管理该 LKM 的 research tasks——在全局推理中发现的候选关系（equivalence、contradiction、connection）的发布、调查和分拣。人类研究者可浏览不同 LKM 的 repo 寻找研究机会。详见 [03-decentralized-architecture.md](03-decentralized-architecture.md)。

## Research Task

LKM 在全局推理过程中发现的候选关系，以 Issue 形式发布到 LKM Repo。三类：equivalence（两个命题语义接近）、contradiction（两个命题互相冲突）、connection（隐含跨包依赖）。确认后由 LKM 创建 curation 包走标准流程。详见 [06-review-and-curation.md](06-review-and-curation.md)。

## Curation Package

LKM 或人类研究者创建的知识包，声明跨包关系（等价、矛盾、连接）。和普通知识包走完全相同的流程：Review Server 审核 → 注册到 Official Registry。详见 [06-review-and-curation.md](06-review-and-curation.md)。

## Open Question

人类/agent 在 Official Registry Issues 上提出的研究问题或知识空白（如"Y 领域缺少 Z 方面的包"）。与 LKM Repo 的 research task（结构化候选）互补，是社区协作发现研究方向的机制。详见 [05-registry-operations.md](05-registry-operations.md)。

## 参考文献

- `libs/storage/models.py`——所有核心类型的 Pydantic 模型
