# Gaia Server Storage Schema

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-13 |
| 状态 | Draft |
| Supersedes | storage-schema.md v1.1 (2026-03-10) |
| 关联文档 | [architecture.md](architecture.md) — Server 整体架构 v2.0, [../graph-ir.md](../graph-ir.md) — Graph IR 规范, [../bp-on-graph-ir.md](../bp-on-graph-ir.md) — BP on Graph IR, [../review/publish-pipeline.md](../review/publish-pipeline.md) — Publish Pipeline |

> **变更摘要 (v1.1 → v2.0)：** Graph IR 使因子图成为持久化的 first-class artifact。本次修订新增 5 个实体（FactorNode、CanonicalBinding、GlobalCanonicalNode、GlobalInferenceState、PackageSubmissionArtifact），扩展 Knowledge（+kind, +parameters, +contradiction/equivalence），重写图拓扑设计（新增 Factor 层），更新所有后端分工和查询模式。

---

## 1. 设计原则

- 存储模型基于三层概念：**Gaia Language**（authoring）→ **Graph IR**（structural）→ **Global Graph**（registry）
- **StorageManager 是唯一门面**——domain services 不直接接触具体后端
- 每个后端是特定数据的 **source of truth**，不是彼此的副本
- **FactorNode 持久存储**——raw graph 和 local canonical graph 是 package 提交的 first-class artifact，不再动态构建
- **概率与结构分离**——Graph IR 只存结构，概率在 GlobalInferenceState（registry 管理）
- Knowledge 有显式版本号，同 id 同 version 只存一份
- Belief 和 probability 保留完整演化历史
- Package submission artifact（source + raw graph + local canonical graph + canonicalization log）作为不可变快照存储
- 多模态资源文件存 TOS（对象存储），数据库只存元信息和路径

---

## 2. 核心实体

### 2.1 Package

一个可复用的知识容器，对应一个 git repo。

```
Package:
    package_id:    str           # 全局唯一
    name:          str
    version:       str           # semver
    description:   str | None
    modules:       list[str]     # module_id 有序列表（叙事顺序）
    exports:       list[str]     # 对外导出的 knowledge_id
    submitter:     str
    submitted_at:  datetime
    status:        str           # submitted | merged | rejected
```

### 2.2 Module

一个内聚的知识单元，分组 knowledge 并通过 chain 串联推理。

```
Module:
    module_id:     str           # package_id + module_name
    package_id:    str
    name:          str
    role:          str           # reasoning | setting | motivation | follow_up_question | other
    imports:       list[ImportRef]
    chain_ids:     list[str]     # 有序
    export_ids:    list[str]     # 此 module 导出的 knowledge_id

ImportRef:
    knowledge_id:  str
    version:       int
    strength:      str           # strong | weak
```

### 2.3 Knowledge

全局可复用的知识对象。带显式版本号，支持用户多次提交修订。

```
Knowledge:
    knowledge_id:  str           # 全局唯一
    version:       int           # 显式版本号，同 id 同 version 只存一份
    type:          str           # claim | question | setting | action | contradiction | equivalence
    kind:          str | None    # root-type-specific kind label（question/action 的子类型）
    content:       str
    parameters:    list[Parameter]  # 空 = ground node，非空 = schema node（∀量化）
    prior:         float         # ∈ (0, 1)，setting 允许 1.0
    keywords:      list[str]
    source_package_id: str       # 创建此版本的 package
    source_module_id:  str
    created_at:    datetime
    embedding:     list[float] | None

Parameter:
    name:          str           # 占位符名称，如 "A", "X"
    constraint:    str           # 约束描述
```

**相对 v1.1 的变化：**

| 变化 | 说明 |
|------|------|
| `type` 扩展 | 新增 `contradiction`, `equivalence`（Relation 作为 knowledge root type） |
| `kind` 新增 | question/action 的子类型；equivalence 要求同 root type 同 kind |
| `parameters` 新增 | 空 = ground node，非空 = schema node。支持 ∀ 量化 |
| `is_schema` 派生属性 | `len(parameters) > 0` |

