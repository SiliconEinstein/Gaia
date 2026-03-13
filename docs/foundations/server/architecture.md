# Gaia Server Architecture

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-13 |
| 状态 | **Draft — 目标架构设计** |
| Supersedes | architecture.md v1.1 (2026-03-10) |
| 关联文档 | [../graph-ir.md](../graph-ir.md), [../bp-on-graph-ir.md](../bp-on-graph-ir.md), [storage-schema.md](storage-schema.md), [../review/publish-pipeline.md](../review/publish-pipeline.md), [../system-overview.md](../system-overview.md) |

> **变更摘要 (v1.1 → v2.0)：** Graph IR 引入后，因子图不再是临时运行时构造物——raw graph 和 local canonical graph 是 package 提交时的 first-class artifact。Server 需要验证、审计、合并这些结构化图。本次修订重新设计了 Storage Layer（新增 FactorNode、CanonicalBinding、GlobalInferenceState）、IngestionService 流程（新增 raw graph 验证 + canonicalization 审计 + global matching）、BPService（从持久化 Graph IR 加载而非动态编译）。

---

## 1. Server 定位

Gaia 是 CLI-first, Server-enhanced。Server 是一个可选的 **registry 和计算后端**。

Server 提供四个增强服务：

| 服务 | 说明 |
|------|------|
| Knowledge integration | 把 packages 合并到全局知识图（Global Canonical Graph） |
| Global search | 跨 package 的 vector + BM25 + topology 搜索 |
| Package verification and review | 验证 raw graph、审计 canonicalization、执行 peer review、global matching |
| Large-scale BP | 在 Global Canonical Graph + GlobalInferenceState 上运行信念传播 |

Server **不修改 package source**——它是 package 的只读消费者。但 server 拥有 global identity assignment（CanonicalBinding）和 GlobalInferenceState，这些是 registry-side 数据。

---

## 2. 总体架构

三层分层架构：Transport → Domain Services → Storage。

```
┌─────────────────────────────────────────────────────┐
│  Transport Layer                                     │
│  ┌──────────────┐  ┌──────────────────┐              │
│  │ HTTP Routes   │  │ Webhook Handler  │              │
│  │ (FastAPI)     │  │ (GitHub events)  │              │
│  └──────┬───────┘  └────────┬─────────┘              │
│         └────────┬──────────┘                        │
│                  ▼                                    │
│         PackageSubmission (统一表示)                   │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Domain Services Layer                               │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │ IngestionService                             │     │
│  │                                              │     │
│  │ submit(pkg) → verify_raw_graph               │     │
│  │             → audit_canonicalization          │     │
│  │             → peer_review                    │     │
│  │             → global_match                   │     │
│  │             → integrate                      │     │
│  │                                              │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                  │
│  │ BPService     │  │ QueryService │                  │
│  │               │  │              │                  │
│  │ run_global()  │  │ search()     │                  │
│  │ run_subgraph()│  │ read()       │                  │
│  │               │  │ subgraph()   │                  │
│  └──────────────┘  └──────────────┘                  │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Storage Layer                                       │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │ StorageManager                            │        │
│  │                                           │        │
│  │ 统一读写接口，封装后端协调                 │        │
│  └──────────────────────────────────────────┘        │
│       │            │            │                     │
│  ┌────▼───┐  ┌─────▼────┐  ┌───▼────────┐           │
│  │ Graph   │  │ Content   │  │ VectorStore│           │
│  │ (Kuzu/  │  │ (LanceDB) │  │ (LanceDB)  │           │
│  │  Neo4j) │  └──────────┘  └────────────┘           │
│  └────────┘                                          │
└─────────────────────────────────────────────────────┘
```

依赖方向严格向下：Transport → Domain → Storage。每层只依赖下一层。

---

## 3. 与 Graph IR 的关系

Graph IR 引入了四个根本性变化，是本次架构修订的驱动力。

### 3.1 因子图从临时变为持久

v1.1 说："因子图不持久存储，每次 BP 运行时从 Knowledge + Chain + ProbabilityRecord 动态构建。"

Graph IR 之后，**raw graph 和 local canonical graph 是 package 的 first-class 提交 artifact**。Server 需要：

- 存储这些 artifact
- 验证 raw graph（re-compile + diff）
- 审计 local canonicalization
- 从 local canonical graph 生成 global canonical graph

