# Gaia Server Storage Schema

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.1 |
| 日期 | 2026-03-10 |
| 状态 | Draft — §3.2 Neo4j 图拓扑部分为 provisional，依赖 Phase 3 graph-spec.md 确认 |
| 关联文档 | [architecture.md](architecture.md) — Server 整体架构, [../domain-model.md](../domain-model.md) — 领域模型, [../theory/inference-theory.md](../theory/inference-theory.md) — BP 理论 |

---

## 1. 设计原则

- 存储模型直接基于 **Gaia Language** 概念（closure、chain、module、package），不引入中间的 Node/HyperEdge 抽象层
- **StorageManager 是唯一门面**——domain services 不直接接触具体后端
- 每个后端是特定数据的 **source of truth**，不是彼此的副本
- BP 的因子图从 closure + chain 动态构建，不持久存储
- Closure 有显式版本号，同 id 同 version 只存一份
- Belief 和 probability 保留完整演化历史
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
    exports:       list[str]     # 对外导出的 closure_id
    submitter:     str
    submitted_at:  datetime
    status:        str           # submitted | merged | rejected
```

### 2.2 Module

一个内聚的知识单元，分组 closure 并通过 chain 串联推理。

```
Module:
    module_id:     str           # package_id + module_name
    package_id:    str
    name:          str
    role:          str           # reasoning | setting | motivation | follow_up_question | other
    imports:       list[ImportRef]
    chain_ids:     list[str]     # 有序
    export_ids:    list[str]     # 此 module 导出的 closure_id

ImportRef:
    closure_id:    str
    version:       int
    strength:      str           # strong | weak
```

### 2.3 Closure

全局可复用的知识对象。带显式版本号，支持用户多次提交修订。

```
Closure:
    closure_id:    str           # 全局唯一
    version:       int           # 显式版本号，同 id 同 version 只存一份
    type:          str           # claim | question | setting | action
    content:       str
    prior:         float         # ∈ (0, 1)，setting 允许 1.0
    keywords:      list[str]
    source_package_id: str       # 创建此版本的 package
    source_module_id:  str
    created_at:    datetime
    embedding:     list[float] | None
```

**版本规则：**
- `(closure_id, version)` 唯一。入库时如果已存在则跳过
- 新版本由新 package 提交时创建，旧版本不可变
- Belief 不在 Closure 表中——独立存储在 BeliefHistory 中

**未来扩展：** Closure 之间的 bundle 和聚类通过新建边关系实现，不修改 closure 本身。

### 2.4 Chain

Module 内的推理链，连接 closure 之间的推理关系。

```
Chain:
    chain_id:      str           # module_id + chain_name
    module_id:     str
    package_id:    str
    type:          str           # deduction | induction | abstraction | contradiction | retraction
    steps:         list[ChainStep]

ChainStep:
    step_index:    int           # 步骤序号（从 0 开始），作为步骤的稳定标识
    premises:      list[ClosureRef]  # 引用的 closure（含版本）
    reasoning:     str           # inference 文本（局部，不导出）
    conclusion:    ClosureRef    # 结论 closure（含版本）

ClosureRef:
    closure_id:    str
    version:       int           # 锁定引用的 closure 版本
```

### 2.5 ProbabilityRecord

推理步骤的可靠性，按 `(chain_id, step_index)` 粒度存储，支持多来源动态调整。

```
ProbabilityRecord:
    chain_id:      str
    step_index:    int           # 对应 ChainStep.step_index
    value:         float         # ∈ (0, 1]，induction 必须 < 1.0
    source:        str           # author | llm_review | lean_verify | code_verify
    source_detail: str | None    # model name, verifier version 等
    recorded_at:   datetime
```

**步骤粒度：** Gaia Language 的 chain_expr 是多步推理，每步有独立的 probability。Review sidecar 也按步调整 `suggested_prior`。因此 probability 绑定到 `(chain_id, step_index)` 而非整个 chain。Chain 的整体可靠性可由各步概率推导（如连乘）。

**多来源策略：** 同一个 step 可有多条 ProbabilityRecord。BP 使用当前生效值，默认取最新一条。未来可支持多来源加权。

**可能的 source 来源：**
- `author` — package 作者在 YAML 中设定
- `llm_review` — LLM review engine 评估后调整
- `lean_verify` — Lean 4 形式化验证结果
- `code_verify` — 代码执行验证结果

### 2.6 BeliefSnapshot

BP 计算结果的历史记录，追踪每个 closure 的信念演化。

```
BeliefSnapshot:
    closure_id:    str
    version:       int
    belief:        float         # ∈ [0, 1]
    bp_run_id:     str           # 哪次 BP 计算的
    computed_at:   datetime
