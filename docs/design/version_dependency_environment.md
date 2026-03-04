# 版本管理、依赖管理与虚拟环境

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [scaling_belief_propagation.md](scaling_belief_propagation.md), [agent_verifiable_memory.md](agent_verifiable_memory.md), [question_as_discovery_context.md](question_as_discovery_context.md) |
| 状态 | Wishlist |

---

## 目录

1. [核心洞察：Gaia 是概率化的知识依赖管理系统](#1-核心洞察gaia-是概率化的知识依赖管理系统)
2. [与 Git/Cargo/uv/Julia 的系统类比](#2-与-gitcargouv-julia-的系统类比)
3. [架构：Server as Registry, Local as Workspace](#3-架构server-as-registry-local-as-workspace)
4. [节点与边的版本管理](#4-节点与边的版本管理)
5. [Edge Dependency Pinning](#5-edge-dependency-pinning)
6. [变更分类与传播](#6-变更分类与传播)
7. [Belief Snapshot](#7-belief-snapshot)
8. [Thought Experiment（虚拟环境）](#8-thought-experiment虚拟环境)
9. [Knowledge Branch 与 Merge](#9-knowledge-branch-与-merge)
10. [本地 Workspace 设计](#10-本地-workspace-设计)
11. [统一 API 设计](#11-统一-api-设计)
12. [本地 vs 服务器实现策略](#12-本地-vs-服务器实现策略)
13. [与其他设计的关系](#13-与其他设计的关系)
14. [实施路线图](#14-实施路线图)

---

## 1. 核心洞察：Gaia 是概率化的知识依赖管理系统

Gaia 的推理超边本质上是一个依赖图：

```
Conclusion C (belief=0.85)
  ├── justified by P1 (belief=0.9)
  ├── justified by P2 (belief=0.7)
  └── via reasoning edge (probability=0.88)
```

这与包管理器的依赖图同构：

```
Package A (v1.2.0)
  ├── depends on B (≥2.0)
  ├── depends on C (≥1.0)
  └── depends on D (=4.1.0)
```

核心操作也对应：

| 包管理器 | Gaia |
|---------|------|
| 添加依赖 | 添加推理边 |
| 删除包 → 什么会 break？ | 删除/降低节点 → 哪些结论受影响？ |
| 更新包版本 → 兼容性检查 | 更新节点内容 → belief 重新传播 |
| 解决版本冲突 | 处理 contradiction |
| lockfile 快照一致状态 | belief snapshot |
| `cargo tree` 看依赖链 | subgraph API 看推理链 |

但有关键差异：

| | 包管理器 | Gaia |
|---|---|---|
| 约束类型 | 布尔（兼容/不兼容） | 概率（0~1 连续值） |
| 图结构 | 必须 DAG | 允许有环（loopy BP） |
| 冲突处理 | 报错，必须解决 | 量化为低 belief，BP 自动传播 |
| 解析算法 | SAT solver | Belief Propagation |

Gaia 本质上是一个 **probabilistic dependency resolver** — 它不 reject 不一致的状态，而是把不一致量化为低 belief。

---

## 2. 与 Git/Cargo/uv/Julia 的系统类比

### 2.1 从每个系统借鉴什么

**Git → 内容版本化**
- 对象模型：content-addressed, immutable
- "修改" = 创建新版本，旧版本永远存在
- Snapshot（commit）= 全量状态的不可变记录
- Branch = 可变指针指向不可变 snapshot
- Diff = 两个 snapshot 之间的差异
- Merge = 合并两条线的变更

**Cargo → 依赖兼容性管理**
- Spec vs Lock：Cargo.toml（我需要什么）vs Cargo.lock（我实际用的什么）
- Semver：变更分类决定对依赖方的影响
- `cargo outdated`：检测过期依赖
- `cargo update`：在兼容范围内更新

**uv/venv → 环境隔离与实验**
- 虚拟环境 = base + overlay，copy-on-write
- 秒级创建、用完即弃
- 完全隔离，不影响系统环境

**Julia Pkg → Registry 模型**
- Official registry（General）= 共享的包仓库
- 本地 environment 面向 registry 开发
- Project.toml + Manifest.toml = spec + lock
- 环境栈：Base → Project → Temp，逐层叠加
- `Pkg.develop()` = 本地开发，`Pkg.register()` = 发布到 registry

### 2.2 逐概念对照表

| 概念 | Git | Cargo | uv/venv | Julia | **Gaia** |
|------|-----|-------|---------|-------|----------|
| 状态快照 | commit | lockfile | — | Manifest.toml | Belief Snapshot |
| 内容版本 | blob hash | semver | — | package UUID+ver | Node/Edge version |
| 依赖声明 | — | Cargo.toml | requirements.txt | Project.toml | Gaia.toml |
| 依赖锁定 | — | Cargo.lock | uv.lock | Manifest.toml | Gaia.lock |
| 并行探索 | branch | — | venv | environment | Thought Experiment / Branch |
| 合并结果 | merge | — | — | — | 3-way merge + BP |
| 中央仓库 | GitHub | crates.io | PyPI | General registry | Gaia Server |
| 本地工作 | working dir | local project | venv | project env | Local Workspace |
| 发布 | push | publish | upload | register | submit (commit) |
| 影响分析 | — | `cargo tree` | — | — | downstream propagation |

---

## 3. 架构：Server as Registry, Local as Workspace

### 3.1 核心模型

本地不是一个独立的 Gaia 实例，而是面向 Server（registry）的 **development environment**。

```
Cargo:
  crates.io (registry)  ←── cargo publish ──  local project
       │                                          │
       └── cargo add (download deps) ────────────→┘

Gaia:
  Gaia Server (registry) ←── gaia submit ──  Local Workspace
       │                                          │
       └── gaia pull (fetch subgraph) ───────────→┘
```

- **Server = Registry**：共享知识图谱，source of truth，负责 review + merge
- **Local = Development environment**：个人工作空间，从 server 拉知识，本地推理，提交成果
- **Commit = Publish**：本地成果经过 review 后 merge 进 server

### 3.2 与 Agent 的关系

每个 agent 有自己的 local workspace：

```
Agent A workspace ──submit──→ Gaia Server ←──submit── Agent B workspace
       │                          │                         │
       └──────── pull ───────────→│←──────── pull ──────────┘
```

多个 agent 各自独立工作，通过 server 共享成果。和多个开发者各自 `cargo publish` 到同一个 registry 完全同构。

### 3.3 回顾 "Gaia is referee, not coach"

这个架构完美对应之前的定位：
- **Server（referee）**：验证、审核、维护共享知识的一致性
- **Local workspace（coach）**：自由探索、实验、推理

---

## 4. 节点与边的版本管理

### 4.1 内容不可变原则

借鉴 Git 的对象模型：内容不可变，"修改" = 创建新版本。

```
Node 42 v1: "Transformer attention is O(n²) in sequence length"
Node 42 v2: "Transformer self-attention is O(n²) in sequence length"
Node 42 v3: "Transformer attention is O(n) with linear attention approximation"

每个版本都保留，任何时候可以查看历史。
```

### 4.2 数据模型

```python
class Node(BaseModel):
    id: int
    version: int = 1
    content: str | dict | list
    content_hash: str | None = None    # SHA256(content)，内容寻址
    prior: float = 0.5
    belief: float | None = None
    # ... 其他字段 ...

class HyperEdge(BaseModel):
    id: int
    version: int = 1
    tail: list[int]
    head: list[int]
    tail_pins: dict[int, int] = {}     # node_id → pinned version
    head_pins: dict[int, int] = {}     # node_id → pinned version
    stale: bool = False                # dependency 是否已更新未检查
    probability: float | None = None
    # ... 其他字段 ...
```

### 4.3 Edge 的版本语义

关键区分 — 什么是版本更新，什么是新边：

- **版本更新**：前提和结论不变，推理过程改进（改写 reasoning 步骤、verification 更新 probability）
- **新边**：tail 或 head 变了 → 这是另一条推理，不是版本更新

### 4.4 利用 LanceDB 原生版本支持

LanceDB 基于 Lance 格式，原生支持 dataset versioning（append-only + time-travel query）。节点版本历史可以直接映射到 LanceDB 的版本机制，不需要自己实现版本存储。

---

## 5. Edge Dependency Pinning

### 5.1 Spec vs Lock

借鉴 Cargo 最核心的思想：声明与锁定分离。

```toml
# Cargo.toml (spec) — 我需要什么
[dependencies]
serde = "≥1.0"

# Cargo.lock (lock) — 我实际用的什么
serde = "1.0.197"
```

映射到 Gaia：

```python
# Edge 创建时（spec）— 我的推理基于 node 42
tail: [42, 17, 89]

# Edge 的 pinning（lock）— 推理基于这些节点的特定版本
tail_pins: {42: 2, 17: 1, 89: 3}
```

### 5.2 Stale Detection

当 tail 节点更新时，自动检测过期依赖：

```
Node 42: v2 → v3

所有 tail 含 node 42 的 edge:
  ├── edge.tail_pins[42] == 2
  ├── 当前 node 42 version == 3
  └── 标记 edge.stale = True
```

等价于 `cargo outdated`。

---

## 6. 变更分类与传播

### 6.1 Semver 思想的适配

节点内容变更的性质不同，对依赖方的影响不同：

| 变更类型 | 含义 | 举例 | 对依赖 edge 的影响 |
|---------|------|------|-------------------|
| **patch** | 措辞修改，语义不变 | "Pythom" → "Python" | 自动更新 pin，不动 probability |
| **minor** | 补充信息，不矛盾 | 增加细节说明 | 更新 pin，probability × 0.95 |
| **major** | 实质性改变 | 推翻原有事实 | 标记 stale，probability × 0.7，排队 review |

### 6.2 变更分类的实现

不需要用户手动声明（虽然支持）。自动分类策略：

```
1. content_hash 相同 → 无变更
2. embedding distance < ε₁ → patch
3. embedding distance < ε₂ 且 LLM 判断"不矛盾" → minor
4. 其他 → major
```

复用现有的 vector search 基础设施计算 embedding distance。

### 6.3 传播机制

Major 变更的 probability 折扣通过 BP 自动传播到下游：

```
Node 42 v2→v3 (major)
  → Edge 201 (tail contains 42): probability × 0.7, stale=True
    → Edge 201 的 head 节点: belief 被 BP 拉低
      → 依赖这些 head 节点的其他 edge: 继续传播
```

一个前提的重大变更会自动降低整个依赖链上所有结论的 belief。

---

## 7. Belief Snapshot

### 7.1 概念

Belief snapshot = Git commit。一个不可变的全量状态记录。

```python
class BeliefSnapshot:
    id: str                          # hash(content)
    parent: str | None               # 前一个 snapshot，形成链/DAG
    timestamp: datetime
    trigger: str                     # "post_merge" | "manual" | "scheduled"
    node_states: dict[int, tuple[int, float]]   # node_id → (version, belief)
    edge_states: dict[int, tuple[int, float, bool]]  # edge_id → (version, probability, stale)
```

### 7.2 创建时机

- 每次 commit merge 后自动创建（类似 Git auto-commit）
- 用户手动请求
- 定时快照（审计用）

### 7.3 Diff

两个 snapshot 之间的差异，等价于 `git diff`：

```
Snapshot A → B:
  node_42.belief:    0.72 → 0.85  (+0.13)  ← 新证据支持
  node_99.belief:    0.91 → 0.45  (-0.46)  ← contradiction 拉低
  edge_17.probability: 0.80 → 0.95         ← verification 更新
  edge_203: stale=True                      ← 依赖的节点有 major 变更
```

---

## 8. Thought Experiment（虚拟环境）

### 8.1 概念

Thought experiment = uv 的虚拟环境。

- 基底（base）= 某个 snapshot（类似 system Python）
- 叠加层（overlay）= belief overrides + speculative edges（类似 installed packages）
- 创建极快（只存 delta，不复制图）
- 完全隔离（不影响主图）
- 用完即弃（零成本销毁）

### 8.2 数据模型

```python
class ThoughtExperiment:
    id: str
    base_snapshot: str                      # fork from which snapshot
    belief_overrides: dict[int, float]      # sparse belief overrides
    added_nodes: list[Node]                 # speculative nodes
    added_edges: list[HyperEdge]            # speculative edges
    derived_beliefs: dict[int, float] | None  # BP result (lazy)
```

十亿节点的图谱，一个实验可能只 override 3 个 belief + 加 2 条边。存储成本近零。

### 8.3 使用流程

```
1. create  →  env = create_experiment(base="main", overrides={node_42: 1.0})
              "假设命题 42 为真"

2. reason  →  add_edge(env, tail=[42, 17], head=[new], ...)
              "在这个假设下推理"

3. propagate → propagate(env)
               "BP 看整个图在此假设下怎么变"

4. inspect  →  diff(env, base="main")
               "和主图比，什么变了？有没有矛盾？"

5a. promote →  submit(env) → 变成正式 commit → server review → merge
5b. discard →  delete(env) → 零成本
```

### 8.4 环境栈（借鉴 Julia）

环境可以嵌套，逐层叠加：

```
Main → Branch "BCS 理论" → Experiment "掺杂 x=0.2"

每层只存 delta，读取时逐层向上查找。
```

---

## 9. Knowledge Branch 与 Merge

### 9.1 Branch

Knowledge branch = Git branch。用于长期并行研究。

```
main: snapshot S₀
  ├── branch A: "假设超导机制是 BCS"  → S₁ₐ → S₂ₐ → ...
  └── branch B: "假设超导机制是 RVB"  → S₁ᵦ → S₂ᵦ → ...
```

每个 branch 有独立的 commit 历史和 belief 状态，底层共享图结构，只记录 delta。

### 9.2 Merge

Gaia 的 merge 比 Git 有优势 — 可以用 BP 自动 resolve 语义冲突：

```
Branch A: node 42 belief = 0.9（找到支持证据）
Branch B: node 42 belief = 0.3（找到反对证据）
Base:     node 42 belief = 0.6

Git 方式：报冲突，人工选择
Gaia 方式：把两个 branch 的新边都合并进主图，跑 BP 重新计算
          支持和反对证据共存，BP 给出综合后的 belief
```

这是 Gaia 相对于传统版本管理的独特优势：冲突不需要人工解决，概率推断自动量化分歧。

---

## 10. 本地 Workspace 设计

### 10.1 目录结构

```
~/.gaia/
├── config.toml              # server 地址、认证信息
├── cache/                   # 从 server 缓存的节点/边（只读）
│   ├── nodes/
│   └── edges/
└── workspaces/
    └── my-research/
        ├── Gaia.toml        # workspace 声明（依赖、配置）
        ├── Gaia.lock        # 锁定的 server 节点版本
        ├── local/           # 本地新增内容
        └── experiments/     # thought experiments
```

### 10.2 Gaia.toml

```toml
[workspace]
name = "superconductivity-research"
server = "https://gaia.example.com"
base_snapshot = "server:snapshot_abc123"

[dependencies]
# 从 server 引用的子图
[dependencies.topic]
query = "superconductivity"
min_belief = 0.5

[dependencies.nodes]
ids = [42, 17, 89]

[dependencies.subgraph]
root = 99
depth = 2
```

### 10.3 Gaia.lock

```toml
# 自动生成，记录精确版本和 belief
[[node]]
id = 42
version = 3
belief = 0.85
content_hash = "sha256:a1b2c3..."

[[node]]
id = 17
version = 1
belief = 0.72
content_hash = "sha256:d4e5f6..."

[[edge]]
id = 201
version = 2
probability = 0.88
tail_pins = { 42 = 3, 17 = 1 }
```

### 10.4 工作流

```
gaia init my-research                        # 创建 workspace
gaia pull "topic:superconductivity"          # 从 server 拉相关子图
                                             # → 生成 Gaia.lock

# 本地工作
gaia add-node "新命题..."                     # 添加本地节点
gaia add-edge --tail 42,17 --head new:1      # 添加推理边（混合 server + 本地节点）
gaia propagate                               # 本地 BP

# 实验
gaia experiment create --override "node:42=1.0"   # 创建虚拟环境
gaia experiment propagate                         # 在环境中跑 BP
gaia experiment diff                              # 看变化
gaia experiment promote                           # 满意 → 提升到 workspace
gaia experiment discard                           # 不满意 → 丢弃

# 检查更新
gaia outdated                                # server 节点有新版本？
gaia update                                  # 拉取最新，检查兼容性

# 提交
gaia submit                                  # 打包本地成果 → commit → server review
```

### 10.5 子图边界问题

本地 workspace 只持有图的子集，需要处理边界：

```
server 上的完整图:  A ── B ── C ── D ── E
本地 pull 了 B, C, D:        [B ── C ── D]
                              ↑           ↑
                          边界节点     边界节点
```

边界节点（B, D）的 belief 使用 server 上的值作为固定约束。本地 BP 在子图内部传播，边界条件固定。这类似有限元分析中的边界条件处理。

当 server 上的边界节点 belief 更新时（`gaia outdated` 检测到），本地 BP 需要以新的边界条件重跑。

---

## 11. 统一 API 设计

本地和服务器暴露相同的 API，实现不同：

### 11.1 版本管理

| API | 来源灵感 | 说明 |
|-----|---------|------|
| `GET /nodes/{id}/history` | `git log -- file` | 节点版本历史 |
| `GET /edges/{id}/history` | `git log -- file` | 边版本历史 |
| `GET /snapshots` | `git log --oneline` | 快照列表 |
| `GET /snapshots/{id}` | `git show` | 快照详情 |
| `POST /snapshots` | `git commit` | 手动创建快照 |
| `GET /diff/snapshots/{a}/{b}` | `git diff` | 快照间 belief diff |
| `POST /snapshots/{id}/restore` | `git checkout` | 恢复到历史快照 |

### 11.2 依赖管理

| API | 来源灵感 | 说明 |
|-----|---------|------|
| `GET /edges/stale` | `cargo outdated` | 检测过期依赖 |
| `POST /edges/{id}/revalidate` | `cargo update` | 重新验证边的兼容性 |
| `GET /nodes/{id}/dependents` | `cargo tree --invert` | 谁依赖了这个节点 |
| `GET /nodes/{id}/impact` | — | 变更影响分析 |

### 11.3 环境管理

| API | 来源灵感 | 说明 |
|-----|---------|------|
| `POST /experiments` | `uv venv` | 创建 thought experiment |
| `GET /experiments/{id}` | — | 查看实验状态 |
| `POST /experiments/{id}/propagate` | 在 venv 里运行代码 | 实验内 BP |
| `GET /experiments/{id}/diff` | `diff env vs base` | 与基底的 belief diff |
| `POST /experiments/{id}/promote` | `pip freeze` + publish | 提升为正式 commit |
| `DELETE /experiments/{id}` | `rm -rf .venv` | 丢弃实验 |

### 11.4 分支管理

| API | 来源灵感 | 说明 |
|-----|---------|------|
| `POST /branches` | `git branch` | 创建知识分支 |
| `GET /branches` | `git branch -a` | 列出所有分支 |
| `POST /branches/{id}/merge` | `git merge` + BP | 合并分支 |
| `GET /branches/{a}/diff/{b}` | `git diff A..B` | 分支间 diff |

---

## 12. 本地 vs 服务器实现策略

概念模型统一，实现按规模分化：

| 机制 | 本地（千~百万节点） | 服务器（十亿节点） |
|------|-------------------|-------------------|
| 版本存储 | LanceDB 单文件，原生 versioning | LanceDB 分布式 + 增量存储 |
| Snapshot | 全量序列化（KB 级） | 增量 diff（只存变更） |
| Experiment | 内存 deepcopy | COW overlay + sparse storage |
| BP | 全图 NumPy，秒级 | 增量/区域化 BP，Rust 引擎 |
| Stale detection | 全量扫描 O(E) | Reverse index（node → edges） |
| Merge conflict | 全图 BP resolve | 子图 BP + boundary propagation |

类比：SQLite vs PostgreSQL — 同样的 SQL，不同的引擎，适配不同的规模。

---

## 13. 与其他设计的关系

| 设计文档 | 关系 |
|---------|------|
| [scaling_belief_propagation.md](scaling_belief_propagation.md) | 大规模 BP 是 experiment/merge 的计算引擎；增量 BP 用于变更传播 |
| [agent_verifiable_memory.md](agent_verifiable_memory.md) | Agent workspace = local Gaia workspace；dry-run = thought experiment |
| [verification_providers.md](verification_providers.md) | Verification 更新 edge probability → 触发版本变更 + BP 传播 |
| [question_as_discovery_context.md](question_as_discovery_context.md) | Question 随 edge 版本一起管理；experiment 中的推理也携带 question |
| [text_structuring_service.md](text_structuring_service.md) | 自动提取的边在 local workspace 中创建，经 submit 进入 server |

---

## 14. 实施路线图

### Phase 1：节点与边的版本管理

- Node/Edge 增加 `version`, `content_hash` 字段
- ModifyNode/ModifyEdge 创建新版本而非覆盖
- 历史查询 API：`GET /nodes/{id}/history`
- 利用 LanceDB 原生 dataset versioning

### Phase 2：Dependency Pinning

- Edge 增加 `tail_pins`, `head_pins`, `stale` 字段
- Edge 创建时自动 pin 到 tail/head 当前版本
- Node 更新时自动标记依赖 edge 为 stale
- `GET /edges/stale` + `POST /edges/{id}/revalidate`
- 变更分类（embedding distance + LLM）

### Phase 3：Belief Snapshot

- Snapshot 数据模型与存储
- Merge 后自动创建 snapshot
- Snapshot diff API
- Snapshot 恢复

### Phase 4：Thought Experiment

- Experiment 创建/销毁 API
- Sparse overlay 存储
- Experiment 内 BP
- Promote → commit 流程

### Phase 5：Local Workspace

- `gaia` CLI 工具
- Gaia.toml / Gaia.lock 格式定义
- `gaia pull` / `gaia submit` / `gaia outdated` 命令
- 子图缓存与边界条件处理

### Phase 6：Knowledge Branch + Merge

- Branch 创建与管理
- 3-way belief merge + BP resolve
- Branch diff API
