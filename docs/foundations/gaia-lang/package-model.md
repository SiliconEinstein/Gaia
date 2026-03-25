# 包模型

> **Status:** Target design
>
> **对齐：** [2026-03-25-gaia-lang-alignment-design.md](../../specs/2026-03-25-gaia-lang-alignment-design.md) §5

本文档定义了 Gaia 知识容器在创作界面中呈现的结构层次：Package、Module 和 Knowledge。

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
- **包含**：对知识对象的引用（`export_ids[]`）。
- **导入**：通过 `ImportRef(knowledge_id, version, strength)` 实现跨模块依赖。

Module 的存在是为了组织上的清晰性。它们不会创建独立的推理边界——包内所有知识都参与同一个因子图。

## Knowledge

Knowledge 对象是一个版本化的命题——知识图的基本单元。

- **标识**：`(knowledge_id, version)`。`knowledge_id` 的作用域限定在包内；版本是一个随编辑递增的整数。
- **类型**：`claim | setting | question`（参见 [knowledge-types.md](knowledge-types.md)）。
- **内容**：命题文本。
- **先验**：仅 `claim` 类型携带先验（作者指定的合理性值，在 (epsilon, 1 - epsilon) 范围内）。`setting` 和 `question` 不参与 BP，不携带先验。
- **参数**：可选的 `Parameter(name, constraint)` 列表，用于模式/通用节点。
- **关键词**：提取的搜索词。

## Factor 生成

Language 层不定义独立的 Factor 数据模型。Factor 由以下编译路径生成：

- **`from:`** —— claim 上的 `from:` 参数编译为粗因子（noisy-AND 合取语义）。
- **论证策略** —— `#abduction`、`#induction`、`#analogy`、`#extrapolation` 程序化生成细因子图。
- **`#relation`** —— `contradiction` / `equivalence` 关系编译为 FactorNode。

详见 [spec.md](spec.md) 和设计文档 §4–§5。

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
    Factor 由 from: / 论证策略 / #relation 编译生成
```

## 跨层引用

- **节点标识层**（raw、local canonical、global canonical）：参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)
- **包的 Graph IR 表示**：参见 [../graph-ir/overview.md](../graph-ir/overview.md)
- **持久化模型的存储模式**：参见 [../lkm/storage.md](../lkm/storage.md)

## 源码

- `libs/storage/models.py` —— `Package`、`Module`、`Knowledge` 模型
- **待更新**：`libs/storage/models.py` 中的 `Chain` 和 `ChainStep` 模型需在后续代码变更中移除或迁移至存储/展示层。