### 3.2 三层知识身份

每个知识命题在三个层次上有身份：

| 层 | 生成者 | 身份 | 范围 |
|----|--------|------|------|
| Raw | `gaia build`（确定性） | `raw_node_id`（content hash） | package-local |
| Local Canonical | agent canonicalization skill | `local_canonical_id` | package-local |
| Global Canonical | review engine / registry | `global_canonical_id` | 全局 |

Raw 和 Local Canonical 是 package 提交的一部分。Global Canonical 是 server/registry 分配的。

### 3.3 FactorNode 替代动态因子

v1.1 中 BP 从 Chain + Knowledge 动态编译因子。Graph IR 之后，**FactorNode 是持久化的一等实体**。有四种类型：

| Factor 类型 | 来源 | 语义 |
|-------------|------|------|
| `reasoning` | ChainExpr（一个 chain 对应一个 factor，不是一步一个） | 前提为真 → 结论以 conditional_probability 成立 |
| `instantiation` | schema→ground 实例化 | 确定性蕴含：schema 为真 → instance 为真 |
| `mutex_constraint` | Contradiction 声明 | 惩罚所有矛盾声称同时为真 |
| `equiv_constraint` | Equivalence 声明 | 奖励等价声称一致 |

FactorNode 的关键字段（见 graph-ir.md §4.6）：

- `premises` — 直接依赖的知识节点（创建 BP 边）
- `contexts` — 间接依赖的知识节点（**不**创建 BP 边，影响折入 conditional_probability）
- `conclusion` — 单个知识节点。reasoning/instantiation: 正常接收消息；constraint: **只读门控**（BP 读其 belief，不向其发消息）

### 3.4 概率与结构分离

Graph IR 本身**不携带概率**。概率来自外部：

- 本地推理：local parameterization overlay（作者本地，不提交）
- 全局推理：GlobalInferenceState（registry 管理）

Server 存储需要显式管理 GlobalInferenceState，而不是在 Knowledge/Chain 上内嵌概率。

### 3.5 端到端工作流

从 agent 本地创作到 server 入库的完整数据流：

```
Agent (local)                              Server
─────────────                              ──────

gaia build          → raw_graph.json
agent: self-review  → weak points + priors (不提交)
agent: graph-construction → local_canonical_graph.json
                           + canonicalization_log.json
gaia infer          → local BP preview (不提交)

gaia publish ──────────────────────────────→ 提交四个 artifact:
                                            1. source YAMLs
                                            2. raw_graph.json
                                            3. local_canonical_graph.json
                                            4. canonicalization_log.json
                                                │
                                                ▼
                                     ┌─ 1. 存储 SubmissionArtifact（不可变快照）
                                     │
                                     ├─ 2. GraphVerifier
                                     │     re-compile source → 独立产 raw graph
                                     │     diff against 提交的 raw_graph
                                     │     不匹配 → reject
                                     │
                                     ├─ 3. CanonicalizationAuditor
                                     │     审计每个 LocalCanonicalNode 的分组决策
                                     │     错误合并 → blocking
                                     │     遗漏合并 → advisory
                                     │
                                     ├─ 4. ReviewEngine (peer review)
                                     │     独立评估推理质量
                                     │     不看作者的 self-review 概率
                                     │     给出 probability judgments
                                     │     → PeerReviewReport
                                     │
                                     ├─ 5. Rebuttal cycle (≤5 rounds)
                                     │     blocking findings → 返回 agent
agent: rebuttal ←────────────────────┤     agent 修改或反驳
gaia publish (with rebuttal) ────────→     re-review
                                     │     > 5 rounds → 升级人工
                                     │
                                     ├─ 6. GlobalMatcher
                                     │     对每个 LocalCanonicalNode:
                                     │       embed → 搜索全局图
                                     │       → match_existing | create_new
                                     │     → list[CanonicalBinding]
                                     │
                                     ├─ 7. Integrator
                                     │     a. 写 CanonicalBinding
                                     │     b. 更新/创建 GlobalCanonicalNode
                                     │     c. FactorNode 写入全局图
                                     │        (premises/conclusion 重映射为 global_canonical_id)
                                     │     d. 从 review report 刷新 GlobalInferenceState
                                     │     e. package 标记 merged
                                     │
                                     └─ 8. BPService.schedule_update()
                                           异步在全局图上跑 BP
                                           更新 GlobalInferenceState.node_beliefs
                                           写入 BeliefSnapshot history
```

