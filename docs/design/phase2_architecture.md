# Gaia Phase 2 架构总览：从推理超图到知识包管理器

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 状态 | Draft |
| 前置文档 | [phase1_billion_scale.md](phase1_billion_scale.md) — Phase 1 系统设计 |
| 整合文档 | [knowledge_package_system.md](knowledge_package_system.md), [version_dependency_environment.md](version_dependency_environment.md), [question_as_discovery_context.md](question_as_discovery_context.md), [theoretical_foundations.md](theoretical_foundations.md), [agent_verifiable_memory.md](agent_verifiable_memory.md), [text_structuring_service.md](text_structuring_service.md), [verification_providers.md](verification_providers.md) |

---

## Abstract

随着 AI agent 深度参与科学研究流程，我们正在进入 agentic science at scale 的时代——agent 自主检索文献、提出假说、设计实验、验证结论。然而，agent 操作的知识基础设施尚未就绪：现有系统存储事实但不建模推理过程，不量化可信度，不追踪依赖关系，也不处理矛盾。当一篇论文被撤稿或新实验结果发表时，其对数百万下游结论的连锁影响几乎无法系统性传播。缺乏这样的基础设施，agent 的推理只能建立在不可验证、不可溯源的静态快照之上。

Gaia 将知识建模为概率推理超图：节点是命题，超边是推理链（前提→结论），每条信息附带连续可信度。矛盾不是需要消除的错误，而是知识演化的常态——系统通过 belief propagation 自动计算全局一致的信念分布，新证据的影响沿推理链传播，无需人工裁决。

在大规模知识管理层面，我们发现版本演化、依赖追踪、状态可复现等挑战与软件包管理（Cargo, Julia Pkg）在逻辑上同构——两者本质上都是 Horn clause 系统上的依赖传播。基于此，Gaia 引入 Knowledge Package 概念：一篇论文或一个理论构成一个命名、版本化的知识包，可以声明依赖、导出结论、发布到注册中心。与软件包管理的关键差异在于，知识依赖是软性的——节点内容不可变，引用永远不会断裂，belief propagation 本身就是冲突解析器，无需 SAT 约束求解。系统还提供统一的环境模型，支持在当前知识状态上创建轻量分支进行反事实推理，为 agent 和研究者提供系统化的思想实验能力。

在这套基础设施之上，我们的长期目标是构建 Large Knowledge Model (LKM)——一个十亿级命题、百亿级推理链的全域学术知识模型。与 LLM 将知识压缩在参数中不同，LKM 的每一条知识都是可寻址、可溯源、可验证的，其可信度随新证据动态演化。LKM 不替代 LLM，而是为其提供一个结构化的、概率一致的外部知识底座。

---

## 目录

