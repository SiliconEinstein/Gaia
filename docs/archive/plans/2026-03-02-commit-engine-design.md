# Commit Engine 模块详细设计

> **Status:** COMPLETED

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.4 |
| 日期 | 2026-03-02 |
| 状态 | 设计完成 |
| 前置文档 | `docs/plans/2026-03-02-lkm-api-design-v2.md`, `docs/plans/2026-03-02-storage-layer-design.md` |
| 目标 | 定义 Commit Engine 模块的结构、接口和工作流 |
| 变更记录 | v1.0: 初始设计; v1.1: 统一命名 (Node/HyperEdge); v1.2: Node 模型变更——text→content, confidence→prior, 新增 title/metadata 字段; v1.3: HyperEdge.reasoning 改为 list = []; v1.4: Node 移除 notations/assumptions (改用 extra)，content 类型改为 str\|dict\|list，type 改为 str；Node/HyperEdge 新增 extra: dict |

---

## 1. 设计原则

- **3 步流程**：Submit → Review → Merge，无独立 resolve 步骤
- **3 种操作**：`add_edge`、`modify_edge`、`modify_node`
- **节点不独立存在**：新节点只能通过 `add_edge` 进入图
- **不做节点合并**：无 `merge_nodes` 操作
- **重合处理**：merge 时有未解决重合则拒绝，用户修改后重新提交

---

## 2. 与 API v2 的变更对照

| API v2 (旧) | 本设计 (新) | 原因 |
|-------------|-----------|------|
| 4 步: submit → review → resolve → merge | 3 步: submit → review → merge | resolve 不需要独立步骤，用户修改后重新提交 |
| 6 个状态 (含 needs_resolution, resolved) | 3 个状态 (pending_review, reviewed, rejected/merged) | 简化状态机 |
| 4 种操作 (含 merge_propositions) | 3 种操作 | 新架构不做节点合并 |
| 操作名 modify_proposition | modify_node | 统一命名 |

---

## 3. 工作流

### 3.1 状态机

```
POST /commits          POST /commits/{id}/review          POST /commits/{id}/merge
      │                         │                                  │
      ▼                         ▼                                  ▼
 pending_review ──────────► reviewed ──────────────────────────► merged
                               │
                               └──► rejected
```

### 3.2 三步流程

**Submit (POST /commits)**：
1. Validator 结构校验（不涉及 LLM）
2. DedupChecker 多路召回去重（vector + BM25，不涉及 LLM）
3. CommitStore 持久化，状态 → `pending_review`
4. 返回 check_results（去重候选、候选矛盾）

**Review (POST /commits/{id}/review)**：
1. LLM 深度审核每条操作
2. 推理有效性、质量评分、重合检测、矛盾检测
3. 状态 → `reviewed`（通过）或 `rejected`（推理无效）
4. 返回 review_results（质量分、确认的重合、确认的矛盾）

**Merge (POST /commits/{id}/merge)**：
1. 检查前置条件：status 必须为 `reviewed`
2. 检查有无未解决的重合 → 有则拒绝
3. 执行入图操作（triple-write）
4. 触发局部 BP
5. 状态 → `merged`
6. 返回 merge_results（创建的节点/超边、belief 更新）

### 3.3 重合处理流程

merge 时有未解决重合则拒绝，用户需修改后重新提交：

```
1. submit → dedup 发现 tail[1] 与节点 102 重合
2. review → LLM 确认重合
3. merge → 拒绝: "有未解决的重合"
4. 用户重新 submit（二选一）:
   a. tail[1] 改为引用已有节点: {"node_id": 102}
   b. 修改 content 使其不再重合
5. 新 commit → review → merge ✓
```

---

## 4. 操作类型

### 4.1 add_edge — 新增超边

tail/head 中的节点支持两种写法：

```json
{
  "op": "add_edge",
  "tail": [
    {"content": "DFT预测fcc YH10稳定", "keywords": "...", "extra": {"notations": "..."}},
    {"node_id": 102}
  ],
  "head": [
    {"content": "YH10在400GPa下Tc≈303K", "keywords": "...", "extra": {"notations": "T_c \\approx 303\\,K"}}
  ],
  "type": "paper-extract",
  "reasoning": ["基于 DFT 和 Eliashberg 方程的理论预测"]
}
```