**概率从哪来？** 结构和概率严格分离。Graph IR 只有结构（哪些节点通过哪些 factor 连接），概率来自两个源：

- 作者本地：local parameterization overlay（preview 用，不提交）
- 全局：GlobalInferenceState（registry 管理，从 peer review 的 probability judgments 初始化，BP 运行后更新 beliefs）

**为什么有两层图拓扑（Chain + Factor）？** Chain 是 authoring-layer 概念（多步叙事），一个 Chain 编译成一个 reasoning FactorNode。保留 Chain 用于 package 结构浏览；Factor 层供 BP 直接消费。

---

## 4. Storage Layer

### 4.1 设计原则

1. StorageManager 是所有存储操作的**唯一门面**
2. 存储模型基于三层概念：Gaia Language（authoring）→ Graph IR（structural）→ Global Graph（registry）
3. 每个后端是特定数据的 source of truth
4. 概率和结构严格分离：Graph IR 只存结构，概率在 GlobalInferenceState
5. Package submission artifact（source + raw graph + local canonical graph + canonicalization log）作为不可变快照存储

### 4.2 数据归属

| 后端 | Source of truth for | 提供的查询能力 |
|------|-------------------|---------------|
| **ContentStore (LanceDB)** | 全量内容：package source、Graph IR artifact、knowledge 内容、chain、factor、CanonicalBinding、GlobalInferenceState、belief/probability history | BM25 搜索、按 ID 读取、BP 批量加载 |
| **GraphStore (Kuzu / Neo4j)** | 图拓扑：Knowledge → Factor → Knowledge 的 bipartite 结构，CanonicalBinding 关系 | 邻居遍历、子图提取、topology search |
| **VectorStore (LanceDB)** | Embedding 向量 | top-k 相似度搜索 |

### 4.3 核心实体变化（相对 v1.1）

#### 不变的实体

Package、Module、Chain、ChainStep、KnowledgeRef、ProbabilityRecord、BeliefSnapshot、Resource、ResourceAttachment — schema 不变，语义不变。Chain 仍是 authoring-layer 概念。

#### 扩展的实体

**Knowledge** — 新增字段以支持 Graph IR knowledge node：

```
Knowledge:
    ... (v1.1 所有字段保持不变)
    kind:            str | None       # question/action 的子类型；equivalence 要求同 root type 同 kind
    parameters:      list[Parameter]  # 空 = ground node，非空 = schema node（∀量化）

Parameter:
    name:            str
    constraint:      str
```

`type` 从 `claim | question | setting | action` 扩展为 `claim | question | setting | action | contradiction | equivalence`。

`is_schema` property：`len(parameters) > 0`。

#### 新增的实体

**FactorNode** — Graph IR 的持久化因子：

```
FactorNode:
    factor_id:       str
    type:            str              # reasoning | instantiation | mutex_constraint | equiv_constraint
    premises:        list[str]        # knowledge node IDs（该图层的 ID 空间）
    contexts:        list[str]        # knowledge node IDs（不创建 BP 边）
    conclusion:      str              # 单个 knowledge node ID
    source_ref:      SourceRef | None
    metadata:        dict | None

SourceRef:
    package:         str
    version:         str
    module:          str
    knowledge_name:  str
```

属性：`is_gate_factor`（mutex_constraint 或 equiv_constraint）；`bp_participant_ids`（gate factor 返回 premises only，非 gate 返回 premises + conclusion）。

**CanonicalBinding** — 本地→全局身份映射（review/registry-side 记录）：

```
CanonicalBinding:
    package:              str
    version:              str
    local_graph_hash:     str
    local_canonical_id:   str
    decision:             str         # match_existing | create_new
    global_canonical_id:  str
    decided_at:           datetime
    decided_by:           str
    reason:               str | None
```

**GlobalCanonicalNode** — 全局去重身份：

```
GlobalCanonicalNode:
    global_canonical_id:  str         # registry-assigned, opaque (如 gcn_<ULID>)
    knowledge_type:       str
    kind:                 str | None
    representative_content: str
    parameters:           list[Parameter]
    member_local_nodes:   list[LocalCanonicalRef]
    provenance:           list[PackageRef]
    metadata:             dict | None
```

