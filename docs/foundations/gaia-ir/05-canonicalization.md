# Canonicalization — 规范化

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 Gaia IR 与公共协作生态（package repo / Official Registry / LKM Repo / review artifacts）的结构边界。变更需要独立 PR 并经负责人审查批准。

## 1. Scope 划分

Gaia IR 只管理 **local package 内部的结构表示**。  
跨 package 的“是不是同一个命题”“是不是旧论证的改写”“会不会 double count”属于 **公共协作生态中的发现、调查与公开制品**，不是 core IR 里的 runtime primitive，也不是 Official Registry 自身直接算出的 judgment。

这里首先要固定一个前提：

- **local-only IR** 指的是 local ownership
- **不是** local-only reference closure

也就是说，一个 `LocalCanonicalGraph` 可以合法地把 external occurrences 显式带入图中；canonicalization 真正要解决的，是这些跨包 occurrence 之间后续如何被公开发现、讨论和使用。

| 概念 | 所属层 | 说明 |
|------|--------|------|
| QID（name-addressed identity） | IR | `{namespace}:{package_name}::{label}`，标识 package 内的一次 Knowledge occurrence |
| `content_hash`（内容指纹） | IR | `SHA-256(type + content + sorted(params))`，用于匹配与去重候选发现 |
| `equivalence` Operator | IR | 作者在包中显式声明两个 claim 的真值等价 |
| `metadata` / provenance | IR | 保留来源、上下文、相关引用等可审计信息 |
| registered package versions | Official Registry | 哪些 package 版本进入官方索引 |
| validated review reports | Official Registry + package repo | reviewer 提交并通过 gate 的 review artifacts |
| relation reports / research tasks | Official Registry Issues / LKM Repo | 人类或 LKM 提交的关系线索与调查入口 |
| curation / investigation packages | package repo + Registry index | 对 duplicate / refinement / contradiction 等关系的公开主张 |

**边界原则：**

- Gaia IR 负责把 package 内发生过什么写清楚
- Official Registry 负责索引 package、assignment、review gate 与 issue 入口，而不是替所有人做最终关系判断
- user、Review Server、LKM curation service 通过 package / review finding / issue 把跨包关系带入公共记录
- 任意下游 LKM 基于这些公开信息，自行构建不 double count 的全局图

## 2. Gaia IR 需要保留什么信息

### 2.1 Occurrence Identity

`Knowledge.id` 使用 QID：

```text
{namespace}:{package_name}::{label}
```

它表达的不是“全局 canonical proposition 是谁”，而是：

- 这是哪个 package
- 在该 package 中是哪一个 Knowledge 节点

这让 registry、reviewer、LKM 和其他研究者都能无歧义地引用 “package A 的 claim X” 和 “package B 的 claim Y”，而不必先假定二者已经是同一个命题。

### 2.2 Content Fingerprint

`content_hash = SHA-256(type + content + sorted(parameters))`

它不带 package 信息，因此同内容节点在不同 package 中会共享同一个哈希。它的作用是：

- 发现跨 package 的精确内容匹配候选
- 作为更昂贵语义比对前的快速预筛选
- 辅助 reviewer、LKM 或研究者建立 duplicate / refinement 审查队列

`content_hash` **不是身份标识**。  
同一个 `content_hash` 不能推出“就是同一个 proposition”；它只说明内容足够接近，值得进一步审查。

### 2.3 显式语义关系

Gaia IR 允许作者在 graph 中用 `equivalence` Operator 声明两个 claim 真值等价。  
这两个 claim 既可以都是本地节点，也可以包含通过 external reference 引入的 foreign QID。

这类 Operator 的意义是：

- 把作者主张的语义关系显式写进公开 package
- 让 reviewer 能审查这个关系本身
- 为后续 review / curation / investigation 提供证据

但它**不是**跨 package identity merge primitive。  
`equivalence(A, B)` 说明的是某个 package 公开提交的真值约束主张，不等于公共生态已经达成 “A 和 B 是同一个 canonical proposition” 的结论。

### 2.4 Provenance 与上下文

package 内的 `metadata`、`background`、`provenance` 等字段，需要尽可能保留：

- 结论来自哪里
- 论证依赖哪些背景
- 新包是在补证据、细化旧论证，还是反驳旧论证

这些信息本身不直接做概率运算，但它们是 reviewer、LKM 和其他研究者判断是否存在 double counting 风险的重要上下文。

## 3. Gaia IR 不定义什么