- 新节点：提供 `content` 等字段，需要去重检查
- 引用已有节点：只提供 `node_id`，不需要去重

### 4.2 modify_edge — 修改超边

```json
{
  "op": "modify_edge",
  "edge_id": 456,
  "changes": {"status": "retracted", "reason": "原始数据有误"}
}
```

### 4.3 modify_node — 修改节点

```json
{
  "op": "modify_node",
  "node_id": 789,
  "changes": {"content": "修正后的文本", "extra": {"notations": "修正后的符号"}}
}
```

---

## 5. 目录结构

```
services/commit-engine/
├── __init__.py
├── engine.py            # CommitEngine — 主入口
├── store.py             # CommitStore — commit 状态持久化 (LanceDB)
├── validator.py         # Validator — 结构校验
├── dedup.py             # DedupChecker — 去重召回
├── reviewer.py          # Reviewer — LLM 审核编排
└── merger.py            # Merger — 入图操作
```

---

## 6. 接口设计

### 6.1 CommitEngine — 对外入口 (4 个方法)

```python
# services/commit-engine/engine.py
class CommitEngine:
    """Commit 工作流编排"""

    def __init__(self, storage: StorageManager, llm: LLMClient): ...

    async def submit(self, request: CommitRequest) -> CommitResponse:
        """POST /commits — 校验 + 去重召回 + 持久化"""

    async def review(self, commit_id: str, depth: str = "standard") -> ReviewResponse:
        """POST /commits/{id}/review — LLM 审核
        前置: status == pending_review"""

    async def merge(self, commit_id: str, force: bool = False) -> MergeResponse:
        """POST /commits/{id}/merge — 入图
        前置: status == reviewed, 无未解决重合 (或 force=true)"""

    async def get_commit(self, commit_id: str) -> Commit:
        """GET /commits/{id} — 查询状态"""
```

### 6.2 CommitStore — 状态持久化 (3 个方法)

```python
# services/commit-engine/store.py
class CommitStore:
    """LanceDB commits 表"""

    def __init__(self, lance_store: LanceStore): ...

    async def save(self, commit: Commit) -> str:
        """保存 commit，返回 commit_id"""

    async def get(self, commit_id: str) -> Commit | None:
        """按 ID 读取 commit"""

    async def update(self, commit_id: str, **fields) -> None:
        """更新 commit 字段 (status, review_results, merge_results)"""
```

### 6.3 Validator — 结构校验 (1 个方法)

```python
# services/commit-engine/validator.py
class Validator:
    """轻量结构校验，不涉及 LLM"""

    def __init__(self, storage: StorageManager): ...

    async def validate(self, operations: list[Operation]) -> list[ValidationResult]:
        """校验每条操作:
        - add_edge: tail/head 非空, type 合法, 引用的 node_id 存在
        - modify_edge: edge_id 存在
        - modify_node: node_id 存在
        """
```

### 6.4 DedupChecker — 去重召回 (1 个方法)

```python
# services/commit-engine/dedup.py
class DedupChecker:
    """多路召回去重，不涉及 LLM"""

    def __init__(self, storage: StorageManager): ...

    async def check(self, texts: list[str]) -> list[list[DedupCandidate]]:
        """对每条新节点文本，通过 vector search + BM25 召回候选匹配。
        引用已有 node_id 的节点跳过。
        返回每条文本的候选列表: [[(node_id, similarity), ...], ...]
        """
```

### 6.5 Reviewer — LLM 审核 (1 个方法)

```python
# services/commit-engine/reviewer.py
class Reviewer:
    """LLM 深度审核"""

    def __init__(self, llm: LLMClient, storage: StorageManager): ...

    async def review(self, commit: Commit, depth: str = "standard") -> ReviewResult:
        """审核 commit 中的每条操作:
        - add_edge: 推理有效性, 质量评分 (tightness/substantiveness),
                    重合检测 (LLM 判断候选是否语义等价), 矛盾检测
        - modify_edge: 影响评估
        - modify_node: 合理性评估

        depth:
        - "standard": 1-2 次 LLM 调用/操作
        - "thorough": 3-5 次 LLM 调用/操作 (+ 交叉验证, 新颖度)
        """
```