```

每次 BP 运行产生一批 BeliefSnapshot。可追踪任意 closure 的信念演化：

```
closure "Heavy objects fall faster" (prior=0.3):
  BP run #1 (2 packages):  belief=0.28
  BP run #2 (5 packages):  belief=0.12  ← 新矛盾证据入库
  BP run #3 (8 packages):  belief=0.05  ← 更多反驳
```

### 2.7 Resource

附加资源的元信息。实际文件存 TOS，数据库只存元信息和 TOS 路径。

```
Resource:
    resource_id:       str           # 全局唯一
    type:              str           # image | code | notebook | dataset | checkpoint | tool_output | other
    format:            str           # png, py, ipynb, parquet, safetensors, json...
    title:             str | None
    description:       str | None
    storage_backend:   str           # tos
    storage_path:      str           # TOS bucket + key
    size_bytes:        int | None
    checksum:          str | None    # sha256
    metadata:          dict          # 自由 key-value，按 type 不同存不同元信息
    created_at:        datetime
    source_package_id: str
```

`metadata` 按 type 约定不同字段：

| type | metadata 示例 |
|------|-------------|
| image | `{"width": 800, "height": 600, "caption": "Figure 3"}` |
| code | `{"language": "python", "entrypoint": "main.py"}` |
| notebook | `{"kernel": "python3", "cell_count": 42}` |
| dataset | `{"rows": 10000, "columns": ["x", "y"], "format": "parquet"}` |
| checkpoint | `{"framework": "pytorch", "model_name": "gpt-neo", "epoch": 5}` |
| tool_output | `{"tool": "lean4", "exit_code": 0, "verified": true}` |

### 2.8 ResourceAttachment

Resource 和 closure/chain/module/package 的多对多关联。

```
ResourceAttachment:
    resource_id:   str
    target_type:   str           # closure | chain | chain_step | module | package
    target_id:     str           # 对应实体的 id（chain_step 使用 "chain_id:step_index" 复合键）
    role:          str           # evidence | visualization | implementation | reproduction | supplement
    description:   str | None    # 这个资源在此处的作用说明
```

一个 resource 可关联多个实体。例如一张实验图同时支撑两个 claim。

**chain_step 寻址：** `ChainStep` 通过 `step_index` 获得稳定标识。当 `target_type = "chain_step"` 时，`target_id` 使用 `"chain_id:step_index"` 复合键（如 `"mod1.chain1:2"`）。

### 2.9 FactorGraph（BP 运行时，不持久存储）

```
Variable:   (closure_id, version) → prior, current_belief
Factor:     (chain_id, step_index) → type, current_probability, premise_ids, conclusion_id
```

每次 BP 运行时从 Closure + Chain + ProbabilityRecord 动态构建。每个 ChainStep 对应一个 Factor。

---

## 3. 各后端存储分工

### 3.1 LanceDB — 全量信息，支持搜索和浏览

LanceDB 是核心 source of truth。

| 表 | 存储内容 | 主要查询 |
|---|---|---|
| `packages` | Package 全部字段 | 按 name/status 查询 |
| `modules` | Module 全部字段（含 imports） | 按 package_id 查询 |
| `closures` | Closure 全部字段 + embedding | BM25 搜索、向量搜索、按 (id, version) 精确查 |
| `chains` | Chain 全部字段（含 steps） | 按 module_id/package_id 查询 |
| `probabilities` | ProbabilityRecord | 按 (chain_id, step_index) 查询历史 |
| `belief_history` | BeliefSnapshot | 按 closure_id 查询演化 |
| `resources` | Resource 元信息 | 按 type/package_id 查询 |
| `resource_attachments` | ResourceAttachment | 按 target_type + target_id 查询 |

### 3.2 Neo4j — 图拓扑，支持遍历和 BP 构建

> **Provisional:** 本节定义的图模型（节点类型、关系类型、属性）依赖 Phase 3 `graph-spec.md` 最终确认。在 graph-spec 完成前，此处的设计可能调整。

```
节点:
    (:Closure  {closure_id, version, type, prior, belief})
    (:Chain    {chain_id, type, probability})
    (:Module   {module_id, name, role})
    (:Package  {package_id, name, version})
    (:Resource {resource_id, type, format})