**版本规则：** 同 v1.1——`(knowledge_id, version)` 唯一，新版本由新 package 提交时创建，旧版本不可变。

### 2.4 Chain

Module 内的推理链，连接 knowledge 之间的推理关系。**Authoring-layer 概念**，用于 package 结构浏览和叙事。

```
Chain:
    chain_id:      str           # module_id + chain_name
    module_id:     str
    package_id:    str
    type:          str           # deduction | induction | abstraction | contradiction | retraction
    steps:         list[ChainStep]

ChainStep:
    step_index:    int           # 步骤序号（从 0 开始）
    premises:      list[KnowledgeRef]
    reasoning:     str           # inference 文本
    conclusion:    KnowledgeRef

KnowledgeRef:
    knowledge_id:  str
    version:       int
```

**与 FactorNode 的关系：** 一个 Chain 编译成一个 reasoning FactorNode（不是一步一个）。Chain 保留多步叙事结构，供浏览使用；Factor 供 BP 消费。两者通过 `FactorNode.source_ref` 关联。

### 2.5 FactorNode

**Graph IR 的持久化因子**（v2.0 新增）。因子定义知识节点间的约束关系，不携带 belief。

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

**四种 factor 类型：**

| Factor 类型 | 生成来源 | premises | contexts | conclusion | 语义 |
|-------------|---------|----------|----------|------------|------|
| `reasoning` | ChainExpr | direct-dep knowledge | indirect-dep knowledge | 推理结论 | 前提真 → 结论以 conditional_probability 成立 |
| `instantiation` | schema→ground 实例化 | `[schema node]` | `[]` | instance node | 确定性蕴含 |
| `mutex_constraint` | Contradiction 声明 | 矛盾 claim nodes | `[]` | Contradiction node（只读门控） | 惩罚矛盾声称同时为真 |
| `equiv_constraint` | Equivalence 声明 | 等价 claim nodes | `[]` | Equivalence node（只读门控） | 奖励等价声称一致 |

**字段语义：**
- `premises` — 直接依赖，创建 BP 边
- `contexts` — 间接依赖，**不**创建 BP 边，影响折入 conditional_probability
- `conclusion` — reasoning/instantiation：正常接收 BP 消息；constraint：**只读门控**（BP 读其 belief，不向其发消息）

**派生属性：**
- `is_gate_factor` = type ∈ {mutex_constraint, equiv_constraint}
- `bp_participant_ids` = gate factor 返回 premises only，非 gate 返回 premises + [conclusion]

### 2.6 CanonicalBinding

**本地→全局身份映射**（v2.0 新增）。Server/registry-side 记录，不属于 package 提交物。

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

**约束：**
- `(package, version, local_graph_hash, local_canonical_id)` 唯一
- 一个 binding 指向恰好一个 `global_canonical_id`
- 多个 package 的 local node 可绑定到同一 global node
- question/action 的 binding 要求 root type + kind 同时匹配

### 2.7 GlobalCanonicalNode

**全局去重身份**（v2.0 新增）。Registry 分配的全局知识标识。

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

LocalCanonicalRef:
    package:             str
    version:             str
    local_canonical_id:  str

PackageRef:
    package:             str
    version:             str
```

### 2.8 GlobalInferenceState

**Registry 管理的全局推理状态**（v2.0 新增）。概率与结构严格分离——Graph IR 只存结构，此实体存运行时参数。

```
GlobalInferenceState:
    graph_hash:          str
    node_priors:         dict[str, float]        # keyed by global_canonical_id
    factor_parameters:   dict[str, FactorParams] # keyed by factor_id
    node_beliefs:        dict[str, float]        # keyed by global_canonical_id
    updated_at:          datetime

FactorParams:
    conditional_probability: float
