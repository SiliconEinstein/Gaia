# 领域词汇表

> **Status:** Current canonical

Gaia 文档中使用的核心术语。

## Knowledge

一个版本化的命题——知识图的基本单元。一个 Knowledge 对象携带内容（命题文本）、类型（claim、question、setting、action、contradiction、equivalence）以及作者分配的先验（初始信念度）。

完整的类型分类参见 `../gaia-lang/knowledge-types.md`。存储 schema 参见 `../graph-ir/graph-ir.md`。

## Reasoning

一个连接前提到结论的推理结构。每个 Reasoning 有一个类型（deduction、induction、abstraction、contradiction、retraction、equivalence），用于分类推理模式。在 Graph IR 中，每个 Reasoning 产生一个 factor node。

因子节点详情参见 `../graph-ir/graph-ir.md`。

## Module

包内 Knowledge 对象和 Reasoning 的逻辑分组。在编写表面中，每个 `.typ` 文件（`lib.typ` 和 `gaia.typ` 除外）隐式地是一个 Module。Module 用于组织清晰性——它们不创建独立的 BP 边界。

## Package

一个完整的、版本化的知识容器。类似于 git 仓库或已发表的论文。提交、审查和集成的单元。身份标识：`(package_id, version)`。

包编写结构参见 `../gaia-lang/package-model.md`。包生命周期参见 `../cli/lifecycle.md`。

## Factor Graph

一个包含 variable node（变量节点，知识对象）和 factor node（因子节点，推理约束）的二部图。Belief Propagation 的核心计算结构。参见 `../graph-ir/overview.md` 和 `../bp/inference.md`。

## Graph IR

Gaia Lang 与 BP 之间的结构中间表示。一个一等提交制品，具有三个身份层：RawGraph、LocalCanonicalGraph 和 GlobalCanonicalGraph。参见 `../graph-ir/overview.md`。

## Belief

一个 Knowledge 对象的后验合理性，由 BP 计算。取值在 [0, 1] 范围内，其中 0.5 表示最大无知（MaxEnt）。参见 `../theory/07-belief-propagation.md`。

## 参考文献

- `libs/storage/models.py`——所有核心类型的 Pydantic 模型