**GlobalInferenceState** — registry 管理的全局推理参数：

```
GlobalInferenceState:
    graph_hash:          str
    node_priors:         dict[str, float]        # keyed by global_canonical_id
    factor_parameters:   dict[str, FactorParams] # keyed by factor_id
    node_beliefs:        dict[str, float]        # keyed by global_canonical_id
    updated_at:          datetime
```

**PackageSubmissionArtifact** — 提交快照（不可变）：

```
PackageSubmissionArtifact:
    package_name:        str
    commit_hash:         str
    source_files:        dict[str, str]  # filename → YAML content
    raw_graph:           dict             # raw_graph.json 内容
    local_canonical_graph: dict
    canonicalization_log: list[dict]
    submitted_at:        datetime
```

### 4.4 ContentStore（LanceDB）

| 表 | 存储内容 | 相对 v1.1 |
|---|---|---|
| `packages` | Package 全部字段 | 不变 |
| `modules` | Module 全部字段 | 不变 |
| `knowledge` | Knowledge 全部字段 + embedding | **+kind, +parameters** |
| `chains` | Chain（authoring-layer，含 steps） | 不变 |
| `factors` | FactorNode | **新增** |
| `canonical_bindings` | CanonicalBinding | **新增** |
| `global_canonical_nodes` | GlobalCanonicalNode | **新增** |
| `global_inference_state` | GlobalInferenceState（单行或版本化） | **新增** |
| `submission_artifacts` | PackageSubmissionArtifact（不可变快照） | **新增** |
| `probabilities` | ProbabilityRecord | 不变 |
| `belief_history` | BeliefSnapshot | 不变 |
| `resources` | Resource 元信息 | 不变 |
| `resource_attachments` | ResourceAttachment | 不变 |

### 4.5 GraphStore（图拓扑）

v1.1 的图模型用 Chain 作为中间节点连接 Knowledge。Graph IR 之后，**FactorNode 成为新的 BP-facing 拓扑节点**，与 Chain 并存。

```
节点:
    (:Knowledge  {knowledge_id, version, type, kind, prior, belief})
    (:Factor     {factor_id, type, is_gate})              # 新增
    (:Chain      {chain_id, type})                        # 保持
    (:GlobalCanonicalNode {global_canonical_id, ...})     # 新增

关系 — Authoring layer（Chain）:
    (:Knowledge)-[:PREMISE {step_index}]->(:Chain)
    (:Chain)-[:CONCLUSION {step_index}]->(:Knowledge)

关系 — Graph IR layer（Factor）:
    (:Knowledge)-[:FACTOR_PREMISE]->(:Factor)             # 直接依赖，创建 BP 边
    (:Knowledge)-[:FACTOR_CONTEXT]->(:Factor)             # 间接依赖，不创建 BP 边
    (:Factor)-[:FACTOR_CONCLUSION]->(:Knowledge)          # conclusion

关系 — Global layer:
    (:Knowledge)-[:CANONICAL_BINDING {decision}]->(:GlobalCanonicalNode)

关系 — 组织结构（保持不变）:
    (:Knowledge)-[:BELONGS_TO]->(:Module)
    (:Module)-[:BELONGS_TO]->(:Package)
    (:Module)-[:IMPORTS {strength}]->(:Knowledge)
    (:Resource)-[:ATTACHED_TO {role}]->(:Knowledge|:Chain)
```

**两层图拓扑的设计理由：**

Chain 是 authoring-layer 概念（多步推理，叙事结构）。FactorNode 是 Graph IR 概念（编译后的因子，BP 直接消费）。保留 Chain 层用于 package 结构浏览和搜索。Factor 层用于 BP 和推理审计。两层通过 FactorNode.source_ref 关联——source_ref 指向生成该 factor 的 Chain。

这不是冗余存储——Chain 粒度是按步（step），Factor 粒度是按 ChainExpr（整条 chain 编译为一个 reasoning factor）。一个 Chain 对应一个 reasoning FactorNode，但它们的拓扑结构不同：Chain 有多步 PREMISE/CONCLUSION，Factor 只有 premises→conclusion。