```

`GlobalInferenceState` 不是 package artifact。由 registry 从 peer review report 的 probability judgments 初始化，BP 运行后更新 `node_beliefs`。

### 2.9 PackageSubmissionArtifact

**提交快照**（v2.0 新增）。不可变，支持 re-verify 和审计追溯。

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

### 2.10 ProbabilityRecord

推理步骤的可靠性，按 `(chain_id, step_index)` 粒度存储。

> **注意：** 这是 authoring-layer 的概率记录（对应 Chain 步骤）。全局 BP 使用 GlobalInferenceState 中的 factor_parameters，不直接使用 ProbabilityRecord。ProbabilityRecord 的主要用途是记录 review 过程中按步骤的 probability 评估历史。

```
ProbabilityRecord:
    chain_id:      str
    step_index:    int
    value:         float         # ∈ (0, 1]
    source:        str           # author | llm_review | lean_verify | code_verify
    source_detail: str | None
    recorded_at:   datetime
```

### 2.11 BeliefSnapshot

BP 计算结果的历史记录。

```
BeliefSnapshot:
    knowledge_id:  str           # global_canonical_id
    belief:        float         # ∈ [0, 1]
    bp_run_id:     str
    computed_at:   datetime
```

**相对 v1.1 的变化：** `knowledge_id` 现在是 `global_canonical_id`（而非 package-local knowledge_id + version）。BP 在 Global Canonical Graph 上运行。

### 2.12 Resource

附加资源的元信息。同 v1.1，不变。

```
Resource:
    resource_id:       str
    type:              str           # image | code | notebook | dataset | checkpoint | tool_output | other
    format:            str
    title:             str | None
    description:       str | None
    storage_backend:   str           # tos
    storage_path:      str
    size_bytes:        int | None
    checksum:          str | None    # sha256
    metadata:          dict
    created_at:        datetime
    source_package_id: str
```

### 2.13 ResourceAttachment

Resource 和实体的多对多关联。同 v1.1，不变。

```
ResourceAttachment:
    resource_id:   str
    target_type:   str           # knowledge | chain | chain_step | module | package
    target_id:     str
    role:          str           # evidence | visualization | implementation | reproduction | supplement
    description:   str | None
```

---

## 3. 各后端存储分工

### 3.1 LanceDB — 全量内容，source of truth

LanceDB 是核心 source of truth，存储所有实体的完整内容。

| 表 | 存储内容 | 主要查询 | 相对 v1.1 |
|---|---|---|---|
| `packages` | Package 全部字段 | 按 name/status 查询 | 不变 |
| `modules` | Module 全部字段（含 imports） | 按 package_id 查询 | 不变 |
| `knowledge` | Knowledge 全部字段 + embedding | BM25 搜索、向量搜索、按 (id, version) 精确查 | **+kind, +parameters** |
| `chains` | Chain 全部字段（含 steps） | 按 module_id/package_id 查询 | 不变 |
| `factors` | FactorNode 全部字段 | 按 package 查、按 type 查、BP 批量加载 | **新增** |
| `canonical_bindings` | CanonicalBinding | 按 (package, version) 查、按 global_canonical_id 反查 | **新增** |
| `global_canonical_nodes` | GlobalCanonicalNode | 按 global_canonical_id 精确查、BM25 搜索 representative_content | **新增** |
| `global_inference_state` | GlobalInferenceState（单行或版本化） | 加载当前状态 | **新增** |
| `submission_artifacts` | PackageSubmissionArtifact（不可变快照） | 按 (package_name, commit_hash) 查 | **新增** |
| `probabilities` | ProbabilityRecord | 按 (chain_id, step_index) 查询历史 | 不变 |
| `belief_history` | BeliefSnapshot | 按 knowledge_id (global_canonical_id) 查询演化 | **key 变为 global_canonical_id** |
| `resources` | Resource 元信息 | 按 type/package_id 查询 | 不变 |
| `resource_attachments` | ResourceAttachment | 按 target_type + target_id 查询 | 不变 |

**Knowledge 表 PyArrow schema 变化：**

```
v1.1 columns:
    knowledge_id, version, type, content, prior, keywords,
    source_package_id, source_module_id, created_at, embedding

