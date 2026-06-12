# 基础文档

Gaia 的概念性基础文档，按理论、生态系统、Gaia Lang 设计、Gaia IR 设计、推理后端、审查管线和 CLI 工作流组织。

与 Python 模块一一对应的 per-name API 文档不在这里维护；请看
[Python API Reference](../reference/engine/index.md)，它从当前代码的 docstring
和 type hints 自动生成。这里保留的是心智模型、设计边界、持久化契约和跨模块语义。

## theory/ — 理论基础

推导链：plausible-reasoning → maxent-grounding → propositional-operators → reasoning-strategies → formalization-methodology → factor-graphs → belief-propagation → causality-and-jaynes

**四层结构：**

**Layer 1 — Jaynes 理论（纯理论，不涉及因子图/BP）：**
- [`01-plausible-reasoning.md`](theory/01-plausible-reasoning.md) — Cox 定理、概率唯一性、弱三段论
- [`02-maxent-grounding.md`](theory/02-maxent-grounding.md) — MaxEnt/Min-KL、从约束到后验

**Layer 2 — 科学本体论（命题与算子，不涉及因子图/BP）：**
- [`03-propositional-operators.md`](theory/03-propositional-operators.md) — 最小原料 {¬, ∧, π}、派生算子、↝ 软蕴含、完备性
- [`04-reasoning-strategies.md`](theory/04-reasoning-strategies.md) — 知识类型、九种推理策略作为 ↝ 微观结构
- [`05-formalization-methodology.md`](theory/05-formalization-methodology.md) — 从科学文本到命题网络的方法论

**Layer 3 — 计算方法（因子图 + BP 作为大规模近似）：**
- [`06-factor-graphs.md`](theory/06-factor-graphs.md) — 命题网络到因子图的映射、势函数
- [`07-belief-propagation.md`](theory/07-belief-propagation.md) — BP 近似推理算法

**Layer 4 — 本体扩展（v0.6+，因果机制作为平行本体）：**
- [`08-causality-and-jaynes.md`](theory/08-causality-and-jaynes.md) — 三层本体（命题 / 推理步 / 世界结构）、Mechanism 与 Jaynesian 命题层的边界、do() 查询语义

## 生态系统 — 设计哲学（极少变更）

- [产品范围](ecosystem/01-product-scope.md) — Gaia 是什么、为何存在
- [去中心化架构](ecosystem/02-decentralized-architecture.md) — 去中心化包管理和推理架构
- [包的创建与发布](ecosystem/03-authoring-and-publishing.md) — 作者从创建包到发布的旅程
- [Registry 运作](ecosystem/04-registry-operations.md) — 注册、去重、推理链激活
- [审核与策展](ecosystem/05-review-and-curation.md) — Review Server + LKM curation
- [多级推理与质量涌现](ecosystem/06-belief-flow-and-quality.md) — 三级推理、错误修正
- [文档维护策略](../documentation-policy.md) — 文档维护规则

## Gaia Lang — 编著语言设计

- [知识类型与推理语义](gaia-lang/knowledge-and-reasoning.md) — Gaia Lang 的心智模型、Action 层、helper claim 和 legacy 边界
- [Formula Logic](gaia-lang/formula-logic.md) — `claim(formula=...)`、FormulaGraph、formula diagnostics 与 BP/probability 的分工
- [谓词逻辑](gaia-lang/predicate-logic.md) — Variable、Domain、Formula AST、forall/exists 与 grounding/lowering 边界
- [Bayes 语义](gaia-lang/bayes.md) — 模型、预测分布、似然和 Bayes action 的语义边界
- [包模型](gaia-lang/package.md) — pyproject.toml、命名规范、目录布局、priors.py
- [Python API Reference](../reference/engine/index.md) — per-name API、signature 和 docstring 自动生成

## Gaia IR — CLI 与 LKM 之间的共享契约

- [概述](gaia-ir/01-overview.md) — Gaia IR 与相邻层总览
- [结构定义](gaia-ir/02-gaia-ir.md) — Knowledge、Strategy、Operator、FormalExpr
- [Identity And Hashing](gaia-ir/03-identity-and-hashing.md) — 对象身份、内容指纹与图哈希的边界
- [Helper Claims](gaia-ir/04-helper-claims.md) — 中间 claim 的 public/private 边界与命名约定
- [规范化](gaia-ir/05-canonicalization.md) — local canonical 到 global canonical 的映射契约
- [参数定义](gaia-ir/06-parameterization.md) — 原子记录、resolution policy
- [Lowering](gaia-ir/07-lowering.md) — Gaia IR 被 backend 消费时的 lowering 边界
- [Validation](gaia-ir/08-validation.md) — Gaia IR 的结构校验与分层边界
- [Gaia IR API](../reference/engine/ir.md) — Pydantic models、字段、类型签名和源码入口自动生成

## BP — 基于 Gaia IR 的计算

- [因子势函数](bp/potentials.md) — 各因子类型的势函数
- [推理](bp/inference.md) — BP 算法应用于 Gaia IR
- [Diagnostic Probabilities](bp/diagnostic-probabilities.md) — 用 joint query 为 logic warning 计算 reviewer-facing 概率
- [局部与全局](bp/local-vs-global.md) — CLI 局部推理 vs LKM 全局推理
- [BeliefState](bp/belief-state.md) — BP 输出、可重现性

## Review — 审查管线

- [审阅管线](review/review-pipeline.md) — 验证 → 审阅 → 门控

## CLI — 本地编著与推理

- [工作流](cli/workflow.md) — compile → check → infer → register 完整管线
- [编译与校验](cli/compilation.md) — `gaia build compile` / `gaia build check` 内部机制
- [推理管线](cli/inference.md) — `gaia run infer`：priors.py、参数化、BP
- [注册流程](cli/registration.md) — `gaia pkg register` 与 registry 协议
- [Research Loop CLI](cli/research-loop.md) — `gaia research` 的 package/inquiry-first 领域探索与评估工作流

## LKM — 计算注册中心（服务端）

> LKM 文档已迁移至 [gaia-lkm](https://github.com/SiliconEinstein/gaia-lkm/tree/main/docs/foundations/lkm/) 仓库维护。