关系:
    # 推理拓扑（BP 核心）
    (:Closure)-[:PREMISE {step_index}]->(:Chain)
    (:Chain)-[:CONCLUSION {step_index}]->(:Closure)

    # 组织结构
    (:Closure)-[:BELONGS_TO]->(:Module)
    (:Chain)-[:BELONGS_TO]->(:Module)
    (:Module)-[:BELONGS_TO]->(:Package)

    # 跨 module 依赖
    (:Module)-[:IMPORTS {strength}]->(:Closure)

    # 资源关联
    (:Resource)-[:ATTACHED_TO {role}]->(:Closure)
    (:Resource)-[:ATTACHED_TO {role}]->(:Chain)
```

Belief 和 probability 的最新值冗余存在 Neo4j 节点属性上，方便遍历时直接读取。由 StorageManager 在 BP 完成或 probability 更新时同步。

### 3.3 VectorStore — 向量搜索

| 存储 | 内容 |
|---|---|
| closure 向量 | `(closure_id, version, embedding)` |

查询：`search(embedding, top_k) → list[(closure_id, version, score)]`

### 3.4 TOS — 对象存储

存储实际的多模态文件（图片、代码、notebook、数据集、checkpoint 等）。

数据库中 Resource.storage_path 指向 TOS 路径。

### 3.5 降级模式

| 状态 | 影响 |
|------|------|
| Neo4j 不可用 | 图查询返回空，拓扑搜索跳过，入库只写 LanceDB + Vector |
| VectorStore 不可用 | 向量搜索跳过，入库只写 LanceDB + Neo4j |
| TOS 不可用 | 资源文件无法上传/下载，元信息仍可查询 |
| LanceDB 不可用 | **系统不可用**（核心 source of truth） |

---

## 4. StorageManager 接口

```python
class StorageManager:
    """所有存储操作的唯一门面"""

    # ── Package 入库（三写原子性）──
    async def ingest_package(self, package: PackageData) -> IngestResult

    # ── Closure ──
    async def get_closure(self, closure_id: str, version: int | None = None) -> Closure | None
    async def get_closures(self, closure_ids: list[str]) -> list[Closure]
    async def get_closure_versions(self, closure_id: str) -> list[Closure]

    # ── Package / Module ──
    async def get_package(self, package_id: str) -> Package | None
    async def get_module(self, module_id: str) -> Module | None
    async def get_chains_by_module(self, module_id: str) -> list[Chain]

    # ── Probability（按步粒度，动态多来源）──
    async def add_probability(self, record: ProbabilityRecord) -> None
    async def get_probability(self, chain_id: str, step_index: int) -> float
    async def get_probability_history(self, chain_id: str,
                                      step_index: int | None = None) -> list[ProbabilityRecord]

    # ── Belief（BP 结果，按版本化 closure）──
    async def write_beliefs(self, bp_run_id: str,
                            beliefs: dict[tuple[str, int], float]) -> None  # key=(closure_id, version)
    async def get_current_belief(self, closure_id: str, version: int | None = None) -> float | None
    async def get_belief_history(self, closure_id: str,
                                 version: int | None = None) -> list[BeliefSnapshot]

    # ── Resource ──
    async def write_resources(self, resources: list[Resource],
                              attachments: list[ResourceAttachment]) -> None
    async def get_resource(self, resource_id: str) -> Resource | None
    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]

    # ── 图查询（委托 Neo4j）──
    async def get_neighbors(self, closure_id: str, direction: str,
                            chain_types: list[str] | None,
                            max_hops: int) -> Subgraph
    async def get_subgraph(self, closure_id: str, max_closures: int) -> Subgraph

    # ── 搜索 ──
    async def search_vector(self, embedding: list[float], top_k: int) -> list[ScoredClosure]
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredClosure]
    async def search_topology(self, seed_ids: list[str], hops: int) -> list[ScoredClosure]

    # ── BP 用 ──
    async def load_all_closures(self) -> list[Closure]
    async def load_all_chains(self) -> list[Chain]
    async def load_all_probabilities(self) -> dict[tuple[str, int], float]  # key=(chain_id, step_index)
