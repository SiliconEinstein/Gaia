# Curation Batch Pipeline Design

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-19 |
| 状态 | Draft |
| 关联文档 | [2026-03-17-curation-service-design.md](2026-03-17-curation-service-design.md), [../../plans/2026-03-18-abstraction-agent.md](../../plans/2026-03-18-abstraction-agent.md) |

---

## 1. 动机

当前 `run_curation()` 的架构是 **全量加载 → 内存处理 → 一次写回**：

```python
all_nodes = await storage.list_global_nodes()     # 全量读
all_factors = await storage.list_factors()         # 全量读
# ... 全部在内存中处理 ...
await storage.upsert_global_nodes(updated_nodes)   # 全量写
await storage.write_factors(mutable_factors)        # 全量写
```

冷启动场景（100 万篇文章 → 500 万+ 节点）下，这个模式有三个致命问题：

1. **内存不可行**：500 万节点 + factor 无法全量加载
2. **无容错**：跑到 abstraction 第 400 批时崩溃，前 399 批的工作全部丢失
3. **全量写浪费**：只改了 100 个 factor，却重写 500 万条

新模式：**DB 是步骤间的共享状态，每步分批处理，每批写回 DB，支持断点续跑**。

## 2. 规模估算

| 层级 | 量级 | 备注 |
|------|------|------|
| 文章 | 1M | 冷启动全量 |
| Knowledge node | 5M-20M | 每篇 5-20 个 claim |
| Cluster | 100K-500K | 取决于相似度阈值 |
| LLM calls（abstraction） | 100K-500K | 每 cluster 至少 1 次，verify/refine 额外调用 |
| Factor | 10M+ | 原有 + curation 新增 |

## 3. Pipeline 步骤与依赖

```
                        ┌─────────────────┐
                        │  1. Clustering   │  需要全量 embedding
                        │  (分片构建 index) │
                        └────────┬────────┘
                                 │ 输出: cluster 列表（持久化到 DB）
                                 ▼
                        ┌─────────────────┐
                        │  2. Dedup        │  content hash 精确匹配
                        │  (全自动, 快)     │  分 batch 执行 merge
                        └────────┬────────┘
                                 │ 改动: 合并重复节点, 重定向 factor
                                 ▼
                        ┌─────────────────┐
                        │  3. Abstraction  │  LLM agent, 最慢
                        │  (分 batch)       │  每批写回新 node + factor
                        └────────┬────────┘
                                 │ ⚠️ BARRIER: 全量完成
                                 ▼
                        ┌─────────────────┐
                        │  4. Analysis     │  LLM agent
                        │  (分 batch)       │  在 abstraction tree 上分析
                        └────────┬────────┘
                                 │ ⚠️ BARRIER: 全量完成
                                 ▼
                        ┌─────────────────┐
                        │  5. Conflict     │  BP 全图 + sensitivity
                        │  Detection       │  probe 可分批
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  6. Structure    │  全图扫描
                        │  Inspection      │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  7. Cleanup      │  分 batch 执行
                        │  + Audit Log     │
                        └─────────────────┘
```

### 步骤间依赖

| 步骤 | 前置条件 | 是否需要 barrier |
|------|----------|:---:|
| Clustering | 全量 node embedding 可用 | — |
| Dedup | Clustering 全量完成 | ✓ |
| Abstraction | Dedup 全量完成（避免对重复节点做 abstraction） | ✓ |
| Analysis | Abstraction **全量**完成（需要完整 abstraction tree） | ✓ |
| Conflict Detection | Analysis 全量完成 | ✓ |
| Structure Inspection | Conflict Detection 完成 | ✓ |
| Cleanup | Structure Inspection 完成 | ✓ |

每个 barrier 的含义：下一步需要读到前一步产出的**全部**数据。例如 Analysis 需要遍历完整的 abstraction tree，如果 Abstraction 只做了一半就开始 Analysis，会漏掉后一半的 schema node。

## 4. 术语

本文档中几个容易混淆的概念：