v2.0 新增 columns:
    kind:        pa.utf8()        # nullable
    parameters:  pa.utf8()        # JSON-serialized list[Parameter]
```

**新增 factors 表 PyArrow schema：**

```
factors:
    factor_id:    pa.utf8()
    type:         pa.utf8()       # reasoning | instantiation | mutex_constraint | equiv_constraint
    premises:     pa.utf8()       # JSON-serialized list[str]
    contexts:     pa.utf8()       # JSON-serialized list[str]
    conclusion:   pa.utf8()       # single knowledge node ID
    source_ref:   pa.utf8()       # JSON-serialized SourceRef | null
    metadata:     pa.utf8()       # JSON-serialized dict | null
    package_id:   pa.utf8()       # 冗余，方便按 package 查询
```

### 3.2 GraphStore — 图拓扑，两层并存

GraphStore 存储两层图拓扑：Authoring layer（Chain）和 Graph IR layer（Factor）。

```
节点:
    (:Knowledge  {knowledge_id, version, type, kind})
    (:Factor     {factor_id, type, is_gate})              # v2.0 新增
    (:Chain      {chain_id, type})                        # 保持
    (:GlobalCanonicalNode {global_canonical_id,           # v2.0 新增
                           knowledge_type, kind,
                           representative_content})
    (:Module   {module_id, name, role})
    (:Package  {package_id, name, version})
    (:Resource {resource_id, type, format})

关系 — Authoring layer（Chain，保持不变）:
    (:Knowledge)-[:PREMISE {step_index}]->(:Chain)
    (:Chain)-[:CONCLUSION {step_index}]->(:Knowledge)

关系 — Graph IR layer（Factor，v2.0 新增）:
    (:Knowledge)-[:FACTOR_PREMISE]->(:Factor)             # 直接依赖，创建 BP 边
    (:Knowledge)-[:FACTOR_CONTEXT]->(:Factor)             # 间接依赖，不创建 BP 边
    (:Factor)-[:FACTOR_CONCLUSION]->(:Knowledge)          # conclusion

关系 — Global layer（v2.0 新增）:
    (:Knowledge)-[:CANONICAL_BINDING {decision, package, version}]->(:GlobalCanonicalNode)

关系 — 组织结构（保持不变）:
    (:Knowledge)-[:BELONGS_TO]->(:Module)
    (:Chain)-[:BELONGS_TO]->(:Module)
    (:Module)-[:BELONGS_TO]->(:Package)
    (:Module)-[:IMPORTS {strength}]->(:Knowledge)
    (:Resource)-[:ATTACHED_TO {role}]->(:Knowledge|:Chain)
```

**两层拓扑的设计理由：**

Chain 是 authoring-layer 概念（多步推理叙事），Factor 是 Graph IR 概念（编译后因子，BP 直接消费）。粒度不同：Chain 按步有多个 PREMISE/CONCLUSION 关系，Factor 是整条 chain 编译为一个 reasoning factor，只有 premises→conclusion。通过 `FactorNode.source_ref` 关联。

**v1.1 中 belief/probability 冗余在 Neo4j 节点属性上，v2.0 不再如此**——概率存在 GlobalInferenceState，图拓扑只存结构。

### 3.3 VectorStore — 向量搜索

| 存储 | 内容 |
|---|---|
| knowledge 向量 | `(knowledge_id, version, embedding)` |
| global_canonical_node 向量 | `(global_canonical_id, embedding)` — GlobalMatcher 用 |

查询：`search(embedding, top_k) → list[(id, score)]`

**ByteHouse embedding search：** 可作为 VectorStore 的替代后端，延后设计。当前 VectorStore 接口不变，后续可替换实现。

### 3.4 TOS — 对象存储

存储实际的多模态文件。同 v1.1，数据库中 `Resource.storage_path` 指向 TOS 路径。

### 3.5 降级模式

| 状态 | 影响 |
|------|------|
| GraphStore 不可用 | 图查询返回空，topology search 跳过，入库只写 Content + Vector |
| VectorStore 不可用 | 向量搜索跳过，入库只写 Content + Graph |
| TOS 不可用 | 资源文件无法上传/下载，元信息仍可查询 |
| ContentStore (LanceDB) 不可用 | **系统不可用**（core source of truth） |

---

## 4. 查询模式

不同使用场景需要查询不同后端。

### 4.1 Package 结构浏览

用户查看某个 package 的结构和推理链。

```
查询路径: ContentStore (LanceDB)