### 4.6 降级模式

| 状态 | 影响 |
|------|------|
| GraphStore 不可用 | 图查询返回空，topology search 跳过，入库只写 Content + Vector |
| VectorStore 不可用 | 向量搜索跳过，入库只写 Content + Graph |
| ContentStore 不可用 | **系统不可用**（core source of truth） |

---

## 5. Domain Services Layer

### 5.1 IngestionService

管理 package 从提交到入库的完整生命周期。

#### 状态机

```
submitted → verifying_raw_graph → raw_verified
                   ↓
                 invalid (raw graph mismatch → blocking)

raw_verified → auditing_canonicalization → canonicalization_audited
                        ↓
                     needs_revision (bad merge → blocking)

canonicalization_audited → peer_reviewing → reviewed
                                ↓
                             needs_revision → (rebuttal cycle, max 5 rounds)
                                ↓
                             rejected

reviewed → global_matching → matched → integrating → merged
                                ↓
                             conflict (identity collision → blocking)
```

外部 API 状态可折叠为：`submitted`、`reviewing`、`integrating`、`merged`、`rejected`。

#### 接口

```python
class IngestionService:
    def __init__(
        self,
        compiler: Compiler,
        graph_verifier: GraphVerifier,
        canonicalization_auditor: CanonicalizationAuditor,
        review_engine: ReviewEngine,
        global_matcher: GlobalMatcher,
        integrator: Integrator,
        storage: StorageManager,
    ):
        ...

    async def submit(self, submission: PackageSubmission) -> SubmissionResult
    async def get_status(self, submission_id: str) -> SubmissionStatus
```

#### 内部组件

| 组件 | 职责 | 输入 → 输出 |
|------|------|------------|
| **Compiler** | re-compile package source（不信任客户端编译） | PackageSource → RawGraph |
| **GraphVerifier** | diff 提交的 raw_graph 与 re-compile 结果 | SubmittedRawGraph + RecompiledRawGraph → VerifyResult |
| **CanonicalizationAuditor** | 审计 local canonical graph 的分组决策 | LocalCanonicalGraph + CanonLog → AuditResult |
| **ReviewEngine** | peer review：推理质量、dependency 标注、probability judgments | Package + LocalCanonicalGraph → PeerReviewReport |
| **GlobalMatcher** | 搜索全局图，为每个 LocalCanonicalNode 决定 match_existing 或 create_new | LocalCanonicalGraph + GlobalGraph → list[CanonicalBinding] |
| **Integrator** | 写入 binding + 更新 GlobalCanonicalNode + 写 factors 到全局图 + 刷新 GlobalInferenceState | MatchResult + ReviewReport → IntegrateResult |

#### 从 v1.1 的变化

| v1.1 组件 | v2.0 | 说明 |
|-----------|------|------|
| Validator | → Compiler + GraphVerifier | 校验拆分为 re-compile + graph diff |
| Compiler | 保持 | 仍然做 deterministic lowering |
| ContextBuilder | 移除 | 外部 context 搜索是 peer review / global matching 的内部步骤 |
| Aligner | → GlobalMatcher | 从 "开放世界关系发现" 演化为 "全局身份分配" |
| ReviewEngine | 保持（消费方式变化） | 现在消费 Graph IR artifact，不再直接消费 source |
| Integrator | 扩展 | 新增 CanonicalBinding 写入、GlobalInferenceState 刷新 |

#### Integration 数据流

Package 提交四个 artifact（graph-ir.md §8.1）：

1. Gaia Lang source
2. Raw Graph IR (raw_graph.json)
3. Local Canonical Graph (local_canonical_graph.json)
4. Canonicalization log

Server-side 完整流程：

