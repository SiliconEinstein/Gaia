# Inference Engine 模块详细设计

> **Status:** COMPLETED

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/plans/2026-03-02-storage-layer-design.md` |
| 目标 | 定义 Inference Engine 模块的结构和接口 |

---

## 1. 设计原则

- **两个方法**：局部 BP (merge 后触发) 和全局 BP (后台 daemon)
- **消息传递在进程内存**：不需要 Redis，BP 消息是单次计算的临时状态
- **Belief 写回 LanceDB**：计算完成后持久化到 `storage.lance.update_beliefs`
- **依赖 StorageManager**：直接用 `graph.get_subgraph` + `graph.get_hyperedge` 取子图，不引入额外存储依赖
- **Phase 1 Python 实现**：先用 Python/NumPy，后续按需迁移到 C++/Rust + gRPC

---

## 2. 目录结构

```
services/inference-engine/
├── __init__.py
├── engine.py            # InferenceEngine — 主入口 (2 个方法)
├── factor_graph.py      # FactorGraph — 内存中的 factor graph 构建
└── bp.py                # BeliefPropagation — loopy BP with damping
```

---

## 3. 接口设计

### 3.1 InferenceEngine — 对外入口 (2 个方法)

```python
# services/inference-engine/engine.py
class InferenceEngine:
    """Belief Propagation 推断引擎"""

    def __init__(self, storage: StorageManager): ...

    async def compute_local_bp(
        self, center_node_ids: list[int], hops: int = 3
    ) -> dict[int, float]:
        """局部 BP：merge 后触发，计算受影响节点的 belief。

        流程：
        1. storage.graph.get_subgraph(center_node_ids, hops) → node_ids, edge_ids
        2. 批量 storage.graph.get_hyperedge(eid) → 完整超边 (tail, head, probability)
        3. 构建 factor graph (进程内存)
        4. 运行 loopy BP with damping
        5. storage.lance.update_beliefs(results) 写回 LanceDB
        6. 返回 {node_id: belief}

        性能：
        - 3-hop 子图约 500 节点、2000 超边
        - 内存占用 ~200KB
        - P50 < 200ms, P99 < 1s
        """

    async def run_global_bp(self) -> None:
        """全局 BP：后台 daemon，按分区遍历全图维护一致性。

        流程：
        1. 将全图按连通分量 / 固定大小分区 (~10^4 节点/分区)
        2. 对每个分区：提取子图 → 构建 factor graph → 运行 BP
        3. 每个分区结果写回 LanceDB
        4. 循环，直到全图 belief 收敛或达到最大轮次

        性能：
        - 单分区 ~10^4 节点, ~10^5 消息, 内存 ~1.6MB
        - 32 workers 并行, 峰值内存 ~50MB
        - 全图一轮约 30 分钟
        """
```

### 3.2 FactorGraph — 内存中的 factor graph

```python
# services/inference-engine/factor_graph.py
class FactorGraph:
    """从超边数据构建 factor graph"""

    def __init__(self): ...

    def add_variable(self, node_id: int, prior: float) -> None:
        """添加变量节点 (对应图中的 Node)"""

    def add_factor(self, edge_id: int, tail: list[int], head: list[int],
                   probability: float) -> None:
        """添加因子节点 (对应图中的 HyperEdge)"""

    @classmethod
    def from_subgraph(cls, nodes: list[Node], edges: list[HyperEdge]) -> "FactorGraph":
        """从子图数据构建 factor graph"""
```

### 3.3 BeliefPropagation — BP 算法

```python
# services/inference-engine/bp.py
class BeliefPropagation:
    """Loopy Belief Propagation with damping"""

    def __init__(self, damping: float = 0.5, max_iterations: int = 50,
                 convergence_threshold: float = 1e-6): ...

    def run(self, graph: FactorGraph) -> dict[int, float]:
        """运行 BP，返回 {node_id: belief}

        消息传递:
        - variable → factor (v2f): 聚合其他 factor 的消息
        - factor → variable (f2v): 基于 factor 函数和其他 variable 的消息

        收敛条件:
        - 所有消息变化 < convergence_threshold
        - 或达到 max_iterations
        """
```

---

## 4. 数据流

### 局部 BP (merge 后触发)

```
Commit Engine merge 完成
    │
    ▼
InferenceEngine.compute_local_bp(affected_node_ids, hops=3)
    │
    ├──1──→ storage.graph.get_subgraph([node_ids], hops=3)
    │       → (node_ids, edge_ids)
    │
    ├──2──→ storage.graph.get_hyperedge(eid) for eid in edge_ids
    │       → list[HyperEdge] (含 tail, head, probability)
    │
    ├──3──→ storage.lance.load_nodes_bulk(node_ids)
    │       → list[Node] (取 belief 作为 prior)
    │
    ├──4──→ FactorGraph.from_subgraph(nodes, edges)
    │       → 内存中的 factor graph
    │
    ├──5──→ BeliefPropagation.run(factor_graph)
    │       → {node_id: new_belief}
    │
    └──6──→ storage.lance.update_beliefs(results)
            → 写回 LanceDB
```

### 全局 BP (后台 daemon)

```
定时触发 / 手动触发
    │
    ▼
InferenceEngine.run_global_bp()
    │
    ├── 分区 1: get_subgraph → build factor graph → BP → update_beliefs
    ├── 分区 2: ...
    ├── ...
    └── 分区 N: ...

    并行度: 32 workers
    每轮耗时: ~30 分钟
```

---

## 5. 接口总览

| 组件 | 方法 | 说明 |
|------|------|------|
| **InferenceEngine** | `compute_local_bp` | 局部 BP (merge 后触发) |
| | `run_global_bp` | 全局 BP (后台 daemon) |
| **FactorGraph** | `add_variable` | 添加变量节点 |
| | `add_factor` | 添加因子节点 |
| | `from_subgraph` | 从子图数据构建 |
| **BeliefPropagation** | `run` | 运行 loopy BP |

**对外 2 个方法，内部 4 个辅助方法。**

---

## 6. 调用方

| 调用方 | 使用的方法 | 场景 |
|--------|-----------|------|
| **Commit Engine (Merger)** | `compute_local_bp` | merge 后计算受影响节点 belief |
| **后台调度器** | `run_global_bp` | 定期全局一致性维护 |
| **查询时读 belief** | `storage.lance.get_beliefs_bulk` | 不经过引擎，直接读 LanceDB |

---

## 7. 后续演进

| Phase 1 | Phase 2 |
|---------|---------|
| Python + NumPy | C++/Rust + gRPC |
| 单进程 BP | 分布式 BP (多机) |
| 简单分区 | 基于图结构的智能分区 |
| 固定 damping | 自适应 damping |
