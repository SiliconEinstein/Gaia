# 包模型

> **Status:** Current canonical

本文档定义了 Gaia 知识容器在创作界面中呈现的结构层次：Package、Module、Knowledge 和 Chain。

## Package

Package 是一个完整的、版本化的知识容器。它类似于一个 git 仓库或一篇已发表的论文。

- **标识**：`(package_id, version)` —— 语义化版本字符串（如 `"4.0.0"`）。
- **创作形式**：一个 Typst 项目目录，包含 `typst.toml` 清单文件、`lib.typ` 入口文件和模块文件。
- **状态值**：`preparing` | `submitted` | `merged` | `rejected`。

Package 是提交、审查和集成的单位。Package 的摄入是原子性的——所有模块要么全部成功，要么全部失败。

## Module

Module 是包内的逻辑分组。在创作界面中，每个 `.typ` 文件（除 `lib.typ` 和 `gaia.typ` 外）隐式地构成一个模块。

- **标识**：`module_id`，作用域限定在包内。
- **角色**：`reasoning` | `setting` | `motivation` | `follow_up_question` | `other`。
- **包含**：对知识对象和链的引用（`chain_ids[]`、`export_ids[]`）。
- **导入**：通过 `ImportRef(knowledge_id, version, strength)` 实现跨模块依赖。

Module 的存在是为了组织上的清晰性。它们不会创建独立的推理边界——包内所有知识都参与同一个因子图。

## Knowledge

Knowledge 对象是一个版本化的命题——知识图的基本单元。

- **标识**：`(knowledge_id, version)`。`knowledge_id` 的作用域限定在包内；版本是一个随编辑递增的整数。
- **类型**：`claim | question | setting | action | contradiction | equivalence`（参见 [knowledge-types.md](knowledge-types.md)）。
- **内容**：命题文本。
- **先验**：作者指定的合理性值，在 (epsilon, 1 - epsilon) 范围内，参与推理的类型必须提供。
- **参数**：可选的 `Parameter(name, constraint)` 列表，用于模式/通用节点。
- **关键词**：提取的搜索词。

## Chain

Chain 是一个展示层的多步推理结构。每条 Chain 代表一个从前提到结论的完整推理单元。

- **标识**：`chain_id`，作用域限定在模块内。
- **类型**：`deduction | induction | abstraction | contradiction | retraction | equivalence`。
- **步骤**：有序的 `ChainStep(step_index, premises[], reasoning, conclusion)` 列表。每一步将前提 `KnowledgeRef` 连接到结论 `KnowledgeRef`。
- **因子映射**：每条 Chain 在 Graph IR 中产生一个因子。Chain 保留了作者的多步论证；因子将其折叠为单一约束。

## 包生命周期（创作视角）

```
authored   -> author writes Typst source
built      -> gaia build: deterministic lowering to Graph IR
inferred   -> gaia infer: local BP preview with local parameterization
published  -> gaia publish: submitted to registry for peer review
```

发布之后的流程参见 [../lkm/lifecycle.md](../lkm/lifecycle.md)。

## 层级间关系

```
Package (1)
  contains -> Module (1..n)
    contains -> Knowledge (0..n)
    contains -> Chain (0..n)
      references -> Knowledge via KnowledgeRef (premises, conclusions)
```

## 跨层引用

- **节点标识层**（raw、local canonical、global canonical）：参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)
- **包的 Graph IR 表示**：参见 [../graph-ir/overview.md](../graph-ir/overview.md)
- **持久化模型的存储模式**：参见 [../lkm/storage.md](../lkm/storage.md)

## 源码

- `libs/storage/models.py` —— `Package`、`Module`、`Knowledge`、`Chain`、`ChainStep` 模型