get_package(package_id) → Package
get_module(module_id) → Module (含 imports, chain_ids)
get_chains_by_module(module_id) → list[Chain] (含 steps)
get_knowledge(knowledge_id, version) → Knowledge
```

Chain 的多步叙事在此场景中保留完整的 step 结构，供用户阅读。

### 4.2 知识搜索

跨 package 搜索知识。三路并行召回 + 归一化 + 加权融合。

```
vector 搜索: VectorStore.search(embedding, top_k)
BM25 搜索:   ContentStore.search_bm25(text, top_k)
topology:    GraphStore.search_topology(seed_ids, hops)

→ 归一化 + 加权(vector=0.5, bm25=0.3, topology=0.2) + top-k
```

搜索对象：Knowledge（最终可能扩展到 GlobalCanonicalNode）。

### 4.3 子图探索

从某个 knowledge 出发探索相关图结构。

```
查询路径: GraphStore

get_subgraph(knowledge_id, max_nodes) → Subgraph
    → 返回相关 Knowledge + Chain + Factor 节点及关系

get_neighbors(knowledge_id, direction, max_hops) → Subgraph
    → 可指定 Authoring layer (Chain) 或 Graph IR layer (Factor) 遍历
```

### 4.4 BP 执行

在 Global Canonical Graph 上运行信念传播。

```
查询路径: ContentStore (批量加载)

load_global_factor_graph() → (list[FactorNode], GlobalInferenceState)
    → FactorNode 的 premises/conclusion 使用 global_canonical_id
    → GlobalInferenceState 提供 node_priors + factor_parameters
    → BP 运行后更新 node_beliefs + 写入 BeliefSnapshot
```

### 4.5 Global Matching

Integration 阶段为 LocalCanonicalNode 分配全局身份。

```
查询路径: VectorStore + ContentStore

1. embed(LocalCanonicalNode.representative_content)
2. VectorStore.search(embedding, top_k) → 候选 GlobalCanonicalNode
3. ContentStore.get_global_node(global_id) → 详细信息
4. 判定 match_existing | create_new
5. ContentStore.write_canonical_bindings(bindings)
6. GraphStore.write_global_topology(bindings, factor_remapping)
```

### 4.6 审计追溯

回溯某个 package 的提交和验证历史。

```
查询路径: ContentStore

get_submission_artifact(package, commit_hash) → PackageSubmissionArtifact
    → 包含 source YAMLs, raw_graph, local_canonical_graph, canonicalization_log
    → 不可变快照，支持 re-verify