| 术语 | 含义 | 解决什么问题 |
|------|------|-------------|
| **batch** | 一次从 DB 加载 N 个 work item 到内存处理，处理完写回 DB + 记 checkpoint | **内存**（不一次加载 50 万 cluster）和**容错**（崩溃后从上一个 batch 续跑） |
| **workers (semaphore)** | 一个 batch 内同时发出的 LLM 并发请求数 | **速度**（不串行等 LLM 响应） |
| **step** | Pipeline 中一个完整阶段（如 Abstraction、Conflict Detection） | **逻辑分层**，step 之间有依赖 |
| **barrier** | 上一步全部 batch 完成后，下一步才能开始 | **数据完整性**（Analysis 需要完整 abstraction tree） |
| **checkpoint** | 记录一个 step 中哪些 work item 已完成 | **断点续跑**（崩溃后跳过已完成的 batch） |
| **changeset** | 一个 batch 产出的增量改动（新增/修改/删除的 node 和 factor） | **增量写入**（不全量重写 DB） |

**batch 和 workers 的关系**：

```
Batch 1 (1000 clusters 加载到内存):
  ├─ worker 1: cluster_001 → LLM call ─┐
  ├─ worker 2: cluster_002 → LLM call  │ 同时进行
  ├─ ...                                │ (semaphore 控制并发数)
  └─ worker 10: cluster_010 → LLM call ┘
  (cluster_011 等 worker 空出来再发)
  ... 1000 个 cluster 全部完成
  → apply_changeset(增量写 DB)
  → record_checkpoint(记录这 1000 个 cluster 已完成)

Batch 2 (下一批 1000 clusters):
  ...
```

两个维度正交：batch_size 控制内存占用和 checkpoint 粒度，workers 控制 LLM 吞吐。瓶颈通常在 LLM API rate limit，调大 workers 到 rate limit 的 80% 即可，batch 之间串行不影响速度。

## 5. 核心抽象

### 4.1 CurationChangeSet

每个 batch 处理后产出的增量改动：

```python
@dataclass
class CurationChangeSet:
    """一批 curation 操作的增量改动。"""
    added_nodes: list[GlobalCanonicalNode] = field(default_factory=list)
    modified_nodes: list[GlobalCanonicalNode] = field(default_factory=list)
    removed_node_ids: list[str] = field(default_factory=list)
    added_factors: list[FactorNode] = field(default_factory=list)
    removed_factor_ids: list[str] = field(default_factory=list)
    audit_entries: list[AuditEntry] = field(default_factory=list)
```

### 4.2 StorageManager.apply_changeset()

增量三写方法（Content → Graph → Vector），替代全量 upsert：

```python
async def apply_changeset(self, changeset: CurationChangeSet) -> None:
    """增量写入 curation 改动到三个 store。"""
    # Content store
    if changeset.added_nodes or changeset.modified_nodes:
        await self.content_store.upsert_global_nodes(
            changeset.added_nodes + changeset.modified_nodes
        )
    if changeset.removed_node_ids:
        await self.content_store.delete_global_nodes(changeset.removed_node_ids)
    if changeset.added_factors:
        await self.content_store.add_factors(changeset.added_factors)  # 增量 append
    if changeset.removed_factor_ids:
        await self.content_store.delete_factors(changeset.removed_factor_ids)

    # Graph store (topology)
    if self.graph_store is not None:
        await self.graph_store.apply_topology_changeset(changeset)

    # Vector store (embeddings for new nodes)
    if self.vector_store is not None and changeset.added_nodes:
        await self.vector_store.index_nodes(changeset.added_nodes)
```

关键区别：
- `add_factors()` 是**增量 append**，不重写全表
- `delete_global_nodes()` / `delete_factors()` 是新方法，当前不存在
- Graph store 需要新的 `apply_topology_changeset()` 方法

### 4.3 CurationStep（Pipeline 步骤接口）