```
1. 存储 PackageSubmissionArtifact（不可变快照）

2. GraphVerifier:
   - re-compile package source → 独立产出 raw graph
   - diff against 提交的 raw_graph.json
   - 任何不匹配 → blocking finding, reject

3. CanonicalizationAuditor:
   - 审计每个 LocalCanonicalNode 及其 log entry
   - 错误合并 → blocking
   - 遗漏合并 → advisory

4. ReviewEngine:
   - 独立评估推理质量（不信任作者的 self-review 概率或 local parameterization）
   - 可给出 node_prior_judgments 和 factor_probability_judgments
   → PeerReviewReport

5. Rebuttal cycle (max 5 rounds, per publish-pipeline.md §5.3)

6. GlobalMatcher:
   - 对每个 LocalCanonicalNode: embed + 搜索全局图
   - 决定 match_existing(global_canonical_id) | create_new
   - question/action 还要求 root type 和 kind 匹配
   → list[CanonicalBinding]

7. Integrator:
   a. 写入 CanonicalBinding 记录
   b. 更新/创建 GlobalCanonicalNode（membership + provenance）
   c. 将 FactorNode 写入全局图（premises/conclusion 重映射为 global_canonical_id）
   d. 从 PeerReviewReport 的 probability judgments 刷新 GlobalInferenceState
   e. 标记 package 为 merged

8. BPService.schedule_update()
   → 异步在 Global Canonical Graph + GlobalInferenceState 上运行 BP
```

### 5.2 BPService

Graph IR 之后，BP 不再从 Knowledge + Chain 动态编译因子。它从持久化的 FactorNode + GlobalInferenceState 加载。

```python
class BPService:
    def __init__(self, storage: StorageManager):
        ...

    async def run_global(self) -> BPResult
    async def run_subgraph(self, node_ids: list[str]) -> BPResult
    async def schedule_update(self) -> None
```

BP 执行流程：

```
1. 加载 GlobalInferenceState（node_priors + factor_parameters）
2. 加载全局图的 FactorNode 集合
3. 对每个 FactorNode:
   - premises → BP 边（knowledge→factor 和 factor→knowledge 消息）
   - contexts → 不创建 BP 边
   - conclusion:
     - reasoning/instantiation → 正常 BP 参与者
     - mutex_constraint/equiv_constraint → 只读门控
4. 运行 sum-product message passing（复用 libs/inference/bp.py）
5. 更新 GlobalInferenceState.node_beliefs
6. 写入 BeliefSnapshot history
```

与 v1.1 的关键变化：

| 维度 | v1.1 | v2.0 |
|------|------|------|
| Variable ID | `int` | `global_canonical_id: str`（内部映射到 int） |
| Factor 来源 | 从 Chain + Knowledge 动态编译 | 从持久化 FactorNode 加载 |
| Factor 类型 | deduction, induction, retraction, contradiction | reasoning, instantiation, mutex_constraint, equiv_constraint |
| Factor 粒度 | 一步一个 factor | 一个 ChainExpr 一个 factor |
| 新 factor | — | instantiation（确定性蕴含） |
| 概率来源 | Knowledge.prior + ProbabilityRecord | GlobalInferenceState.node_priors + factor_parameters |
| Gate 机制 | bp.py 的 `gate_var` | FactorNode.is_gate_factor + conclusion 字段 |

### 5.3 QueryService

```python
class QueryService:
    def __init__(self, storage: StorageManager):
        ...

    async def get_knowledge(self, knowledge_id: str, version: int | None = None) -> Knowledge | None
    async def get_factor(self, factor_id: str) -> FactorNode | None
    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None
    async def get_subgraph(self, knowledge_id: str, direction: str,
                           max_nodes: int) -> Subgraph
    async def search(self, text: str, top_k: int) -> list[ScoredKnowledge]
```

`search()` 内部执行三路并行召回（vector + BM25 + topology）+ 归一化 + 加权融合。搜索策略后续细化。

---

## 6. Transport Layer

### 6.1 统一请求表示

```python
@dataclass
class PackageSubmission:
    source: Literal["webhook", "direct"]
    source_files: dict[str, str]        # filename → YAML content
    raw_graph: dict                      # raw_graph.json content
    local_canonical_graph: dict          # local_canonical_graph.json content
    canonicalization_log: list[dict]      # canonicalization_log.json content
    metadata: SubmissionMetadata

@dataclass
class SubmissionMetadata:
    submitter: str
    submitted_at: datetime
    repo_url: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
```

相比 v1.1 的 `PackageRequest`（只有 `package_files`），现在携带四个 artifact。

### 6.2 HTTP Routes