get_bindings_for_package(package, version) → list[CanonicalBinding]
```

---

## 5. StorageManager 接口

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

    # ── Resource ──
    async def write_resources(self, resources: list[Resource],
                              attachments: list[ResourceAttachment]) -> None
    async def get_resource(self, resource_id: str) -> Resource | None
    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]

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

**与 v1.1 的关键差异：**

| 变化 | 说明 |
|------|------|
| `ingest_package` 增加参数 | 新增 `factors` 和 `submission_artifact` |
| 新增 CanonicalBinding 读写 | `write_canonical_bindings`, `get_bindings_for_package` |
| 新增 GlobalCanonicalNode 读写 | `upsert_global_node`, `get_global_node` |
| 新增 GlobalInferenceState | `get_inference_state`, `update_inference_state` |
| 新增 Factor 查询 | `list_factors`, `get_factors_by_package` |
| BP 加载方式 | `load_all_knowledge() + load_all_chains()` → `load_global_factor_graph()` |

---

## 6. 各后端 ABC

```python
class ContentStore(ABC):
    """LanceDB — 全量内容与元数据"""

    # 写入 — Authoring layer
    async def write_package(self, package: PackageData) -> None
    async def write_knowledge(self, knowledge_list: list[Knowledge]) -> None
    async def write_chains(self, chains: list[Chain]) -> None
    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None
    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None
    async def write_resources(self, resources: list[Resource],
                              attachments: list[ResourceAttachment]) -> None

    # 写入 — Graph IR layer (v2.0 新增)
    async def write_factors(self, factors: list[FactorNode]) -> None
    async def write_submission_artifact(self, artifact: PackageSubmissionArtifact) -> None

    # 写入 — Global layer (v2.0 新增)
    async def write_canonical_bindings(self, bindings: list[CanonicalBinding]) -> None
    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None
    async def update_inference_state(self, state: GlobalInferenceState) -> None

    # 读取 — Authoring layer
    async def get_knowledge(self, knowledge_id: str, version: int | None) -> Knowledge | None
    async def get_knowledge_versions(self, knowledge_id: str) -> list[Knowledge]
    async def get_package(self, package_id: str) -> Package | None
    async def get_module(self, module_id: str) -> Module | None
    async def get_chains_by_module(self, module_id: str) -> list[Chain]
    async def get_probability_history(self, chain_id: str,
                                      step_index: int | None = None) -> list[ProbabilityRecord]
    async def get_belief_history(self, knowledge_id: str) -> list[BeliefSnapshot]
    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]

    # 读取 — Graph IR layer (v2.0 新增)
    async def list_factors(self) -> list[FactorNode]
    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]
    async def get_submission_artifact(self, package: str, commit_hash: str) -> PackageSubmissionArtifact | None

    # 读取 — Global layer (v2.0 新增)
    async def get_canonical_bindings(self, package: str, version: str) -> list[CanonicalBinding]
    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None
    async def get_inference_state(self) -> GlobalInferenceState | None

    # 搜索
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredKnowledge]

    # BP 批量加载
    async def list_knowledge(self) -> list[Knowledge]
    async def list_chains(self) -> list[Chain]


class GraphStore(ABC):
    """图拓扑 — 两层结构"""

    # 写入 — Authoring layer（保持不变）
    async def write_topology(self, knowledge_list: list[Knowledge], chains: list[Chain]) -> None
    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None

    # 写入 — Graph IR layer (v2.0 新增)
    async def write_factor_topology(self, factors: list[FactorNode]) -> None

    # 写入 — Global layer (v2.0 新增)
    async def write_global_topology(self, bindings: list[CanonicalBinding],
                                     global_nodes: list[GlobalCanonicalNode]) -> None

    # 查询
    async def get_neighbors(self, knowledge_id: str, direction: str,
                            chain_types: list[str] | None, max_hops: int) -> Subgraph
    async def get_subgraph(self, knowledge_id: str, max_knowledge: int) -> Subgraph
    async def search_topology(self, seed_ids: list[str], hops: int) -> list[ScoredKnowledge]


class VectorStore(ABC):
    """向量搜索"""

    async def write_embeddings(self, items: list[KnowledgeEmbedding]) -> None
    async def search(self, embedding: list[float], top_k: int) -> list[ScoredKnowledge]