```python
class CurationStep(ABC):
    """Pipeline 中一个可分批执行的步骤。"""

    step_name: str

    @abstractmethod
    async def list_work_items(self, storage: StorageManager) -> list[str]:
        """从 DB 查询待处理的 work item ID 列表。

        已完成的 batch（通过 checkpoint 判断）自动跳过。
        """

    @abstractmethod
    async def process_batch(
        self, batch: list[str], storage: StorageManager
    ) -> CurationChangeSet:
        """处理一批 work items，返回增量改动。"""

    @property
    def batch_size(self) -> int:
        return 1000
```

### 4.4 Checkpoint（断点续跑）

每个步骤只有两个状态：**in_progress**（含未开始）和 **completed**。

```python
@dataclass
class StepCheckpoint:
    step_name: str
    completed_item_ids: set[str]  # 已完成的 work item ID
    status: Literal["in_progress", "completed"]
    last_updated: datetime
```

**幂等性保证**：所有 curation 操作使用确定性 ID（如 `gcn_schema_{sha256(sorted_members)}`），重复执行同一 batch 的 changeset 等价于 upsert，不会产生脏数据。因此 checkpoint 只是性能优化（跳过已完成的 batch），不是正确性保证。

| 操作 | 幂等性 | 原因 |
|------|--------|------|
| create_abstraction | ✅ | 确定性 schema_id，upsert 覆盖 |
| create_constraint | ✅ | 确定性 factor_id |
| dedup merge | ⚠️ 需检查 | source node 可能已删除，跳过即可 |
| delete node/factor | ✅ | 删除不存在的 ID → no-op |

存储方式：DB 中新建 `curation_checkpoints` 表。

### 4.5 PipelineRunner（编排器）

```python
class PipelineRunner:
    """按顺序执行 pipeline 步骤，每步分批，支持断点续跑。"""

    def __init__(self, storage: StorageManager, steps: list[CurationStep]):
        self.storage = storage
        self.steps = steps

    async def run(self) -> PipelineReport:
        for step in self.steps:
            checkpoint = await self._load_checkpoint(step.step_name)

            if checkpoint and checkpoint.status == "completed":
                logger.info("Step %s already completed, skipping", step.step_name)
                continue

            # 查 DB 拿 work items，跳过已完成的
            all_items = await step.list_work_items(self.storage)
            done = checkpoint.completed_item_ids if checkpoint else set()
            remaining = [item for item in all_items if item not in done]

            for batch in chunked(remaining, step.batch_size):
                changeset = await step.process_batch(batch, self.storage)
                await self.storage.apply_changeset(changeset)
                await self._record_batch_done(step.step_name, batch)

            await self._mark_step_completed(step.step_name)
            # BARRIER: 下一步可以开始了
```

**为什么 in_progress 时重新查 DB 是安全的**：步骤间有 barrier，in_progress 期间前置步骤已 completed，不会再改数据，`list_work_items()` 每次查询结果一致。

## 6. 各步骤的 Batch 策略

### 5.1 Clustering

**特殊处理**：不是简单的 per-item batch，而是全量 embedding index 构建。

- **Phase A**：分批计算 embedding（每批 1000 nodes，写回 vector store）
- **Phase B**：构建 FAISS index（需要全量 embedding，但可以分片构建 IVF index）
- **Phase C**：ANN search + BM25 双路召回，输出 cluster 列表
- **持久化**：cluster 列表写入 DB（新建 `curation_clusters` 表），供后续步骤读取

### 5.2 Dedup

- **Work item**：每个 cluster
- **Batch size**：1000 clusters
- **操作**：cluster 内 content hash 匹配 → merge → ChangeSet(modified_nodes, removed_node_ids, removed_factor_ids)
- **无 LLM 调用**，纯计算，很快

### 5.3 Abstraction

- **Work item**：每个 cluster（dedup 后剩余的、size >= 2 的）
- **Batch size**：1000 clusters
- **操作**：每 cluster 调 LLM（abstract → verify → refine）→ ChangeSet(added_nodes, added_factors)
- **并发**：batch 内用 `asyncio.Semaphore` 控制 LLM 并发（当前已实现）
- **这是最慢的步骤**，100K clusters × 3 LLM calls ≈ 300K LLM calls

### 5.4 Analysis

