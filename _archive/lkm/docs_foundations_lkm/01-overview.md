# LKM 概述

> **Status:** Target design

## 定位

Large Knowledge Model (LKM) 是一个建立在概率推理因子图上的计算注册中心。它接收结构化的知识内容，构建全局 FactorGraph，通过 belief propagation 计算所有命题的后验信念。

LKM 的核心数据结构是 **FactorGraph**——一张由 variable nodes（命题）和 factor nodes（命题之间的概率/确定性依赖关系）组成的二部图。LKM 采用 **Local / Global 对偶 FactorGraph** 架构：Local FactorGraph 保留 ingest 后的完整内容（文本、推理步骤），Global FactorGraph 只保留图结构和参数化信息，不存文本内容。两者通过 CanonicalBinding 桥接。

### 与 Gaia 生态的关系

LKM 是 [Gaia 生态](https://github.com/SiliconEinstein/Gaia/tree/main/docs/foundations/ecosystem/) 的服务端组件。Gaia 生态定义了知识的创作、编译、发布和审查流程；LKM 负责接收已发布的内容，在全局尺度上做推理和维护。

```
Gaia CLI (作者端)                LKM (服务端)
  编写 → 编译 → 本地推理           接收 → 集成 → 策展 → 全局推理
  产出 Gaia IR                     产出 Global FactorGraph + Beliefs
```

LKM 不接触 Gaia Lang（Typst DSL），不做编译，不做本地推理。它的输入是已编译的 Gaia IR 或其他结构化格式，输出是全局信念状态。

## 核心数据模型

### FactorGraph

FactorGraph 由两种节点组成：

- **Variable Node**：对应一个命题（claim、setting、question）。分为 `public`（作者显式声明）和 `private`（lowering FormalStrategy 产生的中间节点）。
- **Factor Node**：分为两类，严格对齐 [Gaia IR](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/02-gaia-ir.md)：
  - `strategy`（概率性）：`infer`、`noisy_and` — 携带 conditional probability
  - `operator`（确定性）：`implication`、`equivalence`、`contradiction`、`complement`、`conjunction`、`disjunction`、`instantiation` — 无概率参数

```
Variable: "YBCO superconducts at 90K"        (public)
    │
Factor: strategy/infer
    │
Variable: "YBCO has zero resistance"          (public)
```

概率参数不存储在节点上，而是通过独立的参数化层（PriorRecord、FactorParamRecord）管理，对齐 [Gaia IR 参数化契约](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/06-parameterization.md)。势函数详见 [势函数](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/bp/potentials.md)。

### 为什么是 FactorGraph

FactorGraph 是 belief propagation 算法的原生数据结构。LKM 当前的推理引擎是 loopy BP，因此核心数据模型直接采用 FactorGraph。

这是一个有意识的耦合决策：数据模型服务于推理算法。如果未来推理引擎从 BP 演进为 MCMC 或其他方法，核心数据模型可能需要相应调整。当前设计不为这种可能性预留抽象层；需要时再重构。

### 与 Gaia IR 的关系

[Gaia IR](https://github.com/SiliconEinstein/Gaia/tree/main/docs/foundations/gaia-ir/) 是 Gaia 生态的中间表示层，编码推理超图的拓扑结构（Knowledge、Strategy、Operator），但不包含概率值。IR 的设计目的是解耦 M 个前端和 N 个后端。

FactorGraph 是 IR 经过 **lowering**（确定性展开到 leaf strategy 和 operator 级别 + 注入参数化）后的产物。LKM 不直接在 IR 上运作——IR 是传输格式，进入 LKM 后被 lower 为 FactorGraph，之后不再保留。

```
Gaia IR (交换格式)                  FactorGraph
  Knowledge        ──lower──→  Variable Node (public)
  FormalStrategy   ──lower──→  Operator Factor Nodes + Variable Nodes (private)
  Leaf Strategy    ──lower──→  Strategy Factor Node
  Operator         ──lower──→  Operator Factor Node
  CompositeStrategy ──lower──→  展开为 leaf strategies（不出现在 FactorGraph）
```

Lowering 是确定性的：相同的 IR + 参数化输入永远产出相同的 FactorGraph。

## 数据来源与 Ingest

LKM 从两个数据源接收内容，通过不同的 ingest pipeline 汇聚到同一个 global FactorGraph。

### Pipeline A：社区增量内容（Gaia IR）

面向社区作者通过 [Gaia 生态](https://github.com/SiliconEinstein/Gaia/tree/main/docs/foundations/ecosystem/) 发布的知识包。规模：万至十万量级。

```
作者编写 Gaia Lang
  → gaia build (编译为 LocalCanonicalGraph)
  → gaia publish (发布到 Registry)
  → Registry 分配 Review Server → 审查 → rebuttal → 作者 merge review reports
  → Registry CI 验证（编译重现 ✓、依赖可解析 ✓、review reports 合规 ✓）
  → 包版本进入 Official Registry 索引
  → LKM 拉取已注册包 + validated review reports
  → lower: Gaia IR + validated review reports → local FactorGraph
  → integrate 到 global FactorGraph
```

Registry 是 [GitHub 仓库](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/04-registry-operations.md)（Julia General registry 模型），通过 PR 管理包的注册和审查。LKM 不参与 Registry 治理——它只消费通过完整 registry 验证流程的包。

### Pipeline B：存量论文（XML）

面向已发表的科学文献批量 ingest。规模：千万至亿量级。

```
论文 XML (arXiv, PubMed, ...)
  → rule-based extraction: 提取命题、推理关系、引用关系
  → local FactorGraph (variable nodes + factor nodes) + 参数化记录
  → integrate 到 global FactorGraph
```

XML 到 local FactorGraph 的转换是 **rule-based 确定性过程**，不涉及 ML。论文 XML 中的结构化信息（claims、reasoning、citations）直接映射到 variable nodes 和 factor nodes。

这条路径不经过 Gaia Lang、Gaia IR、也不经过 Registry。

### Source Class

两个数据源的参数质量差异通过参数化层的 `ParameterizationSource.source_class` 区分：`official`（经 registry 验证的 review reports）、`heuristic`（XML 提取规则估计）、`provisional`（mock / 自动化 review）。高信任层级的参数优先，`official` 永远不被 `heuristic` 覆盖。详见 [02-storage.md](02-storage.md)。

## 核心处理流程

### Integrate（同步，确定性去重）

Ingest 后的 local FactorGraph 集成到 global FactorGraph，通过 CanonicalBinding 记录 local → global 的身份映射。包含两类确定性去重：

- **Variable 去重**：content_hash 匹配 → 复用已有 global variable，写入 CanonicalBinding（`decision=match_existing`），更新 `local_members`
- **Factor 去重**：premises + conclusion + factor_type + subtype 匹配 → 复用已有 global factor，追加 FactorParamRecord

不做语义匹配。保证完全相同的命题和推理关系从 integrate 开始就有稳定的 global ID。

详见 [03-lifecycle.md](03-lifecycle.md)。

### Curation（异步，语义匹配）

分为 discovery 和 resolution 两阶段，对齐 [上游 ecosystem 治理模型](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/05-review-and-curation.md)：

- **Discovery（LKM 内部）**：发现语义重复（embedding 相似度）、冲突（BP 诊断）、结构问题 → 产出提案
- **Resolution（通过 registry）**：提案打包为 curation package → 正常 registry 流程 → integrate 生效

LKM 不直接修改全局图结构。所有语义判断通过 curation package 走 registry 审查后才生效。

详见 [04-curation.md](04-curation.md)。

### Belief Propagation

Curation 完成后，从参数化层按 resolution_policy 解析参数，在 global FactorGraph 上运行 loopy BP，结果写入 BeliefSnapshot。

详见 [05-global-inference.md](05-global-inference.md)。

## 读取端

LKM 通过 HTTP API 暴露 global FactorGraph 的内容：

- Variable nodes：命题浏览、信念查询、来源追溯
- Factor nodes：推理关系浏览
- 图拓扑：子图查询、DAG 可视化
- 全文搜索：基于 variable 内容的 BM25 搜索
- Belief 历史：BeliefSnapshot 查询

端点详情见 [06-api.md](06-api.md)。

## Scope 边界

### LKM 做什么

- 接收 local FactorGraph（从 Gaia IR lower 或从 XML 提取）
- 集成到 global FactorGraph（含确定性去重）
- 异步 curation（语义 canonicalization、去重、冲突检测）
- 全局 belief propagation
- 读取 API

### LKM 不做什么

- **不做编译**：Gaia Lang → Gaia IR 是 CLI 的职责
- **不做本地推理**：`gaia infer` 是 CLI 功能，LKM 只做全局推理
- **不做 Registry 治理**：包注册、reviewer 分配、PR 审批是 Registry 的职责
- **不存储 Gaia IR**：IR 是传输格式，lower 后不保留
- **不接触 Gaia Lang**：LKM 完全不了解 Typst DSL

## 存储模型

| 存储内容 | 说明 |
|---------|------|
| **Local FactorGraph** (per package/paper) | lower/extract 后的完整内容（含 content、steps），按来源归档 |
| **Global FactorGraph** | 图结构索引（variable nodes 无 content，factor nodes 无 steps） |
| **CanonicalBinding** | local QID → global gcn_id 的身份映射，含 decision/reason |
| **参数化层** | PriorRecord + FactorParamRecord + ParameterizationSource |
| **BeliefSnapshot** | BP 运行结果（含 resolution_policy、convergence info） |

详见 [02-storage.md](02-storage.md)。

## 未来演进

- **粗粒化子图**：将子图折叠为单个 factor，在不同粒度上做 BP。需要单独设计。
- **增量 BP**：新数据 ingest 后只更新受影响的子图，而非全图重算。
- **推理算法演进**：当前基于 loopy BP。如果未来切换到 MCMC 等其他推理方法，核心数据模型可能需要随之调整。