```
# Package submission
POST   /packages                    # direct publish（提交四个 artifact）
GET    /packages/{id}/status        # 查询提交状态

# Entity reads — authoring layer
GET    /knowledge/{id}
GET    /knowledge/{id}/versions
GET    /chains/{module_id}

# Entity reads — Graph IR layer
GET    /factors/{id}                # 新增
GET    /factors?package={id}        # 新增

# Entity reads — Global layer
GET    /global-nodes/{id}           # 新增
GET    /bindings?package={name}&version={ver}  # 新增

# Graph
GET    /knowledge/{id}/subgraph

# Search
POST   /search

# BP
POST   /bp/run
GET    /bp/status

# Webhook
POST   /webhooks/github
```

### 6.3 Webhook Handler

与 v1.1 相同模式。webhook 触发后构造 `PackageSubmission`（包含从 PR 获取的四个 artifact），调用 `IngestionService.submit()`。

### 6.4 Application Bootstrap

```python
def create_dependencies() -> Dependencies:
    storage = StorageManager(config)
    await storage.initialize()

    compiler = Compiler()
    graph_verifier = GraphVerifier(compiler)
    canonicalization_auditor = CanonicalizationAuditor(
        llm_client=create_llm_client()
    )
    review_engine = ReviewEngine(llm_client=create_llm_client())
    global_matcher = GlobalMatcher(
        storage=storage,
        embedding_client=create_embedding_client(),
    )
    integrator = Integrator(storage=storage)

    ingestion = IngestionService(
        compiler, graph_verifier, canonicalization_auditor,
        review_engine, global_matcher, integrator, storage,
    )
    bp = BPService(storage)
    query = QueryService(storage)

    return Dependencies(ingestion, bp, query)
```

---

## 7. StorageManager 接口

```python
class StorageManager:
    """所有存储操作的唯一门面"""

    # ── Package Ingestion（三写 + Graph IR artifact）──
    async def ingest_package(
        self,
        package: Package,
        modules: list[Module],
        knowledge_items: list[Knowledge],
        chains: list[Chain],
        factors: list[FactorNode],
        submission_artifact: PackageSubmissionArtifact,
        embeddings: list[KnowledgeEmbedding] | None = None,
    ) -> None

    # ── Canonical Binding（integration 阶段）──
    async def write_canonical_bindings(self, bindings: list[CanonicalBinding]) -> None
    async def get_bindings_for_package(self, package: str, version: str) -> list[CanonicalBinding]

    # ── Global Canonical Node ──
    async def upsert_global_node(self, node: GlobalCanonicalNode) -> None
    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None

    # ── Global Inference State ──
    async def get_inference_state(self) -> GlobalInferenceState | None
    async def update_inference_state(self, state: GlobalInferenceState) -> None

    # ── Knowledge ──
    async def get_knowledge(self, knowledge_id: str, version: int | None = None) -> Knowledge | None
    async def get_knowledge_versions(self, knowledge_id: str) -> list[Knowledge]

    # ── Factor (Graph IR) ──
    async def list_factors(self) -> list[FactorNode]
    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]

    # ── Package / Module / Chain ──
    async def get_package(self, package_id: str) -> Package | None
    async def get_module(self, module_id: str) -> Module | None
    async def get_chains_by_module(self, module_id: str) -> list[Chain]

    # ── Submission Artifact（不可变快照）──
    async def get_submission_artifact(
        self, package: str, commit_hash: str
    ) -> PackageSubmissionArtifact | None

    # ── Probability / Belief ──
    async def add_probabilities(self, records: list[ProbabilityRecord]) -> None
    async def write_beliefs(self, snapshots: list[BeliefSnapshot]) -> None
    async def get_belief_history(self, knowledge_id: str) -> list[BeliefSnapshot]

    # ── 图查询（委托 GraphStore）──
    async def get_neighbors(self, knowledge_id: str, direction: str,
                            max_hops: int) -> Subgraph
    async def get_subgraph(self, knowledge_id: str, max_knowledge: int) -> Subgraph

    # ── 搜索 ──
    async def search_vector(self, embedding: list[float], top_k: int) -> list[ScoredKnowledge]
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredKnowledge]
    async def search_topology(self, seed_ids: list[str], hops: int) -> list[ScoredKnowledge]

    # ── BP 用 ──
    async def load_global_factor_graph(self) -> tuple[list[FactorNode], GlobalInferenceState]
```

与 v1.1 的关键差异：

