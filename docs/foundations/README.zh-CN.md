# 基础文档

本目录是 Gaia 下一次基础重置的工作区域。

当任务影响以下任何内容时，请使用此目录：

- 整体架构
- 模块边界
- API 契约
- 图模型语义
- 存储模式或后端能力假设
- 领域词汇表

## 当前状态

Gaia 现在在 [../architecture-rebaseline.md](../architecture-rebaseline.md) 中有文档化的重置诊断。

该重置的执行计划位于此处：

**全局（跨子系统）：**

- [基础重置计划](foundation-reset-plan.md)
- [产品范围](product-scope.md)
- [系统概览](system-overview.md)
- [领域模型](domain-model.md) — 已降级为跳转页，规范内容见 newer ontology / language / review 文档

**图 IR：**

- [图 IR](graph-ir.md) — Gaia Language 与 BP 之间的规范因子图 IR

**理论：**

- [理论基础](theory/theoretical-foundation.md) — Jaynes 纲领
- [推理理论](theory/inference-theory.md) — BP 算法理论

**图 IR 上的 BP：**

- [图 IR 上的 BP](bp-on-graph-ir.md) — 因子函数、门语义、模式/地面 BP 交互

**语言：**

- [Gaia Language 规范](language/gaia-language-spec.md)
- [Gaia Language 设计](language/gaia-language-design.md)
- [语言设计原理](language/design-rationale.md)
- [类型系统方向](language/type-system-direction.md)

**CLI：**

- [Gaia CLI 运行时边界](cli/boundaries.md)
- [Gaia CLI 命令生命周期](cli/command-lifecycle.md)

**审查：**

- [审查流水线与发布工作流](review/publish-pipeline.md) — 当前的自我审查/同行审查/发布契约
- [构建、对齐和审查架构](review/architecture.md) — 已取代的历史参考

**服务器：**

- [服务器架构](server/architecture.md)

## 预期输出

计划是在恢复重大代码重构之前建立一小组持久的基础文档：

1. `product-scope.md`
2. `system-overview.md`
3. `theory/scientific-ontology.md`（科学对象模型和 BP 边界）
4. `theory/theoretical-foundation.md`（以 Jaynes 为中心的理论基础）
5. `language/gaia-language-spec.md`（Gaia Language 规范）
6. `graph-ir.md`（图 IR — 规范因子图层）
7. `theory/inference-theory.md`（BP 算法和 operator 理论）
8. `review/service-boundaries.md`（ReviewService vs CurationService）
9. `review/package-artifact-profiles.md`（knowledge / investigation / review / rebuttal 包语义）
10. `review/publish-pipeline.md`（自我审查、同行审查和发布工作流）
11. `server/architecture.md`（服务器架构）
12. `server/storage-schema.md`（服务器存储模式）
13. `domain-model.md`（兼容跳转页，不再是规范来源）
14. `cli/boundaries.md`（Gaia CLI 运行时分层）

这些文件尚未全部存在。此目录是它们应该被创建和保持最新的地方。

## 文件夹布局

- `theory/`：理论基础与 ontology（Jaynes、科学对象模型、BP operator 理论）
- `language/`：Gaia 形式语言规范、设计和设计原理
- `cli/`：Gaia CLI 运行时边界和未来的 CLI 特定文档
- `review/`：审查、发布语义，以及 review / curation / artifact-profile 边界文档
- `server/`：服务器架构、存储模式、API 契约

## 历史文档

初始构建过程中的历史设计文档和实现计划保存在 [`../archive/`](../archive/) 中。

## 工作规则

当变更影响架构或跨模块行为时，相关的基础文档应在同一分支中更新，或 PR 应明确说明为何推迟文档更新。