0. [Abstract](#abstract)
1. [从 Phase 1 到 Phase 2：什么变了](#1-从-phase-1-到-phase-2什么变了)
2. [核心概念](#2-核心概念)
3. [架构总览](#3-架构总览)
4. [数据模型](#4-数据模型)
5. [存储层](#5-存储层)
6. [Commit + Publish 工作流](#6-commit--publish-工作流)
7. [搜索引擎](#7-搜索引擎)
8. [推理引擎](#8-推理引擎)
9. [API 设计](#9-api-设计)
10. [CLI 设计](#10-cli-设计)
11. [部署架构](#11-部署架构)
12. [Phase 1 → Phase 2 迁移](#12-phase-1--phase-2-迁移)
13. [实施优先级](#13-实施优先级)

---

## 1. 从 Phase 1 到 Phase 2：什么变了

Phase 1 构建了推理超图的核心能力：节点、超边、commit 工作流、三路搜索、局部 BP。Phase 2 的核心认知转变是：

**Gaia 不只是一个推理超图，它是一个知识包管理器。**

这个认知来自对 Cargo/Julia Pkg 的系统类比（详见 [theoretical_foundations.md](theoretical_foundations.md) §7）。两者共享 Horn clause 逻辑骨架，但 Gaia 用概率传播替代 SAT 求解，用 belief 竞争替代编译错误。

### 1.1 七个关键 Insight

| # | Insight | 来源 | 核心含义 |
|---|---------|------|---------|
| 1 | **Knowledge Package = 论文** | Cargo 类比 | 论文/理论/教材章节是命名、版本化的子图，类似 crate |
| 2 | **统一环境模型** | Julia/uv 类比 | 工作区、分支、思想实验都是 base + overlay，统一抽象 |
| 3 | **不需要 SAT** | 节点不可变性分析 | 节点 content-addressed，引用永不断，BP 即是冲突解析器 |
| 4 | **双层 Horn Clause** | 逻辑基础分析 | Package 层（可复用 Cargo 拓扑）+ Edge 层（BP，Gaia 独有） |
| 5 | **Server = Registry** | Cargo/crates.io 类比 | 服务器是包注册中心，本地实例完整可独立运行 |
| 6 | **Question = Context of Discovery** | 科学哲学分析 | 推理链的外部动机，认知索引，搜索桥梁 |
| 7 | **Repo 拆分** | Cargo/crates.io 分离 | gaia-core（共享）/ gaia-server（registry）/ gaia-cli（客户端） |

### 1.2 Phase 1 保留的核心

| 组件 | Phase 1 设计 | Phase 2 变化 |
|------|-------------|-------------|
| Node/HyperEdge 基本结构 | ✓ 保留 | 新增字段（version, content_hash, question 等） |
| Commit 工作流 | submit → review → merge | 保留，扩展为包内操作 |
| 三路搜索 | vector + BM25 + topology | 保留，新增 question 层 |
| 局部 BP | 3-hop subgraph | 保留，新增环境范围 BP |
| LanceDB + Neo4j | 双存储 | 保留，新增 package/environment 表 |

---

## 2. 核心概念

Phase 2 引入四个新的一等概念：

### 2.1 Knowledge Package

**一篇论文就是一个包。** 更准确地说：任何有明确边界的知识贡献（论文、理论体系、教材章节、实验报告）都是一个 Knowledge Package。

```
Knowledge Package = {
    名字 + 版本 (semver)
    一组节点 (命题)
    一组超边 (推理链)
    导出声明 (公开 API)
    依赖列表 (引用了哪些其他包的节点)
}
```

类比 Cargo crate，但包的内部是推理超图而非源代码。

### 2.2 Environment

**一切都是环境。** 本地工作区、知识分支、思想实验在架构上没有区别——都是 base snapshot + sparse overlay。

```
Environment = {
    base: BeliefSnapshot    # 不可变的基础状态
    overlay: {              # 稀疏增量
        added_nodes: [...]
        added_edges: [...]
        modified_beliefs: {node_id: belief}
    }
}
```

没有 `env_type` 或 `lifecycle` 字段——工作区、分支、思想实验在数据模型上完全相同。所谓"workspace 持久、experiment 随时丢弃"只是用户的使用习惯，不是系统的结构属性。如果需要打标签，放 `metadata` 里。

### 2.3 BeliefSnapshot

**环境的冻结状态。** 类似 Git commit / Cargo.lock，记录某一时刻所有节点的 belief 值。不可变。

```
BeliefSnapshot = {
    snapshot_id: str
    beliefs: {node_id: float}  # 全量或稀疏
    timestamp: datetime
    parent: snapshot_id | None  # 链式历史
}
```

### 2.4 Question (Context of Discovery)

**推理链的外部动机。** 记录"为什么要做这个推理"，是搜索的认知索引。

```
HyperEdge.question = "Python CPU 密集任务怎么加速？"
HyperEdge.question_source = "user" | "extracted" | "generated"
```

逻辑上冗余（premises→conclusion 已自足），认知上不冗余（bridging 提问者词汇和答案术语的鸿沟）。

---

## 3. 架构总览

### 3.1 层次结构

```
┌─────────────────────────────────────────────────────────────┐
│  CLI (gaia-cli)                                              │
│  gaia init / add / submit / publish / propagate / tree       │
├─────────────────────────────────────────────────────────────┤
│  Gateway API (gaia-server)                                   │
│  /packages  /environments  /commits  /nodes  /search         │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Package  │ │ Commit   │ │ Search   │ │ Inference     │  │
│  │ Manager  │ │ Engine   │ │ Engine   │ │ Engine        │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────────────────┐ ┌──────────────────────────────┐  │
│  │ Environment Manager  │ │ Text Structuring Service     │  │
│  └──────────────────────┘ └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Core Layer (gaia-core)                                      │
│  models / storage / bp_algorithm / serialization             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 新增 vs 修改 vs 不变

| 组件 | 状态 | 说明 |
|------|------|------|
| **Package Manager** | 新增 | 包的 CRUD、版本管理、依赖追踪、发布 |
| **Environment Manager** | 新增 | 环境的创建、切换、合并、snapshot |
| **Text Structuring Service** | 新增 | 文本 → 超图的自动提取 |
| **Commit Engine** | 修改 | 在包内操作，commit 关联到 package |
| **Search Engine** | 修改 | 新增 question 层召回 + 包范围搜索 |
| **Inference Engine** | 修改 | 新增环境范围 BP + 跨包传播 |
| **Gateway / API** | 修改 | 新增 package/environment 端点 |
| **Storage Layer** | 修改 | 新增 package/environment/snapshot 表 |
| **Core Models** | 修改 | Node/HyperEdge 新增字段 |

---

## 4. 数据模型

### 4.1 Node（修改）

```python
class Node(BaseModel):
    # === Phase 1 保留 ===
    id: int
    type: str = "paper-extract"
    subtype: str | None = None
    title: str | None = None
    content: str | dict | list
    keywords: list[str] = []
    prior: float = 1.0
    belief: float | None = None
    status: Literal["active", "deleted"] = "active"
    metadata: dict = {}
    extra: dict = {}
    created_at: str | None = None

    # === Phase 2 新增 ===
    version: int = 1                    # 单调递增版本号
    content_hash: str | None = None     # SHA256(content)，content-addressed
    package_id: str | None = None       # 所属 Knowledge Package
```

**设计决策**：
- `version` 是简单的整数递增，不是 semver（semver 在 package 层面使用）
- `content_hash` 实现节点不可变性——内容变了就是新版本，hash 变了
- `package_id` 是可选的——Phase 1 的存量节点没有 package 归属

### 4.2 HyperEdge（修改）

```python
class HyperEdge(BaseModel):
    # === Phase 1 保留 ===
    id: int
    type: str = "paper-extract"
    subtype: str | None = None
    tail: list[int] = []
    head: list[int] = []
    probability: float | None = None
    verified: bool = False
    reasoning: list[str] = []
    metadata: dict = {}
    extra: dict = {}
    created_at: str | None = None

    # === Phase 2 新增 ===
    version: int = 1
    content_hash: str | None = None
    package_id: str | None = None
    question: str | None = None                                    # Context of discovery
    question_source: Literal["user", "extracted", "generated"] | None = None
    tail_pins: dict[int, int] | None = None   # {node_id: version} 创建时的依赖版本
    head_pins: dict[int, int] | None = None
    stale: bool = False                        # 依赖节点已更新，推理可能过时
```

**设计决策**：
- `tail_pins` / `head_pins` 记录边创建时引用的节点版本，用于 staleness 检测
- `stale` 是被动标记——当被引用节点更新时，系统标记引用它的边为 stale
- `question` 是可选的，不强制所有边都有

### 4.3 KnowledgePackage（新增）

```python
class KnowledgePackage(BaseModel):
    """一个知识包 = 一篇论文 / 一个理论 / 一个教材章节"""
    name: str                           # 如 "bednorz-mueller-1986"
    version: str                        # semver: "1.0.0"
    description: str | None = None
    authors: list[str] = []
    license: str | None = None

    # 内容
    node_ids: list[int] = []            # 包内所有节点
    edge_ids: list[int] = []            # 包内所有超边
    exports: list[int] = []             # 对外导出的节点 ID（公开 API）

    # 依赖（软依赖，不需要 SAT 解析）
    dependencies: dict[str, str] = {}   # {"bcs-theory": ">=2.0", ...}

    # 元数据
    source: str | None = None           # DOI, URL, etc.
    tags: list[str] = []
    created_at: str | None = None
    published_at: str | None = None     # 发布到 registry 的时间
    status: Literal["draft", "published", "retracted"] = "draft"
```

**设计决策**：
- `exports` 是包的公开接口——其他包只能引用 exports 中的节点
- `dependencies` 是声明式的版本范围，但**不需要 SAT 解析**：节点不可变，引用永不断，多版本天然共存
- `status` 区分草稿、已发布、已撤回

### 4.4 Environment（新增）

```python
class Environment(BaseModel):
    """统一的环境抽象——没有类型区分，一切都是环境"""
    env_id: str
    name: str
    base_snapshot_id: str | None = None       # 基础状态
    parent_env_id: str | None = None          # 从哪个环境 fork 的

    # 稀疏 overlay（只存与 base 不同的部分）
    added_nodes: list[int] = []
    added_edges: list[int] = []
    removed_edges: list[int] = []             # "假设这条推理不存在"
    belief_overrides: dict[int, float] = {}   # {node_id: override_belief}

    # 元数据
    metadata: dict = {}                        # 用户自定义标签（如用途描述）
    created_at: str | None = None
    status: Literal["active", "merged", "archived"] = "active"
```

**设计决策**：
- **没有 `env_type`**——"工作区/分支/实验"只是用户的使用习惯，不是系统结构。统一环境模型意味着数据模型中不区分。如需标记用途，放 `metadata`。
- `removed_edges` 支持"假设这条推理不成立"的场景
- `belief_overrides` 支持"假设这个结论的 belief 是 0.3"的场景
- 合并后状态变为 `merged`，不再需要后变为 `archived`

### 4.5 BeliefSnapshot（新增）

```python
class BeliefSnapshot(BaseModel):
    """不可变的 belief 状态快照，类似 Git commit / Cargo.lock"""
    snapshot_id: str
    env_id: str                              # 哪个环境产生的
    beliefs: dict[int, float]                # {node_id: belief}
    edge_probabilities: dict[int, float]     # {edge_id: probability}
    parent_id: str | None = None             # 前一个 snapshot（链式历史）
    created_at: str
    message: str | None = None               # 描述这个快照的目的
```

### 4.6 实体关系图

```
KnowledgePackage ───contains──→ Node
       │                         │
       │                         │ tail/head
       │                         ▼
       ├───contains──→ HyperEdge
       │                    │
       │                    │ question
       │                    ▼
       │               (question 字段)
       │
       ├───depends_on──→ KnowledgePackage
       │
       └───published_in──→ Registry

Environment ───base──→ BeliefSnapshot
    │
    └───overlay──→ {added_nodes, added_edges, belief_overrides}

BeliefSnapshot ───parent──→ BeliefSnapshot  (链式历史)
```

### 4.7 Commit/Operation 扩展

```python
class AddEdgeOp(BaseModel):
    op: Literal["add_edge"] = "add_edge"
    tail: list[NewNode | NodeRef]
    head: list[NewNode | NodeRef]
    reasoning: list[str] = []
    probability: float | None = None
    question: str | None = None          # Phase 2 新增

class Commit(BaseModel):
    # Phase 1 字段保留
    commit_id: str
    status: Literal["pending_review", "reviewed", "rejected", "merged"]
    message: str | None = None
    operations: list[AddEdgeOp | ModifyNodeOp | ModifyEdgeOp]
    # ...

    # Phase 2 新增
    package_id: str | None = None        # 目标包（可选，兼容 Phase 1 无包 commit）
    env_id: str | None = None            # 目标环境（默认为当前工作区）
```

---

## 5. 存储层

### 5.1 LanceDB（扩展）

Phase 1 LanceDB 存 nodes 表。Phase 2 新增：

| 表 | 内容 | 索引 |
|---|------|------|
| `nodes` | Node 全量数据（Phase 1 已有） | BM25 on content, vector on embedding |
| `hyperedges` | HyperEdge 全量数据 | BM25 on reasoning + question |
| `packages` | KnowledgePackage 元数据 | BM25 on name + description |
| `environments` | Environment 定义 | — |
| `snapshots` | BeliefSnapshot（可能较大） | 按 env_id 分区 |
| `commits` | Commit 记录（Phase 1 已有） | 按 status 过滤 |

**Question 搜索**：`hyperedges` 表的 BM25 索引新增 `question` 字段，实现 question 层召回。

**LanceDB 版本化**：LanceDB 原生支持数据版本化（基于 Lance 格式的 fragment append）。可以直接利用这个能力来存储 BeliefSnapshot 的增量。

### 5.2 Neo4j（扩展）

Phase 1 Neo4j 存 `:Proposition` 和 `:HyperEdge` 节点，通过 `:TAIL` / `:HEAD` 关系连接。Phase 2 新增：

```cypher
// 包归属关系
(:Proposition)-[:BELONGS_TO]->(:Package)
(:HyperEdge)-[:BELONGS_TO]->(:Package)

// 包间依赖关系（从 edge 层自动派生）
(:Package)-[:DEPENDS_ON {version_range: ">=1.0"}]->(:Package)

// 环境拓扑（可选——环境主要在 LanceDB 管理）
(:Environment)-[:BASED_ON]->(:Snapshot)
```

**拓扑查询增强**：包级拓扑（"这个包依赖了哪些包"）+ 节点级拓扑（Phase 1 已有）。

### 5.3 Vector Store（不变）

向量存储的逻辑不变。embedding 仍然是节点内容的 dense 表示。Phase 2 可以考虑为 question 字段也生成 embedding，但这是优化，不是架构变更。

### 5.4 Package Registry Index

Server 模式下新增 registry 索引：

```
registry/
  index/
    ba/
      bcs-theory               # JSON: 版本列表 + 元数据
    be/
      bednorz-mueller-1986     # JSON: 版本列表 + 元数据
  packages/
    bcs-theory/
      2.1.0.tar.gz             # 打包的 nodes.json + edges.json + Gaia.toml
```

借鉴 Cargo registry 的稀疏索引协议。本地模式不需要这个——包直接在本地 LanceDB 中管理。

---

## 6. Commit + Publish 工作流

### 6.1 Phase 1 工作流（保留）

```
submit commit → review (LLM) → merge (triple-write)
```

### 6.2 Phase 2 扩展

```
                    ┌─── 包内工作 ───┐        ┌─── 发布 ───┐
用户/Agent 编辑 →  submit commit    →  review  →  merge     →  publish
                    (操作在包内)     (LLM 审核)  (写入存储)    (推送到 registry)
                                                     │
                                              question 补全
                                              (如果缺失，LLM 生成，
                                               标记 source="generated")
```

**关键变化**：
- Commit 关联到 `package_id`——操作在包的上下文内进行
- Review 阶段增加 question 检测：如果 AddEdgeOp 没有 question，LLM 自动生成
- Merge 后自动更新包的 `node_ids` / `edge_ids` 列表
- Publish 是新步骤——将包推送到 registry（可选，纯本地使用不需要）

### 6.3 Publish 流程

```python
# gaia publish
1. 验证 Gaia.toml 完整性（name, version, exports）
2. 检查 exports 中的节点是否都存在且 belief > 阈值
3. 打包 nodes.json + edges.json + Gaia.toml
4. 计算 content hash（完整性校验）
5. 推送到 registry（HTTP PUT）
6. Registry 更新索引
```

### 6.4 Staleness 检测

Merge 时自动进行：

```
当 node X 被修改（新版本）时：
  找到所有 tail 或 head 引用了 X 的 edge
  对比 edge.tail_pins[X] 与 X.version
  如果不匹配 → 标记 edge.stale = True
  通知用户 "gaia outdated" 有 N 条过时的推理
```

---

## 7. 搜索引擎

### 7.1 Phase 1 召回路径（保留）

| 路径 | 来源 | 权重 |
|------|------|------|
| Vector | embedding 相似度 | 0.5 |
| BM25 | 全文匹配 (node content) | 0.3 |
| Topology | 图遍历 (Neo4j) | 0.2 |

### 7.2 Phase 2 新增：Question 层召回

```
用户查询: "Python 程序太慢怎么办？"

第一层 — Question 匹配（推理链级别）:
  BM25/vector on edge.question
  匹配: edge.question = "Python CPU 密集任务怎么加速？"
  → 返回整条推理链（premises + reasoning + conclusion + belief）

第二层 — Node 匹配（事实级别）:
  Phase 1 三路搜索
  匹配: node.content 包含 "GIL", "multiprocessing"
  → 返回单个节点
```

Question 层权重按来源调整：

```python
question_weight = {
    "user": 1.0,
    "extracted": 0.8,
    "generated": 0.5,
}
```

### 7.3 Phase 2 新增：包范围搜索

```
POST /search/nodes
{
    "query": "超导温度",
    "package": "bednorz-mueller-1986",  // 限定在这个包内搜索
    ...
}
```

### 7.4 Question 聚合

多条边如果有语义相似的 question，自然聚合：

```
question ≈ "铜氧化物能不能高温超导？"
  ├── edge_1: [实验数据A] → [结论] (probability=0.92)
  ├── edge_2: [理论计算B] → [结论] (probability=0.78)
  └── edge_3: [对比实验C] → [结论] (probability=0.85)
```

---

## 8. 推理引擎

### 8.1 Phase 1 能力（保留）

- 局部 BP：以中心节点为起点，取 N-hop 子图，在子图上跑 Loopy BP
- Damping + convergence threshold
- 结果写回 LanceDB

### 8.2 Phase 2：环境范围 BP

```python
async def compute_bp_in_environment(env: Environment):
    """在环境内运行 BP，使用 base + overlay 的合并视图"""
    # 1. 加载 base snapshot 的 beliefs
    base_beliefs = load_snapshot(env.base_snapshot_id)

    # 2. 应用 overlay
    graph = build_graph(base_beliefs)
    graph.add_nodes(env.added_nodes)
    graph.add_edges(env.added_edges)
    graph.remove_edges(env.removed_edges)
    graph.override_beliefs(env.belief_overrides)

    # 3. 在合并视图上跑 BP
    new_beliefs = run_bp(graph)

    # 4. 只存 delta（与 base 不同的部分）
    delta = compute_delta(base_beliefs, new_beliefs)
    return delta
```

**关键**：环境 BP 只存 delta，不复制整个图。这就是 overlay 模型的效率所在。

### 8.3 Phase 2：BP-based Merge

两个环境合并时，不做文本 merge，而是：

```
env_A:  base + overlay_A (adds edges E1, E2)
env_B:  base + overlay_B (adds edges E3, E4, contradicts E1)

merge:
  1. 合并 overlay: added_edges = E1 ∪ E2 ∪ E3 ∪ E4
  2. 在合并后的图上跑 BP
  3. BP 自动处理 E1 和 E4 的矛盾 → belief 竞争
  4. 生成新的 BeliefSnapshot
```

**没有 merge conflict**——概率系统中矛盾不是错误，是特征。BP 自动裁决。

### 8.4 Phase 2：跨包 Belief 传播

当 KP_B 发布新版本（某个结论的 belief 变化了）：

```
1. 找到所有引用了 KP_B 节点的边（通过 tail_pins 中的 package 引用）
2. 标记这些边为 stale
3. 在包含这些边的子图上重跑局部 BP
4. 更新受影响节点的 belief
```

这不是全局 BP——只影响直接引用了变化节点的局部子图。

### 8.5 Seminaïve BP（优化方向）

来自 Datalog 的优化（详见 [theoretical_foundations.md](theoretical_foundations.md) §7.7）：

当前 BP 每轮遍历所有超边。Seminaïve 策略：只传播上一轮 belief 变化超过阈值的节点的消息。在大图上可以显著减少计算量。

---

## 9. API 设计

### 9.1 Phase 1 端点（保留）

```
# Commits
POST   /commits                    # 提交 commit
GET    /commits/{id}               # 查询 commit
POST   /commits/{id}/review        # 审核
POST   /commits/{id}/merge         # 合并

# Read
GET    /nodes/{id}                 # 读取节点
GET    /hyperedges/{id}            # 读取超边
GET    /nodes/{id}/subgraph        # 读取子图

# Search
POST   /search/nodes               # 搜索节点
POST   /search/hyperedges          # 搜索超边
```

### 9.2 Phase 2 新增端点

```
# Packages
POST   /packages                   # 创建包（gaia init）
GET    /packages/{name}            # 查询包信息
GET    /packages/{name}/versions   # 查询包的所有版本
POST   /packages/{name}/publish    # 发布到 registry（gaia publish）
GET    /packages/{name}/tree       # 依赖树（gaia tree）
GET    /packages/{name}/outdated   # 过时依赖（gaia outdated）

# Environments
POST   /environments               # 创建环境（workspace / branch / experiment）
GET    /environments/{id}          # 查询环境
POST   /environments/{id}/snapshot # 创建 snapshot
POST   /environments/{id}/merge    # 合并环境（BP-based merge）
POST   /environments/{id}/propagate # 在环境内运行 BP

# Snapshots
GET    /snapshots/{id}             # 查询 snapshot
GET    /snapshots/{id}/diff/{other} # 对比两个 snapshot

# Search（扩展）
POST   /search/questions           # Question 层搜索（新增）
POST   /search/packages            # 包级搜索（新增）
```

### 9.3 Agent API（扩展）

```
# Agent Verifiable Memory（详见 agent_verifiable_memory.md）
POST   /verify/dry-run             # 预验证操作
POST   /verify/step                # 逐步验证推理链
GET    /verify/confidence-gate     # 检查 belief 是否达标

# dry-run 扩展：question 去重
POST   /verify/dry-run
{
    "question": "Python CPU 密集任务怎么加速？",  // agent 当前子目标
    "operations": [...]
}
→ 返回: "已有 2 条类似 question 的推理链，belief 分别为 0.82, 0.67"
```

---

## 10. CLI 设计

遵循 Cargo 命令体验（详见 [knowledge_package_system.md](knowledge_package_system.md) §10）。

### 10.1 命令对照

| Cargo | Gaia | 说明 |
|-------|------|------|
| `cargo init` | `gaia init` | 创建新包（生成 Gaia.toml） |
| `cargo add` | `gaia add` | 添加依赖 |
| `cargo build` | `gaia propagate` | 运行 BP |
| `cargo publish` | `gaia publish` | 发布到 registry |
| `cargo update` | `gaia update` | 更新依赖版本 |
| `cargo tree` | `gaia tree` | 查看依赖树 |
| `cargo test` | `gaia experiment` | 运行思想实验 |
| — | `gaia submit` | 提交 commit |
| — | `gaia search` | 搜索知识 |
| — | `gaia status` | 查看当前环境 + 待处理 commit |

### 10.2 典型工作流

```bash
# 创建一个新的知识包
gaia init my-research --author "Zhang San"

# 添加依赖
gaia add bednorz-mueller-1986 ">=1.0"

# 提交推理
gaia submit --question "高温超导的机制是什么？" \
  --tail "node:bednorz-mueller-1986::cuprate-structure" \
  --tail "node:bednorz-mueller-1986::ba-doping" \
  --head "新结论..." \
  --reasoning "步骤1: ..." "步骤2: ..."

# 运行 BP 看 belief 变化
gaia propagate

# 检查依赖是否过时
gaia outdated

# 发布
gaia publish
```

---

## 11. 部署架构

### 11.1 三个 Repo

| Repo | 内容 | 类比 |
|------|------|------|
| **gaia-core** | 共享代码：数据模型、BP 算法、序列化、存储抽象 | Rust 标准库 |
| **gaia-server** | FastAPI registry 服务 + 大规模存储（Neo4j, 分布式 LanceDB） | crates.io |
| **gaia-cli** | 本地 CLI + 轻量存储（SQLite/本地 LanceDB） | cargo |

### 11.2 三种部署模式

```
模式 1: 纯本地（like cargo without crates.io）
  gaia-cli + 本地 LanceDB
  不需要网络，完整功能（除了 publish/从 registry 拉取）

模式 2: 客户端 + 服务器（标准模式）
  gaia-cli ←→ gaia-server
  本地是工作环境（缓存 + overlay），服务器是 registry

模式 3: 纯服务器（API 模式）
  gaia-server 独立运行
  通过 REST API 操作，无 CLI
```

### 11.3 本地与服务器的关系

```
本地 (gaia-cli)                     服务器 (gaia-server)
┌─────────────────┐                ┌─────────────────┐
│ 当前环境         │                │ Registry Index  │
│ (base + overlay) │  ←── pull ──── │ (包的版本列表)  │
│                  │                │                  │
│ 缓存的包         │  ─── push ──→ │ 包存储           │
│ (本地 LanceDB)  │   (publish)    │ (分布式存储)     │
│                  │                │                  │
│ 本地 BP          │                │ 全局 BP          │
└─────────────────┘                └─────────────────┘
```

本地不是服务器的子集——它是一个完整的 Gaia 实例。和 Cargo 一样，你可以完全离线使用。

---

## 12. Phase 1 → Phase 2 迁移

### 12.1 数据模型迁移

| 变更 | 向后兼容？ | 迁移策略 |
|------|-----------|---------|
| Node 新增 version, content_hash, package_id | 是（默认值） | version=1, content_hash=计算, package_id=None |
| HyperEdge 新增 question, tail_pins, stale | 是（默认值） | question=None, tail_pins=None, stale=False |
| KnowledgePackage 新增表 | 是（新表） | 无迁移，直接创建 |
| Environment 新增表 | 是（新表） | 无迁移，直接创建 |
| Commit 新增 package_id, env_id | 是（默认值） | package_id=None, env_id=None |

**所有变更都向后兼容**——Phase 1 的存量数据不需要修改，新字段都有合理的默认值。

### 12.2 API 兼容性

Phase 1 的所有端点保持不变。Phase 2 是纯增量——新增端点，不修改已有端点的行为。

### 12.3 存储兼容性

LanceDB 表结构变更通过 schema evolution 处理（LanceDB/Lance 原生支持 column 添加）。Neo4j 新增关系类型不影响已有数据。

---

## 13. 实施优先级

### 13.1 Phase 2a：数据模型 + 包基础

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| P0 | Node/HyperEdge 新增字段（version, content_hash, question） | 无 |
| P0 | KnowledgePackage 模型 + Gaia.toml 解析 | 无 |
| P0 | Commit 关联 package_id | 无 |
| P1 | LanceDB packages 表 + CRUD | P0 |
| P1 | Question 字段写入/读取 | P0 |
| P1 | `gaia init` / `gaia add` CLI 基础 | P0 |

### 13.2 Phase 2b：环境 + 搜索增强

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| P1 | Environment 模型 + 存储 | P0 |
| P1 | BeliefSnapshot 模型 + 存储 | P0 |
| P1 | Question 层搜索（BM25 on question） | P0 (question 字段) |
| P2 | 环境范围 BP | P1 (environment) |
| P2 | Staleness 检测 | P0 (tail_pins) |
| P2 | `gaia propagate` / `gaia status` CLI | P1 |

### 13.3 Phase 2c：发布 + Registry

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| P2 | Publish 工作流 | P1 (package CRUD) |
| P2 | Registry index protocol | P2 (publish) |
| P2 | `gaia publish` / `gaia update` CLI | P2 (registry) |
| P3 | BP-based merge | P2 (environment BP) |
| P3 | 跨包 belief 传播 | P2 (staleness) |

### 13.4 Phase 2d：高级特性

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| P3 | Agent verifiable memory API | P1 (environment) |
| P3 | Text structuring service | P0 (package) |
| P3 | Verification providers | P0 (edge probability) |
| P4 | Seminaïve BP 优化 | P2 (BP) |
| P4 | Repo 拆分（gaia-core / gaia-server / gaia-cli） | P3 (所有功能稳定后) |
| P4 | Question 向量搜索 | P1 (question BM25 先验证价值) |

### 13.5 原则

**能增量就增量。** 所有变更向后兼容 Phase 1。不做 big bang 重写。先在现有 repo 内实现所有功能，最后再拆分 repo（如果确实需要）。