- `ingest_package` 增加 `factors` 和 `submission_artifact` 参数
- 新增 CanonicalBinding、GlobalCanonicalNode、GlobalInferenceState 读写
- 新增 `list_factors()` 和 `get_factors_by_package()`
- `load_all_knowledge() + load_all_chains()` 被 `load_global_factor_graph()` 替代

---

## 8. 三写一致性

Package 入库写入顺序：

```
ingest_package(pkg, factors, artifact, ...):
    1. ContentStore.write(artifact, package, modules, knowledge, chains, factors)
       ← source of truth 先落盘，status = 'preparing'
    2. GraphStore.write(knowledge nodes + chain topology + factor topology)
       ← 图拓扑
    3. VectorStore.write(embeddings)
       ← 向量索引
    4. ContentStore.commit_package(package_id, version)
       ← 翻转为 'merged'，数据变为可见

    失败策略：
    - 步骤 2/3 失败 → 数据留在 'preparing' 状态（不可见），安全重试
    - 显式清理需要 delete_package()
```

Integration 阶段的额外写入（在 ingest 完成之后）：

```
integrate(bindings, global_nodes, inference_state):
    1. ContentStore.write_canonical_bindings(bindings)
    2. ContentStore.upsert_global_nodes(global_nodes)
    3. GraphStore.write_global_topology(bindings, factor_remapping)
    4. ContentStore.update_inference_state(inference_state)
```

---

## 9. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Chain 与 FactorNode 共存 | 保留 Chain + 新增 FactorNode | Chain 用于结构浏览和叙事，FactorNode 用于 BP 和推理审计。粒度不同（step vs chain-level） |
| Graph IR artifact 存为不可变快照 | PackageSubmissionArtifact | 支持 re-verify、审计追溯、重现。对应 git commit 的不可变性 |
| CanonicalBinding 是 server-side 记录 | 不属于 package 提交物 | 只有 review/registry 有权分配全局身份 |
| GlobalInferenceState 独立于 Graph IR | 单独的 runtime state | 概率与结构严格分离。Graph IR 是审计 artifact，InferenceState 是运行时参数 |
| GraphStore 有两层拓扑 | Chain PREMISE/CONCLUSION + Factor FACTOR_PREMISE/CONCLUSION/CONTEXT | 向后兼容 authoring-layer 查询；Factor 层供 BP 使用 |
| ContextBuilder 移除 | 搜索是 review/matching 的内部步骤 | 对齐 publish-pipeline.md：`gaia build context` 已被移除 |
| Aligner → GlobalMatcher | 从"关系发现"变为"身份分配" | Graph IR 的 canonicalization 分三层；server 只做第三层 |
| 动态因子编译废弃 | `load_global_factor_graph()` 替代 `load_all_knowledge() + load_all_chains()` | BP 从持久化 FactorNode 加载 |

---

## 10. 与其他文档的关系

| 文档 | 关系 |
|------|------|
| [graph-ir.md](../graph-ir.md) | 定义 Graph IR 结构。本文档定义 server 如何存储和处理这些结构 |
| [bp-on-graph-ir.md](../bp-on-graph-ir.md) | 定义 BP 语义。本文档的 BPService 实现这些语义 |
| [storage-schema.md](storage-schema.md) | 需要同步更新。本文档 §4 supersedes 部分内容 |
| [publish-pipeline.md](../review/publish-pipeline.md) | 定义 publish cycle。本文档的 IngestionService 实现该 cycle |
| [domain-model.md](../domain-model.md) | closure kind 扩展为包含 contradiction / equivalence |

---

## 11. 未覆盖的内容

以下需要后续独立设计：

1. **storage-schema.md 同步更新** — 将 §4 的实体变化反映到详细 LanceDB 表定义和 Kuzu 建表语句
2. **GlobalMatcher 算法** — embedding 搜索策略、match_existing vs create_new 的判定阈值
3. **CanonicalizationAuditor 策略** — 如何评估 local canonicalization 质量
4. **GraphVerifier 的 build 版本兼容** — 不同 `gaia build` 版本的 raw graph schema 差异处理
5. **GlobalInferenceState 刷新策略** — 如何从 review report 的 probability judgments 生成/更新全局参数
6. **GPU BP 架构** — large-scale BP 的分布式执行
7. **搜索策略详细设计** — 三路召回的权重和策略