```

**与 v1.1 的 GraphStore 差异：**
- 移除 `update_beliefs` 和 `update_probability`（概率不再冗余在图节点上）
- 新增 `write_factor_topology`（Factor 层拓扑写入）
- 新增 `write_global_topology`（GlobalCanonicalNode + CANONICAL_BINDING 关系写入）

---

## 7. 写入一致性

### 7.1 Package Ingestion（三写）

```
ingest_package(pkg, factors, artifact, ...):
    1. ContentStore.write(artifact, package, modules, knowledge, chains, factors)
       ← source of truth 先落盘，status = 'preparing'
    2. GraphStore.write(knowledge nodes + chain topology + factor topology)
       ← 两层图拓扑
    3. VectorStore.write(embeddings)
       ← 向量索引
    4. ContentStore.commit_package(package_id, version)
       ← 翻转为 'merged'，数据变为可见

    失败策略：
    - 步骤 2/3 失败 → 数据留在 'preparing' 状态（不可见），安全重试
    - 显式清理需要 delete_package()
```

### 7.2 Integration（在 ingestion 之后）

```
integrate(bindings, global_nodes, inference_state):
    1. ContentStore.write_canonical_bindings(bindings)
    2. ContentStore.upsert_global_nodes(global_nodes)
    3. GraphStore.write_global_topology(bindings, global_nodes)
       ← CANONICAL_BINDING 关系 + GlobalCanonicalNode 节点
    4. ContentStore.update_inference_state(inference_state)
```

### 7.3 BP 结果写入

```
write_bp_results(beliefs, bp_run_id):
    1. ContentStore.update_inference_state(updated_state)
       ← 更新 node_beliefs
    2. ContentStore.write_belief_snapshots(snapshots)
       ← 历史记录
```

---

## 8. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据模型基础 | 三层：Gaia Language → Graph IR → Global Graph | 对齐 Graph IR 架构，每层有明确职责 |
| 因子图 | **持久存储** FactorNode | Graph IR 使 factor 成为 first-class artifact，不再是派生数据 |
| Chain 与 FactorNode 共存 | 两层图拓扑 | Chain 用于叙事浏览（按步），Factor 用于 BP（按 ChainExpr），粒度不同 |
| 概率存储 | 从 Knowledge/Chain 属性分离到 GlobalInferenceState | 概率与结构严格分离，对齐 Graph IR 设计 |
| GraphStore 不存概率 | 移除 belief/probability 节点属性 | 概率集中在 GlobalInferenceState，避免多处同步 |
| Knowledge 版本 | 保持 `(knowledge_id, version)` 唯一 | v1.1 设计合理，无需改变 |
| Knowledge 扩展 | +kind, +parameters, +contradiction/equivalence | 对齐 Graph IR 的 knowledge node 定义 |
| CanonicalBinding 位置 | Server/registry-side 记录，不属于 package 提交 | 全局身份分配是 registry 职责 |
| GlobalInferenceState | 独立实体，不嵌入 Graph IR | 概率是运行时参数，不是审计 artifact |
| 提交快照 | PackageSubmissionArtifact 不可变 | 支持 re-verify、审计追溯、重现 |
| BeliefSnapshot key | 从 (knowledge_id, version) 改为 global_canonical_id | BP 在 Global Canonical Graph 上运行 |
| VectorStore 后端 | 当前 LanceDB，ByteHouse 延后 | 接口不变，后续可替换实现 |
| 术语 | premises/conclusions/contexts | 对齐 Graph IR 和 BP on Graph IR 文档 |

---

## 9. 与其他文档的关系

| 文档 | 关系 |
|------|------|
| [architecture.md](architecture.md) v2.0 | 本文档 §2-3 展开 architecture.md §4 的实体和后端设计 |
| [../graph-ir.md](../graph-ir.md) | 定义 Graph IR 结构。本文档定义 server 如何存储这些结构 |
| [../bp-on-graph-ir.md](../bp-on-graph-ir.md) | 定义 BP 语义。影响 FactorNode 字段设计和 GlobalInferenceState 结构 |
| [../review/publish-pipeline.md](../review/publish-pipeline.md) | 定义 publish cycle。影响 PackageSubmissionArtifact 和 CanonicalBinding 的写入时机 |
