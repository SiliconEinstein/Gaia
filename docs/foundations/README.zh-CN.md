# 基础文档

本目录包含 Gaia 当前激活的基础文档。

当任务影响以下任何内容时，请使用此目录：

- 整体系统语义或术语
- 包、图、存储等契约
- CLI 与共享侧生命周期边界
- 当前运行时实现

## 从这里开始

- [基础文档治理策略](documentation-policy.md)
- [系统概览](system-overview.md)
- [Gaia 词汇表](meaning/vocabulary.md)
- [基础重置计划](foundation-reset-plan.md)

## 当前结构

基础文档正在逐步重组为三层：

- **Meaning**：概念是什么意思
- **Contracts**：作者侧与系统侧稳定契约
- **Runtime**：当前实现实际上怎么运行

迁移还在进行中，因此一部分激活文档仍然保留在旧子目录里。

## 当前推荐阅读顺序

### Meaning

- [Gaia 词汇表](meaning/vocabulary.md) — 基础术语的规范出处
- [产品范围](product-scope.md) — Gaia 是什么、当前 baseline 是什么
- [理论基础](theory/theoretical-foundation.md) — Jaynes 式认识论动机
- [领域模型](domain-model.md) — 旧的意义层文档，后续会退役
- [推理理论](theory/inference-theory.md) — 当前语义层 operator 理论

### Contracts

- [Gaia Language 规范](language/gaia-language-spec.md)
- [Gaia Language 设计](language/gaia-language-design.md)
- [语言设计原理](language/design-rationale.md)
- [类型系统方向](language/type-system-direction.md)
- [图 IR](graph-ir.md)
- [Gaia CLI 命令生命周期](cli/command-lifecycle.md)
- [审查流水线与发布工作流](review/publish-pipeline.md) — 迁移期的共享侧工作流文档

### Runtime

- [Gaia CLI 运行时边界](cli/boundaries.md)
- [图 IR 上的 BP](bp-on-graph-ir.md)
- [服务器架构](server/architecture.md)
- [服务器存储模式](server/storage-schema.md)

## 迁移说明

- 激活文档应优先使用 `Gaia CLI` 与 `Gaia LKM` 作为主要概念分界。
- 激活文档应把作者侧描述为 Typst package / Gaia package，而不是 YAML package。
- 规范的本地 CLI 生命周期是 `build -> infer -> publish`；`review` 属于共享侧生命周期。

## 历史文档

初始构建过程中的历史设计文档和实现计划保存在 [`../archive/`](../archive/) 中。

## 工作规则

当变更影响架构或跨模块行为时，应在同一分支中更新相关基础文档，或者在 PR 中明确说明为何推迟更新。