- **Work item**：每个 schema node（abstraction 产出的）
- **Batch size**：1000 schema nodes
- **操作**：分析 schema 下的 instance 关系 → contradiction pairs + induction hypotheses
- **前置**：需要 Abstraction 全量完成（barrier）

### 5.5 Conflict Detection

- **Level 1**：全图 BP（不分批，但可以用增量 BP）
- **Level 2**：sensitivity probe 分批（每批 1000 个候选节点 clamp + re-run BP）
- **前置**：需要 Analysis 全量完成

### 5.6 Cleanup

- **Work item**：每个 CurationSuggestion
- **Batch size**：1000 suggestions
- **操作**：执行 merge / create_constraint / archive 等 → ChangeSet

## 7. 与原仓库 (propositional_logic_analysis) 的对比

| 维度 | 原仓库 | Gaia |
|------|--------|------|
| **编排** | Shell 脚本串联独立 CLI 命令 | Python PipelineRunner，步骤间有显式 barrier |
| **持久化** | 文件系统（sharded JSON + SQLite） | LanceDB + Neo4j/Kuzu 三写 |
| **Batch 粒度** | LLM 调用用 semaphore，embedding 用 writer thread | 统一的 CurationStep.batch_size + ChangeSet |
| **断点恢复** | Round-based + `find_unverified_edges()` | Checkpoint 表，per-step per-batch 跟踪 |
| **增量写** | `save_node()` / `save_edge()` 逐条写文件 | `apply_changeset()` 批量增量三写 |
| **全图重建** | `build_graph_to_round()` 从 history 回放 | 不需要——DB 始终是最新状态 |

### 从原仓库借鉴的设计

1. **Semaphore-based LLM concurrency** — 已在 AbstractionAgent 中实现
2. **Round-based 审计** — 对应 AuditEntry，但 Gaia 用 DB 而非文件
3. **Incremental embedding** — 只处理没有 embedding 的新 node

### 不借鉴的设计

1. **文件系统 sharding** — Gaia 用 LanceDB，不需要自己做分片
2. **Shell 脚本编排** — Gaia 用 Python 内部编排，类型安全
3. **Graph JSON 全量快照** — Gaia 的 DB 就是状态，不需要额外快照

## 8. 需要新增/修改的 Storage 接口

| 方法 | 位置 | 说明 |
|------|------|------|
| `apply_changeset(changeset)` | StorageManager | 增量三写 |
| `add_factors(factors)` | ContentStore | 增量 append（当前 `write_factors` 是全量覆盖） |
| `delete_global_nodes(ids)` | ContentStore | 删除节点 |
| `delete_factors(ids)` | ContentStore | 删除 factor |
| `apply_topology_changeset(changeset)` | GraphStore | 增量图拓扑更新 |
| `index_nodes(nodes)` | VectorStore | 为新节点生成 + 写入 embedding |
| `write_clusters(clusters)` | ContentStore | 持久化 cluster 列表 |
| `read_clusters()` | ContentStore | 读取 cluster 列表 |
| `write_checkpoint(checkpoint)` | ContentStore | 写 step checkpoint |
| `read_checkpoint(step_name)` | ContentStore | 读 step checkpoint |

## 9. V1 范围

| 功能 | V1 | 后续 |
|------|:---:|:---:|
| CurationChangeSet 抽象 | ✓ | |
| StorageManager.apply_changeset() | ✓ | |
| CurationStep 接口 | ✓ | |
| PipelineRunner 编排器 | ✓ | |
| Checkpoint 断点续跑 | ✓ | |
| 增量 add_factors / delete_factors | ✓ | |
| 增量 delete_global_nodes | ✓ | |
| Graph store topology changeset | ✓ | |
| Vector store incremental indexing | | ✓（先不做 embedding） |
| Clustering 分片构建 | | ✓（先用全量） |
| 增量 BP | | ✓ |

## 10. 不在此次范围

- Clustering 的分片 FAISS index 构建（大规模优化）
- 增量 BP（只传播受影响区域）
- 事件驱动增量 curation
- Analysis agent 实现（§3.2.3，另起 spec）
