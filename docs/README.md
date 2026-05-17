# Gaia Documentation

Gaia 的文档按读者**正在问的问题**分为 6 个顶层区，每个区只解决一类问题：

| 区 | 你在问 | 入口示例 |
|---|---|---|
| **Tutorials** | "我第一次接触 Gaia，能不能带我走一遍？" | [What Is Gaia?](for-visitors/what-is-gaia.md) · [Quick Start](for-users/quick-start.md) |
| **How-To Guides** | "我有一个具体任务要解决，给我配方" | [Hole And Bridge](for-users/hole-bridge-tutorial.md) · [Choosing A BP Algorithm](foundations/bp/choosing-algorithm.md) |
| **Examples** | "给我看一个完整的领域场景，展示 Gaia 怎么用" | [Bayes — LDL Trial](examples/bayes-ldl-trial.md) · [Formula AST — Custom Predicates](examples/causal-formula-ast.md) |
| **Reference** | "我知道要查什么，给我精确规格 / API / 命令" | [Language Reference](for-users/language-reference.md) · [CLI Commands](for-users/cli-commands.md) · [Engine API](reference/engine/index.md) · [CLI Internals](reference/cli/index.md) · [Contracts](foundations/contracts/review-report.md) |
| **Foundations** | "为什么 Gaia 是这样的？把推导链给我" | [Foundations Overview](foundations/README.md) · [Theory](foundations/theory/01-plausible-reasoning.md) · [Belief Propagation](foundations/bp/inference.md) |
| **Policy & Migration** | "文档自身的规则、版本迁移说明" | [Documentation Policy](documentation-policy.md) · [Migration to alpha 0](migration.md) |

侧边栏与本表完全对应。这是 [Diátaxis](https://diataxis.fr) 的一个变体——把"explanation"展开为带顺序的 **Foundations** 区（因为 theory 文档是真正的 derivation chain），并增加独立的 **Examples** 区（完整领域案例，区别于 How-To 的短配方）。

> **关于命名变更**：之前的 "Start Here" / "User Reference" / "Foundational Docs" / "Deep Reference" 标签已合并为这 5 个区。如果你来自旧链接，URL 路径不变（`for-visitors/`、`for-users/`、`foundations/`、`reference/` 仍然有效），只是 nav label 变了。背景见 [RFC #647](https://github.com/SiliconEinstein/Gaia/issues/647)。

## Choose your path

### 我想了解 Gaia 是什么
你是访问者、研究者、评估者。

→ 从 [What is Gaia?](for-visitors/what-is-gaia.md) 开始。

### 我想用 Gaia 写知识包
你是研究者或正在使用 Gaia CLI 的研究 agent。

→ 跟着 [Quick Start](for-users/quick-start.md) 走完一次完整流程，然后按需查阅：

- [Hole And Bridge](for-users/hole-bridge-tutorial.md) — 跨包补洞 / bridge 机制（How-To）
- [Choosing A BP Algorithm](foundations/bp/choosing-algorithm.md) — 给你的图选合适的 BP 算法（How-To）
- [Bayes — LDL Trial](examples/bayes-ldl-trial.md) — 多假设贝叶斯比较完整案例（Example）
- [Formula AST — Custom Predicates](examples/causal-formula-ast.md) — 自定义谓词 + 类型安全（Example）
- [Language Reference](for-users/language-reference.md) — DSL 语法查询（Reference）
- [CLI Commands](for-users/cli-commands.md) — 用户面 CLI 命令查询（Reference）

### 我想开发 Gaia
你是给 Gaia 代码库写代码的开发者。

→ 入口是 [Engine API Overview](reference/engine/index.md)，然后按需深入：

- [CLI Internals](reference/cli/index.md) — engine-internal CLI invocation 规格（Reference）
- [CLI Workflow](foundations/cli/workflow.md) — 本地 authoring / compilation / inference 的设计原则（Foundations）
- [Gaia Lang Design](foundations/gaia-lang/knowledge-and-reasoning.md) — authoring 模型、actions、formulas、helper claims
- [Gaia IR Design](foundations/gaia-ir/01-overview.md) — persistent structure、identity、lowering、validation
- [Gaia Lang API](reference/engine/lang.md) / [Gaia IR API](reference/engine/ir.md) — 当前 Python 模块自动生成的接口
- LKM server 在 [gaia-lkm repo](https://github.com/SiliconEinstein/gaia-lkm) 维护

## Foundations: derivation chain by rate of change

Foundations 区的子目录按 "内容多久变一次" 组织。读者依据想了解的层次进入：

| 子目录 | 它回答 | 变更频率 |
|---|---|---|
| [Theory](foundations/theory/01-plausible-reasoning.md) | Why does Gaia reason this way? Cox / MaxEnt / propositional operators / causality | Never |
| [Belief Propagation](foundations/bp/inference.md) | How does inference run on Gaia IR? Cromwell, factor types, algorithm parameters | Sometimes |
| [Gaia Lang Design](foundations/gaia-lang/knowledge-and-reasoning.md) | What is the authoring language model? | Sometimes |
| [Gaia IR Design](foundations/gaia-ir/01-overview.md) | What is the persistent reasoning contract? | Sometimes |
| [Ecosystem](foundations/ecosystem/01-product-scope.md) | What are Gaia's product / system design choices? | Rarely |
| [Review Pipeline](foundations/review/review-pipeline.md) | How does package review and curation flow? (process narrative; the report contracts live in Reference / Contracts) | Sometimes |
| [CLI Workflow](foundations/cli/workflow.md) | How does local authoring map to CLI commands? (design layer; the user-facing command list lives in Reference / CLI Commands) | Often |
| [Python API](reference/engine/index.md) | What do current modules expose? (Reference 区，从 docstring 自动生成) | Often |
| LKM | How does the server work? | [gaia-lkm repo](https://github.com/SiliconEinstein/gaia-lkm) |

## Other Resources

| Directory | Contents |
|-----------|----------|
| `archive/` | Historical design docs, previous foundations versions, completed plans |
| `design/` | Scaling belief propagation, engineering related work |
| `ideas/` | Design ideas, academic related work survey |