```

---

## 5. 各后端 ABC

```python
class ContentStore(ABC):
    """LanceDB — 全量内容与元数据"""

    # 写入
    async def write_package(self, package: PackageData) -> None
    async def write_closures(self, closures: list[Closure]) -> None
    async def write_chains(self, chains: list[Chain]) -> None
    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None
    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None
    async def write_resources(self, resources: list[Resource],
                              attachments: list[ResourceAttachment]) -> None

    # 读取
    async def get_closure(self, closure_id: str, version: int | None) -> Closure | None
    async def get_closure_versions(self, closure_id: str) -> list[Closure]
    async def get_package(self, package_id: str) -> Package | None
    async def get_module(self, module_id: str) -> Module | None
    async def get_chains_by_module(self, module_id: str) -> list[Chain]
    async def get_probability_history(self, chain_id: str,
                                      step_index: int | None = None) -> list[ProbabilityRecord]
    async def get_belief_history(self, closure_id: str) -> list[BeliefSnapshot]
    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]

    # 搜索
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredClosure]

    # BP 批量加载
    async def list_closures(self) -> list[Closure]
    async def list_chains(self) -> list[Chain]


class GraphStore(ABC):
    """Neo4j — 图拓扑"""

    # 写入
    async def write_topology(self, closures: list[Closure], chains: list[Chain]) -> None
    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None
    async def update_beliefs(self, beliefs: dict[str, float]) -> None
    async def update_probability(self, chain_id: str, step_index: int, value: float) -> None

    # 查询
    async def get_neighbors(self, closure_id: str, direction: str,
                            chain_types: list[str] | None, max_hops: int) -> Subgraph
    async def get_subgraph(self, closure_id: str, max_closures: int) -> Subgraph
    async def search_topology(self, seed_ids: list[str], hops: int) -> list[ScoredClosure]


class VectorStore(ABC):
    """向量搜索"""

    async def write_embeddings(self, items: list[ClosureEmbedding]) -> None
    async def search(self, embedding: list[float], top_k: int) -> list[ScoredClosure]
```

---

## 6. 三写一致性

Package 入库是 server 唯一的写入路径：

```
ingest_package(pkg):
    1. LanceDB.write(closures, chains, modules, package, resources)  ← source of truth 先落盘
    2. Neo4j.write(topology + resource links)                        ← 图拓扑
    3. VectorStore.write(embeddings)                                  ← 向量索引

    失败策略：
    - 步骤 2 失败 → 删除步骤 1 写入的记录
    - 步骤 3 失败 → 删除步骤 1、2 写入的记录
    - LanceDB 优先：它是 source of truth，最先写入
```

其他写入路径（非 package 入库）：
- `add_probability()` → 写 LanceDB（按 chain_id + step_index）+ 同步 Neo4j 属性
- `write_beliefs()` → 写 LanceDB belief_history（按 closure_id + version）+ 同步 Neo4j 属性

---

## 7. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据模型基础 | Gaia Language 概念（closure/chain/module/package） | 直接对齐领域模型，不引入中间抽象 |
| Closure 版本 | 显式版本号，`(closure_id, version)` 唯一 | 支持 track 用户多次提交修订 |
| 版本化引用 | ChainStep 通过 ClosureRef 锁定 `(closure_id, version)` | 避免多版本歧义，chain 始终引用确定的 closure 版本 |
| Probability 粒度 | 按 `(chain_id, step_index)` 而非整个 chain | 对齐 Gaia Language 多步推理和 review sidecar 按步调整 |
| ChainStep 标识 | `step_index` 作为稳定标识，复合键 `chain_id:step_index` | 支持 ResourceAttachment 和 ProbabilityRecord 的步骤级引用 |
| Belief | 保留完整演化历史 | 可追踪命题可信度随时间变化 |
| 因子图 | 不持久存储，每次 BP 运行时构建 | 因子图是派生数据，不是 source of truth |
| 多模态资源 | Resource + ResourceAttachment + TOS | 灵活关联，文件存 TOS |
| Neo4j 超边建模 | Chain 作为中间节点（provisional，依赖 graph-spec） | 保留"多前提联合支持结论"的超边语义 |
| Neo4j belief/probability | 冗余存储最新值在节点属性 | 方便遍历时直接读取 |
| 术语 | premises/conclusions（不用 head/tail） | 对齐 Gaia Language 领域词汇 |
