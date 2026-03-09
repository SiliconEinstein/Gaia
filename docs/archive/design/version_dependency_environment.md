# 版本管理、依赖管理与知识包

| 文档属性 | 值 |
|---------|---|
| 版本 | 2.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [scaling_belief_propagation.md](scaling_belief_propagation.md), [agent_verifiable_memory.md](agent_verifiable_memory.md), [question_as_discovery_context.md](question_as_discovery_context.md) |
| 状态 | Wishlist |
| 变更记录 | v2.0: 全面重构——引入 Knowledge Package 概念，统一环境模型，明确 Cargo 类比，去除 Git 作为本地后端的设计，新增三包仓库结构 |

---

## 目录

1. [核心洞察：Gaia = 概率化的 Cargo](#1-核心洞察gaia--概率化的-cargo)
2. [Knowledge Package：论文即包](#2-knowledge-package论文即包)
3. [与 Cargo/Julia 的系统对照](#3-与-cargojulia-的系统对照)
4. [统一环境模型](#4-统一环境模型)
5. [节点与边的版本管理](#5-节点与边的版本管理)
6. [Dependency Pinning](#6-dependency-pinning)
7. [变更分类与传播](#7-变更分类与传播)
8. [Belief Snapshot](#8-belief-snapshot)
9. [Gaia.toml / Gaia.lock](#9-gaiatoml--gaialock)
10. [CLI 工作流](#10-cli-工作流)
11. [Server API（Registry）](#11-server-apiregistry)
12. [Standalone 与 Connected 模式](#12-standalone-与-connected-模式)
13. [仓库结构：gaia-core / gaia-server / gaia-cli](#13-仓库结构gaia-core--gaia-server--gaia-cli)
14. [与其他设计的关系](#14-与其他设计的关系)
15. [实施路线图](#15-实施路线图)

---

## 1. 核心洞察：Gaia = 概率化的 Cargo

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
  ├── depends on B (>=2.0)
  ├── depends on C (>=1.0)
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

但 Gaia 是 **概率化** 的 Cargo — 这是本质区别：

| | 包管理器 | Gaia |
|---|---|---|
| 约束类型 | 布尔（兼容/不兼容） | 概率（0~1 连续值） |
| 图结构 | 必须 DAG | 允许有环（loopy BP） |
| 冲突处理 | 报错，必须解决 | 量化为低 belief，BP 自动传播 |
| 解析算法 | SAT solver（硬接口约束） | BP（节点不可变，不需要 SAT） |

Gaia 本质上是一个 **probabilistic dependency resolver** — 它不 reject 不一致的状态，而是把不一致量化为低 belief。更深层地，由于 Gaia 的节点是**不可变的**（content-addressed），跨包引用永远不会断裂，因此 Gaia 在 package 层**不需要 SAT resolver**——Cargo 需要 SAT 的根本原因（硬接口约束 + 版本排他性）在 Gaia 中不存在。Gaia 只需要轻量的版本偏好解析 + staleness 检测，BP 本身就是冲突解析器。详见 [theoretical_foundations.md](theoretical_foundations.md) §7.5。

---

## 2. Knowledge Package：论文即包

### 2.1 核心概念

一篇论文、一个理论体系、一个教科书章节、一条研究贡献 — 它们 **天然就是一个包**：

- 有明确的名字和版本
- 有明确的边界（这篇论文贡献了哪些命题和推理）
- 有明确的依赖（引用了哪些其他论文/理论）
- 有明确的 "导出" 接口（哪些结论可以被后续引用）

这意味着 Gaia **可以** 直接跟随 Cargo 模型：一个 Knowledge Package 就是一个命名的、版本化的子图。

### 2.2 包的构成

```
Knowledge Package "einstein1905_special_relativity"
├── 元数据
│   ├── name: "einstein1905_special_relativity"
│   ├── version: "1.0.0"
│   ├── authors: ["Albert Einstein"]
│   ├── source: "Annalen der Physik, 1905"
│   └── keywords: ["special relativity", "Lorentz transformation"]
├── 节点（命题）
│   ├── "光速在所有惯性参考系中不变"
│   ├── "物理定律在所有惯性参考系中相同"
│   ├── "E = mc²"
│   └── "时间膨胀效应"
├── 边（推理）
│   ├── [光速不变, 物理定律不变] → [洛伦兹变换]
│   └── [洛伦兹变换] → [E = mc²]
└── 依赖
    ├── "maxwell1865_electromagnetic_theory" >= "1.0"
    └── "lorentz1904_electron_theory" >= "1.0"
```

### 2.3 包的类型

| 包类型 | 说明 | 举例 |
|-------|------|------|
| `paper-extract` | 从单篇论文提取的知识 | `einstein1905_special_relativity` |
| `theory` | 一个完整的理论体系 | `quantum_mechanics_foundations` |
| `textbook-chapter` | 教科书章节 | `griffiths_em_ch9_radiation` |
| `research-contribution` | 原创研究贡献（agent 或人类） | `agent_bcs_extension_2026` |
| `meta-analysis` | 跨论文综合分析 | `superconductor_mechanism_survey` |

### 2.4 包名命名规范

遵循 Cargo 的 crate 命名风格：

```
<author_or_group>_<year>_<short_name>

示例:
  einstein1905_special_relativity
  bcs1957_superconductivity
  weinberg1967_electroweak_unification
  agent_bcs_extension_2026
```

### 2.5 导出接口

并非包内所有节点都对外可见。包声明哪些命题可以被其他包依赖：

```toml
[package]
name = "einstein1905_special_relativity"
version = "1.0.0"

[exports]
# 这些命题可以被其他包引用
nodes = [
    "speed_of_light_invariance",
    "e_equals_mc_squared",
    "time_dilation",
    "lorentz_transformation",
]
```

未导出的节点是包的内部推理步骤，外部不应依赖。这等价于 Rust 中 `pub` vs 私有的区分。

---

## 3. 与 Cargo/Julia 的系统对照

### 3.1 1:1 映射

以下概念在 Gaia 和 Cargo/Julia 之间有精确的对应关系：

| Cargo / Julia | Gaia | 说明 |
|---------------|------|------|
| crate / package | Knowledge Package | 命名的、版本化的知识单元 |
| Cargo.toml / Project.toml | Gaia.toml | 声明包元数据和依赖 |
| Cargo.lock / Manifest.toml | Gaia.lock | 锁定实际使用的版本 |
| crates.io / General registry | Gaia Server | 共享的包注册中心 |
| `cargo new` | `gaia init` | 创建新包 |
| `cargo add` | `gaia add` | 添加依赖 |
| `cargo build` | `gaia propagate` | 解析依赖并计算（BP 传播） |
| `cargo publish` | `gaia submit` | 发布到 registry |
| `cargo outdated` | `gaia outdated` | 检测过期依赖 |
| `cargo update` | `gaia update` | 更新到兼容的新版本 |
| semver | semver（适配） | 变更分类（patch/minor/major） |
| `pub` export | `[exports]` 节点 | 导出的公开接口 |
| feature flags | — | Gaia 用 belief 连续值替代布尔 feature |

### 3.2 Gaia 独有概念

以下概念在 Cargo/Julia 中没有对应物，是 Gaia 的概率化扩展：

| Gaia 概念 | 说明 | 最近的 Cargo 类比 |
|-----------|------|-------------------|
| belief | 节点的置信度（0~1） | 版本兼容性（布尔） |
| BP 传播 | 依赖变更时重新计算 belief | dependency resolution |
| contradiction | 两条推理链给出矛盾结论 | version conflict（但 Gaia 不报错，而是量化） |
| Thought Experiment | 假设性推理环境 | 无对应（最近是 `--dry-run`） |
| Belief Snapshot | 全量 belief 状态快照 | lockfile（但包含概率信息） |

### 3.3 关键差异

```
Cargo:
  依赖 = 硬接口调用 → 签名不兼容则编译失败
  冲突 → SAT solver → 有解或无解（布尔）
  无解 → 必须人工解决

Gaia:
  依赖 = 软知识引用 → 节点不可变，引用永不断
  冲突 → BP → 所有节点都有 belief（连续值）
  矛盾 → belief 被拉低，但系统不崩溃
  不需要 SAT — BP 即是 resolver
```

这意味着 Gaia 天然支持 "不一致但可用" 的状态 — 现实世界的科学知识本来就是这样。而且由于节点不可变性，Gaia 永远不会出现 Cargo 式的"版本不可满足"错误——多版本天然共存，BP 自动裁决。

---

## 4. 统一环境模型

### 4.1 核心洞察

Local workspace、thought experiment 和 knowledge branch **都是同一个东西**：一个环境（base + overlay）。不需要三套独立的架构。

```
Environment = Base Snapshot + Overlay (delta)

              ┌─────────────────────────────┐
              │ Overlay                     │
              │  - 新增/修改的节点           │
              │  - 新增/修改的边             │
              │  - belief overrides          │
              ├─────────────────────────────┤
              │ Base Snapshot               │
              │  - 不可变的参考状态           │
              └─────────────────────────────┘
```

### 4.2 三种环境只是生命周期和持久性不同

| 环境类型 | 生命周期 | 持久性 | 典型用途 |
|---------|---------|--------|---------|
| Local Workspace | 长期 | 持久化到磁盘 | 日常研究工作 |
| Knowledge Branch | 中期 | 持久化，有名字 | 并行研究方向 |
| Thought Experiment | 短期 | 内存或临时文件 | 快速假设检验 |

### 4.3 统一数据模型

```python
class Environment:
    id: str
    name: str
    base_snapshot: str            # fork 自哪个快照
    parent_env: str | None        # 环境可以嵌套
    belief_overrides: dict[int, float]   # sparse belief delta
    added_nodes: list[Node]
    added_edges: list[HyperEdge]
    removed_edges: list[int]             # "假设这条推理不存在"
    modified_nodes: dict[int, Node]
    modified_edges: dict[int, HyperEdge]
    derived_beliefs: dict[int, float] | None   # BP 结果（lazy）
    metadata: dict                # 用户自定义标签（用途描述等）
    status: str                   # "active" | "merged" | "archived"
```

**注意**：没有 `kind` 或 `persistent` 字段。"工作区/分支/实验" 只是用户的使用习惯，不是系统结构属性。统一环境模型意味着数据模型中不区分类型——如需标记用途，放 `metadata`。

### 4.4 环境栈

环境可以嵌套，逐层叠加（借鉴 Julia 的环境栈）：

```
Server Main
  └── Local Workspace "my-research"
        └── Branch "BCS 理论"
              └── Experiment "掺杂 x=0.2"

每层只存 delta，读取时逐层向上查找。
```

### 4.5 统一操作

所有环境支持相同的操作集：

| 操作 | 说明 |
|------|------|
| `create(base, kind)` | 创建环境 |
| `add_node(env, node)` | 在环境中添加节点 |
| `add_edge(env, edge)` | 在环境中添加边 |
| `override_belief(env, node_id, value)` | 覆盖 belief |
| `propagate(env)` | 在环境中运行 BP |
| `diff(env, base)` | 与基底的差异 |
| `promote(env)` | 提升到父环境（experiment → workspace → server） |
| `discard(env)` | 丢弃环境 |

promote 操作是分层的：
- Experiment promote → 合入 workspace/branch
- Branch merge → 合入 main
- Workspace submit → 打包成 commit，提交到 server review

### 4.6 Merge（BP-based）

Gaia 的 merge 比 Git 有优势 — 可以用 BP 自动 resolve 语义冲突：

```
Branch A: node 42 belief = 0.9（找到支持证据）
Branch B: node 42 belief = 0.3（找到反对证据）
Base:     node 42 belief = 0.6

Git 方式：报冲突，人工选择
Gaia 方式：把两个 branch 的新边都合并进主图，跑 BP 重新计算
          支持和反对证据共存，BP 给出综合后的 belief
```

冲突不需要人工解决，概率推断自动量化分歧。

---

## 5. 节点与边的版本管理

### 5.1 内容不可变原则

借鉴 Git 的对象模型：内容不可变，"修改" = 创建新版本。

```
Node 42 v1: "Transformer attention is O(n^2) in sequence length"
Node 42 v2: "Transformer self-attention is O(n^2) in sequence length"
Node 42 v3: "Transformer attention is O(n) with linear attention approximation"

每个版本都保留，任何时候可以查看历史。
```

### 5.2 数据模型

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
    tail_pins: dict[int, int] = {}     # node_id -> pinned version
    head_pins: dict[int, int] = {}     # node_id -> pinned version
    stale: bool = False                # dependency 是否已更新未检查
    probability: float | None = None
    # ... 其他字段 ...
```

### 5.3 Edge 的版本语义

关键区分 — 什么是版本更新，什么是新边：

- **版本更新**：前提和结论不变，推理过程改进（改写 reasoning 步骤、verification 更新 probability）
- **新边**：tail 或 head 变了 → 这是另一条推理，不是版本更新

### 5.4 利用 LanceDB 原生版本支持

LanceDB 基于 Lance 格式，原生支持 dataset versioning（append-only + time-travel query）。节点版本历史可以直接映射到 LanceDB 的版本机制，不需要自己实现版本存储。

---

## 6. Dependency Pinning

### 6.1 Spec vs Lock

借鉴 Cargo 最核心的思想：声明与锁定分离。

```toml
# Cargo.toml (spec) — 我需要什么
[dependencies]
serde = ">=1.0"

# Cargo.lock (lock) — 我实际用的什么
serde = "1.0.197"
```

映射到 Gaia：

```python
# Edge 创建时（spec）— 我的推理基于这些包的导出节点
tail: ["einstein1905_special_relativity::speed_of_light_invariance",
       "maxwell1865_electromagnetic_theory::field_equations"]

# Edge 的 pinning（lock）— 推理基于这些包的特定版本
tail_pins: {
    "einstein1905_special_relativity": "1.0.0",
    "maxwell1865_electromagnetic_theory": "2.1.0"
}
```

### 6.2 Stale Detection

当依赖的包更新时，自动检测过期依赖：

```
Package "einstein1905_special_relativity": v1.0.0 -> v1.1.0

所有依赖此包的 edge:
  ├── edge.tail_pins["einstein1905_special_relativity"] == "1.0.0"
  ├── 当前包版本 == "1.1.0"
  └── 标记 edge.stale = True
```

等价于 `cargo outdated`。

### 6.3 跨包依赖解析

包之间的依赖通过导出节点连接：

```
Package A 导出 node "conclusion_X"
Package B 的 edge 依赖 A 的 "conclusion_X"

A 更新 "conclusion_X" → B 的相关 edge 标记 stale
→ B 需要 revalidate 或更新 pin
```

---

## 7. 变更分类与传播

### 7.1 Semver 思想的适配

节点内容变更的性质不同，对依赖方的影响不同：

| 变更类型 | 含义 | 举例 | 对依赖 edge 的影响 |
|---------|------|------|-------------------|
| **patch** | 措辞修改，语义不变 | "Pythom" → "Python" | 自动更新 pin，不动 probability |
| **minor** | 补充信息，不矛盾 | 增加细节说明 | 更新 pin，probability x 0.95 |
| **major** | 实质性改变 | 推翻原有事实 | 标记 stale，probability x 0.7，排队 review |

包级别的版本号遵循标准 semver：

```
einstein1905_special_relativity v1.0.0
  → v1.0.1: 修正一个措辞错误（patch）
  → v1.1.0: 新增一个推论（minor，不影响已有导出）
  → v2.0.0: 修改核心命题的表述（major，可能影响所有依赖方）
```

### 7.2 变更分类的实现

不需要用户手动声明（虽然支持）。自动分类策略：

```
1. content_hash 相同 → 无变更
2. embedding distance < epsilon_1 → patch
3. embedding distance < epsilon_2 且 LLM 判断"不矛盾" → minor
4. 其他 → major
```

复用现有的 vector search 基础设施计算 embedding distance。

### 7.3 传播机制

Major 变更的 probability 折扣通过 BP 自动传播到下游：

```
Node 42 v2->v3 (major)
  → Edge 201 (tail contains 42): probability x 0.7, stale=True
    → Edge 201 的 head 节点: belief 被 BP 拉低
      → 依赖这些 head 节点的其他 edge: 继续传播
```

一个前提的重大变更会自动降低整个依赖链上所有结论的 belief。这跨越包的边界自动传播 — 如果包 A 的导出命题被 major 变更，所有依赖包 A 的下游包都会感受到 belief 的下降。

---

## 8. Belief Snapshot

### 8.1 概念

Belief snapshot = Git commit。一个不可变的全量状态记录。

```python
class BeliefSnapshot:
    id: str                          # hash(content)
    parent: str | None               # 前一个 snapshot，形成链/DAG
    timestamp: datetime
    trigger: str                     # "post_merge" | "manual" | "scheduled"
    node_states: dict[int, tuple[int, float]]   # node_id -> (version, belief)
    edge_states: dict[int, tuple[int, float, bool]]  # edge_id -> (version, probability, stale)
    package_versions: dict[str, str]  # package_name -> version
```

### 8.2 创建时机

- 每次 commit merge 后自动创建（类似 Git auto-commit）
- 用户手动请求
- 定时快照（审计用）

### 8.3 Diff

两个 snapshot 之间的差异，等价于 `git diff`：

```
Snapshot A -> B:
  node_42.belief:    0.72 -> 0.85  (+0.13)  <- 新证据支持
  node_99.belief:    0.91 -> 0.45  (-0.46)  <- contradiction 拉低
  edge_17.probability: 0.80 -> 0.95         <- verification 更新
  edge_203: stale=True                      <- 依赖的节点有 major 变更
  package "bcs1957": v1.0.0 -> v1.1.0       <- 包更新
```

---

## 9. Gaia.toml / Gaia.lock

### 9.1 Gaia.toml — 包声明

```toml
[package]
name = "agent_bcs_extension_2026"
version = "0.1.0"
description = "基于 BCS 理论的高温超导机制扩展研究"
authors = ["research-agent-alpha"]
keywords = ["superconductivity", "BCS", "high-Tc"]
type = "research-contribution"

[dependencies]
# 依赖其他知识包，使用 semver 范围
bcs1957_superconductivity = ">=1.0"
anderson1987_rvb_theory = ">=1.0, <2.0"
recent_htsc_experiments_2025 = ">=1.2"

[exports]
# 本包导出的命题（可被其他包依赖）
nodes = [
    "extended_bcs_pairing_mechanism",
    "predicted_tc_for_material_class_x",
    "doping_dependence_model",
]

[tool.gaia]
# 本地工作配置
server = "https://gaia.example.com"       # 可选，standalone 模式不需要
auto_propagate = true                      # add 后自动跑 BP
```

### 9.2 Gaia.lock — 依赖锁定

```toml
# 自动生成，不要手动编辑

[metadata]
generated_at = "2026-03-04T10:30:00Z"
base_snapshot = "snapshot_abc123"

[[package]]
name = "bcs1957_superconductivity"
version = "1.2.0"
content_hash = "sha256:a1b2c3d4..."

[[package.node]]
name = "cooper_pair_mechanism"
version = 3
belief = 0.92
content_hash = "sha256:e5f6a7b8..."

[[package.node]]
name = "phonon_mediated_attraction"
version = 1
belief = 0.88
content_hash = "sha256:c9d0e1f2..."

[[package]]
name = "anderson1987_rvb_theory"
version = "1.0.0"
content_hash = "sha256:1a2b3c4d..."

[[package.node]]
name = "resonating_valence_bond_state"
version = 2
belief = 0.71
content_hash = "sha256:5e6f7a8b..."
```

### 9.3 与 Cargo 的精确对应

| Cargo | Gaia | 说明 |
|-------|------|------|
| `[package]` name, version | `[package]` name, version | 包标识 |
| `[dependencies]` | `[dependencies]` | semver 范围声明 |
| `[[package]]` in Cargo.lock | `[[package]]` in Gaia.lock | 锁定的包版本 |
| `pub` items | `[exports]` nodes | 导出接口 |
| `[features]` | — | Gaia 用 belief 连续值替代 |
| `[workspace]` | — | 未来可支持多包 workspace |

---

## 10. CLI 工作流

### 10.1 命令总览

| 命令 | Cargo 等价物 | 说明 |
|------|-------------|------|
| `gaia init <name>` | `cargo new` | 创建新知识包 |
| `gaia add <package>` | `cargo add` | 添加依赖包 |
| `gaia add-node <content>` | — | 向包中添加命题 |
| `gaia add-edge --tail ... --head ...` | — | 向包中添加推理边 |
| `gaia propagate` | `cargo build` | 运行 BP 传播 |
| `gaia submit` | `cargo publish` | 提交到 server（review → merge） |
| `gaia outdated` | `cargo outdated` | 检测过期的依赖 |
| `gaia update` | `cargo update` | 更新依赖到兼容的最新版本 |
| `gaia search <query>` | `cargo search` | 搜索 server 上的包 |
| `gaia info <package>` | — | 查看包详情 |
| `gaia diff` | — | 查看当前环境与 base 的 belief diff |
| `gaia experiment create` | — | 创建 thought experiment 环境 |
| `gaia experiment promote` | — | 提升实验结果到 workspace |
| `gaia experiment discard` | — | 丢弃实验 |
| `gaia branch <name>` | `git branch` | 创建知识分支 |
| `gaia merge <branch>` | — | BP-based merge |

### 10.2 典型工作流

```bash
# 1. 创建新的研究包
gaia init agent_bcs_extension_2026
cd agent_bcs_extension_2026

# 2. 添加依赖（从 server 拉取知识包）
gaia add bcs1957_superconductivity ">=1.0"
gaia add anderson1987_rvb_theory ">=1.0"
# → 自动生成 Gaia.lock，缓存依赖包的节点/边到本地

# 3. 添加自己的命题和推理
gaia add-node "扩展 BCS 配对机制到高温超导体"
gaia add-edge \
    --tail "bcs1957_superconductivity::cooper_pair_mechanism" \
    --tail "local::extended_pairing_hypothesis" \
    --head "local::predicted_tc_for_material_class_x" \
    --reasoning "将 Cooper 对机制推广到强耦合极限..."

# 4. 运行 BP 传播
gaia propagate
# → 计算所有节点的 belief

# 5. 快速实验
gaia experiment create --override "bcs1957::cooper_pair_mechanism=1.0"
# "假设 Cooper 对机制完全正确"
gaia experiment propagate
gaia experiment diff        # 看假设对结论的影响
gaia experiment promote     # 满意 → 合入 workspace
# 或 gaia experiment discard  # 不满意 → 丢弃

# 6. 检查依赖更新
gaia outdated
# bcs1957_superconductivity: 1.2.0 -> 1.3.0 (minor)
gaia update
# → 拉取新版本，重新 propagate

# 7. 提交成果
gaia submit
# → 打包为 commit → server review → merge
```

### 10.3 纯本地工作流（无 server）

```bash
# 和 cargo new 不需要 cargo publish 一样
gaia init my_local_research
cd my_local_research

# 不配置 server，纯本地工作
gaia add-node "我的假设..."
gaia add-edge --tail local::hyp1 --head local::conclusion1
gaia propagate
gaia diff

# 所有功能在本地完整可用
# 未来想分享时再 gaia submit
```

---

## 11. Server API（Registry）

Server 作为 registry，提供包的发布、发现和版本管理。

### 11.1 包注册与发布

| API | Cargo 等价物 | 说明 |
|-----|-------------|------|
| `POST /packages` | `cargo publish` | 发布新包 |
| `PUT /packages/{name}/{version}` | `cargo publish`（新版本） | 发布新版本 |
| `GET /packages/{name}` | crates.io 包页面 | 包元数据和版本列表 |
| `GET /packages/{name}/{version}` | — | 特定版本的完整内容 |
| `GET /packages/{name}/{version}/nodes` | — | 包内所有节点 |
| `GET /packages/{name}/{version}/exports` | — | 包的导出节点 |

### 11.2 搜索与发现

| API | 说明 |
|-----|------|
| `POST /search/packages` | 按关键词/主题搜索包 |
| `GET /packages/{name}/dependents` | 谁依赖了这个包 |
| `GET /packages/{name}/dependencies` | 这个包依赖谁 |
| `GET /packages/{name}/impact` | 变更影响分析 |

### 11.3 版本管理

| API | 说明 |
|-----|------|
| `GET /snapshots` | 快照列表 |
| `GET /snapshots/{id}` | 快照详情 |
| `POST /snapshots` | 手动创建快照 |
| `GET /diff/snapshots/{a}/{b}` | 快照间 belief diff |

### 11.4 环境管理

| API | 说明 |
|-----|------|
| `POST /environments` | 创建环境（branch / experiment） |
| `GET /environments/{id}` | 查看环境状态 |
| `POST /environments/{id}/propagate` | 环境内 BP |
| `GET /environments/{id}/diff` | 与基底的 belief diff |
| `POST /environments/{id}/promote` | 提升环境 |
| `DELETE /environments/{id}` | 丢弃环境 |
| `POST /environments/{id}/merge` | BP-based merge |

### 11.5 依赖管理

| API | 说明 |
|-----|------|
| `GET /packages/{name}/outdated` | 检测过期依赖 |
| `POST /packages/{name}/revalidate` | 重新验证兼容性 |
| `GET /nodes/{id}/dependents` | 谁依赖了这个节点（跨包） |

### 11.6 Commit 工作流（复用现有）

包的发布通过现有的 commit 工作流实现：

```
gaia submit → POST /commits（包含包元数据）
           → server review（自动 + 人工）
           → merge（写入 registry）
```

---

## 12. Standalone 与 Connected 模式

### 12.1 核心原则

每个 Gaia 实例（无论是 server 还是 CLI）都是 **完整的**。就像每个 Git clone 是完整的仓库，每个 Gaia 实例可以独立运行全部功能。

Server 是 **可选的** — 纯本地使用完全支持，就像 `cargo new` 不需要 `cargo publish`。

### 12.2 两种模式

| | Standalone 模式 | Connected 模式 |
|---|---|---|
| Server | 不需要 | 连接到 Gaia Server |
| 存储 | 本地 LanceDB + 本地包存储 | 本地缓存 + server registry |
| 版本历史 | 完全在本地 | 本地有工作副本，server 有完整历史 |
| BP | 本地全量计算 | 本地子图计算，边界条件来自 server |
| 包发布 | 不支持（纯本地） | `gaia submit` → server |
| 包依赖 | 只能依赖本地包 | 可以依赖 server 上的任何包 |
| 适用场景 | 个人研究、离线使用、教学 | 团队协作、知识共享 |

### 12.3 Connected 模式下的本地角色

当连接到 server 时，本地实例是 server 的一个 **环境**（base + overlay）：

```
Server（registry，source of truth）
  └── Local（环境 = server snapshot + local overlay）
        ├── 缓存的 server 包（只读）
        ├── 本地新增的节点/边（overlay）
        └── 本地实验/分支（临时环境）
```

本地 **不使用 Git 作为后端**。本地存储是：
- **缓存**：从 server 拉取的包数据（类似 `~/.cargo/registry/cache`）
- **Overlay**：本地新增的内容（等待 submit 到 server）
- **配置**：Gaia.toml / Gaia.lock

### 12.4 离线支持

Connected 模式下也支持离线工作：

```
在线时: gaia add bcs1957_superconductivity
        → 从 server 下载包到本地缓存

离线时: 继续基于缓存的包工作
        gaia add-node / gaia add-edge / gaia propagate 全部本地执行
        gaia outdated 只检查本地缓存

重新上线: gaia submit → 提交累积的工作
          gaia update → 拉取最新的包版本
```

### 12.5 子图边界问题

本地只持有图的子集，需要处理边界：

```
server 上的完整图:  A ── B ── C ── D ── E
本地依赖了 B, C, D:        [B ── C ── D]
                              ^           ^
                          边界节点     边界节点
```

边界节点（B, D）的 belief 使用 server 上的值作为固定约束。本地 BP 在子图内部传播，边界条件固定。这类似有限元分析中的边界条件处理。

当 server 上的边界节点 belief 更新时（`gaia outdated` 检测到），本地 BP 需要以新的边界条件重跑。

---

## 13. 仓库结构：gaia-core / gaia-server / gaia-cli

### 13.1 三包架构

将 Gaia 拆分为三个独立的包（crate），职责清晰：

```
gaia-core/                    # 共享核心库
├── models.py                 # Node, HyperEdge, Commit, Package 等数据模型
├── bp/                       # Belief Propagation 引擎
│   ├── factor_graph.py
│   └── message_passing.py
├── versioning/               # 版本管理逻辑
│   ├── semver.py
│   ├── content_hash.py
│   └── change_classifier.py
├── environment/              # 统一环境模型
│   ├── base.py
│   ├── overlay.py
│   └── snapshot.py
├── package/                  # Knowledge Package 逻辑
│   ├── manifest.py           # Gaia.toml 解析
│   ├── lockfile.py           # Gaia.lock 解析/生成
│   └── resolver.py           # 依赖解析
└── storage/                  # 存储抽象层
    ├── lance_store.py
    └── vector_index.py

gaia-server/                  # FastAPI Registry 服务
├── app.py                    # FastAPI application
├── routes/
│   ├── packages.py           # 包注册/发布/查询
│   ├── commits.py            # Commit 工作流（复用现有）
│   ├── environments.py       # 环境管理
│   ├── search.py             # 搜索
│   └── read.py               # 读取
├── engines/
│   ├── commit_engine.py      # 提交引擎
│   ├── search_engine.py      # 搜索引擎
│   └── inference_engine.py   # BP 推断引擎
├── registry/                 # Registry 逻辑
│   ├── publish.py
│   ├── resolve.py
│   └── index.py
└── storage/                  # 服务端存储（LanceDB + Neo4j）
    ├── neo4j_store.py
    └── manager.py

gaia-cli/                     # 命令行工具
├── main.py                   # CLI 入口
├── commands/
│   ├── init.py               # gaia init
│   ├── add.py                # gaia add / add-node / add-edge
│   ├── propagate.py          # gaia propagate
│   ├── submit.py             # gaia submit
│   ├── outdated.py           # gaia outdated
│   ├── update.py             # gaia update
│   ├── search.py             # gaia search
│   ├── diff.py               # gaia diff
│   ├── experiment.py         # gaia experiment *
│   └── branch.py             # gaia branch / merge
├── workspace/                # 本地 workspace 管理
│   ├── config.py             # 读写配置
│   ├── cache.py              # 包缓存
│   └── overlay.py            # 本地 overlay
└── client/                   # Server API 客户端
    └── registry_client.py
```

### 13.2 依赖关系

```
gaia-cli ──→ gaia-core
    │
    └──→ gaia-server (仅 HTTP 客户端，不依赖 server 代码)

gaia-server ──→ gaia-core

gaia-core ──→ (无内部依赖)
```

关键约束：
- `gaia-core` 不依赖任何 server 或 CLI 代码
- `gaia-cli` 通过 HTTP 与 `gaia-server` 通信，不直接 import server 代码
- `gaia-server` 和 `gaia-cli` 都依赖 `gaia-core` 的模型和 BP 引擎

### 13.3 与现有代码的映射

| 现有代码 | 新位置 | 说明 |
|---------|--------|------|
| `libs/models.py` | `gaia-core/models.py` | 核心数据模型 |
| `libs/storage/lance_store.py` | `gaia-core/storage/lance_store.py` | LanceDB 存储 |
| `libs/storage/neo4j_store.py` | `gaia-server/storage/neo4j_store.py` | Neo4j 仅 server 需要 |
| `services/commit_engine/` | `gaia-server/engines/commit_engine.py` | Commit 引擎 |
| `services/search_engine/` | `gaia-server/engines/search_engine.py` | 搜索引擎 |
| `services/inference_engine/` | `gaia-core/bp/` + `gaia-server/engines/` | BP 核心在 core，调度在 server |
| `services/gateway/` | `gaia-server/` | FastAPI 网关 |

### 13.4 渐进迁移

不需要一次性重构。可以分步进行：

1. 先提取 `gaia-core` — 把 `libs/` 独立为可安装的包
2. 现有 `services/` 重命名为 `gaia-server`
3. 新建 `gaia-cli` — 从零开始，依赖 `gaia-core`

---

## 14. 与其他设计的关系

| 设计文档 | 关系 |
|---------|------|
| [scaling_belief_propagation.md](scaling_belief_propagation.md) | 大规模 BP 是 environment propagate / merge 的计算引擎；增量 BP 用于变更传播；子图 BP + 边界条件用于本地 workspace |
| [agent_verifiable_memory.md](agent_verifiable_memory.md) | Agent 的 workspace = 一个 Knowledge Package 的开发环境；dry-run = thought experiment（统一环境模型的一种）|
| [verification_providers.md](verification_providers.md) | Verification 更新 edge probability → 触发包的 minor/major 版本变更 + BP 传播 |
| [question_as_discovery_context.md](question_as_discovery_context.md) | Question 随 edge 版本一起管理；experiment 中的推理也携带 question；question 可以是包元数据的一部分 |
| [text_structuring_service.md](text_structuring_service.md) | 论文提取的结果直接打包为 `paper-extract` 类型的 Knowledge Package |

---

## 15. 实施路线图

### Phase 1：gaia-core 提取 + Node/Edge 版本管理

- 将 `libs/` 提取为独立的 `gaia-core` 包
- Node/Edge 增加 `version`, `content_hash` 字段
- ModifyNode/ModifyEdge 创建新版本而非覆盖
- 历史查询 API：`GET /nodes/{id}/history`
- 利用 LanceDB 原生 dataset versioning

### Phase 2：Knowledge Package 数据模型

- 定义 Package 数据模型（名称、版本、导出、依赖）
- Gaia.toml / Gaia.lock 格式规范
- 包的创建、存储和读取
- 导出节点管理

### Phase 3：Dependency Pinning + 变更分类

- Edge 增加 `tail_pins`, `head_pins`, `stale` 字段
- Edge 创建时自动 pin 到 tail/head 当前版本
- Node 更新时自动标记依赖 edge 为 stale
- 变更分类（embedding distance + LLM）
- `GET /packages/{name}/outdated`

### Phase 4：Belief Snapshot + 统一环境模型

- Snapshot 数据模型与存储
- Merge 后自动创建 snapshot
- Snapshot diff API
- 统一 Environment 模型（workspace / branch / experiment）
- 环境栈（嵌套环境）

### Phase 5：gaia-cli

- CLI 框架和基础命令（`gaia init`, `gaia add`, `gaia propagate`）
- 本地 workspace 管理（缓存、overlay）
- Standalone 模式完整可用
- `gaia submit` / `gaia outdated` / `gaia update`

### Phase 6：Server Registry

- 包注册与发布 API
- 搜索与发现
- Connected 模式
- `gaia-server` 独立部署

### Phase 7：BP-based Merge + Knowledge Branch

- Branch 创建与管理
- 3-way belief merge + BP resolve
- Branch diff
- 跨包 merge 传播