当前 core IR **不定义**以下对象或语义：

- global canonical ID
- `CanonicalBinding`
- “把两个旧结论合并成第三个结论”的 `binding` Strategy
- “声明这些路径独立”的 `independent_evidence` Strategy
- 某个 backend / LKM 如何 rewrite 全局图

原因不是这些问题不重要，而是它们不该被硬编码成 core IR 的 strategy primitive。

从第一性原理看，double counting 问题首先是：

- 不同 package 的 claim occurrence 是否在说同一个 proposition
- 多条支持路径是否共享关键上游因
- 新 package 是在增加新证据，还是只是在重写旧论证

这些都是 **public review / curation** 问题，而不是 package-local runtime operator 问题。

## 4. Canonicalization 应如何进入公共记录

当后来者发现两个 package 的结论实际上是：

- duplicate
- refinement
- contradiction
- unresolved

这类判断本身应通过新的 Gaia package（例如 investigation / review / curation artifact），或通过 review finding / relation report / LKM research task 进入公共记录。

core IR 在这里的职责不是直接“合并图”，而是保证这些公开制品至少能够：

- 无歧义地引用既有 occurrence
- 提供可审查的论证内容
- 保留产生该主张或 finding 的 provenance

公共协作生态至少应公开暴露：

- 已注册的 package 版本
- occurrence 引用（package/version/qid）
- validated review reports 与其中的 relevant findings
- Official Registry issues / LKM Repo research tasks
- 已公开的 curation / investigation packages，以及它们声明的 supersession / refinement / rebuttal / duplicate 等关系

这些是下游 LKM 构建 anti-double-counting graph 的充分输入。  
具体如何 materialize 成内部图结构，不由 Gaia IR 本体规定。

> **Future work:** imported reference 的附加 metadata / provenance schema 仍待单独设计。当前文档先固定边界：cross-package duplicate handling 不在 core IR 内伪装成新的 Strategy type。

## 5. `content_hash` 的角色

| 用途 | 说明 |
|------|------|
| 跨包同内容精确匹配 | review / curation 发现 duplicate 候选的快速路径 |
| 包内变更检测 | 同一 label 的 content 变更时 hash 变化 |
| 去重候选筛选 | 作为 embedding/semantic match 前的预过滤 |

`content_hash` 不是身份，QID 才是 occurrence identity。  
公共生态中的 canonicalization 判断必须建立在公开可审查的 package 与 review 记录上，而不是单纯建立在 hash 命中上。

## 6. FormalExpr 中间 Knowledge 的创建

展开操作可能需要创建中间 Knowledge（如 deduction 的 conjunction 结果 `M`、abduction 自动补齐的 `AlternativeExplanationForObs`、以及相应的 helper claim）。这些 Knowledge 由执行展开的 compiler/reviewer/agent **显式创建**，不由 FormalExpr 自动产生。

在当前 IR API 中，这一步通常通过专门的 formalization 入口一次性完成：调用方提供 leaf `Strategy`（或等价输入），IR 侧生成中间 Knowledge 与 canonical `FormalExpr`，再落成最终 `FormalStrategy`。**中间 Knowledge 仍然是显式对象，但一般不要求用户手写每个 Operator 与中间 claim ID。**

中间 Knowledge 获得 QID（`{ns}:{pkg}::{generated_label}`），generated_label 以 `__` 开头表示自动生成。

## 7. FormalExpr 的生成方式

- **所有当前已启用的命名策略**（`deduction`、`elimination`、`mathematical_induction`、`case_analysis`、`abduction`、`analogy`、`extrapolation`）：其 canonical `FormalExpr` 骨架由 `type` 和接口节点唯一确定，IR 侧应自动生成
- 对 `abduction` 这类家族，formalization 还可以自动补齐所需的 public interface claim（如 `AlternativeExplanationForObs`），并生成配套的 structural helper claim 与 canonical `FormalExpr`
- `reductio` 与 `induction` 在 theory 层保留，但 Gaia IR core 当前 defer；若需要表达 `induction`，先展开成多条共享同一结论的 abduction
- 对 `analogy`、`extrapolation`，formalization 复用显式给定的接口 claim（如 `BridgeClaim`、`ContinuityClaim`），再生成所需 helper claim
- 规范中的 `formal_expr` 示例应理解为 **formalization 之后的 canonical stored form**，而不是要求用户在正常构图时手写 `operators`
- **`toolcall` / `proof`**：deferred，未引入