### 6.6 Merger — 入图 (1 个方法)

```python
# services/commit-engine/merger.py
class Merger:
    """应用 commit 到图"""

    def __init__(self, storage: StorageManager): ...

    async def merge(self, commit: Commit) -> MergeResult:
        """对每条操作执行入图:
        - add_edge:
            1. IDGenerator 分配 node_id / hyperedge_id
            2. LanceDB 写入新节点 (save_nodes)
            3. Neo4j 创建超边 (create_hyperedge)
            4. VectorSearch 写入 embedding (insert_batch)
        - modify_edge:
            1. Neo4j 更新超边 (update_hyperedge)
        - modify_node:
            1. LanceDB 更新节点 (update_node)
        - 触发局部 BP (返回 belief 更新)
        """
```

---

## 7. 接口总览

| 组件 | 方法 | 说明 |
|------|------|------|
| **CommitEngine** | `submit` | 提交 + 轻量检查 |
| | `review` | LLM 审核 |
| | `merge` | 入图 + 触发 BP |
| | `get_commit` | 查询 commit 状态 |
| **CommitStore** | `save` | 持久化 commit |
| | `get` | 读取 commit |
| | `update` | 更新 commit 字段 |
| **Validator** | `validate` | 结构校验 |
| **DedupChecker** | `check` | 多路召回去重 |
| **Reviewer** | `review` | LLM 深度审核 |
| **Merger** | `merge` | 入图操作 |

**总计 11 个公开方法。**

---

## 8. 数据模型

```python
class Operation(BaseModel):
    op: Literal["add_edge", "modify_edge", "modify_node"]

class AddEdgeOp(Operation):
    op: Literal["add_edge"] = "add_edge"
    tail: list[NewNode | NodeRef]          # {"content": ...} 或 {"node_id": 102}
    head: list[NewNode | NodeRef]
    type: str                               # paper-extract | abstraction | induction | contradiction
    reasoning: list

class ModifyEdgeOp(Operation):
    op: Literal["modify_edge"] = "modify_edge"
    edge_id: int
    changes: dict

class ModifyNodeOp(Operation):
    op: Literal["modify_node"] = "modify_node"
    node_id: int
    changes: dict

class NewNode(BaseModel):
    title: str | None = None
    content: str | dict | list
    keywords: list[str] = []
    metadata: dict | None = None
    extra: dict = {}

class NodeRef(BaseModel):
    node_id: int

class Commit(BaseModel):
    commit_id: str
    status: Literal["pending_review", "reviewed", "rejected", "merged"]
    message: str
    operations: list[AddEdgeOp | ModifyEdgeOp | ModifyNodeOp]
    check_results: dict | None = None
    review_results: dict | None = None
    merge_results: dict | None = None
    created_at: datetime
    updated_at: datetime
```

---

## 9. 思想实验验证

### 场景 1: Research Agent 提交新推理

```
submit: add_edge("DFT预测..." + "声子谱无虚频" → "YH10 Tc≈303K")
  → dedup 发现 "声子谱无虚频" 匹配节点 102
  → 返回候选重合

review: LLM 确认 tail[1] 与节点 102 语义等价

merge: 拒绝 — 有未解决重合

用户重新 submit: tail[1] 改为 {"node_id": 102}
  → 无重合
  → review 通过
  → merge 成功: 创建 1 个新节点 + 1 条超边，tail 引用已有节点 102
```

### 场景 2: Review 发现推理无效

```
submit: add_edge("水是湿的" + "天是蓝的" → "超导Tc=300K")
  → 结构合法，无重合

review: LLM 判断 reasoning_valid = false
  → status → rejected

Agent 放弃或重写
```

### 场景 3: 撤回超边

```
submit: modify_edge(456, status="retracted")
  → edge 456 存在 ✓

review: LLM 评估撤回影响 (12 个下游节点)

merge: Neo4j 更新 edge 456 → 触发 BP 重算 → belief 更新
```

### 场景 4: 批量注入

```
POST /commits/batch
  commits: [论文A的超边, 论文B的超边, ...]
  auto_review: true

每个 commit 独立走 submit → review → merge
批量优化: 跨 commit 去重、批量 LLM review、单次 BP 触发
```
